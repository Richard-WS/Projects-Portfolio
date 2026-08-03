"""Day cycle, player actions, finance, endgame conditions."""

import random

import pytest

from lemonwars import data
from lemonwars.recipes import default_recipe
from lemonwars.sim import GameState


def stock_a_stand(g, cups=80):
    from helpers import restock

    ok, msg = restock(g, cups)
    assert ok, msg


def test_full_day_cycle_advances_and_reports():
    g = GameState("normal", seed=1)
    stock_a_stand(g)
    start = g.day_start_cash
    report = g.end_day()
    assert report["sold"] > 0
    assert report["revenue"] > 0
    assert g.phase == "report"
    g.next_day()
    assert g.day == 2
    assert g.phase == "planning"
    assert g.player.cash == pytest.approx(start + report["net"], abs=0.02)


def test_buy_respects_cash_and_storage():
    g = GameState("normal", seed=2)
    assert g.buy("lemons", 10_000) is False  # unaffordable
    assert g.buy("lemons", 500) is True
    assert g.buy("lemons", 500) is False  # no storage room
    assert g.player.stock("lemons") == pytest.approx(500, abs=0.01)


def test_produce_requires_ingredients_and_gates_on_equipment():
    g = GameState("normal", seed=3)
    ok, msg = g.produce(10)
    assert not ok and "Not enough" in msg
    # coffee requires the coffee machine
    g.recipe = default_recipe("coffee")
    g.active_product = "coffee"
    ok, msg = g.produce(10)
    assert not ok and "Requires" in msg
    g.buy_equipment("coffee_machine")
    for ing in ("coffee", "milk", "cups", "water"):
        g.buy(ing, 100)
    ok, _ = g.produce(10)
    assert ok
    assert g.player.product_stock("coffee") == 10


def test_equipment_prerequisites():
    g = GameState("normal", seed=4)
    assert g.buy_equipment("juicer") is False  # needs squeezer first
    assert g.buy_equipment("squeezer") is True
    assert g.buy_equipment("juicer") is True


def test_loan_take_repay_and_interest():
    g = GameState("normal", seed=5)
    before = g.player.debt
    assert g.take_loan("small")
    assert g.player.debt == pytest.approx(before + 1000, abs=0.01)
    cash_before = g.player.cash
    g.repay_loan(400)
    assert g.player.cash == pytest.approx(cash_before - 400, abs=0.01)
    # interest accrues at day end
    g.end_day()
    assert g.last_report["interest"] > 0


def test_debt_ceiling_blocks_new_loans():
    g = GameState("normal", seed=6)
    g.player.reputation = 5
    for _ in range(6):
        g.take_loan("small")
    assert g.player.debt <= data.MAX_DEBT
    assert g.take_loan("small") is False


def test_taxes_charged_weekly():
    g = GameState("normal", seed=7)
    stock_a_stand(g, 50)
    for _ in range(6):
        g.end_day()
        g.next_day()
    assert g.stats["taxes_paid"] == 0  # day 1..6: no weekly tax yet
    g.end_day()  # day 7
    assert g.stats["taxes_paid"] > 0
    assert g.last_report["taxes"] > 0


def test_bankruptcy_by_debt():
    g = GameState("normal", seed=8)
    g.player.loans = [g.player.loans[0]]
    g.player.loans[0].principal = data.MAX_DEBT + 100
    g._check_bankruptcy()
    assert g.game_over and not g.won
    assert g.end_reason == data.BANKRUPTCY_REASONS["debt"]


def test_bankruptcy_by_cash_floor():
    g = GameState("normal", seed=9)
    g.player.cash = data.CASH_FLOOR - 1
    g._check_bankruptcy()
    assert g.game_over
    assert g.end_reason == data.BANKRUPTCY_REASONS["cash"]


def test_campaign_ends_after_days_override():
    g = GameState("normal", seed=10, days_override=3)
    for _ in range(2):
        g.end_day()
        g.next_day()
    assert not g.game_over
    assert g.day == 3
    g.end_day()
    g.next_day()
    assert g.game_over and g.won
    assert g.end_reason == "campaign"


def test_health_failures_close_the_stand():
    g = GameState("normal", seed=11)
    g.health_fails = 2
    g._check_bankruptcy()
    assert not g.game_over
    g.health_fails = 3
    g._check_bankruptcy()
    assert g.game_over
    assert g.end_reason == data.BANKRUPTCY_REASONS["health"]


def test_net_worth_formula():
    g = GameState("normal", seed=12)
    nw = g.net_worth()
    assert nw == pytest.approx(g.player.cash + g.player.inventory_value(g.market)
                               + g.player.equipment_value() + g.player.tier_value()
                               - g.player.debt, abs=0.01)


def test_travel_moves_district_and_charges_fuel():
    g = GameState("normal", seed=13)
    g.player.cash = 5000
    cash_before = g.player.cash
    ok, _ = g.travel("beach")
    assert ok
    assert g.player.district == "beach"
    assert g.player.cash < cash_before
    assert g.stats["travel_distance"] > 0
    ok, _ = g.travel("beach")
    assert not ok


def test_travel_event_chance_is_reasonable():
    g = GameState("normal", seed=14)
    g.player.cash = 1_000_000
    hits = 0
    for _ in range(50):
        to = "university" if g.player.district != "university" else "beach"
        ok, msg = g.travel(to)
        assert ok
        if msg != f"Arrived at {data.DISTRICTS[to].name}.":
            hits += 1
    assert hits <= 25  # never every trip


def test_insurance_reduces_crime_loss():
    from lemonwars import events

    g1 = GameState("normal", seed=15)
    g2 = GameState("normal", seed=15)
    for g in (g1, g2):
        g.player.cash = 1000
        g.player.insurance.add("business")
        # force the same crime on both, insurance only on g1
    g2.player.insurance.clear()
    for g in (g1, g2):
        msg = events._crime_cash(g, 80.0, "The register was robbed.", "business")
        assert "$" in msg
    assert g1.player.cash > g2.player.cash


def test_autosave_created_at_day_end(tmp_path):
    g = GameState("normal", seed=16, save_dir=str(tmp_path))
    stock_a_stand(g)
    g.end_day()
    assert (tmp_path / "autosave.json").exists()


def test_achievements_unlock():
    g = GameState("normal", seed=17)
    stock_a_stand(g, 100)
    g.player.cash = 5000  # push net worth over $1,000
    g.last_report = {"net": 50, "revenue": 400, "weather": "sunny"}
    from lemonwars import events
    events.check_achievements(g)
    assert "first_profit" in g.achievements
    assert "money_machine" in g.achievements
    assert "thousand_net" in g.achievements


def test_deterministic_same_seed_same_game():
    a = GameState("normal", seed=42)
    b = GameState("normal", seed=42)
    for g in (a, b):
        stock_a_stand(g, 60)
        g.end_day()
    assert a.last_report == b.last_report
    assert a.player.cash == b.player.cash
