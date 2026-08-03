"""Theme: palette, bundled fonts and responsive scaling.

The UI is designed on a 1280x800 logical grid and scales to any window size
(desktop laptops, portrait and landscape phones). `S(v)` converts a design
unit into pixels for the current window.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pygame

# --------------------------------------------------------------------------
# Palette (dark, readable in sunlight, cheap to render)
# --------------------------------------------------------------------------

BG = (15, 21, 30)
PANEL = (24, 32, 44)
PANEL_2 = (32, 42, 58)
PANEL_3 = (42, 54, 72)
TEXT = (233, 239, 247)
MUTED = (138, 153, 173)
FAINT = (86, 100, 122)
ACCENT = (250, 205, 60)          # lemon
ACCENT_DARK = (196, 154, 32)
GREEN = (72, 200, 120)
RED = (235, 92, 92)
BLUE = (92, 162, 235)
ORANGE = (240, 152, 62)
PURPLE = (168, 130, 235)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# --------------------------------------------------------------------------
# Fonts (bundled in assets/fonts so the web build is self-contained)
# --------------------------------------------------------------------------

_font_cache: dict[tuple, pygame.font.Font] = {}
_FONT_DIRS = [
    Path(__file__).resolve().parents[2] / "assets" / "fonts",          # src layout
    Path(__file__).resolve().parents[4] / "assets" / "fonts",          # web build root
    Path.cwd() / "assets" / "fonts",
]


def _find_font(name: str) -> str | None:
    for d in _FONT_DIRS:
        p = d / name
        if p.exists():
            return str(p)
    return None


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        regular = _find_font("DejaVuSans.ttf")
        boldf = _find_font("DejaVuSans-Bold.ttf")
        path = boldf if bold else regular
        if path:
            _font_cache[key] = pygame.font.Font(path, max(size, 6))
        else:
            _font_cache[key] = pygame.font.Font(None, max(size, 6))
    return _font_cache[key]


# --------------------------------------------------------------------------
# Scaling
# --------------------------------------------------------------------------

DESIGN_W, DESIGN_H = 1280, 800


def scale(w: int, h: int) -> float:
    return min(max(min(w / DESIGN_W, h / DESIGN_H), 0.55), 2.2)


class Scaler:
    """Current window scale. App updates `scaler.s` on every resize."""

    def __init__(self) -> None:
        self.s: float = 1.0

    def __call__(self, v) -> int:
        return max(1, int(v * self.s))

    def f(self, v: float) -> float:
        return v * self.s


scaler = Scaler()


def S(v) -> int:
    return scaler(v)


# --------------------------------------------------------------------------
# Drawing helpers
# --------------------------------------------------------------------------

def rect(surf, color, r, radius: int = 6, width: int = 0) -> None:
    pygame.draw.rect(surf, color, r, width, border_radius=S(radius))


def text(surf, s: str, size: int, color, pos, bold: bool = False,
         center: bool = False, right: bool = False) -> pygame.Rect:
    img = font(S(size), bold).render(s, True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
    surf.blit(img, r)
    return r


def bar(surf, r, frac: float, color) -> None:
    """A filled progress bar inside rect r."""
    frac = min(max(frac, 0.0), 1.0)
    rect(surf, PANEL_2, r)
    if frac > 0.01:
        w = max(2, int(r.width * frac))
        rect(surf, color, pygame.Rect(r.x, r.y, w, r.height), radius=3)


def wrap_text(s: str, size: int, max_w: int) -> list[str]:
    f = font(S(size))
    words, lines, cur = s.split(), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if f.size(trial)[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def money(v: float) -> str:
    return f"${v:,.2f}"


def fmt(v) -> str:
    return f"{v:g}"
