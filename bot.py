"""
Six Nations — Bot AI  (Phase 6)

ORIGINAL BOT (Play vs BOT):
  Uses a blend of random and intent moves controlled by
  settings.BOT_INITIAL_RANDOM:
    Turn  1 → (1 - BOT_INITIAL_RANDOM) intent  [default 40% intent / 60% random]
    Turn 50 → ~90% intent, 10% random
    (linear interpolation, capped at each end)

EVOLVED BOT (Play vs EVOLVED BOT):
  Uses evolved weights that multiply the base scores below, AND
  a custom random/deceptive/intent blend controlled by the evolved
  config's w_random and w_deceptive genes.  For example, the first
  generation of evolved bots converged on w_random=0.0 and
  w_deceptive=0.0 (pure intent, no random moves at all).

Base intent priority scores (approximate):
  1000+  Kill an enemy sovereign (bot's 3 target enemies)
   400   Kill an enemy champion  (same targets)
   150   Kill an enemy army      (same targets)
   350   Move allied sovereign away from a trap
   250   Move allied sovereign to a supported hex
   200+  Any other kill
   120   Position allied unit adjacent to enemy sovereign
    90   Move allied champion closer to enemy
    80   Move allied army closer to enemy / push enemy sov into danger
    70   Promote allied army to champion
    60   Muster (recruit) allied army
    50   Keep allied champion on a supported hex
    40   Move enemy champion off a supported hex
     5   Any other legal move (random tie-break within same score)

WEIGHT MULTIPLIERS:  The scoring functions accept an optional `weights`
dict whose keys multiply the base scores above.  For example, if
weights = {'kill_enemy': 2.5, 'muster_promote': 0.0}, killing an enemy
sovereign scores 1000 × 2.5 = 2500, and recruit/promote are zeroed out.
When weights is None (default), all multipliers are 1.0.  See
evolution.py and BotConfig for the full set of weight genes.

The bot also keeps a BotMemory record of every opponent move for analysis.
"""

import random
import settings


# ---------------------------------------------------------------------------
# Move record (opponent history)
# ---------------------------------------------------------------------------

class BotMemory:
    """Stores a record of every move the human player made, and tracks suspicion scores per nation."""

    def __init__(self, debug=False):
        self.moves         = []   # chronological move records
        self.nation_scores = {}   # ring_index -> int score
        self.debug         = debug

    def record(self, turn_number, nation, unit_type_str, from_hex, to_hex, action_type):
        """
        Record one human move.
        unit_type_str : 'army' | 'champion' | 'sovereign' | None (for recruit/promote)
        action_type   : 'move' | 'attack' | 'recruit' | 'promote'
        """
        self.moves.append({
            'turn':   turn_number,
            'nation': nation.ring_index,
            'name':   nation.color_name,
            'utype':  unit_type_str,
            'from':   from_hex,
            'to':     to_hex,
            'action': action_type,
        })

    # ------------------------------------------------------------------
    # Scoring API
    # ------------------------------------------------------------------

    def add_score(self, ring_index, points, nation_names=None):
        """
        Add (or subtract) suspicion points for a nation.
        When points > 0, half (floor) also propagates to each adjacent ally
        on the diplomacy ring, since players tend to move their allies too.
        Negative penalties do NOT propagate to allies.
        nation_names: optional list of color-name strings indexed by ring_index,
                      used for debug output.
        """
        names = nation_names or {}

        def _name(ri):
            if isinstance(names, list) and ri < len(names):
                return names[ri]
            return str(ri)

        old = self.nation_scores.get(ring_index, 0)
        self.nation_scores[ring_index] = old + points
        new = self.nation_scores[ring_index]
        if self.debug:
            sign = '+' if points >= 0 else ''
            print(f"  [Score] {_name(ring_index)}: {old} {sign}{points} -> {new}")

        if points > 0:
            ally_pts = points // 2
            if ally_pts > 0:
                for ally_ri in ((ring_index - 1) % 6, (ring_index + 1) % 6):
                    old_a = self.nation_scores.get(ally_ri, 0)
                    self.nation_scores[ally_ri] = old_a + ally_pts
                    if self.debug:
                        print(f"  [Score]   ally {_name(ally_ri)}: {old_a} +{ally_pts} -> {self.nation_scores[ally_ri]}")

    def guess_faction(self, nation_list, exclude_ring_indices=()):
        """
        Return the Nation with the highest suspicion score,
        or None if no moves have been recorded yet.
        exclude_ring_indices: iterable of ring_index values to skip
        (use to prevent the bot from guessing its own secret nation).
        """
        if not self.nation_scores:
            return None
        candidates = {
            ri: pts
            for ri, pts in self.nation_scores.items()
            if ri not in exclude_ring_indices
        }
        if not candidates:
            return None
        best_ri = max(candidates, key=lambda ri: candidates[ri])
        for n in nation_list:
            if n.ring_index == best_ri:
                return n
        return None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def nation_move_counts(self):
        """Return dict {ring_index: count} of how often human moved each nation."""
        counts = {}
        for m in self.moves:
            ri = m['nation']
            counts[ri] = counts.get(ri, 0) + 1
        return counts

    def most_moved_nations(self, top_n=3):
        """Return list of (ring_index, count) sorted by count descending."""
        counts = self.nation_move_counts()
        return sorted(counts.items(), key=lambda x: -x[1])[:top_n]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _intent_prob(turn_number: int) -> float:
    """Probability of making a strategic intent move on this turn.

    Interpolates linearly from (1 - settings.BOT_INITIAL_RANDOM) at turn 1
    up to 0.90 at turn 50.  BOT_INITIAL_RANDOM=0.60 → starts at 40% intent.
    """
    t         = min(max(turn_number, 1), 50)
    start_p   = 1.0 - settings.BOT_INITIAL_RANDOM   # intent prob at turn 1
    return start_p + (t - 1) / 49.0 * (0.90 - start_p)


def _axial_dist(q1, r1, q2, r2) -> int:
    return (abs(q1 - q2) + abs(r1 - r2) + abs((q1 + r1) - (q2 + r2))) // 2


def _nearest_enemy_sov_dist(grid, q, r, enemy_ring_set) -> int:
    """Distance from (q,r) to the nearest live sovereign in enemy_ring_set."""
    best = 99
    for slist in grid.sovereigns.values():
        for s in slist:
            if s.nation.ring_index in enemy_ring_set:
                d = _axial_dist(q, r, s.q, s.r)
                best = min(best, d)
    return best


def _eligible_nations(player, global_cooldown_idx, nation_list):
    return [
        n for n in nation_list
        if not player.nation_on_cooldown(n)
        and (global_cooldown_idx is None or n.ring_index != global_cooldown_idx)
        and not n.is_ghost
    ]


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _enemy_set(ring_index):
    """Return the 3 ring-indices that are enemies of the given nation."""
    return {(ring_index + 2) % 6, (ring_index + 3) % 6, (ring_index + 4) % 6}


def _adaptive_sovereign_adjustments(grid, actions, bot_ri, suspected_human_ri,
                                    turn_number, nation_list=None, adaptive_turn=None):
    """
    Apply sovereign-targeting intelligence based on the suspected human faction:

    Rule 1 — Hunt the suspected human sovereign (after adaptive_turn):
      If a legal attack would kill a sovereign of the suspected human faction,
      give that action top priority (+2000).

    Rule 2 — Don't hand the human the game:
      - If an attack would kill a sovereign that is an enemy of the suspected human
        and NOT an enemy of the bot (pure human benefit): completely suppress it (-9999.0).
      - If the attack kills a shared enemy sovereign and the human is 1 kill away:
        - If bot is also 1 kill away: ALLOW (tie attempt).
        - If bot is not 1 kill away: completely suppress it (-9999.0) so it doesn't give
          the human a solo victory.
    """
    if suspected_human_ri is None:
        return actions

    bot_enemy_ri   = _enemy_set(bot_ri)
    human_enemy_ri = _enemy_set(suspected_human_ri)

    # Count how many of the suspected human's and bot's 3 targets are already ghost nations
    human_kills_so_far = 0
    bot_kills_so_far   = 0
    if nation_list:
        human_kills_so_far = sum(
            1 for n in nation_list
            if n.ring_index in human_enemy_ri and n.is_ghost
        )
        bot_kills_so_far = sum(
            1 for n in nation_list
            if n.ring_index in bot_enemy_ri and n.is_ghost
        )
    # If human already has 1 kill, any remaining human-target sovereign kill wins for them
    human_one_away = (human_kills_so_far >= 1)
    # If bot also has 1 kill, killing a shared target gives a tie — that's acceptable
    bot_one_away   = (bot_kills_so_far >= 1)

    cutoff = adaptive_turn if adaptive_turn is not None else settings.BOT_ADAPTIVE_TURN
    is_adaptive_phase = (turn_number >= cutoff)

    result = []
    for action in actions:
        score, atype, *payload = action
        if atype == 'attack':
            unit, coord = payload[0], payload[1]
            tq, tr = coord
            target_sovs = grid.sovereigns.get((tq, tr), [])
            for sov in target_sovs:
                # Only apply adjustments if the attacking unit can legally attack this sovereign
                if not unit.nation.is_enemy(sov.nation):
                    continue
                sov_ri = sov.nation.ring_index

                if sov_ri == suspected_human_ri and is_adaptive_phase:
                    # Rule 1: hunt the suspected human's sovereign
                    score += 2000.0

                elif sov_ri in human_enemy_ri:
                    if sov_ri not in bot_enemy_ri:
                        # Pure human benefit, not a bot target — forbid completely
                        if is_adaptive_phase or human_one_away:
                            score = -9999.0
                    elif human_one_away and bot_one_away:
                        # Shared target, both one kill away → tie result — allow
                        score += 1000.0
                    elif human_one_away:
                        # Would give human solo win on the spot — forbid completely
                        score = -9999.0
                    # else: shared target and human needs 2+ kills — allow normal scoring

        result.append((score, atype, *payload))
    return result


def _score_attack(grid, attacker, tq, tr, enemy_ring_set, allied_ring_set=None,
                   weights=None) -> float:
    """Score for attacker targeting hex (tq, tr).

    weights: optional dict with 'kill_enemy' multiplier.  When None every
    multiplier defaults to 1.0 (original hardcoded behaviour).
    """
    from armies    import Army
    from champions import Champion, Sovereign

    w_kill = (weights or {}).get('kill_enemy', 1.0)

    nation   = attacker.nation
    e_sovs   = [s for s in grid.sovereigns.get((tq, tr), []) if nation.is_enemy(s.nation)]
    e_champs = [c for c in grid.champions.get((tq, tr), [])  if nation.is_enemy(c.nation)]
    e_armies = [a for a in grid.armies.get((tq, tr), [])     if nation.is_enemy(a.nation)]

    if e_sovs:
        ri    = e_sovs[0].nation.ring_index
        # NEVER attack the bot's own secret nation's sovereign
        if allied_ring_set and ri in allied_ring_set:
            return -9999.0
        score = (1000 if ri in enemy_ring_set else 250) * w_kill
    elif e_champs:
        ri    = e_champs[0].nation.ring_index
        score = (400  if ri in enemy_ring_set else 100) * w_kill
    elif e_armies:
        ri    = e_armies[0].nation.ring_index
        score = (150  if ri in enemy_ring_set else 50) * w_kill
    else:
        score = 0

    if grid.is_supported(attacker):
        score += 20

    return float(score)


def _score_move(grid, unit, tq, tr, enemy_ring_set, allied_ring_set,
                weights=None) -> float:
    """Score for moving unit to (tq, tr).

    weights: optional dict with multiplier keys:
      'advance_allied'       — moving allied armies/champions toward enemy
      'protect_sovereign'    — protecting allied sovereigns
      'champion_support'     — keeping allied champions on supported hexes
      'endanger_enemy_sov'   — pushing enemy sovereigns toward danger
      'unsupport_enemy_champ'— moving enemy champions off supported hexes
    When None every multiplier defaults to 1.0 (original hardcoded behaviour).
    """
    from armies    import Army
    from champions import Champion, Sovereign

    w = weights or {}
    w_advance   = w.get('advance_allied', 1.0)
    w_protect   = w.get('protect_sovereign', 1.0)
    w_champ_sup = w.get('champion_support', 1.0)
    w_danger    = w.get('endanger_enemy_sov', 1.0)
    w_unsup_ch  = w.get('unsupport_enemy_champ', 1.0)
    w_territory = w.get('claim_territory', 1.0)

    nation    = unit.nation
    is_allied = nation.ring_index in allied_ring_set
    score     = 0.0

    if isinstance(unit, Sovereign):
        if is_allied:
            if grid.is_trapped(unit):
                score += 350 * w_protect
            elif not grid.is_supported(unit):
                allies_here = sum(
                    1 for lst in grid.get_units_at(tq, tr).values()
                    for u in lst if not u.nation.is_enemy(nation) and u is not unit
                )
                score += (250 if allies_here > 0 else 25) * w_protect
        else:
            # Non-allied (target) sovereign — push toward center & threats
            curr_threats = sum(
                1 for nq, nr in grid.get_neighbors(unit.q, unit.r)
                if grid._has_enemy_unit_at(nq, nr, nation)
            )
            new_threats = sum(
                1 for nq, nr in grid.get_neighbors(tq, tr)
                if grid._has_enemy_unit_at(nq, nr, nation)
            )
            if new_threats > curr_threats:
                score += (80 + (new_threats - curr_threats) * 20) * w_danger
            else:
                score += 5

            # Center-proximity bonus: push target sovereigns toward center
            old_d = max(abs(unit.q), abs(unit.r), abs(unit.q + unit.r))
            new_d = max(abs(tq), abs(tr), abs(tq + tr))
            if new_d < old_d:
                # Bigger bonus for getting closer to center
                score += (60 + (old_d - new_d) * 30) * w_danger
                # Extra bonus for reaching the inner ring
                if new_d <= 1:
                    score += 30 * w_danger

    elif isinstance(unit, Champion):
        if is_allied:
            old_d = _nearest_enemy_sov_dist(grid, unit.q, unit.r, enemy_ring_set)
            new_d = _nearest_enemy_sov_dist(grid, tq, tr, enemy_ring_set)
            if new_d < old_d:
                score += (90 + (old_d - new_d) * 10) * w_advance
            allies_at = sum(
                1 for lst in grid.get_units_at(tq, tr).values()
                for u in lst if not u.nation.is_enemy(nation) and u is not unit
            )
            if allies_at > 0:
                score += 50 * w_champ_sup
        else:
            if grid.is_supported(unit):
                allies_at = sum(
                    1 for lst in grid.get_units_at(tq, tr).values()
                    for u in lst if not u.nation.is_enemy(nation)
                )
                if allies_at == 0:
                    score += 40 * w_unsup_ch

    elif isinstance(unit, Army):
        if is_allied:
            old_d = _nearest_enemy_sov_dist(grid, unit.q, unit.r, enemy_ring_set)
            new_d = _nearest_enemy_sov_dist(grid, tq, tr, enemy_ring_set)
            if new_d < old_d:
                score += (80 + (old_d - new_d) * 10) * w_advance
            else:
                score += 5
        else:
            score += 2

    # Territory-claiming bonus (capturing neutral or seizing enemy hexes)
    if hasattr(grid, 'tile_control'):
        curr_owner = grid.tile_control.get((tq, tr))
        unit_ri = nation.ring_index
        if curr_owner is None:
            # Claiming neutral territory
            if is_allied:
                score += 40.0 * w_territory
            else:
                score += 10.0 * w_territory
        elif curr_owner != unit_ri:
            from factions import NATIONS
            owner_ri = curr_owner.ring_index if hasattr(curr_owner, 'ring_index') else curr_owner
            owner_nation = NATIONS[owner_ri]
            if nation.is_enemy(owner_nation) and isinstance(unit, (Army, Champion)):
                # Seizing enemy territory
                if is_allied:
                    score += 70.0 * w_territory
                elif curr_owner in enemy_ring_set:
                    score += 30.0 * w_territory

    score += random.uniform(0, 2)
    return score


# ---------------------------------------------------------------------------
# Action gathering
# ---------------------------------------------------------------------------

def _gather_actions(grid, bot_player, global_cooldown_idx, nation_list,
                    suspected_human_ri=None, turn_number=0, weights=None):
    """
    Build a scored list of all legal bot actions.
    Returns list of (score, action_type, *payload).
    Applies adaptive sovereign strategy after BOT_ADAPTIVE_TURN.

    weights: optional dict of score-category multipliers (see _score_attack,
    _score_move).  Also supports 'muster_promote' key for recruit/promote.
    When None, original hardcoded scores are used.
    """
    eligible        = _eligible_nations(bot_player, global_cooldown_idx, nation_list)
    bot_secret      = bot_player.secret_nation
    bot_ri          = bot_secret.ring_index
    enemy_ring_set  = {n.ring_index for n in bot_secret.enemy_nations(nation_list)}
    allied_ring_set = {n.ring_index for n in nation_list if not bot_secret.is_enemy(n)}

    w_muster = (weights or {}).get('muster_promote', 1.0)

    actions = []

    for nation in eligible:
        is_allied = nation.ring_index in allied_ring_set
        units     = grid.get_all_nation_units(nation)

        for unit in units:
            for coord in grid.get_valid_attacks(unit):
                s = _score_attack(grid, unit, *coord, enemy_ring_set,
                                  allied_ring_set=allied_ring_set,
                                  weights=weights)
                actions.append((s, 'attack', unit, coord))

            for coord in grid.get_valid_moves(unit, mover_secret_nation=bot_secret):
                s = _score_move(grid, unit, *coord, enemy_ring_set,
                                allied_ring_set, weights=weights)
                actions.append((s, 'move', unit, coord))

        for coord in grid.get_recruit_hexes(nation):
            s = (60.0 if is_allied else 15.0) * w_muster
            actions.append((s, 'recruit', nation, coord))

        for coord in grid.get_promote_hexes(nation):
            s = (70.0 if is_allied else 20.0) * w_muster
            actions.append((s, 'promote', nation, coord))

    # Apply adaptive sovereign intelligence
    adaptive_t = weights.get('adaptive_turn') if weights else None
    actions = _adaptive_sovereign_adjustments(
        grid, actions, bot_ri, suspected_human_ri, turn_number,
        nation_list=nation_list, adaptive_turn=adaptive_t)

    return actions


# ---------------------------------------------------------------------------
# Multi-ply lookahead (beam-search negamax)
# ---------------------------------------------------------------------------

def _map_action_to_snapshot(action, unit_map):
    """Remap an action's unit references from the original grid to a snapshot.

    action is (score, atype, unit_or_nation, coord[, ...]).
    For 'move'/'attack': payload[0] is a unit (Army/Champion/Sovereign).
    For 'recruit'/'promote': payload[0] is a Nation — no remapping needed.
    """
    score, atype, *rest = action
    if atype in ('move', 'attack'):
        original_unit = rest[0]
        mapped_unit = unit_map.get(id(original_unit), original_unit)
        return (score, atype, mapped_unit, *rest[1:])
    return action


def _lookahead_best(grid, bot_player, global_cooldown_idx, nation_list,
                    turn_number, suspected_opp_ri, weights,
                    depth, beam_width, mode='position', eval_weights=None,
                    hybrid_ratio=1.0):
    """Beam-search negamax / hybrid lookahead.

    depth: remaining plies to search (0 = evaluate immediate moves, 1 = 1 opponent counter, 2 = 2 counters).
    beam_width: how many top candidates to explore at deeper plies.
    mode: 'action' (score subtraction) or 'position' (board evaluation).
    hybrid_ratio: 0.0 = 100% move score, 1.0 = 100% positional board eval,
                  0.3..0.7 = blended hybrid scoring.

    Returns an action tuple (final_score, atype, *payload) or None.
    """
    from player import Player
    from evaluator import evaluate_position

    bot_secret = bot_player.secret_nation

    # Gather and score all actions (1-ply move scoring)
    actions = _gather_actions(grid, bot_player, global_cooldown_idx, nation_list,
                              suspected_human_ri=suspected_opp_ri,
                              turn_number=turn_number,
                              weights=weights)
    if not actions:
        return None

    # Filter disqualified
    valid = [a for a in actions if a[0] > -1000]
    if valid:
        actions = valid

    # If depth 0 and pure move scoring, return best immediately
    if depth <= 0 and (mode == 'action' or hybrid_ratio <= 0.0):
        best = max(a[0] for a in actions)
        threshold = (best * 0.85) if best > 0 else (best - 50)
        top_tier = [a for a in actions if a[0] >= threshold]
        return random.choice(top_tier)

    # Sort by 1-ply score, take top beam_width candidates
    actions.sort(key=lambda a: a[0], reverse=True)
    candidates = actions[:beam_width]

    best_net = float('-inf')
    best_action = None

    for action in candidates:
        my_move_score = action[0]

        # Snapshot the grid and remap the action
        snap, unit_map = grid.snapshot()
        mapped_action = _map_action_to_snapshot(action, unit_map)

        # Execute on the snapshot
        moved_nation, _, _ = _execute(snap, mapped_action)
        if moved_nation is None:
            continue

        # Simulate cooldown
        new_gci = moved_nation.ring_index

        # If depth == 0 with hybrid evaluation (evaluate position immediately without opponent counter)
        if depth <= 0:
            pos_score = evaluate_position(snap, bot_secret, nation_list, weights=eval_weights)
            net = (1.0 - hybrid_ratio) * my_move_score + hybrid_ratio * pos_score
            if net > best_net:
                best_net = net
                best_action = action
            continue

        # Depth >= 1: Simulate opponent response
        opp_nation = None
        if suspected_opp_ri is not None:
            for n in nation_list:
                if n.ring_index == suspected_opp_ri:
                    opp_nation = n
                    break

        if opp_nation is None:
            # No guess — evaluate our immediate position
            pos_score = evaluate_position(snap, bot_secret, nation_list, weights=eval_weights)
            if mode == 'action':
                net = my_move_score
            else:
                net = (1.0 - hybrid_ratio) * my_move_score + hybrid_ratio * pos_score
        elif mode == 'position' or hybrid_ratio > 0.0:
            # 2-STAGE TAPERED BEAM MINIMAX:
            # Round 1 (Plies 1 & 2): Full beam width (test top opponent counters against our move)
            # Round 2 (Plies 3 & 4): Tapered to 1 (principal variation follow-up sequence)
            fake_opp = Player(opp_nation, is_bot=True, player_id='lookahead_opp')
            opp_suspected_us = bot_secret.ring_index

            opp_actions = _gather_actions(
                snap, fake_opp, new_gci, nation_list,
                suspected_human_ri=opp_suspected_us,
                turn_number=turn_number + 1,
                weights=None)

            if not opp_actions:
                pos_score = evaluate_position(snap, bot_secret, nation_list, weights=eval_weights)
            else:
                opp_valid = [a for a in opp_actions if a[0] > -1000]
                if opp_valid:
                    opp_actions = opp_valid
                opp_actions.sort(key=lambda a: a[0], reverse=True)

                # Round 1 (Ply 2): explore top countermoves up to beam_width
                opp_beam = min(beam_width, len(opp_actions))
                if depth >= 3:
                    opp_beam = min(3, opp_beam)  # cap at 3 for 4-ply

                worst_pos_score = float('inf')

                for opp_idx in range(opp_beam):
                    best_opp_action = opp_actions[opp_idx]

                    if opp_beam == 1:
                        opp_snap = snap
                        opp_mapped_action = best_opp_action
                    else:
                        opp_snap, opp_unit_map = snap.snapshot()
                        opp_mapped_action = _map_action_to_snapshot(best_opp_action, opp_unit_map)

                    opp_moved, _, _ = _execute(opp_snap, opp_mapped_action)

                    if depth > 1 and opp_moved is not None:
                        # Round 2 - Ply 3: Tapered follow-up (our single best reply)
                        our_followups = _gather_actions(
                            opp_snap, bot_player, opp_moved.ring_index, nation_list,
                            suspected_human_ri=suspected_opp_ri,
                            turn_number=turn_number + 2,
                            weights=weights)
                        if our_followups:
                            our_valid = [a for a in our_followups if a[0] > -1000]
                            if our_valid:
                                our_followups = our_valid
                            our_followups.sort(key=lambda a: a[0], reverse=True)
                            our_moved, _, _ = _execute(opp_snap, our_followups[0])

                            if depth > 2 and our_moved is not None:
                                # Round 2 - Ply 4: Tapered follow-up (opponent's single best reply)
                                opp_followups = _gather_actions(
                                    opp_snap, fake_opp, our_moved.ring_index, nation_list,
                                    suspected_human_ri=opp_suspected_us,
                                    turn_number=turn_number + 3,
                                    weights=None)
                                if opp_followups:
                                    opp_f_valid = [a for a in opp_followups if a[0] > -1000]
                                    if opp_f_valid:
                                        opp_followups = opp_f_valid
                                    opp_followups.sort(key=lambda a: a[0], reverse=True)
                                    _execute(opp_snap, opp_followups[0])

                    branch_pos = evaluate_position(opp_snap, bot_secret, nation_list, weights=eval_weights)
                    if branch_pos < worst_pos_score:
                        worst_pos_score = branch_pos

                pos_score = worst_pos_score

            if hybrid_ratio >= 1.0:
                net = pos_score
            elif hybrid_ratio <= 0.0:
                net = my_move_score
            else:
                net = (1.0 - hybrid_ratio) * my_move_score + hybrid_ratio * pos_score
        else:
            # ACTION MODE: net = my_score - opponent_best_score
            fake_opp = Player(opp_nation, is_bot=True, player_id='lookahead_opp')
            opp_suspected_us = bot_secret.ring_index

            opp_actions = _gather_actions(
                snap, fake_opp, new_gci, nation_list,
                suspected_human_ri=opp_suspected_us,
                turn_number=turn_number + 1,
                weights=None)
            if opp_actions:
                opp_valid = [a for a in opp_actions if a[0] > -1000]
                if opp_valid:
                    opp_actions = opp_valid
                opp_best_score = max(a[0] for a in opp_actions)
            else:
                opp_best_score = 0

            net = my_move_score - opp_best_score

        if net > best_net:
            best_net = net
            best_action = action  # return original action

    if best_action is None:
        return None

    return (best_net, *best_action[1:])



def _execute(grid, action):
    """
    Execute one scored action tuple  (score, atype, actor, coord[, path]).
    path is 'intent' | 'random' — used for the debug description label.
    Returns (moved_nation, action_type_str, description) or (None, None, reason).
    """
    score, atype, *rest = action
    # Last element may be a path label; everything before it is payload
    if rest and isinstance(rest[-1], str) and rest[-1] in ('intent', 'random', 'deceptive'):
        payload, path = rest[:-1], rest[-1]
        tag = f"[Bot-{path}]"
    else:
        payload = rest
        tag = "[Bot]"

    if atype == 'attack':
        unit, coord = payload
        success, msg, _ = grid.resolve_attack(unit, *coord)
        if success:
            return unit.nation, 'attack', \
                f"{tag} Attack {unit.nation.color_name} -> {coord}  score={score:.0f}  {msg}"
        return None, None, f"{tag} Attack failed: {msg}"

    if atype == 'move':
        unit, coord = payload
        grid.apply_move(unit, *coord)
        return unit.nation, 'move', \
            f"{tag} Move {unit.nation.color_name} -> {coord}  score={score:.0f}"

    if atype == 'recruit':
        nation, coord = payload
        grid.recruit_army(nation, *coord)
        return nation, 'recruit', f"{tag} Recruit {nation.color_name} at {coord}"

    if atype == 'promote':
        nation, coord = payload
        armies_here = [a for a in grid.armies.get(coord, [])
                       if a.nation.ring_index == nation.ring_index]
        if armies_here:
            grid.promote_to_champion(armies_here[0])
            return nation, 'promote', f"{tag} Promote {nation.color_name} at {coord}"
        return None, None, f"{tag} Promote: no army found"

    return None, None, f"{tag} Unknown action: {atype}"


# ---------------------------------------------------------------------------
# Turn entry points
# ---------------------------------------------------------------------------

def _turn_intent(grid, bot_player, global_cooldown_idx, nation_list,
                 suspected_human_ri=None, turn_number=0):
    """Strategic intent: pick from the top-scoring actions."""
    actions = _gather_actions(grid, bot_player, global_cooldown_idx, nation_list,
                              suspected_human_ri=suspected_human_ri,
                              turn_number=turn_number)
    if not actions:
        return None, None, "[Bot-intent] No legal actions."

    best = max(a[0] for a in actions)
    threshold = (best * 0.85) if best > 0 else (best - 50)
    top_tier  = [a for a in actions if a[0] >= threshold]
    return _execute(grid, random.choice(top_tier))


def _turn_random(grid, bot_player, global_cooldown_idx, nation_list):
    """Purely random legal action (including recruit/promote)."""
    eligible = _eligible_nations(bot_player, global_cooldown_idx, nation_list)
    if not eligible:
        return None, None, "[Bot-random] No eligible nations."

    bot_secret      = bot_player.secret_nation
    allied_ring_set = {n.ring_index for n in nation_list if not bot_secret.is_enemy(n)}

    random.shuffle(eligible)
    pool = []
    for nation in eligible:
        for unit in grid.get_all_nation_units(nation):
            pool += [('move',   unit, c) for c in grid.get_valid_moves(unit, mover_secret_nation=bot_secret)]
            for c in grid.get_valid_attacks(unit):
                # Never randomly attack an allied sovereign
                tq, tr = c
                allied_sovs = [s for s in grid.sovereigns.get((tq, tr), [])
                               if s.nation.ring_index in allied_ring_set
                               and unit.nation.is_enemy(s.nation)]
                if not allied_sovs:
                    pool.append(('attack', unit, c))
        for coord in grid.get_recruit_hexes(nation):
            pool.append(('recruit', nation, coord))
        for coord in grid.get_promote_hexes(nation):
            pool.append(('promote', nation, coord))

    if not pool:
        return None, None, "[Bot-random] No legal moves."

    atype, actor, coord = random.choice(pool)

    if atype == 'move':
        grid.apply_move(actor, *coord)
        return actor.nation, 'move', f"[Bot-random] Move {actor.nation.color_name}"
    if atype == 'attack':
        success, msg, _ = grid.resolve_attack(actor, *coord)
        if success:
            return actor.nation, 'attack', f"[Bot-random] Attack {actor.nation.color_name}"
        return None, None, f"[Bot-random] Attack failed: {msg}"
    if atype == 'recruit':
        grid.recruit_army(actor, *coord)
        return actor, 'recruit', f"[Bot-random] Recruit {actor.color_name}"
    if atype == 'promote':
        armies_here = [a for a in grid.armies.get(coord, [])
                       if a.nation.ring_index == actor.ring_index]
        if armies_here:
            grid.promote_to_champion(armies_here[0])
            return actor, 'promote', f"[Bot-random] Promote {actor.color_name}"

    return None, None, "[Bot-random] Execution failed."


def do_bot_turn(grid, bot_player, global_cooldown_idx, nation_list, turn_number):
    """
    Main bot turn entry point. Blends random and intent based on turn_number.

    Turn  1 -> ~10% intent, 90% random
    Turn 50 -> ~90% intent, 10% random

    Returns (moved_nation, action_type_str, description).
    moved_nation is None if no legal action was found.
    """
    if random.random() < _intent_prob(turn_number):
        return _turn_intent(grid, bot_player, global_cooldown_idx, nation_list)
    else:
        return _turn_random(grid, bot_player, global_cooldown_idx, nation_list)


# ---------------------------------------------------------------------------
# Two-phase API (compute then execute separately, for animation support)
# ---------------------------------------------------------------------------

def compute_bot_action(grid, bot_player, global_cooldown_idx, nation_list, turn_number,
                       suspected_human_ri=None, weights=None, evolved_config=None,
                       lookahead_depth=None, lookahead_beam=None, lookahead_mode=None,
                       eval_weights=None, hybrid_ratio=None):
    """
    Select the bot's next action WITHOUT executing it.

    Returns an action tuple  (score, atype, *payload)  or None if no legal move.
    atype is 'move' | 'attack' | 'recruit' | 'promote'.

    For 'move'/'attack':   payload = (unit, coord)
    For 'recruit'/'promote': payload = (nation, coord)

    suspected_human_ri: ring_index of the bot's best guess for the human's
    secret faction (or None if unknown). Used for adaptive sovereign strategy.

    weights: optional dict of score-category multipliers (from an evolved
    BotConfig).  When None, original hardcoded scores are used.

    evolved_config: optional BotConfig.  When provided, the random/intent
    blend uses the config's intent_probability() instead of _intent_prob().

    lookahead_depth: how many plies to search (1 = current 1-ply, 2+ = multi-ply).
    Defaults to settings.BOT_LOOKAHEAD_DEPTH.

    lookahead_beam: how many top candidates to explore at deeper plies.
    Defaults to settings.BOT_LOOKAHEAD_BEAM.

    lookahead_mode: 'action' (score subtraction) or 'position' (board eval).
    Defaults to settings.BOT_LOOKAHEAD_MODE.

    eval_weights: optional dict of evaluator weight overrides for position mode.

    hybrid_ratio: float 0.0 to 1.0 (blends move score and position eval).
    """
    if evolved_config is not None:
        if lookahead_depth is None:
            lookahead_depth = getattr(evolved_config, 'lookahead_depth', 1)
        if lookahead_beam is None:
            lookahead_beam = getattr(evolved_config, 'lookahead_beam', 3)
        if lookahead_mode is None:
            lookahead_mode = getattr(evolved_config, 'lookahead_mode', 'position')
        if weights is None:
            weights = evolved_config.to_weights_dict()
        if eval_weights is None:
            eval_weights = evolved_config.to_evaluator_weights()
        if hybrid_ratio is None:
            hybrid_ratio = getattr(evolved_config, 'hybrid_ratio', 0.5)
        use_intent = random.random() < evolved_config.intent_probability(turn_number)
    else:
        if lookahead_depth is None:
            lookahead_depth = settings.BOT_LOOKAHEAD_DEPTH
        if lookahead_beam is None:
            lookahead_beam = settings.BOT_LOOKAHEAD_BEAM
        if lookahead_mode is None:
            lookahead_mode = settings.BOT_LOOKAHEAD_MODE
        if hybrid_ratio is None:
            hybrid_ratio = 1.0 if lookahead_mode == 'position' else 0.0
        use_intent = random.random() < _intent_prob(turn_number)

    if use_intent:
        if lookahead_depth > 1 or hybrid_ratio > 0.0:
            # Multi-ply lookahead / hybrid evaluation
            chosen = _lookahead_best(
                grid, bot_player, global_cooldown_idx, nation_list,
                turn_number, suspected_human_ri, weights,
                depth=lookahead_depth - 1, beam_width=lookahead_beam,
                mode=lookahead_mode, eval_weights=eval_weights,
                hybrid_ratio=hybrid_ratio)
            if chosen is None:
                return None
            return (*chosen, 'intent')   # tag with path label
        else:
            # Original 1-ply move scoring
            actions = _gather_actions(grid, bot_player, global_cooldown_idx, nation_list,
                                      suspected_human_ri=suspected_human_ri,
                                      turn_number=turn_number,
                                      weights=weights)
            if not actions:
                return None
            # Discard any disqualified actions (score < -1000)
            valid_actions = [a for a in actions if a[0] > -1000]
            if valid_actions:
                actions = valid_actions
            best      = max(a[0] for a in actions)
            threshold = (best * 0.85) if best > 0 else (best - 50)
            top_tier  = [a for a in actions if a[0] >= threshold]
            chosen = random.choice(top_tier)
            return (*chosen, 'intent')   # tag with path label

    else:
        # Build random pool — also apply adaptive sovereign rules
        bot_ri          = bot_player.secret_nation.ring_index
        allied_ring_set = {n.ring_index for n in nation_list
                           if not bot_player.secret_nation.is_enemy(n)}
        eligible = _eligible_nations(bot_player, global_cooldown_idx, nation_list)
        pool = []
        for nation in eligible:
            for unit in grid.get_all_nation_units(nation):
                pool += [(0, 'move',   unit, c) for c in grid.get_valid_moves(unit, mover_secret_nation=bot_player.secret_nation)]
                for c in grid.get_valid_attacks(unit):
                    # Never randomly attack an allied sovereign
                    tq, tr = c
                    allied_sovs = [s for s in grid.sovereigns.get((tq, tr), [])
                                   if s.nation.ring_index in allied_ring_set
                                   and unit.nation.is_enemy(s.nation)]
                    if not allied_sovs:
                        pool.append((0, 'attack', unit, c))
            for coord in grid.get_recruit_hexes(nation):
                pool.append((0, 'recruit', nation, coord))
            for coord in grid.get_promote_hexes(nation):
                pool.append((0, 'promote', nation, coord))
        if not pool:
            return None
        pool = _adaptive_sovereign_adjustments(
            grid, pool, bot_ri, suspected_human_ri, turn_number,
            nation_list=nation_list)
        # For random, exclude disqualified actions (score < -1000)
        valid_pool = [a for a in pool if a[0] > -1000]
        if valid_pool:
            pool = valid_pool
        chosen = random.choice(pool)
        return (*chosen, 'random')   # tag with path label


def execute_bot_action(grid, action):
    """
    Execute a previously-computed action tuple.

    Returns (moved_nation, action_type_str, description).
    """
    return _execute(grid, action)
