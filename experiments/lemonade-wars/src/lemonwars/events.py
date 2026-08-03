"""Random events: market movements, demand spikes, business setbacks and
business-oriented "crime". Every event is a function of the game state and
returns the news headline the player sees.

Market events nudge ingredient prices for a few days (drug-wars style
arbitrage windows). Business events resolve at the end of the day and cost
money — insurance softens the hits. Travel events fire while moving between
districts.
"""

from __future__ import annotations

import random

from . import data

MULT = "mult"
DAYS = "days"


# --------------------------------------------------------------------------
# Event definitions
# --------------------------------------------------------------------------

EVENTS: list[dict] = []


def _event(key, name, weight, kind, fn, min_day=1):
    EVENTS.append({"key": key, "name": name, "weight": weight, "kind": kind,
                   "min_day": min_day, "fn": fn})


def _market_event(ing: str | list[str], mult: float, days: int):
    ings = [ing] if isinstance(ing, str) else ing
    def fn(game):
        for k in ings:
            game.market.set_modifier(k, mult)
            game.market_events[k] = [mult, days]
        names = ", ".join(data.INGREDIENTS[k].name for k in ings)
        pct = int(round((mult - 1.0) * 100))
        direction = "surge" if mult > 1 else "drop"
        return f"{names} prices {direction} {abs(pct)}% for about {days} days."
    return fn


def _demand_event(name_key: str, mult: float, days: int, text: str):
    def fn(game):
        game.demand_modifiers[name_key] = [mult, days]
        return text
    return fn


# --- market events ---------------------------------------------------------

_event("lemon_shortage", "Lemon Shortage", 9, "market",
       _market_event("lemons", 2.3, 4))
_event("sugar_surplus", "Sugar Surplus", 8, "market",
       _market_event("sugar", 0.55, 4))
_event("ice_shortage", "Ice Shortage", 7, "market",
       _market_event("ice", 2.0, 3))
_event("coffee_boom", "Coffee Boom", 6, "market",
       _market_event("coffee", 1.8, 4))
_event("tea_shortage", "Tea Shortage", 6, "market",
       _market_event("tea", 1.9, 4))
_event("milk_surplus", "Milk Surplus", 5, "market",
       _market_event("milk", 0.6, 3))
_event("import_delays", "Import Delays", 6, "market",
       _market_event(data.ADVANCED + data.LUXURY, 1.35, 3))
_event("crop_failure", "Crop Failure", 6, "market",
       _market_event(["strawberries", "blueberries", "mango", "organic_fruit", "exotic_fruit"], 1.8, 4))
_event("fruit_glut", "Fruit Glut", 5, "market",
       _market_event(["strawberries", "mango", "lime"], 0.6, 3))
_event("fuel_spike", "Fuel Spike", 6, "market",
       lambda game: _fuel_event(game, 1.8, 3))
_event("organic_trend", "Organic Trend", 5, "demand",
       _demand_event("organic_trend", 1.3, 4, "Health-conscious crowds are paying up for organic — demand is up 30% for a few days."))


def _fuel_event(game, mult: float, days: int) -> str:
    game.world.fuel_modifier = mult
    game.demand_modifiers["fuel_spike"] = [mult, days]
    return f"Fuel prices jumped {int(round((mult - 1) * 100))}% — travel will cost more for {days} days."


# --- weather / demand events -----------------------------------------------

_event("heat_wave_streak", "Heat Wave", 6, "weather",
       _demand_event("heat", 1.25, 3, "A heat wave has the city drinking ice-cold — cold drinks sell much better for a few days."))
_event("cold_front", "Cold Front", 5, "weather",
       _demand_event("cold", 1.25, 3, "A cold front moved in — hot drinks are suddenly in demand."))
_event("tourist_boom", "Tourist Boom", 5, "demand",
       _demand_event("tourist_boom", 1.35, 3, "Tourists are flooding the district — foot traffic up 35%."))
_event("food_festival", "Food Festival", 4, "demand",
       _demand_event("festival", 1.40, 2, "A food festival has drawn a crowd — foot traffic up 40% for two days."))
_event("sporting_event", "Sporting Event", 4, "demand",
       _demand_event("sport", 1.50, 1, "Big match today — the crowds are out in force (demand +50% today)."))
_event("music_festival", "Music Festival", 4, "demand",
       _demand_event("music", 1.45, 2, "A music festival is in town — demand up 45% for two days."))
_event("celebrity_visit", "Celebrity Visit", 2, "demand",
       _demand_event("celebrity", 1.60, 1, "A celebrity was spotted nearby — everyone wants a drink (demand +60% today)."))
_event("viral_post", "Viral Social Post", 3, "demand",
       lambda game: _viral(game))


def _viral(game) -> str:
    game.player.awareness = min(120.0, game.player.awareness + 80)
    return "A customer's post about your stand went viral — awareness +80!"


# --- business events (resolved at day end) ---------------------------------

def _inspection(game) -> str:
    p = game.player
    eff_clean = min(100.0, p.cleanliness + p.staff_bonus("cleanliness"))
    if eff_clean >= 70:
        p.reputation = min(100.0, p.reputation + 5)
        return "Health inspection passed with flying colours — reputation +5."
    fine = 200.0
    if "liability" in p.insurance:
        fine *= 0.5
    p.cash = round(p.cash - fine, 2)
    p.reputation = max(0.0, p.reputation - 10)
    game.health_fails += 1
    return f"Health inspection FAILED (cleanliness {eff_clean:.0f}/100). Fine ${fine:.0f}, reputation −10."


_event("health_inspection", "Health Inspection", 6, "business", _inspection, min_day=4)
_event("competitor_discount", "Competitor Discount", 6, "business",
       _demand_event("competitor_discount", 0.80, 2, "A rival vendor slashed prices — your demand dips 20% for two days."))
_event("ingredient_recall", "Ingredient Recall", 4, "business",
       lambda game: _recall(game))
_event("supplier_bankrupt", "Supplier Bankruptcy", 4, "business",
       lambda game: _supplier_bankrupt(game))
_event("power_outage", "Power Outage", 4, "business",
       lambda game: _power_outage(game))
_event("theft", "Theft", 5, "crime",
       lambda game: _crime_cash(game, 80.0, "The register was robbed overnight.", "business"))
_event("shoplifting", "Shoplifting", 5, "crime",
       lambda game: _shoplifting(game))
_event("vandalism", "Vandalism", 4, "crime",
       lambda game: _vandalism(game))
_event("equipment_theft", "Equipment Theft", 3, "crime",
       lambda game: _equipment_theft(game))
_event("counterfeit_coupons", "Counterfeit Coupons", 3, "crime",
       lambda game: _crime_cash(game, 60.0, "Fake coupons drained the till.", "business"))
_event("supplier_scam", "Supplier Scam", 3, "crime",
       lambda game: _crime_cash(game, 50.0, "A supplier took payment and never delivered.", "business"))
_event("cyber_attack", "Cyber Attack", 3, "crime",
       lambda game: _cyber(game))


def _recall(game) -> str:
    p = game.player
    pool = [k for k, s in p.inventory.items() if s["qty"] > 0]
    if not pool:
        return "An ingredient recall was announced — lucky you, none in stock."
    ing = game.rng.choice(pool)
    loss = round(p.inventory[ing]["qty"] * 0.4, 3)
    value = loss * game.market.price(p.district, ing)
    p.inventory[ing]["qty"] = round(p.inventory[ing]["qty"] - loss, 3)
    if "inventory" in p.insurance:
        value *= 0.2
    p.cash = round(p.cash - value, 2)
    return f"Recall on {data.INGREDIENTS[ing].name}: 40% tossed, ${value:.2f} lost."


def _supplier_bankrupt(game) -> str:
    p = game.player
    pool = [k for k, s in p.inventory.items() if s["qty"] > 0]
    if not pool:
        return "A supplier went bankrupt — nothing you carry was affected."
    loss_value = 0.0
    for k in pool:
        qty = p.inventory[k]["qty"]
        loss_value += qty * game.market.price(p.district, k)
        p.inventory.pop(k, None)
    if "inventory" in p.insurance:
        loss_value *= 0.2
    p.cash = round(p.cash - loss_value, 2)
    return f"A key supplier went bankrupt — all their goods were seized (${loss_value:.2f} lost)."


def _power_outage(game) -> str:
    p = game.player
    lost = 0.0
    for k, s in list(p.inventory.items()):
        if k in ("ice", "milk", "strawberries", "blueberries", "mango", "organic_fruit", "exotic_fruit"):
            drop = round(s["qty"] * 0.08, 3)
            s["qty"] = round(s["qty"] - drop, 3)
            lost += drop
            if s["qty"] <= 0.01:
                p.inventory.pop(k)
    return f"Power outage: ${lost:.2f} worth of chilled stock ruined." if lost else "Power outage — nothing chilled was on hand."


def _crime_cash(game, amount: float, text: str, cover_kind: str) -> str:
    p = game.player
    loss = amount
    if cover_kind in p.insurance:
        loss *= 0.3
    p.cash = round(p.cash - loss, 2)
    return f"{text} Lost ${loss:.2f}." + ("" if cover_kind not in p.insurance else " (insurance covered 70%)")


def _shoplifting(game) -> str:
    p = game.player
    pool = [k for k, s in p.products.items() if s["qty"] > 0]
    if not pool:
        return "Shoplifters circled your stand — nothing was out to take."
    key = game.rng.choice(pool)
    loss = min(p.products[key]["qty"], 6.0)
    value = loss * data.PRODUCTS[key].anchor * 0.7
    p.products[key]["qty"] = round(p.products[key]["qty"] - loss, 3)
    if "inventory" in p.insurance:
        value *= 0.2
    p.cash = round(p.cash - value, 2)
    return f"Shoplifting: {int(loss)} {data.PRODUCTS[key].name}(s) gone (${value:.2f} lost)."


def _vandalism(game) -> str:
    p = game.player
    cost = 150.0
    if "equipment" in p.insurance:
        cost *= 0.2
    p.cash = round(p.cash - cost, 2)
    return f"Vandals hit the stand — ${cost:.2f} in repairs." + ("" if "equipment" in p.insurance else "")


def _equipment_theft(game) -> str:
    p = game.player
    owned = [k for k in p.equipment if k != "squeezer"]
    if not owned:
        return "Thieves prowled but only found the squeezer — they left it."
    key = game.rng.choice(owned)
    if "equipment" in p.insurance:
        p.cash = round(p.cash - data.EQUIPMENT[key].cost * 0.2, 2)
        return f"Thieves tried to take the {data.EQUIPMENT[key].name} — insurance covered it (deductible ${data.EQUIPMENT[key].cost * 0.2:.0f})."
    p.equipment.discard(key)
    return f"The {data.EQUIPMENT[key].name} was stolen! Buy a replacement."


def _cyber(game) -> str:
    if not (game.player.tech or game.player.employees):
        return "A phishing attempt hit the cart's tablet — nothing to take."
    loss = 200.0
    if "business" in game.player.insurance:
        loss *= 0.3
    game.player.cash = round(game.player.cash - loss, 2)
    covered = " (insurance covered 70%)" if "business" in game.player.insurance else ""
    return f"Cyber attack on your systems — ${loss:.2f} lost.{covered}"


# --- travel events ---------------------------------------------------------

TRAVEL_EVENTS: list[dict] = []


def _travel_event(key, name, weight, fn):
    TRAVEL_EVENTS.append({"key": key, "name": name, "weight": weight, "fn": fn})


_travel_event("traffic_jam", "Traffic Jam", 25,
              lambda game: _travel_cost(game, 1.3, "Traffic jam — extra fuel burned."))
_travel_event("road_construction", "Road Construction", 18,
              lambda game: _travel_cost(game, 1.5, "Detour around road construction — costly."))
_travel_event("festival_parade", "Festival Parade", 12,
              lambda game: _travel_bonus(game, "You rolled in behind a festival parade — the district is buzzing."))
_travel_event("flat_tire", "Flat Tire", 15,
              lambda game: _travel_pay(game, 40.0, "Flat tire — $40 for a roadside patch."))
_travel_event("police_checkpoint", "Police Checkpoint", 12,
              lambda game: _checkpoint(game))
_travel_event("fuel_shortage", "Fuel Shortage", 10,
              lambda game: _travel_cost(game, 2.0, "Fuel shortage — prices through the roof."))
_travel_event("vehicle_breakdown", "Vehicle Breakdown", 8,
              lambda game: _travel_pay(game, 80.0, "Breakdown — $80 tow and repair."))


def _travel_cost(game, mult, text) -> str:
    game.world.fuel_modifier *= mult
    return f"{text} (fuel ×{mult})."


def _travel_pay(game, amount, text) -> str:
    game.player.cash = round(game.player.cash - amount, 2)
    return f"{text} −${amount:.0f}."


def _travel_bonus(game, text) -> str:
    game.demand_modifiers["parade"] = [1.3, 1]
    return text + " Demand up 30% today."


def _checkpoint(game) -> str:
    if game.player.reputation >= 45:
        return "Police checkpoint waved you through — clean record, no trouble."
    fine = 30.0
    game.player.cash = round(game.player.cash - fine, 2)
    return f"Police checkpoint — paperwork fine of ${fine:.0f}."


# --------------------------------------------------------------------------
# Rollers
# --------------------------------------------------------------------------

def roll_morning_event(game) -> str | None:
    """One morning market/weather/demand headline, or None."""
    chance = 0.30 * game.difficulty.event_mult
    if game.rng.random() > chance:
        return None
    eligible = [e for e in EVENTS if e["min_day"] <= game.day and e["kind"] in ("market", "weather", "demand")]
    ev = game.rng.choices(eligible, weights=[e["weight"] for e in eligible])[0]
    return f"{ev['name']}: {ev['fn'](game)}"


def roll_business_event(game) -> str | None:
    """One end-of-day business/crime event, or None."""
    chance = 0.22 * game.difficulty.event_mult
    if game.rng.random() > chance:
        return None
    eligible = [e for e in EVENTS if e["min_day"] <= game.day and e["kind"] in ("business", "crime")]
    ev = game.rng.choices(eligible, weights=[e["weight"] for e in eligible])[0]
    return f"{ev['name']}: {ev['fn'](game)}"


def roll_travel_event(game) -> str | None:
    w = game.world.weather_at(game.player.district)
    chance = (0.08 + w.travel_risk) * game.difficulty.event_mult
    if game.rng.random() > chance:
        return None
    ev = game.rng.choices(TRAVEL_EVENTS, weights=[e["weight"] for e in TRAVEL_EVENTS])[0]
    return f"{ev['name']}: {ev['fn'](game)}"


# --------------------------------------------------------------------------
# Achievements
# --------------------------------------------------------------------------

ACHIEVEMENTS: list[dict] = []


def _ach(key, name, desc, check):
    ACHIEVEMENTS.append({"key": key, "name": name, "desc": desc, "check": check})


_ach("first_profit", "First Profit", "End a day in the black.",
     lambda g: g.last_report and g.last_report.get("net", 0) > 0)
_ach("money_machine", "Money Machine", "Earn $300 in a single day.",
     lambda g: g.last_report and g.last_report.get("revenue", 0) >= 300)
_ach("thousand_net", "On the Map", "Reach $1,000 net worth.",
     lambda g: g.player.net_worth(g.market) >= 1000)
_ach("ten_thousand_net", "Real Business", "Reach $10,000 net worth.",
     lambda g: g.player.net_worth(g.market) >= 10000)
_ach("hundred_thousand_net", "City Player", "Reach $100,000 net worth.",
     lambda g: g.player.net_worth(g.market) >= 100000)
_ach("million_net", "Beverage Empire", "Reach $1,000,000 net worth.",
     lambda g: g.player.net_worth(g.market) >= 1_000_000)
_ach("served_1000", "Thirsty City", "Serve 1,000 customers.",
     lambda g: g.stats["customers"] >= 1000)
_ach("repeat_master", "Loyal Following", "Win 100 repeat customers.",
     lambda g: g.stats["repeat_customers"] >= 100)
_ach("world_traveller", "On the Road", "Do business in 6 districts.",
     lambda g: len(g.player.visited) >= 6)
_ach("brand_loyal", "Household Name", "Reach 80 reputation.",
     lambda g: g.player.reputation >= 80)
_ach("coffee_king", "Coffee King", "Sell 500 cups of coffee.",
     lambda g: g.stats["sold"] >= 500 and g.active_product == "coffee")
_ach("hot_days", "Beat the Heat", "Sell on a heat-wave day.",
     lambda g: g.last_report and g.last_report.get("weather") == "heat_wave")
_ach("empire_builder", "Empire Builder", "Open a café or better.",
     lambda g: g.player.tier_idx >= 4)
_ach("arbitrage", "Market Timer", "Buy ingredients at a 40%+ discount.",
     lambda g: g.stats.get("best_bargain", 0) >= 0.4)


def check_achievements(game) -> list[str]:
    """Return newly unlocked achievement names."""
    new = []
    for a in ACHIEVEMENTS:
        if a["key"] not in game.achievements and a["check"](game):
            game.achievements.add(a["key"])
            new.append(a["name"])
    return new
