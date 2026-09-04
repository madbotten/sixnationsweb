"""
Six Nations -- Main Entry Point
Phase 4: human drag-and-drop UI, bot random move, turn management.
"""

import sys
import os
import random
import asyncio
import pygame

import settings
import util
import bot as bot_ai
import splash as splash_mod
import moves as moves_mod
from bot import BotMemory
from map import MapGrid
from factions import NATIONS, NATIONS_BY_NAME
from player import Player
from diplomacy_panel import DiplomacyPanel, DiplomacyAction

# Evolution module — optional, only needed for "Play vs Evolved Bot"
try:
    from evolution import load_top_configs, BotConfig, EvolvableBot, BotGoals
    _HAS_EVOLUTION = True
except ImportError:
    _HAS_EVOLUTION = False


# ---------------------------------------------------------------------------
# Network layer — WebSocket send/receive via JS bridge (Pygbag) or stubs
# ---------------------------------------------------------------------------
game_mode_global = 'vs_bot'       # set at runtime; 'vs_bot' | 'vs_human' | 'network'
my_role          = 'player1'      # 'player1' or 'player2'

_incoming_moves = []              # queue of move dicts received from opponent

def _is_wasm():
    """True when running inside Pygbag / Emscripten."""
    try:
        import sys
        return sys.platform == 'emscripten'
    except Exception:
        return False

def _setup_network_receive():
    """Install a JS callback to push incoming WebSocket messages into _incoming_moves."""
    if not _is_wasm():
        return
    import platform
    js = platform.window
    # JS function: when a message arrives on gameSocket, push it onto Python's queue
    js.eval("""
        if (window.gameSocket) {
            window.gameSocket.addEventListener('message', function(ev) {
                var msg = JSON.parse(ev.data);
                if (msg.type && msg.type !== 'START' && msg.type !== 'WAITING'
                    && msg.type !== 'ERROR' && msg.type !== 'DISCONNECT') {
                    // It's a game move — push to Python queue
                    if (!window._pyMoveQueue) window._pyMoveQueue = [];
                    window._pyMoveQueue.push(ev.data);
                }
            });
        }
    """)

def on_local_move_made(move_data: dict):
    """Send the serialized move to the opponent via WebSocket (network mode only)."""
    if game_mode_global != 'network':
        return
    if not _is_wasm():
        return
    import platform, json
    js = platform.window
    payload = json.dumps(move_data)
    js.eval(f"if (window.gameSocket) window.gameSocket.send('{payload}');")

def on_network_move_received():
    """Pop and return the next incoming move dict, or None."""
    if _is_wasm():
        import platform, json
        js = platform.window
        # Pull any messages JS has queued
        raw = js.eval("(window._pyMoveQueue && window._pyMoveQueue.length) ? window._pyMoveQueue.shift() : ''")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
    # Also check the Python-side queue (for desktop testing)
    if _incoming_moves:
        return _incoming_moves.pop(0)
    return None


# ---------------------------------------------------------------------------
# State machine constants
# ---------------------------------------------------------------------------

STATE_HUMAN_TURN        = 0
STATE_BOT_THINKING      = 1
STATE_GAME_OVER         = 2
STATE_BOT_PRE_FLASH     = 3
STATE_BOT_POST_FLASH    = 4
STATE_SPLASH            = 5   # pre-game splash
STATE_INSTRUCTIONS      = 6   # scrollable rules screen
STATE_WAITING_OPPONENT  = 7   # network mode: waiting for remote player's move

BOT_THINK_MS = 900   # ms of "thinking" delay before bot acts
BOT_FLASH_MS = 500   # ms of pre/post flash animation

GAME_RESULT_NONE              = 0
GAME_RESULT_WIN_SCORE         = 1   # Human won: 2 target enemy sovereigns destroyed
GAME_RESULT_WIN_OPPONENT_DEAD = 2   # Human won: bot's secret sovereign destroyed
GAME_RESULT_LOSS_SOVEREIGN    = 3   # Human lost: own secret sovereign destroyed
GAME_RESULT_LOSS_BOT_SCORE    = 4   # Human lost: bot destroyed 2 target sovereigns
GAME_RESULT_TIE              = 5   # Both players meet win condition simultaneously

# Unit icon dimensions (must match map.py draw constants)
UNIT_SIZE    = 40
UNIT_RADIUS  = UNIT_SIZE // 2
UNIT_SPACING = 47


# ---------------------------------------------------------------------------
# Asset loading
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Game state helpers
# ---------------------------------------------------------------------------

def get_eligible_nations(player, global_cooldown_name, all_nations):
    """Nations the current player is allowed to move this turn."""
    return [
        n for n in all_nations
        if not player.nation_on_cooldown(n)
        and (global_cooldown_name is None or n.color_name != global_cooldown_name)
        and not n.is_ghost
    ]


def get_unit_at_screen(grid, mx, my):
    """
    Return (unit, unit_type_str) for the unit icon the mouse is over,
    or (None, None) if none.
    unit_type_str is one of 'sovereign', 'champion', 'knight', 'army'.
    """
    q, r = grid.screen_to_axial(mx, my)
    if not grid.get_tile(q, r):
        return None, None

    cx, cy = grid.screen_pos(q, r)
    # Same ordering/layout as map.py draw()
    units_here = (
        [('sovereign', u) for u in grid.sovereigns.get((q, r), [])]
        + [('champion', u) for u in grid.champions.get((q, r), [])]
        + [('knight',   u) for u in grid.knights.get((q, r), [])]
        + [('army',     u) for u in grid.armies.get((q, r), [])]
    )
    n = len(units_here)
    for i, (utype, unit) in enumerate(units_here):
        ux = cx + (i - (n - 1) / 2.0) * UNIT_SPACING
        if (mx - ux) ** 2 + (my - cy) ** 2 <= UNIT_RADIUS ** 2:
            return unit, utype
    return None, None


# (bot AI logic lives in bot.py)


# ---------------------------------------------------------------------------
# UI drawing helpers
# ---------------------------------------------------------------------------

def draw_drag_ghost(screen, unit_type, nation_color, mx, my):
    """Draw a semi-transparent unit symbol at the current mouse position."""
    size   = UNIT_SIZE + 4
    ghost  = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    s      = int(UNIT_SIZE * 0.42)
    fa     = 210   # fill alpha

    sprite_name = {'army': 'army.png',
                   'knight': 'knight.png',
                   'champion': 'champion.png',
                   'sovereign': 'sovereign.png'}.get(unit_type)
    if sprite_name is not None:
        scale = 3.2 if unit_type in ('champion', 'knight') else 2.0
        icon_h = int(s * scale)
        template = util.load_image(sprite_name, alpha=True)
        if template is not None:
            icon_w = int(icon_h * template.get_width() / template.get_height())
            sprite = util.load_tinted_sprite(sprite_name, nation_color,
                                             icon_w, icon_h)
            if sprite is not None:
                tmp = sprite.copy()
                tmp.set_alpha(fa)
                ghost.blit(tmp, tmp.get_rect(center=(cx, cy)))

    screen.blit(ghost, (mx - cx, my - cy))


def draw_top_bar(screen, font_large, font_small, active_player,
                 current_player, turn_number, game_state, game_mode='vs_bot'):
    bar = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.TOP_BAR_HEIGHT)
    pygame.draw.rect(screen, settings.COLOR_TOP_BAR, bar)
    pygame.draw.line(screen, settings.COLOR_PANEL_BORDER,
                     (0, settings.TOP_BAR_HEIGHT - 1),
                     (settings.SCREEN_WIDTH, settings.TOP_BAR_HEIGHT - 1), 1)

    # Left accent: thin nation-colour stripe so the bar isn't empty
    nc = active_player.secret_nation.color_rgb
    pygame.draw.rect(screen, nc, (0, 0, 4, settings.TOP_BAR_HEIGHT))

    if game_state == STATE_GAME_OVER:
        centre_text = "GAME OVER"
        centre_col  = settings.COLOR_TEXT_MUTED
    elif game_state == STATE_BOT_THINKING:
        centre_text = f"TURN {turn_number}  —  BOT IS THINKING…"
        centre_col  = settings.NATION_COLORS['Galland']
    elif game_state == STATE_WAITING_OPPONENT:
        centre_text = f"TURN {turn_number}  —  WAITING FOR OPPONENT…"
        centre_col  = settings.NATION_COLORS['Beldrin']
    else:
        if game_mode == 'vs_human':
            whose = current_player.player_id.upper() + "'S TURN"
        elif game_mode == 'network':
            whose = "YOUR TURN"
        else:
            whose = "YOUR TURN" if not current_player.is_bot else "BOT'S TURN"
        centre_text = f"TURN {turn_number}  —  {whose}"
        centre_col  = settings.COLOR_TEXT_PRIMARY

    centre_surf = font_large.render(centre_text, True, centre_col)
    screen.blit(centre_surf, centre_surf.get_rect(
        center=(settings.SCREEN_WIDTH // 2, settings.TOP_BAR_HEIGHT // 2)))


def draw_predictions_panel(screen, font_small, player):
    """Floating upper-left panel showing the human player's PREVAIL/DEFEAT goals.

    Mirrors the style of the diplomacy panel on the upper-right.
    Each entry shows: army sprite | nation name | point value (right-aligned).
    """
    MARGIN   = 10
    PADDING  = 12
    PANEL_W  = 300   # wider to fit pts column
    ITEM_H   = 28    # height per nation row
    SECT_H   = 22    # section label height
    SECT_GAP = 8     # gap between PREVAIL and DEFEAT sections
    HDR_H    = 22    # "GOALS" header height

    total_h = (PADDING
               + HDR_H + 6
               + SECT_H + 3 * ITEM_H
               + SECT_GAP
               + SECT_H + 3 * ITEM_H
               + PADDING)

    x = MARGIN
    y = MARGIN

    panel_rect = pygame.Rect(x, y, PANEL_W, total_h)
    pygame.draw.rect(screen, settings.COLOR_PANEL,        panel_rect, border_radius=8)
    pygame.draw.rect(screen, settings.COLOR_PANEL_BORDER, panel_rect, 1, border_radius=8)

    cy = y + PADDING

    # Header row: "GOALS" label + secret-nation colour dot
    nc  = player.secret_nation.color_rgb
    hdr = font_small.render("SECRET GOALS", True, settings.COLOR_TEXT_MUTED)
    screen.blit(hdr, (x + PADDING, cy))
    pygame.draw.circle(screen, nc,
                       (x + PANEL_W - PADDING - 7, cy + hdr.get_height() // 2), 6)
    cy += HDR_H + 6

    # Thin divider
    pygame.draw.line(screen, settings.COLOR_PANEL_BORDER,
                     (x + PADDING, cy), (x + PANEL_W - PADDING, cy), 1)
    cy += 4

    _WEIGHTS = (3, 2, 1)

    def _draw_section(label, label_color, nations):
        nonlocal cy
        lbl_surf = font_small.render(label, True, label_color)
        screen.blit(lbl_surf, (x + PADDING, cy))
        cy += SECT_H

        # Precompute army sprite size from template aspect ratio
        template = util.load_image('army.png', alpha=True)
        sprite_h = 18
        sprite_w = (max(1, int(sprite_h * template.get_width() / template.get_height()))
                    if template else sprite_h)

        for slot_i, nation in enumerate(nations):
            c = nation.color_rgb

            # Army sprite
            sprite = util.load_tinted_sprite('army.png', c, sprite_w, sprite_h)
            icon_x = x + PADDING
            if sprite:
                screen.blit(sprite, sprite.get_rect(
                    midleft=(icon_x, cy + ITEM_H // 2)))
            else:
                pygame.draw.rect(screen, c,
                                 (icon_x, cy + 5, 14, ITEM_H - 10), border_radius=3)

            name_surf = font_small.render(nation.color_name, True, c)
            screen.blit(name_surf, name_surf.get_rect(
                midleft=(icon_x + sprite_w + 8, cy + ITEM_H // 2)))

            # Point value right-aligned
            pts = _WEIGHTS[slot_i] if slot_i < len(_WEIGHTS) else 0
            pts_surf = font_small.render(f"{pts}pt", True, (75, 92, 130))
            screen.blit(pts_surf, pts_surf.get_rect(
                midright=(x + PANEL_W - PADDING, cy + ITEM_H // 2)))

            cy += ITEM_H

    _draw_section("PREVAIL", (52, 210, 96),  player.prevail_picks)
    cy += SECT_GAP
    _draw_section("DEFEAT",  (220, 65, 55),  player.defeat_picks)


def draw_cooldown_panel(screen, font_small, players, global_cooldown_name):
    """Show each player's cooldown nations; global cooldown highlighted."""
    margin = 10
    x = margin
    y = settings.SCREEN_HEIGHT - settings.COOLDOWN_PANEL_H - margin
    w = settings.COOLDOWN_PANEL_W
    h = settings.COOLDOWN_PANEL_H

    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, settings.COLOR_PANEL, rect, border_radius=8)
    pygame.draw.rect(screen, settings.COLOR_PANEL_BORDER, rect, 1, border_radius=8)

    hdr = font_small.render("COOLDOWNS", True, settings.COLOR_TEXT_MUTED)
    screen.blit(hdr, (x + 12, y + 10))

    def _draw_row(label_text, player, row_y):
        lbl = font_small.render(label_text, True, settings.COLOR_TEXT_MUTED)
        screen.blit(lbl, (x + 12, row_y))
        for i, name in enumerate(player.cooldown):
            col = settings.NATION_COLORS[name]
            bx  = x + 55 + i * 36
            pygame.draw.rect(screen, col, (bx, row_y - 2, 28, 20), border_radius=3)
            if name == global_cooldown_name:
                pygame.draw.rect(screen, (255, 255, 255),
                                 (bx, row_y - 2, 28, 20), 2, border_radius=3)

    _draw_row("You:", players[0], y + 34)
    _draw_row("Bot:", players[1], y + 64)

    if global_cooldown_name is not None:
        glbl  = font_small.render(f"Global block: {global_cooldown_name}", True, (90, 105, 140))
        screen.blit(glbl, (x + 12, y + 94))

    leg = font_small.render("(white border = global block)", True, (70, 80, 110))
    screen.blit(leg, (x + 12, y + h - 24))


def draw_error(screen, font_small, message, alpha):
    if not message or alpha <= 0:
        return
    surf = font_small.render(message, True, (255, 100, 80))
    surf.set_alpha(int(alpha))
    screen.blit(surf, surf.get_rect(
        center=(settings.SCREEN_WIDTH // 2, settings.TOP_BAR_HEIGHT + 30)))



def draw_score_screen(screen, player1, player2, nation_list):
    """Full-screen score reveal shown when 3 sovereigns have been destroyed.

    Displays both players' PREVAIL/DEFEAT predictions with correct/wrong marks,
    sorted by score descending.  Press SPACE to play again, ESC to quit.
    """
    W, H = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT

    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((4, 6, 14, 248))
    screen.blit(overlay, (0, 0))

    fnt_hdr   = util.get_font(52, bold=True)
    fnt_rank  = util.get_font(36, bold=True)
    fnt_name  = util.get_font(28, bold=True)
    fnt_label = util.get_font(22, bold=True)
    fnt_pick  = util.get_font(22)
    fnt_hint  = util.get_font(18)
    SHADOW    = (0, 0, 0)

    # Header
    hdr_text = "GAME OVER  --  FINAL SCORES"
    hdr_surf = fnt_hdr.render(hdr_text, True, (210, 222, 255))
    hdr_sh   = fnt_hdr.render(hdr_text, True, SHADOW)
    screen.blit(hdr_sh,  hdr_sh.get_rect(centerx=W // 2 + 2, y=42))
    screen.blit(hdr_surf, hdr_surf.get_rect(centerx=W // 2,   y=40))
    pygame.draw.line(screen, (50, 65, 110), (80, 108), (W - 80, 108), 1)

    # Score entries sorted by score descending
    p1_score = player1.compute_score()
    p2_score = player2.compute_score()
    entries = sorted(
        [("Player 1", player1, p1_score),
         ("Bot",      player2, p2_score)],
        key=lambda x: -x[2])

    ROW_X = 120
    y = 128

    for rank_i, (label, player, score) in enumerate(entries):
        nc = player.secret_nation.color_rgb

        # -- Player header row ------------------------------------------------
        rank_surf  = fnt_rank.render(f"#{rank_i + 1}", True, (190, 206, 255))
        screen.blit(rank_surf, (ROW_X, y))

        full_label = f"{label}  |  secret: {player.secret_nation.color_name}"
        name_surf  = fnt_name.render(full_label, True, nc)
        screen.blit(name_surf,
                    name_surf.get_rect(midleft=(ROW_X + 72, y + fnt_rank.get_height() // 2)))

        score_col  = ((72, 228, 132) if score >= 8
                      else (228, 210, 65) if score >= 4
                      else (200, 80, 65))
        score_surf = fnt_rank.render(f"{score} / 12 pts", True, score_col)
        screen.blit(score_surf, score_surf.get_rect(right=W - ROW_X, y=y))

        y += fnt_rank.get_height() + 10

        # -- PREVAIL row -------------------------------------------------------
        prev_lbl = fnt_label.render("PREVAIL:", True, (52, 210, 96))
        screen.blit(prev_lbl, (ROW_X + 36, y + 4))
        px = ROW_X + 36 + prev_lbl.get_width() + 24

        for slot_i, nation in enumerate(player.prevail_picks):
            weight   = (3, 2, 1)[slot_i]
            nc2      = nation.color_rgb
            survived = not nation.is_ghost
            chk_col  = (60, 220, 90) if survived else (220, 60, 60)
            pts_str  = f"+{weight}" if survived else "+0"
            label    = f"{nation.color_name}  {pts_str}"
            n_surf   = fnt_pick.render(nation.color_name, True, nc2)
            p_surf   = fnt_label.render(pts_str, True, chk_col)
            screen.blit(n_surf, (px, y + 4))
            screen.blit(p_surf, (px + n_surf.get_width() + 6, y + 2))
            px += n_surf.get_width() + p_surf.get_width() + 36

        y += fnt_label.get_height() + 8

        # -- DEFEAT row --------------------------------------------------------
        def_lbl = fnt_label.render("DEFEAT: ", True, (220, 65, 55))
        screen.blit(def_lbl, (ROW_X + 36, y + 4))
        dx = ROW_X + 36 + def_lbl.get_width() + 24

        for slot_i, nation in enumerate(player.defeat_picks):
            weight   = (3, 2, 1)[slot_i]
            nc2      = nation.color_rgb
            defeated = nation.is_ghost
            chk_col  = (60, 220, 90) if defeated else (220, 60, 60)
            pts_str  = f"+{weight}" if defeated else "+0"
            n_surf   = fnt_pick.render(nation.color_name, True, nc2)
            p_surf   = fnt_label.render(pts_str, True, chk_col)
            screen.blit(n_surf, (dx, y + 4))
            screen.blit(p_surf, (dx + n_surf.get_width() + 6, y + 2))
            dx += n_surf.get_width() + p_surf.get_width() + 36

        y += fnt_label.get_height() + 26
        pygame.draw.line(screen, (35, 44, 70), (ROW_X, y), (W - ROW_X, y), 1)
        y += 22

    # Footer
    hint_surf = fnt_hint.render(
        "Press SPACE to play again   |   Press ESC to quit",
        True, (125, 138, 185))
    screen.blit(hint_surf, hint_surf.get_rect(centerx=W // 2, y=H - 46))




# ---------------------------------------------------------------------------
# Recruit / Promote sidebar buttons
# ---------------------------------------------------------------------------

# Direction (dq, dr) pointing outward from map center for each nation's corner
_CORNER_OUTWARD = {
    'Yilerond':  ( 0, -1),
    'Galland':   ( 1, -1),
    'Beldrin':   ( 1,  0),
    'Crestmoor': ( 0,  1),
    'Malkor':    (-1,  1),
    'Ravengard': (-1,  0),
}

def compute_sidebar_buttons(grid, eligible_nations, turn_number=None):
    """
    Return a list of button dicts for recruit/promote actions.
    Each dict: {type, nation, pos:(x,y), size, key:(type,ring_idx)}
    Buttons are placed one hex outward from each nation's corner hex,
    clamped so they always remain inside the visible screen area.
    """
    buttons  = []
    ICON_SIZE = 29
    GAP       = 36   # horizontal gap between two icons for the same nation
    MARGIN    = ICON_SIZE  # minimum distance from screen edges
    eff_turn  = turn_number if turn_number is not None else getattr(grid, 'turn_number', 1)

    for nation in eligible_nations:
        ri = nation.color_name
        cq, cr = grid.NATION_CORNERS[ri]
        dq, dr = _CORNER_OUTWARD[ri]
        # Phantom hex one step outward
        px, py = grid.screen_pos(cq + dq, cr + dr)

        # Clamp so buttons never leave the visible area
        px = max(MARGIN, min(settings.SCREEN_WIDTH  - MARGIN, px))
        py = max(settings.TOP_BAR_HEIGHT + MARGIN,
                 min(settings.SCREEN_HEIGHT - MARGIN, py))

        has_recruitable_hex = bool(grid.get_recruitable_hexes(nation))
        cooldown_elapsed = grid.is_recruit_cooldown_elapsed(nation, eff_turn)
        can_recruit = has_recruitable_hex and cooldown_elapsed

        can_promote = bool(grid.get_promote_hexes(nation))
        can_promote_knight = bool(grid.get_promote_knight_hexes(nation))

        icons = []
        if can_recruit:
            icons.append('recruit')
        if can_promote:
            icons.append('promote')
        if can_promote_knight:
            icons.append('promote_knight')

        for i, icon_type in enumerate(icons):
            offset_x = (i - (len(icons) - 1) / 2.0) * GAP
            bx = int(max(MARGIN, min(settings.SCREEN_WIDTH - MARGIN, px + offset_x)))
            btn_size = UNIT_SIZE if icon_type in ('promote_knight', 'recruit') else ICON_SIZE
            buttons.append({
                'type':   icon_type,
                'nation': nation,
                'pos':    (bx, int(py)),
                'size':   btn_size,
                'key':    (icon_type, ri),
            })

    return buttons


def draw_sidebar_buttons(screen, grid, buttons, action_pending, pending_nation, font_tiny,
                         drag_knight_nation=None, drag_recruit_nation=None):
    """Draw recruit/promote buttons outside each nation's corner hex."""
    w, h = grid.hex_width, grid.hex_height

    for btn in buttons:
        bx, by   = btn['pos']
        size     = btn['size']
        nation   = btn['nation']
        btype    = btn['type']
        c        = nation.color_rgb
        radius   = size // 2

        if btype == 'recruit':
            # Instead of the little circle button, show an ordinary army icon there
            if drag_recruit_nation is not None and drag_recruit_nation.color_name == nation.color_name:
                continue
            grid.draw_unit_icon(screen, bx, by, 'army', c, size=UNIT_SIZE)
            continue

        if btype == 'promote_knight':
            # Instead of the little circle button, show an ordinary knight icon there
            if drag_knight_nation is not None and drag_knight_nation.color_name == nation.color_name:
                continue
            grid.draw_unit_icon(screen, bx, by, 'knight', c, size=UNIT_SIZE)
            continue

        active = (action_pending == btype
                  and pending_nation is not None
                  and pending_nation.color_name == nation.color_name)

        # Coloured circular background
        bg_col  = tuple(min(255, int(v * 0.7 + 30)) for v in c)
        pygame.draw.circle(screen, bg_col, (bx, by), radius)

        # Border: bright white when active, subtle otherwise
        border_col   = (255, 255, 255) if active else (180, 190, 210)
        border_width = 3 if active else 1
        pygame.draw.circle(screen, border_col, (bx, by), radius, border_width)

        # Symbol: champion (sword) in white
        s = int(size * 0.35)
        sym_col = (255, 255, 255)

        if btype == 'promote':
            icon_h = int(s * 2.0)
            sprite_name = 'champion.png'
            label = "PRO"
        else:
            sprite_name = None
            label = ""

        if sprite_name:
            template = util.load_image(sprite_name, alpha=True)
            if template is not None:
                icon_w = int(icon_h * template.get_width() / template.get_height())
                sprite = util.load_tinted_sprite(sprite_name, sym_col, icon_w, icon_h)
                if sprite is not None:
                    screen.blit(sprite, sprite.get_rect(center=(bx, by)))

        # Small label below
        lbl = font_tiny.render(label, True,
                               (255, 255, 255) if active else (160, 170, 195))
        screen.blit(lbl, lbl.get_rect(midtop=(bx, by + radius + 2)))


def get_sidebar_button_at(buttons, mx, my):
    """Return the button dict the mouse is over, or None."""
    for btn in buttons:
        bx, by = btn['pos']
        r = btn['size'] // 2
        if (mx - bx) ** 2 + (my - by) ** 2 <= r * r:
            return btn
    return None


def _clear_action(state):
    """Return a cleared action-pending state tuple."""
    return None, None, set(), set()

def check_trigger_game_end(grid, nation_list) -> bool:
    """
    Run ghost detection then check the new victory trigger:
    game ends when 3 or more sovereigns have been destroyed.
    """
    grid.check_ghost_nations(nation_list)
    return grid.count_ghost_nations(nation_list) >= 3


def _apply_diplomacy_move(grid, panel, action: DiplomacyAction, all_nations):
    """
    Apply a diplomacy move between two nations:
    - Renew: re-lock only, stance unchanged.
    - Declare war: set_enemy, lock pair (cooldown), and reconcile.
    - Declare ally: set_ally, lock pair (cooldown), and reconcile.
    - End war/ally: set_neutral, unlock pair (NO cooldown), and reconcile.
    """
    box, flag = action.box_nation, action.flag_nation
    if action.from_zone == action.to_zone:       # renew: same zone, re-lock only
        panel.lock_pair(flag, box)
        return
    elif action.to_zone == 'war':
        flag.set_enemy(box)
        panel.lock_pair(flag, box)
        new_stance = 'enemy'
    elif action.to_zone == 'ally':
        flag.set_ally(box)
        panel.lock_pair(flag, box)
        new_stance = 'ally'
    else:                                        # to_zone resolved to own box -> neutral
        flag.set_neutral(box)
        panel.unlock_pair(flag, box)             # No cooldown when returning home to neutral!
        new_stance = 'neutral'
    try:
        from map import reconcile_stance_change
        events = reconcile_stance_change(grid, flag, box, new_stance, all_nations)
        for ev in events:
            print(f"[Diplomacy Reconciliation] {ev}")
    except (ImportError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    global game_mode_global
    try:
        random.seed(os.urandom(16))
    except Exception:
        import time
        random.seed(int(time.time() * 1000))
    pygame.init()
    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    pygame.display.set_caption(settings.WINDOW_TITLE)
    clock = pygame.time.Clock()

    font_large = util.get_font(22, bold=True)
    font_small = util.get_font(14)

    # --- Game state ----------------------------------------------------------
    nation_list  = list(NATIONS)
    dipl_panel   = DiplomacyPanel(nation_list)

    # Player objects — created after splash screen selects game_mode.
    # Initialise with vs_bot defaults so the splash can show the secret nation.
    p1_nation = random.choice(nation_list)
    p2_nation = random.choice([n for n in nation_list if n is not p1_nation])

    player1 = Player(secret_nation=p1_nation, is_bot=False, player_id='player1')
    player2 = Player(secret_nation=p2_nation, is_bot=True,  player_id='player2')
    players = [player1, player2]

    current_player_idx  = 0
    global_cooldown_name = None
    turn_number         = 1
    grid.turn_number    = turn_number
    game_state          = STATE_SPLASH
    game_mode           = 'vs_bot'       # set by splash button click
    game_result         = GAME_RESULT_NONE
    bot_think_timer     = 0

    # Evolved bot config — loaded if bot_configs_stable.json or bot_configs.json exists
    evolved_bot_config  = None           # BotConfig or None
    evolved_bot_weights = None           # dict or None
    _stable_path = os.path.join(os.path.dirname(__file__), 'bot_configs_stable.json')
    _default_path = os.path.join(os.path.dirname(__file__), 'bot_configs.json')
    _evolved_configs_path = _stable_path if os.path.exists(_stable_path) else _default_path
    has_evolved_configs = (_HAS_EVOLUTION and os.path.exists(_evolved_configs_path))

    error_message = ""
    error_alpha   = 0.0

    grid = MapGrid()
    grid.generate_map()

    # Drag state (game board)
    drag_unit           = None
    drag_unit_type      = None
    drag_knight_nation  = None
    drag_recruit_nation = None
    highlight_move      = set()
    highlight_attack    = set()
    drag_mouse_pos      = (0, 0)

    # Splash prediction picks and drag state
    prevail_picks       = []    # list[Nation], max 3
    defeat_picks        = []    # list[Nation], max 3
    drag_splash_nation  = None  # Nation being dragged on the splash screen
    drag_splash_src     = None  # 'palette' | 'prevail' | 'defeat'
    drag_splash_pos     = (0, 0)
    # Rects cached after each draw_splash call (None until first draw)
    splash_bot_rect     = None
    splash_human_rect   = None
    splash_inst_rect    = None
    splash_evolved_rect = None
    splash_prevail_rect = None
    splash_defeat_rect  = None
    splash_tile_rects   = {}    # color_name -> Rect

    # Action-pending state (recruit / promote)
    action_pending   = None   # None | 'recruit' | 'promote'
    pending_nation   = None
    highlight_muster = set()  # cyan — valid recruit hexes
    highlight_promo  = set()  # gold — valid promote hexes
    sidebar_buttons  = []

    # Bot memory: records all human moves for future analysis
    bot_memory = BotMemory(debug=(settings.DEPLOYMENT == 'DEBUG'))

    # Bot goals (prevail + defeat, assigned once per game like human picks)
    # Initialised to empty; will be randomised when vs_bot game starts.
    bot_goals = None

    # Bot animation flash state
    bot_pending_action    = None
    bot_flash_hex         = None
    bot_flash_button_key  = None
    bot_flash_timer       = 0

    # Splash / instructions state
    splash_fonts = {
        'title':  util.get_font(80, bold=True),
        'large':  util.get_font(40, bold=True),
        'medium': util.get_font(26),
        'small':  util.get_font(16),
        'btn':    util.get_font(20, bold=True),
    }
    rules_path   = os.path.join(os.path.dirname(__file__), 'sixnations.txt')
    rules_raw    = open(rules_path).read() if os.path.exists(rules_path) else ''
    rules_surfs  = splash_mod.build_rules_surfaces(
        rules_raw,
        util.get_font(22, bold=True),
        util.get_font(19),
        settings.SCREEN_WIDTH - 280,
    )

    inst_scroll  = 0
    inst_max_scroll = 0
    splash_mx, splash_my = 0, 0

    print("=== Six Nations ===")
    print(f"Player1: {p1_nation.color_name}  |  Player2: {p2_nation.color_name}")
    print(f"Tiles: {len(grid.tiles)} | Armies: {sum(len(v) for v in grid.armies.values())} "
          f"| Champions: {sum(len(v) for v in grid.champions.values())} "
          f"| Sovereigns: {sum(len(v) for v in grid.sovereigns.values())}")
    print("===================")

    # -------------------------------------------------------------------------
    running = True
    while running:
        dt = clock.tick(settings.FPS)
        grid.turn_number = turn_number

        # ── Events ───────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if game_state in (STATE_SPLASH, STATE_INSTRUCTIONS):
                    game_state = STATE_SPLASH
                elif action_pending is not None or drag_unit is not None:
                    action_pending = pending_nation = None
                    highlight_muster = highlight_promo = set()
                    drag_unit = drag_unit_type = None
                    highlight_move = highlight_attack = set()
                else:
                    running = False

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if game_state == STATE_GAME_OVER:
                    # Full game reset back to splash
                    import random as _rnd
                    _rnd.shuffle(nation_list)
                    for _n in nation_list:
                        _n.is_ghost = False
                    p1_nation = nation_list[0]
                    p2_nation = nation_list[1]
                    player1 = Player(secret_nation=p1_nation, is_bot=False, player_id='player1')
                    player2 = Player(secret_nation=p2_nation, is_bot=True,  player_id='player2')
                    players = [player1, player2]
                    current_player_idx  = 0
                    global_cooldown_name = None
                    turn_number         = 1
                    grid.turn_number    = turn_number
                    game_result         = GAME_RESULT_NONE
                    game_state          = STATE_SPLASH
                    game_mode           = 'vs_bot'
                    bot_think_timer     = 0
                    prevail_picks       = []
                    defeat_picks        = []
                    drag_splash_nation  = None
                    drag_splash_src     = None
                    drag_splash_pos     = (0, 0)
                    splash_bot_rect     = None
                    splash_human_rect   = None
                    splash_inst_rect    = None
                    splash_evolved_rect = None
                    splash_prevail_rect = None
                    splash_defeat_rect  = None
                    splash_tile_rects   = {}
                    drag_unit           = None
                    drag_unit_type      = None
                    drag_knight_nation  = None
                    drag_recruit_nation = None
                    highlight_move      = set()
                    highlight_attack    = set()
                    action_pending      = None
                    pending_nation      = None
                    highlight_muster    = set()
                    highlight_promo     = set()
                    sidebar_buttons     = []
                    evolved_bot_config  = None
                    evolved_bot_weights = None
                    bot_memory          = BotMemory(debug=(settings.DEPLOYMENT == 'DEBUG'))
                    bot_goals           = None
                    grid.generate_map()
                    dipl_panel.reset()

            # ---- Splash: left-click (buttons + drag start) -----------------
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and game_state == STATE_SPLASH):
                mx, my = event.pos
                buttons_en = (len(prevail_picks) == 3 and len(defeat_picks) == 3)

                # Mode / instructions buttons (use rects cached from last draw)
                if splash_bot_rect is not None:
                    if buttons_en and splash_bot_rect.collidepoint(mx, my):
                        player1.prevail_picks = list(prevail_picks)
                        player1.defeat_picks  = list(defeat_picks)
                        _sn = list(nation_list)
                        import random as _rnd2; _rnd2.shuffle(_sn)
                        player2.prevail_picks = _sn[:3]
                        player2.defeat_picks  = _sn[3:]
                        game_mode = 'vs_bot'
                        player2.is_bot = True
                        if _HAS_EVOLUTION:
                            bot_goals = BotGoals.random_for(p2_nation, nation_list)
                        game_state     = STATE_HUMAN_TURN
                        game_mode_global = game_mode
                        # Always try to load an evolved config; fall back to basic bot
                        _loaded = load_top_configs(_evolved_configs_path) if _HAS_EVOLUTION and os.path.exists(_evolved_configs_path) else []
                        if _loaded:
                            evolved_bot_config  = _loaded[0]
                            evolved_bot_weights = evolved_bot_config.to_weights_dict()
                            print(f"[Mode] Playing vs Evolved Bot")
                        else:
                            evolved_bot_config  = None
                            evolved_bot_weights = None
                            print(f"[Mode] Playing vs Bot (no evolved configs yet)")
                    elif buttons_en and splash_human_rect.collidepoint(mx, my):
                        player1.prevail_picks = list(prevail_picks)
                        player1.defeat_picks  = list(defeat_picks)
                        _sn = list(nation_list)
                        import random as _rnd4; _rnd4.shuffle(_sn)
                        player2.prevail_picks = _sn[:3]
                        player2.defeat_picks  = _sn[3:]
                        game_mode = 'vs_human'
                        player2.is_bot = False
                        evolved_bot_config  = None
                        evolved_bot_weights = None
                        game_state     = STATE_HUMAN_TURN
                        game_mode_global = game_mode
                        print(f"[Mode] Playing vs Human (hot-seat)")
                    elif (splash_inst_rect is not None
                          and splash_inst_rect.collidepoint(mx, my)):
                        game_state  = STATE_INSTRUCTIONS
                        inst_scroll = 0

                # Drag start: check palette tiles
                if drag_splash_nation is None and splash_tile_rects:
                    placed = {n.color_name for n in prevail_picks + defeat_picks}
                    for ri, trect in splash_tile_rects.items():
                        if trect.collidepoint(mx, my) and ri not in placed:
                            drag_splash_nation = NATIONS_BY_NAME[ri]
                            drag_splash_src    = 'palette'
                            drag_splash_pos    = (mx, my)
                            break

                # Drag start: from PREVAIL box
                if drag_splash_nation is None and splash_prevail_rect is not None:
                    for i, srect in enumerate(splash_mod.get_slot_rects(splash_prevail_rect)):
                        if srect.collidepoint(mx, my) and i < len(prevail_picks):
                            drag_splash_nation = prevail_picks.pop(i)
                            drag_splash_src    = 'prevail'
                            drag_splash_pos    = (mx, my)
                            break

                # Drag start: from DEFEAT box
                if drag_splash_nation is None and splash_defeat_rect is not None:
                    for i, srect in enumerate(splash_mod.get_slot_rects(splash_defeat_rect)):
                        if srect.collidepoint(mx, my) and i < len(defeat_picks):
                            drag_splash_nation = defeat_picks.pop(i)
                            drag_splash_src    = 'defeat'
                            drag_splash_pos    = (mx, my)
                            break

            # ---- Splash: right-click (remove from box) ----------------------
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
                  and game_state == STATE_SPLASH):
                mx, my = event.pos
                if splash_prevail_rect is not None:
                    for i, srect in enumerate(splash_mod.get_slot_rects(splash_prevail_rect)):
                        if srect.collidepoint(mx, my) and i < len(prevail_picks):
                            prevail_picks.pop(i)
                            break
                if splash_defeat_rect is not None:
                    for i, srect in enumerate(splash_mod.get_slot_rects(splash_defeat_rect)):
                        if srect.collidepoint(mx, my) and i < len(defeat_picks):
                            defeat_picks.pop(i)
                            break

            # ---- Splash: drag motion ----------------------------------------
            elif (event.type == pygame.MOUSEMOTION
                  and game_state == STATE_SPLASH and drag_splash_nation is not None):
                drag_splash_pos = event.pos

            # ---- Instructions screen clicks --------------------------------
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and game_state == STATE_INSTRUCTIONS):
                mx, my = event.pos
                s_rect, _ = splash_mod.draw_instructions(
                    screen, splash_fonts, rules_surfs, inst_scroll, mx, my)
                if s_rect.collidepoint(mx, my):
                    game_state = STATE_SPLASH

            # ---- Mouse wheel (instructions scroll) -------------------------
            elif event.type == pygame.MOUSEWHEEL:
                if game_state == STATE_INSTRUCTIONS:
                    inst_scroll = max(0, min(
                        inst_max_scroll, inst_scroll - event.y * 45))

            # ---- Human click / drag start ----------------------------------
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and game_state == STATE_HUMAN_TURN):
                mx, my = event.pos

                # Check if diplomacy panel consumed the click
                if dipl_panel.on_mousedown(event.pos):
                    action_pending = pending_nation = None
                    highlight_muster = highlight_promo = set()
                    continue

                active_player = players[current_player_idx]
                eligible = get_eligible_nations(
                    active_player, global_cooldown_name, nation_list)

                # --- Sidebar button click / drag start ---
                btn = get_sidebar_button_at(sidebar_buttons, mx, my)
                if btn:
                    if btn['type'] == 'recruit':
                        # Drag-and-drop army recruitment: start drag immediately
                        drag_recruit_nation = btn['nation']
                        drag_mouse_pos = (mx, my)
                        highlight_muster = set(grid.get_recruit_hexes(drag_recruit_nation, turn_number=turn_number))
                        action_pending = pending_nation = None
                        highlight_promo = set()
                    elif btn['type'] == 'promote_knight':
                        # Drag-and-drop knight promotion: start drag immediately
                        drag_knight_nation = btn['nation']
                        drag_mouse_pos = (mx, my)
                        highlight_promo = set(grid.get_promote_knight_hexes(drag_knight_nation))
                        action_pending = pending_nation = None
                        highlight_muster = set()
                    elif (action_pending == btn['type']
                            and pending_nation is not None
                            and pending_nation.color_name == btn['nation'].color_name):
                        # Click same button again → cancel
                        action_pending = pending_nation = None
                        highlight_muster = highlight_promo = set()
                    else:
                        action_pending   = btn['type']
                        pending_nation   = btn['nation']
                        highlight_muster = set()
                        highlight_promo  = set()
                        if action_pending == 'promote':
                            highlight_promo  = set(grid.get_promote_hexes(pending_nation))


                # --- Promote selection (Champion) ---
                elif action_pending == 'promote':
                    tq, tr = grid.screen_to_axial(mx, my)
                    if (tq, tr) in highlight_promo:
                        armies_here = [a for a in grid.armies.get((tq, tr), [])
                                       if a.nation.color_name == pending_nation.color_name]
                        if armies_here:
                            grid.promote_to_champion(armies_here[0])
                            moved_nation     = pending_nation
                            _move_data = moves_mod.serialize_move(
                                'promote', pending_nation.color_name,
                                to_hex=(tq, tr))
                            on_local_move_made(_move_data)
                            if game_mode == 'vs_bot':
                                bot_memory.record(turn_number, pending_nation,
                                                  None, (tq, tr), None, 'promote')
                            if settings.DEPLOYMENT == 'DEBUG':
                                print(f"[{active_player.player_id} promote] T{turn_number} {pending_nation.color_name} at {(tq,tr)}  {_move_data}")
                            if game_mode == 'vs_bot':
                                bot_memory.add_score(pending_nation.color_name, 2, settings.NATION_NAMES)
                            action_pending   = pending_nation = None
                            highlight_muster = highlight_promo = set()

                            active_player.add_to_cooldown(moved_nation)
                            global_cooldown_name = moved_nation.color_name
                            dipl_panel.tick_cooldowns()
                            if check_trigger_game_end(grid, nation_list):
                                game_state  = STATE_GAME_OVER
                                game_result = True
                            elif game_mode == 'vs_bot':
                                game_state = STATE_BOT_THINKING
                                bot_think_timer = BOT_THINK_MS
                                current_player_idx = 1
                            elif game_mode == 'network':
                                game_state = STATE_WAITING_OPPONENT
                                turn_number += 1
                            else:
                                current_player_idx = 1 - current_player_idx
                                turn_number += 1
                    else:
                        action_pending = pending_nation = None
                        highlight_muster = highlight_promo = set()

                # --- Promote selection (Knight) ---
                elif action_pending == 'promote_knight':
                    tq, tr = grid.screen_to_axial(mx, my)
                    if (tq, tr) in highlight_promo:
                        armies_here = [a for a in grid.armies.get((tq, tr), [])
                                       if a.nation.color_name == pending_nation.color_name]
                        if armies_here:
                            grid.promote_to_knight(armies_here[0])
                            moved_nation     = pending_nation
                            _move_data = moves_mod.serialize_move(
                                'promote_knight', pending_nation.color_name,
                                to_hex=(tq, tr))
                            on_local_move_made(_move_data)
                            if game_mode == 'vs_bot':
                                bot_memory.record(turn_number, pending_nation,
                                                  None, (tq, tr), None, 'promote_knight')
                            if settings.DEPLOYMENT == 'DEBUG':
                                print(f"[{active_player.player_id} promote knight] T{turn_number} {pending_nation.color_name} at {(tq,tr)}  {_move_data}")
                            if game_mode == 'vs_bot':
                                bot_memory.add_score(pending_nation.color_name, 2, settings.NATION_NAMES)
                            action_pending   = pending_nation = None
                            highlight_muster = highlight_promo = set()

                            active_player.add_to_cooldown(moved_nation)
                            global_cooldown_name = moved_nation.color_name
                            dipl_panel.tick_cooldowns()
                            if check_trigger_game_end(grid, nation_list):
                                game_state  = STATE_GAME_OVER
                                game_result = True
                            elif game_mode == 'vs_bot':
                                game_state = STATE_BOT_THINKING
                                bot_think_timer = BOT_THINK_MS
                                current_player_idx = 1
                            elif game_mode == 'network':
                                game_state = STATE_WAITING_OPPONENT
                                turn_number += 1
                            else:
                                current_player_idx = 1 - current_player_idx
                                turn_number += 1
                    else:
                        action_pending = pending_nation = None
                        highlight_muster = highlight_promo = set()

                # --- Normal drag start ---
                else:
                    unit, utype = get_unit_at_screen(grid, mx, my)
                    if unit:
                        if unit.nation in eligible:
                            drag_unit        = unit
                            drag_unit_type   = utype
                            highlight_move   = set(grid.get_valid_moves(unit))
                            highlight_attack  = set(grid.get_valid_attacks(unit))
                            drag_mouse_pos   = (mx, my)
                        else:
                            error_message = (
                                f"{unit.nation.color_name} is on cooldown — pick another nation.")
                            error_alpha = 255.0

            # ---- Splash: drop nation into box --------------------------------
            elif (event.type == pygame.MOUSEBUTTONUP and event.button == 1
                  and game_state == STATE_SPLASH
                  and drag_splash_nation is not None):
                mx, my = event.pos
                dropped = False
                placed_ri = {n.color_name for n in prevail_picks + defeat_picks}

                if (splash_prevail_rect is not None
                        and splash_prevail_rect.collidepoint(mx, my)):
                    if (len(prevail_picks) < 3
                            and drag_splash_nation.color_name not in placed_ri):
                        prevail_picks.append(drag_splash_nation)
                        dropped = True

                elif (splash_defeat_rect is not None
                      and splash_defeat_rect.collidepoint(mx, my)):
                    if (len(defeat_picks) < 3
                            and drag_splash_nation.color_name not in placed_ri):
                        defeat_picks.append(drag_splash_nation)
                        dropped = True

                if not dropped:
                    # Return to source box if it was dragged from one
                    if drag_splash_src == 'prevail':
                        prevail_picks.append(drag_splash_nation)
                    elif drag_splash_src == 'defeat':
                        defeat_picks.append(drag_splash_nation)
                    # If from palette: just cancel (no re-add needed)

                drag_splash_nation = None
                drag_splash_src    = None

            # ---- Drag motion -----------------------------------------------
            elif event.type == pygame.MOUSEMOTION:
                if game_state == STATE_HUMAN_TURN:
                    dipl_panel.on_mousemotion(event.pos)
                if drag_unit or drag_knight_nation or drag_recruit_nation:
                    drag_mouse_pos = event.pos

            # ---- Human diplomacy drop --------------------------------------
            elif (event.type == pygame.MOUSEBUTTONUP and event.button == 1
                  and game_state == STATE_HUMAN_TURN and dipl_panel.drag):
                action = dipl_panel.on_mouseup(event.pos)
                if action:
                    _apply_diplomacy_move(grid, dipl_panel, action, nation_list)
                    dipl_panel.tick_cooldowns()
                    # Let the bot observe what the human did diplomatically
                    if game_mode == 'vs_bot':
                        _new_stance = ('ally'    if action.to_zone == 'ally'
                                       else 'enemy' if action.to_zone == 'war'
                                       else 'neutral')
                        bot_memory.observe_diplomacy(action.flag_nation,
                                                     action.box_nation,
                                                     _new_stance)

                    if check_trigger_game_end(grid, nation_list):
                        game_state  = STATE_GAME_OVER
                        game_result = True
                    elif game_mode == 'vs_bot':
                        game_state      = STATE_BOT_THINKING
                        bot_think_timer = BOT_THINK_MS
                        current_player_idx = 1
                    elif game_mode == 'network':
                        game_state = STATE_WAITING_OPPONENT
                        turn_number += 1
                    else:
                        current_player_idx = 1 - current_player_idx
                        turn_number += 1

            # ---- Recruit drag drop -----------------------------------------
            elif (event.type == pygame.MOUSEBUTTONUP and event.button == 1
                  and drag_recruit_nation and game_state == STATE_HUMAN_TURN):
                mx, my = event.pos
                tq, tr = grid.screen_to_axial(mx, my)
                moved_nation = None

                if (tq, tr) in highlight_muster:
                    grid.recruit_army(drag_recruit_nation, tq, tr, turn_number=turn_number)
                    moved_nation = drag_recruit_nation
                    _move_data = moves_mod.serialize_move(
                        'recruit', moved_nation.color_name,
                        to_hex=(tq, tr))
                    on_local_move_made(_move_data)
                    if game_mode == 'vs_bot':
                        bot_memory.record(turn_number, moved_nation,
                                          None, None, (tq, tr), 'recruit')
                    if settings.DEPLOYMENT == 'DEBUG':
                        print(f"[{active_player.player_id} recruit] T{turn_number} {moved_nation.color_name} at {(tq,tr)}  {_move_data}")
                    if game_mode == 'vs_bot':
                        bot_memory.add_score(moved_nation.color_name, 2, settings.NATION_NAMES)

                # Always clear recruit drag state and highlights
                drag_recruit_nation = None
                highlight_muster = set()

                if moved_nation:
                    active_player = players[current_player_idx]
                    active_player.add_to_cooldown(moved_nation)
                    global_cooldown_name = moved_nation.color_name
                    dipl_panel.tick_cooldowns()
                    if check_trigger_game_end(grid, nation_list):
                        game_state  = STATE_GAME_OVER
                        game_result = True
                    elif game_mode == 'vs_bot':
                        game_state      = STATE_BOT_THINKING
                        bot_think_timer = BOT_THINK_MS
                        current_player_idx = 1
                    elif game_mode == 'network':
                        game_state = STATE_WAITING_OPPONENT
                        turn_number += 1
                    else:
                        current_player_idx = 1 - current_player_idx
                        turn_number += 1

            # ---- Knight promo drag drop ------------------------------------
            elif (event.type == pygame.MOUSEBUTTONUP and event.button == 1
                  and drag_knight_nation and game_state == STATE_HUMAN_TURN):
                mx, my = event.pos
                tq, tr = grid.screen_to_axial(mx, my)
                moved_nation = None

                if (tq, tr) in highlight_promo:
                    armies_here = [a for a in grid.armies.get((tq, tr), [])
                                   if a.nation.color_name == drag_knight_nation.color_name]
                    if armies_here:
                        grid.promote_to_knight(armies_here[0])
                        moved_nation = drag_knight_nation
                        _move_data = moves_mod.serialize_move(
                            'promote_knight', moved_nation.color_name,
                            to_hex=(tq, tr))
                        on_local_move_made(_move_data)
                        if game_mode == 'vs_bot':
                            bot_memory.record(turn_number, moved_nation,
                                              None, (tq, tr), None, 'promote_knight')
                        if settings.DEPLOYMENT == 'DEBUG':
                            print(f"[{active_player.player_id} promote knight] T{turn_number} {moved_nation.color_name} at {(tq,tr)}  {_move_data}")
                        if game_mode == 'vs_bot':
                            bot_memory.add_score(moved_nation.color_name, 2, settings.NATION_NAMES)

                # Always clear knight drag state and highlights
                drag_knight_nation = None
                highlight_promo = set()

                if moved_nation:
                    active_player = players[current_player_idx]
                    active_player.add_to_cooldown(moved_nation)
                    global_cooldown_name = moved_nation.color_name
                    dipl_panel.tick_cooldowns()
                    if check_trigger_game_end(grid, nation_list):
                        game_state  = STATE_GAME_OVER
                        game_result = True
                    elif game_mode == 'vs_bot':
                        game_state      = STATE_BOT_THINKING
                        bot_think_timer = BOT_THINK_MS
                        current_player_idx = 1
                    elif game_mode == 'network':
                        game_state = STATE_WAITING_OPPONENT
                        turn_number += 1
                    else:
                        current_player_idx = 1 - current_player_idx
                        turn_number += 1

            # ---- Human drag drop -------------------------------------------
            elif (event.type == pygame.MOUSEBUTTONUP and event.button == 1
                  and drag_unit and game_state == STATE_HUMAN_TURN):
                mx, my = event.pos
                tq, tr = grid.screen_to_axial(mx, my)

                moved_nation = None

                if (tq, tr) in highlight_move:
                    from_hex = (drag_unit.q, drag_unit.r)
                    _unit_type_snap = drag_unit_type  # capture before drag clears
                    _unit_snap      = drag_unit        # capture before apply_move moves it
                    success, msg = grid.apply_move(drag_unit, tq, tr)
                    if success:
                        moved_nation = drag_unit.nation
                        _move_data = moves_mod.serialize_move(
                            'move', drag_unit.nation.color_name,
                            unit_type=_unit_type_snap,
                            from_hex=from_hex, to_hex=(tq, tr))
                        on_local_move_made(_move_data)
                        if game_mode == 'vs_bot':
                            bot_memory.record(turn_number, drag_unit.nation,
                                              drag_unit_type, from_hex, (tq, tr), 'move')
                        # Scoring (bot mode only)
                        ri = drag_unit.nation.color_name
                        _nnames = settings.NATION_NAMES
                        if settings.DEPLOYMENT == 'DEBUG':
                            print(f"[{active_player.player_id} move] T{turn_number} {drag_unit.nation.color_name} {_unit_type_snap} {from_hex}->{(tq,tr)}  {_move_data}")
                        if game_mode == 'vs_bot':
                            bot_memory.add_score(ri, 2, _nnames)
                            if _unit_type_snap == 'champion' and grid.is_supported(_unit_snap):
                                bot_memory.add_score(ri, 4, _nnames)
                            elif _unit_type_snap == 'sovereign':
                                if not grid.is_supported(_unit_snap):
                                    bot_memory.add_score(ri, -4, _nnames)
                                fq, fr = from_hex
                                old_d = max(abs(fq), abs(fr), abs(fq + fr))
                                new_d = max(abs(tq), abs(tr), abs(tq + tr))
                                if new_d <= 1:
                                    bot_memory.add_score(ri, -3, _nnames)
                                elif new_d < old_d:
                                    bot_memory.add_score(ri, -2, _nnames)
                    else:
                        error_message = msg; error_alpha = 255.0

                elif (tq, tr) in highlight_attack:
                    from_hex = (drag_unit.q, drag_unit.r)
                    # Capture target-hex nations BEFORE resolving (destroyed units disappear)
                    _target_ris = set()
                    for _u in grid.sovereigns.get((tq, tr), []):
                        if drag_unit.nation.is_enemy(_u.nation):
                            _target_ris.add(_u.nation.color_name)
                    for _u in grid.champions.get((tq, tr), []):
                        if drag_unit.nation.is_enemy(_u.nation):
                            _target_ris.add(_u.nation.color_name)
                    for _u in grid.knights.get((tq, tr), []):
                        if drag_unit.nation.is_enemy(_u.nation):
                            _target_ris.add(_u.nation.color_name)
                    for _u in grid.armies.get((tq, tr), []):
                        if drag_unit.nation.is_enemy(_u.nation):
                            _target_ris.add(_u.nation.color_name)
                    success, msg, _ = grid.resolve_attack(drag_unit, tq, tr)
                    if success:
                        moved_nation = drag_unit.nation
                        _move_data = moves_mod.serialize_move(
                            'attack', drag_unit.nation.color_name,
                            unit_type=drag_unit_type,
                            from_hex=from_hex, to_hex=(tq, tr))
                        on_local_move_made(_move_data)
                        if game_mode == 'vs_bot':
                            bot_memory.record(turn_number, drag_unit.nation,
                                              drag_unit_type, from_hex, (tq, tr), 'attack')
                            _nnames = settings.NATION_NAMES
                            bot_memory.add_score(drag_unit.nation.color_name, 2, _nnames)
                            for _ri in _target_ris:
                                bot_memory.add_score(_ri, -4, _nnames)
                        if settings.DEPLOYMENT == 'DEBUG':
                            print(f"[{active_player.player_id} attack] T{turn_number} {drag_unit.nation.color_name} {from_hex}->{(tq,tr)}  {_move_data}")
                    else:
                        error_message = msg; error_alpha = 255.0

                elif (tq, tr) != (drag_unit.q, drag_unit.r):
                    # Dropped on invalid hex — snap back silently
                    pass

                # Clear drag state always
                drag_unit      = None
                drag_unit_type = None
                highlight_move   = set()
                highlight_attack = set()

                # After a successful move ---
                if moved_nation:
                    active_player = players[current_player_idx]
                    active_player.add_to_cooldown(moved_nation)
                    global_cooldown_name = moved_nation.color_name
                    dipl_panel.tick_cooldowns()
                    if check_trigger_game_end(grid, nation_list):
                        game_state  = STATE_GAME_OVER
                        game_result = True
                    elif game_mode == 'vs_bot':
                        game_state      = STATE_BOT_THINKING
                        bot_think_timer = BOT_THINK_MS
                        current_player_idx = 1
                    elif game_mode == 'network':
                        game_state = STATE_WAITING_OPPONENT
                        turn_number += 1
                    else:
                        current_player_idx = 1 - current_player_idx
                        turn_number += 1

        # ── Network: poll for opponent's move ──────────────────────────────
        if game_state == STATE_WAITING_OPPONENT:
            incoming = on_network_move_received()
            if incoming:
                success, msg, moved_nation, destroyed = moves_mod.apply_serialized_move(
                    grid, incoming, nation_list)
                if success and moved_nation:
                    # Opponent is always player2 in our local model
                    player2.add_to_cooldown(moved_nation)
                    global_cooldown_name = moved_nation.color_name
                    dipl_panel.tick_cooldowns()
                    if settings.DEPLOYMENT == 'DEBUG':
                        print(f"[Network] Received move: {incoming}")
                    if check_trigger_game_end(grid, nation_list):
                        game_state  = STATE_GAME_OVER
                        game_result = True
                    else:
                        game_state = STATE_HUMAN_TURN
                elif settings.DEPLOYMENT == 'DEBUG':
                    print(f"[Network] Bad move from opponent: {msg}")

        # ── Bot thinking countdown ─────────────────────────────────────────
        if game_state == STATE_BOT_THINKING:
            bot_think_timer -= dt
            if bot_think_timer <= 0:
                # Compute the action (don't execute yet — animate first)
                # Build top-3 suspicion list for this turn
                _top3_pairs = bot_memory.guess_top3_factions(
                    nation_list,
                    exclude_names=(p2_nation.color_name,))
                _top3_names = [n.color_name for n, _ in _top3_pairs]
                _bottom3_pairs = bot_memory.guess_bottom3_factions(
                    nation_list,
                    exclude_names=(p2_nation.color_name,))
                _bottom3_names = [n.color_name for n, _ in _bottom3_pairs]
                _suspected_name = _top3_names[0] if _top3_names else None
                bot_pending_action = bot_ai.compute_bot_action(
                    grid, player2, global_cooldown_name, nation_list,
                    turn_number, suspected_human_ri=_suspected_name,
                    weights=evolved_bot_weights,
                    evolved_config=evolved_bot_config,
                    lookahead_depth=evolved_bot_config.lookahead_depth if evolved_bot_config else None,
                    lookahead_beam=evolved_bot_config.lookahead_beam if evolved_bot_config else None,
                    lookahead_mode=evolved_bot_config.lookahead_mode if evolved_bot_config else None,
                    eval_weights=evolved_bot_config.to_evaluator_weights() if evolved_bot_config else None,
                    dipl_state=dipl_panel.state,
                    bot_goals=bot_goals,
                    top3_names=_top3_names,
                    bottom3_names=_bottom3_names)
                if bot_pending_action is None:
                    # No legal move at all; skip straight to human turn
                    game_state         = STATE_HUMAN_TURN
                    current_player_idx = 0
                    turn_number       += 1
                    dipl_panel.tick_cooldowns()
                else:
                    _, atype, *payload = bot_pending_action
                    if atype == 'diplomacy':
                        # Diplomacy actions: no hex flash — execute immediately then show panel
                        nation_a, nation_b, new_stance = payload[0], payload[1], payload[2]
                        from diplomacy_panel import DiplomacyAction as _DA
                        dipl_action = _DA(
                            box_nation=nation_b,
                            flag_nation=nation_a,
                            from_zone='home',   # bot-generated; reconcile handles effects
                            to_zone='war' if new_stance == 'enemy' else
                                    'ally' if new_stance == 'ally' else 'home')
                        _apply_diplomacy_move(grid, dipl_panel, dipl_action, nation_list)
                        # No flash — immediately transition to post-flash / turn end
                        if settings.DEPLOYMENT == 'DEBUG':
                            print(f"[Bot-dipl] {nation_a.color_name} -> {new_stance} -> {nation_b.color_name}")
                        bot_pending_action   = None
                        if check_trigger_game_end(grid, nation_list):
                            game_state  = STATE_GAME_OVER
                            game_result = True
                        else:
                            game_state         = STATE_HUMAN_TURN
                            current_player_idx = 0
                            turn_number       += 1
                            dipl_panel.tick_cooldowns()
                    elif atype in ('move', 'attack'):
                        actor, coord = payload[0], payload[1]
                        bot_flash_hex = (actor.q, actor.r)
                        bot_flash_button_key = None
                        bot_flash_timer = BOT_FLASH_MS
                        game_state = STATE_BOT_PRE_FLASH
                    else:   # recruit / promote
                        actor = payload[0]
                        ri = actor.color_name
                        bot_flash_hex = None
                        bot_flash_button_key = (atype if atype == 'recruit' else 'promote', ri)
                        bot_flash_timer = BOT_FLASH_MS
                        game_state = STATE_BOT_PRE_FLASH

        # ── Bot pre-flash (show source) ───────────────────────────────────
        if game_state == STATE_BOT_PRE_FLASH:
            bot_flash_timer -= dt
            if bot_flash_timer <= 0:
                # Execute the action
                moved_nation, _atype, bot_msg = bot_ai.execute_bot_action(
                    grid, bot_pending_action)
                if settings.DEPLOYMENT == 'DEBUG':
                    print(f"[Bot] {bot_msg}")

                if moved_nation:
                    player2.add_to_cooldown(moved_nation)
                    global_cooldown_name = moved_nation.color_name

                # Determine post-flash hex (destination)
                _, atype, *payload = bot_pending_action
                if atype in ('move', 'attack'):
                    actor, coord = payload[0], payload[1]
                    bot_flash_hex = coord
                else:
                    bot_flash_hex = None
                bot_flash_button_key = None

                bot_flash_timer = BOT_FLASH_MS
                game_state = STATE_BOT_POST_FLASH

        # ── Bot post-flash (show destination) ─────────────────────────────
        if game_state == STATE_BOT_POST_FLASH:
            bot_flash_timer -= dt
            if bot_flash_timer <= 0:
                bot_pending_action   = None
                bot_flash_hex        = None
                bot_flash_button_key = None

                if check_trigger_game_end(grid, nation_list):
                    game_state  = STATE_GAME_OVER
                    game_result = True
                else:
                    game_state         = STATE_HUMAN_TURN
                    current_player_idx = 0
                    turn_number       += 1
                    dipl_panel.tick_cooldowns()

        # ── Error fade ────────────────────────────────────────────────────────
        if error_alpha > 0:
            error_alpha = max(0.0, error_alpha - dt * 0.4)
            if error_alpha == 0:
                error_message = ""

        # ── Draw ─────────────────────────────────────────────────────────────
        splash_mx, splash_my = pygame.mouse.get_pos()

        if game_state == STATE_SPLASH:
            _buttons_en = (len(prevail_picks) == 3 and len(defeat_picks) == 3)
            _splash_result = splash_mod.draw_splash(
                screen, splash_fonts, p1_nation,
                splash_mx, splash_my,
                evolved_available=has_evolved_configs,
                prevail_nations=prevail_picks,
                defeat_nations=defeat_picks,
                drag_nation=drag_splash_nation,
                drag_pos=drag_splash_pos if drag_splash_nation else None,
                buttons_enabled=_buttons_en)
            (splash_bot_rect, splash_human_rect, splash_inst_rect, splash_evolved_rect,
             splash_prevail_rect, splash_defeat_rect, splash_tile_rects) = _splash_result

        elif game_state == STATE_INSTRUCTIONS:
            _, inst_max_scroll = splash_mod.draw_instructions(
                screen, splash_fonts, rules_surfs,
                inst_scroll, splash_mx, splash_my)

        else:
            screen.fill(settings.COLOR_BACKGROUND)

            # Nations the active player cannot move right now → rendered as frozen
            active_player = players[current_player_idx]
            eligible_now      = get_eligible_nations(active_player, global_cooldown_name, nation_list)
            eligible_name_set = {n.color_name for n in eligible_now}
            frozen_name_set   = {n.color_name for n in nation_list
                                 if n.color_name not in eligible_name_set}
            ghost_name_set    = {n.color_name for n in nation_list if n.is_ghost}

            grid.draw(screen,
                      highlight_move=highlight_move,
                      highlight_attack=highlight_attack,
                      drag_unit=drag_unit,
                      frozen_nations=frozen_name_set,
                      ghost_nations=ghost_name_set)

            # Action-pending highlights drawn on top of board
            hw, hh = grid.hex_width, grid.hex_height
            for (q, r) in highlight_muster:
                cx, cy = grid.screen_pos(q, r)
                grid.draw_hex_polygon(screen, cx, cy, hw - 2, hh - 2, (50, 220, 180), 3)
            for (q, r) in highlight_promo:
                cx, cy = grid.screen_pos(q, r)
                grid.draw_hex_polygon(screen, cx, cy, hw - 2, hh - 2, (220, 185, 40), 3)

            # Recompute sidebar buttons every frame (cheap) and draw them
            sidebar_buttons = compute_sidebar_buttons(grid, eligible_now, turn_number=turn_number)
            font_tiny = util.get_font(11)
            draw_sidebar_buttons(screen, grid, sidebar_buttons,
                                 action_pending, pending_nation, font_tiny,
                                 drag_knight_nation=drag_knight_nation,
                                 drag_recruit_nation=drag_recruit_nation)

            # Draw Diplomacy Panel on right sidebar
            dipl_panel.draw(screen, splash_fonts)

            current_player = players[current_player_idx]
            # In vs_bot, always show the human's secret nation (player1)
            display_player = player1 if game_mode == 'vs_bot' else active_player
            draw_top_bar(screen, font_large, font_small,
                         display_player, current_player, turn_number,
                         game_state, game_mode)
            draw_predictions_panel(screen, font_small, player1)
            draw_cooldown_panel(screen, font_small, players, global_cooldown_name)
            draw_error(screen, font_small, error_message, error_alpha)

            # Debug: bot faction guess (top-left, below top bar) — DEBUG mode only
            if settings.DEPLOYMENT == 'DEBUG' and game_mode == 'vs_bot':
                _guess = bot_memory.guess_faction(
                    nation_list,
                    exclude_names=(p2_nation.color_name,))
                if _guess:
                    _gt = f"Bot guess for player: {_guess.color_name}"
                    _gs = font_small.render(_gt, True, _guess.color_rgb)
                    screen.blit(_gs, (14, settings.TOP_BAR_HEIGHT + 8))

            # Drag ghost drawn last (on top of everything)
            if drag_unit and drag_unit_type:
                draw_drag_ghost(screen, drag_unit_type,
                                drag_unit.nation.color_rgb, *drag_mouse_pos)
            elif drag_knight_nation:
                draw_drag_ghost(screen, 'knight',
                                drag_knight_nation.color_rgb, *drag_mouse_pos)
            elif drag_recruit_nation:
                draw_drag_ghost(screen, 'army',
                                drag_recruit_nation.color_rgb, *drag_mouse_pos)

            # Bot animation flash — bright pulsing ring on the relevant hex / button
            if game_state in (STATE_BOT_PRE_FLASH, STATE_BOT_POST_FLASH):
                frac  = bot_flash_timer / BOT_FLASH_MS
                pulse = int(180 + 75 * abs(2 * frac - 1))

                if bot_flash_hex:
                    fq, fr = bot_flash_hex
                    fx, fy = grid.screen_pos(fq, fr)
                    flash_surf = pygame.Surface((hw + 10, hh + 10), pygame.SRCALPHA)
                    grid.draw_hex_polygon(flash_surf,
                                          (hw + 10) // 2, (hh + 10) // 2,
                                          hw + 6, hh + 6,
                                          (255, 255, 255, pulse))
                    screen.blit(flash_surf, (fx - (hw + 10) // 2,
                                             fy - (hh + 10) // 2))
                    grid.draw_hex_polygon(screen, fx, fy,
                                          hw - 2, hh - 2,
                                          (255, 255, 255), 3)

                if bot_flash_button_key:
                    for btn in sidebar_buttons:
                        if btn['key'] == bot_flash_button_key:
                            bx, by = btn['pos']
                            r = btn['size'] // 2 + 4
                            pygame.draw.circle(screen, (255, 255, 255),
                                               (bx, by), r, 3)
                            break

            if game_state == STATE_GAME_OVER:
                draw_score_screen(screen, player1, player2, nation_list)

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
