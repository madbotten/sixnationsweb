"""
Six Nations — Move Serialization & Execution

Provides a unified pipeline for serializing game actions into JSON-safe dicts
and applying them back to a MapGrid.  Used by:
  - Local UI (main.py) after drag-drop / button clicks
  - Bot AI (bot.py execute_bot_action)
  - Future network ingestion (on_network_move_received)
"""


def serialize_move(move_type, nation_ri, unit_type=None,
                   from_hex=None, to_hex=None):
    """
    Produce a JSON-serializable dict describing a game action.

    move_type : 'move' | 'attack' | 'recruit' | 'promote'
    nation_ri : ring_index of the nation being moved
    unit_type : 'army' | 'champion' | 'sovereign' (None for recruit/promote)
    from_hex  : (q, r) source hex  (None for recruit)
    to_hex    : (q, r) target hex  (None for promote-in-place)
    """
    return {
        'type':      move_type,
        'nation_ri': nation_ri,
        'unit_type': unit_type,
        'from':      list(from_hex) if from_hex else None,
        'to':        list(to_hex)   if to_hex   else None,
    }


def _find_unit(grid, unit_type, nation_ri, q, r):
    """
    Locate a specific unit on the grid by type, nation, and hex.
    Returns the unit object, or None.
    """
    if unit_type == 'sovereign':
        bucket = grid.sovereigns.get((q, r), [])
    elif unit_type == 'champion':
        bucket = grid.champions.get((q, r), [])
    elif unit_type == 'army':
        bucket = grid.armies.get((q, r), [])
    else:
        return None

    for u in bucket:
        if u.nation.ring_index == nation_ri:
            return u
    return None


def _find_nation(nation_list, ring_index):
    """Look up a Nation object by ring_index."""
    for n in nation_list:
        if n.ring_index == ring_index:
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
    nation_ri = move_data['nation_ri']
    unit_type = move_data.get('unit_type')
    from_hex  = tuple(move_data['from']) if move_data.get('from') else None
    to_hex    = tuple(move_data['to'])   if move_data.get('to')   else None
    nation    = _find_nation(nation_list, nation_ri)

    if nation is None:
        return False, f"Unknown nation ring_index={nation_ri}", None, []

    # ── Move ──────────────────────────────────────────────────────────────
    if mtype == 'move':
        if from_hex is None or to_hex is None or unit_type is None:
            return False, "Move requires from, to, and unit_type.", None, []
        unit = _find_unit(grid, unit_type, nation_ri, *from_hex)
        if unit is None:
            return False, f"No {unit_type} for nation {nation_ri} at {from_hex}.", None, []
        success, msg = grid.apply_move(unit, *to_hex)
        if success:
            return True, msg, nation, []
        return False, msg, None, []

    # ── Attack ────────────────────────────────────────────────────────────
    if mtype == 'attack':
        if from_hex is None or to_hex is None or unit_type is None:
            return False, "Attack requires from, to, and unit_type.", None, []
        unit = _find_unit(grid, unit_type, nation_ri, *from_hex)
        if unit is None:
            return False, f"No {unit_type} for nation {nation_ri} at {from_hex}.", None, []
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

    # ── Promote ───────────────────────────────────────────────────────────
    if mtype == 'promote':
        coord = to_hex or from_hex
        if coord is None:
            return False, "Promote requires a hex.", None, []
        armies_here = [a for a in grid.armies.get(coord, [])
                       if a.nation.ring_index == nation_ri]
        if not armies_here:
            return False, f"No army for nation {nation_ri} at {coord}.", None, []
        grid.promote_to_champion(armies_here[0])
        return True, "Promoted.", nation, []

    return False, f"Unknown move type: {mtype}", None, []
