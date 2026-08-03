"""Customer demand and the daily sales resolution.

Demand is driven by the district's demographic mix, weather, season, player
reputation, advertising awareness, competition, tier capacity, technology and
active events. Each simulated customer then weighs the price against a
demographic price-sensitivity before buying; every purchase produces a
satisfaction score that feeds reputation and repeat business.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import data


# --------------------------------------------------------------------------
# District / demographic fit
# --------------------------------------------------------------------------

def district_ideal(game, include_weather: bool = True) -> dict[str, float]:
    """The flavour vector this district most wants right now.

    Demographic tastes are mixed by their share of the district, then nudged
    by weather and season (hot days pull toward refreshment, cold days toward
    warmth).
    """
    d = data.DISTRICTS[game.player.district]
    ideal = {dim: 0.0 for dim in data.FLAVOUR_DIMS}
    for demog_key, share in d.mix.items():
        taste = data.DEMOGRAPHICS[demog_key].taste
        for dim in data.FLAVOUR_DIMS:
            ideal[dim] += taste[dim] * share
    if include_weather:
        w = game.world.weather_at(game.player.district)
        season = data.season_for_day(game.day)
        shift = (w.refresh_shift + season.refresh_shift) * game.difficulty.weather_mult
        ideal["refresh"] += shift
        shift_w = (w.warm_shift + season.warm_shift) * game.difficulty.weather_mult
        ideal["warm"] += shift_w
        ideal["fresh"] -= max(0, shift) * 0.3
    return {dim: min(max(v, 0), 100) for dim, v in ideal.items()}


def product_fit(game, flavour: dict, demog_key: str | None = None,
                include_weather: bool = True) -> float:
    """0..100 — how well a product's flavour matches its market."""
    if demog_key is not None:
        demog = data.DEMOGRAPHICS[demog_key]
        dist = 0.0
        wsum = 0.0
        for dim in data.FLAVOUR_DIMS:
            w = demog.pref[dim]
            dist += w * abs(flavour[dim] - demog.taste[dim])
            wsum += w
        return round(100.0 - dist / max(wsum, 1e-6), 1)
    ideal = district_ideal(game, include_weather)
    d = data.DISTRICTS[game.player.district]
    dist = 0.0
    wsum = 0.0
    for dim in data.FLAVOUR_DIMS:
        w = 0.0
        for demog_key, share in d.mix.items():
            w += data.DEMOGRAPHICS[demog_key].pref[dim] * share
        dist += w * abs(flavour[dim] - ideal[dim])
        wsum += w
    return round(100.0 - dist / max(wsum, 1e-6), 1)


# --------------------------------------------------------------------------
# Demand
# --------------------------------------------------------------------------

def expected_customers(game) -> float:
    """Raw expected foot traffic before stock limits."""
    p = game.player
    d = data.DISTRICTS[p.district]
    season = data.season_for_day(game.day)
    w = game.world.weather_at(p.district)

    base = d.demand * season.foot * w.foot * p.tier().cust_mult

    rep_mult = 0.6 + p.reputation / 160.0
    awareness_mult = 0.65 + 0.35 * (1.0 - math.exp(-p.awareness / 120.0))
    comp_mult = 1.0 - d.competition * 0.30 * (0.6 + 0.4 * game.difficulty.competitor_mult)
    tech_mult = 1.0
    if "online_ordering" in p.tech:
        tech_mult *= 1.15
    if "delivery_app" in p.tech:
        tech_mult *= 1.10
    storefront = 1.4 if "storefront" in p.equipment else 1.0

    flavour = game.recipe.flavour(data.PRODUCTS[game.active_product])
    fit_mult = 0.7 + 0.6 * product_fit(game, flavour) / 100.0

    event_mult = 1.0
    for name, (mult, _days) in game.demand_modifiers.items():
        event_mult *= mult

    cap = p.tier().max_serve
    if "cashier" in p.employees:
        cap *= 1.10
    if "cash_register" in p.equipment:
        cap *= 1.15

    customers = base * rep_mult * awareness_mult * comp_mult * tech_mult * \
        storefront * fit_mult * event_mult
    return min(max(customers, 5.0), cap)


# --------------------------------------------------------------------------
# Sales resolution
# --------------------------------------------------------------------------

@dataclass
class SalesReport:
    customers: int = 0
    sold: int = 0
    lost: int = 0
    revenue: float = 0.0
    avg_satisfaction: float = 0.0
    repeats: int = 0
    quality: float = 0.0
    reference: float = 0.0
    fit: float = 0.0
    weather_fit: float = 0.0
    satisfaction_samples: list = field(default_factory=list)


def weather_fit_for(game, temp: str) -> float:
    """How well the serving temperature matches today's weather."""
    w = game.world.weather_at(game.player.district)
    hot_drink = temp in ("hot", "warm")
    if not hot_drink:
        if w.key in ("heat_wave", "sunny", "humid"):
            return 16.0
        if w.key in ("cold_snap", "snow"):
            return -12.0
        if w.key in ("rain", "thunderstorm", "windy"):
            return -5.0
    else:
        if w.key in ("cold_snap", "snow", "rain", "thunderstorm"):
            return 16.0
        if w.key in ("heat_wave", "sunny", "humid"):
            return -14.0
    return 0.0


def reference_price(game) -> float:
    product = data.PRODUCTS[game.active_product]
    d = data.DISTRICTS[game.player.district]
    return round(product.anchor * d.cost_mult * (1.0 + game.player.reputation / 600.0), 2)


def run_sales(game) -> SalesReport:
    p = game.player
    report = SalesReport()
    product = data.PRODUCTS[game.active_product]
    stock = p.product_stock(game.active_product)
    if stock <= 0.01:
        report.customers = int(expected_customers(game))
        report.lost = report.customers
        return report

    flavour = game.recipe.flavour(product)
    quality = game.recipe.quality(game, product, flavour)
    ref = reference_price(game)
    ratio = game.price / max(ref, 0.01)
    temp = game.recipe.temp
    wfit = weather_fit_for(game, temp)

    report.quality = quality
    report.reference = ref
    report.weather_fit = wfit
    report.fit = product_fit(game, flavour)

    demog_keys = list(data.DEMOGRAPHICS)
    d = data.DISTRICTS[p.district]
    mix_weights = [d.mix.get(k, 0.0) for k in demog_keys]
    patience = game.difficulty.patience
    loyalty = 1.2 if "loyalty" in p.tech else 1.0
    revenue_mult = 1.05 if "predictive_pricing" in p.tech else 1.0
    service_clean = 45.0 + p.staff_bonus("service") + p.staff_bonus("cleanliness") * 0.5
    cleanliness = min(100.0, p.cleanliness + p.staff_bonus("cleanliness"))

    total_sat = 0.0
    for _ in range(int(expected_customers(game))):
        if stock <= 0.01:
            report.lost += 1
            continue
        demog = data.DEMOGRAPHICS[game.rng.choices(demog_keys, weights=mix_weights)[0]]
        price_sens = demog.price_sens * patience
        buy_chance = 0.92 - price_sens * max(0.0, ratio - 1.0) * 1.5 \
            - (1.0 - quality / 100.0) * 0.22
        buy_chance = min(max(buy_chance, 0.04), 0.98)
        if game.rng.random() >= buy_chance:
            continue

        stock -= 1
        report.sold += 1
        sat = 0.58 * quality + 0.10 * product_fit(game, flavour, demog.key) \
            + 0.14 * wfit + 0.10 * min(100.0, service_clean) \
            - max(0.0, (ratio - 1.0) * price_sens * 40.0)
        sat = min(max(sat, 3.0), 100.0)
        report.satisfaction_samples.append(sat)
        total_sat += sat

        if game.rng.random() < (0.04 + 0.5 * sat / 100.0) * loyalty:
            report.repeats += 1
        price_now = game.price * revenue_mult
        report.revenue += price_now
        p.sales_tax_bill = round(p.sales_tax_bill + price_now * 0.08, 2)

    p.products[game.active_product]["qty"] = round(stock, 3)
    if stock <= 0.01:
        p.products.pop(game.active_product, None)

    report.customers = report.sold + report.lost
    if report.satisfaction_samples:
        report.avg_satisfaction = round(sum(report.satisfaction_samples) / len(report.satisfaction_samples), 1)
        delta = min(max((report.avg_satisfaction - 58.0) * 0.015, -2.0), 3.0)
        p.reputation = round(min(max(p.reputation + delta, 0.0), 100.0), 1)
    if report.lost > 0:
        p.reputation = round(max(0.0, p.reputation - min(3.0, report.lost / 25.0)), 1)

    # stats
    game.stats["customers"] += report.customers
    game.stats["sold"] += report.sold
    game.stats["lost_sales"] += report.lost
    game.stats["repeat_customers"] += report.repeats
    game.stats["revenue"] = round(game.stats["revenue"] + report.revenue, 2)
    p.cash = round(p.cash + report.revenue, 2)
    return report
