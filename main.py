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
from factions import NATIONS
from player import Player

# Evolution module — optional, only needed for "Play vs Evolved Bot"
try:
    from evolution import load_top_configs, BotConfig, EvolvableBot
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
UNIT_SIZE    = 44
UNIT_RADIUS  = UNIT_SIZE // 2
UNIT_SPACING = 52


# ---------------------------------------------------------------------------
# Asset loading
# ---------------------------------------------------------------------------

def load_diplo_ring(size: int) -> pygame.Surface:
    img = util.load_image("DiplomacyRing.jpg", size=(size, size))
    if img is not None:
        return img
    surf = pygame.Surface((size, size))
    surf.fill((25, 30, 45))
    font = util.get_font(13, bold=True)
    lbl  = font.render("DIPLOMACY RING", True, (100, 110, 140))
    surf.blit(lbl, lbl.get_rect(center=(size // 2, size // 2)))
    return surf


# ---------------------------------------------------------------------------
# Game state helpers
# ---------------------------------------------------------------------------

def get_eligible_nations(player, global_cooldown_idx, all_nations):
    """Nations the current player is allowed to move this turn."""
    return [
        n for n in all_nations
        if not player.nation_on_cooldown(n)
        and (global_cooldown_idx is None or n.ring_index != global_cooldown_idx)
        and not n.is_ghost
    ]


def get_unit_at_screen(grid, mx, my):
    """
    Return (unit, unit_type_str) for the unit icon the mouse is over,
    or (None, None) if none.
    unit_type_str is one of 'sovereign', 'champion', 'army'.
    """
    q, r = grid.screen_to_axial(mx, my)
    if not grid.get_tile(q, r):
        return None, None

    cx, cy = grid.screen_pos(q, r)
    # Same ordering/layout as map.py draw()
    units_here = (
        [('sovereign', u) for u in grid.sovereigns.get((q, r), [])]
        + [('champion', u) for u in grid.champions.get((q, r), [])]
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
                   'champion': 'champion.png',
                   'sovereign': 'sovereign.png'}.get(unit_type)
    if sprite_name is not None:
        scale = 3.2 if unit_type == 'champion' else 2.0
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

    nation = active_player.secret_nation
    col    = nation.color_rgb

    if game_mode == 'vs_human':
        label_text = f"{active_player.player_id.upper()} SECRET NATION:"
    else:
        label_text = "YOUR SECRET NATION:"
    lbl = font_small.render(label_text, True, settings.COLOR_TEXT_MUTED)
    screen.blit(lbl, lbl.get_rect(midleft=(20, settings.TOP_BAR_HEIGHT // 2 - 10)))
    bx, by = 22, settings.TOP_BAR_HEIGHT // 2 + 4
    pygame.draw.rect(screen, col, (bx, by, 28, 20), border_radius=4)
    name = font_large.render(nation.color_name.upper(), True, col)
    screen.blit(name, name.get_rect(midleft=(bx + 38, by + 10)))

    if game_state == STATE_GAME_OVER:
        centre_text = "GAME OVER"
        centre_col  = settings.COLOR_TEXT_MUTED
    elif game_state == STATE_BOT_THINKING:
        centre_text = f"TURN {turn_number}  —  BOT IS THINKING…"
        centre_col  = settings.NATION_COLORS[1]   # green-ish pulse colour
    elif game_state == STATE_WAITING_OPPONENT:
        centre_text = f"TURN {turn_number}  —  WAITING FOR OPPONENT…"
        centre_col  = settings.NATION_COLORS[2]   # sky-blue pulse
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


def draw_diplo_panel(screen, diplo_img, font_small):
    size   = settings.DIPLO_RING_SIZE
    margin = 10
    x = settings.SCREEN_WIDTH - size - margin
    y = margin
    panel = pygame.Rect(x - 6, y - 6, size + 12, size + 12)
    pygame.draw.rect(screen, settings.COLOR_PANEL, panel, border_radius=6)
    pygame.draw.rect(screen, settings.COLOR_PANEL_BORDER, panel, 1, border_radius=6)
    screen.blit(diplo_img, (x, y))
    lbl = font_small.render("Diplomatic Ring", True, settings.COLOR_TEXT_MUTED)
    screen.blit(lbl, lbl.get_rect(midtop=(x + size // 2, y + size + 8)))


def draw_cooldown_panel(screen, font_small, players, global_cooldown_idx):
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
        for i, ri in enumerate(player.cooldown):
            col = settings.NATION_COLORS[ri]
            bx  = x + 55 + i * 36
            pygame.draw.rect(screen, col, (bx, row_y - 2, 28, 20), border_radius=3)
            if ri == global_cooldown_idx:
                pygame.draw.rect(screen, (255, 255, 255),
                                 (bx, row_y - 2, 28, 20), 2, border_radius=3)

    _draw_row("You:", players[0], y + 34)
    _draw_row("Bot:", players[1], y + 64)

    if global_cooldown_idx is not None:
        gname = settings.NATION_NAMES[global_cooldown_idx]
        glbl  = font_small.render(f"Global block: {gname}", True, (90, 105, 140))
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


def draw_game_over(screen, font_large, font_small, result):
    """Semi-transparent game-over overlay with bold, shadowed text."""
    W, H = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT

    # Darker overlay so the board fades further into the background
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 210))
    screen.blit(overlay, (0, 0))

    if result == GAME_RESULT_WIN_SCORE:
        msg = "YOU WIN!"
        col = (80, 235, 140)
        sub = "You have destroyed 2 of your 3 target sovereigns."
    elif result == GAME_RESULT_WIN_OPPONENT_DEAD:
        msg = "YOU WIN!"
        col = (80, 235, 140)
        sub = "Your opponent\u2019s secret sovereign has been destroyed."
    elif result == GAME_RESULT_LOSS_SOVEREIGN:
        msg = "YOU LOSE."
        col = (235, 80, 60)
        sub = "Your secret nation\u2019s sovereign has been destroyed."
    elif result == GAME_RESULT_TIE:
        msg = "IT\u2019S A TIE."
        col = (220, 205, 60)
        sub = "Both secret nations share the same victories \u2014 a simultaneous win."
    else:   # GAME_RESULT_LOSS_BOT_SCORE
        msg = "YOU LOSE."
        col = (235, 80, 60)
        sub = "Your opponent has destroyed 2 of their 3 target sovereigns."

    font_title = util.get_font(72, bold=True)
    font_sub   = util.get_font(24, bold=True)
    font_hint  = util.get_font(18)
    SHADOW     = (0, 0, 0)

    # Title
    cy_title = H // 2 - 60
    title_surf = font_title.render(msg, True, col)
    shadow_surf = font_title.render(msg, True, SHADOW)
    screen.blit(shadow_surf, shadow_surf.get_rect(center=(W // 2 + 3, cy_title + 3)))
    screen.blit(title_surf,  title_surf.get_rect(center=(W // 2, cy_title)))

    # Subtitle
    cy_sub = H // 2 + 20
    sub_surf = font_sub.render(sub, True, (230, 235, 255))
    sh_sub   = font_sub.render(sub, True, SHADOW)
    screen.blit(sh_sub,  sh_sub.get_rect(center=(W // 2 + 2, cy_sub + 2)))
    screen.blit(sub_surf, sub_surf.get_rect(center=(W // 2, cy_sub)))

    # ESC hint
    cy_esc = H // 2 + 66
    esc_surf = font_hint.render("Press ESC to quit.", True, (160, 168, 195))
    sh_esc   = font_hint.render("Press ESC to quit.", True, SHADOW)
    screen.blit(sh_esc,  sh_esc.get_rect(center=(W // 2 + 1, cy_esc + 1)))
    screen.blit(esc_surf, esc_surf.get_rect(center=(W // 2, cy_esc)))


# ---------------------------------------------------------------------------
# Recruit / Promote sidebar buttons
# ---------------------------------------------------------------------------

# Direction (dq, dr) pointing outward from map center for each nation's corner
_CORNER_OUTWARD = [
    ( 0, -1),   # 0 Yellow
    ( 1, -1),   # 1 Green
    ( 1,  0),   # 2 Sky Blue
    ( 0,  1),   # 3 Cobalt
    (-1,  1),   # 4 Magenta
    (-1,  0),   # 5 Crimson
]

def compute_sidebar_buttons(grid, eligible_nations):
    """
    Return a list of button dicts for recruit/promote actions.
    Each dict: {type, nation, pos:(x,y), size, key:(type,ring_idx)}
    Buttons are placed one hex outward from each nation's corner hex,
    clamped so they always remain inside the visible screen area.
    """
    buttons  = []
    ICON_SIZE = 32
    GAP       = 40   # horizontal gap between two icons for the same nation
    MARGIN    = ICON_SIZE  # minimum distance from screen edges

    for nation in eligible_nations:
        ri = nation.ring_index
        cq, cr = grid.NATION_CORNERS[ri]
        dq, dr = _CORNER_OUTWARD[ri]
        # Phantom hex one step outward
        px, py = grid.screen_pos(cq + dq, cr + dr)

        # Clamp so buttons never leave the visible area
        px = max(MARGIN, min(settings.SCREEN_WIDTH  - MARGIN, px))
        py = max(settings.TOP_BAR_HEIGHT + MARGIN,
                 min(settings.SCREEN_HEIGHT - MARGIN, py))

        can_recruit = bool(grid.get_recruit_hexes(nation))
        can_promote = bool(grid.get_promote_hexes(nation))

        icons = []
        if can_recruit:
            icons.append('recruit')
        if can_promote:
            icons.append('promote')

        for i, icon_type in enumerate(icons):
            offset_x = (i - (len(icons) - 1) / 2.0) * GAP
            bx = int(max(MARGIN, min(settings.SCREEN_WIDTH - MARGIN, px + offset_x)))
            buttons.append({
                'type':   icon_type,
                'nation': nation,
                'pos':    (bx, int(py)),
                'size':   ICON_SIZE,
                'key':    (icon_type, ri),
            })

    return buttons


def draw_sidebar_buttons(screen, grid, buttons, action_pending, pending_nation, font_tiny):
    """Draw recruit/promote buttons outside each nation's corner hex."""
    w, h = grid.hex_width, grid.hex_height

    for btn in buttons:
        bx, by   = btn['pos']
        size     = btn['size']
        nation   = btn['nation']
        btype    = btn['type']
        c        = nation.color_rgb
        radius   = size // 2

        active = (action_pending == btype
                  and pending_nation is not None
                  and pending_nation.ring_index == nation.ring_index)

        # Coloured circular background
        bg_col  = tuple(min(255, int(v * 0.7 + 30)) for v in c)
        pygame.draw.circle(screen, bg_col, (bx, by), radius)

        # Border: bright white when active, subtle otherwise
        border_col   = (255, 255, 255) if active else (180, 190, 210)
        border_width = 3 if active else 1
        pygame.draw.circle(screen, border_col, (bx, by), radius, border_width)

        # Symbol: army (shield) or champion (sword cross) in white
        s = int(size * 0.35)
        sym_col = (255, 255, 255)

        if btype == 'recruit':
            # Army shield sprite (white for sidebar button)
            icon_h = int(s * 2.0)
            sprite_name = 'army.png'
            template = util.load_image(sprite_name, alpha=True)
            if template is not None:
                icon_w = int(icon_h * template.get_width() / template.get_height())
                sprite = util.load_tinted_sprite(sprite_name, sym_col, icon_w, icon_h)
                if sprite is not None:
                    screen.blit(sprite, sprite.get_rect(center=(bx, by)))
        else:
            # Champion sword sprite (white for sidebar button)
            icon_h = int(s * 2.0)
            sprite_name = 'champion.png'
            template = util.load_image(sprite_name, alpha=True)
            if template is not None:
                icon_w = int(icon_h * template.get_width() / template.get_height())
                sprite = util.load_tinted_sprite(sprite_name, sym_col, icon_w, icon_h)
                if sprite is not None:
                    screen.blit(sprite, sprite.get_rect(center=(bx, by)))

        # Small label below
        label = "REC" if btype == 'recruit' else "PRO"
        lbl   = font_tiny.render(label, True,
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

def check_all_end_conditions(grid, player1, player2, nation_list):
    """
    Run ghost detection then evaluate all win/loss/tie conditions.
    Returns a GAME_RESULT_* constant, or None if the game continues.
    Priority: tie > individual win > individual loss.
    """
    grid.check_ghost_nations(nation_list)
    p1_wins  = grid.check_win_condition(player1, nation_list)
    p2_wins  = grid.check_win_condition(player2, nation_list)
    p1_loses = grid.check_loss_condition(player1)
    p2_loses = grid.check_loss_condition(player2)

    # Simultaneous wins or simultaneous sovereign deaths → tie
    if (p1_wins and p2_wins) or (p1_loses and p2_loses):
        return GAME_RESULT_TIE
    if p1_wins:
        return GAME_RESULT_WIN_SCORE
    if p2_loses:
        return GAME_RESULT_WIN_OPPONENT_DEAD
    if p2_wins:
        return GAME_RESULT_LOSS_BOT_SCORE
    if p1_loses:
        return GAME_RESULT_LOSS_SOVEREIGN
    return None


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

    # Player objects — created after splash screen selects game_mode.
    # Initialise with vs_bot defaults so the splash can show the secret nation.
    p1_nation = random.choice(nation_list)
    p2_nation = random.choice([n for n in nation_list if n is not p1_nation])

    player1 = Player(secret_nation=p1_nation, is_bot=False, player_id='player1')
    player2 = Player(secret_nation=p2_nation, is_bot=True,  player_id='player2')
    players = [player1, player2]

    current_player_idx  = 0
    global_cooldown_idx = None
    turn_number         = 1
    game_state          = STATE_SPLASH
    game_mode           = 'vs_bot'       # set by splash button click
    game_result         = GAME_RESULT_NONE
    bot_think_timer     = 0

    # Evolved bot config — loaded if bot_configs.json exists
    evolved_bot_config  = None           # BotConfig or None
    evolved_bot_weights = None           # dict or None
    _evolved_configs_path = os.path.join(os.path.dirname(__file__), 'bot_configs.json')
    has_evolved_configs = (_HAS_EVOLUTION
                          and os.path.exists(_evolved_configs_path))

    error_message = ""
    error_alpha   = 0.0

    grid = MapGrid()
    grid.generate_map()

    # Drag state
    drag_unit      = None
    drag_unit_type = None
    highlight_move   = set()
    highlight_attack = set()
    drag_mouse_pos   = (0, 0)

    # Action-pending state (recruit / promote)
    action_pending   = None   # None | 'recruit' | 'promote'
    pending_nation   = None
    highlight_muster = set()  # cyan — valid recruit hexes
    highlight_promo  = set()  # gold — valid promote hexes
    sidebar_buttons  = []

    # Bot memory: records all human moves for future analysis
    bot_memory = BotMemory(debug=(settings.DEPLOYMENT == 'DEBUG'))

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
        util.get_font(17, bold=True),
        util.get_font(15),
        settings.SCREEN_WIDTH - 280,
    )
    inst_scroll  = 0
    inst_max_scroll = 0
    splash_mx, splash_my = 0, 0

    diplo_img   = load_diplo_ring(settings.DIPLO_RING_SIZE)
    diplo_splash = pygame.transform.smoothscale(diplo_img, (140, 140)) if diplo_img else None

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

            # ---- Splash screen clicks --------------------------------------
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and game_state == STATE_SPLASH):
                mx, my = event.pos
                b_rect, h_rect, i_rect, e_rect = splash_mod.draw_splash(
                    screen, splash_fonts, p1_nation, mx, my, diplo_splash,
                    evolved_available=has_evolved_configs)
                if b_rect.collidepoint(mx, my):
                    game_mode      = 'vs_bot'
                    player2.is_bot = True
                    evolved_bot_config  = None
                    evolved_bot_weights = None
                    game_state     = STATE_HUMAN_TURN
                    game_mode_global = game_mode
                    print(f"[Mode] Playing vs Bot")
                elif e_rect and e_rect.collidepoint(mx, my):
                    game_mode      = 'vs_bot'
                    player2.is_bot = True
                    game_state     = STATE_HUMAN_TURN
                    game_mode_global = game_mode
                    # Load a random evolved config
                    _loaded = load_top_configs(_evolved_configs_path)
                    if _loaded:
                        evolved_bot_config  = random.choice(_loaded)
                        evolved_bot_weights = evolved_bot_config.to_weights_dict()
                        print(f"[Mode] Playing vs Evolved Bot  "
                              f"(kill={evolved_bot_config.w_kill_enemy:.2f}  "
                              f"rnd={evolved_bot_config.w_random:.2f}  "
                              f"dec={evolved_bot_config.w_deceptive:.2f})")
                    else:
                        evolved_bot_config  = None
                        evolved_bot_weights = None
                        print(f"[Mode] Playing vs Bot (no evolved configs found)")
                elif h_rect.collidepoint(mx, my):
                    game_mode      = 'vs_human'
                    player2.is_bot = False
                    evolved_bot_config  = None
                    evolved_bot_weights = None
                    game_state     = STATE_HUMAN_TURN
                    game_mode_global = game_mode
                    print(f"[Mode] Playing vs Human (hot-seat)")
                elif i_rect.collidepoint(mx, my):
                    game_state    = STATE_INSTRUCTIONS
                    inst_scroll   = 0

            # ---- Instructions screen clicks --------------------------------
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and game_state == STATE_INSTRUCTIONS):
                mx, my = event.pos
                s_rect, _ = splash_mod.draw_instructions(
                    screen, splash_fonts, rules_surfs, inst_scroll, mx, my)
                if s_rect.collidepoint(mx, my):
                    game_state = STATE_HUMAN_TURN

            # ---- Mouse wheel (instructions scroll) -------------------------
            elif event.type == pygame.MOUSEWHEEL:
                if game_state == STATE_INSTRUCTIONS:
                    inst_scroll = max(0, min(
                        inst_max_scroll, inst_scroll - event.y * 45))

            # ---- Human click / drag start ----------------------------------
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and game_state == STATE_HUMAN_TURN):
                mx, my = event.pos
                active_player = players[current_player_idx]
                eligible = get_eligible_nations(
                    active_player, global_cooldown_idx, nation_list)

                # --- Sidebar button click? ---
                btn = get_sidebar_button_at(sidebar_buttons, mx, my)
                if btn:
                    if (action_pending == btn['type']
                            and pending_nation is not None
                            and pending_nation.ring_index == btn['nation'].ring_index):
                        # Click same button again → cancel
                        action_pending = pending_nation = None
                        highlight_muster = highlight_promo = set()
                    else:
                        action_pending   = btn['type']
                        pending_nation   = btn['nation']
                        highlight_muster = set()
                        highlight_promo  = set()
                        if action_pending == 'recruit':
                            highlight_muster = set(grid.get_recruit_hexes(pending_nation))
                        else:
                            highlight_promo  = set(grid.get_promote_hexes(pending_nation))

                # --- Recruit placement ---
                elif action_pending == 'recruit':
                    tq, tr = grid.screen_to_axial(mx, my)
                    if (tq, tr) in highlight_muster:
                        grid.recruit_army(pending_nation, tq, tr)
                        moved_nation     = pending_nation
                        _move_data = moves_mod.serialize_move(
                            'recruit', pending_nation.ring_index,
                            to_hex=(tq, tr))
                        on_local_move_made(_move_data)
                        if game_mode == 'vs_bot':
                            bot_memory.record(turn_number, pending_nation,
                                              None, None, (tq, tr), 'recruit')
                        if settings.DEPLOYMENT == 'DEBUG':
                            print(f"[{active_player.player_id} recruit] T{turn_number} {pending_nation.color_name} at {(tq,tr)}  {_move_data}")
                        if game_mode == 'vs_bot':
                            bot_memory.add_score(pending_nation.ring_index, 2, settings.NATION_NAMES)
                        action_pending   = pending_nation = None
                        highlight_muster = highlight_promo = set()

                        active_player.add_to_cooldown(moved_nation)
                        global_cooldown_idx = moved_nation.ring_index
                        end = check_all_end_conditions(
                            grid, player1, player2, nation_list)
                        if end is not None:
                            game_state = STATE_GAME_OVER
                            game_result = end
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
                        # Click outside valid hexes → cancel
                        action_pending = pending_nation = None
                        highlight_muster = highlight_promo = set()

                # --- Promote selection ---
                elif action_pending == 'promote':
                    tq, tr = grid.screen_to_axial(mx, my)
                    if (tq, tr) in highlight_promo:
                        armies_here = [a for a in grid.armies.get((tq, tr), [])
                                       if a.nation.ring_index == pending_nation.ring_index]
                        if armies_here:
                            grid.promote_to_champion(armies_here[0])
                            moved_nation     = pending_nation
                            _move_data = moves_mod.serialize_move(
                                'promote', pending_nation.ring_index,
                                to_hex=(tq, tr))
                            on_local_move_made(_move_data)
                            if game_mode == 'vs_bot':
                                bot_memory.record(turn_number, pending_nation,
                                                  None, (tq, tr), None, 'promote')
                            if settings.DEPLOYMENT == 'DEBUG':
                                print(f"[{active_player.player_id} promote] T{turn_number} {pending_nation.color_name} at {(tq,tr)}  {_move_data}")
                            if game_mode == 'vs_bot':
                                bot_memory.add_score(pending_nation.ring_index, 2, settings.NATION_NAMES)
                            action_pending   = pending_nation = None
                            highlight_muster = highlight_promo = set()

                            active_player.add_to_cooldown(moved_nation)
                            global_cooldown_idx = moved_nation.ring_index
                            end = check_all_end_conditions(
                                grid, player1, player2, nation_list)
                            if end is not None:
                                game_state = STATE_GAME_OVER
                                game_result = end
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
                            highlight_move   = set(grid.get_valid_moves(unit, mover_secret_nation=active_player.secret_nation))
                            highlight_attack  = set(grid.get_valid_attacks(unit))
                            drag_mouse_pos   = (mx, my)
                        else:
                            error_message = (
                                f"{unit.nation.color_name} is on cooldown — pick another nation.")
                            error_alpha = 255.0

            # ---- Drag motion -----------------------------------------------
            elif event.type == pygame.MOUSEMOTION and drag_unit:
                drag_mouse_pos = event.pos

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
                    success, msg = grid.apply_move(drag_unit, tq, tr, mover_secret_nation=active_player.secret_nation)
                    if success:
                        moved_nation = drag_unit.nation
                        _move_data = moves_mod.serialize_move(
                            'move', drag_unit.nation.ring_index,
                            unit_type=_unit_type_snap,
                            from_hex=from_hex, to_hex=(tq, tr))
                        on_local_move_made(_move_data)
                        if game_mode == 'vs_bot':
                            bot_memory.record(turn_number, drag_unit.nation,
                                              drag_unit_type, from_hex, (tq, tr), 'move')
                        # Scoring (bot mode only)
                        ri = drag_unit.nation.ring_index
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
                            _target_ris.add(_u.nation.ring_index)
                    for _u in grid.champions.get((tq, tr), []):
                        if drag_unit.nation.is_enemy(_u.nation):
                            _target_ris.add(_u.nation.ring_index)
                    for _u in grid.armies.get((tq, tr), []):
                        if drag_unit.nation.is_enemy(_u.nation):
                            _target_ris.add(_u.nation.ring_index)
                    success, msg, _ = grid.resolve_attack(drag_unit, tq, tr)
                    if success:
                        moved_nation = drag_unit.nation
                        _move_data = moves_mod.serialize_move(
                            'attack', drag_unit.nation.ring_index,
                            unit_type=drag_unit_type,
                            from_hex=from_hex, to_hex=(tq, tr))
                        on_local_move_made(_move_data)
                        if game_mode == 'vs_bot':
                            bot_memory.record(turn_number, drag_unit.nation,
                                              drag_unit_type, from_hex, (tq, tr), 'attack')
                            _nnames = settings.NATION_NAMES
                            bot_memory.add_score(drag_unit.nation.ring_index, 2, _nnames)
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
                    global_cooldown_idx = moved_nation.ring_index
                    end = check_all_end_conditions(
                        grid, player1, player2, nation_list)
                    if end is not None:
                        game_state  = STATE_GAME_OVER
                        game_result = end
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
                    global_cooldown_idx = moved_nation.ring_index
                    if settings.DEPLOYMENT == 'DEBUG':
                        print(f"[Network] Received move: {incoming}")
                    end = check_all_end_conditions(
                        grid, player1, player2, nation_list)
                    if end is not None:
                        game_state  = STATE_GAME_OVER
                        game_result = end
                    else:
                        game_state = STATE_HUMAN_TURN
                elif settings.DEPLOYMENT == 'DEBUG':
                    print(f"[Network] Bad move from opponent: {msg}")

        # ── Bot thinking countdown ─────────────────────────────────────────
        if game_state == STATE_BOT_THINKING:
            bot_think_timer -= dt
            if bot_think_timer <= 0:
                # Compute the action (don't execute yet — animate first)
                _suspected = bot_memory.guess_faction(
                    nation_list,
                    exclude_ring_indices=(p2_nation.ring_index,))
                _suspected_ri = _suspected.ring_index if _suspected else None
                bot_pending_action = bot_ai.compute_bot_action(
                    grid, player2, global_cooldown_idx, nation_list,
                    turn_number, suspected_human_ri=_suspected_ri,
                    weights=evolved_bot_weights,
                    evolved_config=evolved_bot_config)
                if bot_pending_action is None:
                    # No legal move at all; skip straight to human turn
                    game_state         = STATE_HUMAN_TURN
                    current_player_idx = 0
                    turn_number       += 1
                else:
                    _, atype, *payload = bot_pending_action
                    actor, coord = payload[0], payload[1]
                    if atype in ('move', 'attack'):
                        bot_flash_hex = (actor.q, actor.r)
                        bot_flash_button_key = None
                    else:   # recruit / promote
                        ri = actor.ring_index
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
                    global_cooldown_idx = moved_nation.ring_index

                # Determine post-flash hex (destination)
                _, atype, *payload = bot_pending_action
                actor, coord = payload[0], payload[1]
                bot_flash_hex = coord
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

                end = check_all_end_conditions(
                    grid, player1, player2, nation_list)
                if end is not None:
                    game_state  = STATE_GAME_OVER
                    game_result = end
                else:
                    game_state         = STATE_HUMAN_TURN
                    current_player_idx = 0
                    turn_number       += 1

        # ── Error fade ────────────────────────────────────────────────────────
        if error_alpha > 0:
            error_alpha = max(0.0, error_alpha - dt * 0.4)
            if error_alpha == 0:
                error_message = ""

        # ── Draw ─────────────────────────────────────────────────────────────
        splash_mx, splash_my = pygame.mouse.get_pos()

        if game_state == STATE_SPLASH:
            splash_mod.draw_splash(screen, splash_fonts, p1_nation,
                                   splash_mx, splash_my, diplo_splash,
                                   evolved_available=has_evolved_configs)

        elif game_state == STATE_INSTRUCTIONS:
            _, inst_max_scroll = splash_mod.draw_instructions(
                screen, splash_fonts, rules_surfs,
                inst_scroll, splash_mx, splash_my)

        else:
            screen.fill(settings.COLOR_BACKGROUND)

            # Nations the active player cannot move right now → rendered as frozen
            active_player = players[current_player_idx]
            eligible_now      = get_eligible_nations(active_player, global_cooldown_idx, nation_list)
            eligible_ring_idx = {n.ring_index for n in eligible_now}
            frozen_ring_idx   = {n.ring_index for n in nation_list
                                 if n.ring_index not in eligible_ring_idx}
            ghost_ring_idx    = {n.ring_index for n in nation_list if n.is_ghost}

            grid.draw(screen,
                      highlight_move=highlight_move,
                      highlight_attack=highlight_attack,
                      drag_unit=drag_unit,
                      frozen_nations=frozen_ring_idx,
                      ghost_nations=ghost_ring_idx)

            # Action-pending highlights drawn on top of board
            hw, hh = grid.hex_width, grid.hex_height
            for (q, r) in highlight_muster:
                cx, cy = grid.screen_pos(q, r)
                grid.draw_hex_polygon(screen, cx, cy, hw - 2, hh - 2, (50, 220, 180), 3)
            for (q, r) in highlight_promo:
                cx, cy = grid.screen_pos(q, r)
                grid.draw_hex_polygon(screen, cx, cy, hw - 2, hh - 2, (220, 185, 40), 3)

            # Recompute sidebar buttons every frame (cheap) and draw them
            sidebar_buttons = compute_sidebar_buttons(grid, eligible_now)
            font_tiny = util.get_font(11)
            draw_sidebar_buttons(screen, grid, sidebar_buttons,
                                 action_pending, pending_nation, font_tiny)

            current_player = players[current_player_idx]
            # In vs_bot, always show the human's secret nation (player1)
            display_player = player1 if game_mode == 'vs_bot' else active_player
            draw_top_bar(screen, font_large, font_small,
                         display_player, current_player, turn_number,
                         game_state, game_mode)
            draw_diplo_panel(screen, diplo_img, font_small)
            draw_cooldown_panel(screen, font_small, players, global_cooldown_idx)
            draw_error(screen, font_small, error_message, error_alpha)

            # Debug: bot faction guess (top-left, below top bar) — DEBUG mode only
            if settings.DEPLOYMENT == 'DEBUG' and game_mode == 'vs_bot':
                _guess = bot_memory.guess_faction(
                    nation_list,
                    exclude_ring_indices=(p2_nation.ring_index,))
                if _guess:
                    _gt = f"Bot guess for player: {_guess.color_name}"
                    _gs = font_small.render(_gt, True, _guess.color_rgb)
                    screen.blit(_gs, (14, settings.TOP_BAR_HEIGHT + 8))

            # Drag ghost drawn last (on top of everything)
            if drag_unit and drag_unit_type:
                draw_drag_ghost(screen, drag_unit_type,
                                drag_unit.nation.color_rgb, *drag_mouse_pos)

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
                draw_game_over(screen, font_large, font_small, game_result)

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
