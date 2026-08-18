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

import pygame
import settings
from factions import NATIONS


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

    NATION_CORNERS = [
        ( 0, -3),   # 0 Yellow
        ( 3, -3),   # 1 Green
        ( 3,  0),   # 2 Sky Blue
        ( 0,  3),   # 3 Cobalt
        (-3,  3),   # 4 Magenta
        (-3,  0),   # 5 Crimson
    ]

    # [corner, army1, army2, army3]
    NATION_HEXES = [
        [( 0, -3), ( 1, -3), (-1, -2), ( 0, -2)],   # 0 Yellow
        [( 3, -3), ( 2, -3), ( 3, -2), ( 2, -2)],   # 1 Green
        [( 3,  0), ( 3, -1), ( 2,  1), ( 2,  0)],   # 2 Sky Blue
        [( 0,  3), (-1,  3), ( 1,  2), ( 0,  2)],   # 3 Cobalt
        [(-3,  3), (-2,  3), (-3,  2), (-2,  2)],   # 4 Magenta
        [(-3,  0), (-3,  1), (-2, -1), (-2,  0)],   # 5 Crimson
    ]

    def __init__(self):
        self.tiles      = {}   # (q,r) -> Tile
        self.armies     = {}   # (q,r) -> [Army, ...]
        self.champions  = {}   # (q,r) -> [Champion, ...]
        self.sovereigns = {}   # (q,r) -> [Sovereign, ...]
        self.hex_width  = settings.HEX_WIDTH
        self.hex_height = settings.HEX_HEIGHT

    # =======================================================================
    # Map generation
    # =======================================================================

    def generate_map(self):
        """Place all 37 hex tiles and starting units."""
        from armies    import Army
        from champions import Champion, Sovereign

        self.tiles.clear()
        self.armies.clear()
        self.champions.clear()
        self.sovereigns.clear()

        nation_coords = {coord for hexes in self.NATION_HEXES for coord in hexes}

        for coord in (self.get_ring_coords(0)
                      + self.get_ring_coords(1)
                      + self.get_ring_coords(2)):
            if coord not in nation_coords:
                self.tiles[coord] = Tile(coord[0], coord[1], owner=None)

        for nation_idx, hexes in enumerate(self.NATION_HEXES):
            nation = NATIONS[nation_idx]
            corner = self.NATION_CORNERS[nation_idx]
            for i, coord in enumerate(hexes):
                q, r = coord
                t = Tile(q, r, owner=nation)
                if coord == corner:
                    t.is_corner = True
                self.tiles[coord] = t
                if i == 0:
                    self.add_sovereign(Sovereign(nation, q, r))
                    self.add_champion(Champion(nation, q, r))
                else:
                    self.add_army(Army(nation, q, r))

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
            'armies':     list(self.armies.get((q, r), [])),
        }

    def get_all_nation_units(self, nation):
        """Return all units (sovereigns, champions, armies) belonging to nation."""
        units = []
        for slist in self.sovereigns.values():
            units.extend(s for s in slist if s.nation.ring_index == nation.ring_index)
        for clist in self.champions.values():
            units.extend(c for c in clist if c.nation.ring_index == nation.ring_index)
        for alist in self.armies.values():
            units.extend(a for a in alist if a.nation.ring_index == nation.ring_index)
        return units

    def _army_count(self, nation) -> int:
        return sum(
            1 for alist in self.armies.values()
            for a in alist if a.nation.ring_index == nation.ring_index
        )

    def _has_champion(self, nation) -> bool:
        return any(
            c.nation.ring_index == nation.ring_index
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
        return n1.ring_index == n2.ring_index or n1.is_ally(n2)

    def is_supported(self, unit) -> bool:
        """
        True if unit has at least one allied unit in the same hex.
        (Armies cannot support other armies -- irrelevant since max 1 army
        per hex -- but allied champions/sovereigns do support an army.)
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
        s_sovs   = [s for s in self.sovereigns.get((q,r),[])
                    if s is not sov and self._are_allied(nation, s.nation)]
        return s_champs, s_armies, s_sovs

    # =======================================================================
    # Game Logic -- valid move / attack queries
    # =======================================================================

    def get_valid_moves(self, unit) -> list:
        """
        Return list of (q,r) hexes the unit can move to (non-attack moves only).
        Army   : adjacent hex with no army AND no enemy units.
        Champion/Sovereign: adjacent hex with no enemy units.
        """
        from armies    import Army
        from champions import Champion, Sovereign
        q, r   = unit.hex_location
        nation = unit.nation
        valid  = []
        for nq, nr in self.get_neighbors(q, r):
            if not self.get_tile(nq, nr):
                continue
            if self._has_enemy_unit_at(nq, nr, nation):
                continue
            if isinstance(unit, Army) and self.armies.get((nq, nr)):
                continue          # only one army per hex
            valid.append((nq, nr))
        return valid

    def get_valid_attacks(self, unit) -> list:
        """
        Return list of (q,r) hexes where unit can make a legal attack.
        Only armies and champions may attack.
        """
        from armies    import Army
        from champions import Champion
        q, r   = unit.hex_location
        nation = unit.nation
        valid  = set()
        atk_supp = self.is_supported(unit)

        for nq, nr in self.get_neighbors(q, r):
            if not self.get_tile(nq, nr):
                continue

            e_armies = [a for a in self.armies.get((nq,nr),[])
                        if nation.is_enemy(a.nation)]
            e_champs = [c for c in self.champions.get((nq,nr),[])
                        if nation.is_enemy(c.nation)]
            e_sovs   = [s for s in self.sovereigns.get((nq,nr),[])
                        if nation.is_enemy(s.nation)]

            if isinstance(unit, Army):
                # vs enemy army
                for ea in e_armies:
                    if atk_supp or not self.is_supported(ea):
                        valid.add((nq, nr)); break
                # vs trapped+unsupported sovereign (army can't attack champion)
                for es in e_sovs:
                    if not self.is_supported(es) and self.is_trapped(es):
                        valid.add((nq, nr)); break

            elif isinstance(unit, Champion):
                # vs enemy army
                for ea in e_armies:
                    if atk_supp or not self.is_supported(ea):
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

    def _move_unit(self, unit, tq, tr):
        """Unconditionally relocate unit to (tq, tr)."""
        from armies    import Army
        from champions import Champion, Sovereign
        if isinstance(unit, Army):
            self.remove_army(unit);     unit.q, unit.r = tq, tr; self.add_army(unit)
        elif isinstance(unit, Champion):
            self.remove_champion(unit); unit.q, unit.r = tq, tr; self.add_champion(unit)
        elif isinstance(unit, Sovereign):
            self.remove_sovereign(unit);unit.q, unit.r = tq, tr; self.add_sovereign(unit)

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

        target_type: 'army' | 'champion' | 'sovereign' | None (auto-select).

        Returns (success: bool, message: str, destroyed: list[unit]).
        If success is False the attack was illegal and nothing was changed.
        When the attacker survives and must advance, it is moved automatically.
        """
        from armies    import Army
        from champions import Champion, Sovereign

        nation       = attacker.nation
        atk_supp     = self.is_supported(attacker)

        # Collect enemy units in target hex
        e_armies  = [a for a in self.armies.get((tq,tr),[])    if nation.is_enemy(a.nation)]
        e_champs  = [c for c in self.champions.get((tq,tr),[]) if nation.is_enemy(c.nation)]
        e_sovs    = [s for s in self.sovereigns.get((tq,tr),[]) if nation.is_enemy(s.nation)]

        # Auto-select target type if not specified
        if target_type is None:
            if e_armies:   target_type = 'army'
            elif e_champs: target_type = 'champion'
            elif e_sovs:   target_type = 'sovereign'
            else:          return False, "No enemy units in target hex.", []

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
                messages.append("Enemy army destroyed.")

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
                    messages.append(f"{target.nation.color_name} sovereign destroyed!")
                else:
                    # Attacker is supported, sovereign is supported
                    sc, sa, ss = self._sovereign_supporters(target)
                    if sc:
                        return False, "Illegal: champion cannot attack a sovereign supported by a champion.", []
                    elif sa:
                        # Attack hits the supporting army instead
                        army = sa[0]
                        self.remove_army(army); destroyed.append(army)
                        messages.append(f"Supporting army destroyed; sovereign shielded.")
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
            army_there  = bool(self.armies.get((tq, tr)))
            can_advance = not still_enemy and (not isinstance(attacker, Army) or not army_there)
            if can_advance:
                self._move_unit(attacker, tq, tr)
            else:
                messages.append("Attacker cannot advance (hex not clear).")

        return True, " ".join(messages), destroyed

    # =======================================================================
    # Game Logic -- recruitment & promotion
    # =======================================================================

    def get_recruit_hexes(self, nation) -> list:
        """
        Return starting hexes where a new army may be placed.
        Conditions: nation not ghost, fewer than 3 armies, hex has no army
        and no enemy units.
        """
        if nation.is_ghost or self._army_count(nation) >= 3:
            return []
        return [
            coord for coord in self.NATION_HEXES[nation.ring_index]
            if not self.armies.get(coord)
            and not self._has_enemy_unit_at(*coord, nation)
        ]

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
            coord for coord in self.NATION_HEXES[nation.ring_index]
            if any(a.nation.ring_index == nation.ring_index
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

    # =======================================================================
    # Game Logic -- win / loss / ghost detection
    # =======================================================================

    def check_ghost_nations(self, all_nations):
        """Mark any nation missing its sovereign as a ghost nation."""
        living_sov_nations = {
            s.nation.ring_index
            for slist in self.sovereigns.values() for s in slist
        }
        for nation in all_nations:
            nation.is_ghost = nation.ring_index not in living_sov_nations

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
            radius  = size // 2
            s       = int(size * 0.33)
            pygame.draw.circle(screen, (225, 230, 242), (cx, cy), radius)
            pygame.draw.circle(screen, (150, 158, 180), (cx, cy), radius, 1)
            outline = (130, 140, 165)
        else:
            # Bare-symbol style: larger, directly on hex background
            s       = int(size * 0.42)
            outline = (10, 13, 22)

        if unit_type == 'army':
            sw  = int(s * 0.65)
            pts = [
                (cx - sw, cy - int(s * 0.72)),
                (cx + sw, cy - int(s * 0.72)),
                (cx + sw, cy + int(s * 0.10)),
                (cx,      cy + s             ),
                (cx - sw, cy + int(s * 0.10)),
            ]
            pygame.draw.polygon(screen, c, pts)
            pygame.draw.polygon(screen, outline, pts, 2)

        elif unit_type == 'champion':
            bw = max(3, size // 11)
            gw = int(s * 1.55)
            gh = max(3, size // 11)
            gy = cy + int(s * 0.40)
            pygame.draw.rect(screen, c, (cx - bw//2, cy - s, bw, s * 2))
            pygame.draw.rect(screen, c, (cx - gw//2, gy - gh//2, gw, gh))
            pygame.draw.rect(screen, outline, (cx - bw//2, cy - s, bw, s * 2), 1)
            pygame.draw.rect(screen, outline, (cx - gw//2, gy - gh//2, gw, gh), 1)

        elif unit_type == 'sovereign':
            base_y = cy + int(s * 0.44)
            pts = [
                (cx - s,          base_y              ),
                (cx - s,          cy - int(s * 0.56)  ),
                (cx - int(s*0.4), cy - int(s * 0.10)  ),
                (cx,              cy - s               ),
                (cx + int(s*0.4), cy - int(s * 0.10)  ),
                (cx + s,          cy - int(s * 0.56)  ),
                (cx + s,          base_y              ),
            ]
            pygame.draw.polygon(screen, c, pts)
            pygame.draw.polygon(screen, outline, pts, 2)

    def draw(self, screen: pygame.Surface,
             highlight_move=None, highlight_attack=None,
             drag_unit=None, frozen_nations=None):
        """
        Render hex board and units.
        highlight_move   : set of (q,r) to outline in green (valid moves).
        highlight_attack : set of (q,r) to outline in red   (valid attacks).
        drag_unit        : unit currently being dragged (skip drawing it at original pos).
        """
        w, h = self.hex_width, self.hex_height

        # -- Hex tiles -------------------------------------------------------
        for (q, r), tile in self.tiles.items():
            cx, cy = self.screen_pos(q, r)

            if tile.owner is not None:
                fill   = tile.owner.color_light
                border = tile.owner.color_rgb
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
        UNIT_SIZE    = 44
        UNIT_SPACING = 52

        for (q, r) in self.tiles:
            cx, cy = self.screen_pos(q, r)
            units = (
                [('sovereign', u) for u in self.sovereigns.get((q,r), []) if u is not drag_unit]
                + [('champion', u) for u in self.champions.get((q,r), []) if u is not drag_unit]
                + [('army',     u) for u in self.armies.get((q,r), [])    if u is not drag_unit]
            )
            n = len(units)
            if n == 0:
                continue
            for i, (utype, unit) in enumerate(units):
                ux = cx + (i - (n-1)/2.0) * UNIT_SPACING
                frozen = (frozen_nations is not None
                          and unit.nation.ring_index in frozen_nations)
                self.draw_unit_icon(screen, ux, cy, utype,
                                    unit.nation.color_rgb, UNIT_SIZE,
                                    frozen=frozen)
