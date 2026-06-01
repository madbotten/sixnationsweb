"""
Alignments - Game Entry Point
Implements the multi-phase game engine: Phase 1 (Map Building via drag-and-drop tile snapping
with an automated bot player) and Phase 2 (Full-screen scrollable map visualization).
"""

import sys
import pygame
import random

# Import configurations, map model, bot system, and helper utilities
import settings
import util
from map import MapGrid
from bot import BotPlayer

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
    
    # 4. Draft Deck of 12 Tiles per player according to partitioning rules
    # 11 Unique tiles must be distributed across players (e.g. 6 to player, 5 to bot)
    # Remaining hand slots are padded with randomly drawn common tiles
    unique_pool = list(settings.UNIQUE_TILES)
    random.shuffle(unique_pool)
    
    player_uniques = unique_pool[:6]
    bot_uniques = unique_pool[6:]
    
    # Pad hands to exactly 12 tiles using common tiles
    player_hand = list(player_uniques)
    while len(player_hand) < settings.TOTAL_TILES_PER_PLAYER:
        player_hand.append(random.choice(settings.COMMON_TILES))
        
    bot_hand = list(bot_uniques)
    while len(bot_hand) < settings.TOTAL_TILES_PER_PLAYER:
        bot_hand.append(random.choice(settings.COMMON_TILES))
        
    # Shuffle final decks so unique cards are nicely interspersed
    random.shuffle(player_hand)
    random.shuffle(bot_hand)
    
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

    # 6. Master Loop
    running = True
    while running:
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

        # Define viewport layout rects based on current phase
        if game_phase == settings.PHASE_MAP_BUILDING:
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
                    running = False
                    
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    # Player can only click to drag during their own turn in map building phase
                    if game_phase == settings.PHASE_MAP_BUILDING and active_turn == 'player':
                        # Check click inside left hand panel (x < 400)
                        if left_panel_rect.collidepoint(mouse_x, mouse_y):
                            # Determine which card was clicked in the vertical hand grid
                            # Hand is rendered in a 2-column grid starting at y=120
                            start_y = 120
                            card_w, card_h = 160, 95
                            spacing_x, spacing_y = 180, 105
                            
                            for i, terrain in enumerate(player_hand):
                                row = i // 2
                                col = i % 2
                                cx = 110 + col * spacing_x
                                cy = start_y + row * spacing_y
                                
                                # Click hit-test box around card center
                                card_rect = pygame.Rect(cx - card_w//2, cy - card_h//2, card_w, card_h)
                                if card_rect.collidepoint(mouse_x, mouse_y):
                                    # Start dragging!
                                    dragged_tile_idx = i
                                    dragged_tile_terrain = terrain
                                    util.play_sound(filename=None, volume=0.3, pitch_hz=440.0, duration_ms=50) # Select click
                                    break
                                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and dragged_tile_idx is not None:
                    # Player released the dragged card
                    placed_successfully = False
                    
                    # Dropped in the map viewport?
                    if map_viewport_rect.collidepoint(mouse_x, mouse_y):
                        # Convert drop coordinate to axial grid slot
                        q, r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
                        
                        # Validate adjacency and placement restrictions
                        if map_grid.is_valid_placement(q, r, dragged_tile_terrain):
                            # Commit placement
                            map_grid.place_tile(q, r, dragged_tile_terrain, owner='player')
                            
                            # Play successful placement chime
                            util.play_sound(filename=None, volume=0.5, pitch_hz=587.33, duration_ms=180) # D5
                            
                            # Remove from player's hand
                            player_hand.pop(dragged_tile_idx)
                            
                            # Reset drag status and swap turns
                            dragged_tile_idx = None
                            dragged_tile_terrain = None
                            placed_successfully = True
                            
                            # Check if the map building phase has finished
                            if not player_hand and not bot_player.hand:
                                # Completed! Transition phases
                                game_phase = settings.PHASE_MAIN_GAME
                                util.play_sound(filename=None, volume=0.6, pitch_hz=880.0, duration_ms=400)
                            else:
                                active_turn = 'bot'
                                bot_turn_timer = pygame.time.get_ticks()
                                
                    if not placed_successfully:
                        # Dropped out of bounds or invalid: Return tile to hand with fail feedback buzz
                        util.play_sound(filename=None, volume=0.4, pitch_hz=180.0, duration_ms=220)
                        dragged_tile_idx = None
                        dragged_tile_terrain = None

        # --- C. Bot Placement Actions ---
        if game_phase == settings.PHASE_MAP_BUILDING and active_turn == 'bot':
            # Wait for short natural thinking delay (800ms)
            current_time = pygame.time.get_ticks()
            if current_time - bot_turn_timer >= 800:
                # Solve and execute bot placement instantly
                bot_action = bot_player.choose_placement(map_grid)
                if bot_action:
                    bq, br, b_terrain = bot_action
                    map_grid.place_tile(bq, br, b_terrain, owner='bot')
                    
                    # Play beautiful deep placement chime
                    util.play_sound(filename=None, volume=0.4, pitch_hz=392.0, duration_ms=220) # G4
                    
                # Swap turns
                if not player_hand and not bot_player.hand:
                    game_phase = settings.PHASE_MAIN_GAME
                    util.play_sound(filename=None, volume=0.6, pitch_hz=880.0, duration_ms=400)
                else:
                    active_turn = 'player'

        # --- D. Rendering ---
        # Draw base deep-space background
        screen.fill(settings.COLOR_BACKGROUND)
        
        # Calculate snap preview ghost coordinates under drag
        ghost_info = None
        if dragged_tile_idx is not None and map_viewport_rect.collidepoint(mouse_x, mouse_y):
            g_q, g_r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
            g_valid = map_grid.is_valid_placement(g_q, g_r, dragged_tile_terrain)
            ghost_info = {'q': g_q, 'r': g_r, 'terrain': dragged_tile_terrain, 'valid': g_valid}

        # 1. Render Hex Map inside its designated viewport (passing dragged terrain for constraint shading)
        map_grid.draw(screen, map_viewport_rect, ghost_info=ghost_info, dragged_terrain=dragged_tile_terrain)
        
        # 2. Render Left Drafting Panel (Only in Phase 1)
        if game_phase == settings.PHASE_MAP_BUILDING:
            # Draw panel background glass overlay
            pygame.draw.rect(screen, settings.COLOR_HUD_BG, left_panel_rect)
            pygame.draw.rect(screen, settings.COLOR_NEON_CYAN, left_panel_rect, width=1) # Neon border
            
            # Header Title Text
            try:
                font_hud = pygame.font.SysFont("Courier", 20, bold=True)
                font_small = pygame.font.SysFont("Courier", 12)
                
                title_surf = font_hud.render("MAP TILES", True, settings.COLOR_NEON_CYAN)
                screen.blit(title_surf, (30, 45))
                
                # Render 2-column hand grid
                start_y = 120
                card_w, card_h = 160, 95
                spacing_x, spacing_y = 180, 105
                
                for i, terrain in enumerate(player_hand):
                    # Skip rendering the tile currently grabbed by the mouse
                    if i == dragged_tile_idx:
                        continue
                        
                    row = i // 2
                    col = i % 2
                    cx = 110 + col * spacing_x
                    cy = start_y + row * spacing_y
                    
                    # Check mouse hover on tile
                    card_rect = pygame.Rect(cx - card_w//2, cy - card_h//2, card_w, card_h)
                    is_hovered = card_rect.collidepoint(mouse_x, mouse_y) and active_turn == 'player'
                    
                    # Outer glow borders
                    border_color = settings.COLOR_NEON_CYAN if is_hovered else settings.COLOR_TEXT_MUTED
                    pygame.draw.rect(screen, settings.COLOR_BACKGROUND, card_rect, border_radius=10)
                    pygame.draw.rect(screen, border_color, card_rect, width=2, border_radius=10)
                    
                    # Draw actual tile structure inside card
                    # Cache lookup loads image with glowing border based on terrain category
                    tile_surf = util.load_image(
                        terrain, 
                        alpha=True, 
                        color_fallback=settings.COLOR_NEON_CYAN if terrain in settings.COMMON_TILES else settings.COLOR_NEON_PINK,
                        size=(140, 76)
                    )
                    screen.blit(tile_surf, (cx - 70, cy - 38))
                    
                    # Display terrain name
                    text_name = font_small.render(terrain.upper(), True, settings.COLOR_TEXT_PRIMARY if is_hovered else settings.COLOR_TEXT_MUTED)
                    text_rect = text_name.get_rect(center=(cx, cy + 32))
                    screen.blit(text_name, text_rect)
            except Exception as e:
                print(f"[Render Error] Failed to draw hand panel: {e}")
                
        # 3. Render Floating dragged card (following mouse pointer)
        if dragged_tile_idx is not None:
            tile_surf = util.load_image(
                dragged_tile_terrain, 
                alpha=True, 
                color_fallback=settings.COLOR_NEON_CYAN if dragged_tile_terrain in settings.COMMON_TILES else settings.COLOR_NEON_PINK,
                size=(settings.HEX_WIDTH, settings.HEX_HEIGHT)
            )
            # Alpha blend blit centered on mouse
            screen.blit(tile_surf, (mouse_x - settings.HEX_WIDTH // 2, mouse_y - settings.HEX_HEIGHT // 2))
            
        # 4. Render HUD / Floating status panels
        try:
            font_title = pygame.font.SysFont("Courier", 18, bold=True)
            font_body = pygame.font.SysFont("Courier", 12)
            
            # HUD Floating Card
            hud_card = pygame.Surface((450, 80), pygame.SRCALPHA)
            pygame.draw.rect(hud_card, settings.COLOR_HUD_BG, (0, 0, 450, 80), border_radius=10)
            
            # Draw content depending on Phase
            if game_phase == settings.PHASE_MAP_BUILDING:
                pygame.draw.rect(hud_card, settings.COLOR_NEON_CYAN, (0, 0, 450, 80), width=1, border_radius=10)
                
                if active_turn == 'player':
                    status_text = "PLAYER TURN: BUILD THE MAP"
                    color_status = settings.COLOR_NEON_CYAN
                    tip_text = "Drag tiles from hand & drop adjoining existing tiles."
                else:
                    status_text = "BOT TURN: EXPANDING MAP..."
                    color_status = settings.COLOR_NEON_PURPLE
                    tip_text = "Wait for the bot player to place a tile."
            else:
                # Full Screen Completed Map
                pygame.draw.rect(hud_card, settings.COLOR_NEON_GREEN, (0, 0, 450, 80), width=2, border_radius=10)
                status_text = "MAP CONSTRUCTION COMPLETE"
                color_status = settings.COLOR_NEON_GREEN
                tip_text = "Map stabilized. Use WASD to navigate full screen."
                
            txt_status = font_title.render(status_text, True, color_status)
            txt_tip = font_body.render(tip_text, True, settings.COLOR_TEXT_PRIMARY)
            txt_scroll = font_body.render("WASD or Arrows: Camera Scroll  |  ESC: Exit", True, settings.COLOR_TEXT_MUTED)
            
            hud_card.blit(txt_status, (20, 12))
            hud_card.blit(txt_tip, (20, 36))
            hud_card.blit(txt_scroll, (20, 54))
            
            # Draw HUD card at top-right of display
            screen.blit(hud_card, (settings.SCREEN_WIDTH - 480, 20))
            
            # Show small player and bot hands counters
            if game_phase == settings.PHASE_MAP_BUILDING:
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

        # Update display & double-buffer
        pygame.display.flip()

    # Safe Engine Exit
    print("Safely shutting down Alignments engine...")
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
