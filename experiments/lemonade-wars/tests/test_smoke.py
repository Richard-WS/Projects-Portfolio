"""Headless smoke tests: the autoplay policy plays real campaigns with no
display (SDL dummy driver), proving the whole loop runs end to end.

These run in CI on a bare runner — no X server, no audio.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from lemonwars.autoplay import Autoplay  # noqa: E402
from lemonwars.sim import GameState  # noqa: E402


@pytest.mark.parametrize("difficulty,days", [("normal", 30), ("hard", 20), ("expert", 15)])
def test_autoplay_survives_a_campaign(difficulty, days):
    g = GameState(difficulty, seed=11)
    bot = Autoplay()
    for _ in range(days):
        assert g.phase == "planning"
        bot.play_day(g)
        assert g.phase == "report"
        g.next_day()
        assert not g.game_over, f"bankrupt day {g.day}: {g.end_reason}"
        assert g.player.cash >= -501
    assert g.day == days + 1
    assert g.stats["days"] == days
    assert g.stats["revenue"] >= 0


def test_autoplay_is_deterministic_per_seed():
    results = []
    for _ in range(2):
        g = GameState("normal", seed=99)
        bot = Autoplay()
        for _ in range(12):
            bot.play_day(g)
            g.next_day()
        results.append((g.player.cash, g.stats["revenue"], g.player.district))
    assert results[0] == results[1]


def test_autoplay_grows_or_stays_solvent():
    """The normal-difficulty bot should end a month with more than it started."""
    g = GameState("normal", seed=5)
    bot = Autoplay()
    start_nw = g.net_worth()
    for _ in range(30):
        bot.play_day(g)
        g.next_day()
    assert g.net_worth() > start_nw


def test_health_code_repeat_failures_end_campaign():
    from lemonwars import events

    g = GameState("normal", seed=3)
    g.health_fails = 2
    g.player.cleanliness = 10  # guaranteed inspection failure
    events._inspection(g)
    assert g.health_fails == 3
    g._check_bankruptcy()
    assert g.game_over
    assert "health" in g.end_reason


def test_endless_simulation_mode_never_ends():
    g = GameState("simulation", seed=2)
    bot = Autoplay()
    for _ in range(45):
        bot.play_day(g)
        g.next_day()
    assert not g.game_over
    assert g.day == 46
