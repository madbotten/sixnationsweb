"""
Alignments - Game Entry Point
Implements the multi-phase game engine: Phase 1 (Map Building via drag-and-drop tile snapping
with an automated bot player) and Phase 2 (Full-screen scrollable map visualization with Champion and Army profiles).
"""

import sys
import pygame
import random
# Import configurations, map model, player system, and helper utilities
import settings
import util
import player
from map import MapGrid
from player import Player
from champions import Champion
from armies import Army




def calculate_forces_strength(forces_list, opposing_forces=None):
    """
    Calculates total combat strength for a side's forces.

    Artifact effects applied here:
    - FLAME_SWORD:      Champion's holding faction gains +2 combat strength.
    - WALL_BREAKER:     Treats opposing stronghold_strength as 2 less (applied on the
                        opposing side's stronghold item when resolving combat; handled
                        by passing a negative bonus via stronghold item's obj attribute).
    - TOXIC_CROSSBOW:   If the opposing side has a champion holding this, each champion
                        on THIS side fights at -1 strength (min 1).

    Args:
        forces_list (list): Force item dicts for this side.
        opposing_forces (list | None): Force item dicts for the opposing side, used to
                                       check for Toxic Crossbow.
    """
    # Check if opposing side has a champion carrying a Toxic Crossbow
    toxic_crossbow_active = False
    if opposing_forces:
        for item in opposing_forces:
            if item['type'] == 'champion':
                art = getattr(item['obj'], 'artifact', None)
                if art is not None and getattr(art, 'power', '') == 'TOXIC_CROSSBOW':
                    toxic_crossbow_active = True
                    break

    total = 0
    for item in forces_list:
        if item['type'] == 'army':
            total += getattr(item['obj'], 'strength', 1)
        elif item['type'] == 'champion':
            champ = item['obj']
            champ_str = getattr(champ, 'strength', 3)
            if toxic_crossbow_active:
                champ_str = max(1, champ_str - 1)
            total += champ_str
            art = getattr(champ, 'artifact', None)
            if art is not None and getattr(art, 'power', '') == 'FLAME_SWORD':
                total += 2  # Flame Sword: +2 combat strength
        elif item['type'] == 'stronghold':
            tile = item['obj']
            sh_str = tile.stronghold_strength
            total += sh_str
    return total


def resolve_combat(allied_forces, opposing_forces, moving_faction, map_grid):
    """
    Roll 1d6 + total strength for each side and return the result.

    Artifact effects applied here:
    - TOXIC_CROSSBOW: passed to calculate_forces_strength via opposing_forces.
    - WALL_BREAKER:   If allied side has a champion holding Wall Breaker and opposing
                      side has a stronghold, reduce effective stronghold strength by 2.
    """
    # Wall Breaker: check if allied champion holds it and opposing has a stronghold
    allied_has_wall_breaker = any(
        item['type'] == 'champion' and
        getattr(getattr(item['obj'], 'artifact', None), 'power', '') == 'WALL_BREAKER'
        for item in allied_forces
    )
    if allied_has_wall_breaker:
        for item in opposing_forces:
            if item['type'] == 'stronghold':
                tile = item['obj']
                tile.stronghold_strength = max(0, tile.stronghold_strength - 2)
                print(f"[Wall Breaker] Stronghold effective strength reduced by 2 (now {tile.stronghold_strength}).")

    allied_strength = calculate_forces_strength(allied_forces, opposing_forces=opposing_forces)
    opposed_strength = calculate_forces_strength(opposing_forces, opposing_forces=allied_forces)

    allied_roll = random.randint(1, 6)
    opposed_roll = random.randint(1, 6)

    allied_total = allied_strength + allied_roll
    opposed_total = opposed_strength + opposed_roll

    if allied_total > opposed_total:
        outcome = "allied"
    elif opposed_total > allied_total:
        outcome = "opposed"
    else:
        outcome = "draw"

    print(f"[Combat] Allied roll: {allied_roll} + strength {allied_strength} = {allied_total}")
    print(f"[Combat] Opposed roll: {opposed_roll} + strength {opposed_strength} = {opposed_total}")
    print(f"[Combat] Outcome: {outcome}")

    if outcome == "allied":
        take_combat_losses(allied_forces, opposing_forces, allied_roll, moving_faction, map_grid)
    elif outcome == "opposed":
        take_combat_losses(opposing_forces, allied_forces, opposed_roll, moving_faction, map_grid)

    return {
        "allied_roll": allied_roll,
        "allied_strength": allied_strength,
        "allied_total": allied_total,
        "opposed_roll": opposed_roll,
        "opposed_strength": opposed_strength,
        "opposed_total": opposed_total,
        "outcome": outcome,
    }



def take_combat_losses(winner_forces, loser_forces, winner_raw_die_roll, moving_faction, map_grid):
    """
    Apply combat losses to the losing side after a battle.

    Losses equal the winner's raw die roll.  Armies absorb losses before
    champions (armies are "preferential" targets).  Within armies, those
    whose faction is farthest from moving_faction on the diplomacy ring are
    eliminated first.  Armies take partial strength damage and are removed
    from both the display list and the game board when strength hits 0.
    Champions soak remaining losses with partial-strength damage and are
    similarly removed when strength hits 0.

    Artifact effects:
    - GOLDEN_AXE:  If the winning side has a champion holding Golden Axe, the
                   total losses inflicted increase by 1.
    - ELVEN_ARMS:  When a losing champion would take lethal damage (strength → 0),
                   the Elven Arms artifact is consumed instead: it absorbs up to 3 pts
                   of damage (champion survives with remaining strength), and any
                   overflow damage beyond what the artifact covers passes to an enemy
                   stronghold in the same hex (if one exists).

    Args:
        winner_forces:        List of force dicts on the winning side.
        loser_forces:         List of force dicts on the losing side.
        winner_raw_die_roll:  The raw 1d6 result rolled by the winning side
                              (equals the total losses inflicted).
        moving_faction:       The faction whose turn it is (used to determine
                              ring-distance ordering among loser armies).
        map_grid:             The MapGrid instance (used to remove destroyed
                              units from the game board).
    """
    losses_remaining = winner_raw_die_roll

    # --- Golden Axe: winner champion adds +1 to losses inflicted ---
    for item in winner_forces:
        if item['type'] == 'champion':
            art = getattr(item['obj'], 'artifact', None)
            if art is not None and getattr(art, 'power', '') == 'GOLDEN_AXE':
                losses_remaining += 1
                print(f"[Golden Axe] {item['obj'].name} inflicts +1 bonus loss (total: {losses_remaining}).")
                break  # Only one champion can trigger this

    # --- Phase 1: Armies absorb losses (farthest ring distance first) ---
    loser_armies = [item for item in loser_forces if item['type'] == 'army']

    # Sort armies so that farthest diplomatic distance from moving_faction
    # comes first (they are eliminated before closer allies).
    loser_armies.sort(
        key=lambda item: moving_faction.diplomatic_distance(item['obj'].faction),
        reverse=True
    )

    for item in loser_armies:
        if losses_remaining <= 0:
            break
        army = item['obj']
        damage = min(losses_remaining, army.strength)
        army.strength -= damage
        losses_remaining -= damage
        if army.strength <= 0:
            loser_forces.remove(item)
            map_grid.remove_army(army)
            print(f"[Combat Losses] Army '{item['name']}' ({army.faction.race}) destroyed.")
        else:
            print(f"[Combat Losses] Army '{item['name']}' ({army.faction.race}) took {damage} damage (strength now {army.strength}).")

    # --- Phase 2: Champions absorb remaining losses (with Elven Arms shield check) ---
    loser_champs = [item for item in loser_forces if item['type'] == 'champion']

    for item in loser_champs:
        if losses_remaining <= 0:
            break
        champ = item['obj']
        damage = min(losses_remaining, champ.strength)
        would_be_lethal = (damage >= champ.strength)

        art = getattr(champ, 'artifact', None)
        if would_be_lethal and art is not None and getattr(art, 'power', '') == 'ELVEN_ARMS':
            # --- Elven Arms: sacrifice the artifact to save the champion ---
            absorbed = min(3, damage)          # Artifact absorbs up to 3 pts
            overflow = damage - absorbed        # Remaining damage after absorption
            champ.strength -= absorbed
            if champ.strength <= 0:
                champ.strength = 1             # Champion survives with at least 1 strength
            losses_remaining -= damage
            champ.artifact = None              # Artifact is destroyed
            print(
                f"[Elven Arms] {champ.name}'s Elven Arms sacrificed! Absorbed {absorbed} damage. "
                f"Champion survives with {champ.strength} strength."
            )
            # Any overflow passes to an enemy stronghold in the same hex, if present
            if overflow > 0:
                loser_strongholds = [i for i in loser_forces if i['type'] == 'stronghold']
                for sh_item in loser_strongholds:
                    tile = sh_item['obj']
                    sh_damage = min(overflow, tile.stronghold_strength)
                    tile.stronghold_strength -= sh_damage
                    overflow -= sh_damage
                    if tile.stronghold_strength <= 0:
                        tile.is_stronghold = False
                        loser_forces.remove(sh_item)
                        print(f"[Elven Arms Overflow] Stronghold '{sh_item['name']}' destroyed by overflow damage!")
                    else:
                        print(f"[Elven Arms Overflow] Stronghold '{sh_item['name']}' took {sh_damage} overflow (strength now {tile.stronghold_strength}).")
                    break  # Only one stronghold target
        else:
            champ.strength -= damage
            losses_remaining -= damage
            if champ.strength <= 0:
                loser_forces.remove(item)
                map_grid.remove_champion(champ)
                print(f"[Combat Losses] Champion '{champ.name}' ({champ.faction.race}) slain.")
            else:
                print(f"[Combat Losses] Champion '{champ.name}' ({champ.faction.race}) took {damage} damage (strength now {champ.strength}).")

    # --- Phase 2.5: Stronghold absorbs remaining losses (after all units are gone) ---
    if losses_remaining > 0:
        loser_strongholds = [item for item in loser_forces if item['type'] == 'stronghold']
        for item in loser_strongholds:
            if losses_remaining <= 0:
                break
            tile = item['obj']
            damage = min(losses_remaining, tile.stronghold_strength)
            tile.stronghold_strength -= damage
            losses_remaining -= damage
            if tile.stronghold_strength <= 0:
                tile.is_stronghold = False
                loser_forces.remove(item)
                print(f"[Combat Losses] Stronghold '{item['name']}' has fallen! The stronghold is destroyed.")
            else:
                print(f"[Combat Losses] Stronghold '{item['name']}' took {damage} damage (strength now {tile.stronghold_strength}).")

    if losses_remaining > 0:
        print(f"[Combat Losses] {losses_remaining} excess loss(es) absorbed with no targets remaining.")


    # --- Phase 3: Winner takes half losses (rounded down) ---
    winner_losses = winner_raw_die_roll // 2
    print(f"[Combat Losses] Winner takes {winner_losses} loss(es) (half of {winner_raw_die_roll}).")

    winner_armies = [item for item in winner_forces if item['type'] == 'army']
    winner_armies.sort(
        key=lambda item: moving_faction.diplomatic_distance(item['obj'].faction),
        reverse=True
    )

    for item in winner_armies:
        if winner_losses <= 0:
            break
        army = item['obj']
        damage = min(winner_losses, army.strength)
        army.strength -= damage
        winner_losses -= damage
        if army.strength <= 0:
            winner_forces.remove(item)
            map_grid.remove_army(army)
            print(f"[Combat Losses] (Winner) Army '{item['name']}' ({army.faction.race}) destroyed.")
        else:
            print(f"[Combat Losses] (Winner) Army '{item['name']}' ({army.faction.race}) took {damage} damage (strength now {army.strength}).")

    winner_champs = [item for item in winner_forces if item['type'] == 'champion']

    for item in winner_champs:
        if winner_losses <= 0:
            break
        champ = item['obj']
        damage = min(winner_losses, champ.strength)
        champ.strength -= damage
        winner_losses -= damage
        if champ.strength <= 0:
            winner_forces.remove(item)
            map_grid.remove_champion(champ)
            print(f"[Combat Losses] (Winner) Champion '{champ.name}' ({champ.faction.race}) slain.")
        else:
            print(f"[Combat Losses] (Winner) Champion '{champ.name}' ({champ.faction.race}) took {damage} damage (strength now {champ.strength}).")

    if winner_losses > 0:
        print(f"[Combat Losses] {winner_losses} excess winner loss(es) absorbed with no targets remaining.")






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
    Returns an artifact tooltip tuple (text, color) if the mouse hovers over the
    artifact row and the champion holds an artifact, otherwise returns None.
    """
    artifact_tooltip = None

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

        art = getattr(selected_champion, 'artifact', None)
        if art is not None:
            # Highlight border in neon pink when the mouse hovers over the artifact row
            is_hover_art = art_rect.collidepoint(mouse_x, mouse_y)
            art_border_color = settings.COLOR_NEON_PINK if is_hover_art else settings.COLOR_TEXT_MUTED
            pygame.draw.rect(screen, art_border_color, art_rect, width=1, border_radius=8)
        else:
            pygame.draw.rect(screen, settings.COLOR_TEXT_MUTED, art_rect, width=1, border_radius=8)

        lbl_art = font_label.render("ARTIFACT", True, settings.COLOR_NEON_CYAN)
        screen.blit(lbl_art, (35, start_y + 3 * row_h + 10))
        
        if art is not None:
            art_name = art.name.upper()
            val_art = font_value.render(art_name, True, settings.COLOR_NEON_PINK)
            try:
                art_img = art.get_image(size=(40, 40))
                screen.blit(art_img, (220, start_y + 3 * row_h + 10))
            except Exception as e:
                print(f"[UI Warning] Failed to render artifact image: {e}")

            # Build tooltip when mouse hovers the artifact row
            power_tooltips = {
                "FLAME_SWORD":    "Flame Sword: +2 combat strength",
                "GOLDEN_AXE":     "Golden Axe: +1 loss inflicted when your side wins",
                "AIR_SWORD":      "Air Sword: move 2 hexes per turn",
                "ELVEN_ARMS":     "Elven Arms: sacrificed on lethal hit, absorbs 3 damage",
                "STAR_STAFF":     "Star Staff: +1 gold each income phase",
                "TOXIC_CROSSBOW": "Toxic Crossbow: enemy champions fight at -1 strength",
                "WALL_BREAKER":   "Wall Breaker: +2 effective strength vs. strongholds",
            }
            tooltip_text = power_tooltips.get(getattr(art, 'power', ''), art.name)
            if art_rect.collidepoint(mouse_x, mouse_y):
                artifact_tooltip = (tooltip_text, settings.COLOR_NEON_PINK)
        else:
            val_art = font_value.render("NONE", True, settings.COLOR_TEXT_MUTED)
        screen.blit(val_art, (35, start_y + 3 * row_h + 30))

        # Close Button at bottom
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

    return artifact_tooltip


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
    
    human_player_obj = Player(faction=shuffled_factions[0], is_bot=False)
    bot_player_obj = Player(faction=shuffled_factions[1], is_bot=True)
    
    # 5. Play startup chime (rising synthesizer sound)
    util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100) # C5
    pygame.time.delay(120)
    util.play_sound(filename=None, volume=0.5, pitch_hz=659.25, duration_ms=200) # E5
    
    running = True

    # --- Turn & Phase State Tracking ---
    # Two-player game: Index 0 is Human player, Index 1 is Bot player.
    players = [human_player_obj, bot_player_obj]
    current_player_idx = 0
    current_player = human_player_obj
    current_faction = None
    current_turn_phase = None
    previous_faction_by_player = [None, None]
    bot_just_started_turn = False

    def process_combat_phase(faction):
        nonlocal combat_hexes, current_combat_idx, loaded_combat_hex_idx, current_turn_phase
        # Consolidate armies and detect combat locations
        map_grid.consolidate_armies(faction)
        combat_hexes = map_grid.get_combat_hexes(faction)
        current_combat_idx = 0
        loaded_combat_hex_idx = -1

        # If human player and there are no combat locations, auto-skip to Control Phase
        if not current_player.is_robot() and not combat_hexes:
            print(f"[Combat Phase] Automatically skipped Combat Phase for {faction.race} (no opposed units).")
            advance_turn_phase()

    def process_control_phase(faction):
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
        nonlocal current_player_idx, current_player, current_faction, current_turn_phase, is_mustering, bot_just_started_turn
        is_mustering = False
        
        # Reset has_moved state for all armies and champions at start of a player turn
        for loc, armies_list in map_grid.armies.items():
            for army in armies_list:
                army.has_moved = False
        for loc, champs_list in map_grid.champions.items():
            for champ in champs_list:
                champ.has_moved = False
                # Air Sword: refresh the extra move step each turn
                art = getattr(champ, 'artifact', None)
                if art is not None and getattr(art, 'power', '') == 'AIR_SWORD':
                    champ.moves_remaining = 1
                else:
                    champ.moves_remaining = 0


        current_player_idx = player_index
        current_player = players[player_index]
        player = current_player
        
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

        # Star Staff: +1 gold if the faction's champion holds it
        for loc, champs in map_grid.champions.items():
            for champ in champs:
                if champ.faction == chosen_f:
                    art = getattr(champ, 'artifact', None)
                    if art is not None and getattr(art, 'power', '') == 'STAR_STAFF':
                        chosen_f.gold += 1
                        print(f"[Star Staff] {chosen_f.race} earns +1 bonus gold from Star Staff (total: {chosen_f.gold}).")

        gold_after = ", ".join([f"{f.race}={f.gold}" for f in FACTIONS])
        print(f"[Gold Debug] Before: {gold_before} | Added {income} to {chosen_f.race} | After: {gold_after}")
        
        player_name = "Player 1" if player_index == 0 else "Bot Player 2"
        print(f"[Turn Start] {player_name} controls {chosen_f.race}. Phase: Muster. Added {income} gold (Total: {chosen_f.gold}).")
        
        if player_index == 1:
            bot_just_started_turn = True
            
        # Center camera on the active faction's Stronghold
        sh_coord = map_grid.find_stronghold_coord(chosen_f)
        if sh_coord:
            map_grid.center_on_hex(sh_coord[0], sh_coord[1])

    # Helper function to check units left to move
    def check_movement_left():
        unmoved_armies = sum(1 for loc, armies in map_grid.armies.items() for army in armies if army.faction == current_faction and not army.has_moved)
        unmoved_champions = sum(1 for loc, champs in map_grid.champions.items() for champ in champs if champ.faction == current_faction and not getattr(champ, 'has_moved', False))
        return unmoved_armies + unmoved_champions

    def process_victory_phase():
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

    # Helper function to advance phase
    def advance_turn_phase():
        nonlocal current_turn_phase, is_mustering, selected_champion, selected_army
        nonlocal combat_hexes, current_combat_idx, loaded_combat_hex_idx
        is_mustering = False
        selected_champion = None
        selected_army = None

        # Advance from income to move
        if current_turn_phase == settings.TURN_PHASE_INCOME:
            current_turn_phase = settings.TURN_PHASE_MOVE
            return

        if current_turn_phase == settings.TURN_PHASE_MOVE:
            current_turn_phase = settings.TURN_PHASE_COMBAT
            process_combat_phase(current_faction)
            return
        
        if current_turn_phase == settings.TURN_PHASE_COMBAT:
            current_turn_phase = settings.TURN_PHASE_CONTROL
            process_control_phase(current_faction)
            return
        
        if current_turn_phase == settings.TURN_PHASE_CONTROL:
            process_victory_phase()


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
    combat_hexes = []
    current_combat_idx = 0
    loaded_combat_hex_idx = -1
    allied_forces = []
    opposing_forces = []
    conflicted_forces = []
    combat_result = None


    while running and game_phase == settings.PHASE_MAIN_GAME:
        dt = clock.tick(settings.FPS) / 1000.0
        
        # --- Bot Player Turn Automation ---
        if current_player.is_robot():
            if bot_just_started_turn:
                bot_just_started_turn = False
            else:
                if current_turn_phase == settings.TURN_PHASE_INCOME:
                    player.run_bot_muster_phase(current_faction, map_grid, advance_turn_phase)
                elif current_turn_phase == settings.TURN_PHASE_MOVE:
                    player.run_bot_move_phase(current_faction, map_grid, advance_turn_phase)
                elif current_turn_phase == settings.TURN_PHASE_COMBAT:
                    player.run_bot_combat_phase(current_faction, map_grid, advance_turn_phase)
                elif current_turn_phase == settings.TURN_PHASE_CONTROL:
                    player.run_bot_control_phase(current_faction, map_grid, advance_turn_phase)
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
        elif not current_player.is_robot() and not left_panel_collapsed:
            show_full_left_panel = True

        if show_full_left_panel:
            left_panel_rect = pygame.Rect(0, 0, settings.PANEL_WIDTH, settings.SCREEN_HEIGHT)
            map_viewport_rect = pygame.Rect(settings.PANEL_WIDTH, 0, settings.SCREEN_WIDTH - settings.PANEL_WIDTH, settings.SCREEN_HEIGHT)
        else:
            left_panel_rect = pygame.Rect(0, 0, 0, 0)
            map_viewport_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)

        # Populate forces lists for the active combat hex if needed
        if current_turn_phase == settings.TURN_PHASE_COMBAT and not current_player.is_robot():
            if combat_hexes and current_combat_idx < len(combat_hexes):
                if loaded_combat_hex_idx != current_combat_idx:
                    loaded_combat_hex_idx = current_combat_idx
                    allied_forces = []
                    opposing_forces = []
                    conflicted_forces = []
                    combat_result = None
                    
                    hex_coord = combat_hexes[current_combat_idx]
                    tile = map_grid.tiles.get(hex_coord)
                    if tile:
                        from factions import Faction
                        all_armies = map_grid.armies.get(hex_coord, [])
                        all_champs = map_grid.champions.get(hex_coord, [])
                        
                        opposed_factions = set()
                        for a in all_armies:
                            if current_faction.isOpposed(a.faction):
                                opposed_factions.add(a.faction)
                        for c in all_champs:
                            if current_faction.isOpposed(c.faction):
                                opposed_factions.add(c.faction)
                        if getattr(tile, 'is_stronghold', False) and tile.owner and isinstance(tile.owner, Faction) and current_faction.isOpposed(tile.owner):
                            opposed_factions.add(tile.owner)
                            
                        def get_alignment_group(fac):
                            if current_faction.isFullyAligned(fac) or current_faction.isStronglyAligned(fac):
                                return 'left'
                            for opp_fac in opposed_factions:
                                if opp_fac.isFullyAligned(fac) or opp_fac.isStronglyAligned(fac):
                                    return 'middle'
                            return 'right'
                            
                        # Group champions
                        for c in all_champs:
                            item = {
                                'type': 'champion',
                                'name': c.name,
                                'strength': c.strength,
                                'obj': c
                            }
                            grp = get_alignment_group(c.faction)
                            if grp == 'left':
                                allied_forces.append(item)
                            elif grp == 'middle':
                                opposing_forces.append(item)
                            else:
                                conflicted_forces.append(item)
                                
                        # Group armies
                        for a in all_armies:
                            item = {
                                'type': 'army',
                                'name': a.name,
                                'strength': a.strength,
                                'obj': a
                            }
                            grp = get_alignment_group(a.faction)
                            if grp == 'left':
                                allied_forces.append(item)
                            elif grp == 'middle':
                                opposing_forces.append(item)
                            else:
                                conflicted_forces.append(item)
                                
                        # Group stronghold if present
                        if getattr(tile, 'is_stronghold', False) and tile.owner and isinstance(tile.owner, Faction):
                            item = {
                                'type': 'stronghold',
                                'name': f"{tile.owner.race} Stronghold",
                                'strength': None,
                                'obj': tile,
                                'faction': tile.owner
                            }
                            grp = get_alignment_group(tile.owner)
                            if grp == 'left':
                                allied_forces.append(item)
                            elif grp == 'middle':
                                opposing_forces.append(item)
                            else:
                                conflicted_forces.append(item)

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
                
            if current_turn_phase == settings.TURN_PHASE_COMBAT and not current_player.is_robot():
                engage_btn_rect = pygame.Rect(340, 900, 240, 60)
                defer_btn_rect = pygame.Rect(620, 900, 240, 60)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if engage_btn_rect.collidepoint(mouse_x, mouse_y):
                        util.play_sound(filename=None, volume=0.4, pitch_hz=659.25, duration_ms=100)
                        combat_result = resolve_combat(allied_forces, opposing_forces, current_faction, map_grid)
                    elif defer_btn_rect.collidepoint(mouse_x, mouse_y):
                        util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                        if current_combat_idx < len(combat_hexes) - 1:
                            current_combat_idx += 1
                        else:
                            advance_turn_phase()
                    else:
                        # Check if any conflicted unit was clicked to bribe
                        if combat_hexes and current_combat_idx < len(combat_hexes):
                            max_items = max(len(allied_forces), len(opposing_forces), len(conflicted_forces))
                            
                            spacing = 70
                            avatar_size = 50
                            if max_items > 7:
                                spacing = 50
                                avatar_size = 35
                            elif max_items > 5:
                                spacing = 60
                                avatar_size = 42
                                
                            for idx, item in enumerate(conflicted_forces):
                                item_y = 200 + idx * spacing
                                item_rect = pygame.Rect(810, item_y, 340, avatar_size)
                                if item_rect.collidepoint(mouse_x, mouse_y):
                                    if current_faction.gold >= 1:
                                        current_faction.gold -= 1
                                        bribed_item = conflicted_forces.pop(idx)
                                        allied_forces.append(bribed_item)
                                        bribed_item['obj'].bribed_by = current_faction
                                        util.play_sound(filename=None, volume=0.5, pitch_hz=880.0, duration_ms=150)
                                        print(f"[Bribe Success] Bribed {bribed_item['name']} to {current_faction.race} side for 1 gold.")
                                    else:
                                        util.play_sound(filename=None, volume=0.3, pitch_hz=220.0, duration_ms=150)
                                        print(f"[Bribe Failure] Not enough gold to bribe {item['name']}.")
                                    break
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        util.play_sound(filename=None, volume=0.4, pitch_hz=523.25, duration_ms=100)
                        if current_combat_idx < len(combat_hexes) - 1:
                            current_combat_idx += 1
                        else:
                            advance_turn_phase()
                    elif event.key == pygame.K_ESCAPE:
                        running = False
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
                    if not current_player.is_robot():
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
                    if is_currently_collapsed and not current_player.is_robot():
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
                        elif not current_player.is_robot() and left_panel_rect.collidepoint(mouse_x, mouse_y):
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
                                            util.play_sound(filename=None, volume=0.4, pitch_hz=587.33, duration_ms=100)

                                            # Air Sword: if moves_remaining > 0 after the move,
                                            # keep the champion selected for a second step.
                                            if getattr(selected_champion, 'moves_remaining', 0) > 0:
                                                selected_champion.moves_remaining -= 1
                                                print(f"[Air Sword] {selected_champion.name} has 1 extra move step remaining — stay selected.")
                                                # Do NOT mark has_moved yet; champion stays selected
                                            else:
                                                selected_champion.has_moved = True  # Mark as moved this turn
                                                selected_champion = None
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

        if current_turn_phase == settings.TURN_PHASE_COMBAT and not current_player.is_robot():
            # 1. Render map centered and zoomed in on the right 1/4
            combat_map_rect = pygame.Rect(1200, 0, 400, 1000)
            
            # Retrieve active hex coordinates
            if combat_hexes and current_combat_idx < len(combat_hexes):
                hex_coord = combat_hexes[current_combat_idx]
                tile = map_grid.tiles.get(hex_coord)
                
                # Zoom in parameters temporarily
                zoom_w = 450
                zoom_h = 246
                orig_w = map_grid.hex_width
                orig_h = map_grid.hex_height
                
                map_grid.hex_width = zoom_w
                map_grid.hex_height = zoom_h
                
                orig_cx = map_grid.camera_x
                orig_cy = map_grid.camera_y
                
                map_grid.center_on_hex(hex_coord[0], hex_coord[1])
                
                # Draw map viewport, highlight combat hex in red
                map_grid.draw(screen, combat_map_rect, highlight_coords=[hex_coord], highlight_color=(255, 0, 0))
                
                # Restore original parameters
                map_grid.hex_width = orig_w
                map_grid.hex_height = orig_h
                map_grid.camera_x = orig_cx
                map_grid.camera_y = orig_cy
            else:
                tile = None
                hex_coord = (0, 0)
                
            # 2. Draw Left 3/4 Opaque Combat Panel
            opaque_combat_rect = pygame.Rect(0, 0, 1200, 1000)
            pygame.draw.rect(screen, (15, 18, 25), opaque_combat_rect)
            pygame.draw.line(screen, settings.COLOR_TEXT_MUTED, (1200, 0), (1200, 1000), 2)
            
            if tile:
                # Format hex name using helper
                def format_hex_name(name):
                    import re
                    # Add space around lowercase 'of' when followed by uppercase
                    name = re.sub(r'([a-zA-Z])of([A-Z])', r'\1 of \2', name)
                    # Add space before any uppercase letters
                    spaced = re.sub(r'(?<!^)(?=[A-Z])', ' ', name)
                    # Normalize spaces
                    spaced = re.sub(r'\s+', ' ', spaced)
                    return spaced.upper()
                    
                hex_name = format_hex_name(tile.terrain_type)
                
                # Render Hex name at top
                font_hex = util.get_font(36, bold=True)
                txt_hex = font_hex.render(hex_name, True, settings.COLOR_TEXT_PRIMARY)
                screen.blit(txt_hex, txt_hex.get_rect(center=(600, 35)))
                
                # Render Faction Treasury
                font_gold = util.get_font(20, bold=True)
                txt_gold = font_gold.render(f"{current_faction.race} Treasury: {current_faction.gold} Gold", True, settings.COLOR_NEON_GREEN)
                screen.blit(txt_gold, (50, 35))
                
                # Progress and coordinates
                font_sub = util.get_font(18)
                progress_str = f"COMBAT {current_combat_idx + 1} OF {len(combat_hexes)}"
                txt_progress = font_sub.render(progress_str, True, settings.COLOR_NEON_CYAN)
                screen.blit(txt_progress, txt_progress.get_rect(center=(600, 80)))
                
                # Divider line
                pygame.draw.line(screen, settings.COLOR_TEXT_MUTED, (100, 120), (1100, 120), 1)
                
                left_items = allied_forces
                middle_items = opposing_forces
                right_items = conflicted_forces
                    
                # Layout spacing calculation
                max_items = max(len(left_items), len(middle_items), len(right_items))
                spacing = 70
                avatar_size = 50
                if max_items > 7:
                    spacing = 50
                    avatar_size = 35
                elif max_items > 5:
                    spacing = 60
                    avatar_size = 42
                    
                # Vertical column dividers at x=400 and x=780
                pygame.draw.line(screen, settings.COLOR_TEXT_MUTED, (400, 155), (400, 880), 1)
                pygame.draw.line(screen, settings.COLOR_TEXT_MUTED, (780, 155), (780, 880), 1)
                
                # Setup fonts
                font_col_header = util.get_font(20, bold=True)
                font_item_name = util.get_font(15, bold=True)
                font_item_detail = util.get_font(13)
                         # Column 1: Faction Side (x=50)
                txt_col_left = font_col_header.render(f"{current_faction.race.upper()} SIDE", True, settings.COLOR_NEON_CYAN)
                screen.blit(txt_col_left, (50, 150))
                txt_str_left = font_item_name.render(f"Strength: {calculate_forces_strength(left_items)}", True, settings.COLOR_TEXT_PRIMARY)
                screen.blit(txt_str_left, (50, 175))

                # Combat result display — Allied column
                if combat_result is not None:
                    font_result = util.get_font(17, bold=True)
                    allied_outcome_color = settings.COLOR_NEON_GREEN if combat_result["outcome"] == "allied" else (settings.COLOR_NEON_PINK if combat_result["outcome"] == "opposed" else settings.COLOR_TEXT_MUTED)
                    txt_allied_result = font_result.render(
                        f"Roll: {combat_result['allied_roll']}  Total: {combat_result['allied_total']}",
                        True, allied_outcome_color
                    )
                    screen.blit(txt_allied_result, (50, 850))

                if not left_items:
                    txt_empty = font_item_detail.render("No units present", True, settings.COLOR_TEXT_MUTED)
                    screen.blit(txt_empty, (50, 200))
                else:
                    for idx, item in enumerate(left_items):
                        item_y = 200 + idx * spacing
                        if item['type'] == 'stronghold':
                            avatar = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
                            pygame.draw.circle(avatar, (255, 215, 0, 45), (avatar_size // 2, avatar_size // 2), avatar_size // 2 - 2, 0)
                            pygame.draw.circle(avatar, (255, 215, 0), (avatar_size // 2, avatar_size // 2), avatar_size // 2 - 2, 2)
                            font_sh = util.get_font(int(avatar_size * 0.24), bold=True)
                            txt_sh = font_sh.render("SH", True, (255, 215, 0))
                            avatar.blit(txt_sh, txt_sh.get_rect(center=(avatar_size // 2, avatar_size // 2)))
                        else:
                            avatar = item['obj'].get_surface(size=(avatar_size, avatar_size))
                        screen.blit(avatar, (50, item_y))
                        
                        txt_name = font_item_name.render(item['name'], True, settings.COLOR_TEXT_PRIMARY)
                        screen.blit(txt_name, (50 + avatar_size + 15, item_y + int(avatar_size * 0.08)))
                        if item['strength'] is not None:
                            txt_strength = font_item_detail.render(f"Strength: {item['strength']}", True, settings.COLOR_TEXT_MUTED)
                        else:
                            txt_strength = font_item_detail.render("Structure", True, (255, 215, 0))
                        screen.blit(txt_strength, (50 + avatar_size + 15, item_y + int(avatar_size * 0.5)))
                    
                # Column 2: Opposition Side (x=430)
                txt_col_mid = font_col_header.render("OPPOSITION SIDE", True, settings.COLOR_NEON_PINK)
                screen.blit(txt_col_mid, (530, 150))
                txt_str_mid = font_item_name.render(f"Strength: {calculate_forces_strength(middle_items)}", True, settings.COLOR_TEXT_PRIMARY)
                screen.blit(txt_str_mid, (530, 175))

                # Combat result display — Opposition column
                if combat_result is not None:
                    font_result = util.get_font(17, bold=True)
                    opposed_outcome_color = settings.COLOR_NEON_GREEN if combat_result["outcome"] == "opposed" else (settings.COLOR_NEON_PINK if combat_result["outcome"] == "allied" else settings.COLOR_TEXT_MUTED)
                    txt_opposed_result = font_result.render(
                        f"Roll: {combat_result['opposed_roll']}  Total: {combat_result['opposed_total']}",
                        True, opposed_outcome_color
                    )
                    screen.blit(txt_opposed_result, (530, 850))

                if not middle_items:
                    txt_empty = font_item_detail.render("No units present", True, settings.COLOR_TEXT_MUTED)
                    screen.blit(txt_empty, (430, 200))
                else:
                    for idx, item in enumerate(middle_items):
                        item_y = 200 + idx * spacing
                        if item['type'] == 'stronghold':
                            avatar = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
                            pygame.draw.circle(avatar, (255, 215, 0, 45), (avatar_size // 2, avatar_size // 2), avatar_size // 2 - 2, 0)
                            pygame.draw.circle(avatar, (255, 215, 0), (avatar_size // 2, avatar_size // 2), avatar_size // 2 - 2, 2)
                            font_sh = util.get_font(int(avatar_size * 0.24), bold=True)
                            txt_sh = font_sh.render("SH", True, (255, 215, 0))
                            avatar.blit(txt_sh, txt_sh.get_rect(center=(avatar_size // 2, avatar_size // 2)))
                        else:
                            avatar = item['obj'].get_surface(size=(avatar_size, avatar_size))
                        screen.blit(avatar, (430, item_y))
                        
                        txt_name = font_item_name.render(item['name'], True, settings.COLOR_TEXT_PRIMARY)
                        screen.blit(txt_name, (430 + avatar_size + 15, item_y + int(avatar_size * 0.08)))
                        if item['strength'] is not None:
                            txt_strength = font_item_detail.render(f"Strength: {item['strength']}", True, settings.COLOR_TEXT_MUTED)
                        else:
                            txt_strength = font_item_detail.render("Structure", True, (255, 215, 0))
                        screen.blit(txt_strength, (430 + avatar_size + 15, item_y + int(avatar_size * 0.5)))
 
                # Column 3: Conflicted Side (x=810)
                txt_col_right = font_col_header.render("CONFLICTED", True, settings.COLOR_TEXT_MUTED)
                screen.blit(txt_col_right, (810, 150))
                txt_str_right = font_item_name.render(f"Strength: {calculate_forces_strength(right_items)}", True, settings.COLOR_TEXT_PRIMARY)
                screen.blit(txt_str_right, (810, 175))
                
                if not right_items:
                    txt_empty = font_item_detail.render("No units present", True, settings.COLOR_TEXT_MUTED)
                    screen.blit(txt_empty, (810, 200))
                else:
                    for idx, item in enumerate(right_items):
                        item_y = 200 + idx * spacing
                        if item['type'] == 'stronghold':
                            avatar = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
                            pygame.draw.circle(avatar, (255, 215, 0, 45), (avatar_size // 2, avatar_size // 2), avatar_size // 2 - 2, 0)
                            pygame.draw.circle(avatar, (255, 215, 0), (avatar_size // 2, avatar_size // 2), avatar_size // 2 - 2, 2)
                            font_sh = util.get_font(int(avatar_size * 0.24), bold=True)
                            txt_sh = font_sh.render("SH", True, (255, 215, 0))
                            avatar.blit(txt_sh, txt_sh.get_rect(center=(avatar_size // 2, avatar_size // 2)))
                        else:
                            avatar = item['obj'].get_surface(size=(avatar_size, avatar_size))
                        screen.blit(avatar, (810, item_y))
                        
                        txt_name = font_item_name.render(item['name'], True, settings.COLOR_TEXT_PRIMARY)
                        screen.blit(txt_name, (810 + avatar_size + 15, item_y + int(avatar_size * 0.08)))
                        if item['strength'] is not None:
                            txt_strength = font_item_detail.render(f"Strength: {item['strength']}", True, settings.COLOR_TEXT_MUTED)
                        else:
                            txt_strength = font_item_detail.render("Structure", True, (255, 215, 0))
                        screen.blit(txt_strength, (810 + avatar_size + 15, item_y + int(avatar_size * 0.5)))
                    
            # Draw Engage & Defer/Continue buttons
            engage_btn_rect = pygame.Rect(340, 900, 240, 60)
            defer_btn_rect = pygame.Rect(620, 900, 240, 60)

            font_btn = util.get_font(20, bold=True)

            # Only show Engage button before combat has been resolved
            if combat_result is None:
                is_hover_engage = engage_btn_rect.collidepoint(mouse_x, mouse_y)
                if is_hover_engage:
                    pygame.draw.rect(screen, settings.COLOR_NEON_GREEN, engage_btn_rect, border_radius=10)
                    text_color_engage = (11, 14, 20)
                else:
                    pygame.draw.rect(screen, (20, 24, 33), engage_btn_rect, border_radius=10)
                    pygame.draw.rect(screen, settings.COLOR_NEON_GREEN, engage_btn_rect, width=2, border_radius=10)
                    text_color_engage = settings.COLOR_NEON_GREEN
                txt_engage = font_btn.render("ENGAGE", True, text_color_engage)
                screen.blit(txt_engage, txt_engage.get_rect(center=engage_btn_rect.center))

            # Defer button — relabeled CONTINUE after combat resolves
            is_hover_defer = defer_btn_rect.collidepoint(mouse_x, mouse_y)
            if is_hover_defer:
                pygame.draw.rect(screen, settings.COLOR_NEON_PINK, defer_btn_rect, border_radius=10)
                text_color_defer = (11, 14, 20)
            else:
                pygame.draw.rect(screen, (20, 24, 33), defer_btn_rect, border_radius=10)
                pygame.draw.rect(screen, settings.COLOR_NEON_PINK, defer_btn_rect, width=2, border_radius=10)
                text_color_defer = settings.COLOR_NEON_PINK

            defer_label = "CONTINUE" if combat_result is not None else "DEFER"
            txt_defer = font_btn.render(defer_label, True, text_color_defer)
            screen.blit(txt_defer, txt_defer.get_rect(center=defer_btn_rect.center))
            
            pygame.display.flip()
            continue
        
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
            art_tooltip = draw_left_champion_statistics_panel(screen, selected_champion, left_panel_rect, map_grid, mouse_x, mouse_y)
            if art_tooltip is not None:
                tooltip_to_draw = art_tooltip
            
        # 2.1 Render Left Statistics Panel for selected Army (only if not in movement phase)
        elif selected_army is not None and current_turn_phase != settings.TURN_PHASE_MOVE:
            draw_left_army_statistics_panel(screen, selected_army, left_panel_rect, map_grid, mouse_x, mouse_y)

        # 2.2 Render Left Faction Turn Phase Panel / tab for active turn
        elif not current_player.is_robot():
            if left_panel_collapsed:
                draw_collapsed_tab(screen, current_faction, current_turn_phase, map_grid, mouse_x, mouse_y)
            else:
                draw_left_phase_panel(screen, left_panel_rect, current_faction, current_turn_phase, map_grid, mouse_x, mouse_y, is_mustering, secret_faction=human_player_obj.faction)
        elif current_player.is_robot():
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
