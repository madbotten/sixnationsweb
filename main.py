"""
Alignments - Game Entry Point
Implements the multi-phase game engine: Phase 1 (Map Building via drag-and-drop tile snapping
with an automated bot player) and Phase 2 (Full-screen scrollable map visualization with Power profiles).
"""

import sys
import pygame
import random
# Import configurations, map model, bot system, and helper utilities
import settings
import util
from map import MapGrid
from bot import BotPlayer
from player import Player



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
    game_phase = settings.PHASE_MAP_BUILDING
    
    # 4. Draft Deck of 16 Tiles per player according to partitioning rules
    # Unique tiles must be distributed across players
    # Remaining hand slots are padded with randomly drawn common tiles
    unique_pool = list(settings.UNIQUE_TILES)
    random.shuffle(unique_pool)
    
    # Distribute unique tiles as evenly as possible between player and bot
    half_size = len(unique_pool) // 2
    player_uniques = unique_pool[:half_size]
    bot_uniques = unique_pool[half_size:]
    
    # Pad hands to exactly 16 tiles using common tiles
    player_hand = list(player_uniques)
    while len(player_hand) < settings.TOTAL_TILES_PER_PLAYER:
        player_hand.append(random.choice(settings.COMMON_TILES))
        
    bot_hand = list(bot_uniques)
    while len(bot_hand) < settings.TOTAL_TILES_PER_PLAYER:
        bot_hand.append(random.choice(settings.COMMON_TILES))
        
    # Shuffle final decks so unique cards are nicely interspersed
    random.shuffle(player_hand)
    random.shuffle(bot_hand)
    
    # Initialize Player alignment objects
    human_player_obj = Player()
    bot_player_obj = Player()
    print(f"Human Player Alignment: {human_player_obj.get_alignment_parts()}")
    print(f"Bot Player Alignment: {bot_player_obj.get_alignment_parts()}")

    # Initialize the automated Bot Player
    bot_player = BotPlayer(hand=bot_hand)
    
    # Turn state tracking ('player' or 'bot')
    active_turn = 'player'
    bot_turn_timer = 0  # Timestamp to handle natural bot placement pacing
    
    # Drag-and-drop variables
    dragged_tile_idx = None
    dragged_tile_terrain = None
    
    # 5. Play startup chime (rising synthesizer sound)
    util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100) # C5
    pygame.time.delay(120)
    util.play_sound(filename=None, volume=0.5, pitch_hz=659.25, duration_ms=200) # E5
    
    print("Welcome to Alignments!")
    print(f"Player uniques: {player_uniques}")
    print(f"Bot uniques: {bot_uniques}")
    print(f"Player hand: {player_hand}")
    print(f"Bot hand: {bot_hand}")

    # 6. Master Loops
    running = True

    # --- TEMPORARY BOT SETUP FOR QUICK MAIN LOOP DEVELOPMENT ---
    # Run the automated quick setup function to build map instantly
    from bot import bot_map_quick_setup
    bot_map_quick_setup(map_grid, player_hand, bot_player)
    game_phase = settings.PHASE_MAIN_GAME

    # --- PHASE 1: MAP BUILDING SETUP LOOP (TEMPORARILY BYPASSED) ---
    while False and running and game_phase == settings.PHASE_MAP_BUILDING:
        # Determine Frame Delta Time (seconds)
        dt = clock.tick(settings.FPS) / 1000.0
        
        # --- A. Keyboard Camera Scrolling (WASD / Arrows) ---
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

        # Define viewport layout rects
        left_panel_rect = pygame.Rect(0, 0, settings.PANEL_WIDTH, settings.SCREEN_HEIGHT)
        map_viewport_rect = pygame.Rect(settings.PANEL_WIDTH, 0, settings.SCREEN_WIDTH - settings.PANEL_WIDTH, settings.SCREEN_HEIGHT)

        # --- B. Event Processing ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    if active_turn == 'player':
                        # Check click inside left hand panel
                        if left_panel_rect.collidepoint(mouse_x, mouse_y):
                            start_y = 120
                            card_w, card_h = 160, 95
                            spacing_x, spacing_y = 180, 105
                            
                            for i, terrain in enumerate(player_hand):
                                row = i // 2
                                col = i % 2
                                cx = 110 + col * spacing_x
                                cy = start_y + row * spacing_y
                                
                                card_rect = pygame.Rect(cx - card_w//2, cy - card_h//2, card_w, card_h)
                                if card_rect.collidepoint(mouse_x, mouse_y):
                                    dragged_tile_idx = i
                                    dragged_tile_terrain = terrain
                                    util.play_sound(filename=None, volume=0.3, pitch_hz=440.0, duration_ms=50)
                                    break
                                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and dragged_tile_idx is not None:
                    placed_successfully = False
                    
                    if map_viewport_rect.collidepoint(mouse_x, mouse_y):
                        q, r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
                        
                        if map_grid.is_valid_placement(q, r, dragged_tile_terrain):
                            map_grid.place_tile(q, r, dragged_tile_terrain, owner='player')
                            util.play_sound(filename=None, volume=0.5, pitch_hz=587.33, duration_ms=180)
                            player_hand.pop(dragged_tile_idx)
                            
                            dragged_tile_idx = None
                            dragged_tile_terrain = None
                            placed_successfully = True
                            
                            if not player_hand and not bot_player.hand:
                                game_phase = settings.PHASE_MAIN_GAME
                                util.play_sound(filename=None, volume=0.6, pitch_hz=880.0, duration_ms=400)
                            else:
                                active_turn = 'bot'
                                bot_turn_timer = pygame.time.get_ticks()
                                
                    if not placed_successfully:
                        util.play_sound(filename=None, volume=0.4, pitch_hz=180.0, duration_ms=220)
                        dragged_tile_idx = None
                        dragged_tile_terrain = None

        # --- C. Bot Placement Actions ---
        if active_turn == 'bot':
            current_time = pygame.time.get_ticks()
            if current_time - bot_turn_timer >= 800:
                bot_action = bot_player.choose_placement(map_grid)
                if bot_action:
                    bq, br, b_terrain = bot_action
                    map_grid.place_tile(bq, br, b_terrain, owner='bot')
                    util.play_sound(filename=None, volume=0.4, pitch_hz=392.0, duration_ms=220)
                    
                if not player_hand and not bot_player.hand:
                    game_phase = settings.PHASE_MAIN_GAME
                    util.play_sound(filename=None, volume=0.6, pitch_hz=880.0, duration_ms=400)
                else:
                    active_turn = 'player'

        # --- D. Rendering ---
        screen.fill(settings.COLOR_BACKGROUND)
        
        ghost_info = None
        if dragged_tile_idx is not None and map_viewport_rect.collidepoint(mouse_x, mouse_y):
            g_q, g_r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
            g_valid = map_grid.is_valid_placement(g_q, g_r, dragged_tile_terrain)
            ghost_info = {'q': g_q, 'r': g_r, 'terrain': dragged_tile_terrain, 'valid': g_valid}

        map_grid.draw(screen, map_viewport_rect, ghost_info=ghost_info, dragged_terrain=dragged_tile_terrain)
        
        # Render Left Drafting Panel
        pygame.draw.rect(screen, settings.COLOR_HUD_BG, left_panel_rect)
        pygame.draw.rect(screen, settings.COLOR_NEON_CYAN, left_panel_rect, width=1)
        
        try:
            font_hud = pygame.font.SysFont("Courier", 20, bold=True)
            title_surf = font_hud.render("MAP TILES", True, settings.COLOR_NEON_CYAN)
            screen.blit(title_surf, (30, 45))
            
            start_y = 120
            card_w, card_h = 160, 95
            spacing_x, spacing_y = 180, 105
            
            for i, terrain in enumerate(player_hand):
                if i == dragged_tile_idx:
                    continue
                    
                row = i // 2
                col = i % 2
                cx = 110 + col * spacing_x
                cy = start_y + row * spacing_y
                
                card_rect = pygame.Rect(cx - card_w//2, cy - card_h//2, card_w, card_h)
                is_hovered = card_rect.collidepoint(mouse_x, mouse_y) and active_turn == 'player'
                
                border_color = settings.COLOR_NEON_CYAN if is_hovered else settings.COLOR_TEXT_MUTED
                pygame.draw.rect(screen, settings.COLOR_BACKGROUND, card_rect, border_radius=10)
                pygame.draw.rect(screen, border_color, card_rect, width=2, border_radius=10)
                
                tile_surf = util.load_terrain_image(
                    terrain, 
                    alpha=True, 
                    color_fallback=settings.COLOR_NEON_CYAN if terrain in settings.COMMON_TILES else settings.COLOR_NEON_PINK,
                    size=(140, 76)
                )
                screen.blit(tile_surf, (cx - 70, cy - 38))
        except Exception as e:
            print(f"[Render Error] Failed to draw hand panel: {e}")
            
        if dragged_tile_idx is not None:
            tile_surf = util.load_terrain_image(
                dragged_tile_terrain, 
                alpha=True, 
                color_fallback=settings.COLOR_NEON_CYAN if dragged_tile_terrain in settings.COMMON_TILES else settings.COLOR_NEON_PINK,
                size=(settings.HEX_WIDTH, settings.HEX_HEIGHT)
            )
            screen.blit(tile_surf, (mouse_x - settings.HEX_WIDTH // 2, mouse_y - settings.HEX_HEIGHT // 2))
            
        # Render HUD Status Cards
        try:
            font_title = pygame.font.SysFont("Courier", 18, bold=True)
            font_body = pygame.font.SysFont("Courier", 12)
            
            hud_card = pygame.Surface((450, 80), pygame.SRCALPHA)
            pygame.draw.rect(hud_card, settings.COLOR_HUD_BG, (0, 0, 450, 80), border_radius=10)
            pygame.draw.rect(hud_card, settings.COLOR_NEON_CYAN, (0, 0, 450, 80), width=1, border_radius=10)
            
            if active_turn == 'player':
                status_text = "PLAYER TURN: BUILD THE MAP"
                color_status = settings.COLOR_NEON_CYAN
                tip_text = "Drag tiles from hand & drop adjoining existing tiles."
            else:
                status_text = "BOT TURN: EXPANDING MAP..."
                color_status = settings.COLOR_NEON_PURPLE
                tip_text = "Wait for the bot player to place a tile."
                
            txt_status = font_title.render(status_text, True, color_status)
            txt_tip = font_body.render(tip_text, True, settings.COLOR_TEXT_PRIMARY)
            txt_scroll = font_body.render("WASD or Arrows: Camera Scroll  |  ESC: Exit", True, settings.COLOR_TEXT_MUTED)
            
            hud_card.blit(txt_status, (20, 12))
            hud_card.blit(txt_tip, (20, 36))
            hud_card.blit(txt_scroll, (20, 54))
            screen.blit(hud_card, (settings.SCREEN_WIDTH - 480, 20))
            
            deck_card = pygame.Surface((300, 50), pygame.SRCALPHA)
            pygame.draw.rect(deck_card, settings.COLOR_HUD_BG, (0, 0, 300, 50), border_radius=10)
            pygame.draw.rect(deck_card, settings.COLOR_TEXT_MUTED, (0, 0, 300, 50), width=1, border_radius=10)
            
            p_cnt = font_body.render(f"PLAYER HAND: {len(player_hand)} left", True, settings.COLOR_NEON_CYAN)
            b_cnt = font_body.render(f"BOT HAND:    {len(bot_player.hand)} left", True, settings.COLOR_NEON_PURPLE)
            deck_card.blit(p_cnt, (15, 10))
            deck_card.blit(b_cnt, (15, 28))
            screen.blit(deck_card, (settings.SCREEN_WIDTH - 330, 110))
        except Exception as e:
            print(f"[Render Warning] Failed to draw HUD Overlay: {e}")

        pygame.display.flip()


    # --- PHASE 2: MAIN GAMEPLAY LOOP (MAP VIEWING & POWERS DETAIL PANEL) ---
    selected_power = None
    moving_power = None
    active_game_turn = 'player'  # 'player' or 'bot'
    bot_game_turn_timer = 0
    
    while running and game_phase == settings.PHASE_MAIN_GAME:
        dt = clock.tick(settings.FPS) / 1000.0
        
        # --- A. Keyboard Camera Scrolling (WASD / Arrows) ---
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

        # Define layout viewport boundaries dynamically based on selection
        if selected_power is not None:
            left_panel_rect = pygame.Rect(0, 0, settings.PANEL_WIDTH, settings.SCREEN_HEIGHT)
            map_viewport_rect = pygame.Rect(settings.PANEL_WIDTH, 0, settings.SCREEN_WIDTH - settings.PANEL_WIDTH, settings.SCREEN_HEIGHT)
        else:
            left_panel_rect = pygame.Rect(0, 0, 0, 0)
            map_viewport_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)

        # --- B. Event Processing ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if moving_power is not None:
                        moving_power = None
                        util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                    elif selected_power is not None:
                        selected_power = None
                        util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                    else:
                        running = False
                        
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    if active_game_turn == 'player':
                        if moving_power is not None:
                            # Convert click to axial coordinate on map
                            dq, dr = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
                            # Get valid adjacent destinations on the map
                            valid_dests = map_grid.get_valid_movement_destinations(moving_power)
                            if (dq, dr) in valid_dests:
                                # Move the power
                                old_loc = moving_power.hex_location
                                if old_loc in map_grid.powers:
                                    if moving_power in map_grid.powers[old_loc]:
                                        map_grid.powers[old_loc].remove(moving_power)
                                        if not map_grid.powers[old_loc]:
                                            del map_grid.powers[old_loc]
                                moving_power.hex_location = (dq, dr)
                                map_grid.add_power(moving_power)
                                util.play_sound(filename=None, volume=0.5, pitch_hz=587.33, duration_ms=180)
                                
                                # End player turn and pass to bot
                                active_game_turn = 'bot'
                                bot_game_turn_timer = pygame.time.get_ticks()
                                moving_power = None
                            else:
                                # Cancel movement if click is invalid (non-adjacent or off-map)
                                util.play_sound(filename=None, volume=0.4, pitch_hz=180.0, duration_ms=220)
                                moving_power = None
                        else:
                            clicked_close = False
                            clicked_move = False
                            clicked_unique = False
                            
                            # Check panel buttons if selection is active
                            if selected_power is not None and left_panel_rect.collidepoint(mouse_x, mouse_y):
                                close_btn_rect = pygame.Rect(30, 800, 340, 45)
                                if close_btn_rect.collidepoint(mouse_x, mouse_y):
                                    selected_power = None
                                    clicked_close = True
                                    util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                                    
                                if not clicked_close:
                                    move_btn_rect = pygame.Rect(30, 730, 340, 45)
                                    if move_btn_rect.collidepoint(mouse_x, mouse_y):
                                        moving_power = selected_power
                                        selected_power = None # Closes the profile display
                                        clicked_move = True
                                        util.play_sound(filename=None, volume=0.4, pitch_hz=659.25, duration_ms=100)
                                        
                                if not clicked_close and not clicked_move:
                                    unique_btn_rect = pygame.Rect(30, 660, 340, 45)
                                    if unique_btn_rect.collidepoint(mouse_x, mouse_y):
                                        clicked_unique = True
                                        # Play a nice high-pitched chime for activating unique ability
                                        util.play_sound(filename=None, volume=0.5, pitch_hz=880.0, duration_ms=150)
                                        print(f"Unique Ability clicked: {selected_power.unique_ability}")
                                        
                            if not clicked_close and not clicked_move and not clicked_unique:
                                if map_viewport_rect.collidepoint(mouse_x, mouse_y):
                                    clicked_power = map_grid.get_power_at_screen_pos(mouse_x, mouse_y, map_viewport_rect)
                                    if clicked_power is not None:
                                        selected_power = clicked_power
                                        util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                                    else:
                                        if selected_power is not None:
                                            selected_power = None
                                            util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)

        # --- B.5 Bot Turn Processing ---
        if active_game_turn == 'bot':
            current_time = pygame.time.get_ticks()
            if current_time - bot_game_turn_timer >= 1000:
                action = bot_player.choose_power_movement(map_grid)
                if action:
                    p_unit, b_q, b_r = action
                    old_loc = p_unit.hex_location
                    if old_loc in map_grid.powers:
                        if p_unit in map_grid.powers[old_loc]:
                            map_grid.powers[old_loc].remove(p_unit)
                            if not map_grid.powers[old_loc]:
                                del map_grid.powers[old_loc]
                    p_unit.hex_location = (b_q, b_r)
                    map_grid.add_power(p_unit)
                    
                    # Play bot movement chime
                    util.play_sound(filename=None, volume=0.5, pitch_hz=493.88, duration_ms=180) # B4
                
                # Turn goes back to player
                active_game_turn = 'player'

        # --- C. Rendering ---
        screen.fill(settings.COLOR_BACKGROUND)
        
        # 1. Render Hex Map inside viewport (passing valid moves highlight if player is moving a unit)
        highlight_coords = None
        if moving_power is not None:
            highlight_coords = map_grid.get_valid_movement_destinations(moving_power)
        map_grid.draw(screen, map_viewport_rect, highlight_coords=highlight_coords)
        
        # 2. Render Left Statistics Panel (Only if Power is selected)
        if selected_power is not None:
            # Draw panel background glass overlay
            pygame.draw.rect(screen, settings.COLOR_HUD_BG, left_panel_rect)
            
            # Determine glow color matching alignment
            glow_color = (189, 0, 255) # default purple
            parts = selected_power.get_alignment_parts()
            if parts:
                moral = parts[1]
                if "good" in moral:
                    glow_color = settings.COLOR_NEON_CYAN
                elif "evil" in moral:
                    glow_color = settings.COLOR_NEON_PINK
                elif "neutral" in moral:
                    glow_color = settings.COLOR_NEON_GREEN
                    
            pygame.draw.rect(screen, glow_color, left_panel_rect, width=1) # Neon border
            
            try:
                # Fonts
                font_hud = pygame.font.SysFont("Courier", 22, bold=True)
                font_label = pygame.font.SysFont("Courier", 14, bold=True)
                font_value = pygame.font.SysFont("Courier", 16)
                font_title_bold = pygame.font.SysFont("Courier", 26, bold=True)
                
                # Power Image Card Container
                img_rect = pygame.Rect(110, 50, 180, 180)
                pygame.draw.rect(screen, settings.COLOR_BACKGROUND, img_rect, border_radius=15)
                pygame.draw.rect(screen, glow_color, img_rect, width=3, border_radius=15)
                
                # Power square surface scaling
                power_surf = selected_power.get_surface(size=(174, 174), mask_type="square")
                screen.blit(power_surf, (113, 53))
                
                # Power Name
                name_text = selected_power.name.upper()
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
                
                tile = map_grid.get_tile(selected_power.q, selected_power.r)
                formatted_loc = util.format_location_name(tile.terrain_type) if tile else "Empty Space"
                val_loc = font_value.render(formatted_loc, True, settings.COLOR_TEXT_PRIMARY)
                screen.blit(val_loc, (45, start_y + 30))
                
                # Strength Row
                str_rect = pygame.Rect(30, start_y + row_h, 340, 60)
                pygame.draw.rect(screen, (20, 24, 33), str_rect, border_radius=8)
                pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, str_rect, width=1, border_radius=8)
                
                lbl_str = font_label.render("STRENGTH", True, settings.COLOR_NEON_CYAN)
                screen.blit(lbl_str, (45, start_y + row_h + 10))
                
                val_str = font_value.render(str(selected_power.strength), True, settings.COLOR_TEXT_PRIMARY)
                screen.blit(val_str, (45, start_y + row_h + 30))
                
                # Futuristic horizontal progress bar for strength
                max_str = 15
                bar_w = 200
                bar_h = 10
                bx = 150
                by = start_y + row_h + 33
                pygame.draw.rect(screen, (40, 45, 55), (bx, by, bar_w, bar_h), border_radius=5)
                
                fill_w = int(bar_w * min(1.0, selected_power.strength / max_str))
                pygame.draw.rect(screen, settings.COLOR_NEON_GREEN, (bx, by, fill_w, bar_h), border_radius=5)
                
                # Alignment Row
                align_rect = pygame.Rect(30, start_y + 2 * row_h, 340, 60)
                pygame.draw.rect(screen, (20, 24, 33), align_rect, border_radius=8)
                pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, align_rect, width=1, border_radius=8)
                
                lbl_align = font_label.render("ALIGNMENT", True, settings.COLOR_NEON_CYAN)
                screen.blit(lbl_align, (45, start_y + 2 * row_h + 10))
                
                align_parts = selected_power.get_alignment_parts()
                align_str = " ".join([p.capitalize() for p in align_parts]) if align_parts else "Unaligned"
                val_align = font_value.render(align_str, True, glow_color)
                screen.blit(val_align, (45, start_y + 2 * row_h + 30))

                
                # Unique Ability Button (above Move Button)
                unique_ability_name = selected_power.unique_ability.upper()
                unique_btn_rect = pygame.Rect(30, 660, 340, 45)
                is_hover_unique = unique_btn_rect.collidepoint(mouse_x, mouse_y)
                unique_fill = (40, 45, 55) if is_hover_unique else (25, 29, 38)
                # Unique ability border glows with the unit's alignment color on hover
                unique_border = glow_color if is_hover_unique else settings.COLOR_TEXT_MUTED
                
                pygame.draw.rect(screen, unique_fill, unique_btn_rect, border_radius=10)
                pygame.draw.rect(screen, unique_border, unique_btn_rect, width=2, border_radius=10)
                
                lbl_unique = font_hud.render(unique_ability_name, True, settings.COLOR_TEXT_PRIMARY if is_hover_unique else settings.COLOR_TEXT_MUTED)
                lbl_unique_rect = lbl_unique.get_rect(center=unique_btn_rect.center)
                screen.blit(lbl_unique, lbl_unique_rect)

                # Move Button (above Close Button)
                move_btn_rect = pygame.Rect(30, 730, 340, 45)
                is_hover_move = move_btn_rect.collidepoint(mouse_x, mouse_y)
                move_fill = (40, 45, 55) if is_hover_move else (25, 29, 38)
                move_border = settings.COLOR_NEON_CYAN if is_hover_move else settings.COLOR_TEXT_MUTED
                
                pygame.draw.rect(screen, move_fill, move_btn_rect, border_radius=10)
                pygame.draw.rect(screen, move_border, move_btn_rect, width=2, border_radius=10)
                
                lbl_move = font_hud.render("MOVE", True, settings.COLOR_TEXT_PRIMARY if is_hover_move else settings.COLOR_TEXT_MUTED)
                lbl_move_rect = lbl_move.get_rect(center=move_btn_rect.center)
                screen.blit(lbl_move, lbl_move_rect)
                
                # Close Button at bottom
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
                print(f"[Render Error] Failed to draw power stats: {e}")

        # 3. Render HUD status card (Phase 2 version)
        try:
            font_title = pygame.font.SysFont("Courier", 18, bold=True)
            font_body = pygame.font.SysFont("Courier", 12)
            
            hud_card = pygame.Surface((450, 80), pygame.SRCALPHA)
            pygame.draw.rect(hud_card, settings.COLOR_HUD_BG, (0, 0, 450, 80), border_radius=10)
            
            if active_game_turn == 'bot':
                pygame.draw.rect(hud_card, settings.COLOR_NEON_PURPLE, (0, 0, 450, 80), width=2, border_radius=10)
                status_text = "BOT TURN: SELECTING MOVEMENT"
                color_status = settings.COLOR_NEON_PURPLE
                tip_text = "The bot is deciding which Power unit to move."
                txt_scroll = font_body.render("Please wait for the bot's action.", True, settings.COLOR_TEXT_MUTED)
            else:
                if moving_power is not None:
                    pygame.draw.rect(hud_card, settings.COLOR_NEON_PINK, (0, 0, 450, 80), width=2, border_radius=10)
                    status_text = "PLAYER TURN: MOVE POWER"
                    color_status = settings.COLOR_NEON_PINK
                    tip_text = f"Click highlighted adjacent hex to move {moving_power.name}."
                    txt_scroll = font_body.render("Click Map: Move Power  |  ESC: Cancel", True, settings.COLOR_TEXT_MUTED)
                else:
                    pygame.draw.rect(hud_card, settings.COLOR_NEON_GREEN, (0, 0, 450, 80), width=2, border_radius=10)
                    status_text = "PLAYER TURN: CHOOSE ACTION"
                    color_status = settings.COLOR_NEON_GREEN
                    tip_text = "Click a Power to view profile. WASD to scroll."
                    if selected_power is not None:
                        tip_text = f"Selected: {selected_power.name}. Use an ability button."
                    txt_scroll = font_body.render("WASD or Arrows: Camera Scroll  |  ESC: Deselect", True, settings.COLOR_TEXT_MUTED)
                
            txt_status = font_title.render(status_text, True, color_status)
            txt_tip = font_body.render(tip_text, True, settings.COLOR_TEXT_PRIMARY)
            
            hud_card.blit(txt_status, (20, 12))
            hud_card.blit(txt_tip, (20, 36))
            hud_card.blit(txt_scroll, (20, 54))
            screen.blit(hud_card, (settings.SCREEN_WIDTH - 480, 20))
        except Exception as e:
            print(f"[Render Warning] Failed to draw gameplay HUD: {e}")

        pygame.display.flip()

    # Safe Engine Exit
    print("Safely shutting down Alignments engine...")
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
