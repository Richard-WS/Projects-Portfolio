"""Application shell: window, logical design surface, scaling, screens and
the main loop.

The game renders to a fixed logical grid — 1280x800 landscape or 720x1280
portrait, chosen from the window's aspect — then scales that surface onto
the real window (aspect-fit, letterboxed). This makes every screen adapt to
laptops and phones without any per-pixel layout code.

Touch: pygbag maps taps to MOUSEBUTTONDOWN/UP automatically, so the widgets
work on phones with no extra code.
"""

from __future__ import annotations

import os
import sys
import time

import pygame

from . import theme
from .screens import (DifficultyScreen, EndScreen, GameScreen, ReportScreen,
                      TitleScreen)
from .theme import S

LANDSCAPE_W, LANDSCAPE_H = theme.DESIGN_W, theme.DESIGN_H
PORTRAIT_W, PORTRAIT_H = 720, 1280

AUTOPLAY_INTERVAL = 0.45  # seconds between autoplay actions


class App:
    def __init__(self, headless: bool = False, save_dir: str | None = None):
        self.headless = headless
        self.save_dir = save_dir
        self.running = True
        self.mode = "title"            # title | difficulty | game | report | end
        self.game = None
        self.autoplay_on = False
        self.notice_text = ""
        self._notice_until = 0.0
        self._auto_tick = 0.0
        self._last_frame = time.time()

        self.window = pygame.display.set_mode((1280, 800), pygame.RESIZABLE)
        pygame.display.set_caption("Lemonade Wars")

        self.title = TitleScreen(self)
        self.difficulty = DifficultyScreen(self)
        self.game_screen = GameScreen(self)
        self.report = ReportScreen(self)
        self.end = EndScreen(self)

        self.size = (1280, 800)
        self._make_logical()

    # ------------------------------------------------------------ geometry

    def _make_logical(self) -> None:
        w, h = self.window.get_size()
        portrait = h > w
        if portrait:
            self.size = (PORTRAIT_W, PORTRAIT_H)
            self.logical = pygame.Surface((PORTRAIT_W, PORTRAIT_H))
        else:
            self.size = (LANDSCAPE_W, LANDSCAPE_H)
            self.logical = pygame.Surface((LANDSCAPE_W, LANDSCAPE_H))
        theme.scaler.s = 1.0  # logical grid is already the design grid
        self.game_screen.last_layout = None  # force panel rebuild

    def to_logical(self, pos) -> tuple[int, int]:
        """Map window pixels to logical design coordinates."""
        ww, wh = self.window.get_size()
        lw, lh = self.size
        scale = min(ww / lw, wh / lh)
        off_x = (ww - lw * scale) / 2.0
        off_y = (wh - lh * scale) / 2.0
        return (int((pos[0] - off_x) / scale), int((pos[1] - off_y) / scale))

    # ------------------------------------------------------------- actions

    def notice(self, msg: str) -> None:
        self.notice_text = msg
        self._notice_until = time.time() + 2.5

    def start_game(self, difficulty_key: str, autoplay: bool = False,
                   days_override: int | None = None) -> None:
        from ..sim import GameState

        self.game = GameState(difficulty_key, seed=None, save_dir=self.save_dir,
                              days_override=days_override)
        self.autoplay_on = autoplay
        self.game_screen.last_layout = None
        self.mode = "game"
        self.notice(f"Day 1 — {self.game.player.tier().name} ready. Good luck!")

    def load_autosave(self):
        from ..sim import GameState

        if not self.save_dir:
            return None
        return GameState.load(self.save_dir, "autosave")

    def advance(self) -> None:
        """Move past the night report into the next planning day."""
        if not self.game:
            return
        self.game.next_day()
        if self.game.game_over:
            self.mode = "end"
        else:
            self.mode = "game"
            self.game_screen.last_layout = None

    def _end_day_via_ui(self) -> None:
        if not self.game or self.game.phase != "planning" or self.game.game_over:
            return
        self.game.end_day()
        if self.game.game_over:
            self.mode = "end"
        else:
            self.mode = "report"

    def _autoplay_step(self, now: float) -> None:
        """Autoplay advances exactly one day per tick (watchable pace)."""
        if not self.autoplay_on or not self.game:
            return
        if now - self._auto_tick < AUTOPLAY_INTERVAL:
            return
        self._auto_tick = now
        g = self.game
        if self.mode == "game":
            if g.phase == "planning" and not g.game_over:
                from ..autoplay import Autoplay

                Autoplay().play_day(g)
                g.end_day()
                if g.game_over:
                    self.mode = "end"
                else:
                    self.mode = "report"
        elif self.mode == "report":
            self.advance()
        if self.mode == "end":
            self.autoplay_on = False

    # -------------------------------------------------------------- events

    def handle_event(self, ev) -> None:
        if ev.type == pygame.QUIT:
            self.running = False
            return
        if ev.type == pygame.VIDEORESIZE:
            self.window = pygame.display.set_mode(ev.size, pygame.RESIZABLE)
            self._make_logical()
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.running = False
            return

        # map mouse coordinates into the logical grid
        if hasattr(ev, "pos"):
            ev = pygame.event.Event(ev.type, dict(ev.__dict__))
            ev.pos = self.to_logical(ev.pos)

        if self.mode == "title":
            self.title.handle(ev)
        elif self.mode == "difficulty":
            self.difficulty.handle(ev)
        elif self.mode == "game":
            self.game_screen.handle(ev)
        elif self.mode == "report":
            self.report.handle(ev)
        elif self.mode == "end":
            self.end.handle(ev)

    # ------------------------------------------------------------ rendering

    def render(self) -> None:
        surf = self.logical
        surf.fill(theme.BG)
        if self.mode == "title":
            self.title.draw(surf)
        elif self.mode == "difficulty":
            self.difficulty.draw(surf)
        elif self.mode == "game":
            self.game_screen.draw(surf)
        elif self.mode == "report":
            self.report.draw(surf)
        elif self.mode == "end":
            self.end.draw(surf)

        # letterboxed aspect-fit blit to the window
        ww, wh = self.window.get_size()
        lw, lh = self.size
        scale = min(ww / lw, wh / lh)
        dw, dh = int(lw * scale), int(lh * scale)
        self.window.fill((8, 10, 14))
        try:
            pygame.transform.smoothscale(surf, (max(dw, 1), max(dh, 1)),
                                         self.window,
                                         (ww - dw) // 2, (wh - dh) // 2)
        except Exception:
            self.window.blit(surf, ((ww - dw) // 2, (wh - dh) // 2))
        pygame.display.flip()

    def tick(self, dt: float) -> None:
        now = time.time()
        if self.notice_text and now > self._notice_until:
            self.notice_text = ""
        self._autoplay_step(now)
        self.render()

    # ---------------------------------------------------------------- loop

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = clock.tick(60) / 1000.0
            for ev in pygame.event.get():
                self.handle_event(ev)
            self.tick(dt)


def main() -> None:
    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()
    try:
        App().run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
