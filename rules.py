"""
rules.py — Single source of truth for Six Nations game rules.

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! CRITICAL MAINTENANCE CONTRACT                                            !!
!!                                                                          !!
!! This module is the ONLY place where move legality and action            !!
!! consequences are defined.  main.py (human player), bot.py (AI scorer),  !!
!! and evolution.py (headless tournament) ALL import from here.            !!
!!                                                                          !!
!! If you add a new move type, change a cooldown rule, or alter who can    !!
!! move on a given turn, YOU MUST DO IT HERE AND ONLY HERE.                !!
!!                                                                          !!
!! Implementing a rule in more than one place WILL cause the bot and the   !!
!! human to play different games.  This is exactly how the diplomacy       !!
!! cooldown bug was introduced: cooldowns were applied in the human handler !!
!! but not in the bot handler, so the human was constrained and the bot    !!
!! was not.  The fix (Phase 1–3 of the bot diplomacy refactor) required    !!
!! auditing three separate files.  Do not repeat that mistake.             !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

HOW TO ADD A NEW MOVE TYPE
--------------------------
1. Add the execution branch to execute_action() below.
2. move_consequence() already handles the general case ('pass' → no
   cooldown, everything else → full cooldown).  Only override if the new
   type needs different cooldown semantics.
3. If the new type has eligibility restrictions beyond the standard
   ghost/cooldown filter, extend get_eligible_nations().
4. All callers (main.py, bot._execute, evolution.HeadlessGame.play) will
   pick up the change automatically — do NOT touch those files for rules.

Design contract
---------------
* Legality  — which nations/hexes are legal for a given player/turn
* Execution — apply an action to the grid, return what cooldowns result
* This module does NOT drive rendering or scoring (those stay in main.py /
  bot.py), and it does NOT import pygame.

move_consequence(action_type, moved_nation)
    -> (player_nation_or_None, global_cooldown_name_or_None)

    Encodes the cooldown rule for every action type in one place:
      - pass   : (None, None)          -- no cooldown generated
      - all others: (moved_nation, moved_nation.color_name)
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Eligibility — which nations may a player act on this turn?
# ---------------------------------------------------------------------------

def get_eligible_nations(player, global_cooldown_name, nation_list):
    """Return nations the player is allowed to act on this turn.

    A nation is ineligible if:
      - It is on the player's personal move cooldown, OR
      - It is the globally-blocked nation (last moved by the opponent), OR
      - It has become a ghost nation (sovereign destroyed).

    This is the single canonical implementation shared by all callers
    (main.py human turn, bot._gather_actions, _lookahead_best, etc.).
    """
    return [
        n for n in nation_list
        if not player.nation_on_cooldown(n)
        and (global_cooldown_name is None or n.color_name != global_cooldown_name)
        and not n.is_ghost
    ]


# ---------------------------------------------------------------------------
# Cooldown consequence — what does each action type generate?
# ---------------------------------------------------------------------------

def move_consequence(action_type: str, moved_nation):
    """Return the cooldown consequence of completing an action.

    Returns
    -------
    (player_cooldown_nation, new_global_cooldown_name)
        player_cooldown_nation  : Nation object to add to player.cooldown,
                                  or None if no player cooldown generated.
        new_global_cooldown_name: color_name string to set as global block,
                                  or None if the global block should be cleared.

    Rules
    -----
    PASS    -> (None, None)      No nation moved; existing global block cleared.
    Others  -> (moved_nation, moved_nation.color_name)
    """
    if action_type == 'pass' or moved_nation is None:
        return None, None
    return moved_nation, moved_nation.color_name


# ---------------------------------------------------------------------------
# Full action execution
# ---------------------------------------------------------------------------

def execute_action(grid, action, dipl_state=None, turn_number=None):
    """Execute one scored action tuple and return consequences.

    This is the canonical implementation of action execution used by both
    human (main.py) and bot (bot.py / evolution.py) code paths.

    Parameters
    ----------
    grid       : MapGrid — the live board state (mutated in-place).
    action     : tuple  — (score, action_type, *payload[, path_label])
    dipl_state : DiplomacyState | None — needed for diplomacy locking.
    turn_number: int | None — needed for recruit cooldown stamping.

    Returns
    -------
    (moved_nation, action_type_str, description, player_cd_nation, new_global_cd)

    moved_nation   : Nation that moved, or None on failure / pass.
    action_type_str: canonical string ('move', 'attack', 'recruit', ..., 'pass').
    description    : human-readable log string.
    player_cd_nation  : Nation to add to player.cooldown (None = no cooldown).
    new_global_cd  : color_name to set as global_cooldown_name (None = clear).

    Callers are responsible for:
      - Calling player.add_to_cooldown(player_cd_nation) if not None.
      - Setting global_cooldown_name = new_global_cd.
      - Calling dipl_panel.tick_cooldowns() / dipl_state.tick_cooldowns().
      - Checking game-end condition.
      - Advancing turn / transitioning game state.
    """
    from settings import DEPLOYMENT

    score, atype, *rest = action
    # Strip optional trailing path label ('intent' / 'random' / 'deceptive')
    if rest and isinstance(rest[-1], str) and rest[-1] in ('intent', 'random', 'deceptive'):
        payload, path = rest[:-1], rest[-1]
        tag = f"[{path}]"
    else:
        payload = rest
        tag = "[move]"

    # -- PASS ----------------------------------------------------------------
    if atype == 'pass':
        return None, 'pass', f"{tag} Pass (no legal move).", None, None

    # -- ATTACK --------------------------------------------------------------
    if atype == 'attack':
        unit, coord = payload[0], payload[1]
        success, msg, _ = grid.resolve_attack(unit, *coord)
        if success:
            nation = unit.nation
            p_cd, g_cd = move_consequence('attack', nation)
            return nation, 'attack', \
                f"{tag} Attack {nation.color_name} -> {coord}  score={score:.0f}  {msg}", \
                p_cd, g_cd
        return None, None, f"{tag} Attack failed: {msg}", None, None

    # -- MOVE ----------------------------------------------------------------
    if atype == 'move':
        unit, coord = payload[0], payload[1]
        grid.apply_move(unit, *coord)
        nation = unit.nation
        p_cd, g_cd = move_consequence('move', nation)
        return nation, 'move', \
            f"{tag} Move {nation.color_name} -> {coord}  score={score:.0f}", \
            p_cd, g_cd

    # -- RECRUIT -------------------------------------------------------------
    if atype == 'recruit':
        nation, coord = payload[0], payload[1]
        eff_turn = turn_number if turn_number is not None else getattr(grid, 'turn_number', None)
        grid.recruit_army(nation, *coord, turn_number=eff_turn)
        p_cd, g_cd = move_consequence('recruit', nation)
        return nation, 'recruit', \
            f"{tag} Recruit {nation.color_name} at {coord}", \
            p_cd, g_cd

    # -- PROMOTE (champion) --------------------------------------------------
    if atype == 'promote':
        nation, coord = payload[0], payload[1]
        armies_here = [a for a in grid.armies.get(coord, [])
                       if a.nation.color_name == nation.color_name]
        if armies_here:
            grid.promote_to_champion(armies_here[0])
            p_cd, g_cd = move_consequence('promote', nation)
            return nation, 'promote', \
                f"{tag} Promote champion {nation.color_name} at {coord}", \
                p_cd, g_cd
        return None, None, f"{tag} Promote: no army found at {coord}", None, None

    # -- PROMOTE KNIGHT ------------------------------------------------------
    if atype == 'promote_knight':
        nation, coord = payload[0], payload[1]
        armies_here = [a for a in grid.armies.get(coord, [])
                       if a.nation.color_name == nation.color_name]
        if armies_here:
            grid.promote_to_knight(armies_here[0])
            p_cd, g_cd = move_consequence('promote_knight', nation)
            return nation, 'promote_knight', \
                f"{tag} Promote knight {nation.color_name} at {coord}", \
                p_cd, g_cd
        return None, None, f"{tag} Promote knight: no army found at {coord}", None, None

    # -- DIPLOMACY -----------------------------------------------------------
    if atype == 'diplomacy':
        # payload = (nation_a, nation_b, new_stance[, dipl_state_override])
        nation_a, nation_b, new_stance = payload[0], payload[1], payload[2]
        dipl_state_local = payload[3] if len(payload) > 3 else dipl_state

        if new_stance == 'ally':
            nation_a.set_ally(nation_b)
        elif new_stance == 'enemy':
            nation_a.set_enemy(nation_b)
        else:
            nation_a.set_neutral(nation_b)

        if dipl_state_local is not None:
            if new_stance == 'neutral':
                dipl_state_local.unlock_pair(nation_a, nation_b)
            else:
                dipl_state_local.lock_pair(nation_a, nation_b)

        try:
            from map import reconcile_stance_change
            import factions as _factions
            all_nations = list(getattr(grid, 'nations', _factions.NATIONS))
            events = reconcile_stance_change(grid, nation_a, nation_b, new_stance, all_nations)
            if DEPLOYMENT == 'DEBUG':
                for ev in events:
                    print(f"[rules-diplomacy] {ev}")
        except (ImportError, AttributeError):
            pass

        p_cd, g_cd = move_consequence('diplomacy', nation_a)
        return nation_a, 'diplomacy', \
            f"{tag} Diplomacy: {nation_a.color_name} -> {new_stance} -> {nation_b.color_name}", \
            p_cd, g_cd

    # -- UNKNOWN -------------------------------------------------------------
    return None, None, f"{tag} Unknown action type: {atype!r}", None, None
