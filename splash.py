"""
Six Nations — Splash Screen & Instructions Screen
"""

import os
import math
import pygame

import settings
import util


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
    dy_half = hh // 2

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
    filled=True  → filled with (darker) nation color
    filled=False → transparent with white border
    hovered      → brighter highlight
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
            # underline gap
            result.append((None, 2))
            continue

        # Word-wrap body text
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

def draw_splash(screen, fonts, human_nation, mx, my, diplo_img=None,
                evolved_available=False):
    """
    Draw the splash screen.
    fonts    : dict with keys 'title','large','medium','small','btn'
    diplo_img: optional pre-scaled pygame.Surface for the Diplomacy Ring image
    evolved_available: if True, show a third mode button "EVOLVED BOT"
    Returns (bot_rect, human_rect, instructions_rect, evolved_rect_or_None).
    """
    W  = settings.SCREEN_WIDTH
    H  = settings.SCREEN_HEIGHT
    nc = human_nation.color_rgb

    # Vertical anchor — sit in the upper 40 % of the window so everything
    # lands comfortably on screen even with OS menu-bar / title-bar overhead.
    cy = int(H * 0.40)   # ~560 px on a 1400-px window

    # Background + hex tile pattern
    screen.fill(settings.COLOR_BACKGROUND)
    _draw_hex_bg(screen, nc, W, H)

    # Large watermark crown behind title
    wm_surf  = pygame.Surface((W, H), pygame.SRCALPHA)
    wm_color = (nc[0], nc[1], nc[2], 28)
    _draw_crown(wm_surf, W // 2, cy - 30, 210, wm_color)
    screen.blit(wm_surf, (0, 0))

    # -- Title --
    title_surf = fonts['title'].render("SIX NATIONS", True, (230, 236, 255))
    title_rect = title_surf.get_rect(center=(W // 2, cy - 100))
    screen.blit(title_surf, title_rect)

    # Diplomacy Ring images flanking the title
    if diplo_img:
        img_w, img_h = diplo_img.get_size()
        gap  = 30   # gap between title text and image inner edge
        ty   = cy - 100   # vertical centre (matches title centre)
        lx   = title_rect.left - gap - img_w // 2
        rx   = title_rect.right + gap + img_w // 2
        screen.blit(diplo_img, diplo_img.get_rect(center=(lx, ty)))
        screen.blit(diplo_img, diplo_img.get_rect(center=(rx, ty)))

    # Nation color accent line
    line_color = tuple(min(255, int(v * 0.9 + 30)) for v in nc)
    line_w = 420
    pygame.draw.rect(screen, line_color,
                     (W // 2 - line_w // 2, cy - 48, line_w, 3),
                     border_radius=2)

    # -- Faction reveal --
    sub = fonts['medium'].render("Your secret faction is", True, (145, 158, 190))
    screen.blit(sub, sub.get_rect(center=(W // 2, cy)))

    name_surf = fonts['large'].render(human_nation.color_name.upper(), True, nc)
    screen.blit(name_surf, name_surf.get_rect(center=(W // 2, cy + 54)))

    # Small crown icon beside the name
    icon_y  = cy + 54
    icon_x  = W // 2 - name_surf.get_width() // 2 - 36
    icon_x2 = W // 2 + name_surf.get_width() // 2 + 36
    _draw_crown(screen, icon_x,  icon_y, 20, nc)
    _draw_crown(screen, icon_x2, icon_y, 20, nc)

    # -- Buttons --
    bw, bh  = 230, 56
    gap     = 20    # gap between mode buttons

    evolved_rect = None

    if evolved_available:
        # Three mode buttons
        n_btns  = 3
        total_w = bw * n_btns + gap * (n_btns - 1)
        left_x  = W // 2 - total_w // 2

        bot_rect     = pygame.Rect(left_x,                   cy + 110, bw, bh)
        evolved_rect = pygame.Rect(left_x + bw + gap,        cy + 110, bw, bh)
        human_rect   = pygame.Rect(left_x + 2 * (bw + gap),  cy + 110, bw, bh)
    else:
        # Two mode buttons (original layout)
        total_w = bw * 2 + gap
        left_x  = W // 2 - total_w // 2

        bot_rect   = pygame.Rect(left_x,           cy + 110, bw, bh)
        human_rect = pygame.Rect(left_x + bw + gap, cy + 110, bw, bh)

    inst_rect  = pygame.Rect(W // 2 - 310 // 2, cy + 185, 310, bh)

    _draw_button(screen, fonts['btn'], "PLAY vs BOT",   bot_rect,   True,  nc,
                 bot_rect.collidepoint(mx, my))
    if evolved_available and evolved_rect:
        _draw_button(screen, fonts['btn'], "EVOLVED BOT", evolved_rect, True, nc,
                     evolved_rect.collidepoint(mx, my))
    _draw_button(screen, fonts['btn'], "PLAY vs HUMAN", human_rect, True,  nc,
                 human_rect.collidepoint(mx, my))
    _draw_button(screen, fonts['btn'], "INSTRUCTIONS",  inst_rect,  False, nc,
                 inst_rect.collidepoint(mx, my))

    return bot_rect, human_rect, inst_rect, evolved_rect


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

    # ── Header ─────────────────────────────────────────────────────────────
    HEADER_H = 90
    title_s = fonts['large'].render("HOW TO PLAY", True, (210, 220, 255))
    screen.blit(title_s, title_s.get_rect(center=(W // 2, HEADER_H // 2)))
    pygame.draw.line(screen, (80, 90, 130), (80, HEADER_H - 4), (W - 80, HEADER_H - 4), 1)

    # ── Sticky START button (always at bottom) ─────────────────────────────
    FOOTER_H = 80
    bw, bh   = 280, 54
    start_rect = pygame.Rect(W // 2 - bw // 2, H - FOOTER_H + (FOOTER_H - bh) // 2, bw, bh)
    pygame.draw.rect(screen, (22, 28, 48),
                     (0, H - FOOTER_H, W, FOOTER_H))
    pygame.draw.line(screen, (60, 70, 110),
                     (0, H - FOOTER_H), (W, H - FOOTER_H), 1)
    _draw_button(screen, fonts['btn'], "START GAME", start_rect, True, (80, 120, 200),
                 start_rect.collidepoint(mx, my))

    # ── Scrollable text area ────────────────────────────────────────────────
    TEXT_TOP  = HEADER_H + 10
    TEXT_BOT  = H - FOOTER_H - 10
    TEXT_H    = TEXT_BOT - TEXT_TOP
    TEXT_X    = 120
    TEXT_W    = W - TEXT_X * 2
    LINE_H    = 22

    # Compute total content height
    total_h = 0
    for surf, gap in rules_surfs:
        total_h += gap
        if surf:
            total_h += surf.get_height() + 4
    max_scroll = max(0, total_h - TEXT_H)
    scroll_y   = max(0, min(scroll_y, max_scroll))

    # Clip to text area and draw
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

    # Scroll bar
    if max_scroll > 0:
        bar_x   = W - 20
        bar_top = TEXT_TOP
        bar_bot = TEXT_BOT
        bar_h   = bar_bot - bar_top
        thumb_h = max(30, int(bar_h * TEXT_H / (total_h)))
        thumb_y = int(bar_top + (bar_h - thumb_h) * scroll_y / max_scroll)
        pygame.draw.rect(screen, (45, 52, 78),   (bar_x, bar_top, 8, bar_h), border_radius=4)
        pygame.draw.rect(screen, (100, 115, 165), (bar_x, thumb_y, 8, thumb_h), border_radius=4)

    # Fade gradients at top/bottom of text area
    for grad_y, direction in ((TEXT_TOP, 1), (TEXT_BOT, -1)):
        for i in range(32):
            alpha = int(255 * (1 - i / 32))
            fade  = pygame.Surface((TEXT_W + 80, 1), pygame.SRCALPHA)
            fade.fill((0, 0, 0, alpha))
            screen.blit(fade, (TEXT_X - 20, grad_y + i * direction))

    return start_rect, max_scroll
