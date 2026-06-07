"""
Hexagonal Map Engine - Alignments
Handles axial grid geometry, camera viewports, placement validation, and modular rendering.
"""

import math
import pygame
import settings
import util
from powers import Power

class Tile:
    def __init__(self, q, r, terrain_type, owner='player'):
        self.q = q
        self.r = r
        self.terrain_type = terrain_type
        self.owner = owner  # 'player', 'bot', or 'system'
        
        # Unique tiles have distinct aesthetic colors when rendering placeholders
        self.glow_color = settings.COLOR_NEON_CYAN
        if terrain_type in settings.UNIQUE_TILES:
            # Shift between hot pink, purple, and green for unique tiles
            idx = settings.UNIQUE_TILES.index(terrain_type)
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
        # Key: (q, r), Value: Power
        self.powers = {}
        # Key: (q, r), Value: List of Champion units
        self.champions = {}
        
        # Camera scroll offset (center of the screen)
        # Starting camera is centered on (0, 0)
        self.camera_x = 0
        self.camera_y = 0
        
        self.hex_width = settings.HEX_WIDTH
        self.hex_height = settings.HEX_HEIGHT
        
        # Populate initial "woods" tile at (0, 0)
        self.place_tile(0, 0, "woods", "system")

    def place_tile(self, q, r, terrain_type, owner):
        """
        Adds a tile to the map coordinates.
        """
        self.tiles[(q, r)] = Tile(q, r, terrain_type, owner)
        
        # Spawn associated Powers when specific tiles are placed
        clean_terrain = terrain_type.replace(" ", "").lower()
        if clean_terrain == "woods" and q == 0 and r == 0:
            # The Void starts in the initial game tile used to start the map
            self.add_power(Power("Void", q, r, strength=10))
        elif clean_terrain == "pitofdespair":
            # The Demon starts in Pit of Despair
            self.add_power(Power("Demon", q, r, strength=10))
        elif clean_terrain == "towerofjustice":
            # The Angel starts in Tower of Justice
            self.add_power(Power("Angel", q, r, strength=10))
        elif clean_terrain == "templeofevil":
            # Rakshasa starts in Temple of Evil
            self.add_power(Power("Rakshasa", q, r, strength=10))
        elif clean_terrain == "tanelorn":
            # Couatl starts in Tanelorn
            self.add_power(Power("Couatl", q, r, strength=10))
        elif clean_terrain == "echoingcaverns":
            # Shoggoth starts in Echoing Caverns
            self.add_power(Power("Shoggoth", q, r, strength=10))
        elif clean_terrain == "obsidianwastes":
            # Dragon starts in Obsidian Wastes
            self.add_power(Power("Dragon", q, r, strength=10))
        elif clean_terrain == "thewilds":
            # Pegasus starts in The Wilds
            self.add_power(Power("Pegasus", q, r, strength=10))
        elif clean_terrain == "limbo":
            # Kirin starts in Limbo
            self.add_power(Power("Kirin", q, r, strength=10))


    def add_power(self, power):
        """
        Adds a power unit to the map. Supports multiple units at the same location.
        """
        loc = power.hex_location
        if loc not in self.powers:
            self.powers[loc] = []
        self.powers[loc].append(power)

    def add_champion(self, champion):
        """
        Adds a champion unit to the map. Supports multiple units at the same location.
        """
        loc = champion.hex_location
        if loc not in self.champions:
            self.champions[loc] = []
        self.champions[loc].append(champion)

    def get_champion_count(self, alignment):
        """
        Returns the number of active champions with the given alignment part on the grid.
        """
        count = 0
        for loc, c_list in self.champions.items():
            for c in c_list:
                if c.alignment.lower() == alignment.lower():
                    count += 1
        return count

    def get_next_champion_index(self, alignment):
        """
        Returns the first unused index (1 to 4) for a given alignment.
        """
        used_indices = set()
        for loc, c_list in self.champions.items():
            for c in c_list:
                if c.alignment.lower() == alignment.lower():
                    used_indices.add(c.index)
        for idx in range(1, 5):
            if idx not in used_indices:
                return idx
        return None

    def get_power_at_screen_pos(self, mouse_x, mouse_y, viewport_rect):
        """
        Checks if a left-click occurred on any Power unit nested in the map grid.
        Returns the Power object if hit, otherwise None.
        """
        view_cx = viewport_rect.x + viewport_rect.width / 2.0
        view_cy = viewport_rect.y + viewport_rect.height / 2.0
        
        # Identify axial coordinates under the mouse
        q, r = self.screen_to_axial(mouse_x, mouse_y, viewport_rect)
        
        powers_list = self.powers.get((q, r), [])
        if not powers_list:
            return None
            
        lx, ly = self.get_hex_center(q, r)
        cx = view_cx + self.camera_x + lx
        cy = view_cy + self.camera_y + ly
        
        num_powers = len(powers_list)
        
        # Dynamic layout scaling based on current hex width (baseline 293)
        scale = self.hex_width / 293.0
        size_val = max(12, int(36 * scale))
        unit_size = (size_val, size_val)
        spacing = max(2, int(6 * scale))
        oy = int(-35 * scale)  # Top row for Powers
        
        for idx, power in enumerate(powers_list):
            ox = int((idx - (num_powers - 1) / 2.0) * (unit_size[0] + spacing))
            px = int(cx + ox - unit_size[0] / 2)
            py = int(cy + oy - unit_size[1] / 2)
            
            power_rect = pygame.Rect(px, py, unit_size[0], unit_size[1])
            if power_rect.collidepoint(mouse_x, mouse_y):
                return power
        return None

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
        unit_size = (size_val, size_val)
        spacing = max(2, int(6 * scale))
        oy = 0  # Middle row for Champions
        
        for idx, champ in enumerate(champions_list):
            ox = int((idx - (num_champs - 1) / 2.0) * (unit_size[0] + spacing))
            px = int(cx + ox - unit_size[0] / 2)
            py = int(cy + oy - unit_size[1] / 2)
            
            champ_rect = pygame.Rect(px, py, unit_size[0], unit_size[1])
            if champ_rect.collidepoint(mouse_x, mouse_y):
                return champ
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

    def get_valid_movement_destinations(self, power):
        """
        Returns a list of axial coordinate tuples (q, r) that are adjacent to the power
        and have a tile placed on the map grid.
        """
        q, r = power.hex_location
        neighbors = self.get_neighbors(q, r)
        valid_destinations = [n for n in neighbors if n in self.tiles]
        return valid_destinations


    def is_valid_placement(self, q, r, terrain_type=None):
        """
        Validates if a tile can be placed at (q, r).
        1. Coordinate must be empty.
        2. Must have at least one adjacent tile in the current map grid.
        3. Restricted tiles (Limbo, PitofDespair, etc.) cannot be adjacent to each other.
        4. Restricted tiles cannot be placed next to the starting hex (0, 0).
        """
        if (q, r) in self.tiles:
            return False
            
        # Lowercase restricted tiles list for robust comparison
        restricted_lower = [t.lower() for t in settings.RESTRICTED_TILES]
        is_restricted_dragging = False
        if terrain_type is not None:
            is_restricted_dragging = terrain_type.replace(" ", "").lower() in restricted_lower

        # Enforce rule: RESTRICTED_TILES may not be placed next to the starting hex (0, 0)
        if is_restricted_dragging and (q, r) in self.get_neighbors(0, 0):
            return False

        has_neighbor = False
        for n_q, n_r in self.get_neighbors(q, r):
            neighbor_tile = self.tiles.get((n_q, n_r))
            if neighbor_tile is not None:
                has_neighbor = True
                
                # Check restricted placement constraint
                if is_restricted_dragging:
                    if neighbor_tile.terrain_type.replace(" ", "").lower() in restricted_lower:
                        return False
                
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

    def center_on_power(self, power):
        """
        Adjusts the camera scroll offsets so that the hex containing the specified power
        is centered in the map viewport.
        """
        if power is not None:
            lx, ly = self.get_hex_center(power.q, power.r)
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
                
                # Draw solid black boundary lines around all placed hexes
                self.draw_hex_polygon(screen, cx, cy, w - 2, h - 2, (0, 0, 0), width=3)
                
                # Dynamic layout scaling based on current hex width (baseline 293)
                scale = self.hex_width / 293.0
                size_val = max(12, int(36 * scale))
                unit_size = (size_val, size_val)
                spacing = max(2, int(6 * scale))
                border_w = max(1, int(1.2 * scale))

                # 1. Render Powers in the top row
                powers_list = self.powers.get((q, r), [])
                if powers_list:
                    num_powers = len(powers_list)
                    oy_power = int(-35 * scale)
                    for idx, power in enumerate(powers_list):
                        ox = int((idx - (num_powers - 1) / 2.0) * (unit_size[0] + spacing))
                        px = int(cx + ox - unit_size[0] / 2)
                        py = int(cy + oy_power - unit_size[1] / 2)
                        
                        power_surf = power.get_surface(size=unit_size, mask_type="square")
                        screen.blit(power_surf, (px, py))
                        
                        glow_color = (189, 0, 255)
                        parts = power.get_alignment_parts()
                        if parts:
                            moral = parts[1]
                            if "good" in moral:
                                glow_color = settings.COLOR_NEON_CYAN
                            elif "evil" in moral:
                                glow_color = settings.COLOR_NEON_PINK
                            elif "neutral" in moral:
                                glow_color = settings.COLOR_NEON_GREEN
                        pygame.draw.rect(screen, glow_color, (px, py, unit_size[0], unit_size[1]), border_w)

                # 2. Render Champions in the middle row
                champions_list = self.champions.get((q, r), [])
                if champions_list:
                    num_champs = len(champions_list)
                    oy_champ = 0
                    for idx, champ in enumerate(champions_list):
                        ox = int((idx - (num_champs - 1) / 2.0) * (unit_size[0] + spacing))
                        px = int(cx + ox - unit_size[0] / 2)
                        py = int(cy + oy_champ - unit_size[1] / 2)
                        
                        champ_surf = champ.get_surface(size=unit_size, mask_type="square")
                        screen.blit(champ_surf, (px, py))
                        
                        glow_color = (189, 0, 255)
                        if champ.alignment == "good":
                            glow_color = settings.COLOR_NEON_CYAN
                        elif champ.alignment == "evil":
                            glow_color = settings.COLOR_NEON_PINK
                        elif champ.alignment == "neutral":
                            glow_color = settings.COLOR_NEON_GREEN
                        elif champ.alignment == "lawful":
                            glow_color = (0, 100, 255)
                        elif champ.alignment == "chaotic":
                            glow_color = (255, 128, 0)
                        pygame.draw.rect(screen, glow_color, (px, py, unit_size[0], unit_size[1]), border_w)

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
                    font = pygame.font.SysFont("Courier", 10, bold=True)
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
