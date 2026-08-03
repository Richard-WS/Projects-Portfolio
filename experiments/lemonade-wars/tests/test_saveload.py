"""Save/load round-trips: the restored game is byte-identical in behaviour."""

import pytest

from lemonwars.saveload import load, save
from lemonwars.sim import GameState


def _played_game(tmp_path, days=5, seed=7):
    g = GameState("normal", seed=seed, save_dir=str(tmp_path))
    for ing in ("lemons", "sugar", "ice", "cups", "water"):
        g.buy(ing, 300)
    g.produce(60)
    for _ in range(days):
        g.end_day()
        g.next_day()
    return g


def test_save_load_roundtrip_state(tmp_path):
    g = _played_game(tmp_path)
    assert save(g, tmp_path, "slot1")
    g2 = load(tmp_path, "slot1")
    assert g2 is not None
    assert g2.day == g.day
    assert g2.player.cash == g.player.cash
    assert g2.player.debt == g.player.debt
    assert g2.player.inventory == g.player.inventory
    assert g2.player.products == g.player.products
    assert g2.price == g.price
    assert g2.active_product == g.active_product
    assert g2.recipe.snapshot() == g.recipe.snapshot()
    assert g2.stats == g.stats
    assert g2.achievements == g.achievements
    assert g2.player.district == g.player.district
    assert g2.player.reputation == g.player.reputation


def test_restored_game_is_behaviourally_identical(tmp_path):
    g = _played_game(tmp_path, days=4)
    save(g, tmp_path, "slot2")
    g2 = load(tmp_path, "slot2")
    # same actions must produce identical outcomes
    for game in (g, g2):
        for ing in ("lemons", "sugar"):
            game.buy(ing, 100)
        game.produce(40)
        game.set_price(2.75)
        game.end_day()
    assert g.last_report == g2.last_report
    assert g.player.cash == g2.player.cash


def test_load_missing_slot_returns_none(tmp_path):
    assert load(tmp_path, "nope") is None


def test_save_missing_dir_is_created(tmp_path):
    target = tmp_path / "a" / "b"
    g = _played_game(tmp_path, days=1)
    assert save(g, target, "autosave")
    assert (target / "autosave.json").exists()


def test_roundtrip_preserves_market_and_world(tmp_path):
    g = _played_game(tmp_path, days=6)
    save(g, tmp_path, "slot3")
    g2 = load(tmp_path, "slot3")
    assert g2.market.prices == g.market.prices
    assert g2.world.weather == g.world.weather
    assert g2.world.fuel_price == g.world.fuel_price
