"""
Six Nations — Move Serialization & Execution

Provides a unified pipeline for serializing game actions into JSON-safe dicts
and applying them back to a MapGrid.  Used by:
  - Local UI (main.py) after drag-drop / button clicks
  - Bot AI (bot.py execute_bot_action)
  - Future network ingestion (on_network_move_received)
"""


def serialize_move(move_type, nation_name, unit_type=None,
                   from_hex=None, to_hex=None):
    """
    Produce a JSON-serializable dict describing a game action.

    move_type : 'move' | 'attack' | 'recruit' | 'promote'
    nation_name : color_name of the nation being moved
    unit_type : 'army' | 'champion' | 'sovereign' (None for recruit/promote)
    from_hex  : (q, r) source hex  (None for recruit)
    to_hex    : (q, r) target hex  (None for promote-in-place)
    """
    return {
        'type':      move_type,
        'nation_name': nation_name,
        'unit_type': unit_type,
        'from':      list(from_hex) if from_hex else None,
        'to':        list(to_hex)   if to_hex   else None,
    }


def _find_unit(grid, unit_type, nation_name, q, r):
    """
    Locate a specific unit on the grid by type, nation, and hex.
    Returns the unit object, or None.
    """
    if unit_type == 'sovereign':
        bucket = grid.sovereigns.get((q, r), [])
    elif unit_type == 'champion':
        bucket = grid.champions.get((q, r), [])
    elif unit_type == 'knight':
        bucket = grid.knights.get((q, r), [])
    elif unit_type == 'army':
        bucket = grid.armies.get((q, r), [])
    else:
        return None

    for u in bucket:
        if u.nation.color_name == nation_name:
            return u
    return None


def _find_nation(nation_list, nation_name):
    """Look up a Nation object by color_name."""
    for n in nation_list:
        if n.color_name == nation_name:
            return n
    return None


def apply_serialized_move(grid, move_data, nation_list):
    """
    Execute a move described by a serialized dict.

    Returns (success: bool, msg: str, moved_nation, destroyed: list).
      - moved_nation is the Nation object that was moved (or None on failure).
      - destroyed is a list of destroyed unit objects (empty for non-attacks).
    """
    mtype     = move_data['type']
    nation_name = move_data['nation_name']
    unit_type = move_data.get('unit_type')
    from_hex  = tuple(move_data['from']) if move_data.get('from') else None
    to_hex    = tuple(move_data['to'])   if move_data.get('to')   else None
    nation    = _find_nation(nation_list, nation_name)

    if nation is None:
        return False, f"Unknown nation '{nation_name}'", None, []

    # ── Move ──────────────────────────────────────────────────────────────
    if mtype == 'move':
        if from_hex is None or to_hex is None or unit_type is None:
            return False, "Move requires from, to, and unit_type.", None, []
        unit = _find_unit(grid, unit_type, nation_name, *from_hex)
        if unit is None:
            return False, f"No {unit_type} for nation {nation_name} at {from_hex}.", None, []
        success, msg = grid.apply_move(unit, *to_hex)
        if success:
            return True, msg, nation, []
        return False, msg, None, []

    # ── Attack ────────────────────────────────────────────────────────────
    if mtype == 'attack':
        if from_hex is None or to_hex is None or unit_type is None:
            return False, "Attack requires from, to, and unit_type.", None, []
        unit = _find_unit(grid, unit_type, nation_name, *from_hex)
        if unit is None:
            return False, f"No {unit_type} for nation {nation_name} at {from_hex}.", None, []
        success, msg, destroyed = grid.resolve_attack(unit, *to_hex)
        if success:
            return True, msg, nation, destroyed
        return False, msg, None, []

    # ── Recruit ───────────────────────────────────────────────────────────
    if mtype == 'recruit':
        if to_hex is None:
            return False, "Recruit requires a target hex.", None, []
        grid.recruit_army(nation, *to_hex)
        return True, "Recruited.", nation, []

    # ── Promote to Champion ───────────────────────────────────────────────
    if mtype == 'promote':
        coord = to_hex or from_hex
        if coord is None:
            return False, "Promote requires a hex.", None, []
        armies_here = [a for a in grid.armies.get(coord, [])
                       if a.nation.color_name == nation_name]
        if not armies_here:
            return False, f"No army for nation {nation_name} at {coord}.", None, []
        grid.promote_to_champion(armies_here[0])
        return True, "Promoted to champion.", nation, []

    # ── Promote to Knight ─────────────────────────────────────────────────
    if mtype in ('promote_knight', 'promote_to_knight'):
        coord = to_hex or from_hex
        if coord is None:
            return False, "Promote knight requires a hex.", None, []
        armies_here = [a for a in grid.armies.get(coord, [])
                       if a.nation.color_name == nation_name]
        if not armies_here:
            return False, f"No army for nation {nation_name} at {coord}.", None, []
        grid.promote_to_knight(armies_here[0])
        return True, "Promoted to knight.", nation, []

    return False, f"Unknown move type: {mtype}", None, []
