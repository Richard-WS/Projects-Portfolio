"""Ingredient market: price bounds, drift, event modifiers, district spread."""

import random

from lemonwars import data
from lemonwars.market import IngredientMarket


def test_initial_prices_within_bounds():
    m = IngredientMarket(random.Random(1))
    for d in data.DISTRICTS:
        for k, ing in data.INGREDIENTS.items():
            p = m.prices[d][k]
            assert ing.pmin <= p <= ing.pmax, (d, k, p)


def test_prices_include_district_cost_multiplier():
    m = IngredientMarket(random.Random(2))
    beach = data.DISTRICTS["beach"]  # cost_mult 1.20
    industrial = data.DISTRICTS["industrial"]  # cost_mult 0.85
    # over many ingredients the beach should tend pricier than industrial
    avg_b = sum(m.prices["beach"][k] for k in ("lemons", "sugar", "ice", "milk", "coffee")) / 5
    avg_i = sum(m.prices["industrial"][k] for k in ("lemons", "sugar", "ice", "milk", "coffee")) / 5
    assert avg_b > avg_i


def test_daily_walk_stays_bounded_over_200_days():
    m = IngredientMarket(random.Random(3))
    for _ in range(200):
        m.daily_update()
    for d in data.DISTRICTS:
        for k, ing in data.INGREDIENTS.items():
            p = m.prices[d][k]
            assert ing.pmin * 0.9 <= p <= ing.pmax * 1.1


def test_prices_drift_but_do_not_freeze():
    m = IngredientMarket(random.Random(4))
    before = m.prices["downtown"]["lemons"]
    moved = False
    for _ in range(60):
        m.daily_update()
        if m.prices["downtown"]["lemons"] != before:
            moved = True
            break
    assert moved


def test_modifier_applies_and_clears():
    m = IngredientMarket(random.Random(5))
    base = m.price("downtown", "lemons")
    m.set_modifier("lemons", 2.3)
    assert m.price("downtown", "lemons") == round(base * 2.3, 3)
    m.clear_modifiers()
    assert m.price("downtown", "lemons") == base


def test_snapshot_restore_roundtrip():
    m = IngredientMarket(random.Random(6))
    for _ in range(10):
        m.daily_update()
    m.set_modifier("sugar", 0.5)
    snap = m.snapshot()
    m2 = IngredientMarket.restore(random.Random(6), snap)
    assert m2.prices == m.prices
    assert m2.modifiers == m.modifiers
    m2.daily_update()
    m.daily_update()
    assert m2.prices == m.prices  # same rng state restored -> identical future


def test_ice_machine_discount_in_local_price():
    from lemonwars.sim import GameState

    g = GameState("normal", seed=7)
    before = g.local_price("ice")
    g.buy_equipment("ice_machine")
    after = g.local_price("ice")
    assert after == round(before * 0.7, 3)
