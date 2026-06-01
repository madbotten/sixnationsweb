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
        return util.load_image(self.terrain_type, alpha=True, color_fallback=self.glow_color, size=size)

class MapGrid:
    def __init__(self):
        # Key: (q, r), Value: Tile
        self.tiles = {}
        
        # Camera scroll offset (center of the screen)
        # Starting camera is centered on (0, 0)
        self.camera_x = 0
        self.camera_y = 0
        
        # Populate initial "woods" tile at (0, 0)
        self.place_tile(0, 0, "woods", "system")

    def place_tile(self, q, r, terrain_type, owner):
        """
        Adds a tile to the map coordinates.
        """
        self.tiles[(q, r)] = Tile(q, r, terrain_type, owner)

    def get_tile(self, q, r):
        return self.tiles.get((q, r))

    def get_hex_center(self, q, r):
        """
        Converts axial grid coordinates (q, r) to local cartesian coordinates (x, y) relative to map center.
        """
        x = settings.HEX_WIDTH * 0.75 * q
        y = settings.HEX_HEIGHT * (r + q / 2.0)
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
        q = local_x / (settings.HEX_WIDTH * 0.75)
        r = (local_y / settings.HEX_HEIGHT) - q / 2.0
        
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
        3. Restricted tiles (Limbo, PitofDespair, etc.) cannot be adjacent to each other.
        """
        if (q, r) in self.tiles:
            return False
            
        # Ensure we check case-insensitively or cleanly with the list
        is_restricted_dragging = False
        if terrain_type is not None:
            # Capitalize to match RESTRICTED_TILES casing
            clean_dragged = terrain_type.capitalize() if terrain_type.islower() else terrain_type
            is_restricted_dragging = clean_dragged in settings.RESTRICTED_TILES

        has_neighbor = False
        for n_q, n_r in self.get_neighbors(q, r):
            neighbor_tile = self.tiles.get((n_q, n_r))
            if neighbor_tile is not None:
                has_neighbor = True
                
                # Check restricted placement constraint
                if is_restricted_dragging:
                    clean_neighbor = neighbor_tile.terrain_type.capitalize() if neighbor_tile.terrain_type.islower() else neighbor_tile.terrain_type
                    if clean_neighbor in settings.RESTRICTED_TILES:
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

    def draw(self, screen, viewport_rect, ghost_info=None, dragged_terrain=None):
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
        w = settings.HEX_WIDTH
        h = settings.HEX_HEIGHT
        
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
                
                # Draw hexagon neon trim around placed nodes for extreme visual polish
                # The starting tile gets cyan, player tiles get cyan/green, bot gets purple/pink
                trim_color = settings.COLOR_NEON_CYAN
                if tile.owner == 'bot':
                    trim_color = settings.COLOR_NEON_PURPLE
                elif tile.owner == 'system':
                    trim_color = settings.COLOR_NEON_GREEN
                elif tile.terrain_type in settings.UNIQUE_TILES:
                    trim_color = tile.glow_color
                
                self.draw_hex_polygon(screen, cx, cy, w - 2, h - 2, trim_color, width=1)

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
                
        # Restore clip
        screen.set_clip(original_clip)
