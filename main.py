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
import bot
from map import MapGrid
from player import Player
from champions import Champion
from armies import Army




def draw_left_phase_panel(screen, left_panel_rect, current_faction, current_turn_phase, map_grid, mouse_x, mouse_y, is_mustering=False, secret_faction=None):
    """
    Renders the Faction Turn Phase control panel on the left during human player's turn.
    """
    # Draw background panel
    pygame.draw.rect(screen, settings.COLOR_HUD_BG, left_panel_rect)
    pygame.draw.rect(screen, settings.COLOR_NEON_CYAN, left_panel_rect, width=1)
    
    try:
        font_title = util.get_font(24, bold=True)
        font_label = util.get_font(14, bold=True)
        font_value = util.get_font(18)
        
        # Faction name info (placed at the top)
        lbl_faction = font_label.render("ACTIVE FACTION", True, settings.COLOR_TEXT_MUTED)
        screen.blit(lbl_faction, (20, 30))
        
        val_faction = font_title.render(current_faction.race.upper(), True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_faction, (20, 50))
        
        # Collapse Button "<<"
        collapse_btn_rect = pygame.Rect(250, 25, 30, 30)
        is_hover_collapse = collapse_btn_rect.collidepoint(mouse_x, mouse_y)
        collapse_fill = (40, 45, 55) if is_hover_collapse else (25, 29, 38)
        collapse_border = settings.COLOR_NEON_CYAN if is_hover_collapse else settings.COLOR_TEXT_MUTED
        
        pygame.draw.rect(screen, collapse_fill, collapse_btn_rect, border_radius=6)
        pygame.draw.rect(screen, collapse_border, collapse_btn_rect, width=1, border_radius=6)
        
        font_collapse = util.get_font(14, bold=True)
        txt_collapse = font_collapse.render("<<", True, settings.COLOR_TEXT_PRIMARY if is_hover_collapse else settings.COLOR_TEXT_MUTED)
        txt_collapse_rect = txt_collapse.get_rect(center=collapse_btn_rect.center)
        screen.blit(txt_collapse, txt_collapse_rect)
        
        # Divider (shifted down slightly)
        pygame.draw.line(screen, settings.COLOR_TEXT_MUTED, (20, 90), (280, 90), 1)
        
        # Phase Title (placed below the divider)
        lbl_phase = font_label.render("CURRENT PHASE", True, settings.COLOR_TEXT_MUTED)
        screen.blit(lbl_phase, (20, 110))
        
        if current_turn_phase == settings.TURN_PHASE_INCOME:
            phase_str = "MUSTER PHASE"
        elif current_turn_phase == settings.TURN_PHASE_MOVE:
            phase_str = "MOVEMENT PHASE"
        elif current_turn_phase == settings.TURN_PHASE_COMBAT:
            phase_str = "COMBAT PHASE"
        elif current_turn_phase == settings.TURN_PHASE_CONTROL:
            phase_str = "CONTROL PHASE"
        elif current_turn_phase == settings.TURN_PHASE_VICTORY:
            phase_str = "VICTORY CHECK"
        else:
            phase_str = "ACTIVE PHASE"
        val_phase = font_title.render(phase_str, True, settings.COLOR_NEON_CYAN)
        screen.blit(val_phase, (20, 130))
        
        # Treasury gold info
        if current_turn_phase != settings.TURN_PHASE_VICTORY:
            lbl_gold = font_label.render("FACTION TREASURY", True, settings.COLOR_TEXT_MUTED)
            screen.blit(lbl_gold, (20, 200))
            
            val_gold = font_value.render(f"🪙 {current_faction.gold} Gold", True, settings.COLOR_NEON_GREEN)
            screen.blit(val_gold, (20, 225))
        
        if current_turn_phase == settings.TURN_PHASE_CONTROL:
            # Controlled Hexes count
            lbl_hexes = font_label.render("CONTROLLED HEXES", True, settings.COLOR_TEXT_MUTED)
            screen.blit(lbl_hexes, (20, 270))
            
            controlled_count = map_grid.get_controlled_hex_count(current_faction)
            val_hexes = font_value.render(f"⬢ {controlled_count} Hexes", True, (255, 215, 0))
            screen.blit(val_hexes, (20, 295))
        elif current_turn_phase == settings.TURN_PHASE_VICTORY:
            # Victory Points
            lbl_vp = font_label.render("VICTORY POINTS", True, settings.COLOR_TEXT_MUTED)
            screen.blit(lbl_vp, (20, 200))
            
            # Find opposed factions and count destroyed strongholds
            vp = 0
            opposed_statuses = []
            if secret_faction is not None:
                from factions import FACTIONS
                opposed_factions = [f for f in FACTIONS if secret_faction.isOpposed(f)]
                for f in opposed_factions:
                    sh_coord = map_grid.find_stronghold_coord(f)
                    if sh_coord is None:
                        vp += 1
                        opposed_statuses.append(f"{f.race}: DESTROYED")
                    else:
                        opposed_statuses.append(f"{f.race}: Active")
            
            val_vp = font_value.render(f"🏆 {vp} / 3 Opposed", True, (255, 215, 0))
            screen.blit(val_vp, (20, 225))
            
            # Opposed Strongholds list
            lbl_opposed = font_label.render("OPPOSED STRONGHOLDS", True, settings.COLOR_TEXT_MUTED)
            screen.blit(lbl_opposed, (20, 270))
            
            y_offset = 295
            for status_str in opposed_statuses:
                color = settings.COLOR_NEON_PINK if "DESTROYED" in status_str else settings.COLOR_TEXT_PRIMARY
                txt_status = font_value.render(status_str, True, color)
                screen.blit(txt_status, (20, y_offset))
                y_offset += 25
        
        if current_turn_phase == settings.TURN_PHASE_INCOME:
            # "Muster Army" Button
            muster_btn_rect = pygame.Rect(20, 400, 260, 50)
            is_hover_muster = muster_btn_rect.collidepoint(mouse_x, mouse_y)
            
            if is_mustering:
                muster_fill = (50, 45, 25) if is_hover_muster else (35, 30, 15)
                muster_border = (255, 215, 0)
            else:
                muster_fill = (40, 45, 55) if is_hover_muster else (25, 29, 38)
                muster_border = settings.COLOR_NEON_CYAN if is_hover_muster else settings.COLOR_TEXT_MUTED
                
            pygame.draw.rect(screen, muster_fill, muster_btn_rect, border_radius=10)
            pygame.draw.rect(screen, muster_border, muster_btn_rect, width=2, border_radius=10)
            
            text_color = (255, 215, 0) if is_mustering else (settings.COLOR_TEXT_PRIMARY if is_hover_muster else settings.COLOR_TEXT_MUTED)
            txt_muster = font_label.render("MUSTER ARMY (COST: 1G)", True, text_color)
            txt_muster_rect = txt_muster.get_rect(center=muster_btn_rect.center)
            screen.blit(txt_muster, txt_muster_rect)
            
            # "Done" Button
            done_btn_rect = pygame.Rect(20, 470, 260, 50)
            is_hover_done = done_btn_rect.collidepoint(mouse_x, mouse_y)
            done_fill = (40, 45, 55) if is_hover_done else (25, 29, 38)
            done_border = settings.COLOR_NEON_CYAN if is_hover_done else settings.COLOR_TEXT_MUTED
            
            pygame.draw.rect(screen, done_fill, done_btn_rect, border_radius=10)
            pygame.draw.rect(screen, done_border, done_btn_rect, width=2, border_radius=10)
            
            txt_done = font_label.render("DONE", True, settings.COLOR_TEXT_PRIMARY if is_hover_done else settings.COLOR_TEXT_MUTED)
            txt_done_rect = txt_done.get_rect(center=done_btn_rect.center)
            screen.blit(txt_done, txt_done_rect)
        elif current_turn_phase in (settings.TURN_PHASE_MOVE, settings.TURN_PHASE_COMBAT, settings.TURN_PHASE_CONTROL, settings.TURN_PHASE_VICTORY):
            # "Done" Button at y = 400
            done_btn_rect = pygame.Rect(20, 400, 260, 50)
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


def draw_bot_collapsed_tab(screen, current_faction, current_turn_phase):
    """
    Renders the small collapsed tab in the upper left during Bot Player 2's turn.
    """
    tab_rect = pygame.Rect(20, 20, 260, 85)
    # Draw solid black background for max contrast
    pygame.draw.rect(screen, (0, 0, 0), tab_rect, border_radius=10)
    pygame.draw.rect(screen, settings.COLOR_NEON_PINK, tab_rect, width=2, border_radius=10)
    try:
        font_tab_faction = util.get_font(16, bold=True)
        font_tab_phase = util.get_font(12, bold=True)
        
        # Line 1: BOT PLAYER 2
        txt_bot = font_tab_faction.render("BOT PLAYER 2", True, settings.COLOR_NEON_PINK)
        screen.blit(txt_bot, (35, 30))
        
        # Map current turn phase to name
        if current_turn_phase == settings.TURN_PHASE_INCOME:
            phase_str = "MUSTER"
        elif current_turn_phase == settings.TURN_PHASE_MOVE:
            phase_str = "MOVEMENT"
        elif current_turn_phase == settings.TURN_PHASE_COMBAT:
            phase_str = "COMBAT"
        elif current_turn_phase == settings.TURN_PHASE_CONTROL:
            phase_str = "CONTROL"
        else:
            phase_str = "ACTIVE"
            
        # Line 2: <FACTION> - <PHASE>
        txt_turn = font_tab_phase.render(f"{current_faction.race.upper()} - {phase_str}", True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(txt_turn, (35, 55))
    except Exception as e:
        print(f"[Render Error] Failed to draw collapsed bot tab: {e}")


def draw_collapsed_tab(screen, current_faction, current_turn_phase, map_grid, mouse_x, mouse_y):
    """
    Renders the small collapsed tab in the upper left during Player 1's turn.
    """
    tab_rect = pygame.Rect(20, 20, 260, 85)
    # Draw solid black background for max contrast
    pygame.draw.rect(screen, (0, 0, 0), tab_rect, border_radius=10)
    pygame.draw.rect(screen, settings.COLOR_NEON_CYAN, tab_rect, width=2, border_radius=10)
    try:
        font_tab_faction = util.get_font(16, bold=True)
        font_tab_phase = util.get_font(12, bold=True)
        font_tab_stats = util.get_font(12, bold=True)
        font_arrow = util.get_font(22, bold=True)
        
        # Faction name text
        txt_faction = font_tab_faction.render(current_faction.race.upper(), True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(txt_faction, (35, 30))
        
        # Phase name text
        if current_turn_phase == settings.TURN_PHASE_INCOME:
            phase_str = "MUSTER"
        elif current_turn_phase == settings.TURN_PHASE_MOVE:
            phase_str = "MOVEMENT"
        elif current_turn_phase == settings.TURN_PHASE_COMBAT:
            phase_str = "COMBAT"
        elif current_turn_phase == settings.TURN_PHASE_CONTROL:
            phase_str = "CONTROL"
        elif current_turn_phase == settings.TURN_PHASE_VICTORY:
            phase_str = "VICTORY"
        else:
            phase_str = "ACTIVE"
            
        txt_phase = font_tab_phase.render(f"{phase_str} PHASE", True, settings.COLOR_NEON_CYAN)
        screen.blit(txt_phase, (35, 52))
        
        # Third line text depending on current phase
        third_line_str = ""
        if current_turn_phase == settings.TURN_PHASE_INCOME:
            third_line_str = f"Gold: {current_faction.gold}"
        elif current_turn_phase == settings.TURN_PHASE_MOVE:
            unmoved_armies = sum(1 for loc, armies in map_grid.armies.items() for army in armies if army.faction == current_faction and not army.has_moved)
            unmoved_champions = sum(1 for loc, champs in map_grid.champions.items() for champ in champs if champ.faction == current_faction and not getattr(champ, 'has_moved', False))
            units_left = unmoved_armies + unmoved_champions
            third_line_str = f"Left to Move: {units_left}"
        elif current_turn_phase == settings.TURN_PHASE_CONTROL:
            controlled_count = map_grid.get_controlled_hex_count(current_faction)
            third_line_str = f"Hexes Controlled: {controlled_count}"

        if third_line_str:
            txt_stats = font_tab_stats.render(third_line_str, True, settings.COLOR_TEXT_MUTED)
            screen.blit(txt_stats, (35, 74))
        
        # Vertical divider line
        pygame.draw.line(screen, settings.COLOR_TEXT_MUTED, (195, 25), (195, 100), 1)
        
        # ">>" Button
        done_btn_rect = pygame.Rect(210, 27, 60, 70)
        is_hover_done = done_btn_rect.collidepoint(mouse_x, mouse_y)
        
        done_fill = (40, 45, 55) if is_hover_done else (25, 29, 38)
        done_border = settings.COLOR_NEON_CYAN if is_hover_done else settings.COLOR_TEXT_MUTED
        
        pygame.draw.rect(screen, done_fill, done_btn_rect, border_radius=8)
        pygame.draw.rect(screen, done_border, done_btn_rect, width=1, border_radius=8)
        
        txt_arrow = font_arrow.render(">>", True, settings.COLOR_TEXT_PRIMARY if is_hover_done else settings.COLOR_TEXT_MUTED)
        txt_arrow_rect = txt_arrow.get_rect(center=done_btn_rect.center)
        screen.blit(txt_arrow, txt_arrow_rect)
        
    except Exception as e:
        print(f"[Render Error] Failed to draw collapsed tab: {e}")


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
        font_hud = util.get_font(22, bold=True)
        font_label = util.get_font(14, bold=True)
        font_value = util.get_font(16)
        font_title_bold = util.get_font(22, bold=True)
        
        # Champion Image Card Container
        img_rect = pygame.Rect(60, 50, 180, 180)
        pygame.draw.rect(screen, settings.COLOR_BACKGROUND, img_rect, border_radius=15)
        pygame.draw.rect(screen, glow_color, img_rect, width=3, border_radius=15)
        
        # Champion square surface scaling
        champ_surf = selected_champion.get_surface(size=(174, 174), mask_type="square")
        screen.blit(champ_surf, (63, 53))
        
        # Champion Title
        name_text = "CHAMPION"
        name_surf = font_title_bold.render(name_text, True, settings.COLOR_TEXT_PRIMARY)
        name_rect = name_surf.get_rect(center=(150, 270))
        screen.blit(name_surf, name_rect)
        
        # Statistics rows
        start_y = 320
        row_h = 75
        
        # Location Row
        loc_rect = pygame.Rect(20, start_y, 260, 60)
        pygame.draw.rect(screen, (20, 24, 33), loc_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, loc_rect, width=1, border_radius=8)
        
        lbl_loc = font_label.render("LOCATION", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_loc, (35, start_y + 10))
        
        tile = map_grid.get_tile(selected_champion.q, selected_champion.r)
        formatted_loc = util.format_location_name(tile.terrain_type) if tile else "Empty Space"
        val_loc = font_value.render(formatted_loc, True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_loc, (35, start_y + 30))
        
        # Strength Row
        str_rect = pygame.Rect(20, start_y + row_h, 260, 60)
        pygame.draw.rect(screen, (20, 24, 33), str_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, str_rect, width=1, border_radius=8)
        
        lbl_str = font_label.render("STRENGTH", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_str, (35, start_y + row_h + 10))
        
        val_str = font_value.render(str(selected_champion.strength), True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_str, (35, start_y + row_h + 30))
        
        # Horizontal progress bar for strength
        max_str = 15
        bar_w = 120
        bar_h = 10
        bx = 140
        by = start_y + row_h + 33
        pygame.draw.rect(screen, (40, 45, 55), (bx, by, bar_w, bar_h), border_radius=5)
        fill_w = int(bar_w * min(1.0, selected_champion.strength / max_str))
        pygame.draw.rect(screen, settings.COLOR_NEON_GREEN, (bx, by, fill_w, bar_h), border_radius=5)
        
        # Faction Row
        align_rect = pygame.Rect(20, start_y + 2 * row_h, 260, 60)
        pygame.draw.rect(screen, (20, 24, 33), align_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, align_rect, width=1, border_radius=8)
        
        lbl_align = font_label.render("FACTION", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_align, (35, start_y + 2 * row_h + 10))
        
        val_align = font_value.render(selected_champion.faction.race.upper(), True, glow_color)
        screen.blit(val_align, (35, start_y + 2 * row_h + 30))
        
        # Artifact Row
        art_rect = pygame.Rect(20, start_y + 3 * row_h, 260, 60)
        pygame.draw.rect(screen, (20, 24, 33), art_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, art_rect, width=1, border_radius=8)
        
        lbl_art = font_label.render("ARTIFACT", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_art, (35, start_y + 3 * row_h + 10))
        
        if getattr(selected_champion, 'artifact', None) is not None:
            art_name = selected_champion.artifact.name.upper()
            val_art = font_value.render(art_name, True, settings.COLOR_NEON_PINK)
            try:
                art_img = selected_champion.artifact.get_image(size=(40, 40))
                screen.blit(art_img, (220, start_y + 3 * row_h + 10))
            except Exception as e:
                print(f"[UI Warning] Failed to render artifact image: {e}")
        else:
            val_art = font_value.render("NONE", True, settings.COLOR_TEXT_MUTED)
        screen.blit(val_art, (35, start_y + 3 * row_h + 30))
        
        # Close Button at bottom (y = 800 since there are no moves/summon options)
        close_btn_rect = pygame.Rect(20, 800, 260, 45)
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
        font_hud = util.get_font(22, bold=True)
        font_label = util.get_font(14, bold=True)
        font_value = util.get_font(16)
        font_title_bold = util.get_font(22, bold=True)
        
        # Army Image Card Container
        img_rect = pygame.Rect(60, 50, 180, 180)
        pygame.draw.rect(screen, settings.COLOR_BACKGROUND, img_rect, border_radius=15)
        pygame.draw.rect(screen, glow_color, img_rect, width=3, border_radius=15)
        
        # Army square surface scaling
        army_surf = selected_army.get_surface(size=(174, 174), mask_type="square")
        screen.blit(army_surf, (63, 53))
        
        # Army Title
        name_text = selected_army.name.upper()
        name_surf = font_title_bold.render(name_text, True, settings.COLOR_TEXT_PRIMARY)
        name_rect = name_surf.get_rect(center=(150, 270))
        screen.blit(name_surf, name_rect)
        
        # Statistics rows
        start_y = 320
        row_h = 70
        
        # Location Row
        loc_rect = pygame.Rect(20, start_y, 260, 56)
        pygame.draw.rect(screen, (20, 24, 33), loc_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, loc_rect, width=1, border_radius=8)
        
        lbl_loc = font_label.render("LOCATION", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_loc, (35, start_y + 8))
        
        tile = map_grid.get_tile(selected_army.q, selected_army.r)
        formatted_loc = util.format_location_name(tile.terrain_type) if tile else "Empty Space"
        val_loc = font_value.render(formatted_loc, True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_loc, (35, start_y + 26))
        
        # Strength Row
        str_rect = pygame.Rect(20, start_y + row_h, 260, 56)
        pygame.draw.rect(screen, (20, 24, 33), str_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, str_rect, width=1, border_radius=8)
        
        lbl_str = font_label.render("STRENGTH", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_str, (35, start_y + row_h + 8))
        
        val_str = font_value.render(str(selected_army.strength), True, settings.COLOR_TEXT_PRIMARY)
        screen.blit(val_str, (35, start_y + row_h + 26))
        
        # Horizontal progress bar for strength
        max_str = 15
        bar_w = 120
        bar_h = 10
        bx = 140
        by = start_y + row_h + 29
        pygame.draw.rect(screen, (40, 45, 55), (bx, by, bar_w, bar_h), border_radius=5)
        fill_w = int(bar_w * min(1.0, selected_army.strength / max_str))
        pygame.draw.rect(screen, settings.COLOR_NEON_GREEN, (bx, by, fill_w, bar_h), border_radius=5)
        
        # Owning Faction Row
        align_rect = pygame.Rect(20, start_y + 2 * row_h, 260, 56)
        pygame.draw.rect(screen, (20, 24, 33), align_rect, border_radius=8)
        pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, align_rect, width=1, border_radius=8)
        
        lbl_align = font_label.render("OWNING FACTION", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_align, (35, start_y + 2 * row_h + 8))
        
        val_align = font_value.render(selected_army.faction.race.upper(), True, glow_color)
        screen.blit(val_align, (35, start_y + 2 * row_h + 26))
        
        # Close Button at bottom (y = 800 since there are no moves/summon options)
        close_btn_rect = pygame.Rect(20, 800, 260, 45)
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
        font_tooltip = util.get_font(12, bold=True)
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


def draw_hud_status_card(screen, human_player_obj, map_grid, mouse_x, mouse_y):
    """
    Renders the gameplay HUD status card at the top right, including Zoom buttons and the View Ring button.
    """
    try:
        font_secret = util.get_font(16, bold=True)
        font_body = util.get_font(12)
        font_zoom_label = util.get_font(14, bold=True)
        font_zoom = util.get_font(18, bold=True)
        
        hud_card = pygame.Surface((450, 120), pygame.SRCALPHA)
        pygame.draw.rect(hud_card, settings.COLOR_HUD_BG, (0, 0, 450, 120), border_radius=10)
        pygame.draw.rect(hud_card, settings.COLOR_NEON_GREEN, (0, 0, 450, 120), width=2, border_radius=10)
        
        # Secret faction at the top, increased font size
        tip_text = f"Secret Faction: {human_player_obj.faction.race} (Ring {human_player_obj.faction.ring_number})"
        txt_tip = font_secret.render(tip_text, True, settings.COLOR_TEXT_PRIMARY)
        hud_card.blit(txt_tip, (20, 14))
 
        # Calculate victory points
        vp = 0
        from factions import FACTIONS
        opposed_factions = [f for f in FACTIONS if human_player_obj.faction.isOpposed(f)]
        for f in opposed_factions:
            sh_coord = map_grid.find_stronghold_coord(f)
            if sh_coord is None:
                vp += 1
        txt_vp = font_body.render(f"Victory Points: {vp} / 3", True, settings.COLOR_NEON_CYAN)
        hud_card.blit(txt_vp, (20, 36))
 
        # "Zoom" text to the left of the + and - buttons (moved down to the View Ring row)
        txt_zoom = font_zoom_label.render("Zoom", True, settings.COLOR_TEXT_MUTED)
        hud_card.blit(txt_zoom, (305, 66))
 
        # Zoom Out Button (moved down to the View Ring row)
        zoom_out_rect = pygame.Rect(355, 60, 28, 28)
        zoom_out_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 355, 20 + 60, 28, 28)
        is_hover_out = zoom_out_global_rect.collidepoint(mouse_x, mouse_y)
        out_fill = (40, 45, 55) if is_hover_out else (25, 29, 38)
        out_border = settings.COLOR_NEON_CYAN if is_hover_out else settings.COLOR_TEXT_MUTED
        pygame.draw.rect(hud_card, out_fill, zoom_out_rect, border_radius=6)
        pygame.draw.rect(hud_card, out_border, zoom_out_rect, width=1, border_radius=6)
        
        txt_out = font_zoom.render("-", True, settings.COLOR_TEXT_PRIMARY if is_hover_out else settings.COLOR_TEXT_MUTED)
        txt_out_rect = txt_out.get_rect(center=zoom_out_rect.center)
        hud_card.blit(txt_out, txt_out_rect)
 
        # Zoom In Button (moved down to the View Ring row)
        zoom_in_rect = pygame.Rect(395, 60, 28, 28)
        zoom_in_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 395, 20 + 60, 28, 28)
        is_hover_in = zoom_in_global_rect.collidepoint(mouse_x, mouse_y)
        in_fill = (40, 45, 55) if is_hover_in else (25, 29, 38)
        in_border = settings.COLOR_NEON_CYAN if is_hover_in else settings.COLOR_TEXT_MUTED
        pygame.draw.rect(hud_card, in_fill, zoom_in_rect, border_radius=6)
        pygame.draw.rect(hud_card, in_border, zoom_in_rect, width=1, border_radius=6)
        
        txt_in = font_zoom.render("+", True, settings.COLOR_TEXT_PRIMARY if is_hover_in else settings.COLOR_TEXT_MUTED)
        txt_in_rect = txt_in.get_rect(center=zoom_in_rect.center)
        hud_card.blit(txt_in, txt_in_rect)
 
        # View Ring Button
        view_ring_rect = pygame.Rect(20, 59, 120, 30)
        view_ring_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 20, 20 + 59, 120, 30)
        is_hover_ring = view_ring_global_rect.collidepoint(mouse_x, mouse_y)
        ring_fill = (40, 45, 55) if is_hover_ring else (25, 29, 38)
        ring_border = settings.COLOR_NEON_CYAN if is_hover_ring else settings.COLOR_TEXT_MUTED
        pygame.draw.rect(hud_card, ring_fill, view_ring_rect, border_radius=6)
        pygame.draw.rect(hud_card, ring_border, view_ring_rect, width=1, border_radius=6)
        
        font_ring = util.get_font(14, bold=True)
        txt_ring = font_ring.render("VIEW RING", True, settings.COLOR_TEXT_PRIMARY if is_hover_ring else settings.COLOR_TEXT_MUTED)
        txt_ring_rect = txt_ring.get_rect(center=view_ring_rect.center)
        hud_card.blit(txt_ring, txt_ring_rect)
 
        # Map movement instructions at the bottom
        txt_scroll = font_body.render("WASD or Arrows: Camera Scroll  |  ESC: Deselect", True, settings.COLOR_TEXT_MUTED)
        hud_card.blit(txt_scroll, (20, 98))
 
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

    def process_control_phase(faction):
        # Consolidate armies of the moving faction in each hex
        for loc in list(map_grid.armies.keys()):
            q, r = loc
            faction_armies = [a for a in map_grid.armies[loc] if a.faction == faction]
            if len(faction_armies) > 1:
                total_strength = sum(a.strength for a in faction_armies)
                remaining_army = faction_armies[0]
                remaining_army.strength = total_strength
                
                # Remove the rest of the armies of this faction on this hex
                for other_army in faction_armies[1:]:
                    map_grid.remove_army(other_army)

        # We only examine hexes that either have a unit for the active faction (whose turn we are on),
        # or are currently owned by the active faction.
        from factions import Faction
        for (q, r), tile in map_grid.tiles.items():
            # Strongholds are immune to normal control phase changes
            if tile.is_stronghold:
                continue

            if tile.owner is not None and not isinstance(tile.owner, Faction):
                tile.owner = None

            # Check if active faction has any units in this hex
            has_active_unit = False
            if any(army.faction == faction for army in map_grid.armies.get((q, r), [])):
                has_active_unit = True
            if any(champ.faction == faction for champ in map_grid.champions.get((q, r), [])):
                has_active_unit = True

            is_active_owner = (tile.owner == faction)

            # Skip hexes that neither have a unit for the active Faction nor are owned by the active Faction
            if not has_active_unit and not is_active_owner:
                continue

            # Determine if there are any adversaries (Unaligned or Loosely Aligned relative to active faction)
            # Adversary/Unaligned/Loosely Aligned means: NOT Fully Aligned and NOT Strongly Aligned with active faction.
            active_adversary_present = False
            for army in map_grid.armies.get((q, r), []):
                if not (faction.isFullyAligned(army.faction) or faction.isStronglyAligned(army.faction)):
                    active_adversary_present = True
                    break
            if not active_adversary_present:
                for champ in map_grid.champions.get((q, r), []):
                    if not (faction.isFullyAligned(champ.faction) or faction.isStronglyAligned(champ.faction)):
                        active_adversary_present = True
                        break

            # Check rules
            if is_active_owner:
                # --- LOSS CHECK ---
                # Control is lost if:
                # 1. No Faction unit (of the owner) is in the hex (since we are active_owner, this is has_active_unit = False)
                # 2. At least one adversary unit is in the hex
                # Since we are already active_owner, if has_active_unit is False, we check active_adversary_present.
                if not has_active_unit and active_adversary_present:
                    tile.owner = None
                    print(f"[Control Phase] Faction {faction.race} lost control of hex ({q}, {r})")
            else:
                # --- GAIN CHECK ---
                # We know has_active_unit is True (otherwise we would have skipped the hex).
                # Current owner is not active faction.
                # First, check if current owner (if any, let's call it prev_owner) loses control.
                owner_loses = False
                prev_owner = tile.owner
                if prev_owner is not None:
                    # Current owner B loses control if B has no units present,
                    # and there is an adversary unit relative to B present (A is present and A is adversary to B).
                    has_owner_unit = False
                    if any(army.faction == prev_owner for army in map_grid.armies.get((q, r), [])):
                        has_owner_unit = True
                    if any(champ.faction == prev_owner for champ in map_grid.champions.get((q, r), [])):
                        has_owner_unit = True

                    owner_adversary_present = False
                    for army in map_grid.armies.get((q, r), []):
                        if not (prev_owner.isFullyAligned(army.faction) or prev_owner.isStronglyAligned(army.faction)):
                            owner_adversary_present = True
                            break
                    if not owner_adversary_present:
                        for champ in map_grid.champions.get((q, r), []):
                            if not (prev_owner.isFullyAligned(champ.faction) or prev_owner.isStronglyAligned(champ.faction)):
                                owner_adversary_present = True
                                break

                    owner_loses = (not has_owner_unit) and owner_adversary_present

                if prev_owner is not None and owner_loses:
                    tile.owner = None
                    print(f"[Control Phase] Faction {prev_owner.race} lost control of hex ({q}, {r})")

                if tile.owner is None:
                    # Hex is uncontrolled (or owner just lost it).
                    # Active faction gains control if no adversaries relative to active faction are present.
                    if not active_adversary_present:
                        tile.owner = faction
                        print(f"[Control Phase] Faction {faction.race} gained control of hex ({q}, {r})")


    # Helper function to start a player's turn
    def start_player_turn(player_index):
        nonlocal current_player_idx, current_faction, current_turn_phase, is_mustering
        is_mustering = False
        
        # Reset has_moved state for all armies and champions at start of a player turn
        for loc, armies_list in map_grid.armies.items():
            for army in armies_list:
                army.has_moved = False
        for loc, champs_list in map_grid.champions.items():
            for champ in champs_list:
                champ.has_moved = False
                
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
        from factions import FACTIONS
        gold_before = ", ".join([f"{f.race}={f.gold}" for f in FACTIONS])
        income = map_grid.calculate_faction_income(chosen_f)
        chosen_f.gold += income
        gold_after = ", ".join([f"{f.race}={f.gold}" for f in FACTIONS])
        print(f"[Gold Debug] Before: {gold_before} | Added {income} to {chosen_f.race} | After: {gold_after}")
        
        player_name = "Player 1" if player_index == 0 else "Bot Player 2"
        print(f"[Turn Start] {player_name} controls {chosen_f.race}. Phase: Muster. Added {income} gold (Total: {chosen_f.gold}).")
            
        # If human player, center camera on their Stronghold
        if player_index == 0:
            sh_coord = map_grid.find_stronghold_coord(chosen_f)
            if sh_coord:
                map_grid.center_on_hex(sh_coord[0], sh_coord[1])

    # Helper function to check units left to move
    def check_movement_left():
        unmoved_armies = sum(1 for loc, armies in map_grid.armies.items() for army in armies if army.faction == current_faction and not army.has_moved)
        unmoved_champions = sum(1 for loc, champs in map_grid.champions.items() for champ in champs if champ.faction == current_faction and not getattr(champ, 'has_moved', False))
        return unmoved_armies + unmoved_champions

    # Helper function to advance phase
    def advance_turn_phase():
        nonlocal current_turn_phase, is_mustering, selected_champion, selected_army
        is_mustering = False
        selected_champion = None
        selected_army = None
        if current_turn_phase == settings.TURN_PHASE_INCOME:
            current_turn_phase = settings.TURN_PHASE_MOVE
            if current_player_idx == 0 and check_movement_left() == 0:
                if map_grid.has_combat_for_faction(current_faction):
                    current_turn_phase = settings.TURN_PHASE_COMBAT
                else:
                    print(f"[Combat Phase] Automatically skipped Combat Phase for {current_faction.race} (no opposed units).")
                    current_turn_phase = settings.TURN_PHASE_CONTROL
                    process_control_phase(current_faction)
        elif current_turn_phase == settings.TURN_PHASE_MOVE:
            # Check if there is any hex containing our faction's units and an opposed faction's units
            if map_grid.has_combat_for_faction(current_faction):
                current_turn_phase = settings.TURN_PHASE_COMBAT
            else:
                print(f"[Combat Phase] Automatically skipped Combat Phase for {current_faction.race} (no opposed units).")
                current_turn_phase = settings.TURN_PHASE_CONTROL
                process_control_phase(current_faction)
        elif current_turn_phase == settings.TURN_PHASE_COMBAT:
            current_turn_phase = settings.TURN_PHASE_CONTROL
            process_control_phase(current_faction)
        elif current_turn_phase == settings.TURN_PHASE_CONTROL:
            # Check for victory/loss at the end of the turn
            for p_idx, p_obj in enumerate(players):
                p_name = "Player 1" if p_idx == 0 else "Bot Player 2"
                if map_grid.find_stronghold_coord(p_obj.faction) is None:
                    print(f"[GAME OVER] {p_name} ({p_obj.faction.race}) has lost their stronghold!")
                vp_count = 0
                from factions import FACTIONS
                opposed_facs = [f for f in FACTIONS if p_obj.faction.isOpposed(f)]
                for f in opposed_facs:
                    if map_grid.find_stronghold_coord(f) is None:
                        vp_count += 1
                if vp_count >= 2:
                    print(f"[VICTORY] {p_name} ({p_obj.faction.race}) WINS by destroying opposed strongholds!")
            
            # Immediately end faction turn and proceed to next player (bypassing Victory Phase)
            next_player_idx = 1 - current_player_idx
            start_player_turn(next_player_idx)


    # Initialize the first turn!
    start_player_turn(0)

    # --- PHASE 2: MAIN GAMEPLAY LOOP (MAP VIEWING) ---
    selected_champion = None
    selected_army = None
    is_mustering = False
    left_panel_collapsed = False
    
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
    ring_btn_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 20, 20 + 59, 120, 30)
    

    
    while running and game_phase == settings.PHASE_MAIN_GAME:
        dt = clock.tick(settings.FPS) / 1000.0
        
        # --- Bot Player Turn Automation ---
        if current_player_idx == 1:
            if current_turn_phase == settings.TURN_PHASE_INCOME:
                bot.run_bot_muster_phase(current_faction, map_grid, advance_turn_phase)
            elif current_turn_phase == settings.TURN_PHASE_MOVE:
                bot.run_bot_move_phase(current_faction, map_grid, advance_turn_phase)
            elif current_turn_phase == settings.TURN_PHASE_COMBAT:
                bot.run_bot_combat_phase(current_faction, map_grid, advance_turn_phase)
            elif current_turn_phase == settings.TURN_PHASE_CONTROL:
                bot.run_bot_control_phase(current_faction, map_grid, advance_turn_phase)
            else:
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
        show_full_left_panel = False
        is_own_champ_in_move = (selected_champion is not None and 
                                current_turn_phase == settings.TURN_PHASE_MOVE and 
                                selected_champion.faction == current_faction)
                                
        if selected_champion is not None and not is_own_champ_in_move:
            show_full_left_panel = True
        elif selected_army is not None and current_turn_phase != settings.TURN_PHASE_MOVE:
            show_full_left_panel = True
        elif current_player_idx == 0 and not left_panel_collapsed:
            show_full_left_panel = True

        if show_full_left_panel:
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
                elif event.key == pygame.K_SPACE:
                    if current_player_idx == 0:
                        advance_turn_phase()
                        util.play_sound(filename=None, volume=0.3, pitch_hz=440.0, duration_ms=100)
                        
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    # Check "Ring" button first
                    if ring_btn_rect.collidepoint(mouse_x, mouse_y):
                        show_ring_window = True
                        util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                        continue

                    # Check HUD Zoom buttons first
                    zoom_out_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 355, 20 + 49, 28, 28)
                    zoom_in_global_rect = pygame.Rect(settings.SCREEN_WIDTH - 480 + 395, 20 + 49, 28, 28)
                    
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
                    
                    # Check collapsed tab click first
                    is_own_champ_in_move = (selected_champion is not None and 
                                            current_turn_phase == settings.TURN_PHASE_MOVE and 
                                            selected_champion.faction == current_faction)
                                            
                    is_currently_collapsed = (left_panel_collapsed and 
                                             (selected_champion is None or is_own_champ_in_move) and 
                                             (selected_army is None or current_turn_phase == settings.TURN_PHASE_MOVE))
                    if is_currently_collapsed and current_player_idx == 0:
                        tab_rect = pygame.Rect(20, 20, 260, 85)
                        if tab_rect.collidepoint(mouse_x, mouse_y):
                            done_btn_rect = pygame.Rect(210, 27, 60, 70)
                            if done_btn_rect.collidepoint(mouse_x, mouse_y):
                                advance_turn_phase()
                                clicked_close = True
                                util.play_sound(filename=None, volume=0.3, pitch_hz=440.0, duration_ms=100)
                            else:
                                left_panel_collapsed = False
                                clicked_close = True
                                util.play_sound(filename=None, volume=0.3, pitch_hz=440.0, duration_ms=100)
                    
                    # Check panel buttons if selection is active
                    if not clicked_close:
                        if selected_champion is not None and left_panel_rect.collidepoint(mouse_x, mouse_y):
                            close_btn_rect = pygame.Rect(20, 800, 260, 45)
                            if close_btn_rect.collidepoint(mouse_x, mouse_y):
                                selected_champion = None
                                clicked_close = True
                                util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                        elif selected_army is not None and left_panel_rect.collidepoint(mouse_x, mouse_y):
                            close_btn_rect = pygame.Rect(20, 800, 260, 45)
                            if close_btn_rect.collidepoint(mouse_x, mouse_y):
                                selected_army = None
                                clicked_close = True
                                util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                        elif current_player_idx == 0 and left_panel_rect.collidepoint(mouse_x, mouse_y):
                            collapse_btn_rect = pygame.Rect(250, 25, 30, 30)
                            if collapse_btn_rect.collidepoint(mouse_x, mouse_y):
                                left_panel_collapsed = True
                                is_mustering = False
                                clicked_close = True
                                util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                            else:
                                # Define bounds dynamically based on current phase
                                if current_turn_phase == settings.TURN_PHASE_INCOME:
                                    done_btn_rect = pygame.Rect(20, 470, 260, 50)
                                    muster_btn_rect = pygame.Rect(20, 400, 260, 50)
                                elif current_turn_phase in (settings.TURN_PHASE_MOVE, settings.TURN_PHASE_COMBAT, settings.TURN_PHASE_CONTROL, settings.TURN_PHASE_VICTORY):
                                    done_btn_rect = pygame.Rect(20, 400, 260, 50)
                                    muster_btn_rect = pygame.Rect(0, 0, 0, 0)
                                else:
                                    done_btn_rect = pygame.Rect(0, 0, 0, 0)
                                    muster_btn_rect = pygame.Rect(0, 0, 0, 0)

                                if done_btn_rect.collidepoint(mouse_x, mouse_y):
                                    advance_turn_phase()
                                    clicked_close = True
                                    util.play_sound(filename=None, volume=0.3, pitch_hz=440.0, duration_ms=100)
                                elif muster_btn_rect.collidepoint(mouse_x, mouse_y):
                                    if current_turn_phase == settings.TURN_PHASE_INCOME and current_faction.gold > 0:
                                        is_mustering = not is_mustering
                                        util.play_sound(filename=None, volume=0.4, pitch_hz=587.33, duration_ms=100)
                                    clicked_close = True
                                
                    if not clicked_close:
                        if map_viewport_rect.collidepoint(mouse_x, mouse_y):
                            # Direct mustering check when collapsed
                            did_muster_action = False
                            if (left_panel_collapsed and selected_champion is None and selected_army is None and
                                current_turn_phase == settings.TURN_PHASE_INCOME):
                                q, r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
                                if map_grid.can_muster_army(current_faction, q, r):
                                    did_muster_action = True
                                    if current_faction.gold >= 1:
                                        map_grid.muster_army(current_faction, q, r, strength=1)
                                        current_faction.gold -= 1
                                        util.play_sound(filename=None, volume=0.4, pitch_hz=659.25, duration_ms=100)
                                        if current_faction.gold <= 0:
                                            advance_turn_phase()
                                    else:
                                        util.play_sound(filename=None, volume=0.2, pitch_hz=220.0, duration_ms=150)

                            if did_muster_action:
                                pass
                            elif is_mustering:
                                q, r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
                                if map_grid.can_muster_army(current_faction, q, r) and current_faction.gold >= 1:
                                    map_grid.muster_army(current_faction, q, r, strength=1)
                                    current_faction.gold -= 1
                                    util.play_sound(filename=None, volume=0.4, pitch_hz=659.25, duration_ms=100)
                                    if current_faction.gold <= 0:
                                        is_mustering = False
                                        advance_turn_phase()
                                else:
                                    util.play_sound(filename=None, volume=0.2, pitch_hz=220.0, duration_ms=150)
                            elif current_turn_phase == settings.TURN_PHASE_MOVE:
                                clicked_army = map_grid.get_army_at_screen_pos(mouse_x, mouse_y, map_viewport_rect)
                                clicked_champ = map_grid.get_champion_at_screen_pos(mouse_x, mouse_y, map_viewport_rect)
                                
                                # 1. If clicked own army
                                if clicked_army is not None and clicked_army.faction == current_faction:
                                    if clicked_army == selected_army:
                                        # Clicked a second time! Check if strength > 1
                                        if clicked_army.strength > 1:
                                            clicked_army.strength -= 1
                                            
                                            from armies import Army
                                            next_idx = map_grid.get_next_army_index(current_faction)
                                            new_army = Army(
                                                faction=current_faction,
                                                q=clicked_army.q,
                                                r=clicked_army.r,
                                                strength=1,
                                                index=next_idx
                                            )
                                            map_grid.add_army(new_army)
                                            
                                            selected_army = new_army
                                            selected_champion = None
                                            util.play_sound(filename=None, volume=0.4, pitch_hz=659.25, duration_ms=100)
                                        else:
                                            util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                                    else:
                                        if not clicked_army.has_moved:
                                            selected_army = clicked_army
                                            selected_champion = None
                                            util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                                        else:
                                            util.play_sound(filename=None, volume=0.2, pitch_hz=220.0, duration_ms=150)
                                        
                                # 2. If clicked own champion
                                elif clicked_champ is not None and clicked_champ.faction == current_faction:
                                    if not getattr(clicked_champ, 'has_moved', False):
                                        selected_champion = clicked_champ
                                        selected_army = None
                                        util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                                    else:
                                        util.play_sound(filename=None, volume=0.2, pitch_hz=220.0, duration_ms=150)
                                        
                                # 3. Clicked somewhere else (possible movement destination or select other units)
                                else:
                                    if selected_army is not None:
                                        q, r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
                                        if map_grid.can_move_army(selected_army, q, r):
                                            map_grid.move_army(selected_army, q, r)
                                            selected_army.has_moved = True # Mark as moved this turn
                                            selected_army = None
                                            util.play_sound(filename=None, volume=0.4, pitch_hz=587.33, duration_ms=100)
                                            if check_movement_left() == 0:
                                                advance_turn_phase()
                                        else:
                                            selected_army = None
                                            util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                                            
                                    elif selected_champion is not None and selected_champion.faction == current_faction:
                                        q, r = map_grid.screen_to_axial(mouse_x, mouse_y, map_viewport_rect)
                                        if map_grid.can_move_champion(selected_champion, q, r):
                                            map_grid.move_champion(selected_champion, q, r)
                                            selected_champion.has_moved = True # Mark as moved this turn
                                            selected_champion = None
                                            util.play_sound(filename=None, volume=0.4, pitch_hz=587.33, duration_ms=100)
                                            if check_movement_left() == 0:
                                                advance_turn_phase()
                                        else:
                                            selected_champion = None
                                            util.play_sound(filename=None, volume=0.3, pitch_hz=330.0, duration_ms=80)
                                            
                                    else:
                                        if clicked_champ is not None:
                                            selected_champion = clicked_champ
                                            selected_army = None
                                            util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                                        elif clicked_army is not None:
                                            selected_army = clicked_army
                                            selected_champion = None
                                            util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                                        else:
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
                            else:
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
        controlled_coords = [coord for coord, tile in map_grid.tiles.items() if tile.owner == current_faction]
        highlight_coords = list(controlled_coords)
        if current_turn_phase == settings.TURN_PHASE_MOVE:
            if selected_army is not None:
                if selected_army.hex_location not in highlight_coords:
                    highlight_coords.append(selected_army.hex_location)
            elif selected_champion is not None and selected_champion.faction == current_faction and not getattr(selected_champion, 'has_moved', False):
                if selected_champion.hex_location not in highlight_coords:
                    highlight_coords.append(selected_champion.hex_location)
        map_grid.draw(screen, map_viewport_rect, highlight_coords=highlight_coords, highlight_color=(255, 215, 0))
        
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

        # 2. Render Left Statistics Panel for selected Champion (only if not moving own champion in movement phase)
        show_champ_profile = False
        if selected_champion is not None:
            if current_turn_phase != settings.TURN_PHASE_MOVE or selected_champion.faction != current_faction:
                show_champ_profile = True
                
        if show_champ_profile:
            draw_left_champion_statistics_panel(screen, selected_champion, left_panel_rect, map_grid, mouse_x, mouse_y)
            
        # 2.1 Render Left Statistics Panel for selected Army (only if not in movement phase)
        elif selected_army is not None and current_turn_phase != settings.TURN_PHASE_MOVE:
            draw_left_army_statistics_panel(screen, selected_army, left_panel_rect, map_grid, mouse_x, mouse_y)

        # 2.2 Render Left Faction Turn Phase Panel / tab for active turn
        elif current_player_idx == 0:
            if left_panel_collapsed:
                draw_collapsed_tab(screen, current_faction, current_turn_phase, map_grid, mouse_x, mouse_y)
            else:
                draw_left_phase_panel(screen, left_panel_rect, current_faction, current_turn_phase, map_grid, mouse_x, mouse_y, is_mustering, secret_faction=human_player_obj.faction)
        elif current_player_idx == 1:
            draw_bot_collapsed_tab(screen, current_faction, current_turn_phase)

        # 3. Render HUD status card (Phase 2 version)
        draw_hud_status_card(screen, human_player_obj, map_grid, mouse_x, mouse_y)

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
            
            font_tip = util.get_font(14, bold=True)
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
            font_title = util.get_font(22, bold=True)
            txt_title = font_title.render("FACTION PROFILE", True, settings.COLOR_TEXT_MUTED)
            txt_title_rect = txt_title.get_rect(center=(settings.SCREEN_WIDTH // 2, win_y + 40))
            screen.blit(txt_title, txt_title_rect)
            
            # Race Header
            font_race = util.get_font(32, bold=True)
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
            
            font_label = util.get_font(14, bold=True)
            font_val = util.get_font(18)
            
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
            font_tip = util.get_font(14, bold=True)
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
