"""
Diplomacy Panel for Six Nations.

Renders a persistent diplomacy interface on the right side of the screen containing
six nation boxes. Each box displays the stances other nations hold toward that nation
(foreign-coloured flags in ally and war rows) and available neutral slots (own-coloured
flags in the home row).

Players can drag flags to:
- Declare war / alliance (from home to enemy/ally row)
- End war / alliance (from enemy/ally row back to flag's home box)
- Renew war / alliance (re-drop on same row)
"""

import random
from dataclasses import dataclass
import pygame

import settings
import util
from factions import Nation

NATION_ABBREV = {
    'Yilerond':  'YIL',
    'Galland':   'GAL',
    'Beldrin':   'BEL',
    'Crestmoor': 'CRE',
    'Malkor':    'MAL',
    'Ravengard': 'RAV',
}


@dataclass
class _FlagSlot:
    slot_idx: int
    flag_nation: Nation
    zone: str              # 'home' | 'ally' | 'war'
    locked: bool
    partner: Nation | None # the partner nation representing this relationship
    rect: pygame.Rect


@dataclass
class _DragState:
    flag_nation: Nation    # nation of the flag being dragged
    from_box: Nation       # nation of the box the flag was taken from
    from_zone: str         # 'home' | 'ally' | 'war'
    from_index: int        # index within that zone's row
    mouse_offset: tuple[int, int]
    curr_pos: tuple[int, int]


@dataclass
class DiplomacyAction:
    box_nation: Nation     # the partner nation involved in the action
    flag_nation: Nation    # the nation of the moved flag
    from_zone: str         # 'home' | 'ally' | 'war'
    to_zone: str           # 'home' | 'ally' | 'war'


class DiplomacyState:
    """Pure-Python (no pygame) diplomacy cooldown tracker.

    Tracks which nation-pairs are on cooldown after a stance change.
    Used by both DiplomacyPanel (UI layer) and headless HeadlessGame (evolution).
    """

    def __init__(self):
        # Cooldowns keyed by frozenset({name_a, name_b}) -> turns_remaining (int)
        self.cooldowns: dict = {}

    def reset(self):
        """Clear all cooldowns."""
        self.cooldowns.clear()

    def lock_pair(self, a, b):
        """Lock diplomacy between two nations for a secret random duration."""
        cd = random.randint(settings.DIPL_COOLDOWN_MIN, settings.DIPL_COOLDOWN_MAX)
        self.cooldowns[frozenset({a.color_name, b.color_name})] = cd

    def unlock_pair(self, a, b):
        """Remove cooldown lock between two nations."""
        self.cooldowns.pop(frozenset({a.color_name, b.color_name}), None)

    def is_locked(self, a, b) -> bool:
        """True if relationship between nation a and nation b is on cooldown."""
        return self.cooldowns.get(frozenset({a.color_name, b.color_name}), 0) > 0

    def tick_cooldowns(self):
        """Decrement all active cooldowns by 1. Call after every turn (human or bot)."""
        expired = []
        for pair in list(self.cooldowns.keys()):
            self.cooldowns[pair] -= 1
            if self.cooldowns[pair] <= 0:
                expired.append(pair)
        for pair in expired:
            del self.cooldowns[pair]


class DiplomacyPanel:
    """Manages the 6-nation diplomacy boxes on the right sidebar."""

    def __init__(self, nations: list[Nation]):
        self.nations = nations
        self.state   = DiplomacyState()   # pure-Python cooldown tracker
        self.drag: _DragState | None = None
        self.mouse_pos: tuple[int, int] = (0, 0)

    # -------------------------------------------------------------------------
    # Public State API  (delegate to self.state for cooldown ops)
    # -------------------------------------------------------------------------

    def reset(self):
        """Clear all cooldowns and active drag state."""
        self.state.reset()
        self.drag = None

    def lock_pair(self, a: Nation, b: Nation):
        """Lock diplomacy between two nations for a secret random duration."""
        self.state.lock_pair(a, b)

    def unlock_pair(self, a: Nation, b: Nation):
        """Remove cooldown lock between two nations."""
        self.state.unlock_pair(a, b)

    def is_locked(self, a: Nation, b: Nation) -> bool:
        """True if relationship between nation a and nation b is on cooldown."""
        return self.state.is_locked(a, b)

    def tick_cooldowns(self):
        """Decrement all active cooldowns by 1. Call after every turn (human or bot)."""
        self.state.tick_cooldowns()



    # -------------------------------------------------------------------------
    # Layout and Geometry Helpers
    # -------------------------------------------------------------------------

    def _box_rect(self, index: int) -> pygame.Rect:
        return pygame.Rect(
            settings.DIPL_PANEL_X,
            settings.DIPL_PANEL_Y + index * (settings.DIPL_BOX_H + settings.DIPL_BOX_GAP),
            settings.DIPL_PANEL_W,
            settings.DIPL_BOX_H,
        )

    def _get_box_and_index_at(self, pos: tuple[int, int]) -> tuple[Nation, int, pygame.Rect] | None:
        mx, my = pos
        for i, nation in enumerate(self.nations):
            rect = self._box_rect(i)
            if rect.collidepoint(mx, my):
                return nation, i, rect
        return None

    def _slot_rect(self, box_rect: pygame.Rect, zone: str, slot_index: int) -> pygame.Rect:
        x = box_rect.x + 60 + slot_index * (settings.DIPL_FLAG_W + settings.DIPL_FLAG_GAP)
        if zone == 'home':
            y = box_rect.y + 34
        elif zone == 'ally':
            y = box_rect.y + 86
        else:  # 'war'
            y = box_rect.y + 138
        return pygame.Rect(x, y, settings.DIPL_FLAG_W, settings.DIPL_FLAG_H)


    def _flag_slots_for_box(self, box_nation: Nation, box_rect: pygame.Rect) -> list[_FlagSlot]:
        """Compute all flag slots displayed inside a nation's box."""
        slots: list[_FlagSlot] = []

        # 1. Home row: own-coloured flags for neutral capacity.
        # Home flags are NEVER locked; flags only lock in war or ally rows.
        for idx in range(min(5, len(box_nation.neutrals))):
            rect = self._slot_rect(box_rect, 'home', idx)
            slots.append(_FlagSlot(
                slot_idx=idx,
                flag_nation=box_nation,
                zone='home',
                locked=False,
                partner=None,
                rect=rect,
            ))


        # 2. Ally row: foreign-coloured flags for allied nations.
        for idx, ally in enumerate(box_nation.allies):
            if idx >= 5:
                break
            rect = self._slot_rect(box_rect, 'ally', idx)
            locked = self.is_locked(box_nation, ally)
            slots.append(_FlagSlot(
                slot_idx=idx,
                flag_nation=ally,
                zone='ally',
                locked=locked,
                partner=ally,
                rect=rect,
            ))

        # 3. War row: foreign-coloured flags for enemy nations.
        for idx, enemy in enumerate(box_nation.enemies):
            if idx >= 5:
                break
            rect = self._slot_rect(box_rect, 'war', idx)
            locked = self.is_locked(box_nation, enemy)
            slots.append(_FlagSlot(
                slot_idx=idx,
                flag_nation=enemy,
                zone='war',
                locked=locked,
                partner=enemy,
                rect=rect,
            ))

        return slots

    def _get_drop_zone(self, box_nation: Nation, box_rect: pygame.Rect,
                        pos: tuple[int, int]) -> str:
        """Classify which zone within a nation's box pos falls into."""
        rel_y = pos[1] - box_rect.y
        if rel_y < 74:
            return 'home'
        elif rel_y < 126:
            return 'ally'
        else:
            return 'war'

    # -------------------------------------------------------------------------
    # Mouse Event Handling
    # -------------------------------------------------------------------------

    def on_mousedown(self, pos: tuple[int, int]) -> bool:
        """Handle mouse down. Returns True if the diplomacy panel consumed the click."""
        mx, my = pos
        # If click is outside the panel area, do not consume
        if mx < settings.DIPL_PANEL_X - 10:
            return False

        # Hit test flags
        for i, nation in enumerate(self.nations):
            box_rect = self._box_rect(i)
            if not box_rect.collidepoint(mx, my):
                continue

            slots = self._flag_slots_for_box(nation, box_rect)
            for slot in slots:
                if slot.rect.collidepoint(mx, my):
                    if slot.locked:
                        # Locked flags cannot be dragged
                        return True
                    # Start dragging this flag
                    self.drag = _DragState(
                        flag_nation=slot.flag_nation,
                        from_box=nation,
                        from_zone=slot.zone,
                        from_index=slot.slot_idx,
                        mouse_offset=(mx - slot.rect.x, my - slot.rect.y),
                        curr_pos=pos,
                    )
                    return True
            # Click was inside the box but not on a flag
            return True

        # Click was on panel background
        return True

    def on_mousemotion(self, pos: tuple[int, int]):
        """Update current mouse position for hover effects and active drag."""
        self.mouse_pos = pos
        if self.drag is not None:
            self.drag.curr_pos = pos

    def on_mouseup(self, pos: tuple[int, int]) -> DiplomacyAction | None:
        """
        Handle mouse release.
        Returns a valid DiplomacyAction if a legal drop occurred, or None to cancel/snap back.
        """
        if self.drag is None:
            return None

        ds = self.drag
        self.drag = None

        hit = self._get_box_and_index_at(pos)
        if not hit:
            # Dropped outside any nation box -> cancel
            return None

        target_box, _, target_rect = hit
        target_zone = self._get_drop_zone(target_box, target_rect, pos)

        # ---------------------------------------------------------------------
        # Validation Rules
        # ---------------------------------------------------------------------

        # Case 1: RENEW (drop flag back on same zone of same box)
        if (ds.from_zone in ('war', 'ally')
                and target_box == ds.from_box
                and target_zone == ds.from_zone):
            if not self.is_locked(ds.flag_nation, ds.from_box):
                return DiplomacyAction(
                    box_nation=ds.from_box,
                    flag_nation=ds.flag_nation,
                    from_zone=ds.from_zone,
                    to_zone=ds.from_zone,
                )
            return None

        # Case 2: END RELATIONSHIP (war or ally flag dropped anywhere on flag's own box)
        if (ds.from_zone in ('war', 'ally')
                and target_box == ds.flag_nation):
            if not self.is_locked(ds.flag_nation, ds.from_box):
                return DiplomacyAction(
                    box_nation=ds.from_box,
                    flag_nation=ds.flag_nation,
                    from_zone=ds.from_zone,
                    to_zone='home',
                )
            return None

        # Case 3: DECLARE WAR (home flag dropped onto target's war row)
        if (ds.from_zone == 'home'
                and target_zone == 'war'
                and target_box != ds.flag_nation
                and ds.flag_nation.get_stance(target_box) == 'neutral'):
            return DiplomacyAction(
                box_nation=target_box,
                flag_nation=ds.flag_nation,
                from_zone='home',
                to_zone='war',
            )

        # Case 4: DECLARE ALLIANCE (home flag dropped onto target's ally row)
        if (ds.from_zone == 'home'
                and target_zone == 'ally'
                and target_box != ds.flag_nation
                and ds.flag_nation.get_stance(target_box) == 'neutral'):
            return DiplomacyAction(
                box_nation=target_box,
                flag_nation=ds.flag_nation,
                from_zone='home',
                to_zone='ally',
            )

        # All other moves (war <-> ally direct swap, home to home, etc.) are blocked
        return None

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, fonts: dict | None = None):
        """Render the complete diplomacy panel on the right sidebar."""
        font_title = util.get_font(14, bold=True)
        font_label = util.get_font(11, bold=True)
        font_micro = util.get_font(11)

        # Precompute army sprite dimensions from template
        template = util.load_image('army.png', alpha=True)
        icon_h = 24
        icon_w = int(icon_h * (template.get_width() / template.get_height())) if template else 21

        # 1. Panel Container Background
        panel_rect = pygame.Rect(
            settings.DIPL_PANEL_X - 10,
            settings.TOP_BAR_HEIGHT,
            settings.DIPL_PANEL_W + 20,
            settings.SCREEN_HEIGHT - settings.TOP_BAR_HEIGHT,
        )
        pygame.draw.rect(screen, settings.COLOR_PANEL, panel_rect)
        pygame.draw.line(
            screen,
            settings.COLOR_PANEL_BORDER,
            (panel_rect.x, panel_rect.y),
            (panel_rect.x, panel_rect.bottom),
            2,
        )

        hovered_valid_action: str | None = None
        hover_action_pos: tuple[int, int] = (0, 0)

        # 2. Draw each nation's box
        for i, nation in enumerate(self.nations):
            box_rect = self._box_rect(i)

            # Box Card Background
            pygame.draw.rect(screen, (18, 23, 35), box_rect, border_radius=8)
            pygame.draw.rect(screen, (36, 46, 68), box_rect, 1, border_radius=8)

            # Check if this box is hovered while dragging
            is_box_hovered = (
                self.drag is not None and box_rect.collidepoint(self.drag.curr_pos)
            )

            # Top Accent / Header
            color_pill = pygame.Rect(box_rect.x + 12, box_rect.y + 9, 10, 14)
            pygame.draw.rect(screen, nation.color_rgb, color_pill, border_radius=3)

            title_surf = font_title.render(nation.color_name.upper(), True, settings.COLOR_TEXT_PRIMARY)
            screen.blit(title_surf, (box_rect.x + 28, box_rect.y + 7))

            # Header info (ghost or counts)
            if nation.is_ghost:
                fallen_surf = font_label.render("FALLEN", True, (220, 60, 60))
                screen.blit(fallen_surf, (box_rect.right - 55, box_rect.y + 9))
            else:
                summary_txt = f"Allies: {len(nation.allies)}  Wars: {len(nation.enemies)}"
                summary_surf = font_micro.render(summary_txt, True, (115, 128, 155))
                screen.blit(summary_surf, (box_rect.right - summary_surf.get_width() - 12, box_rect.y + 9))

            # Row Dividers and Labels
            # Home Row
            home_lbl = font_label.render("HOME", True, (120, 130, 150))
            screen.blit(home_lbl, (box_rect.x + 12, box_rect.y + 43))

            # Ally Row
            pygame.draw.line(
                screen, (30, 40, 56),
                (box_rect.x + 12, box_rect.y + 74),
                (box_rect.right - 12, box_rect.y + 74), 1
            )
            ally_lbl = font_label.render("ALLY", True, (65, 205, 120))
            screen.blit(ally_lbl, (box_rect.x + 12, box_rect.y + 95))

            # War Row
            pygame.draw.line(
                screen, (30, 40, 56),
                (box_rect.x + 12, box_rect.y + 126),
                (box_rect.right - 12, box_rect.y + 126), 1
            )
            war_lbl = font_label.render("WAR", True, (235, 65, 75))
            screen.blit(war_lbl, (box_rect.x + 12, box_rect.y + 147))

            # Dynamic Drag Target Zone Highlighting
            if is_box_hovered and self.drag:
                ds = self.drag
                target_zone = self._get_drop_zone(nation, box_rect, ds.curr_pos)

                # Renew highlight
                if (ds.from_zone in ('war', 'ally')
                        and nation == ds.from_box
                        and target_zone == ds.from_zone
                        and not self.is_locked(ds.flag_nation, ds.from_box)):
                    zone_rect = pygame.Rect(
                        box_rect.x + 6,
                        box_rect.y + (80 if ds.from_zone == 'ally' else 132),
                        box_rect.width - 12, 46
                    )
                    pygame.draw.rect(screen, (245, 195, 45), zone_rect, 2, border_radius=6)
                    hovered_valid_action = f"Renew {ds.from_zone.upper()}"
                    hover_action_pos = (zone_rect.right - 120, zone_rect.y + 4)

                # End war/ally (return to own box)
                elif (ds.from_zone in ('war', 'ally')
                      and nation == ds.flag_nation
                      and not self.is_locked(ds.flag_nation, ds.from_box)):
                    pygame.draw.rect(screen, (80, 200, 255), box_rect, 2, border_radius=8)
                    hovered_valid_action = "Return Home (Neutral)"
                    hover_action_pos = (box_rect.centerx - 70, box_rect.y + 42)

                # Declare war
                elif (ds.from_zone == 'home'
                      and target_zone == 'war'
                      and nation != ds.flag_nation
                      and ds.flag_nation.get_stance(nation) == 'neutral'):
                    war_zone_rect = pygame.Rect(box_rect.x + 6, box_rect.y + 132, box_rect.width - 12, 46)
                    pygame.draw.rect(screen, (235, 65, 75), war_zone_rect, 2, border_radius=6)
                    hovered_valid_action = f"Declare WAR on {nation.color_name}"
                    hover_action_pos = (war_zone_rect.right - 160, war_zone_rect.y + 4)

                # Declare ally
                elif (ds.from_zone == 'home'
                      and target_zone == 'ally'
                      and nation != ds.flag_nation
                      and ds.flag_nation.get_stance(nation) == 'neutral'):
                    ally_zone_rect = pygame.Rect(box_rect.x + 6, box_rect.y + 80, box_rect.width - 12, 46)
                    pygame.draw.rect(screen, (65, 205, 120), ally_zone_rect, 2, border_radius=6)
                    hovered_valid_action = f"Declare ALLIANCE with {nation.color_name}"
                    hover_action_pos = (ally_zone_rect.right - 190, ally_zone_rect.y + 4)

            # Draw Empty Slot Outlines for all 3 rows (5 slots each)
            for s in range(5):
                # Home empty
                h_rect = self._slot_rect(box_rect, 'home', s)
                pygame.draw.rect(screen, (20, 26, 38), h_rect, border_radius=5)
                pygame.draw.rect(screen, (32, 40, 56), h_rect, 1, border_radius=5)

                # Ally empty
                a_rect = self._slot_rect(box_rect, 'ally', s)
                pygame.draw.rect(screen, (18, 28, 24), a_rect, border_radius=5)
                pygame.draw.rect(screen, (28, 44, 36), a_rect, 1, border_radius=5)

                # War empty
                w_rect = self._slot_rect(box_rect, 'war', s)
                pygame.draw.rect(screen, (28, 20, 24), w_rect, border_radius=5)
                pygame.draw.rect(screen, (46, 30, 36), w_rect, 1, border_radius=5)

            # Draw Occupied Flag Slots (Army Icons)
            slots = self._flag_slots_for_box(nation, box_rect)
            for slot in slots:
                # If this flag is currently lifted by dragging, draw a ghost silhouette
                if (self.drag
                        and self.drag.from_box == nation
                        and self.drag.from_zone == slot.zone
                        and self.drag.from_index == slot.slot_idx):
                    pygame.draw.rect(screen, (22, 28, 42), slot.rect, border_radius=5)
                    pygame.draw.rect(screen, (70, 90, 130), slot.rect, 1, border_radius=5)
                    continue

                # Slot background
                pygame.draw.rect(screen, (16, 22, 34), slot.rect, border_radius=5)

                # Tinted Army Icon
                sprite = util.load_tinted_sprite('army.png', slot.flag_nation.color_rgb, icon_w, icon_h)
                if sprite:
                    screen.blit(sprite, sprite.get_rect(center=slot.rect.center))
                else:
                    pygame.draw.circle(screen, slot.flag_nation.color_rgb, slot.rect.center, 9)

                # Slot Border / Box
                is_hovered = slot.rect.collidepoint(self.mouse_pos) and (self.drag is None)
                if slot.locked:
                    # Locked flags have a red border/box (cooldown count is NEVER shown)
                    pygame.draw.rect(screen, (235, 45, 55), slot.rect, 2, border_radius=5)
                elif is_hovered:
                    # Hover highlight on draggable army icons
                    pygame.draw.rect(screen, (255, 255, 255), slot.rect, 2, border_radius=5)
                else:
                    # Normal subtle edge
                    pygame.draw.rect(screen, (34, 44, 64), slot.rect, 1, border_radius=5)

        # 3. Draw Active Dragged Army Icon (on top of all boxes)
        if self.drag is not None:
            ds = self.drag
            fx = ds.curr_pos[0] - ds.mouse_offset[0]
            fy = ds.curr_pos[1] - ds.mouse_offset[1]
            flag_rect = pygame.Rect(fx, fy, settings.DIPL_FLAG_W, settings.DIPL_FLAG_H)

            # Drop shadow
            shadow_rect = flag_rect.copy()
            shadow_rect.x += 4
            shadow_rect.y += 4
            shadow_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 120))
            screen.blit(shadow_surf, shadow_rect.topleft)

            # Dragged card body
            pygame.draw.rect(screen, (16, 22, 34), flag_rect, border_radius=5)
            pygame.draw.rect(screen, (255, 255, 255), flag_rect, 2, border_radius=5)

            # Dragged army icon
            sprite = util.load_tinted_sprite('army.png', ds.flag_nation.color_rgb, icon_w, icon_h)
            if sprite:
                screen.blit(sprite, sprite.get_rect(center=flag_rect.center))
            else:
                pygame.draw.circle(screen, ds.flag_nation.color_rgb, flag_rect.center, 9)

            # Floating Action Badge if hovering over a valid target
            if hovered_valid_action:
                badge_surf = font_label.render(hovered_valid_action, True, (255, 255, 255))
                bw, bh = badge_surf.get_width() + 14, badge_surf.get_height() + 8
                bx, by = flag_rect.centerx - bw // 2, flag_rect.top - bh - 6
                # Keep inside screen
                bx = max(settings.DIPL_PANEL_X - 60, min(settings.SCREEN_WIDTH - bw - 10, bx))
                by = max(settings.TOP_BAR_HEIGHT + 10, by)

                badge_bg = pygame.Rect(bx, by, bw, bh)
                pygame.draw.rect(screen, (10, 14, 22), badge_bg, border_radius=5)
                pygame.draw.rect(screen, (80, 160, 240), badge_bg, 1, border_radius=5)
                screen.blit(badge_surf, (bx + 7, by + 4))

