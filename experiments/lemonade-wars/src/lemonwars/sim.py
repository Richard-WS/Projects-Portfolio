"""GameState — the single orchestrator that owns a campaign.

The whole simulation is pure Python with no pygame dependency, so the game
runs headless (tests, autoplay, CI) and the UI layer is a thin renderer on
top. Day structure:

    planning (day N)  -> player acts (buy / recipe / price / ad / travel)
    end_day()         -> sell, spoilage, wages, interest, taxes, events
    report (day N)    -> night report shown to the player
    next_day()        -> day N+1: weather, market, events rolled
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from . import data, events
from .customers import expected_customers, reference_price, run_sales
from .market import IngredientMarket
from .player import Loan, Player
from .recipes import default_recipe
from .world import World

MONEY_STATS = ("revenue", "expenses", "ad_spend", "interest_paid", "taxes_paid",
               "best_day_profit", "best_day_revenue")


class GameState:
    def __init__(self, difficulty_key: str = "normal", seed=None,
                 save_dir: str | None = None, days_override: int | None = None):
        self.seed = seed
        self.difficulty = data.DIFFICULTIES[difficulty_key]
        self.campaign_days = days_override if days_override is not None else self.difficulty.days
        self.save_dir = Path(save_dir) if save_dir else Path.cwd() / "saves"
        self.rng = random.Random(seed)

        self.day = 1
        self.phase = "planning"          # planning | report
        self.player = Player(self.difficulty)
        self.world = World(self.rng)
        self.world.reset(1, self.difficulty.weather_mult)
        self.market = IngredientMarket(self.rng)

        self.active_product = "lemonade"
        self.recipe = default_recipe("lemonade")
        self.price: float = data.PRODUCTS["lemonade"].anchor

        self.ads_active: list[list] = []          # [ad_key, days_left]
        self.market_events: dict[str, list] = {}  # ing -> [mult, days]
        self.demand_modifiers: dict[str, list] = {}  # name -> [mult, days]
        self.messages: list[str] = []             # rolling news log
        self.morning_news: list[str] = []

        self.stats: dict = {k: (0.0 if k in MONEY_STATS else 0) for k in data.STAT_KEYS}
        self.stats["best_bargain"] = 0.0
        self.achievements: set[str] = set()

        self.health_fails = 0
        self.game_over = False
        self.won = False
        self.end_reason = ""

        self.day_start_cash: float = self.player.cash
        self.day_spent: float = 0.0
        self.last_report: dict | None = None

    # ------------------------------------------------------------------ util

    def log(self, msg: str) -> None:
        self.messages.append(f"Day {self.day}: {msg}")
        del self.messages[:-60]

    def local_price(self, ing: str) -> float:
        p = self.market.price(self.player.district, ing)
        if ing == "ice" and "ice_machine" in self.player.equipment:
            p *= 0.7
        return round(p, 3)

    def net_worth(self) -> float:
        return self.player.net_worth(self.market)

    def title(self) -> str:
        nw = self.net_worth()
        for threshold, name in data.TITLES:
            if nw >= threshold:
                return name
        return data.TITLES[-1][1]

    def campaign_day_total(self) -> int:
        return self.campaign_days if self.campaign_days else 999999

    # ------------------------------------------------------------ day cycle

    def begin_day(self) -> None:
        """Roll the new day: weather, market, event decay, morning news."""
        self.world.daily_update(self.day, self.difficulty.weather_mult)
        self.market.daily_update()

        # decay market events
        for ing, (mult, days) in list(self.market_events.items()):
            days -= 1
            if days <= 0:
                self.market_events.pop(ing, None)
                if self.market.modifiers.get(ing) == mult:
                    self.market.modifiers.pop(ing, None)
            else:
                self.market_events[ing] = [mult, days]

        # decay demand modifiers
        for name, (mult, days) in list(self.demand_modifiers.items()):
            days -= 1
            if days <= 0:
                self.demand_modifiers.pop(name, None)
            else:
                self.demand_modifiers[name] = [mult, days]

        # fuel modifier decays with the demand modifier that owns it
        if "fuel_spike" not in self.demand_modifiers:
            self.world.fuel_modifier = 1.0

        # ads expire, awareness decays
        self.ads_active = [[k, d - 1] for k, d in self.ads_active if d > 1]
        self.player.awareness = round(max(0.0, self.player.awareness * 0.75), 2)

        # morning news
        self.morning_news = []
        headline = events.roll_morning_event(self)
        if headline:
            self.morning_news.append(headline)
            self.log(headline)

    def end_day(self) -> dict:
        """Run the sell phase and everything after it. Returns the report."""
        p = self.player
        product = data.PRODUCTS[self.active_product]

        # 1. sell
        report = run_sales(self)
        revenue = round(report.revenue, 2)

        # 2. spoilage
        spoiled = p.spoilage(self)
        self.stats["spoiled_units"] += spoiled

        # 3. wages + staff
        wages = p.daily_wages()
        p.cash = round(p.cash - wages, 2)
        p.tick_staff()

        # 4. loan interest
        rep = p.reputation
        credit = 1.5 if rep < 40 else (1.0 if rep < 70 else 0.7)
        interest = round(sum(l.principal * l.rate for l in p.loans) / 365.0
                         * self.difficulty.loan_mult * credit, 2)
        p.cash = round(p.cash - interest, 2)
        self.stats["interest_paid"] = round(self.stats["interest_paid"] + interest, 2)

        # 5. insurance premiums (weekly)
        insurance_cost = 0.0
        if self.day % 7 == 0:
            for ins in data.INSURANCE_TYPES:
                if ins["key"] in p.insurance:
                    insurance_cost += ins["premium"]
            p.cash = round(p.cash - insurance_cost, 2)

        # 6. weekly taxes
        tax_total = 0.0
        if self.day % 7 == 0:
            business_tax = round(max(0.0, p.week_profit) * 0.15, 2)
            payroll_tax = round(p.payroll_accum * 0.05, 2)
            tax_total = round(business_tax + p.sales_tax_bill + payroll_tax, 2)
            p.cash = round(p.cash - tax_total, 2)
            self.stats["taxes_paid"] = round(self.stats["taxes_paid"] + tax_total, 2)
            p.week_profit = 0.0
            p.sales_tax_bill = 0.0
            p.payroll_accum = 0.0
        else:
            p.week_profit = round(p.week_profit + (revenue - wages - interest - insurance_cost), 2)
            p.payroll_accum = round(p.payroll_accum + wages, 2)

        # 7. business / crime events
        night_event = events.roll_business_event(self)
        if night_event:
            self.log(night_event)
            self.stats["events_survived"] += 1

        # 8. cleanliness drift
        cleaner = p.staff_bonus("cleanliness")
        p.cleanliness = round(min(max(p.cleanliness - 1.5 + cleaner * 0.4, 20.0), 100.0), 1)

        # 9. stats + report
        day_net = round(p.cash - self.day_start_cash, 2)
        self.stats["days"] = self.day
        self.stats["expenses"] = round(self.stats["expenses"] + wages + interest + insurance_cost + tax_total, 2)
        self.stats["profit"] = round(self.stats["profit"] + day_net, 2)
        self.stats["best_day_revenue"] = max(self.stats["best_day_revenue"], revenue)
        self.stats["best_day_profit"] = max(self.stats["best_day_profit"], day_net)

        self.last_report = {
            "day": self.day,
            "customers": report.customers,
            "sold": report.sold,
            "lost": report.lost,
            "revenue": revenue,
            "avg_satisfaction": report.avg_satisfaction,
            "repeats": report.repeats,
            "quality": report.quality,
            "weather": self.world.weather_at(p.district).key,
            "spoiled": round(spoiled, 1),
            "wages": wages,
            "interest": interest,
            "insurance": insurance_cost,
            "taxes": tax_total,
            "spent": round(self.day_spent, 2),
            "net": day_net,
            "night_event": night_event,
        }

        # 10. achievements
        for name in events.check_achievements(self):
            self.log(f"Achievement unlocked: {name}!")

        # 11. bankruptcy checks
        self._check_bankruptcy()

        if not self.game_over:
            self.save("autosave")
        self.phase = "report"
        return self.last_report

    def _check_bankruptcy(self) -> None:
        p = self.player
        if p.debt > data.MAX_DEBT:
            self.game_over, self.won, self.end_reason = True, False, data.BANKRUPTCY_REASONS["debt"]
        elif p.cash < data.CASH_FLOOR:
            self.game_over, self.won, self.end_reason = True, False, data.BANKRUPTCY_REASONS["cash"]
        elif self.health_fails >= 3:
            self.game_over, self.won, self.end_reason = True, False, data.BANKRUPTCY_REASONS["health"]

    def next_day(self) -> None:
        self.day += 1
        self.day_start_cash = self.player.cash
        self.day_spent = 0.0
        if self.campaign_days and self.day > self.campaign_days:
            self.game_over, self.won, self.end_reason = True, True, "campaign"
            return
        self.phase = "planning"
        self.begin_day()

    # ------------------------------------------------------------ player actions

    def buy(self, ing: str, qty: float) -> bool:
        price = self.local_price(ing)
        cost = round(price * qty, 2)
        if cost > self.player.cash + 1e-6:
            return False
        room = self.player.storage_room()
        if qty > room + 1e-6:
            return False
        ok = self.player.buy_ingredient(ing, qty, price, room)
        if ok:
            self.day_spent = round(self.day_spent + cost, 2)
            self.stats["bought_units"] += qty
            base = data.INGREDIENTS[ing].base * data.DISTRICTS[self.player.district].cost_mult
            if base > 0:
                self.stats["best_bargain"] = max(self.stats["best_bargain"], 1.0 - price / base)
        return ok

    def produce(self, batch_qty: int | float) -> tuple[bool, str]:
        """Produce `batch_qty` cups of the active product. Returns (ok, msg)."""
        batch = int(batch_qty)
        if batch <= 0:
            return False, "Pick a batch size first."
        product = data.PRODUCTS[self.active_product]
        if product.requires and product.requires not in self.player.equipment:
            return False, f"Requires the {data.EQUIPMENT[product.requires].name}."
        usage = self.recipe.usage(product)
        needed = {k: round(v * batch, 3) for k, v in usage.items()}
        for k, need in needed.items():
            if self.player.stock(k) < need - 1e-6:
                return False, f"Not enough {data.INGREDIENTS[k].name} (need {need:g}, have {self.player.stock(k):g})."
        space = self.player.storage_room()
        if batch > space + 1e-6:
            return False, f"Not enough storage (need {batch:g} units, have {space:g})."
        for k, need in needed.items():
            self.player.consume(k, need)
        self.player.add_products(self.active_product, float(batch))
        self.stats["batches"] += 1
        self.stats["recipes_created"] += 1
        self.log(f"Produced {batch} {product.name}.")
        return True, f"Produced {batch} {product.name}."

    def set_recipe(self, recipe) -> None:
        self.recipe = recipe

    def set_price(self, price: float) -> None:
        self.price = round(min(max(price, 0.25), 99.0), 2)

    def run_ad(self, key: str) -> bool:
        ad = data.ADS[next(i for i, a in enumerate(data.ADS) if a.key == key)]
        if ad.cost > self.player.cash + 1e-6:
            return False
        self.player.cash = round(self.player.cash - ad.cost, 2)
        self.player.awareness = round(min(150.0, self.player.awareness + ad.awareness), 2)
        self.ads_active.append([key, ad.duration])
        self.stats["ad_spend"] = round(self.stats["ad_spend"] + ad.cost, 2)
        self.day_spent = round(self.day_spent + ad.cost, 2)
        return True

    def travel(self, to: str) -> tuple[bool, str]:
        if to == self.player.district:
            return False, "Already there."
        cost = self.world.travel_cost(self.player.district, to, self)
        if cost > self.player.cash + 1e-6:
            return False, f"Can't afford the trip (${cost:.2f})."
        self.player.cash = round(self.player.cash - cost, 2)
        self.day_spent = round(self.day_spent + cost, 2)
        self.stats["travel_distance"] += data.DISTRICTS[to].fuel
        self.player.district = to
        self.player.visited.add(to)
        headline = events.roll_travel_event(self)
        if headline:
            self.log(headline)
            return True, f"Arrived at {data.DISTRICTS[to].name}. {headline}"
        return True, f"Arrived at {data.DISTRICTS[to].name}."

    def take_loan(self, key: str) -> bool:
        option = next(o for o in data.LOAN_OPTIONS if o.key == key)
        if self.player.debt + option.amount > data.MAX_DEBT:
            return False
        rep = self.player.reputation
        credit = 1.5 if rep < 40 else (1.0 if rep < 70 else 0.7)
        rate = option.rate * credit * self.difficulty.loan_mult
        self.player.loans.append(Loan(option.amount, rate))
        self.player.cash = round(self.player.cash + option.amount, 2)
        self.stats["loans_taken"] += 1
        self.log(f"Took a {option.name} (${option.amount:.0f}).")
        return True

    def repay_loan(self, amount: float) -> bool:
        amount = round(min(max(amount, 0.0), self.player.cash), 2)
        if amount <= 0 or self.player.debt <= 0:
            return False
        remaining = amount
        # pay the most expensive loan first
        for loan in sorted(self.player.loans, key=lambda l: -l.rate):
            if remaining <= 0:
                break
            pay = min(loan.principal, remaining)
            loan.principal = round(loan.principal - pay, 2)
            remaining = round(remaining - pay, 2)
        self.player.loans = [l for l in self.player.loans if l.principal > 0.01]
        self.player.cash = round(self.player.cash - amount, 2)
        return True

    def buy_equipment(self, key: str) -> bool:
        eq = data.EQUIPMENT[key]
        if key in self.player.equipment or eq.cost > self.player.cash + 1e-6:
            return False
        if eq.requires and eq.requires not in self.player.equipment:
            return False
        self.player.cash = round(self.player.cash - eq.cost, 2)
        self.player.equipment.add(key)
        self.day_spent = round(self.day_spent + eq.cost, 2)
        self.log(f"Bought the {eq.name}.")
        return True

    def buy_tech(self, key: str) -> bool:
        t = data.TECH[key]
        if key in self.player.tech or t.cost > self.player.cash + 1e-6:
            return False
        if t.requires and t.requires not in self.player.tech:
            return False
        self.player.cash = round(self.player.cash - t.cost, 2)
        self.player.tech.add(key)
        self.day_spent = round(self.day_spent + t.cost, 2)
        self.log(f"Unlocked {t.name}.")
        return True

    def upgrade_tier(self) -> bool:
        if self.player.tier_idx + 1 >= len(data.TIERS):
            return False
        nxt = data.TIERS[self.player.tier_idx + 1]
        if nxt.cost > self.player.cash + 1e-6:
            return False
        self.player.cash = round(self.player.cash - nxt.cost, 2)
        self.player.tier_idx += 1
        self.day_spent = round(self.day_spent + nxt.cost, 2)
        self.log(f"Upgraded to a {nxt.name}.")
        return True

    def toggle_insurance(self, key: str) -> bool:
        ins = next(i for i in data.INSURANCE_TYPES if i["key"] == key)
        if key in self.player.insurance:
            self.player.insurance.discard(key)
        else:
            if ins["premium"] > self.player.cash + 1e-6:
                return False
            self.player.cash = round(self.player.cash - ins["premium"], 2)
            self.day_spent = round(self.day_spent + ins["premium"], 2)
            self.player.insurance.add(key)
        return True

    def hire(self, role: str) -> bool:
        return self.player.hire(role, self.rng)

    def fire(self, role: str) -> bool:
        return self.player.fire(role)

    # ------------------------------------------------------------ forecasting

    def forecast(self) -> dict:
        """Rough sales estimate for the Sell tab."""
        product = data.PRODUCTS[self.active_product]
        customers = expected_customers(self)
        stock = self.player.product_stock(self.active_product)
        ref = reference_price(self)
        ratio = self.price / max(ref, 0.01)
        quality = self.recipe.quality(self, product)
        buy_rate = min(max(0.92 - max(0.0, ratio - 1.0) * 1.2 - (1.0 - quality / 100.0) * 0.22, 0.04), 0.98)
        buyers = int(min(customers * buy_rate, stock))
        revenue = round(buyers * self.price, 2)
        return {"customers": int(customers), "buyers": buyers, "revenue": revenue,
                "stock": stock, "quality": quality, "reference": ref, "ratio": ratio}

    # ------------------------------------------------------------ save/load

    def to_dict(self) -> dict:
        from . import saveload
        return saveload.game_to_dict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        from . import saveload
        return saveload.game_from_dict(d)

    def save(self, slot: str = "autosave") -> bool:
        from . import saveload
        return saveload.save(self, self.save_dir, slot)

    @classmethod
    def load(cls, save_dir, slot: str = "autosave") -> "GameState | None":
        from . import saveload
        return saveload.load(save_dir, slot)
