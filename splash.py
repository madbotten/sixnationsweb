"""
Six Nations — Splash Screen & Instructions Screen
"""

import os
import math
import pygame

import settings
import util
from factions import NATIONS, NATIONS_BY_NAME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hex_pts(cx, cy, w, h):
    """Return the 6 pixel corners of a flat-top hexagon."""
    pts = []
    for i in range(6):
        angle = math.radians(60 * i)
        pts.append((cx + w / 2 * math.cos(angle),
                    cy + h / 2 * math.sin(angle)))
    return pts


def _draw_hex_bg(screen, nation_color, W, H):
    """Tile the background with faint translucent hex outlines."""
    nc = nation_color
    cols = []
    for v in nc:
        cols.append(max(0, min(255, int(v * 0.35 + 15))))
    tile_color = tuple(cols)

    hw, hh = 120, 104           # flat-top hex tile size
    dx      = hw * 3 // 4 * 2  # horizontal step (overlapping)

    for col in range(-1, W // dx + 2):
        for row in range(-1, H // hh + 3):
            cx = col * dx
            cy = row * hh + (hh // 2 if col % 2 else 0)
            pts = _hex_pts(cx, cy, hw, hh)
            pygame.draw.polygon(screen, tile_color, pts, 1)


def _draw_crown(screen, cx, cy, size, color):
    """Draw a decorative sovereign crown polygon."""
    s = size
    base_y = cy + int(s * 0.44)
    pts = [
        (cx - s,          base_y),
        (cx - s,          cy - int(s * 0.56)),
        (cx - int(s*0.4), cy - int(s * 0.10)),
        (cx,              cy - s             ),
        (cx + int(s*0.4), cy - int(s * 0.10)),
        (cx + s,          cy - int(s * 0.56)),
        (cx + s,          base_y            ),
    ]
    pygame.draw.polygon(screen, color, pts)
    dark = tuple(max(0, v - 60) for v in color)
    pygame.draw.polygon(screen, dark, pts, 3)


def _draw_button(screen, font, text, rect, filled, nation_color, hovered):
    """
    Draw a styled rounded-rect button.
    filled=True  -> filled with (darker) nation color
    filled=False -> transparent with white border
    hovered      -> brighter highlight
    """
    r = 10
    nc = nation_color

    if filled:
        base = tuple(min(255, int(v * 0.55 + 30)) for v in nc)
        hot  = tuple(min(255, int(v * 0.75 + 40)) for v in nc)
        fill = hot if hovered else base
        pygame.draw.rect(screen, fill, rect, border_radius=r)
        border = (255, 255, 255) if hovered else (200, 210, 240)
        pygame.draw.rect(screen, border, rect, width=2, border_radius=r)
    else:
        if hovered:
            ghost = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            ghost.fill((255, 255, 255, 28))
            screen.blit(ghost, rect.topleft)
        border = (200, 210, 240) if hovered else (130, 140, 170)
        pygame.draw.rect(screen, border, rect, width=2, border_radius=r)

    lbl = font.render(text, True, (240, 244, 255))
    screen.blit(lbl, lbl.get_rect(center=rect.center))
    return rect


def _draw_button_ex(screen, font, text, rect, nation_color, hovered, enabled):
    """Like _draw_button but renders greyed-out when not enabled."""
    if not enabled:
        pygame.draw.rect(screen, (18, 24, 40), rect, border_radius=10)
        pygame.draw.rect(screen, (38, 48, 72), rect, 2, border_radius=10)
        lbl = font.render(text, True, (50, 62, 95))
        screen.blit(lbl, lbl.get_rect(center=rect.center))
    else:
        _draw_button(screen, font, text, rect, True, nation_color, hovered)


# ---------------------------------------------------------------------------
# Prediction-box layout constants
# ---------------------------------------------------------------------------

_SLOT_H      = 70    # height of each prediction slot
_SLOT_GAP    = 8     # gap between slots
_BOX_LABEL_H = 44    # vertical space for the box label at the top
_BOX_PADDING = 12    # internal horizontal/vertical padding
_BOX_H       = (_BOX_LABEL_H + _BOX_PADDING
                + 3 * (_SLOT_H + _SLOT_GAP) - _SLOT_GAP
                + _BOX_PADDING + 10)   # ~308 px total

TILE_H = 86   # height of each nation tile in the right-column palette


def get_slot_rects(box_rect):
    """Return the 3 slot pygame.Rects for a prediction box.

    Public -- main.py uses this for drag hit-testing.
    """
    rects = []
    for i in range(3):
        y = box_rect.y + _BOX_LABEL_H + _BOX_PADDING + i * (_SLOT_H + _SLOT_GAP)
        rects.append(pygame.Rect(
            box_rect.x + _BOX_PADDING, y,
            box_rect.width - 2 * _BOX_PADDING, _SLOT_H))
    return rects


# ---------------------------------------------------------------------------
# Inner drawing helpers for the prediction UI
# ---------------------------------------------------------------------------

def _draw_army_sprite(surface, cx, cy, nation_color, size, faded=False):
    """Blit a tinted army sprite centred at (cx, cy) onto *surface*."""
    s = int(size * 0.42)
    icon_h = max(1, int(s * 2.0))
    template = util.load_image('army.png', alpha=True)
    if template is None:
        pygame.draw.circle(surface, nation_color, (int(cx), int(cy)), max(1, size // 2))
        return
    icon_w = max(1, int(icon_h * template.get_width() / template.get_height()))
    color  = tuple(int(v * 0.45) for v in nation_color) if faded else nation_color
    sprite = util.load_tinted_sprite('army.png', color, icon_w, icon_h)
    if sprite is not None:
        if faded:
            sprite = sprite.copy()
            sprite.set_alpha(80)
        surface.blit(sprite, sprite.get_rect(center=(int(cx), int(cy))))


def _draw_prediction_box(screen, fonts, rect, label, label_color, nations):
    """Draw one PREVAIL or DEFEAT prediction box with its placed nation slots."""
    pygame.draw.rect(screen, (11, 16, 28), rect, border_radius=14)
    pygame.draw.rect(screen, label_color, rect, 2, border_radius=14)

    lbl_surf = fonts['large'].render(label, True, label_color)
    screen.blit(lbl_surf, (rect.x + 18, rect.y + 10))

    _draw_army_sprite(screen,
                      rect.x + 20 + lbl_surf.get_width() + 36,
                      rect.y + _BOX_LABEL_H // 2,
                      label_color, 28)

    _SLOT_POINTS = ("3 points", "2 points", "1 point")

    for i, slot_rect in enumerate(get_slot_rects(rect)):
        if i < len(nations):
            nation = nations[i]
            c  = nation.color_rgb
            bg = tuple(int(v * 0.18 + 8) for v in c)
            pygame.draw.rect(screen, bg, slot_rect, border_radius=8)
            pygame.draw.rect(screen, c,  slot_rect, 1, border_radius=8)

            icon_size = int(_SLOT_H * 0.55)
            _draw_army_sprite(screen,
                              slot_rect.x + _BOX_PADDING + icon_size,
                              slot_rect.centery, c, icon_size)

            name_col  = tuple(min(255, int(v * 1.1 + 20)) for v in c)
            name_surf = fonts['medium'].render(nation.color_name, True, name_col)
            screen.blit(name_surf, name_surf.get_rect(
                midleft=(slot_rect.x + _BOX_PADDING * 2 + icon_size * 2 + 4,
                         slot_rect.centery)))
        else:
            # Empty slot — show point-value hint; overdrawn once a flag is placed
            pygame.draw.rect(screen, (16, 22, 36), slot_rect, border_radius=8)
            pygame.draw.rect(screen, (40, 52, 80), slot_rect, 1, border_radius=8)
            pts_text = _SLOT_POINTS[i] if i < len(_SLOT_POINTS) else ""
            pts_surf = fonts['medium'].render(pts_text, True, (52, 68, 108))
            screen.blit(pts_surf, pts_surf.get_rect(center=slot_rect.center))


def _draw_nation_tile(screen, fonts, rect, nation, is_placed, hovered):
    """Draw a draggable nation tile in the right-column palette."""
    c = nation.color_rgb

    if is_placed:
        bg         = tuple(int(v * 0.07 + 4) for v in c)
        border_col = tuple(int(v * 0.22) for v in c)
        text_col   = tuple(int(v * 0.30) for v in c)
    else:
        bg         = tuple(int(v * 0.22 + 12) for v in c)
        if hovered:
            bg     = tuple(int(v * 0.38 + 16) for v in c)
        border_col = tuple(min(255, int(v * 0.80 + 20)) for v in c)
        if hovered:
            border_col = c
        text_col   = c

    pygame.draw.rect(screen, bg, rect, border_radius=10)
    pygame.draw.rect(screen, border_col, rect, 2, border_radius=10)

    icon_size = int(rect.height * 0.58)
    icon_cx   = rect.x + 20 + icon_size // 2
    _draw_army_sprite(screen, icon_cx, rect.centery, c, icon_size, is_placed)

    name_surf = fonts['large'].render(nation.color_name, True, text_col)
    screen.blit(name_surf, name_surf.get_rect(
        midleft=(icon_cx + icon_size // 2 + 16, rect.centery)))

    if hovered and not is_placed:
        hint = fonts['small'].render("drag to PREVAIL or DEFEAT", True, (140, 158, 200))
        screen.blit(hint, hint.get_rect(midright=(rect.right - 16, rect.centery)))


# ---------------------------------------------------------------------------
# Rules text pre-processing
# ---------------------------------------------------------------------------

def _is_section_header(line):
    """Detect an ALL-CAPS section heading."""
    s = line.strip()
    if not s or len(s) < 2:
        return False
    return s.isupper() or (not any(c.islower() for c in s) and any(c.isalpha() for c in s))


def build_rules_surfaces(raw_text, font_h, font_b, max_width):
    """
    Return a list of (surface_or_None, extra_gap_above).
    surface=None means a vertical gap only.
    """
    result = []
    for raw_line in raw_text.split('\n'):
        line = raw_line.rstrip()
        if not line:
            result.append((None, 10))
            continue

        if _is_section_header(line):
            surf = font_h.render(line, True, (255, 255, 255))
            result.append((surf, 22))
            result.append((None, 2))
            continue

        words = line.split()
        cur = []
        for word in words:
            test = ' '.join(cur + [word])
            if font_b.size(test)[0] <= max_width:
                cur.append(word)
            else:
                if cur:
                    s = font_b.render(' '.join(cur), True, (255, 255, 255))
                    result.append((s, 0))
                cur = [word]
        if cur:
            s = font_b.render(' '.join(cur), True, (255, 255, 255))
            result.append((s, 0))

    return result


# ---------------------------------------------------------------------------
# Public drawing functions
# ---------------------------------------------------------------------------

def draw_splash(screen, fonts, human_nation=None, mx=0, my=0,
                prevail_nations=None, defeat_nations=None,
                drag_nation=None, drag_pos=None,
                buttons_enabled=False):
    """
    Draw the splash screen with two-column prediction layout.

    Left column  : PREVAIL and DEFEAT prediction boxes.
    Right column : Six draggable nation tiles.
    Bottom strip : Mode buttons (disabled until 6 picks made) + INSTRUCTIONS.

    Returns
    -------
    (bot_rect, human_rect, inst_rect, evolved_rect,
     prevail_rect, defeat_rect, tile_rects)
    where tile_rects is dict {color_name: pygame.Rect}.
    """
    prevail_nations = prevail_nations or []
    defeat_nations  = defeat_nations  or []

    W  = settings.SCREEN_WIDTH
    H  = settings.SCREEN_HEIGHT
    nc = human_nation.color_rgb if human_nation is not None else (200, 180, 100)

    screen.fill(settings.COLOR_BACKGROUND)
    _draw_hex_bg(screen, nc, W, H)

    # Layout
    TITLE_H   = 164
    BTN_STRIP = 108
    CONTENT_Y = TITLE_H
    CONTENT_H = H - TITLE_H - BTN_STRIP
    LEFT_W    = 950
    RIGHT_X   = 992

    # Watermark crown
    wm_surf = pygame.Surface((W, H), pygame.SRCALPHA)
    _draw_crown(wm_surf, W // 2, TITLE_H // 2, 110, (nc[0], nc[1], nc[2], 18))
    screen.blit(wm_surf, (0, 0))

    # Title strip
    title_surf = fonts['title'].render("SIX NATIONS", True, (228, 234, 255))
    screen.blit(title_surf, title_surf.get_rect(centerx=W // 2, centery=50))

    line_col = (180, 195, 230)
    lw = 420
    pygame.draw.rect(screen, line_col, (W // 2 - lw // 2, 88, lw, 2), border_radius=1)

    sub_surf  = fonts['large'].render("Choose your secret goals", True, (228, 234, 255))
    sub_rect  = sub_surf.get_rect(centerx=W // 2, centery=125)
    screen.blit(sub_surf, sub_rect)
    crown_col = (212, 175, 55)
    _draw_crown(screen, sub_rect.left - 28, 125, 13, crown_col)
    _draw_crown(screen, sub_rect.right + 28, 125, 13, crown_col)

    pygame.draw.line(screen, settings.COLOR_HEX_BORDER, (0, TITLE_H), (W, TITLE_H), 1)

    # Column divider
    pygame.draw.line(screen, settings.COLOR_HEX_BORDER,
                     (LEFT_W, CONTENT_Y + 20), (LEFT_W, H - BTN_STRIP - 20), 1)

    # Left column: prediction boxes — centred horizontally AND vertically
    BOX_W          = 860
    BOX_X          = (LEFT_W - BOX_W) // 2
    BOX_GAP        = 34
    BOX_TOTAL_H    = 2 * _BOX_H + BOX_GAP
    BOX_Y_PREVAIL  = CONTENT_Y + (CONTENT_H - BOX_TOTAL_H) // 2
    BOX_Y_DEFEAT   = BOX_Y_PREVAIL + _BOX_H + BOX_GAP

    prevail_rect = pygame.Rect(BOX_X, BOX_Y_PREVAIL, BOX_W, _BOX_H)
    defeat_rect  = pygame.Rect(BOX_X, BOX_Y_DEFEAT,  BOX_W, _BOX_H)

    _draw_prediction_box(screen, fonts, prevail_rect, "PREVAIL",
                         (52, 210, 96), prevail_nations)
    _draw_prediction_box(screen, fonts, defeat_rect,  "DEFEAT",
                         (220, 65, 55), defeat_nations)

    # Right column: nation palette
    placed_set = {n.color_name for n in prevail_nations + defeat_nations}
    if drag_nation is not None:
        placed_set.discard(drag_nation.color_name)

    TILE_W   = W - RIGHT_X - 44
    TILE_GAP = 18
    tile_total_h = 6 * TILE_H + 5 * TILE_GAP
    tile_start_y = CONTENT_Y + (CONTENT_H - tile_total_h) // 2

    col_hdr = fonts['medium'].render("NATIONS", True, settings.COLOR_TEXT_MUTED)
    screen.blit(col_hdr, col_hdr.get_rect(x=RIGHT_X, y=CONTENT_Y + 8))

    tile_rects = {}
    for idx, nation in enumerate(NATIONS):
        name      = nation.color_name
        ty        = tile_start_y + idx * (TILE_H + TILE_GAP)
        tile_rect = pygame.Rect(RIGHT_X, ty, TILE_W, TILE_H)
        tile_rects[name] = tile_rect
        is_placed = name in placed_set
        hovered   = tile_rect.collidepoint(mx, my) and not is_placed
        _draw_nation_tile(screen, fonts, tile_rect, nation, is_placed, hovered)

    # Hint text
    n_placed = len(prevail_nations) + len(defeat_nations)
    n_needed = 6 - n_placed
    if not buttons_enabled and n_needed > 0:
        hint_text = ("Place " + str(n_needed) + " more flag"
                     + ("s" if n_needed != 1 else "")
                     + " to unlock the game buttons")
        hint_surf = fonts['small'].render(hint_text, True, (72, 88, 138))
        screen.blit(hint_surf, hint_surf.get_rect(centerx=W // 2, y=H - BTN_STRIP + 8))

    # Bottom button strip — always 2 buttons: BOT + HUMAN
    BTN_Y = H - BTN_STRIP + (BTN_STRIP - 56) // 2 + 14
    bw, bh = 230, 56
    gap    = 20
    total_w = bw * 2 + gap
    left_x  = W // 2 - total_w // 2 - 180
    bot_rect   = pygame.Rect(left_x,             BTN_Y, bw, bh)
    human_rect = pygame.Rect(left_x + bw + gap,  BTN_Y, bw, bh)
    evolved_rect = None

    inst_rect = pygame.Rect(W - 294, BTN_Y, 254, bh)

    _draw_button_ex(screen, fonts['btn'], "PLAY vs BOT",   bot_rect, nc,
                    bot_rect.collidepoint(mx, my), buttons_enabled)
    _draw_button_ex(screen, fonts['btn'], "PLAY vs HUMAN", human_rect, nc,
                    human_rect.collidepoint(mx, my), buttons_enabled)
    _draw_button(screen, fonts['btn'], "INSTRUCTIONS", inst_rect, False, nc,
                 inst_rect.collidepoint(mx, my))

    # Drag ghost
    if drag_nation is not None and drag_pos is not None:
        dgx, dgy = drag_pos
        ghost_w, ghost_h = 320, TILE_H
        gs = pygame.Surface((ghost_w, ghost_h), pygame.SRCALPHA)
        c  = drag_nation.color_rgb
        bg = tuple(int(v * 0.38 + 16) for v in c)
        pygame.draw.rect(gs, (*bg, 210), (0, 0, ghost_w, ghost_h), border_radius=10)
        pygame.draw.rect(gs, (*c,  230), (0, 0, ghost_w, ghost_h), 2, border_radius=10)
        icon_size = int(ghost_h * 0.58)
        _draw_army_sprite(gs, 20 + icon_size // 2, ghost_h // 2, c, icon_size)
        name_s = fonts['medium'].render(drag_nation.color_name, True, c)
        gs.blit(name_s, name_s.get_rect(midleft=(20 + icon_size + 12, ghost_h // 2)))
        screen.blit(gs, (dgx - ghost_w // 2, dgy - ghost_h // 2))

    return (bot_rect, human_rect, inst_rect, evolved_rect,
            prevail_rect, defeat_rect, tile_rects)


def draw_instructions(screen, fonts, rules_surfs, scroll_y, mx, my):
    """
    Draw the scrollable instructions screen.
    rules_surfs: output of build_rules_surfaces().
    Returns (start_rect, max_scroll).
    """
    W  = settings.SCREEN_WIDTH
    H  = settings.SCREEN_HEIGHT
    nc = (130, 145, 200)   # neutral accent color for instructions

    screen.fill((0, 0, 0))

    HEADER_H = 90
    title_s = fonts['large'].render("HOW TO PLAY", True, (210, 220, 255))
    screen.blit(title_s, title_s.get_rect(center=(W // 2, HEADER_H // 2)))
    pygame.draw.line(screen, (80, 90, 130), (80, HEADER_H - 4), (W - 80, HEADER_H - 4), 1)

    FOOTER_H = 80
    bw, bh   = 280, 54
    start_rect = pygame.Rect(W // 2 - bw // 2, H - FOOTER_H + (FOOTER_H - bh) // 2, bw, bh)
    pygame.draw.rect(screen, (22, 28, 48), (0, H - FOOTER_H, W, FOOTER_H))
    pygame.draw.line(screen, (60, 70, 110), (0, H - FOOTER_H), (W, H - FOOTER_H), 1)
    _draw_button(screen, fonts['btn'], "BACK TO MENU", start_rect, True, (80, 120, 200),
                 start_rect.collidepoint(mx, my))

    TEXT_TOP  = HEADER_H + 10
    TEXT_BOT  = H - FOOTER_H - 10
    TEXT_H    = TEXT_BOT - TEXT_TOP
    TEXT_X    = 120
    TEXT_W    = W - TEXT_X * 2

    total_h = 0
    for surf, gap in rules_surfs:
        total_h += gap
        if surf:
            total_h += surf.get_height() + 4
    max_scroll = max(0, total_h - TEXT_H)
    scroll_y   = max(0, min(scroll_y, max_scroll))

    clip_rect = pygame.Rect(TEXT_X - 20, TEXT_TOP, TEXT_W + 40, TEXT_H)
    screen.set_clip(clip_rect)

    y = TEXT_TOP - scroll_y
    for surf, gap in rules_surfs:
        y += gap
        if surf:
            if TEXT_TOP - surf.get_height() <= y <= TEXT_BOT:
                screen.blit(surf, (TEXT_X, y))
            y += surf.get_height() + 4

    screen.set_clip(None)

    if max_scroll > 0:
        bar_x   = W - 20
        bar_top = TEXT_TOP
        bar_bot = TEXT_BOT
        bar_h   = bar_bot - bar_top
        thumb_h = max(30, int(bar_h * TEXT_H / (total_h)))
        thumb_y = int(bar_top + (bar_h - thumb_h) * scroll_y / max_scroll)
        pygame.draw.rect(screen, (45, 52, 78),   (bar_x, bar_top, 8, bar_h), border_radius=4)
        pygame.draw.rect(screen, (100, 115, 165), (bar_x, thumb_y, 8, thumb_h), border_radius=4)

    for grad_y, direction in ((TEXT_TOP, 1), (TEXT_BOT, -1)):
        for i in range(32):
            alpha = int(255 * (1 - i / 32))
            fade  = pygame.Surface((TEXT_W + 80, 1), pygame.SRCALPHA)
            fade.fill((0, 0, 0, alpha))
            screen.blit(fade, (TEXT_X - 20, grad_y + i * direction))

    return start_rect, max_scroll
