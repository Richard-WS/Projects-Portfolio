"""Headless UI smoke tests: run the real App on the dummy video driver.

Exercises the full path a user takes — title -> difficulty -> game ->
report -> end — through the actual event pipeline, plus the responsive
portrait switch. Renders every frame to catch layout crashes.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from lemonwars.ui import app as appmod  # noqa: E402
from lemonwars.ui import screens  # noqa: E402
from lemonwars.ui import theme  # noqa: E402
from lemonwars.ui.app import App  # noqa: E402

appmod.AUTOPLAY_INTERVAL = 0.0  # one autoplay action per tick in tests


def _init_pygame():
    pygame.init()
    # Font objects die with the font module on quit(); re-init fresh ones.
    theme._font_cache.clear()


def _click(app, widget):
    """Post a real press+release at the widget's logical centre."""
    cx, cy = widget.rect().center
    for etype in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        ev = pygame.event.Event(etype, {"pos": (cx, cy), "button": 1})
        app.handle_event(ev)


def _new_campaign(app):
    title_btns = app.title._buttons()
    assert title_btns[0].label == "New Campaign"
    _click(app, title_btns[0])
    assert app.mode == "difficulty"


def _pick_normal(app):
    for b in app.difficulty._cards():
        if b._key == "normal":
            _click(app, b)
            return
    raise AssertionError("normal difficulty card not found")


def test_title_to_game_flow(tmp_path):
    _init_pygame()
    try:
        app = App(headless=True, save_dir=str(tmp_path))
        app.tick(0.05)  # title renders

        _new_campaign(app)
        app.tick(0.05)  # difficulty renders
        _pick_normal(app)
        assert app.mode == "game"
        assert app.game is not None and app.game.day == 1
        app.tick(0.05)  # game screen renders

        # click End Day through the header widget
        for w in app.game_screen._header_widgets():
            if getattr(w, "label", "") == "End Day" and w.enabled:
                _click(app, w)
                break
        assert app.mode == "report"
        app.tick(0.05)  # report renders
        app.advance()
        assert app.mode == "game"
        assert app.game.day == 2
    finally:
        pygame.quit()


def test_autoplay_runs_campaign_to_end(tmp_path):
    _init_pygame()
    try:
        app = App(headless=True, save_dir=str(tmp_path))
        app.start_game("normal", autoplay=True, days_override=3)
        assert app.mode == "game"

        day_seen = 1
        for _ in range(30):
            app.tick(0.05)
            if app.game:
                day_seen = max(day_seen, app.game.day)
            if app.mode == "end":
                break
        assert app.mode == "end", f"autoplay never finished (day {day_seen})"
        assert app.game.won
        assert app.game.end_reason == "campaign"
        app.tick(0.05)  # end screen renders
    finally:
        pygame.quit()


def test_all_tabs_render(tmp_path):
    _init_pygame()
    try:
        app = App(headless=True, save_dir=str(tmp_path))
        app.start_game("normal")
        # stock the stand so panels with live data render meaningfully
        g = app.game
        g.buy("lemons", 400)
        g.buy("sugar", 300)
        g.buy("ice", 300)
        g.buy("cups", 200)
        g.buy("water", 200)
        g.produce(60)
        for tab in range(len(screens.TABS)):
            app.game_screen.tab = tab
            app.game_screen.last_layout = None
            app.tick(0.05)
    finally:
        pygame.quit()


def test_portrait_responsive_layout(tmp_path):
    _init_pygame()
    try:
        app = App(headless=True, save_dir=str(tmp_path))
        # switch the window to a tall phone aspect
        pygame.display.set_mode((400, 800), pygame.RESIZABLE)
        app.handle_event(pygame.event.Event(
            pygame.VIDEORESIZE, {"size": (400, 800)}))
        assert app.size == (720, 1280), app.size
        app.start_game("normal")
        app.game_screen.tab = 3  # districts (2-col grid)
        app.tick(0.05)
        assert app.logical.get_size() == (720, 1280)
        # and back to landscape
        pygame.display.set_mode((1600, 900), pygame.RESIZABLE)
        app.handle_event(pygame.event.Event(
            pygame.VIDEORESIZE, {"size": (1600, 900)}))
        assert app.size == (1280, 800), app.size
        app.tick(0.05)
    finally:
        pygame.quit()
