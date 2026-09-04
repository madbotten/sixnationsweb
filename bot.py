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
from factions import NATIONS_BY_NAME


# ---------------------------------------------------------------------------
# Move record (opponent history)
# ---------------------------------------------------------------------------

class BotMemory:
    """Stores a record of every move the human player made, and tracks suspicion scores per nation."""

    def __init__(self, debug=False):
        self.moves         = []   # chronological move records
        self.nation_scores = {}   # color_name -> int score
        self.debug         = debug

    def record(self, turn_number, nation, unit_type_str, from_hex, to_hex, action_type):
        """
        Record one human move.
        unit_type_str : 'army' | 'champion' | 'sovereign' | None (for recruit/promote)
        action_type   : 'move' | 'attack' | 'recruit' | 'promote'
        """
        self.moves.append({
            'turn':   turn_number,
            'nation': nation.color_name,
            'name':   nation.color_name,
            'utype':  unit_type_str,
            'from':   from_hex,
            'to':     to_hex,
            'action': action_type,
        })

    # ------------------------------------------------------------------
    # Scoring API
    # ------------------------------------------------------------------

    def add_score(self, color_name, points, nation_names=None):
        """
        Add (or subtract) suspicion points for a nation identified by color_name.
        """
        old = self.nation_scores.get(color_name, 0)
        self.nation_scores[color_name] = old + points
        new = self.nation_scores[color_name]
        if self.debug:
            sign = '+' if points >= 0 else ''
            print(f"  [Score] {color_name}: {old} {sign}{points} -> {new}")

    def guess_faction(self, nation_list, exclude_names=()):
        """
        Return the Nation with the highest suspicion score,
        or None if no moves have been recorded yet.
        exclude_names: iterable of color_name strings to skip
        (use to prevent the bot from guessing its own secret nation).
        """
        if not self.nation_scores:
            return None
        candidates = {
            name: pts
            for name, pts in self.nation_scores.items()
            if name not in exclude_names
        }
        if not candidates:
            return None
        best_name = max(candidates, key=lambda n: candidates[n])
        for n in nation_list:
            if n.color_name == best_name:
                return n
        return None

    def guess_top3_factions(self, nation_list, exclude_names=()):
        """
        Return a list of up to 3 (Nation, score) tuples in descending score order.
        Combines suspicion scores with move-frequency counts.
        exclude_names: iterable of color_name strings to skip.
        """
        counts = self.nation_move_counts()
        # Blend: suspicion score + 0.5 * move count
        all_scores = {}
        all_names = {n.color_name for n in nation_list} - set(exclude_names)
        for name in all_names:
            s = self.nation_scores.get(name, 0) + 0.5 * counts.get(name, 0)
            all_scores[name] = s
        if not all_scores:
            return []
        sorted_names = sorted(all_scores, key=lambda n: all_scores[n], reverse=True)
        result = []
        for name in sorted_names[:3]:
            for n in nation_list:
                if n.color_name == name:
                    result.append((n, all_scores[name]))
                    break
        return result

    def guess_bottom3_factions(self, nation_list, exclude_names=()):
        """
        Return a list of up to 3 (Nation, score) tuples in ASCENDING score order.
        These are the nations the human appears to care about LEAST — inferred
        as the opponent's defeat-goal targets.
        exclude_names: iterable of color_name strings to skip.
        """
        counts = self.nation_move_counts()
        all_scores = {}
        all_names = {n.color_name for n in nation_list} - set(exclude_names)
        for name in all_names:
            s = self.nation_scores.get(name, 0) + 0.5 * counts.get(name, 0)
            all_scores[name] = s
        if not all_scores:
            return []
        sorted_names = sorted(all_scores, key=lambda n: all_scores[n])  # ascending
        result = []
        for name in sorted_names[:3]:
            for n in nation_list:
                if n.color_name == name:
                    result.append((n, all_scores[name]))
                    break
        return result


    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def nation_move_counts(self):
        """Return dict {color_name: count} of how often human moved each nation."""
        counts = {}
        for m in self.moves:
            name = m['nation']
            counts[name] = counts.get(name, 0) + 1
        return counts

    def most_moved_nations(self, top_n=3):
        """Return list of (color_name, count) sorted by count descending."""
        counts = self.nation_move_counts()
        return sorted(counts.items(), key=lambda x: -x[1])[:top_n]

    def observe_diplomacy(self, flag_nation, box_nation, new_stance):
        """Update suspicion scores from a human diplomacy move.

        Alliance signal: both nations in an ally declaration earn +3 prevail
        suspicion.  The player chose to ally them — a strong signal they want
        both to survive and thrive.

        War signal: deliberately uninformative.  A war could be the player
        pitting two enemies against each other, OR fighting their own defeat
        goals.  Without more context we cannot tell which side the player
        is rooting for, so no points are awarded.

        Peace signal: also skipped — could be cancelling an old war/ally for
        many reasons with no clear prevail direction.
        """
        if new_stance == 'ally':
            self.add_score(flag_nation.color_name, 3)
            self.add_score(box_nation.color_name,  3)
            if self.debug:
                print(f"  [Dipl-observe] Alliance {flag_nation.color_name} ↔ "
                      f"{box_nation.color_name} → +3 each")


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


def _nearest_enemy_sov_dist(grid, q, r, enemy_name_set) -> int:
    """Distance from (q,r) to the nearest live sovereign in enemy_name_set."""
    best = 99
    for slist in grid.sovereigns.values():
        for s in slist:
            if s.nation.color_name in enemy_name_set:
                d = _axial_dist(q, r, s.q, s.r)
                best = min(best, d)
    return best


def _eligible_nations(player, global_cooldown_name, nation_list):
    return [
        n for n in nation_list
        if not player.nation_on_cooldown(n)
        and (global_cooldown_name is None or n.color_name != global_cooldown_name)
        and not n.is_ghost
    ]


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _enemy_names(nation, all_nations):
    """Return the set of color_names of nations that are enemies of the given nation."""
    return {n.color_name for n in nation.enemy_nations(all_nations)}

# Backwards-compat alias imported by evolution.py
_enemy_set = _enemy_names



def _adaptive_sovereign_adjustments(grid, actions, bot_name, suspected_human_name,
                                    turn_number, nation_list=None, adaptive_turn=None,
                                    top3_names=None, top3_spread=0.5, bot_goals=None):
    """
    Apply sovereign-targeting intelligence based on secret goals or suspected human faction.

    When bot_goals is provided:
      - Prevail goals & bot's own sovereign are strictly protected (-9999.0).
      - Defeat goals receive a high-priority kill bonus (+2000.0).

    When bot_goals is None (legacy mode):
      top3_names / suspected_human_name are used with human-blocking logic.
    """
    if bot_goals is not None:
        result = []
        for action in actions:
            score, atype, *payload = action
            if atype == 'attack':
                unit, coord = payload[0], payload[1]
                tq, tr = coord
                target_sovs = grid.sovereigns.get((tq, tr), [])
                for sov in target_sovs:
                    if not unit.nation.is_enemy(sov.nation):
                        continue
                    sov_name = sov.nation.color_name
                    if sov_name in bot_goals.prevail_goals or sov_name == bot_name:
                        score = -9999.0
                    elif sov_name in bot_goals.defeat_goals:
                        score += 2000.0
                    break
            result.append((score, atype, *payload))
        return result

    # Build the effective list of (human_name, weight) pairs (legacy mode)
    if top3_names:
        weighted_humans = [
            (name, top3_spread ** i)
            for i, name in enumerate(top3_names[:3])
        ]
    elif suspected_human_name is not None:
        weighted_humans = [(suspected_human_name, 1.0)]
    else:
        return actions

    bot_enemy_names = {n.color_name for n in NATIONS_BY_NAME[bot_name].enemy_nations(nation_list)}

    # Aggregate human enemy names across all guesses (weighted by rank)
    # We use the top guess (weight 1.0) for the critical blocking logic
    top_human_name = weighted_humans[0][0]
    human_enemy_names = {n.color_name for n in NATIONS_BY_NAME[top_human_name].enemy_nations(nation_list)}

    human_kills_so_far = 0
    bot_kills_so_far   = 0
    if nation_list:
        human_kills_so_far = sum(
            1 for n in nation_list
            if n.color_name in human_enemy_names and n.is_ghost
        )
        bot_kills_so_far = sum(
            1 for n in nation_list
            if n.color_name in bot_enemy_names and n.is_ghost
        )
    human_one_away = (human_kills_so_far >= 1)
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
                if not unit.nation.is_enemy(sov.nation):
                    continue
                sov_name = sov.nation.color_name

                # Check against each ranked human guess
                for h_name, h_weight in weighted_humans:
                    if sov_name == h_name and is_adaptive_phase:
                        score += 2000.0 * h_weight
                        break

                    h_enemy_names = {n.color_name for n in NATIONS_BY_NAME[h_name].enemy_nations(nation_list)}
                    if sov_name in h_enemy_names:
                        if sov_name not in bot_enemy_names:
                            if is_adaptive_phase or human_one_away:
                                score = -9999.0
                        elif human_one_away and bot_one_away:
                            score += 1000.0 * h_weight
                        elif human_one_away:
                            score = -9999.0
                        break

        result.append((score, atype, *payload))
    return result


def _score_attack(grid, attacker, tq, tr, enemy_name_set,
                   weights=None, allied_name_set=None) -> float:
    """Score for attacker targeting hex (tq, tr)."""
    from units import Army, Champion, Sovereign

    w_kill = (weights or {}).get('kill_enemy', 1.0)

    nation   = attacker.nation
    e_sovs   = [s for s in grid.sovereigns.get((tq, tr), []) if nation.is_enemy(s.nation)]
    e_champs = [c for c in grid.champions.get((tq, tr), [])  if nation.is_enemy(c.nation)]
    e_knights= [k for k in grid.knights.get((tq, tr), [])    if nation.is_enemy(k.nation)]
    e_armies = [a for a in grid.armies.get((tq, tr), [])     if nation.is_enemy(a.nation)]

    if e_sovs:
        name  = e_sovs[0].nation.color_name
        if allied_name_set and name in allied_name_set:
            return -9999.0
        score = (1000 if name in enemy_name_set else 250) * w_kill
    elif e_champs:
        name  = e_champs[0].nation.color_name
        if allied_name_set and name in allied_name_set:
            return -500.0
        score = (400  if name in enemy_name_set else 100) * w_kill
    elif e_knights:
        name  = e_knights[0].nation.color_name
        if allied_name_set and name in allied_name_set:
            return -500.0
        score = (250  if name in enemy_name_set else 75) * w_kill
    elif e_armies:
        name  = e_armies[0].nation.color_name
        if allied_name_set and name in allied_name_set:
            return -500.0
        score = (150  if name in enemy_name_set else 50) * w_kill
    else:
        score = 0

    if grid.is_supported(attacker):
        score += 20

    return float(score)


def _score_move(grid, unit, tq, tr, enemy_name_set, allied_name_set,
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
    from units import Army
    from units import Champion, Sovereign
    from units import Knight

    w = weights or {}
    w_advance   = w.get('advance_allied', 1.0)
    w_protect   = w.get('protect_sovereign', 1.0)
    w_champ_sup = w.get('champion_support', 1.0)
    w_danger    = w.get('endanger_enemy_sov', 1.0)
    w_unsup_ch  = w.get('unsupport_enemy_champ', 1.0)
    w_territory = w.get('claim_territory', 1.0)

    nation    = unit.nation
    is_allied = nation.color_name in allied_name_set
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
            old_d = _nearest_enemy_sov_dist(grid, unit.q, unit.r, enemy_name_set)
            new_d = _nearest_enemy_sov_dist(grid, tq, tr, enemy_name_set)
            if new_d < old_d:
                score += (90 + (old_d - new_d) * 10) * w_advance
            allies_at = sum(
                1 for lst in grid.get_units_at(tq, tr).values()
                for u in lst if not u.nation.is_enemy(nation) and u is not unit
            )
            if allies_at > 0:
                score += 50 * w_champ_sup
        else:
            # Non-allied champion: advance toward enemy defeat targets
            non_allied_targets = {n.color_name for n in nation.enemies
                                  if n.color_name in enemy_name_set}
            if non_allied_targets:
                old_d = _nearest_enemy_sov_dist(grid, unit.q, unit.r, non_allied_targets)
                new_d = _nearest_enemy_sov_dist(grid, tq, tr, non_allied_targets)
                if new_d < old_d:
                    score += (75 + (old_d - new_d) * 10) * w_advance
            if grid.is_supported(unit):
                allies_at = sum(
                    1 for lst in grid.get_units_at(tq, tr).values()
                    for u in lst if not u.nation.is_enemy(nation)
                )
                if allies_at == 0:
                    score += 40 * w_unsup_ch

    elif isinstance(unit, (Army, Knight)):
        if is_allied:
            old_d = _nearest_enemy_sov_dist(grid, unit.q, unit.r, enemy_name_set)
            new_d = _nearest_enemy_sov_dist(grid, tq, tr, enemy_name_set)
            base_adv = 85 if isinstance(unit, Knight) else 80
            if new_d < old_d:
                score += (base_adv + (old_d - new_d) * 10) * w_advance
            else:
                score += 5
        else:
            # Non-allied army/knight: advance toward enemy defeat targets
            non_allied_targets = {n.color_name for n in nation.enemies
                                  if n.color_name in enemy_name_set}
            if non_allied_targets:
                old_d = _nearest_enemy_sov_dist(grid, unit.q, unit.r, non_allied_targets)
                new_d = _nearest_enemy_sov_dist(grid, tq, tr, non_allied_targets)
                base_adv = 70 if isinstance(unit, Knight) else 65
                if new_d < old_d:
                    score += (base_adv + (old_d - new_d) * 10) * w_advance
                else:
                    score += 2
            else:
                score += 2

    # Territory-claiming bonus (capturing neutral or seizing enemy hexes)
    if hasattr(grid, 'tile_control'):
        curr_owner = grid.tile_control.get((tq, tr))   # color_name or None
        unit_name  = nation.color_name
        if curr_owner is None:
            # Claiming unclaimed territory
            if is_allied:
                score += 40.0 * w_territory
            else:
                score += 10.0 * w_territory
        elif curr_owner != unit_name:
            from factions import NATIONS_BY_NAME
            owner_nation = NATIONS_BY_NAME[curr_owner]
            if nation.is_enemy(owner_nation) and isinstance(unit, (Army, Knight, Champion)):
                # Seizing enemy territory
                if is_allied:
                    score += 70.0 * w_territory
                elif curr_owner in enemy_name_set:
                    score += 30.0 * w_territory

    score += random.uniform(0, 0.01)  # tiny tie-break only; was uniform(0,2) which corrupted beam ordering
    return score


# ---------------------------------------------------------------------------
# Action gathering
# ---------------------------------------------------------------------------

def _gather_actions(grid, bot_player, global_cooldown_name, nation_list,
                    suspected_human_ri=None, turn_number=0, weights=None,
                    dipl_state=None, bot_goals=None,
                    top3_names=None, bottom3_names=None,
                    exclude_diplomacy=False):
    """
    Build a scored list of all legal bot actions.
    Returns list of (score, action_type, *payload).
    Applies adaptive sovereign strategy after BOT_ADAPTIVE_TURN.

    weights: optional dict of score-category multipliers (see _score_attack,
    _score_move).  Also supports 'muster_promote' key for recruit/promote.
    When None, original hardcoded scores are used.

    dipl_state: DiplomacyState instance for cooldown checking (None = no diplomacy actions).
    bot_goals:  BotGoals instance with prevail_goals/defeat_goals lists (None = skip diplomacy).
    top3_names:    list of up to 3 color_name strings (top human-faction guesses = inferred prevail).
    bottom3_names: list of up to 3 color_name strings (bottom human-faction guesses = inferred defeat).
    exclude_diplomacy: if True, skip all diplomacy action generation (used by lookahead tree
                       so diplomacy is always evaluated 1-ply and not mixed into beam search).
    """
    eligible        = _eligible_nations(bot_player, global_cooldown_name, nation_list)
    bot_secret      = bot_player.secret_nation
    bot_ri          = bot_secret.color_name

    if bot_goals is not None:
        allied_name_set = set(bot_goals.prevail_goals) | {bot_ri}
        enemy_name_set  = set(bot_goals.defeat_goals) | {n.color_name for n in bot_secret.enemy_nations(nation_list)}
    else:
        allied_name_set = {n.color_name for n in bot_secret.allies} | {bot_ri}
        enemy_name_set  = {n.color_name for n in bot_secret.enemy_nations(nation_list)}

    w_muster = (weights or {}).get('muster_promote', 1.0)

    actions = []

    for nation in eligible:
        is_allied = nation.color_name in allied_name_set
        units     = grid.get_all_nation_units(nation)

        for unit in units:
            for coord in grid.get_valid_attacks(unit):
                s = _score_attack(grid, unit, *coord, enemy_name_set,
                                  allied_name_set=allied_name_set,
                                  weights=weights)
                actions.append((s, 'attack', unit, coord))

            for coord in grid.get_valid_moves(unit):
                s = _score_move(grid, unit, *coord, enemy_name_set,
                                allied_name_set, weights=weights)
                actions.append((s, 'move', unit, coord))

        for coord in grid.get_recruit_hexes(nation):
            s = (60.0 if is_allied else 15.0) * w_muster
            actions.append((s, 'recruit', nation, coord))

        for coord in grid.get_promote_hexes(nation):
            s = (70.0 if is_allied else 20.0) * w_muster
            actions.append((s, 'promote', nation, coord))

        for coord in grid.get_promote_knight_hexes(nation):
            s = (65.0 if is_allied else 18.0) * w_muster
            actions.append((s, 'promote_knight', nation, coord))

    # --- Diplomacy actions ---
    if not exclude_diplomacy and dipl_state is not None and bot_goals is not None and weights is not None:
        # Fine-grained diplomacy genes with fallbacks to legacy genes
        w_def_vs_def  = weights.get('w_dipl_defeat_vs_defeat',  weights.get('w_diplomacy_war',   1.8))
        w_prev_ally   = weights.get('w_dipl_prevail_alliance',  weights.get('w_diplomacy_ally',  1.5))
        w_prev_vs_def = weights.get('w_dipl_prevail_vs_defeat', weights.get('w_diplomacy_war',   2.0))
        w_opp_pv_war  = weights.get('w_dipl_opp_prevail_war',   weights.get('w_diplomacy_war',   1.2))
        w_opp_df_aly  = weights.get('w_dipl_opp_defeat_ally',   weights.get('w_diplomacy_ally',  1.0))
        w_peace       = weights.get('w_dipl_peace',             weights.get('w_diplomacy_peace', 0.5))
        top3_spread   = weights.get('top3_spread', 0.5)

        # Decay weights for top 3 guessed opponent prevail nations
        # Rank 0 (top guess): 1.0, Rank 1: top3_spread, Rank 2: top3_spread^2
        t3_rank = {}
        if top3_names:
            for rank, name in enumerate(top3_names[:3]):
                t3_rank[name] = (top3_spread ** rank)

        def _propose_diplomacy(na, nb, desired_stance, base_score, weight):
            """Propose a diplomacy action adhering to 2-step rules (neutral <-> ally/enemy).

            - If na is nb, or either is ghost, or pair is locked: return.
            - If curr == desired_stance: propose RENEW (re-lock) at 0.8x score.
            - If curr == 'neutral': directly propose desired_stance.
            - If curr opposes desired_stance (enemy <-> ally direct jump is illegal):
              propose 'neutral' as Step 1 (e.g. end war between prevail picks, or break
              alliance between defeat targets).
            """
            if na is nb or na.is_ghost or nb.is_ghost:
                return
            if dipl_state.is_locked(na, nb):
                return
            curr = na.get_stance(nb)

            if curr == desired_stance:
                # Already in desired stance — offer renew (re-lock cooldown) at maintenance priority
                eff_score = base_score * weight * 0.25
                if eff_score >= 10.0:
                    actions.append((eff_score, 'diplomacy', na, nb, desired_stance))
            elif curr == 'neutral':
                # Direct 1-step move to desired stance
                eff_score = base_score * weight
                if eff_score > 0.0:
                    actions.append((eff_score, 'diplomacy', na, nb, desired_stance))
            else:
                # Direct jump between 'enemy' and 'ally' is illegal under game rules!
                # Step 1: Transition to 'neutral' to clear the opposing stance.
                # (e.g., end war between prevail picks, or break alliance between defeat picks)
                eff_score = base_score * weight * 0.95
                if eff_score > 0.0:
                    actions.append((eff_score, 'diplomacy', na, nb, 'neutral'))

        # ── First-person diplomacy (bot_secret moving its own flag) ──
        for other in nation_list:
            if other is bot_secret or other.is_ghost:
                continue
            if dipl_state.is_locked(bot_secret, other):
                continue
            other_name = other.color_name
            curr_stance = bot_secret.get_stance(other)

            if other_name in bot_goals.defeat_goals:
                # Direct war against defeat goal
                _propose_diplomacy(bot_secret, other, 'enemy', 65.0, w_prev_vs_def)
            elif other_name in bot_goals.prevail_goals:
                # Direct alliance with prevail goal
                _propose_diplomacy(bot_secret, other, 'ally', 60.0, w_prev_ally)
            elif other_name in t3_rank:
                # Direct war against suspected opponent prevail
                decay = t3_rank.get(other_name, 1.0)
                _propose_diplomacy(bot_secret, other, 'enemy', 40.0 * decay, w_opp_pv_war)
            elif curr_stance in ('ally', 'enemy') and w_peace > 0:
                # De-escalate non-priority relationship back to neutral
                _propose_diplomacy(bot_secret, other, 'neutral', 20.0, w_peace)

        # ── Third-party diplomacy (manipulating other nations' relationships) ──
        # Pre-compute active nation groups
        d_nations = [n for n in nation_list
                     if n.color_name in bot_goals.defeat_goals and not n.is_ghost]
        p_nations = [n for n in nation_list
                     if n.color_name in bot_goals.prevail_goals and not n.is_ghost]

        # Helper: assess nation board strength (territory + weighted units)
        def _nation_strength(nation):
            territory = sum(1 for owner in grid.tile_control.values()
                            if owner == nation.color_name) if hasattr(grid, 'tile_control') else 0
            armies    = len([u for ul in grid.armies.values()
                             for u in ul if u.nation is nation])
            champions = len([u for ul in grid.champions.values()
                             for u in ul if u.nation is nation])
            sov       = len([u for ul in grid.sovereigns.values()
                             for u in ul if u.nation is nation])
            return territory + armies + champions * 2 + sov * 3

        # Strategy 1: Wars between bot's defeat-goal nations (weaken both)
        for i, da in enumerate(d_nations):
            for db in d_nations[i+1:]:
                _propose_diplomacy(da, db, 'enemy', 55.0, w_def_vs_def)

        # Strategy 2: Wars between prevail-goal and defeat-goal nations
        # Prevail nation gets bonus when it is measurably stronger than the defeat nation.
        for pn in p_nations:
            for dn in d_nations:
                base = 45.0
                if _nation_strength(pn) >= _nation_strength(dn):
                    base += 15.0  # +15 tactical edge for dominant prevail attacker
                _propose_diplomacy(pn, dn, 'enemy', base, w_prev_vs_def)

        # Strategy 3: Alliances between bot's prevail-goal nations
        # (If at war, 2-step machine automatically proposes neutral first to stop the bloodshed)
        for i, pa in enumerate(p_nations):
            for pb in p_nations[i+1:]:
                _propose_diplomacy(pa, pb, 'ally', 55.0, w_prev_ally)

        # Strategy 4: Wars between suspected opponent prevail nations (disrupt opponent)
        if top3_names:
            h_nations = [n for n in nation_list
                         if n.color_name in top3_names and not n.is_ghost]
            for i, ha in enumerate(h_nations):
                for hb in h_nations[i+1:]:
                    decay = min(t3_rank.get(ha.color_name, 1.0), t3_rank.get(hb.color_name, 1.0))
                    _propose_diplomacy(ha, hb, 'enemy', 35.0 * decay, w_opp_pv_war)

        # Strategy 5: Alliances between inferred opponent defeat nations
        # (Bottom 3 nations: shielding them prevents opponent from claiming victory)
        if bottom3_names:
            b_nations = [n for n in nation_list
                         if n.color_name in bottom3_names and not n.is_ghost]
            for i, ba in enumerate(b_nations):
                for bb in b_nations[i+1:]:
                    _propose_diplomacy(ba, bb, 'ally', 40.0, w_opp_df_aly)

    # Apply adaptive sovereign intelligence
    adaptive_t  = weights.get('adaptive_turn') if weights else None
    top3_spread = (weights.get('top3_spread', 0.5) if weights else 0.5)
    actions = _adaptive_sovereign_adjustments(
        grid, actions, bot_ri, suspected_human_ri, turn_number,
        nation_list=nation_list, adaptive_turn=adaptive_t,
        top3_names=top3_names, top3_spread=top3_spread,
        bot_goals=bot_goals)

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


def _lookahead_best(grid, bot_player, global_cooldown_name, nation_list,
                    turn_number, suspected_opp_ri, weights,
                    depth, beam_width, mode='position', eval_weights=None,
                    hybrid_ratio=1.0, bot_goals=None,
                    top3_names=None, bottom3_names=None):
    """Beam-search negamax / hybrid lookahead.

    depth: remaining plies to search (0 = evaluate immediate moves, 1 = 1 opponent counter, 2 = 2 counters).
    beam_width: how many top candidates to explore at deeper plies.
    mode: 'action' (score subtraction) or 'position' (board evaluation).
    hybrid_ratio: 0.0 = 100% move score, 1.0 = 100% positional board eval,
                  0.3..0.7 = blended hybrid scoring.

    Returns an action tuple (final_score, atype, *payload) or None.
    """
    from player import Player
    from evaluator import evaluate_position, _derive_ghost_set

    bot_secret = bot_player.secret_nation

    # Gather and score all actions (1-ply move scoring, diplomacy excluded from tree)
    actions = _gather_actions(grid, bot_player, global_cooldown_name, nation_list,
                              suspected_human_ri=suspected_opp_ri,
                              turn_number=turn_number,
                              weights=weights,
                              bot_goals=bot_goals,
                              top3_names=top3_names,
                              bottom3_names=bottom3_names,
                              exclude_diplomacy=True)
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
        new_gci = moved_nation.color_name

        # If depth == 0 with hybrid evaluation (evaluate position immediately without opponent counter)
        if depth <= 0:
            pos_score = evaluate_position(snap, bot_secret, nation_list, weights=eval_weights,
                                          ghost_name_set=_derive_ghost_set(snap),
                                          bot_goals=bot_goals)
            net = (1.0 - hybrid_ratio) * my_move_score + hybrid_ratio * pos_score
            if net > best_net:
                best_net = net
                best_action = action
            continue

        # Depth >= 1: Simulate opponent response
        opp_nation = None
        if suspected_opp_ri is not None:
            for n in nation_list:
                if n.color_name == suspected_opp_ri:
                    opp_nation = n
                    break

        if opp_nation is None:
            # No guess — evaluate our immediate position
            pos_score = evaluate_position(snap, bot_secret, nation_list, weights=eval_weights,
                                          ghost_name_set=_derive_ghost_set(snap),
                                          bot_goals=bot_goals)
            if mode == 'action':
                net = my_move_score
            else:
                net = (1.0 - hybrid_ratio) * my_move_score + hybrid_ratio * pos_score
        elif mode == 'position' or hybrid_ratio > 0.0:
            # 2-STAGE TAPERED BEAM MINIMAX:
            # Round 1 (Plies 1 & 2): Full beam width (test top opponent counters against our move)
            # Round 2 (Plies 3 & 4): Tapered to 1 (principal variation follow-up sequence)
            fake_opp = Player(opp_nation, is_bot=True, player_id='lookahead_opp')
            opp_suspected_us = bot_secret.color_name

            opp_actions = _gather_actions(
                snap, fake_opp, new_gci, nation_list,
                suspected_human_ri=opp_suspected_us,
                turn_number=turn_number + 1,
                weights=weights,
                exclude_diplomacy=True)

            if not opp_actions:
                pos_score = evaluate_position(snap, bot_secret, nation_list, weights=eval_weights,
                                              ghost_name_set=_derive_ghost_set(snap),
                                              bot_goals=bot_goals)
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
                            opp_snap, bot_player, opp_moved.color_name, nation_list,
                            suspected_human_ri=suspected_opp_ri,
                            turn_number=turn_number + 2,
                            weights=weights,
                            bot_goals=bot_goals,
                            top3_names=top3_names,
                            bottom3_names=bottom3_names,
                            exclude_diplomacy=True)
                        if our_followups:
                            our_valid = [a for a in our_followups if a[0] > -1000]
                            if our_valid:
                                our_followups = our_valid
                            our_followups.sort(key=lambda a: a[0], reverse=True)
                            our_moved, _, _ = _execute(opp_snap, our_followups[0])

                            if depth > 2 and our_moved is not None:
                                # Round 2 - Ply 4: Tapered follow-up (opponent's single best reply)
                                opp_followups = _gather_actions(
                                    opp_snap, fake_opp, our_moved.color_name, nation_list,
                                    suspected_human_ri=opp_suspected_us,
                                    turn_number=turn_number + 3,
                                    weights=weights,
                                    exclude_diplomacy=True)
                                if opp_followups:
                                    opp_f_valid = [a for a in opp_followups if a[0] > -1000]
                                    if opp_f_valid:
                                        opp_followups = opp_f_valid
                                    opp_followups.sort(key=lambda a: a[0], reverse=True)
                                    _execute(opp_snap, opp_followups[0])

                    branch_pos = evaluate_position(opp_snap, bot_secret, nation_list, weights=eval_weights,
                                                    ghost_name_set=_derive_ghost_set(opp_snap),
                                                    bot_goals=bot_goals)
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
            opp_suspected_us = bot_secret.color_name

            opp_actions = _gather_actions(
                snap, fake_opp, new_gci, nation_list,
                suspected_human_ri=opp_suspected_us,
                turn_number=turn_number + 1,
                weights=weights,
                exclude_diplomacy=True)
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



def _execute(grid, action, dipl_state=None):
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
                       if a.nation.color_name == nation.color_name]
        if armies_here:
            grid.promote_to_champion(armies_here[0])
            return nation, 'promote', f"{tag} Promote {nation.color_name} at {coord}"
        return None, None, f"{tag} Promote: no army found"

    if atype == 'promote_knight':
        nation, coord = payload
        armies_here = [a for a in grid.armies.get(coord, [])
                       if a.nation.color_name == nation.color_name]
        if armies_here:
            grid.promote_to_knight(armies_here[0])
            return nation, 'promote_knight', f"{tag} Promote Knight {nation.color_name} at {coord}"
        return None, None, f"{tag} Promote Knight: no army found"

    if atype == 'diplomacy':
        # payload = (nation_a, nation_b, new_stance[, dipl_state])
        # dipl_state is optional — headless games pass it; main.py handles locking via panel
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
            events = reconcile_stance_change(
                grid, nation_a, nation_b, new_stance,
                list(NATIONS_BY_NAME.values()))
            for ev in events:
                if settings.DEPLOYMENT == 'DEBUG':
                    print(f"[Bot-diplomacy] {ev}")
        except (ImportError, AttributeError):
            pass
        return nation_a, 'diplomacy', \
            f"{tag} Diplomacy: {nation_a.color_name} → {new_stance} → {nation_b.color_name}"

    return None, None, f"{tag} Unknown action: {atype}"



# ---------------------------------------------------------------------------
# Turn entry points
# ---------------------------------------------------------------------------

def _turn_intent(grid, bot_player, global_cooldown_name, nation_list,
                 suspected_human_ri=None, turn_number=0):
    """Strategic intent: pick from the top-scoring actions."""
    actions = _gather_actions(grid, bot_player, global_cooldown_name, nation_list,
                              suspected_human_ri=suspected_human_ri,
                              turn_number=turn_number)
    if not actions:
        return None, None, "[Bot-intent] No legal actions."

    best = max(a[0] for a in actions)
    threshold = (best * 0.85) if best > 0 else (best - 50)
    top_tier  = [a for a in actions if a[0] >= threshold]
    return _execute(grid, random.choice(top_tier))


def _turn_random(grid, bot_player, global_cooldown_name, nation_list):
    """Purely random legal action (including recruit/promote)."""
    eligible = _eligible_nations(bot_player, global_cooldown_name, nation_list)
    if not eligible:
        return None, None, "[Bot-random] No eligible nations."

    bot_secret      = bot_player.secret_nation
    allied_name_set = {n.color_name for n in nation_list if not bot_secret.is_enemy(n)}

    random.shuffle(eligible)
    pool = []
    for nation in eligible:
        for unit in grid.get_all_nation_units(nation):
            pool += [('move',   unit, c) for c in grid.get_valid_moves(unit)]
            for c in grid.get_valid_attacks(unit):
                # Never randomly attack an allied sovereign
                tq, tr = c
                allied_sovs = [s for s in grid.sovereigns.get((tq, tr), [])
                               if s.nation.color_name in allied_name_set
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
                       if a.nation.color_name == actor.color_name]
        if armies_here:
            grid.promote_to_champion(armies_here[0])
            return actor, 'promote', f"[Bot-random] Promote {actor.color_name}"

    return None, None, "[Bot-random] Execution failed."


def do_bot_turn(grid, bot_player, global_cooldown_name, nation_list, turn_number):
    """
    Main bot turn entry point. Blends random and intent based on turn_number.

    Turn  1 -> ~10% intent, 90% random
    Turn 50 -> ~90% intent, 10% random

    Returns (moved_nation, action_type_str, description).
    moved_nation is None if no legal action was found.
    """
    if random.random() < _intent_prob(turn_number):
        return _turn_intent(grid, bot_player, global_cooldown_name, nation_list)
    else:
        return _turn_random(grid, bot_player, global_cooldown_name, nation_list)


# ---------------------------------------------------------------------------
# Two-phase API (compute then execute separately, for animation support)
# ---------------------------------------------------------------------------

def compute_bot_action(grid, bot_player, global_cooldown_name, nation_list, turn_number,
                       suspected_human_ri=None, weights=None, evolved_config=None,
                       lookahead_depth=None, lookahead_beam=None, lookahead_mode=None,
                       eval_weights=None, hybrid_ratio=None,
                       dipl_state=None, bot_goals=None,
                       top3_names=None, bottom3_names=None):
    """
    Select the bot's next action WITHOUT executing it.

    Returns an action tuple  (score, atype, *payload)  or None if no legal move.
    atype is 'move' | 'attack' | 'recruit' | 'promote' | 'diplomacy'.

    For 'move'/'attack':   payload = (unit, coord)
    For 'recruit'/'promote': payload = (nation, coord)
    For 'diplomacy':       payload = (nation_a, nation_b, new_stance)

    suspected_human_ri: color_name of the bot's best guess for the human's
    secret faction (or None if unknown). Used for adaptive sovereign strategy.
    Deprecated in favour of top3_names but kept for backward-compat.

    top3_names: list of up to 3 color_name strings (ranked guesses) for the
    human's secret faction. Supersedes suspected_human_ri when provided.

    weights: optional dict of score-category multipliers (from an evolved
    BotConfig).  When None, original hardcoded scores are used.

    evolved_config: optional BotConfig.  When provided, the random/intent
    blend uses the config's intent_probability() instead of _intent_prob().

    dipl_state: DiplomacyState instance for cooldown checking.
    bot_goals:  BotGoals with prevail_goals/defeat_goals lists.
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
            # Diplomacy always evaluated 1-ply (not mixed into the beam search tree)
            dipl_actions = _gather_actions(
                grid, bot_player, global_cooldown_name, nation_list,
                suspected_human_ri=suspected_human_ri,
                turn_number=turn_number,
                weights=weights,
                dipl_state=dipl_state,
                bot_goals=bot_goals,
                top3_names=top3_names,
                bottom3_names=bottom3_names,
                exclude_diplomacy=False)   # diplomacy-only subset
            dipl_actions = [a for a in dipl_actions if a[1] == 'diplomacy' and a[0] > -1000]
            best_dipl = max(dipl_actions, key=lambda a: a[0]) if dipl_actions else None

            # Military moves via multi-ply lookahead (diplomacy excluded from tree)
            military = _lookahead_best(
                grid, bot_player, global_cooldown_name, nation_list,
                turn_number, suspected_human_ri, weights,
                depth=lookahead_depth - 1, beam_width=lookahead_beam,
                mode=lookahead_mode, eval_weights=eval_weights,
                hybrid_ratio=hybrid_ratio,
                bot_goals=bot_goals,
                top3_names=top3_names,
                bottom3_names=bottom3_names)

            # Pick whichever is better: best diplomacy vs best military
            if best_dipl is not None:
                if military is None:
                    return (*best_dipl, 'intent')
                if hybrid_ratio > 0.0 and lookahead_mode == 'position':
                    from evaluator import evaluate_position
                    root_pos = evaluate_position(grid, bot_secret, nation_list, weights=eval_weights,
                                                 bot_goals=bot_goals)
                    dipl_eff = (1.0 - hybrid_ratio) * best_dipl[0] + hybrid_ratio * root_pos
                else:
                    dipl_eff = best_dipl[0]
                if dipl_eff > military[0]:
                    return (*best_dipl, 'intent')
                return (*military, 'intent')
            if military is None:
                return None
            return (*military, 'intent')
        else:
            # Original 1-ply move scoring
            actions = _gather_actions(grid, bot_player, global_cooldown_name, nation_list,
                                      suspected_human_ri=suspected_human_ri,
                                      turn_number=turn_number,
                                      weights=weights,
                                      dipl_state=dipl_state,
                                      bot_goals=bot_goals,
                                      top3_names=top3_names,
                                      bottom3_names=bottom3_names)
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
        bot_ri = bot_player.secret_nation.color_name
        if bot_goals is not None:
            allied_name_set = set(bot_goals.prevail_goals) | {bot_ri}
        else:
            allied_name_set = {n.color_name for n in bot_player.secret_nation.allies} | {bot_ri}
        eligible = _eligible_nations(bot_player, global_cooldown_name, nation_list)
        pool = []
        for nation in eligible:
            for unit in grid.get_all_nation_units(nation):
                pool += [(0, 'move',   unit, c) for c in grid.get_valid_moves(unit)]
                for c in grid.get_valid_attacks(unit):
                    # Never randomly attack an allied sovereign
                    tq, tr = c
                    allied_sovs = [s for s in grid.sovereigns.get((tq, tr), [])
                                   if s.nation.color_name in allied_name_set
                                   and unit.nation.is_enemy(s.nation)]
                    if not allied_sovs:
                        pool.append((0, 'attack', unit, c))
            for coord in grid.get_recruit_hexes(nation):
                pool.append((0, 'recruit', nation, coord))
            for coord in grid.get_promote_hexes(nation):
                pool.append((0, 'promote', nation, coord))
            for coord in grid.get_promote_knight_hexes(nation):
                pool.append((0, 'promote_knight', nation, coord))
        if not pool:
            return None
        pool = _adaptive_sovereign_adjustments(
            grid, pool, bot_ri, suspected_human_ri, turn_number,
            nation_list=nation_list, bot_goals=bot_goals)
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
