"""
Hexagonal Map Engine -- Six Nations

Board layout (flat-topped hexagons, axial coordinates):
  Ring 0 : 1  hex  -- center, neutral
  Ring 1 : 6  hexes -- inner ring, neutral
  Ring 2 : 12 hexes -- 6 nation army-start hexes + 6 neutral
  Ring 3 : 18 hexes -- all nation territory (3 per nation + corner)
  Total  : 37 hexes

Each nation owns 4 hexes:
  - 1 corner hex  (ring-3 vertex) -- Sovereign + Champion start here
  - 2 adjacent ring-3 hexes      -- 1 Army each
  - 1 adjacent ring-2 hex        -- 1 Army
"""

import os
import pygame
import settings
import util
from factions import NATIONS, NATIONS_BY_NAME
from armies import Army
from champions import Champion, Sovereign
from knights import Knight


# ---------------------------------------------------------------------------
# Tile
# ---------------------------------------------------------------------------

class Tile:
    def __init__(self, q: int, r: int, owner=None):
        self.q         = q
        self.r         = r
        self.owner     = owner      # None = neutral, Nation = starting territory
        self.is_corner = False      # True for the sovereign/champion-start hex


# ---------------------------------------------------------------------------
# MapGrid
# ---------------------------------------------------------------------------

class MapGrid:
    """Full 37-hex board.  Statically centred; no scroll or zoom."""

    NATION_CORNERS = {
        'Yilerond':  ( 0, -3),
        'Galland':   ( 3, -3),
        'Beldrin':   ( 3,  0),
        'Crestmoor': ( 0,  3),
        'Malkor':    (-3,  3),
        'Ravengard': (-3,  0),
    }

    # {name: [corner, army1, army2, army3]}
    NATION_HEXES = {
        'Yilerond':  [( 0, -3), ( 1, -3), (-1, -2), ( 0, -2)],
        'Galland':   [( 3, -3), ( 2, -3), ( 3, -2), ( 2, -2)],
        'Beldrin':   [( 3,  0), ( 3, -1), ( 2,  1), ( 2,  0)],
        'Crestmoor': [( 0,  3), (-1,  3), ( 1,  2), ( 0,  2)],
        'Malkor':    [(-3,  3), (-2,  3), (-3,  2), (-2,  2)],
        'Ravengard': [(-3,  0), (-3,  1), (-2, -1), (-2,  0)],
    }

    def __init__(self):
        self.tiles        = {}   # (q,r) -> Tile
        self.tile_control = {}   # (q,r) -> Optional[str] (nation color_name or None=UNCLAIMED)
        self.armies       = {}   # (q,r) -> [Army, ...]
        self.knights      = {}   # (q,r) -> [Knight, ...]
        self.champions    = {}   # (q,r) -> [Champion, ...]
        self.sovereigns   = {}   # (q,r) -> [Sovereign, ...]
        self.hex_width    = settings.HEX_WIDTH
        self.hex_height   = settings.HEX_HEIGHT

    # =======================================================================
    # Map generation
    # =======================================================================

    def generate_map(self):
        """Place all 37 hex tiles, starting control, and starting units."""
        from armies    import Army
        from champions import Champion, Sovereign
        from knights   import Knight

        self.tiles.clear()
        self.tile_control.clear()
        self.armies.clear()
        self.knights.clear()
        self.champions.clear()
        self.sovereigns.clear()

        nation_coords = {coord for hexes in self.NATION_HEXES for coord in hexes}

        for coord in (self.get_ring_coords(0)
                      + self.get_ring_coords(1)
                      + self.get_ring_coords(2)):
            if coord not in nation_coords:
                self.tiles[coord] = Tile(coord[0], coord[1], owner=None)
                self.tile_control[coord] = None

        for nation_name, hexes in self.NATION_HEXES.items():
            nation = NATIONS_BY_NAME[nation_name]
            corner = self.NATION_CORNERS[nation_name]
            for i, coord in enumerate(hexes):
                q, r = coord
                t = Tile(q, r, owner=nation)
                if coord == corner:
                    t.is_corner = True
                self.tiles[coord] = t
                self.tile_control[coord] = nation_name
                if i == 0:
                    self.add_sovereign(Sovereign(nation, q, r))
                    self.add_champion(Champion(nation, q, r))
                else:
                    self.add_army(Army(nation, q, r))

    # =======================================================================
    # Snapshot (lightweight deep copy for lookahead simulation)
    # =======================================================================

    def snapshot(self):
        """Return an independent copy of the grid for lookahead simulation.

        Tiles are shared (read-only during play). All units are cloned.
        tile_control is shallow copied.
        Returns (clone_grid, unit_map) where unit_map maps
        id(original_unit) -> cloned_unit, allowing actions scored on the
        original grid to be replayed on the clone.
        """
        clone = MapGrid.__new__(MapGrid)
        clone.tiles        = self.tiles       # shared — never mutated mid-game
        clone.tile_control = dict(self.tile_control)
        clone.hex_width    = self.hex_width
        clone.hex_height   = self.hex_height

        unit_map = {}

        clone.armies = {}
        for coord, army_list in self.armies.items():
            cloned = []
            for a in army_list:
                c = Army(a.nation, a.q, a.r)
                unit_map[id(a)] = c
                cloned.append(c)
            clone.armies[coord] = cloned

        clone.knights = {}
        for coord, knight_list in self.knights.items():
            cloned = []
            for k in knight_list:
                c = Knight(k.nation, k.q, k.r)
                unit_map[id(k)] = c
                cloned.append(c)
            clone.knights[coord] = cloned

        clone.champions = {}
        for coord, champ_list in self.champions.items():
            cloned = []
            for ch in champ_list:
                c = Champion(ch.nation, ch.q, ch.r)
                unit_map[id(ch)] = c
                cloned.append(c)
            clone.champions[coord] = cloned

        clone.sovereigns = {}
        for coord, sov_list in self.sovereigns.items():
            cloned = []
            for s in sov_list:
                c = Sovereign(s.nation, s.q, s.r)
                unit_map[id(s)] = c
                cloned.append(c)
            clone.sovereigns[coord] = cloned

        return clone, unit_map

    # =======================================================================
    # Unit management
    # =======================================================================

    def add_army(self, army):
        self.armies.setdefault(army.hex_location, []).append(army)

    def remove_army(self, army):
        loc = army.hex_location
        if loc in self.armies:
            self.armies[loc] = [a for a in self.armies[loc] if a is not army]
            if not self.armies[loc]:
                del self.armies[loc]

    def add_knight(self, knight):
        self.knights.setdefault(knight.hex_location, []).append(knight)

    def remove_knight(self, knight):
        loc = knight.hex_location
        if loc in self.knights:
            self.knights[loc] = [k for k in self.knights[loc] if k is not knight]
            if not self.knights[loc]:
                del self.knights[loc]

    def add_champion(self, champ):
        self.champions.setdefault(champ.hex_location, []).append(champ)

    def remove_champion(self, champ):
        loc = champ.hex_location
        if loc in self.champions:
            self.champions[loc] = [c for c in self.champions[loc] if c is not champ]
            if not self.champions[loc]:
                del self.champions[loc]

    def add_sovereign(self, sov):
        self.sovereigns.setdefault(sov.hex_location, []).append(sov)

    def remove_sovereign(self, sov):
        loc = sov.hex_location
        if loc in self.sovereigns:
            self.sovereigns[loc] = [s for s in self.sovereigns[loc] if s is not sov]
            if not self.sovereigns[loc]:
                del self.sovereigns[loc]

    def get_units_at(self, q, r):
        return {
            'sovereigns': list(self.sovereigns.get((q, r), [])),
            'champions':  list(self.champions.get((q, r), [])),
            'knights':    list(self.knights.get((q, r), [])),
            'armies':     list(self.armies.get((q, r), [])),
        }

    def get_all_nation_units(self, nation):
        """Return all units (sovereigns, champions, knights, armies) belonging to nation."""
        units = []
        for slist in self.sovereigns.values():
            units.extend(s for s in slist if s.nation is nation)
        for clist in self.champions.values():
            units.extend(c for c in clist if c.nation is nation)
        for klist in self.knights.values():
            units.extend(k for k in klist if k.nation is nation)
        for alist in self.armies.values():
            units.extend(a for a in alist if a.nation is nation)
        return units

    def _army_count(self, nation) -> int:
        """Count active armies and knights for nation (knights count toward army cap)."""
        armies_cnt  = sum(1 for alist in self.armies.values()  for a in alist if a.nation is nation)
        knights_cnt = sum(1 for klist in self.knights.values() for k in klist if k.nation is nation)
        return armies_cnt + knights_cnt

    def _has_knight(self, nation) -> bool:
        return any(
            k.nation is nation
            for klist in self.knights.values() for k in klist
        )

    def _has_champion(self, nation) -> bool:
        return any(
            c.nation is nation
            for clist in self.champions.values() for c in clist
        )

    # =======================================================================
    # Geometry helpers
    # =======================================================================

    def get_ring_coords(self, n: int):
        if n == 0:
            return [(0, 0)]
        results, q, r = [], 0, -n
        for dq, dr in [(1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1)]:
            for _ in range(n):
                results.append((q, r)); q += dq; r += dr
        return results

    def get_hex_center(self, q, r):
        return self.hex_width * 0.75 * q, self.hex_height * (r + q / 2.0)

    def screen_pos(self, q, r):
        lx, ly = self.get_hex_center(q, r)
        return settings.MAP_CENTER_X + lx, settings.MAP_CENTER_Y + ly

    def screen_to_axial(self, sx, sy):
        lx = sx - settings.MAP_CENTER_X
        ly = sy - settings.MAP_CENTER_Y
        q  = lx / (self.hex_width * 0.75)
        r  = (ly / self.hex_height) - q / 2.0
        return self.hex_round(q, r)

    def hex_round(self, q, r):
        s = -q - r
        rq, rr, rs = round(q), round(r), round(s)
        dq, dr, ds = abs(rq-q), abs(rr-r), abs(rs-s)
        if dq > dr and dq > ds: rq = -rr - rs
        elif dr > ds:            rr = -rq - rs
        return int(rq), int(rr)

    def get_neighbors(self, q, r):
        """6 neighbours in fixed direction order (0=right, clockwise)."""
        return [
            (q+1, r  ), (q+1, r-1),
            (q,   r-1), (q-1, r  ),
            (q-1, r+1), (q,   r+1),
        ]

    def get_tile(self, q, r):
        return self.tiles.get((q, r))

    # =======================================================================
    # Game Logic -- support / trap detection
    # =======================================================================

    @staticmethod
    def _are_allied(n1, n2) -> bool:
        """True if two nations are the same or ring-adjacent (allies)."""
        return n1 is n2 or n1.is_ally(n2)

    def is_supported(self, unit) -> bool:
        """
        True if unit has at least one allied unit in the same hex.
        """
        q, r = unit.hex_location
        units = self.get_units_at(q, r)
        nation = unit.nation
        for sov in units['sovereigns']:
            if sov is not unit and self._are_allied(nation, sov.nation):
                return True
        for champ in units['champions']:
            if champ is not unit and self._are_allied(nation, champ.nation):
                return True
        for knight in units.get('knights', []):
            if knight is not unit and self._are_allied(nation, knight.nation):
                return True
        for army in units['armies']:
            if army is not unit and self._are_allied(nation, army.nation):
                return True
        return False

    def _has_enemy_unit_at(self, q, r, nation) -> bool:
        """True if any unit at (q,r) is an enemy of nation."""
        for sov  in self.sovereigns.get((q,r), []):
            if nation.is_enemy(sov.nation):   return True
        for champ in self.champions.get((q,r), []):
            if nation.is_enemy(champ.nation): return True
        for knight in self.knights.get((q,r), []):
            if nation.is_enemy(knight.nation): return True
        for army  in self.armies.get((q,r), []):
            if nation.is_enemy(army.nation):  return True
        return False

    def is_trapped(self, sovereign) -> bool:
        """
        An unsupported sovereign is trapped if enemy units occupy at least
        one pair of geometrically opposite neighbours (directions 0&3, 1&4, 2&5).
        Supported sovereigns are never trapped.
        """
        if self.is_supported(sovereign):
            return False
        q, r   = sovereign.hex_location
        nbrs   = self.get_neighbors(q, r)
        nation = sovereign.nation
        for i in range(3):
            if (self._has_enemy_unit_at(*nbrs[i],   nation) and
                    self._has_enemy_unit_at(*nbrs[i+3], nation)):
                return True
        return False

    def _sovereign_supporters(self, sov):
        """
        Return (supporting_champions, supporting_armies, supporting_sovereigns)
        -- units in the same hex that are allied with sov (excluding sov itself).
        """
        q, r   = sov.hex_location
        nation = sov.nation
        s_champs = [c for c in self.champions.get((q,r),[])
                    if c is not sov and self._are_allied(nation, c.nation)]
        s_armies = [a for a in self.armies.get((q,r),[])
                    if self._are_allied(nation, a.nation)]
        s_knights = [k for k in self.knights.get((q,r),[])
                     if self._are_allied(nation, k.nation)]
        s_sovs   = [s for s in self.sovereigns.get((q,r),[])
                    if s is not sov and self._are_allied(nation, s.nation)]
        return s_champs, s_armies + s_knights, s_sovs

    # =======================================================================
    # Game Logic -- valid move / attack queries
    # =======================================================================

    def _would_be_supported_at(self, nation, nq, nr) -> bool:
        """True if moving a unit of nation to (nq, nr) would place it in a hex with an allied/same-color piece."""
        for sov in self.sovereigns.get((nq, nr), []):
            if self._are_allied(nation, sov.nation):
                return True
        for champ in self.champions.get((nq, nr), []):
            if self._are_allied(nation, champ.nation):
                return True
        for knight in self.knights.get((nq, nr), []):
            if self._are_allied(nation, knight.nation):
                return True
        for army in self.armies.get((nq, nr), []):
            if self._are_allied(nation, army.nation):
                return True
        return False

    def get_valid_moves(self, unit) -> list:
        """
        Return list of (q,r) hexes the unit can move to (non-attack moves only).

        Terrain entry rules by unit type:
          Army / Knight : own, ally, unclaimed, enemy territory. Blocked from neutral.
          Champion      : all terrain types (unclaimed, own, ally, neutral, enemy).
          Sovereign     : own territory only, AND destination must already be supported
                          (a friendly unit present there). No player may move a sovereign
                          to an unsupported hex.
        """
        from armies    import Army
        from champions import Champion, Sovereign
        from knights   import Knight
        q, r   = unit.hex_location
        nation = unit.nation
        valid  = []
        for nq, nr in self.get_neighbors(q, r):
            if not self.get_tile(nq, nr):
                continue
            if self._has_enemy_unit_at(nq, nr, nation):
                continue
            if isinstance(unit, (Army, Knight)) and (self.armies.get((nq, nr)) or self.knights.get((nq, nr))):
                continue          # only one army/knight per hex

            # --- Terrain entry gate ---
            owner_name = self.tile_control.get((nq, nr))  # None = UNCLAIMED

            if isinstance(unit, Sovereign):
                # Sovereign: own territory only
                if owner_name != nation.color_name:
                    continue

            elif isinstance(unit, (Army, Knight)):
                # Army/Knight: blocked from neutral-owned territory
                if owner_name is not None and owner_name != nation.color_name:
                    owner_nation = NATIONS_BY_NAME[owner_name]
                    if nation.get_stance(owner_nation) == 'neutral':
                        continue

            # Champion: no terrain restriction — all hexes allowed

            valid.append((nq, nr))

        # Sovereign: destination must already be supported (universal rule).
        # Prevents any player from walking a sovereign into an isolated hex.
        if isinstance(unit, Sovereign):
            valid = [coord for coord in valid
                     if self._would_be_supported_at(nation, *coord)]

        return valid

    def get_valid_attacks(self, unit) -> list:
        """
        Return list of (q,r) hexes where unit can make a legal attack.
        Only armies, knights, and champions may attack.
        """
        from armies    import Army
        from champions import Champion
        from knights   import Knight
        q, r   = unit.hex_location
        nation = unit.nation
        valid  = set()
        atk_supp = self.is_supported(unit)

        for nq, nr in self.get_neighbors(q, r):
            if not self.get_tile(nq, nr):
                continue

            e_armies  = [a for a in self.armies.get((nq,nr),[])    if nation.is_enemy(a.nation)]
            e_knights = [k for k in self.knights.get((nq,nr),[])   if nation.is_enemy(k.nation)]
            e_champs  = [c for c in self.champions.get((nq,nr),[]) if nation.is_enemy(c.nation)]
            e_sovs    = [s for s in self.sovereigns.get((nq,nr),[]) if nation.is_enemy(s.nation)]

            if isinstance(unit, Army):
                # vs enemy army
                for ea in e_armies:
                    if atk_supp or not self.is_supported(ea):
                        valid.add((nq, nr)); break
                # vs enemy knight: only if attacker is supported
                for ek in e_knights:
                    if atk_supp:
                        valid.add((nq, nr)); break
                # vs trapped+unsupported sovereign (army can't attack champion)
                for es in e_sovs:
                    if not self.is_supported(es) and self.is_trapped(es):
                        valid.add((nq, nr)); break

            elif isinstance(unit, Knight):
                # vs enemy army (unsupported knight attacking unsupported army trades)
                for ea in e_armies:
                    if atk_supp or not self.is_supported(ea):
                        valid.add((nq, nr)); break
                # vs enemy knight (unsupported knight attacking unsupported knight trades)
                for ek in e_knights:
                    if atk_supp or not self.is_supported(ek):
                        valid.add((nq, nr)); break
                # vs unsupported sovereign (no trap required for knights)
                for es in e_sovs:
                    if not self.is_supported(es):
                        valid.add((nq, nr)); break

            elif isinstance(unit, Champion):
                # vs enemy army
                for ea in e_armies:
                    if atk_supp or not self.is_supported(ea):
                        valid.add((nq, nr)); break
                # vs enemy knight
                for ek in e_knights:
                    if atk_supp or not self.is_supported(ek):
                        valid.add((nq, nr)); break
                # vs enemy champion
                for ec in e_champs:
                    if atk_supp or not self.is_supported(ec):
                        valid.add((nq, nr)); break
                # vs enemy sovereign
                for es in e_sovs:
                    sov_supp = self.is_supported(es)
                    if not sov_supp:
                        valid.add((nq, nr)); break
                    if atk_supp:
                        sc, sa, ss = self._sovereign_supporters(es)
                        if not sc:   # not shielded by a champion
                            valid.add((nq, nr)); break

        return list(valid)

    # =======================================================================
    # Game Logic -- applying moves and attacks
    # =======================================================================

    def update_hex_control(self, unit, tq, tr):
        """Update hex control at (tq, tr) when unit moves or advances there.

        Seizure rules:
          - UNCLAIMED (None)  : any Army/Knight/Champion claims it.
          - OWN / ALLY        : no seizure (friendly territory kept).
          - NEUTRAL           : no seizure (champion may pass through).
          - ENEMY             : Army/Knight/Champion seizes it.
          - Ghost-owned       : treated as unclaimed; any Army/Knight/Champion claims it.
        """
        from armies    import Army
        from champions import Champion, Sovereign
        from knights   import Knight

        curr_name = self.tile_control.get((tq, tr))
        unit_name = unit.nation.color_name

        if curr_name is None:
            # UNCLAIMED: first army/knight/champion claims it
            if isinstance(unit, (Army, Knight, Champion)):
                self.tile_control[(tq, tr)] = unit_name
        elif curr_name != unit_name:
            owner_nation = NATIONS_BY_NAME[curr_name]
            if owner_nation.is_ghost:
                # Ghost-owned: treat as unclaimed
                if isinstance(unit, (Army, Knight, Champion)):
                    self.tile_control[(tq, tr)] = unit_name
            elif unit.nation.get_stance(owner_nation) == 'enemy':
                # Enemy territory: seize it
                if isinstance(unit, (Army, Knight, Champion)):
                    self.tile_control[(tq, tr)] = unit_name
            # ally or neutral: no seizure

    def _move_unit(self, unit, tq, tr):
        """Unconditionally relocate unit to (tq, tr) and update territory control."""
        from armies    import Army
        from champions import Champion, Sovereign
        from knights   import Knight
        if isinstance(unit, Army):
            self.remove_army(unit);     unit.q, unit.r = tq, tr; self.add_army(unit)
        elif isinstance(unit, Knight):
            self.remove_knight(unit);   unit.q, unit.r = tq, tr; self.add_knight(unit)
        elif isinstance(unit, Champion):
            self.remove_champion(unit); unit.q, unit.r = tq, tr; self.add_champion(unit)
        elif isinstance(unit, Sovereign):
            self.remove_sovereign(unit); unit.q, unit.r = tq, tr; self.add_sovereign(unit)
        self.update_hex_control(unit, tq, tr)

    def apply_move(self, unit, tq, tr):
        """
        Validate and apply a non-attack move.
        Returns (success: bool, message: str).
        """
        if (tq, tr) not in self.get_valid_moves(unit):
            return False, "That move is not legal."
        self._move_unit(unit, tq, tr)
        return True, "Move applied."

    def resolve_attack(self, attacker, tq, tr, target_type=None):
        """
        Resolve an attack by attacker on hex (tq, tr).

        target_type: 'army' | 'knight' | 'champion' | 'sovereign' | None (auto-select).

        Returns (success: bool, message: str, destroyed: list[unit]).
        If success is False the attack was illegal and nothing was changed.
        When the attacker survives and must advance, it is moved automatically.
        """
        from armies    import Army
        from champions import Champion, Sovereign
        from knights   import Knight

        nation       = attacker.nation
        atk_supp     = self.is_supported(attacker)

        # Collect enemy units in target hex
        e_armies  = [a for a in self.armies.get((tq,tr),[])    if nation.is_enemy(a.nation)]
        e_knights = [k for k in self.knights.get((tq,tr),[])   if nation.is_enemy(k.nation)]
        e_champs  = [c for c in self.champions.get((tq,tr),[]) if nation.is_enemy(c.nation)]
        e_sovs    = [s for s in self.sovereigns.get((tq,tr),[]) if nation.is_enemy(s.nation)]

        # Auto-select target type if not specified
        if target_type is None:
            if e_armies:     target_type = 'army'
            elif e_knights:  target_type = 'knight'
            elif e_champs:   target_type = 'champion'
            elif e_sovs:     target_type = 'sovereign'
            else:            return False, "No enemy units in target hex.", []

        destroyed         = []
        messages          = []
        attacker_lives    = True
        advance           = False
        force_no_advance  = False

        # -------------------------------------------------------------------
        # ARMY attacks
        # -------------------------------------------------------------------
        if isinstance(attacker, Army):

            if target_type == 'army':
                if not e_armies:
                    return False, "No enemy army in that hex.", []
                target = e_armies[0]
                tgt_supp = self.is_supported(target)

                if not atk_supp and tgt_supp:
                    return False, "Illegal: unsupported army cannot attack a supported army.", []
                if not atk_supp and not tgt_supp:
                    self.remove_army(target); self.remove_army(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both armies destroyed.")
                elif atk_supp and not tgt_supp:
                    self.remove_army(target); destroyed.append(target)
                    advance = True; messages.append("Enemy army destroyed, attacker advances.")
                else:   # both supported
                    self.remove_army(target); self.remove_army(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both armies destroyed (both supported).")

            elif target_type == 'knight':
                if not e_knights:
                    return False, "No enemy knight in that hex.", []
                target = e_knights[0]
                tgt_supp = self.is_supported(target)

                if not atk_supp:
                    return False, "Illegal: unsupported army cannot attack a knight.", []
                if atk_supp and not tgt_supp:
                    self.remove_knight(target); destroyed.append(target)
                    advance = True; messages.append("Enemy knight destroyed, attacker advances.")
                else:   # both supported
                    self.remove_knight(target); self.remove_army(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both units destroyed (both supported).")

            elif target_type == 'champion':
                return False, "Illegal: armies cannot attack champions.", []

            elif target_type == 'sovereign':
                if not e_sovs:
                    return False, "No enemy sovereign in that hex.", []
                target = e_sovs[0]
                if self.is_supported(target) or not self.is_trapped(target):
                    return False, "Illegal: army can only attack an unsupported, trapped sovereign.", []
                self.remove_sovereign(target); destroyed.append(target)
                advance = True
                messages.append(f"{target.nation.color_name} sovereign destroyed!")

        # -------------------------------------------------------------------
        # KNIGHT attacks
        # -------------------------------------------------------------------
        elif isinstance(attacker, Knight):

            if target_type == 'army':
                if not e_armies:
                    return False, "No enemy army in that hex.", []
                target = e_armies[0]
                tgt_supp = self.is_supported(target)

                if not atk_supp and tgt_supp:
                    return False, "Illegal: unsupported knight cannot attack a supported army.", []
                if not atk_supp and not tgt_supp:
                    self.remove_army(target); self.remove_knight(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both units destroyed (knight trades with army).")
                elif atk_supp and not tgt_supp:
                    self.remove_army(target); destroyed.append(target)
                    advance = True; messages.append("Enemy army destroyed, attacker advances.")
                else:   # both supported
                    self.remove_army(target); self.remove_knight(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both units destroyed (both supported).")

            elif target_type == 'knight':
                if not e_knights:
                    return False, "No enemy knight in that hex.", []
                target = e_knights[0]
                tgt_supp = self.is_supported(target)

                if not atk_supp and tgt_supp:
                    return False, "Illegal: unsupported knight cannot attack a supported knight.", []
                if not atk_supp and not tgt_supp:
                    self.remove_knight(target); self.remove_knight(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both knights destroyed.")
                elif atk_supp and not tgt_supp:
                    self.remove_knight(target); destroyed.append(target)
                    advance = True; messages.append("Enemy knight destroyed, attacker advances.")
                else:   # both supported
                    self.remove_knight(target); self.remove_knight(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both knights destroyed (both supported).")

            elif target_type == 'champion':
                return False, "Illegal: knights cannot attack champions.", []

            elif target_type == 'sovereign':
                if not e_sovs:
                    return False, "No enemy sovereign in that hex.", []
                target = e_sovs[0]
                if self.is_supported(target):
                    return False, "Illegal: knight can only attack an unsupported sovereign.", []
                self.remove_sovereign(target); destroyed.append(target)
                advance = True
                messages.append(f"{target.nation.color_name} sovereign destroyed!")

        # -------------------------------------------------------------------
        # CHAMPION attacks
        # -------------------------------------------------------------------
        elif isinstance(attacker, Champion):

            if target_type == 'army':
                if not e_armies:
                    return False, "No enemy army in that hex.", []
                target = e_armies[0]
                if not atk_supp and self.is_supported(target):
                    return False, "Illegal: unsupported champion cannot attack a supported army.", []
                self.remove_army(target); destroyed.append(target)
                advance = True
                messages.append("Enemy army destroyed.")

            elif target_type == 'knight':
                if not e_knights:
                    return False, "No enemy knight in that hex.", []
                target = e_knights[0]
                if not atk_supp and self.is_supported(target):
                    return False, "Illegal: unsupported champion cannot attack a supported knight.", []
                self.remove_knight(target); destroyed.append(target)
                advance = True
                messages.append("Enemy knight destroyed.")

            elif target_type == 'champion':
                if not e_champs:
                    return False, "No enemy champion in that hex.", []
                target = e_champs[0]
                tgt_supp = self.is_supported(target)
                if not atk_supp and tgt_supp:
                    return False, "Illegal: unsupported champion cannot attack a supported champion.", []
                if not atk_supp and not tgt_supp:
                    self.remove_champion(target); self.remove_champion(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both champions destroyed.")
                elif atk_supp and not tgt_supp:
                    self.remove_champion(target); destroyed.append(target)
                    advance = True; messages.append("Enemy champion destroyed, attacker advances.")
                else:
                    self.remove_champion(target); self.remove_champion(attacker)
                    destroyed += [target, attacker]; attacker_lives = False
                    messages.append("Both champions destroyed (both supported).")

            elif target_type == 'sovereign':
                if not e_sovs:
                    return False, "No enemy sovereign in that hex.", []
                target = e_sovs[0]
                sov_supp = self.is_supported(target)

                if not atk_supp and sov_supp:
                    return False, "Illegal: unsupported champion cannot attack a supported sovereign.", []

                if not sov_supp:
                    # Unsupported sovereign -- always legal
                    self.remove_sovereign(target); destroyed.append(target)
                    advance = True
                    messages.append(f"{target.nation.color_name} sovereign destroyed!")
                else:
                    # Attacker is supported, sovereign is supported
                    sc, sa, ss = self._sovereign_supporters(target)
                    if sc:
                        return False, "Illegal: champion cannot attack a sovereign supported by a champion.", []
                    elif sa:
                        # Attack hits the supporting army/knight instead
                        unit_guard = sa[0]
                        if isinstance(unit_guard, Army):
                            self.remove_army(unit_guard); destroyed.append(unit_guard)
                            messages.append("Supporting army destroyed; sovereign shielded.")
                        elif isinstance(unit_guard, Knight):
                            self.remove_knight(unit_guard); destroyed.append(unit_guard)
                            messages.append("Supporting knight destroyed; sovereign shielded.")
                    else:
                        # Supported only by another sovereign
                        self.remove_sovereign(target); destroyed.append(target)
                        force_no_advance = True   # rule exception: no advance
                        messages.append(f"{target.nation.color_name} sovereign destroyed! (champion stays)")
        else:
            return False, "Sovereigns cannot attack.", []

        # -------------------------------------------------------------------
        # Forward movement
        # -------------------------------------------------------------------
        if attacker_lives and advance and not force_no_advance:
            still_enemy = self._has_enemy_unit_at(tq, tr, nation)
            unit_there  = bool(self.armies.get((tq, tr)) or self.knights.get((tq, tr)))
            can_advance = not still_enemy and (not isinstance(attacker, (Army, Knight)) or not unit_there)
            if can_advance:
                self._move_unit(attacker, tq, tr)
            else:
                messages.append("Attacker cannot advance (hex not clear).")

        return True, " ".join(messages), destroyed

    # =======================================================================
    # Game Logic -- territory, army capacity, recruitment & promotion
    # =======================================================================

    def get_controlled_hex_count(self, nation) -> int:
        """Return total number of hexes currently controlled by nation."""
        name = nation.color_name
        return sum(1 for owner_name in self.tile_control.values() if owner_name == name)

    def get_max_army_cap(self, nation) -> int:
        """Return maximum armies fieldable by nation: 3 base + 1 for every 3 additional hexes over 4."""
        controlled = self.get_controlled_hex_count(nation)
        extra = max(0, controlled - 4)
        return 3 + (extra // 3)

    def can_muster_army(self, nation) -> bool:
        """True if nation has fewer active armies on the board than its current max cap."""
        return self._army_count(nation) < self.get_max_army_cap(nation)

    def get_valid_muster_hexes(self, nation) -> list:
        """
        Return hexes where a new army may be mustered for nation.
        Conditions:
        1. Nation is not a ghost.
        2. Nation has not reached its max army cap.
        3. Hex is controlled by nation.
        4. Hex does not already contain an army.
        5. Hex is not adjacent to any enemy piece.
        """
        if nation.is_ghost or not self.can_muster_army(nation):
            return []

        name = nation.color_name
        valid = []
        for coord, owner_name in self.tile_control.items():
            if owner_name != name:
                continue
            if self.armies.get(coord):
                continue  # already has an army
            if self.knights.get(coord):
                continue  # already has a knight
            q, r = coord
            # Check adjacency to any enemy piece
            has_adjacent_enemy = False
            for nq, nr in self.get_neighbors(q, r):
                if self._has_enemy_unit_at(nq, nr, nation):
                    has_adjacent_enemy = True
                    break
            if not has_adjacent_enemy:
                valid.append(coord)
        return valid

    def get_recruit_hexes(self, nation) -> list:
        """Alias for get_valid_muster_hexes for backward compatibility."""
        return self.get_valid_muster_hexes(nation)

    def recruit_army(self, nation, q, r):
        """Place a new Army for nation at (q,r). Returns the new Army."""
        from armies import Army
        army = Army(nation, q, r)
        self.add_army(army)
        return army

    def get_promote_hexes(self, nation) -> list:
        """
        Return starting hexes where an army may be promoted to champion.
        Conditions: nation not ghost, no champion on board,
        hex has an army belonging to nation.
        """
        if nation.is_ghost or self._has_champion(nation):
            return []
        return [
            coord for coord in self.NATION_HEXES[nation.color_name]
            if any(a.nation is nation
                   for a in self.armies.get(coord, []))
        ]

    def promote_to_champion(self, army):
        """Remove army and place a Champion in the same hex. Returns the Champion."""
        from champions import Champion
        q, r = army.hex_location
        self.remove_army(army)
        champ = Champion(army.nation, q, r)
        self.add_champion(champ)
        return champ

    def get_promote_knight_hexes(self, nation) -> list:
        """
        Return starting hexes where an army may be promoted to a knight.
        Conditions: nation not ghost, no knight on board,
        hex has an army belonging to nation.
        """
        if nation.is_ghost or self._has_knight(nation):
            return []
        return [
            coord for coord in self.NATION_HEXES[nation.color_name]
            if any(a.nation is nation
                   for a in self.armies.get(coord, []))
        ]

    def promote_to_knight(self, army):
        """Remove army and place a Knight in the same hex. Returns the Knight."""
        from knights import Knight
        q, r = army.hex_location
        self.remove_army(army)
        knight = Knight(army.nation, q, r)
        self.add_knight(knight)
        return knight

    # =======================================================================
    # Game Logic -- win / loss / ghost detection
    # =======================================================================

    def check_ghost_nations(self, all_nations):
        """Mark any nation missing its sovereign as a ghost nation.

        On the turn a nation first becomes a ghost, release its territory so
        tiles resolve to their occupier (or neutral if contested/empty).
        """
        living_sov_nations = {
            s.nation.color_name
            for slist in self.sovereigns.values() for s in slist
        }
        for nation in all_nations:
            was_ghost = nation.is_ghost
            nation.is_ghost = nation.color_name not in living_sov_nations
            if nation.is_ghost and not was_ghost:
                # Nation just collapsed this turn — release its territory
                self.release_ghost_territory(nation)

    def release_ghost_territory(self, nation):
        """Release all tiles owned by a newly-collapsed ghost nation.

        Each tile resolves to:
        - The single occupying nation if exactly one nation has units there
        - Neutral (None) if empty or contested by 2+ nations
        """
        name = nation.color_name
        for coord, owner_name in list(self.tile_control.items()):
            if owner_name != name:
                continue
            # Collect all nations with units on this hex
            occupiers = set()
            for unit_list in (
                self.armies.get(coord, []),
                self.knights.get(coord, []),
                self.champions.get(coord, []),
                self.sovereigns.get(coord, []),
            ):
                for u in unit_list:
                    occupiers.add(u.nation.color_name)
            if len(occupiers) == 1:
                self.tile_control[coord] = next(iter(occupiers))
            else:
                self.tile_control[coord] = None  # empty or contested → unclaimed

    def check_win_condition(self, player, all_nations) -> bool:
        """
        Player wins if 2 of their 3 enemy nations are ghost nations
        (sovereigns destroyed).
        """
        enemies       = player.secret_nation.enemy_nations(all_nations)
        ghost_enemies = [e for e in enemies if e.is_ghost]
        return len(ghost_enemies) >= 2

    def check_loss_condition(self, player) -> bool:
        """Player loses immediately if their own secret nation becomes a ghost."""
        return player.secret_nation.is_ghost

    def count_ghost_nations(self, all_nations) -> int:
        """Return the number of nations whose sovereign has been destroyed."""
        return sum(1 for n in all_nations if n.is_ghost)

    # =======================================================================
    # Rendering helpers
    # =======================================================================

    def draw_hex_polygon(self, surface, cx, cy, w, h, color, width=0):
        verts = [
            (cx + w/2.0, cy       ), (cx + w/4.0, cy + h/2.0),
            (cx - w/4.0, cy + h/2.0), (cx - w/2.0, cy      ),
            (cx - w/4.0, cy - h/2.0), (cx + w/4.0, cy - h/2.0),
        ]
        pygame.draw.polygon(surface, color, verts, width)

    def draw_unit_icon(self, screen, cx, cy, unit_type, nation_color, size=44, frozen=False):
        cx, cy = int(cx), int(cy)
        c = nation_color

        if frozen:
            # White-circle "frozen" style: light disc + smaller symbol inside
            radius = size // 2
            s      = int(size * 0.33)
            pygame.draw.circle(screen, (225, 230, 242), (cx, cy), radius)
            pygame.draw.circle(screen, (150, 158, 180), (cx, cy), radius, 1)
        else:
            s = int(size * 0.42)

        # All unit types use tinted PNG sprites
        scale = 3.2 if unit_type in ('champion', 'knight') else 2.0
        icon_h = int(s * scale)
        sprite_name = {'army': 'army.png',
                       'knight': 'knight.png',
                       'champion': 'champion.png',
                       'sovereign': 'sovereign.png'}.get(unit_type)
        if sprite_name is None:
            return
        template = util.load_image(sprite_name, alpha=True)
        if template is None:
            return
        icon_w = int(icon_h * template.get_width() / template.get_height())
        sprite = util.load_tinted_sprite(sprite_name, c, icon_w, icon_h)
        if sprite is not None:
            screen.blit(sprite, sprite.get_rect(center=(cx, cy)))

    def draw(self, screen: pygame.Surface,
             highlight_move=None, highlight_attack=None,
             drag_unit=None, frozen_nations=None, ghost_nations=None):
        """
        Render hex board and units.
        highlight_move   : set of (q,r) to outline in green (valid moves).
        highlight_attack : set of (q,r) to outline in red   (valid attacks).
        drag_unit        : unit currently being dragged (skip drawing it at original pos).
        ghost_names    : set of color_name values whose territory shading is suppressed.
        """
        w, h = self.hex_width, self.hex_height
        _ghost_names = ghost_nations or set()

        # -- Hex tiles -------------------------------------------------------
        for (q, r), tile in self.tiles.items():
            cx, cy = self.screen_pos(q, r)

            owner_name = self.tile_control.get((q, r))
            if owner_name is not None and owner_name not in _ghost_names:
                owner_nation = NATIONS_BY_NAME[owner_name]
                fill   = owner_nation.color_light
                border = owner_nation.color_rgb
                bwidth = 3 if tile.is_corner else 2
            else:
                fill   = settings.COLOR_HEX_NEUTRAL
                border = settings.COLOR_HEX_BORDER
                bwidth = 1

            self.draw_hex_polygon(screen, cx, cy, w-1, h-1, fill)
            self.draw_hex_polygon(screen, cx, cy, w-1, h-1, border, bwidth)


        # -- Highlights ------------------------------------------------------
        if highlight_move:
            for (q, r) in highlight_move:
                cx, cy = self.screen_pos(q, r)
                self.draw_hex_polygon(screen, cx, cy, w-2, h-2, (60, 220, 80), 3)

        if highlight_attack:
            for (q, r) in highlight_attack:
                cx, cy = self.screen_pos(q, r)
                self.draw_hex_polygon(screen, cx, cy, w-2, h-2, (220, 55, 55), 3)

        # -- Units -----------------------------------------------------------
        UNIT_SIZE    = 40
        UNIT_SPACING = 47

        for (q, r) in self.tiles:
            cx, cy = self.screen_pos(q, r)
            units = (
                [('sovereign', u) for u in self.sovereigns.get((q,r), []) if u is not drag_unit]
                + [('champion', u) for u in self.champions.get((q,r), []) if u is not drag_unit]
                + [('knight',   u) for u in self.knights.get((q,r), [])   if u is not drag_unit]
                + [('army',     u) for u in self.armies.get((q,r), [])    if u is not drag_unit]
            )
            n = len(units)
            if n == 0:
                continue
            for i, (utype, unit) in enumerate(units):
                ux = cx + (i - (n-1)/2.0) * UNIT_SPACING
                frozen = (frozen_nations is not None
                          and unit.nation.color_name in frozen_nations)
                self.draw_unit_icon(screen, ux, cy, utype,
                                    unit.nation.color_rgb, UNIT_SIZE,
                                    frozen=frozen)
