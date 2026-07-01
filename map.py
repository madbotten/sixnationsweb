"""
Hexagonal Map Engine - Alignments
Handles axial grid geometry, camera viewports, placement validation, and modular rendering.
"""

import math
import pygame
import settings
import util

class Tile:
    def __init__(self, q, r, terrain_type, owner='player'):
        self.q = q
        self.r = r
        self.terrain_type = terrain_type
        self.owner = owner  # 'player', 'bot', or a Faction object
        self.is_stronghold = False
        self.stronghold_strength = 3  # Defensive strength of this stronghold tile
        self.has_artifact = False
        self.artifact = None
        
        # Unique tiles have distinct aesthetic colors when rendering placeholders
        self.glow_color = settings.COLOR_NEON_CYAN
        uniques_lower = [t.lower() for t in settings.UNIQUE_TILES]
        terrain_clean = terrain_type.lower()
        if terrain_clean in uniques_lower:
            # Shift between hot pink, purple, and green for unique tiles
            idx = uniques_lower.index(terrain_clean)
            if idx % 3 == 0:
                self.glow_color = settings.COLOR_NEON_PINK
            elif idx % 3 == 1:
                self.glow_color = settings.COLOR_NEON_PURPLE
            else:
                self.glow_color = settings.COLOR_NEON_GREEN

    def get_surface(self, size):
        # Delegate image loading to cache utility
        return util.load_terrain_image(self.terrain_type, alpha=True, color_fallback=self.glow_color, size=size)

class MapGrid:
    def __init__(self):
        # Key: (q, r), Value: Tile
        self.tiles = {}
        # Key: (q, r), Value: List of Champion units
        self.champions = {}
        # Key: (q, r), Value: List of Army units
        self.armies = {}
        
        # Camera scroll offset (center of the screen)
        # Starting camera is centered on (0, 0)
        self.camera_x = 0
        self.camera_y = 0
        
        self.hex_width = settings.HEX_WIDTH
        self.hex_height = settings.HEX_HEIGHT

    def get_ring_coords(self, n):
        """
        Returns ordered coordinates of concentric Ring n.
        For Ring 0, returns [(0, 0)].
        """
        if n == 0:
            return [(0, 0)]
        results = []
        q, r = 0, -n
        directions = [(1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)]
        for d in directions:
            for _ in range(n):
                results.append((q, r))
                q += d[0]
                r += d[1]
        return results

    def generate_map(self):
        """
        Generates a 37-hex grid:
        - Center 7 hexes (Ring 0 & Ring 1) are random unique terrains with artifacts.
        - Outer 30 hexes (Ring 2 & Ring 3) are divided into 10 adjacent sectors of 3 hexes.
        - Each Faction (0-9) is assigned to a sector such that no two opposed factions start next to each other.
        - The 3 hexes of a faction's sector are placed with their home terrain and owned by the Faction.
        - Exactly one Stronghold is placed in Ring 3 for each Faction.
        """
        import random
        from factions import FACTIONS
        
        self.tiles.clear()
        
        # 1. Place the center 7 unique tiles
        from artifacts import create_artifact_pool
        artifact_pool = create_artifact_pool()
        center_coords = self.get_ring_coords(0) + self.get_ring_coords(1)
        unique_terrains = random.sample(settings.UNIQUE_TILES, len(center_coords))
        
        for coord, terrain in zip(center_coords, unique_terrains):
            q, r = coord
            self.place_tile(q, r, terrain, "system")
            self.tiles[(q, r)].has_artifact = True
            if artifact_pool:
                self.tiles[(q, r)].artifact = artifact_pool.pop(0)
            
        # 2. Find a valid faction placement cycle around the outside
        faction_order = None
        while not faction_order:
            shuffled_factions = list(FACTIONS)
            random.shuffle(shuffled_factions)
            valid = True
            for i in range(10):
                f1 = shuffled_factions[i]
                f2 = shuffled_factions[(i + 1) % 10]
                if f1.isOpposed(f2):
                    valid = False
                    break
            if valid:
                faction_order = shuffled_factions

        # 3. Retrieve Ring 2 and Ring 3 coordinates
        ring2 = self.get_ring_coords(2)
        ring3 = self.get_ring_coords(3)
        outer_coords = ring2 + ring3
        
        # Sort outer coordinates by polar angle
        def get_polar_key(coord):
            q, r = coord
            x, y = self.get_hex_center(q, r)
            angle = math.atan2(y, x)
            if angle < 0:
                angle += 2 * math.pi
            # Sub-sort: outer ring (Ring 3) has distance 3, inner (Ring 2) has distance 2.
            dist = max(abs(q), abs(r), abs(q + r))
            return (angle, -dist)
            
        outer_coords.sort(key=get_polar_key)
        
        # 4. Partition the sorted coordinates into 10 sectors of 3 hexes each
        # And place tiles for each Faction in the cycle
        for idx, faction in enumerate(faction_order):
            sector_coords = outer_coords[idx * 3 : (idx + 1) * 3]
            
            # Place the 3 home terrain tiles
            for coord in sector_coords:
                q, r = coord
                self.place_tile(q, r, faction.home_terrain, faction)
                
            # Randomly pick a tile in the outer ring (Ring 3) to be the Stronghold.
            ring3_candidates = [
                c for c in sector_coords if max(abs(c[0]), abs(c[1]), abs(c[0] + c[1])) == 3
            ]
            
            stronghold_coord = random.choice(ring3_candidates) if ring3_candidates else random.choice(sector_coords)
            self.tiles[stronghold_coord].is_stronghold = True
            
            # Give each faction an army in their stronghold hex at setup
            self.muster_army(faction, stronghold_coord[0], stronghold_coord[1], strength=1)
            
            # Give each faction a champion in their stronghold hex at setup
            from champions import Champion
            champion = Champion(faction, stronghold_coord[0], stronghold_coord[1])
            self.add_champion(champion)

    def place_tile(self, q, r, terrain_type, owner):
        """
        Adds a tile to the map coordinates.
        """
        self.tiles[(q, r)] = Tile(q, r, terrain_type, owner)

    def add_champion(self, champion):
        """
        Adds a champion unit to the map. Supports multiple units at the same location.
        """
        loc = champion.hex_location
        if loc not in self.champions:
            self.champions[loc] = []
        self.champions[loc].append(champion)

    def add_army(self, army):
        """
        Adds an army unit to the map. Supports multiple units at the same location.
        """
        loc = army.hex_location
        if loc not in self.armies:
            self.armies[loc] = []
        self.armies[loc].append(army)

    def remove_army(self, army):
        """
        Removes an army from its current location on the map.
        """
        loc = army.hex_location
        if loc in self.armies:
            if army in self.armies[loc]:
                self.armies[loc].remove(army)
            if not self.armies[loc]:
                del self.armies[loc]

    def remove_champion(self, champion):
        """
        Removes a champion from its current location on the map.
        """
        loc = champion.hex_location
        if loc in self.champions:
            if champion in self.champions[loc]:
                self.champions[loc].remove(champion)
            if not self.champions[loc]:
                del self.champions[loc]

    def can_muster_army(self, faction, q, r):
        """
        Checks if the faction controls the hex (owns the tile) and can muster there.
        """
        tile = self.get_tile(q, r)
        if not tile:
            return False
        return tile.owner == faction

    def muster_army(self, faction, q, r, strength=1):
        """
        Creates and adds an army to the map at (q, r) if controlled by the faction.
        """
        if not self.can_muster_army(faction, q, r):
            raise ValueError(f"Faction {faction.race} does not control hex ({q}, {r}) to muster an army.")
        
        from armies import Army
        index = self.get_next_army_index(faction)
        army = Army(faction, q, r, strength=strength, index=index)
        self.add_army(army)
        return army

    def can_move_army(self, army, target_q, target_r):
        """
        Checks if the army can move to the target coordinates.
        The target hex must have an existing tile, and must be adjacent to the army's current location.
        """
        if not self.get_tile(target_q, target_r):
            return False
        
        current_loc = army.hex_location
        neighbors = self.get_neighbors(current_loc[0], current_loc[1])
        return (target_q, target_r) in neighbors

    def move_army(self, army, new_q, new_r):
        """
        Moves the army to the new location (new_q, new_r) if valid.
        """
        if not self.can_move_army(army, new_q, new_r):
            raise ValueError(f"Army cannot move to ({new_q}, {new_r}) from {army.hex_location}.")
        
        self.remove_army(army)
        army.q = new_q
        army.r = new_r
        self.add_army(army)

    def can_move_champion(self, champion, target_q, target_r):
        """
        Checks if the champion can move to the target coordinates.
        The target hex must have an existing tile, and must be adjacent to the champion's current location.
        """
        if not self.get_tile(target_q, target_r):
            return False
        
        current_loc = champion.hex_location
        neighbors = self.get_neighbors(current_loc[0], current_loc[1])
        return (target_q, target_r) in neighbors

    def move_champion(self, champion, new_q, new_r):
        """
        Moves the champion to the new location (new_q, new_r) if valid.
        """
        if not self.can_move_champion(champion, new_q, new_r):
            raise ValueError(f"Champion cannot move to ({new_q}, {new_r}) from {champion.hex_location}.")
        
        self.remove_champion(champion)
        champion.q = new_q
        champion.r = new_r
        self.add_champion(champion)

        # Claim artifact if present on the target tile and champion has none
        tile = self.get_tile(new_q, new_r)
        if tile and tile.artifact is not None and champion.artifact is None:
            champion.artifact = tile.artifact
            champion.artifact.discovered = True
            tile.artifact = None
            tile.has_artifact = False
            print(f"[Artifact Claimed] {champion.name} claimed {champion.artifact.name}!")
            # Air Sword grants an extra move step this turn
            if champion.artifact.power == "AIR_SWORD":
                champion.moves_remaining = 1
                print(f"[Air Sword] {champion.name} may take one additional move this turn.")

    def get_champion_count(self, faction):
        """
        Returns the number of active champions with the given faction on the grid.
        """
        count = 0
        for loc, c_list in self.champions.items():
            for c in c_list:
                if c.faction == faction:
                    count += 1
        return count

    def get_next_champion_index(self, faction):
        """
        Returns the first unused index (always 1 since only one is allowed) or None if already in play.
        """
        for loc, c_list in self.champions.items():
            for c in c_list:
                if c.faction == faction:
                    return None
        return 1

    def get_army_count(self, faction):
        """
        Returns the number of active armies with the given faction on the grid.
        """
        count = 0
        for loc, a_list in self.armies.items():
            for a in a_list:
                if a.faction == faction:
                    count += 1
        return count

    def get_controlled_hex_count(self, faction):
        """
        Returns the number of hexes controlled by the given faction.
        """
        return sum(1 for tile in self.tiles.values() if tile.owner == faction)

    def calculate_faction_income(self, faction):
        """
        Calculates the gold income for a faction:
        1 gold for each 3 hexes controlled, rounded down, minimum 1 gold.
        """
        controlled_count = self.get_controlled_hex_count(faction)
        return max(1, controlled_count // 3)

    def get_next_army_index(self, faction):
        """
        Returns the first unused index for a given faction.
        """
        used_indices = set()
        for loc, a_list in self.armies.items():
            for a in a_list:
                if a.faction == faction:
                    used_indices.add(a.index)
        # Search sequentially without a maximum cap
        idx = 1
        while idx in used_indices:
            idx += 1
        return idx

    def is_hex_muster_available(self, q, r):
        """
        Returns True always since there is no limit/hex tracking on armies.
        """
        return True


    def get_champion_at_screen_pos(self, mouse_x, mouse_y, viewport_rect):
        """
        Checks if a left-click occurred on any Champion unit nested in the map grid.
        Returns the Champion object if hit, otherwise None.
        """
        view_cx = viewport_rect.x + viewport_rect.width / 2.0
        view_cy = viewport_rect.y + viewport_rect.height / 2.0
        
        # Identify axial coordinates under the mouse
        q, r = self.screen_to_axial(mouse_x, mouse_y, viewport_rect)
        
        champions_list = self.champions.get((q, r), [])
        if not champions_list:
            return None
            
        lx, ly = self.get_hex_center(q, r)
        cx = view_cx + self.camera_x + lx
        cy = view_cy + self.camera_y + ly
        
        num_champs = len(champions_list)
        
        # Dynamic layout scaling based on current hex width (baseline 293)
        scale = self.hex_width / 293.0
        size_val = max(12, int(36 * scale))
        size_val_champ = int(size_val * 1.2)
        unit_size = (size_val_champ, size_val_champ)
        spacing = max(2, int(6 * scale))
        row_padding = max(1, int(3 * scale))
        oy = int(-unit_size[1] / 2.0 - row_padding)  # Top row for Champions (bottoms just above center)
        
        for idx, champ in enumerate(champions_list):
            ox = int((idx - (num_champs - 1) / 2.0) * (unit_size[0] + spacing))
            px = int(cx + ox - unit_size[0] / 2)
            py = int(cy + oy - unit_size[1] / 2)
            
            champ_rect = pygame.Rect(px, py, unit_size[0], unit_size[1])
            if champ_rect.collidepoint(mouse_x, mouse_y):
                return champ
        return None

    def get_army_at_screen_pos(self, mouse_x, mouse_y, viewport_rect):
        """
        Checks if a left-click occurred on any Army unit nested in the map grid.
        Returns the Army object if hit, otherwise None.
        """
        view_cx = viewport_rect.x + viewport_rect.width / 2.0
        view_cy = viewport_rect.y + viewport_rect.height / 2.0
        
        # Identify axial coordinates under the mouse
        q, r = self.screen_to_axial(mouse_x, mouse_y, viewport_rect)
        
        armies_list = self.armies.get((q, r), [])
        if not armies_list:
            return None
            
        lx, ly = self.get_hex_center(q, r)
        cx = view_cx + self.camera_x + lx
        cy = view_cy + self.camera_y + ly
        
        num_armies = len(armies_list)
        
        # Dynamic layout scaling based on current hex width (baseline 293)
        scale = self.hex_width / 293.0
        size_val = max(12, int(36 * scale))
        unit_size = (size_val, size_val)
        spacing = max(2, int(6 * scale))
        row_padding = max(1, int(3 * scale))
        oy = int(unit_size[1] / 2.0 + row_padding)  # Bottom row for Armies (tops just below center)
        
        for idx, army in enumerate(armies_list):
            ox = int((idx - (num_armies - 1) / 2.0) * (unit_size[0] + spacing))
            px = int(cx + ox - unit_size[0] / 2)
            py = int(cy + oy - unit_size[1] / 2)
            
            army_rect = pygame.Rect(px, py, unit_size[0], unit_size[1])
            if army_rect.collidepoint(mouse_x, mouse_y):
                return army
        return None


    def get_tile(self, q, r):
        return self.tiles.get((q, r))

    def get_hex_center(self, q, r):
        """
        Converts axial grid coordinates (q, r) to local cartesian coordinates (x, y) relative to map center.
        """
        x = self.hex_width * 0.75 * q
        y = self.hex_height * (r + q / 2.0)
        return x, y

    def screen_to_axial(self, screen_x, screen_y, viewport_rect):
        """
        Converts screen coordinates to closest integer axial (q, r) coordinates.
        """
        # Calculate coordinate relative to viewport center and camera offset
        view_cx = viewport_rect.x + viewport_rect.width / 2.0
        view_cy = viewport_rect.y + viewport_rect.height / 2.0
        
        local_x = screen_x - view_cx - self.camera_x
        local_y = screen_y - view_cy - self.camera_y
        
        # Generalized squashed fractional axial coordinates
        q = local_x / (self.hex_width * 0.75)
        r = (local_y / self.hex_height) - q / 2.0
        
        return self.hex_round(q, r)

    def hex_round(self, q, r):
        """
        Robustly rounds floating point axial coordinates to the nearest hex grid integer.
        """
        s = -q - r
        
        rq = round(q)
        rr = round(r)
        rs = round(s)
        
        q_diff = abs(rq - q)
        r_diff = abs(rr - r)
        s_diff = abs(rs - s)
        
        if q_diff > r_diff and q_diff > s_diff:
            rq = -rr - rs
        elif r_diff > s_diff:
            rr = -rq - rs
        else:
            rs = -rq - rr
            
        return int(rq), int(rr)

    def get_neighbors(self, q, r):
        """
        Returns the 6 neighbor coordinates for axial coordinate (q, r).
        """
        return [
            (q + 1, r),
            (q - 1, r),
            (q, r + 1),
            (q, r - 1),
            (q + 1, r - 1),
            (q - 1, r + 1)
        ]



    def is_valid_placement(self, q, r, terrain_type=None):
        """
        Validates if a tile can be placed at (q, r).
        1. Coordinate must be empty.
        2. Must have at least one adjacent tile in the current map grid.
        """
        if (q, r) in self.tiles:
            return False
            
        has_neighbor = False
        for n_q, n_r in self.get_neighbors(q, r):
            if (n_q, n_r) in self.tiles:
                has_neighbor = True
                break
                
        return has_neighbor


    def get_valid_placements(self, terrain_type=None):
        """
        Scans all occupied coordinates and gathers unique adjacent empty coordinates that satisfy constraints.
        """
        valid_positions = set()
        for q, r in self.tiles.keys():
            for n_q, n_r in self.get_neighbors(q, r):
                if (n_q, n_r) not in self.tiles:
                    if self.is_valid_placement(n_q, n_r, terrain_type):
                        valid_positions.add((n_q, n_r))
        return list(valid_positions)

    def scroll(self, dx, dy):
        """
        Shifts the map camera.
        """
        self.camera_x += dx
        self.camera_y += dy

    def find_stronghold_coord(self, faction):
        """
        Finds the axial coordinates (q, r) of the stronghold owned by the faction.
        """
        for coord, tile in self.tiles.items():
            if tile.is_stronghold and tile.owner == faction:
                return coord
        return None

    def destroy_stronghold(self, faction):
        """
        When a Stronghold of a faction is destroyed, all units of that Faction
        will also be removed and any hexes in control of that Faction will be
        moved back to owned by none.
        """
        # 1. Remove stronghold status and owner from the stronghold tile
        sh_coord = self.find_stronghold_coord(faction)
        if sh_coord:
            self.tiles[sh_coord].is_stronghold = False
            self.tiles[sh_coord].owner = None
            
        # 2. Move any hexes in control of that Faction back to owned by None
        for coord, tile in self.tiles.items():
            if tile.owner == faction:
                tile.owner = None
                
        # 3. Remove all armies of that Faction
        for coord in list(self.armies.keys()):
            self.armies[coord] = [army for army in self.armies[coord] if army.faction != faction]
            if not self.armies[coord]:
                del self.armies[coord]
                
        # 4. Remove all champions of that Faction
        for coord in list(self.champions.keys()):
            self.champions[coord] = [champ for champ in self.champions[coord] if champ.faction != faction]
            if not self.champions[coord]:
                del self.champions[coord]

    def get_combat_hexes(self, faction):
        """
        Returns a sorted list of axial coordinates (q, r) where the given faction
        has at least one unit (army or champion) and there is at least one opposed unit
        (opposed army, opposed champion, or opposed stronghold).
        """
        from factions import Faction
        combat_hexes = []
        possible_hexes = set(list(self.armies.keys()) + list(self.champions.keys()))
        for (q, r) in possible_hexes:
            has_our_army = any(a.faction == faction for a in self.armies.get((q, r), []))
            has_our_champ = any(c.faction == faction for c in self.champions.get((q, r), []))
            if has_our_army or has_our_champ:
                has_opposed_army = any(faction.isOpposed(a.faction) for a in self.armies.get((q, r), []))
                has_opposed_champ = any(faction.isOpposed(c.faction) for c in self.champions.get((q, r), []))
                
                has_opposed_stronghold = False
                tile = self.tiles.get((q, r))
                if tile and getattr(tile, 'is_stronghold', False) and isinstance(tile.owner, Faction) and faction.isOpposed(tile.owner):
                    has_opposed_stronghold = True
                
                if has_opposed_army or has_opposed_champ or has_opposed_stronghold:
                    combat_hexes.append((q, r))
        combat_hexes.sort()
        return combat_hexes

    def has_combat_for_faction(self, faction):
        """
        Checks if there is any hex containing the given faction's units
        and an opposed faction's units.
        """
        return len(self.get_combat_hexes(faction)) > 0

    def consolidate_armies(self, faction):
        """
        Consolidates all armies of the given faction in each hex into a single army
        with the combined strength.
        """
        for loc in list(self.armies.keys()):
            faction_armies = [a for a in self.armies[loc] if a.faction == faction]
            if len(faction_armies) > 1:
                total_strength = sum(a.strength for a in faction_armies)
                remaining_army = faction_armies[0]
                remaining_army.strength = total_strength
                
                # Remove the rest of the armies of this faction on this hex
                for other_army in faction_armies[1:]:
                    self.remove_army(other_army)



    def center_on_hex(self, q, r):
        """
        Centers the map camera viewport on the given hex coordinate (q, r).
        """
        lx, ly = self.get_hex_center(q, r)
        self.camera_x = -lx
        self.camera_y = -ly


    def draw_hex_polygon(self, surface, cx, cy, w, h, color, width=0):
        """
        Draws a squashed flat-topped hexagon onto a surface with custom width and height.
        """
        vertices = [
            (cx + w / 2.0, cy),
            (cx + w / 4.0, cy + h / 2.0),
            (cx - w / 4.0, cy + h / 2.0),
            (cx - w / 2.0, cy),
            (cx - w / 4.0, cy - h / 2.0),
            (cx + w / 4.0, cy - h / 2.0)
        ]
        pygame.draw.polygon(surface, color, vertices, width)

    def draw(self, screen, viewport_rect, ghost_info=None, dragged_terrain=None, highlight_coords=None, highlight_color=(255, 0, 127)):
        """
        Renders the active map and visual guidelines onto the screen, clipped to viewport_rect.
        ghost_info is a dictionary: {'q': int, 'r': int, 'terrain': str, 'valid': bool}
        """
        # Create a clipper sub-surface or clip drawing region of screen
        original_clip = screen.get_clip()
        screen.set_clip(viewport_rect)
        
        # Calculate viewport center
        view_cx = viewport_rect.x + viewport_rect.width / 2.0
        view_cy = viewport_rect.y + viewport_rect.height / 2.0
        
        # Draw background space grid coordinates (faint aesthetic dots or lines to guide map scale)
        # We can dynamically iterate through visible coordinates
        w = self.hex_width
        h = self.hex_height
        
        # Determine placements based on constraints for currently dragged tile
        all_spots = self.get_valid_placements(None)
        valid_spots = self.get_valid_placements(dragged_terrain) if dragged_terrain else all_spots
        bad_spots = [spot for spot in all_spots if spot not in valid_spots]
        
        # Draw empty valid placement spots as glowing neon grid targets
        for q, r in valid_spots:
            lx, ly = self.get_hex_center(q, r)
            cx = view_cx + self.camera_x + lx
            cy = view_cy + self.camera_y + ly
            
            # Draw hex outline only if visible
            if (viewport_rect.x - w / 2 < cx < viewport_rect.x + viewport_rect.width + w / 2 and
                viewport_rect.y - h / 2 < cy < viewport_rect.y + viewport_rect.height + h / 2):
                
                # Faint glowing outline for placement suggestions
                self.draw_hex_polygon(screen, cx, cy, w - 4, h - 4, (30, 45, 60), width=1)
                pygame.draw.circle(screen, (40, 60, 80), (int(cx), int(cy)), 3)

        # Draw bad spots (constraint violations) in translucent red shading!
        for q, r in bad_spots:
            lx, ly = self.get_hex_center(q, r)
            cx = view_cx + self.camera_x + lx
            cy = view_cy + self.camera_y + ly
            
            # Draw bad hex outline and shading only if visible
            if (viewport_rect.x - w / 2 < cx < viewport_rect.x + viewport_rect.width + w / 2 and
                viewport_rect.y - h / 2 < cy < viewport_rect.y + viewport_rect.height + h / 2):
                
                # Draw transparent filled red shading using a temp Surface
                red_shade = pygame.Surface((w, h), pygame.SRCALPHA)
                self.draw_hex_polygon(red_shade, w / 2.0, h / 2.0, w - 4, h - 4, (255, 30, 60, 80), width=0) # Soft red fill
                self.draw_hex_polygon(red_shade, w / 2.0, h / 2.0, w - 4, h - 4, (255, 30, 60, 255), width=2) # Neon red border
                pygame.draw.circle(red_shade, (255, 30, 60), (int(w / 2.0), int(h / 2.0)), 4)
                
                # Blit red shading onto screen
                screen.blit(red_shade, (int(cx - w / 2.0), int(cy - h / 2.0)))

        # Draw already placed tiles
        tile_size_px = (int(w), int(h))
        for (q, r), tile in self.tiles.items():
            lx, ly = self.get_hex_center(q, r)
            cx = view_cx + self.camera_x + lx
            cy = view_cy + self.camera_y + ly
            
            # Simple visibility clipping to avoid drawing out-of-screen tiles
            if (viewport_rect.x - w < cx < viewport_rect.x + viewport_rect.width + w and
                viewport_rect.y - h < cy < viewport_rect.y + viewport_rect.height + h):
                
                # Retrieve texture surface (uses synthetic fallback if missing)
                tile_surf = tile.get_surface(tile_size_px)
                
                # Blit texture surface centered at (cx, cy)
                blit_x = int(cx - tile_surf.get_width() / 2)
                blit_y = int(cy - tile_surf.get_height() / 2)
                screen.blit(tile_surf, (blit_x, blit_y))
                
                # Draw solid black boundary lines around all placed hexes (commented out per feedback)
                # self.draw_hex_polygon(screen, cx, cy, w - 2, h - 2, (0, 0, 0), width=3)
                

                
                from factions import Faction
                if isinstance(tile.owner, Faction):
                    try:
                        font_owner = util.get_font(10, bold=True)
                        txt_owner = font_owner.render(tile.owner.race.upper(), True, settings.COLOR_NEON_CYAN)
                        screen.blit(txt_owner, txt_owner.get_rect(center=(cx, cy + h / 4.0 + 3.0)))
                    except:
                        pass

                # Render Stronghold and Artifact visual markers
                if getattr(tile, 'is_stronghold', False):
                    try:
                        font_sh = util.get_font(11, bold=True)
                        txt_sh = font_sh.render("STRONGHOLD", True, (255, 215, 0))
                        screen.blit(txt_sh, txt_sh.get_rect(center=(cx, cy - h / 3.0 - 3.0)))
                    except:
                        pass
                elif getattr(tile, 'has_artifact', False) and tile.artifact is not None:
                    try:
                        font_art = util.get_font(10, bold=True)
                        txt_art = font_art.render("ARTIFACT", True, settings.COLOR_NEON_PINK)
                        screen.blit(txt_art, txt_art.get_rect(center=(cx, cy - h / 3.0 - 3.0)))
                    except:
                        pass

                
                # Dynamic layout scaling based on current hex width (baseline 293)
                scale = self.hex_width / 293.0
                size_val = max(12, int(36 * scale))
                unit_size_army = (size_val, size_val)
                unit_size_champ = (int(size_val * 1.2), int(size_val * 1.2))
                spacing = max(2, int(6 * scale))
                border_w = max(1, int(1.2 * scale))
                row_padding = max(1, int(3 * scale))


                # 2. Render Champions in the top row (bottoms just above center)
                champions_list = self.champions.get((q, r), [])
                if champions_list:
                    num_champs = len(champions_list)
                    oy_champ = int(-unit_size_champ[1] / 2.0 - row_padding)
                    for idx, champ in enumerate(champions_list):
                        ox = int((idx - (num_champs - 1) / 2.0) * (unit_size_champ[0] + spacing))
                        px = int(cx + ox - unit_size_champ[0] / 2)
                        py = int(cy + oy_champ - unit_size_champ[1] / 2)
                        
                        champ_surf = champ.get_surface(size=unit_size_champ, mask_type="square")
                        screen.blit(champ_surf, (px, py))
                        
                        glow_color = settings.COLOR_NEON_CYAN
                        pygame.draw.rect(screen, glow_color, (px, py, unit_size_champ[0], unit_size_champ[1]), border_w)

                # 3. Render Armies in the bottom row (tops just below center)
                armies_list = self.armies.get((q, r), [])
                if armies_list:
                    num_armies = len(armies_list)
                    oy_army = int(unit_size_army[1] / 2.0 + row_padding)
                    for idx, army in enumerate(armies_list):
                        ox = int((idx - (num_armies - 1) / 2.0) * (unit_size_army[0] + spacing))
                        px = int(cx + ox - unit_size_army[0] / 2)
                        py = int(cy + oy_army - unit_size_army[1] / 2)
                        
                        army_surf = army.get_surface(size=unit_size_army, mask_type="square")
                        screen.blit(army_surf, (px, py))
                        
                        glow_color = settings.COLOR_NEON_CYAN
                        pygame.draw.rect(screen, glow_color, (px, py, unit_size_army[0], unit_size_army[1]), border_w)

                        # Draw strength number if strength > 1
                        if getattr(army, 'strength', 1) > 1:
                            try:
                                font_num = util.get_font(12, bold=True)
                                txt_num = font_num.render(str(army.strength), True, (255, 255, 255))
                                txt_rect = txt_num.get_rect(center=(px + unit_size_army[0] / 2, py + unit_size_army[1] / 2))
                                # Draw small black circle behind text for maximum contrast
                                pygame.draw.circle(screen, (0, 0, 0), txt_rect.center, max(8, int(txt_num.get_width() / 2.0 + 3)))
                                screen.blit(txt_num, txt_rect)
                            except:
                                pass

        # Draw ghost preview (snapping guideline) under drag and drop
        if ghost_info:
            g_q = ghost_info['q']
            g_r = ghost_info['r']
            g_terrain = ghost_info['terrain']
            g_valid = ghost_info['valid']
            
            lx, ly = self.get_hex_center(g_q, g_r)
            cx = view_cx + self.camera_x + lx
            cy = view_cy + self.camera_y + ly
            
            # Check visibility
            if (viewport_rect.x - w < cx < viewport_rect.x + viewport_rect.width + w and
                viewport_rect.y - h < cy < viewport_rect.y + viewport_rect.height + h):
                
                # Draw ghost surface alpha blended
                ghost_color = settings.COLOR_NEON_CYAN if g_valid else settings.COLOR_NEON_PINK
                
                # Draw translucent glowing polygon filling the ghost cell
                ghost_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                # Compute local hex center relative to ghost surface
                self.draw_hex_polygon(ghost_surface, w / 2.0, h / 2.0, w - 4, h - 4, (*ghost_color, 80), width=0)
                self.draw_hex_polygon(ghost_surface, w / 2.0, h / 2.0, w - 4, h - 4, ghost_color, width=3)
                
                # Try drawing the name of the ghost terrain
                try:
                    font = util.get_font(10, bold=True)
                    text = font.render(g_terrain.upper(), True, (255, 255, 255))
                    text_rect = text.get_rect(center=(w / 2.0, h / 2.0))
                    ghost_surface.blit(text, text_rect)
                except:
                    pass
                
                screen.blit(ghost_surface, (int(cx - w / 2.0), int(cy - h / 2.0)))
                
        # Draw highlight borders around specific tiles if provided
        if highlight_coords:
            for q, r in highlight_coords:
                lx, ly = self.get_hex_center(q, r)
                cx = view_cx + self.camera_x + lx
                cy = view_cy + self.camera_y + ly
                
                if (viewport_rect.x - w / 2 < cx < viewport_rect.x + viewport_rect.width + w / 2 and
                    viewport_rect.y - h / 2 < cy < viewport_rect.y + viewport_rect.height + h / 2):
                    
                    # Draw a nice thick neon glowing outline for movement destinations
                    self.draw_hex_polygon(screen, cx, cy, w - 2, h - 2, highlight_color, width=3)

        # Restore clip
        screen.set_clip(original_clip)
