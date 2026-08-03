"""Recipe designer: usage scaling, flavour vector, cost and quality."""

import random

from lemonwars import data
from lemonwars.recipes import Recipe, default_recipe
from lemonwars.sim import GameState


def test_default_recipe_uses_base_units():
    r = default_recipe("lemonade")
    usage = r.usage()
    assert usage["lemons"] == 2.0
    assert usage["sugar"] == 1.5
    assert usage["ice"] == 1.5


def test_sugar_slider_scales_sugar_usage():
    low = Recipe("lemonade", sugar=0)
    high = Recipe("lemonade", sugar=100)
    assert high.usage()["sugar"] == 3 * low.usage()["sugar"]
    assert high.usage()["sugar"] == 2.25  # 1.5 * 1.5
    assert low.usage()["sugar"] == 0.75   # 1.5 * 0.5


def test_fruit_slider_scales_fruit_ingredients_only():
    weak = Recipe("pink_lemonade", fruit=0)
    strong = Recipe("pink_lemonade", fruit=100)
    assert strong.usage()["strawberries"] == 1.5
    assert weak.usage()["strawberries"] == 0.5
    # non-fruit ingredients unaffected by the fruit slider
    assert weak.usage()["cups"] == strong.usage()["cups"] == 1.0


def test_premium_adds_luxury_ingredients():
    plain = Recipe("lemonade", premium=False)
    fancy = Recipe("lemonade", premium=True)
    assert fancy.usage()["premium_sweetener"] == 0.5
    assert "organic_fruit" in fancy.usage()
    assert "premium_sweetener" not in plain.usage()


def test_hot_product_ignores_ice():
    r = Recipe("coffee", ice=100)
    assert "ice" not in r.usage()


def test_flavour_vector_clamped_and_moves_with_sliders():
    r = Recipe("lemonade", sugar=100, ice=100, temp="frozen")
    f = r.flavour()
    assert all(0 <= v <= 100 for v in f.values())
    base = default_recipe("lemonade").flavour()
    assert f["sweet"] > base["sweet"]
    assert f["refresh"] > base["refresh"]


def test_quality_penalises_extreme_settings():
    ideal = Recipe("lemonade", sugar=55, ice=55, fruit=50, temp="extra_cold")
    awful = Recipe("lemonade", sugar=100, ice=0, fruit=100, temp="hot")
    g = GameState("normal", seed=1)
    q_good = ideal.quality(g)
    q_bad = awful.quality(g)
    assert q_good > q_bad


def test_cost_per_cup_uses_price_fn():
    r = default_recipe("lemonade")
    cost = r.cost_per_cup(lambda ing: data.INGREDIENTS[ing].base)
    assert 0.5 < cost < 2.0  # sanity for the base recipe


def test_equipment_and_cook_boost_quality():
    g = GameState("normal", seed=2)
    r = default_recipe("lemonade")
    before = r.quality(g)
    g.buy_equipment("squeezer")
    g.buy_equipment("juicer")
    g.hire("cook")
    after = r.quality(g)
    assert after > before


def test_recipe_snapshot_roundtrip():
    r = Recipe("limeade", sugar=20, ice=80, fruit=70, premium=True, temp="frozen")
    r2 = Recipe.restore(r.snapshot())
    assert r2.product_key == r.product_key
    assert r2.sugar == r.sugar and r2.ice == r.ice and r2.fruit == r.fruit
    assert r2.premium == r.premium and r2.temp == r.temp
