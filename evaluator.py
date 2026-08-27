"""
Six Nations — Positional Board Evaluator

Scores a board position from the perspective of a given secret nation.
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
    'champion_approach':   5.0,   # per hex closer an allied champion is to enemy sov

    # Territory
    'territory_control':   2.0,   # per net controlled hex (allied vs enemy)
}

# Ordered list of evaluator weight keys (for evolution gene registration)
EVAL_WEIGHT_KEYS = list(DEFAULT_EVAL_WEIGHTS.keys())


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------

def evaluate_position(grid, secret_nation, nation_list, weights=None):
    """Score the board position from the perspective of secret_nation.

    Parameters:
        grid: MapGrid instance (or snapshot).
        secret_nation: the Nation object of the evaluating player.
        nation_list: list of all 6 Nation objects.
        weights: optional dict of weight overrides. Missing keys fall back
                 to DEFAULT_EVAL_WEIGHTS.

    Returns:
        float score — higher is better for the secret_nation player.
    """
    # Build effective weights: defaults + overrides
    w = dict(DEFAULT_EVAL_WEIGHTS)
    if weights:
        w.update(weights)

    score = 0.0

    enemy_nations = secret_nation.enemy_nations(nation_list)
    allied_nations = [n for n in nation_list if not secret_nation.is_enemy(n)]

    enemy_ri_set = {n.ring_index for n in enemy_nations}
    allied_ri_set = {n.ring_index for n in allied_nations}

    # -----------------------------------------------------------------------
    # 1. Win / loss progress  (ghost nations = sovereigns already killed)
    # -----------------------------------------------------------------------
    for n in enemy_nations:
        if n.is_ghost:
            score += w['ghost_enemy']

    if secret_nation.is_ghost:
        return w['own_sov_dead']  # game over, nothing else matters

    for n in allied_nations:
        if n is not secret_nation and n.is_ghost:
            score += w['ally_sov_dead']

    # -----------------------------------------------------------------------
    # 2. Sovereign vulnerability
    # -----------------------------------------------------------------------

    # Enemy sovereigns — vulnerability is good for us
    for sov_list in grid.sovereigns.values():
        for sov in sov_list:
            ri = sov.nation.ring_index
            if ri in enemy_ri_set:
                trapped = grid.is_trapped(sov)
                supported = grid.is_supported(sov)
                if trapped and not supported:
                    score += w['enemy_killable']
                elif trapped:
                    score += w['enemy_trapped']
                elif not supported:
                    score += w['enemy_unsupported']

            elif ri == secret_nation.ring_index:
                # Own sovereign safety
                trapped = grid.is_trapped(sov)
                supported = grid.is_supported(sov)
                if trapped and not supported:
                    score += w['own_sov_killable']
                elif trapped:
                    score += w['own_sov_trapped']

    # -----------------------------------------------------------------------
    # 3. Material count
    # -----------------------------------------------------------------------
    for army_list in grid.armies.values():
        for army in army_list:
            ri = army.nation.ring_index
            if ri in allied_ri_set:
                score += w['allied_army']
            elif ri in enemy_ri_set:
                score += w['enemy_army']

    for knight_list in grid.knights.values():
        for knight in knight_list:
            ri = knight.nation.ring_index
            if ri in allied_ri_set:
                score += w['allied_knight']
            elif ri in enemy_ri_set:
                score += w['enemy_knight']

    for champ_list in grid.champions.values():
        for champ in champ_list:
            ri = champ.nation.ring_index
            if ri in allied_ri_set:
                score += w['allied_champion']
                if grid.is_supported(champ):
                    score += w['allied_champ_sup']
            elif ri in enemy_ri_set:
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
            if sov.nation.ring_index in enemy_ri_set:
                enemy_sov_positions.append((sov.q, sov.r))

    if enemy_sov_positions:
        # Check allied units adjacent to enemy sovereigns
        for sov_q, sov_r in enemy_sov_positions:
            neighbors = set(grid.get_neighbors(sov_q, sov_r))
            # Allied armies adjacent
            for army_list in grid.armies.values():
                for army in army_list:
                    if army.nation.ring_index in allied_ri_set:
                        if (army.q, army.r) in neighbors:
                            score += w['adjacent_enemy_sov']

            # Allied knights adjacent
            for knight_list in grid.knights.values():
                for knight in knight_list:
                    if knight.nation.ring_index in allied_ri_set:
                        if (knight.q, knight.r) in neighbors:
                            score += w['adjacent_enemy_sov']

            # Allied champions adjacent
            for champ_list in grid.champions.values():
                for champ in champ_list:
                    if champ.nation.ring_index in allied_ri_set:
                        if (champ.q, champ.r) in neighbors:
                            score += w['adjacent_enemy_sov']

        # Allied champion approach distance
        for champ_list in grid.champions.values():
            for champ in champ_list:
                if champ.nation.ring_index in allied_ri_set:
                    min_dist = min(
                        _axial_dist(champ.q, champ.r, sq, sr)
                        for sq, sr in enemy_sov_positions)
                    # Closer = better; max hex distance on the board is ~6
                    approach_bonus = max(0, 6 - min_dist) * w['champion_approach']
                    score += approach_bonus

    # -----------------------------------------------------------------------
    # 5. Territory control
    # -----------------------------------------------------------------------
    if 'territory_control' in w and hasattr(grid, 'tile_control'):
        for owner_ri in grid.tile_control.values():
            if owner_ri is not None:
                if owner_ri in allied_ri_set:
                    score += w['territory_control']
                elif owner_ri in enemy_ri_set:
                    score -= w['territory_control']

    return score
