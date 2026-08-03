"""Demand and sales resolution."""

import random

from lemonwars import data
from lemonwars.customers import (district_ideal, expected_customers, product_fit,
                                 reference_price, run_sales, weather_fit_for)
from lemonwars.recipes import default_recipe
from lemonwars.sim import GameState


def test_district_ideals_differ_by_market():
    g = GameState("normal", seed=1)
    g.player.district = "beach"
    beach_ideal = district_ideal(g, include_weather=False)
    g.player.district = "business"
    biz_ideal = district_ideal(g, include_weather=False)
    # beach skews refreshment/premium, business skews warmth/premium
    assert beach_ideal["refresh"] > biz_ideal["refresh"]
    assert biz_ideal["warm"] > beach_ideal["warm"]


def test_fit_prefers_matching_product_in_district():
    g = GameState("normal", seed=2)
    g.player.district = "beach"
    lemonade = default_recipe("lemonade").flavour(data.PRODUCTS["lemonade"])
    coffee = default_recipe("coffee").flavour(data.PRODUCTS["coffee"])
    assert product_fit(g, lemonade) > product_fit(g, coffee)

    g.player.district = "business"
    g.day = 350  # winter
    assert product_fit(g, coffee) > product_fit(g, lemonade)


def test_demand_positive_and_capped_by_tier():
    g = GameState("normal", seed=3)
    for _ in range(20):
        g.begin_day()
        n = expected_customers(g)
        assert 5 <= n <= g.player.tier().max_serve + 1
        g.next_day()


def test_reputation_and_awareness_drive_demand():
    g = GameState("normal", seed=4)
    g.begin_day()
    low = expected_customers(g)
    g.player.reputation = 90
    g.player.awareness = 100
    high = expected_customers(g)
    assert high > low


def test_sell_with_no_stock_loses_all_customers():
    g = GameState("normal", seed=5)
    report = run_sales(g)
    assert report.sold == 0
    assert report.lost == report.customers > 0
    assert report.revenue == 0


def test_sell_consumes_stock_and_generates_revenue():
    from helpers import restock

    g = GameState("normal", seed=6)
    ok, msg = restock(g, 80)
    assert ok, msg
    cash_before = g.player.cash
    report = run_sales(g)
    assert report.sold > 0
    assert report.revenue == round(report.sold * g.price, 2)
    assert g.player.cash == round(cash_before + report.revenue, 2)
    assert g.player.product_stock("lemonade") < 80


def test_high_price_cuts_sales():
    from helpers import restock

    g1 = GameState("normal", seed=7)
    g2 = GameState("normal", seed=7)
    for g in (g1, g2):
        ok, msg = restock(g, 100)
        assert ok, msg
    g1.set_price(reference_price(g1) * 0.8)
    g2.set_price(reference_price(g2) * 3.0)
    r1 = run_sales(g1)
    r2 = run_sales(g2)
    assert r1.sold > r2.sold


def test_satisfaction_within_bounds_and_reputation_moves():
    from helpers import restock

    g = GameState("normal", seed=8)
    ok, msg = restock(g, 100)
    assert ok, msg
    g.set_price(1.50)  # cheap + good -> happy customers
    rep_before = g.player.reputation
    report = run_sales(g)
    assert report.avg_satisfaction > 0
    assert report.avg_satisfaction <= 100
    assert g.player.reputation >= rep_before


def test_weather_fit_opposes_heat_and_cold():
    g = GameState("normal", seed=9)
    g.world.weather["downtown"] = "heat_wave"
    assert weather_fit_for(g, "extra_cold") > 0
    assert weather_fit_for(g, "hot") < 0
    g.world.weather["downtown"] = "snow"
    assert weather_fit_for(g, "hot") > 0
    assert weather_fit_for(g, "extra_cold") < 0


def test_repeat_customers_boosted_by_loyalty_program():
    from helpers import restock

    g1 = GameState("normal", seed=10)
    g2 = GameState("normal", seed=10)
    for g in (g1, g2):
        ok, msg = restock(g, 100)
        assert ok, msg
        g.set_price(1.50)
    g2.buy_tech("loyalty")
    # equalise cash so the tech purchase doesn't disturb demand math
    g2.player.cash = g1.player.cash
    r1 = run_sales(g1)
    r2 = run_sales(g2)
    assert r2.repeats >= r1.repeats
