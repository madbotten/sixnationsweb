"""
Alignments - Game Entry Point
Implements the multi-phase game engine: Phase 1 (Map Building via drag-and-drop tile snapping
with an automated bot player) and Phase 2 (Full-screen scrollable map visualization with Champion and Army profiles).
"""

import sys
import pygame
import random
# Import configurations, map model, bot system, and helper utilities
import settings
import util
from map import MapGrid
from player import Player
from champions import Champion
from armies import Army




def draw_left_phase_panel(screen, left_panel_rect, current_faction, current_turn_phase, mouse_x, mouse_y):
    """
    Renders the Faction Turn Phase control panel on the left during human player's turn.
    """
    # Draw background panel
    pygame.draw.rect(screen, settings.COLOR_HUD_BG, left_panel_rect)
    pygame.draw.rect(screen, settings.COLOR_NEON_CYAN, left_panel_rect, width=1)
    
    try:
        font_title = pygame.font.SysFont("Courier", 24, bold=True)
        font_label = pygame.font.SysFont("Courier", 14, bold=True)
        font_value = pygame.font.SysFont("Courier", 18)
        
        # Phase Title
        phase_str = "INCOME PHASE" if current_turn_phase == settings.TURN_PHASE_INCOME else "ACTIVE PHASE"
        title_surf = font_title.render(phase_str, True, settings.COLOR_NEON_CYAN)
        screen.blit(title_surf, (30, 40))
        
        # Divider
        pygame.draw.line(screen, settings.COLOR_TEXT_MUTED, (30, 80), (370, 80), 1)
        
        # Faction name info
        lbl_faction = font_label.render("ACTIVE FACTION", True, settings.COLOR_TEXT_MUTED)
        screen.blit(lbl_faction, (30, 110))
        
        val_faction = font_title.render(current_faction.race.upper(), True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_faction, (30, 135))
        
        # Treasury gold info
        lbl_gold = font_label.render("FACTION TREASURY", True, settings.COLOR_TEXT_MUTED)
        screen.blit(lbl_gold, (30, 200))
        
        val_gold = font_value.render(f"🪙 {current_faction.gold} Gold", True, settings.COLOR_NEON_GREEN)
        screen.blit(val_gold, (30, 225))
        
        # "Muster Army" Button (Visual only for now)
        muster_btn_rect = pygame.Rect(30, 400, 340, 50)
        is_hover_muster = muster_btn_rect.collidepoint(mouse_x, mouse_y)
        muster_fill = (40, 45, 55) if is_hover_muster else (25, 29, 38)
        muster_border = settings.COLOR_NEON_CYAN if is_hover_muster else settings.COLOR_TEXT_MUTED
        
        pygame.draw.rect(screen, muster_fill, muster_btn_rect, border_radius=10)
        pygame.draw.rect(screen, muster_border, muster_btn_rect, width=2, border_radius=10)
        
        txt_muster = font_label.render("MUSTER ARMY (COST: 1G)", True, settings.COLOR_TEXT_PRIMARY if is_hover_muster else settings.COLOR_TEXT_MUTED)
        txt_muster_rect = txt_muster.get_rect(center=muster_btn_rect.center)
        screen.blit(txt_muster, txt_muster_rect)
        
        # "Done" Button
        done_btn_rect = pygame.Rect(30, 470, 340, 50)
        is_hover_done = done_btn_rect.collidepoint(mouse_x, mouse_y)
        done_fill = (40, 45, 55) if is_hover_done else (25, 29, 38)
        done_border = settings.COLOR_NEON_CYAN if is_hover_done else settings.COLOR_TEXT_MUTED
        
        pygame.draw.rect(screen, done_fill, done_btn_rect, border_radius=10)
        pygame.draw.rect(screen, done_border, done_btn_rect, width=2, border_radius=10)
        
        txt_done = font_label.render("DONE", True, settings.COLOR_TEXT_PRIMARY if is_hover_done else settings.COLOR_TEXT_MUTED)
        txt_done_rect = txt_done.get_rect(center=done_btn_rect.center)
        screen.blit(txt_done, txt_done_rect)
        
    except Exception as e:
        print(f"[Render Error] Failed to draw phase panel: {e}")


def draw_left_champion_statistics_panel(screen, selected_champion, left_panel_rect, map_grid, mouse_x, mouse_y):
    """
    Renders the statistics HUD panel for the selected Champion unit on the left.
    """
    # Draw panel background glass overlay
    pygame.draw.rect(screen, settings.COLOR_HUD_BG, left_panel_rect)
    
    # Glow color is neon cyan for champions
    glow_color = settings.COLOR_NEON_CYAN
    pygame.draw.rect(screen, glow_color, left_panel_rect, width=1) # Neon border
    
    try:
        # Fonts
        font_hud = pygame.font.SysFont("Courier", 22, bold=True)
        font_label = pygame.font.SysFont("Courier", 14, bold=True)
        font_value = pygame.font.SysFont("Courier", 16)
        font_title_bold = pygame.font.SysFont("Courier", 22, bold=True)
        
        # Champion Image Card Container
        img_rect = pygame.Rect(110, 50, 180, 180)
        pygame.draw.rect(screen, settings.COLOR_BACKGROUND, img_rect, border_radius=15)
        pygame.draw.rect(screen, glow_color, img_rect, width=3, border_radius=15)
        
        # Champion square surface scaling
        champ_surf = selected_champion.get_surface(size=(174, 174), mask_type="square")
        screen.blit(champ_surf, (113, 53))
        
        # Champion Title
        name_text = selected_champion.name.upper()
        name_surf = font_title_bold.render(name_text, True, settings.COLOR_TEXT_PRIMARY)
        name_rect = name_surf.get_rect(center=(200, 270))
        screen.blit(name_surf, name_rect)
        
        # Statistics rows
        start_y = 320
        row_h = 75
        
        # Location Row
        loc_rect = pygame.Rect(30, start_y, 340, 60)
        pygame.draw.rect(screen, (20, 24, 33), loc_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, loc_rect, width=1, border_radius=8)
        
        lbl_loc = font_label.render("LOCATION", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_loc, (45, start_y + 10))
        
        tile = map_grid.get_tile(selected_champion.q, selected_champion.r)
        formatted_loc = util.format_location_name(tile.terrain_type) if tile else "Empty Space"
        val_loc = font_value.render(formatted_loc, True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_loc, (45, start_y + 30))
        
        # Strength Row
        str_rect = pygame.Rect(30, start_y + row_h, 340, 60)
        pygame.draw.rect(screen, (20, 24, 33), str_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, str_rect, width=1, border_radius=8)
        
        lbl_str = font_label.render("STRENGTH", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_str, (45, start_y + row_h + 10))
        
        val_str = font_value.render(str(selected_champion.strength), True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_str, (45, start_y + row_h + 30))
        
        # Horizontal progress bar for strength
        max_str = 15
        bar_w = 200
        bar_h = 10
        bx = 150
        by = start_y + row_h + 33
        pygame.draw.rect(screen, (40, 45, 55), (bx, by, bar_w, bar_h), border_radius=5)
        fill_w = int(bar_w * min(1.0, selected_champion.strength / max_str))
        pygame.draw.rect(screen, settings.COLOR_NEON_GREEN, (bx, by, fill_w, bar_h), border_radius=5)
        
        # Faction Row
        align_rect = pygame.Rect(30, start_y + 2 * row_h, 340, 60)
        pygame.draw.rect(screen, (20, 24, 33), align_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, align_rect, width=1, border_radius=8)
        
        lbl_align = font_label.render("FACTION", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_align, (45, start_y + 2 * row_h + 10))
        
        val_align = font_value.render(selected_champion.faction.race.upper(), True, glow_color)
        screen.blit(val_align, (45, start_y + 2 * row_h + 30))
        
        # Close Button at bottom (y = 800 since there are no moves/summon options)
        close_btn_rect = pygame.Rect(30, 800, 340, 45)
        is_hover_close = close_btn_rect.collidepoint(mouse_x, mouse_y)
        btn_fill = (40, 45, 55) if is_hover_close else (25, 29, 38)
        btn_border = settings.COLOR_NEON_CYAN if is_hover_close else settings.COLOR_TEXT_MUTED
        
        pygame.draw.rect(screen, btn_fill, close_btn_rect, border_radius=10)
        pygame.draw.rect(screen, btn_border, close_btn_rect, width=2, border_radius=10)
        
        lbl_close = font_hud.render("CLOSE PROFILE", True, settings.COLOR_TEXT_PRIMARY if is_hover_close else settings.COLOR_TEXT_MUTED)
        lbl_close_rect = lbl_close.get_rect(center=close_btn_rect.center)
        screen.blit(lbl_close, lbl_close_rect)
        
    except Exception as e:
        print(f"[Render Error] Failed to draw champion stats: {e}")


def draw_left_army_statistics_panel(screen, selected_army, left_panel_rect, map_grid, mouse_x, mouse_y):
    """
    Renders the statistics HUD panel for the selected Army unit on the left.
    """
    # Draw panel background glass overlay
    pygame.draw.rect(screen, settings.COLOR_HUD_BG, left_panel_rect)
    
    # Glow color is neon cyan for armies
    glow_color = settings.COLOR_NEON_CYAN
    pygame.draw.rect(screen, glow_color, left_panel_rect, width=1) # Neon border
    
    try:
        # Fonts
        font_hud = pygame.font.SysFont("Courier", 22, bold=True)
        font_label = pygame.font.SysFont("Courier", 14, bold=True)
        font_value = pygame.font.SysFont("Courier", 16)
        font_title_bold = pygame.font.SysFont("Courier", 22, bold=True)
        
        # Army Image Card Container
        img_rect = pygame.Rect(110, 50, 180, 180)
        pygame.draw.rect(screen, settings.COLOR_BACKGROUND, img_rect, border_radius=15)
        pygame.draw.rect(screen, glow_color, img_rect, width=3, border_radius=15)
        
        # Army square surface scaling
        army_surf = selected_army.get_surface(size=(174, 174), mask_type="square")
        screen.blit(army_surf, (113, 53))
        
        # Army Title
        name_text = selected_army.name.upper()
        name_surf = font_title_bold.render(name_text, True, settings.COLOR_TEXT_PRIMARY)
        name_rect = name_surf.get_rect(center=(200, 270))
        screen.blit(name_surf, name_rect)
        
        # Statistics rows
        start_y = 320
        row_h = 70
        
        # Location Row
        loc_rect = pygame.Rect(30, start_y, 340, 56)
        pygame.draw.rect(screen, (20, 24, 33), loc_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, loc_rect, width=1, border_radius=8)
        
        lbl_loc = font_label.render("LOCATION", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_loc, (45, start_y + 8))
        
        tile = map_grid.get_tile(selected_army.q, selected_army.r)
        formatted_loc = util.format_location_name(tile.terrain_type) if tile else "Empty Space"
        val_loc = font_value.render(formatted_loc, True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_loc, (45, start_y + 26))
        
        # Strength Row
        str_rect = pygame.Rect(30, start_y + row_h, 340, 56)
        pygame.draw.rect(screen, (20, 24, 33), str_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, str_rect, width=1, border_radius=8)
        
        lbl_str = font_label.render("STRENGTH", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_str, (45, start_y + row_h + 8))
        
        val_str = font_value.render(str(selected_army.strength), True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_str, (45, start_y + row_h + 26))
        
        # Horizontal progress bar for strength
        max_str = 15
        bar_w = 200
        bar_h = 10
        bx = 150
        by = start_y + row_h + 29
        pygame.draw.rect(screen, (40, 45, 55), (bx, by, bar_w, bar_h), border_radius=5)
        fill_w = int(bar_w * min(1.0, selected_army.strength / max_str))
        pygame.draw.rect(screen, settings.COLOR_NEON_GREEN, (bx, by, fill_w, bar_h), border_radius=5)
        
        # Owning Faction Row
        align_rect = pygame.Rect(30, start_y + 2 * row_h, 340, 56)
        pygame.draw.rect(screen, (20, 24, 33), align_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, align_rect, width=1, border_radius=8)
        
        lbl_align = font_label.render("OWNING FACTION", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_align, (45, start_y + 2 * row_h + 8))
        
        val_align = font_value.render(selected_army.faction.race.upper(), True, glow_color)
        screen.blit(val_align, (45, start_y + 2 * row_h + 26))
        
        # Close Button at bottom (y = 800 since there are no moves/summon options)
        close_btn_rect = pygame.Rect(30, 800, 340, 45)
        is_hover_close = close_btn_rect.collidepoint(mouse_x, mouse_y)
        btn_fill = (40, 45, 55) if is_hover_close else (25, 29, 38)
        btn_border = settings.COLOR_NEON_CYAN if is_hover_close else settings.COLOR_TEXT_MUTED
        
        pygame.draw.rect(screen, btn_fill, close_btn_rect, border_radius=10)
        pygame.draw.rect(screen, btn_border, close_btn_rect, width=2, border_radius=10)
        
        lbl_close = font_hud.render("CLOSE PROFILE", True, settings.COLOR_TEXT_PRIMARY if is_hover_close else settings.COLOR_TEXT_MUTED)
        lbl_close_rect = lbl_close.get_rect(center=close_btn_rect.center)
        screen.blit(lbl_close, lbl_close_rect)
        
    except Exception as e:
        print(f"[Render Error] Failed to draw army stats: {e}")


def draw_mouseover_tooltip(screen, tooltip_to_draw, mouse_x, mouse_y):
    """
    Renders the mouseover tooltip on top of all UI overlays.
    """
    if tooltip_to_draw is None:
        return
        
    hover_text, glow_color = tooltip_to_draw
    try:
        font_tooltip = pygame.font.SysFont("Courier", 12, bold=True)
        txt_surf = font_tooltip.render(hover_text.upper(), True, settings.COLOR_TEXT_PRIMARY)
        
        tw = txt_surf.get_width() + 16
        th = txt_surf.get_height() + 10
        
        tx = mouse_x + 15
        ty = mouse_y + 15
        
        # Enforce boundary checking
        if tx + tw > settings.SCREEN_WIDTH:
            tx = mouse_x - tw - 5
        if ty + th > settings.SCREEN_HEIGHT:
            ty = mouse_y - th - 5
            
        tooltip_rect = pygame.Rect(tx, ty, tw, th)
        
        # Render using a semi-transparent surface for rich aesthetics
        tooltip_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.rect(tooltip_surf, (20, 24, 33, 240), (0, 0, tw, th), border_radius=6)
        pygame.draw.rect(tooltip_surf, glow_color, (0, 0, tw, th), width=1, border_radius=6)
        
        tooltip_surf.blit(txt_surf, (8, 5))
        screen.blit(tooltip_surf, (tx, ty))
    except Exception as e:
        print(f"[Render Warning] Failed to draw tooltip: {e}")



def draw_hud_status_card(screen, human_player_obj, mouse_x, mouse_y):
    """
    Renders the gameplay HUD status card at the top right, including Zoom buttons.
    """
    try:
        font_title = pygame.font.SysFont("Courier", 18, bold=True)
        font_body = pygame.font.SysFont("Courier", 12)
        
        hud_card = pygame.Surface((450, 80), pygame.SRCALPHA)
        pygame.draw.rect(hud_card, settings.COLOR_HUD_BG, (0, 0, 450, 80), border_radius=10)
        
        pygame.draw.rect(hud_card, settings.COLOR_NEON_GREEN, (0, 0, 450, 80), width=2, border_radius=10)
        status_text = "MAP VIEW MODE"
        color_status = settings.COLOR_NEON_GREEN
        tip_text = f"Secret Faction: {human_player_obj.faction.race} (Ring {human_player_obj.faction.ring_number})"
        txt_scroll = font_body.render("WASD or Arrows: Camera Scroll  |  ESC: Deselect", True, settings.COLOR_TEXT_MUTED)
            
        txt_status = font_title.render(status_text, True, color_status)
        txt_tip = font_body.render(tip_text, True, settings.COLOR_TEXT_PRIMARY)
        
        hud_card.blit(txt_status, (20, 12))
        hud_card.blit(txt_tip, (20, 36))
        hud_card.blit(txt_scroll, (20, 54))

        # Zoom Out Button
        zoom_out_rect = pygame.Rect(355, 10, 28, 28)
        zoom_out_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 355, 20 + 10, 28, 28)
        is_hover_out = zoom_out_global_rect.collidepoint(mouse_x, mouse_y)
        out_fill = (40, 45, 55) if is_hover_out else (25, 29, 38)
        out_border = settings.COLOR_NEON_CYAN if is_hover_out else settings.COLOR_TEXT_MUTED
        pygame.draw.rect(hud_card, out_fill, zoom_out_rect, border_radius=6)
        pygame.draw.rect(hud_card, out_border, zoom_out_rect, width=1, border_radius=6)
        
        font_zoom = pygame.font.SysFont("Courier", 18, bold=True)
        txt_out = font_zoom.render("-", True, settings.COLOR_TEXT_PRIMARY if is_hover_out else settings.COLOR_TEXT_MUTED)
        txt_out_rect = txt_out.get_rect(center=zoom_out_rect.center)
        hud_card.blit(txt_out, txt_out_rect)

        # Zoom In Button
        zoom_in_rect = pygame.Rect(395, 10, 28, 28)
        zoom_in_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 395, 20 + 10, 28, 28)
        is_hover_in = zoom_in_global_rect.collidepoint(mouse_x, mouse_y)
        in_fill = (40, 45, 55) if is_hover_in else (25, 29, 38)
        in_border = settings.COLOR_NEON_CYAN if is_hover_in else settings.COLOR_TEXT_MUTED
        pygame.draw.rect(hud_card, in_fill, zoom_in_rect, border_radius=6)
        pygame.draw.rect(hud_card, in_border, zoom_in_rect, width=1, border_radius=6)
        
        txt_in = font_zoom.render("+", True, settings.COLOR_TEXT_PRIMARY if is_hover_in else settings.COLOR_TEXT_MUTED)
        txt_in_rect = txt_in.get_rect(center=zoom_in_rect.center)
        hud_card.blit(txt_in, txt_in_rect)

        screen.blit(hud_card, (settings.SCREEN_WIDTH - 480, 20))
    except Exception as e:
        print(f"[Render Warning] Failed to draw gameplay HUD: {e}")


def main():
    # 1. Initialize Pygame modules & Audio Mixer
    pygame.init()
    pygame.mixer.init()
    
    # 2. Configure display and clock
    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    pygame.display.set_caption(settings.WINDOW_TITLE)
    clock = pygame.time.Clock()
    
    # 3. Setup Game World State
    map_grid = MapGrid()
    # Zoom out by one level initially so the entire map fits on screen at start
    map_grid.hex_width = int(map_grid.hex_width * 0.9)
    map_grid.hex_height = int(map_grid.hex_width / 1.83125)
    
    game_phase = settings.PHASE_MAIN_GAME
    
    # 4. Generate map automatically at start time
    map_grid.generate_map()
    
    from factions import FACTIONS
    shuffled_factions = list(FACTIONS)
    random.shuffle(shuffled_factions)
    
    human_player_obj = Player(faction=shuffled_factions[0])
    bot_player_obj = Player(faction=shuffled_factions[1])
    
    # 5. Play startup chime (rising synthesizer sound)
    util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100) # C5
    pygame.time.delay(120)
    util.play_sound(filename=None, volume=0.5, pitch_hz=659.25, duration_ms=200) # E5
    
    running = True

    # --- Turn & Phase State Tracking ---
    # Two-player game: Index 0 is Human player, Index 1 is Bot player.
    players = [human_player_obj, bot_player_obj]
    current_player_idx = 0
    current_faction = None
    current_turn_phase = None
    previous_faction_by_player = [None, None]

    # Helper function to start a player's turn
    def start_player_turn(player_index):
        nonlocal current_player_idx, current_faction, current_turn_phase
        current_player_idx = player_index
        player = players[player_index]
        
        # Choose the next faction, preventing picking the same faction consecutively
        prev_f = previous_faction_by_player[player_index]
        chosen_f = player.choose_next_faction(previous_faction=prev_f)
        previous_faction_by_player[player_index] = chosen_f
        current_faction = chosen_f
        
        # Start at Income Phase
        current_turn_phase = settings.TURN_PHASE_INCOME
        
        # Calculate and credit income
        income = map_grid.calculate_faction_income(chosen_f)
        chosen_f.gold += income
        print(f"[Turn Start] Player {player_index} controls {chosen_f.race}. Phase: Income. Added {income} gold (Total: {chosen_f.gold}).")
        
        # If human player, center camera on their Stronghold
        if player_index == 0:
            sh_coord = map_grid.find_stronghold_coord(chosen_f)
            if sh_coord:
                map_grid.center_on_hex(sh_coord[0], sh_coord[1])

    # Helper function to advance phase
    def advance_turn_phase():
        nonlocal current_turn_phase
        if current_turn_phase == settings.TURN_PHASE_INCOME:
            current_turn_phase = settings.TURN_PHASE_MOVE
        elif current_turn_phase == settings.TURN_PHASE_MOVE:
            current_turn_phase = settings.TURN_PHASE_COMBAT
        elif current_turn_phase == settings.TURN_PHASE_COMBAT:
            current_turn_phase = settings.TURN_PHASE_CONTROL
        elif current_turn_phase == settings.TURN_PHASE_CONTROL:
            current_turn_phase = settings.TURN_PHASE_VICTORY
        elif current_turn_phase == settings.TURN_PHASE_VICTORY:
            # End of faction turn, proceed to next player
            next_player_idx = 1 - current_player_idx
            start_player_turn(next_player_idx)

    # Initialize the first turn!
    start_player_turn(0)

    # --- PHASE 2: MAIN GAMEPLAY LOOP (MAP VIEWING) ---
    selected_champion = None
    selected_army = None
    
    # Load and scale TenFactions.jpg to fit the screen overlay
    try:
        ten_factions_img_raw = pygame.image.load("TenFactions.jpg")
        img_w, img_h = ten_factions_img_raw.get_size()
        scale_factor = min(1200 / img_w, 850 / img_h)
        scaled_w = int(img_w * scale_factor)
        scaled_h = int(img_h * scale_factor)
        ten_factions_img = pygame.transform.smoothscale(ten_factions_img_raw, (scaled_w, scaled_h))
    except Exception as e:
        print(f"Error loading TenFactions.jpg: {e}")
        ten_factions_img = None

    show_ring_window = False
    active_faction_profile = None
    ring_btn_rect = pygame.Rect(20, 20, 100, 36)
    

    
    while running and game_phase == settings.PHASE_MAIN_GAME:
        dt = clock.tick(settings.FPS) / 1000.0
        
        # --- Bot Player Turn Automation ---
        if current_player_idx == 1:
            while current_player_idx == 1:
                advance_turn_phase()
                
        # --- A. Keyboard Camera Scrolling (WASD / Arrows) ---
        if not show_ring_window and active_faction_profile is None:
            keys = pygame.key.get_pressed()
            scroll_dx = 0
            scroll_dy = 0
            current_speed = settings.SCROLL_SPEED * dt
            
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                scroll_dx += current_speed
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                scroll_dx -= current_speed
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                scroll_dy += current_speed
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                scroll_dy -= current_speed
                
            map_grid.scroll(scroll_dx, scroll_dy)
        
        # Get mouse variables
        mouse_x, mouse_y = pygame.mouse.get_pos()

        # Define layout viewport boundaries dynamically based on selection and human turn status
        if selected_champion is not None or selected_army is not None or current_player_idx == 0:
            left_panel_rect = pygame.Rect(0, 0, settings.PANEL_WIDTH, settings.SCREEN_HEIGHT)
            map_viewport_rect = pygame.Rect(settings.PANEL_WIDTH, 0, settings.SCREEN_WIDTH - settings.PANEL_WIDTH, settings.SCREEN_HEIGHT)
        else:
            left_panel_rect = pygame.Rect(0, 0, 0, 0)
            map_viewport_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)

        # --- B. Main Game Event Processing ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if show_ring_window:
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                    show_ring_window = False
                    util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                continue

            if active_faction_profile is not None:
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                    active_faction_profile = None
                    util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                continue
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if selected_champion is not None:
                        selected_champion = None
                        util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                    elif selected_army is not None:
                        selected_army = None
                        util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                    else:
                        running = False
                        
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    # Check "Ring" button first
                    if ring_btn_rect.collidepoint(mouse_x, mouse_y):
                        show_ring_window = True
                        util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                        continue

                    # Check HUD Zoom buttons first
                    zoom_out_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 355, 20 + 10, 28, 28)
                    zoom_in_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 395, 20 + 10, 28, 28)
                    
                    if zoom_out_global_rect.collidepoint(mouse_x, mouse_y):
                        # Zoom out
                        new_w = int(map_grid.hex_width * 0.9)
                        if new_w >= 100:
                            map_grid.hex_width = new_w
                            map_grid.hex_height = int(new_w / 1.83125)
                            util.play_sound(filename=None, volume=0.3, pitch_hz=440.0, duration_ms=50)
                        continue
                    elif zoom_in_global_rect.collidepoint(mouse_x, mouse_y):
                        # Zoom in
                        new_w = int(map_grid.hex_width * 1.1)
                        if new_w <= 600:
                            map_grid.hex_width = new_w
                            map_grid.hex_height = int(new_w / 1.83125)
                            util.play_sound(filename=None, volume=0.3, pitch_hz=587.33, duration_ms=50)
                        continue

                    clicked_close = False
                    
                    # Check panel buttons if selection is active
                    if selected_champion is not None and left_panel_rect.collidepoint(mouse_x, mouse_y):
                        close_btn_rect = pygame.Rect(30, 800, 340, 45)
                        if close_btn_rect.collidepoint(mouse_x, mouse_y):
                            selected_champion = None
                            clicked_close = True
                            util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                    elif selected_army is not None and left_panel_rect.collidepoint(mouse_x, mouse_y):
                        close_btn_rect = pygame.Rect(30, 800, 340, 45)
                        if close_btn_rect.collidepoint(mouse_x, mouse_y):
                            selected_army = None
                            clicked_close = True
                            util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                    elif current_player_idx == 0 and left_panel_rect.collidepoint(mouse_x, mouse_y):
                        # Done button click handling on the Faction Turn Phase panel
                        done_btn_rect = pygame.Rect(30, 470, 340, 50)
                        if done_btn_rect.collidepoint(mouse_x, mouse_y):
                            advance_turn_phase()
                            clicked_close = True
                            util.play_sound(filename=None, volume=0.3, pitch_hz=440.0, duration_ms=100)
                                
                    if not clicked_close:
                        if map_viewport_rect.collidepoint(mouse_x, mouse_y):
                            clicked_champ = map_grid.get_champion_at_screen_pos(mouse_x, mouse_y, map_viewport_rect)
                            if clicked_champ is not None:
                                selected_champion = clicked_champ
                                selected_army = None
                                util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                            else:
                                clicked_army = map_grid.get_army_at_screen_pos(mouse_x, mouse_y, map_viewport_rect)
                                if clicked_army is not None:
                                    selected_army = clicked_army
                                    selected_champion = None
                                    util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                                else:
                                    # Check if stronghold was clicked
                                    from factions import Faction
                                    q, r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
                                    tile = map_grid.get_tile(q, r)
                                    if tile and getattr(tile, 'is_stronghold', False) and isinstance(tile.owner, Faction):
                                        active_faction_profile = tile.owner
                                        util.play_sound(filename=None, volume=0.4, pitch_hz=659.25, duration_ms=120)
                                    else:
                                        if selected_champion is not None:
                                            selected_champion = None
                                            util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                                        elif selected_army is not None:
                                            selected_army = None
                                            util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)

        # --- C. Rendering ---
        screen.fill(settings.COLOR_BACKGROUND)
        
        # 1. Render Hex Map inside viewport
        map_grid.draw(screen, map_viewport_rect)
        
        # 1.5 Check Mouseover Tooltip for Champions or Armies
        tooltip_to_draw = None
        if not show_ring_window and active_faction_profile is None and map_viewport_rect.collidepoint(mouse_x, mouse_y):
            hovered_unit = map_grid.get_champion_at_screen_pos(mouse_x, mouse_y, map_viewport_rect)
            if hovered_unit is None:
                hovered_unit = map_grid.get_army_at_screen_pos(mouse_x, mouse_y, map_viewport_rect)
                
            if hovered_unit is not None:
                hover_text = hovered_unit.name
                if hasattr(hovered_unit, 'alignment'):
                    opt = hovered_unit.alignment.lower()
                    if opt == "good":
                        glow_color = settings.COLOR_NEON_CYAN
                    elif opt == "evil":
                        glow_color = settings.COLOR_NEON_PINK
                    elif opt == "neutral":
                        glow_color = settings.COLOR_NEON_GREEN
                    elif opt == "lawful":
                        glow_color = (0, 100, 255)
                    elif opt == "chaotic":
                        glow_color = (255, 128, 0)
                else:
                    glow_color = settings.COLOR_NEON_CYAN
                
                tooltip_to_draw = (hover_text, glow_color)

        # 2. Render Left Statistics Panel for selected Champion
        if selected_champion is not None:
            draw_left_champion_statistics_panel(screen, selected_champion, left_panel_rect, map_grid, mouse_x, mouse_y)
            
        # 2.1 Render Left Statistics Panel for selected Army
        elif selected_army is not None:
            draw_left_army_statistics_panel(screen, selected_army, left_panel_rect, map_grid, mouse_x, mouse_y)

        # 2.2 Render Left Faction Turn Phase Panel for active turn
        elif current_player_idx == 0:
            draw_left_phase_panel(screen, left_panel_rect, current_faction, current_turn_phase, mouse_x, mouse_y)

        # 3. Render HUD status card (Phase 2 version)
        draw_hud_status_card(screen, human_player_obj, mouse_x, mouse_y)

        # Draw "Ring" button in the upper left corner of the game screen
        is_hover_ring = ring_btn_rect.collidepoint(mouse_x, mouse_y)
        ring_btn_fill = (40, 45, 55) if is_hover_ring else (25, 29, 38)
        ring_btn_border = settings.COLOR_NEON_CYAN if is_hover_ring else settings.COLOR_TEXT_MUTED
        
        pygame.draw.rect(screen, ring_btn_fill, ring_btn_rect, border_radius=8)
        pygame.draw.rect(screen, ring_btn_border, ring_btn_rect, width=2, border_radius=8)
        
        font_ring_btn = pygame.font.SysFont("Courier", 16, bold=True)
        txt_ring = font_ring_btn.render("RING", True, settings.COLOR_TEXT_PRIMARY if is_hover_ring else settings.COLOR_TEXT_MUTED)
        txt_ring_rect = txt_ring.get_rect(center=ring_btn_rect.center)
        screen.blit(txt_ring, txt_ring_rect)

        # 4. Draw Mouseover Tooltip on top of all UI overlays
        draw_mouseover_tooltip(screen, tooltip_to_draw, mouse_x, mouse_y)

        # 5. Draw Ring Window overlay if active
        if show_ring_window and ten_factions_img is not None:
            # Dark translucent layer covering the screen
            overlay = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((11, 14, 20, 200))
            screen.blit(overlay, (0, 0))
            
            # Centered window for the image
            img_w, img_h = ten_factions_img.get_size()
            win_w = img_w + 20
            win_h = img_h + 20
            win_x = (settings.SCREEN_WIDTH - win_w) // 2
            win_y = (settings.SCREEN_HEIGHT - win_h) // 2
            
            pygame.draw.rect(screen, (20, 24, 33), (win_x, win_y, win_w, win_h), border_radius=12)
            pygame.draw.rect(screen, settings.COLOR_NEON_CYAN, (win_x, win_y, win_w, win_h), width=3, border_radius=12)
            
            screen.blit(ten_factions_img, (win_x + 10, win_y + 10))
            
            font_tip = pygame.font.SysFont("Courier", 14, bold=True)
            tip_surf = font_tip.render("Click anywhere or press any key to close", True, settings.COLOR_TEXT_MUTED)
            tip_rect = tip_surf.get_rect(center=(settings.SCREEN_WIDTH // 2, win_y + win_h + 25))
            screen.blit(tip_surf, tip_rect)

        # 6. Draw Faction Profile Window overlay if active
        if active_faction_profile is not None:
            # Dark translucent layer covering the screen
            overlay = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((11, 14, 20, 220))
            screen.blit(overlay, (0, 0))
            
            # Centered window for the profile
            win_w, win_h = 600, 500
            win_x = (settings.SCREEN_WIDTH - win_w) // 2
            win_y = (settings.SCREEN_HEIGHT - win_h) // 2
            
            # Draw window background/border
            pygame.draw.rect(screen, (20, 24, 33), (win_x, win_y, win_w, win_h), border_radius=15)
            pygame.draw.rect(screen, settings.COLOR_NEON_CYAN, (win_x, win_y, win_w, win_h), width=3, border_radius=15)
            
            # Title
            font_title = pygame.font.SysFont("Courier", 22, bold=True)
            txt_title = font_title.render("FACTION PROFILE", True, settings.COLOR_TEXT_MUTED)
            txt_title_rect = txt_title.get_rect(center=(settings.SCREEN_WIDTH // 2, win_y + 40))
            screen.blit(txt_title, txt_title_rect)
            
            # Race Header
            font_race = pygame.font.SysFont("Courier", 32, bold=True)
            txt_race = font_race.render(active_faction_profile.race.upper(), True, settings.COLOR_NEON_CYAN)
            txt_race_rect = txt_race.get_rect(center=(settings.SCREEN_WIDTH // 2, win_y + 80))
            screen.blit(txt_race, txt_race_rect)
            
            # Divider line
            pygame.draw.line(screen, settings.COLOR_TEXT_MUTED, (win_x + 40, win_y + 115), (win_x + win_w - 40, win_y + 115), 1)
            
            # Champion avatar on the left
            avatar_w, avatar_h = 160, 160
            avatar_x = win_x + 40
            avatar_y = win_y + 140
            
            try:
                champ_avatar = util.load_champion_image(
                    active_faction_profile.race.lower(), 
                    size=(avatar_w, avatar_h), 
                    mask_type="circle"
                )
                pygame.draw.circle(screen, (11, 14, 20), (avatar_x + avatar_w // 2, avatar_y + avatar_h // 2), avatar_w // 2 + 4)
                pygame.draw.circle(screen, settings.COLOR_NEON_CYAN, (avatar_x + avatar_w // 2, avatar_y + avatar_h // 2), avatar_w // 2 + 4, width=2)
                screen.blit(champ_avatar, (avatar_x, avatar_y))
            except Exception as avatar_err:
                print(f"Error loading faction avatar: {avatar_err}")
                pygame.draw.rect(screen, (11, 14, 20), (avatar_x, avatar_y, avatar_w, avatar_h), border_radius=10)
                pygame.draw.rect(screen, settings.COLOR_NEON_CYAN, (avatar_x, avatar_y, avatar_w, avatar_h), width=2, border_radius=10)
                
            # Details on the right
            info_x = win_x + 230
            info_y = win_y + 140
            
            font_label = pygame.font.SysFont("Courier", 14, bold=True)
            font_val = pygame.font.SysFont("Courier", 18)
            
            # 1. Home Terrain
            lbl_terrain = font_label.render("HOME TERRAIN", True, settings.COLOR_TEXT_MUTED)
            val_terrain = font_val.render(active_faction_profile.home_terrain.upper(), True, settings.COLOR_TEXT_PRIMARY)
            screen.blit(lbl_terrain, (info_x, info_y))
            screen.blit(val_terrain, (info_x, info_y + 20))
            
            # 2. Ring Position
            lbl_ring = font_label.render("DIPLOMATIC POSITION", True, settings.COLOR_TEXT_MUTED)
            val_ring = font_val.render(f"Ring Position {active_faction_profile.ring_number}", True, settings.COLOR_TEXT_PRIMARY)
            screen.blit(lbl_ring, (info_x, info_y + 55))
            screen.blit(val_ring, (info_x, info_y + 75))
            
            # 3. Gold / Treasury
            lbl_gold = font_label.render("TREASURY", True, settings.COLOR_TEXT_MUTED)
            val_gold = font_val.render(f"{active_faction_profile.gold} Gold", True, settings.COLOR_NEON_GREEN)
            screen.blit(lbl_gold, (info_x, info_y + 110))
            screen.blit(val_gold, (info_x, info_y + 130))
            
            # 4. Diplomatic Alignment relative to player's secret faction
            lbl_align = font_label.render("DIPLOMATIC ALIGNMENT", True, settings.COLOR_TEXT_MUTED)
            player_faction = human_player_obj.faction
            dist = active_faction_profile.diplomatic_distance(player_faction)
            
            if dist == 0:
                align_str = "YOUR SECRET FACTION"
                align_color = settings.COLOR_NEON_GREEN
            elif dist == 1:
                align_str = "STRONGLY ALIGNED (Dist 1)"
                align_color = settings.COLOR_NEON_CYAN
            elif dist in (2, 3):
                align_str = f"LOOSELY ALIGNED (Dist {dist})"
                align_color = settings.COLOR_TEXT_PRIMARY
            else: # 4 or 5
                align_str = f"OPPOSED FACTION (Dist {dist})"
                align_color = settings.COLOR_NEON_PINK
                
            val_align = font_val.render(align_str, True, align_color)
            screen.blit(lbl_align, (info_x, info_y + 165))
            screen.blit(val_align, (info_x, info_y + 185))
            
            # Close Tip
            font_tip = pygame.font.SysFont("Courier", 14, bold=True)
            tip_surf = font_tip.render("Click anywhere or press any key to close", True, settings.COLOR_TEXT_MUTED)
            tip_rect = tip_surf.get_rect(center=(settings.SCREEN_WIDTH // 2, win_y + win_h - 30))
            screen.blit(tip_surf, tip_rect)

        pygame.display.flip()

    # Safe Engine Exit
    print("Safely shutting down Alignments engine...")
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
