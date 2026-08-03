"""Minimal touch-friendly widgets: buttons, sliders, toggles, tab bars,
scroll areas. All coordinates are design units (1280x800 grid); theme.S()
converts to real pixels at draw/event time."""

from __future__ import annotations

import pygame

from . import theme
from .theme import S, font, rect, text


class Widget:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.enabled = True
        self.visible = True

    def rect(self) -> pygame.Rect:
        return pygame.Rect(S(self.x), S(self.y), S(self.w), S(self.h))

    def hit(self, pos) -> bool:
        return self.rect().collidepoint(pos)

    def handle(self, ev, pos) -> bool:
        return False

    def draw(self, surf):  # pragma: no cover - interface
        pass


_PENDING_PRESS: tuple | None = None  # (pos, button) — survives widget recreation


class Button(Widget):
    def __init__(self, x, y, w, h, label, cb=None, accent=False,
                 danger=False, muted=False, size=20):
        super().__init__(x, y, w, h)
        self.label = label
        self.cb = cb
        self.accent = accent
        self.danger = danger
        self.muted = muted
        self.size = size
        self._hover = False

    def handle(self, ev, pos) -> bool:
        global _PENDING_PRESS
        if not (self.enabled and self.visible):
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.hit(pos):
            _PENDING_PRESS = (pos, ev.button)
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            press = _PENDING_PRESS
            _PENDING_PRESS = None
            if press and self.hit(pos) and self.cb:
                self.cb()
                return True
        if ev.type == pygame.MOUSEMOTION:
            self._hover = self.hit(pos)
        return False

    def draw(self, surf):
        if not self.visible:
            return
        r = self.rect()
        down = _PENDING_PRESS is not None and r.collidepoint(_PENDING_PRESS[0])
        if not self.enabled:
            col = theme.PANEL_2
        elif self.accent:
            col = theme.ACCENT_DARK if down else theme.ACCENT
        elif self.danger:
            col = (120, 48, 48) if down else theme.RED
        elif self.muted:
            col = theme.PANEL_3 if down else theme.PANEL_2
        else:
            col = theme.PANEL_3 if (down or self._hover) else theme.PANEL_2
        rect(surf, col, r)
        tcol = theme.TEXT if not self.accent else theme.BLACK
        if not self.enabled:
            tcol = theme.FAINT
        img = font(S(self.size), True).render(self.label, True, tcol)
        surf.blit(img, img.get_rect(center=r.center))


class Slider(Widget):
    def __init__(self, x, y, w, label, value=50, on_change=None, step=1):
        super().__init__(x, y, w, 26)
        self.label = label
        self.value = float(value)
        self.step = step
        self.on_change = on_change
        self._drag = False
        self._shown = True

    def handle(self, ev, pos) -> bool:
        if not self.enabled:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.hit(pos):
            self._drag = True
            self._set(pos)
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._drag = False
        if ev.type == pygame.MOUSEMOTION and self._drag:
            self._set(pos)
            return True
        return False

    def _set(self, pos) -> None:
        r = self.rect()
        frac = min(max((pos[0] - r.x) / max(r.width, 1), 0.0), 1.0)
        val = self.value = round(frac * 100.0 / self.step) * self.step
        if self.on_change:
            self.on_change(val)

    def draw(self, surf):
        r = self.rect()
        text(surf, self.label, 14, theme.MUTED, (r.x, r.y - S(2)))
        track = pygame.Rect(r.x, r.y + S(8), r.width, S(6))
        rect(surf, theme.PANEL_2, track)
        fill = pygame.Rect(track.x, track.y, int(track.width * self.value / 100.0), track.height)
        rect(surf, theme.ACCENT, fill)
        knob_x = track.x + int(track.width * self.value / 100.0)
        pygame.draw.circle(surf, theme.TEXT, (knob_x, track.centery), S(8))
        text(surf, f"{self.value:.0f}", 14, theme.TEXT, (r.right + S(8), r.y),
             right=True)


class Toggle(Widget):
    def __init__(self, x, y, w, h, label, value=False, cb=None, size=16):
        super().__init__(x, y, w, h)
        self.label = label
        self.value = value
        self.cb = cb
        self.size = size

    def handle(self, ev, pos) -> bool:
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.hit(pos):
            self.value = not self.value
            if self.cb:
                self.cb(self.value)
            return True
        return False

    def draw(self, surf):
        r = self.rect()
        box = pygame.Rect(r.x, r.y + S(2), S(28), S(16))
        rect(surf, theme.ACCENT if self.value else theme.PANEL_3, box, radius=8)
        knob = pygame.Rect(box.x + (S(12) if self.value else S(2)), box.y + S(2),
                           S(12), S(12))
        pygame.draw.circle(surf, theme.WHITE, knob.center, S(6))
        text(surf, self.label, self.size, theme.TEXT, (box.right + S(8), r.y))


class TabBar(Widget):
    """Row of tabs; `vertical` flips to a column (portrait phone layout)."""

    def __init__(self, x, y, w, h, tabs, active=0, on_change=None, vertical=False):
        super().__init__(x, y, w, h)
        self.tabs = tabs
        self.active = active
        self.on_change = on_change
        self.vertical = vertical
        self._buttons: list[Button] = []

    def layout(self) -> None:
        self._buttons = []
        n = len(self.tabs)
        if self.vertical:
            gap = S(6)
            bh = (S(self.h) - gap * (n - 1)) // n
            for i, label in enumerate(self.tabs):
                b = Button(self.x, self.y + i * (bh + gap), self.w, bh, label,
                           cb=lambda i=i: self._select(i), size=13)
                b._meta = i
                self._buttons.append(b)
        else:
            gap = S(8)
            bw = (S(self.w) - gap * (n - 1)) // n
            for i, label in enumerate(self.tabs):
                b = Button(self.x + i * (bw + gap), self.y, bw, self.h, label,
                           cb=lambda i=i: self._select(i), size=15)
                b._meta = i
                self._buttons.append(b)

    def _select(self, i) -> None:
        if self.active != i:
            self.active = i
            if self.on_change:
                self.on_change(i)

    def handle(self, ev, pos) -> bool:
        if not self._buttons:
            self.layout()
        for i, b in enumerate(self._buttons):
            b.enabled = (i != self.active)
            if b.handle(ev, pos):
                return True
        return False

    def draw(self, surf):
        if not self._buttons:
            self.layout()
        for i, b in enumerate(self._buttons):
            if i == self.active:
                b.accent = True
            else:
                b.accent = False
            b.draw(surf)


class ScrollArea(Widget):
    """Clips children to its rect and scrolls them with wheel or drag."""

    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self.offset = 0
        self.content_h = 0
        self._drag = False
        self._drag_y = 0
        self._drag_off = 0

    def reset(self) -> None:
        self.offset = 0

    def handle(self, ev, pos) -> bool:
        if not self.rect().collidepoint(pos):
            return False
        if ev.type == pygame.MOUSEWHEEL:
            self.offset -= ev.y * S(36)
            self._clamp()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self._drag, self._drag_y, self._drag_off = True, pos[1], self.offset
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._drag = False
        if ev.type == pygame.MOUSEMOTION and self._drag:
            self.offset = self._drag_off + (self._drag_y - pos[1])
            self._clamp()
            return True
        return False

    def _clamp(self) -> None:
        max_off = max(0, self.content_h - self.h)
        self.offset = min(max(self.offset, 0), max_off)

    def view_rect(self) -> pygame.Rect:
        r = self.rect()
        return pygame.Rect(r.x, r.y - self.offset, r.w, r.h)


def scroll_draw(surf, area, draw_fn):
    """Draw scroll content on an offscreen surface, then blit the visible
    slice at the scroll offset. Children draw at content coordinates."""
    r = area.rect()
    if r.width <= 0 or r.height <= 0:
        return
    ch = max(area.content_h, r.height)
    content = pygame.Surface((r.width, ch))
    content.fill(theme.PANEL)
    draw_fn(content)
    surf.blit(content, (r.x, r.y),
              area=(0, min(area.offset, ch - r.height), r.width, r.height))
