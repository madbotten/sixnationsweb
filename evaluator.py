"""
Six Nations — Positional Board Evaluator

Scores a board position from the perspective of a player's goals (BotGoals).
Higher values = better position for that player.

Used by the multi-ply lookahead in bot.py (mode='position') to evaluate
board states after simulated moves, enabling proper minimax search.

This module has NO pygame or UI dependencies — it reads only grid state.
"""


# ---------------------------------------------------------------------------
# Hex distance helper (axial coordinates)
# ---------------------------------------------------------------------------

def _axial_dist(q1, r1, q2, r2):
    return (abs(q1 - q2) + abs(r1 - r2) + abs((q1 + r1) - (q2 + r2))) // 2


# ---------------------------------------------------------------------------
# Default evaluation weights (starting values — can be overridden by evolved
# weights passed via the `weights` parameter to evaluate_position).
# ---------------------------------------------------------------------------

DEFAULT_EVAL_WEIGHTS = {
    # Win/loss condition
    'ghost_enemy':       500.0,   # per enemy sovereign already killed
    'own_sov_dead':    -10000.0,  # own sovereign killed = catastrophe
    'ally_sov_dead':     -50.0,   # allied (non-self) sovereign killed

    # Sovereign vulnerability
    'enemy_killable':    200.0,   # enemy sovereign trapped + unsupported
    'enemy_trapped':      80.0,   # enemy sovereign trapped but supported
    'enemy_unsupported':  40.0,   # enemy sovereign unsupported but free
    'own_sov_killable': -300.0,   # own sovereign trapped + unsupported
    'own_sov_trapped':  -100.0,   # own sovereign trapped but supported

    # Material
    'allied_army':        15.0,   # per allied army on the board
    'allied_knight':      20.0,   # per allied knight on the board
    'allied_champion':    25.0,   # per allied champion on the board
    'enemy_army':        -10.0,   # per enemy army on the board
    'enemy_knight':      -15.0,   # per enemy knight on the board
    'enemy_champion':    -20.0,   # per enemy champion on the board

    # Champion support
    'allied_champ_sup':   30.0,   # per allied champion on a supported hex
    'enemy_champ_unsup':  20.0,   # per enemy champion on an unsupported hex

    # Proximity / threat
    'adjacent_enemy_sov': 25.0,   # per allied unit adjacent to enemy sovereign
    'champion_approach':   5.0,   # per hex closer a PREVAIL champion is to a DEFEAT sovereign
    'enemy_champ_threat':  5.0,   # per hex closer a DEFEAT champion is to a PREVAIL sovereign
                                  # (closer = larger penalty; mirrors champion_approach)

    # Territory
    'territory_control':   2.0,   # per net controlled hex (allied vs enemy)
}

# Ordered list of evaluator weight keys (for evolution gene registration)
EVAL_WEIGHT_KEYS = list(DEFAULT_EVAL_WEIGHTS.keys())


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------

def _derive_ghost_set(grid):
    """Return a set of color_names whose sovereign is absent from a snapshot grid.

    Used by lookahead code to derive ghost state from a snapshot without
    touching the shared Nation singleton flags (which live on the real game).
    """
    import settings
    surviving = set()
    for sov_list in grid.sovereigns.values():
        for sov in sov_list:
            surviving.add(sov.nation.color_name)
    all_names = set(settings.NATION_NAMES)
    return all_names - surviving


def evaluate_position(grid, bot_goals=None, nation_list=None, weights=None,
                      ghost_name_set=None):
    """Score the board position from the perspective of bot_goals.

    Parameters:
        grid: MapGrid instance (or snapshot).
        bot_goals: optional BotGoals instance with prevail_goals and defeat_goals.
        nation_list: list of all 6 Nation objects.
        weights: optional dict of weight overrides. Missing keys fall back
                 to DEFAULT_EVAL_WEIGHTS.
        ghost_name_set: optional set of color_name values to treat as ghost
                 (sovereign already dead). When provided, overrides n.is_ghost
                 on the Nation singletons. Use this in lookahead snapshots where
                 Nation.is_ghost hasn't been updated.

    Returns:
        float score — higher is better for the evaluating player.
    """
    # Build effective weights: defaults + overrides
    w = dict(DEFAULT_EVAL_WEIGHTS)
    if weights:
        w.update(weights)

    score = 0.0

    if bot_goals is not None:
        prevail_set = set(bot_goals.prevail_goals)
        defeat_set  = set(bot_goals.defeat_goals)
        allied_nations = [n for n in (nation_list or []) if n.color_name in prevail_set]
        enemy_nations  = [n for n in (nation_list or []) if n.color_name in defeat_set]
    else:
        enemy_nations  = []
        allied_nations = []
        prevail_set    = set()
        defeat_set     = set()

    enemy_name_set = {n.color_name for n in enemy_nations}
    allied_name_set = {n.color_name for n in allied_nations}

    def _is_ghost(nation):
        if ghost_name_set is not None:
            return nation.color_name in ghost_name_set
        return nation.is_ghost

    # -----------------------------------------------------------------------
    # 1. Win / loss progress  (ghost nations = sovereigns already killed)
    # -----------------------------------------------------------------------
    if bot_goals is not None:
        # Score defeat targets: killing them gains points, weighted by priority
        for idx, d_name in enumerate(bot_goals.defeat_goals):
            d_mult = (3.0, 2.0, 1.0)[idx] if idx < 3 else 1.0
            dn = next((n for n in (nation_list or []) if n.color_name == d_name), None)
            if dn and _is_ghost(dn):
                score += w['ghost_enemy'] * (d_mult / 2.0)

        # Score prevail targets: protecting them avoids penalty
        for idx, p_name in enumerate(bot_goals.prevail_goals):
            p_mult = (3.0, 2.0, 1.0)[idx] if idx < 3 else 1.0
            pn = next((n for n in (nation_list or []) if n.color_name == p_name), None)
            if pn and _is_ghost(pn):
                score += (-w['ghost_enemy']) * (p_mult / 2.0)

    # -----------------------------------------------------------------------
    # 2. Sovereign vulnerability
    # -----------------------------------------------------------------------

    # Enemy sovereigns — vulnerability is good for us
    for sov_list in grid.sovereigns.values():
        for sov in sov_list:
            ri = sov.nation.color_name
            if ri in enemy_name_set:
                supported = grid.is_supported(sov)
                if not supported:
                    score += w['enemy_killable']
                elif hasattr(grid, 'is_trapped') and grid.is_trapped(sov):
                    score += w['enemy_trapped']

            elif ri in allied_name_set:
                # Friendly sovereign safety
                supported = grid.is_supported(sov)
                if not supported:
                    score += w['own_sov_killable']
                elif hasattr(grid, 'is_trapped') and grid.is_trapped(sov):
                    score += w['own_sov_trapped']

    # -----------------------------------------------------------------------
    # 3. Material count
    # -----------------------------------------------------------------------
    for army_list in grid.armies.values():
        for army in army_list:
            ri = army.nation.color_name
            if ri in allied_name_set:
                score += w['allied_army']
            elif ri in enemy_name_set:
                score += w['enemy_army']

    for knight_list in grid.knights.values():
        for knight in knight_list:
            ri = knight.nation.color_name
            if ri in allied_name_set:
                score += w['allied_knight']
            elif ri in enemy_name_set:
                score += w['enemy_knight']

    for champ_list in grid.champions.values():
        for champ in champ_list:
            ri = champ.nation.color_name
            if ri in allied_name_set:
                score += w['allied_champion']
                if grid.is_supported(champ):
                    score += w['allied_champ_sup']
            elif ri in enemy_name_set:
                score += w['enemy_champion']
                if not grid.is_supported(champ):
                    score += w['enemy_champ_unsup']

    # -----------------------------------------------------------------------
    # 4. Proximity: allied units near enemy sovereigns
    # -----------------------------------------------------------------------

    # Collect enemy sovereign positions
    enemy_sov_positions = []
    for sov_list in grid.sovereigns.values():
        for sov in sov_list:
            if sov.nation.color_name in enemy_name_set:
                enemy_sov_positions.append((sov.q, sov.r))

    if enemy_sov_positions:
        # Check allied units adjacent to enemy sovereigns
        for sov_q, sov_r in enemy_sov_positions:
            neighbors = set(grid.get_neighbors(sov_q, sov_r))
            # Allied armies adjacent
            for army_list in grid.armies.values():
                for army in army_list:
                    if army.nation.color_name in allied_name_set:
                        if (army.q, army.r) in neighbors:
                            score += w['adjacent_enemy_sov']

            # Allied knights adjacent
            for knight_list in grid.knights.values():
                for knight in knight_list:
                    if knight.nation.color_name in allied_name_set:
                        if (knight.q, knight.r) in neighbors:
                            score += w['adjacent_enemy_sov']

            # Allied champions adjacent
            for champ_list in grid.champions.values():
                for champ in champ_list:
                    if champ.nation.color_name in allied_name_set:
                        if (champ.q, champ.r) in neighbors:
                            score += w['adjacent_enemy_sov']

        # PREVAIL champion approach: closer to DEFEAT sovereign = better
        for champ_list in grid.champions.values():
            for champ in champ_list:
                if champ.nation.color_name in allied_name_set:
                    min_dist = min(
                        _axial_dist(champ.q, champ.r, sq, sr)
                        for sq, sr in enemy_sov_positions)
                    # Closer = better; max hex distance on the board is ~6
                    approach_bonus = max(0, 6 - min_dist) * w['champion_approach']
                    score += approach_bonus

    # DEFEAT champion threat: closer to a PREVAIL sovereign = worse for us
    prevail_sov_positions = []
    for sov_list in grid.sovereigns.values():
        for sov in sov_list:
            if sov.nation.color_name in allied_name_set:
                prevail_sov_positions.append((sov.q, sov.r))

    if prevail_sov_positions:
        for champ_list in grid.champions.values():
            for champ in champ_list:
                if champ.nation.color_name in enemy_name_set:
                    min_dist = min(
                        _axial_dist(champ.q, champ.r, sq, sr)
                        for sq, sr in prevail_sov_positions)
                    # Closer = bigger penalty (mirrors champion_approach logic)
                    threat_penalty = max(0, 6 - min_dist) * w['enemy_champ_threat']
                    score -= threat_penalty

    # -----------------------------------------------------------------------
    # 5. Territory control
    # -----------------------------------------------------------------------
    if 'territory_control' in w and hasattr(grid, 'tile_control'):
        for owner_ri in grid.tile_control.values():
            if owner_ri is not None:
                if owner_ri in allied_name_set:
                    score += w['territory_control']
                elif owner_ri in enemy_name_set:
                    score -= w['territory_control']

    return score
