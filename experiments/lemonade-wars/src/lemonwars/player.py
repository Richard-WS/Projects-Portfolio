"""Player state: cash, loans, inventory, equipment, staff, reputation.

The player owns no pygame or UI state — this is pure simulation state so the
whole game can run headless (tests, autoplay) without a display.
"""

from __future__ import annotations

import random

from . import data


class Loan:
    __slots__ = ("principal", "rate")

    def __init__(self, principal: float, rate: float):
        self.principal = float(principal)
        self.rate = float(rate)


class Player:
    def __init__(self, difficulty: data.Difficulty):
        # The $500 starting cash plus the proceeds of the $2,000 business loan
        # (the loan itself is recorded as a liability below).
        self.cash: float = round(difficulty.start_cash + data.START_LOAN, 2)
        self.loans: list[Loan] = [Loan(data.START_LOAN, data.START_LOAN_RATE)]
        self.inventory: dict[str, dict] = {}       # ing -> {"qty": float, "age": int}
        self.products: dict[str, dict] = {}        # key -> {"qty": float, "age": int}
        self.equipment: set[str] = set()
        self.tech: set[str] = set()
        self.tier_idx: int = 0
        self.insurance: set[str] = set()
        self.employees: dict[str, dict] = {}       # role -> {"skill","morale","days"}
        self.awareness: float = 5.0
        self.reputation: float = data.START_REPUTATION
        # weekly finance
        self.week_profit: float = 0.0
        self.sales_tax_bill: float = 0.0
        self.payroll_accum: float = 0.0
        self.cleanliness: float = 60.0
        self.district: str = data.START_DISTRICT
        self.visited: set[str] = {data.START_DISTRICT}

    # -- money ---------------------------------------------------------------

    @property
    def debt(self) -> float:
        return sum(l.principal for l in self.loans)

    def tier(self) -> data.Tier:
        return data.TIERS[self.tier_idx]

    def capacity(self) -> int:
        cap = self.tier().storage
        if "squeezer" in self.equipment:
            cap += 10
        if "juicer" in self.equipment:
            cap += 15
        if "delivery_vehicle" in self.equipment:
            cap += 25
        if "storefront" in self.equipment:
            cap += 100
        return cap

    def storage_used(self) -> float:
        return sum(s["qty"] for s in self.inventory.values()) + \
               sum(s["qty"] for s in self.products.values())

    def storage_room(self) -> float:
        return max(0.0, self.capacity() - self.storage_used())

    # -- inventory -----------------------------------------------------------

    def stock(self, ing: str) -> float:
        return self.inventory.get(ing, {}).get("qty", 0.0)

    def product_stock(self, key: str) -> float:
        return self.products.get(key, {}).get("qty", 0.0)

    def buy_ingredient(self, ing: str, qty: float, price: float, room: float = 1e9) -> bool:
        qty = round(float(qty), 3)
        if qty <= 0:
            return False
        cost = round(qty * price, 2)
        if cost > self.cash + 1e-6:
            return False
        if qty > room + 1e-6:
            return False
        self.cash = round(self.cash - cost, 2)
        stock = self.inventory.setdefault(ing, {"qty": 0.0, "age": 0})
        stock["qty"] = round(stock["qty"] + qty, 3)
        return True

    def consume(self, ing: str, qty: float) -> bool:
        stock = self.inventory.get(ing)
        if not stock or stock["qty"] < qty - 1e-6:
            return False
        stock["qty"] = round(stock["qty"] - qty, 3)
        if stock["qty"] <= 0.01:
            self.inventory.pop(ing, None)
        return True

    def add_products(self, key: str, qty: float) -> None:
        stock = self.products.setdefault(key, {"qty": 0.0, "age": 0})
        stock["qty"] = round(stock["qty"] + qty, 3)

    def ingredient_freshness(self, product: data.Product) -> float:
        """0 (all fresh) .. 1 (all about to turn) weighted over the recipe."""
        ing = data.INGREDIENTS
        used = product.base_recipe
        total = 0.0
        weight_sum = 0.0
        for k, units in used.items():
            if k not in self.inventory or self.inventory[k]["qty"] <= 0:
                total += 1.0
                weight_sum += units
                continue
            age = self.inventory[k]["age"]
            shelf = max(1, ing[k].shelf)
            total += min(1.0, age / shelf) * units
            weight_sum += units
        return total / max(weight_sum, 1e-6)

    def spoilage(self, game=None) -> float:
        """Age everything one day; return units lost (stats)."""
        lost = 0.0
        ing = data.INGREDIENTS
        heat = game is not None and game.world.weather_at(self.district).key == "heat_wave"
        has_fridge = "refrigeration" in self.equipment
        automation = "inventory_automation" in self.tech

        for k, s in list(self.inventory.items()):
            s["age"] += 1
            shelf = ing[k].shelf
            if s["age"] > shelf:
                lost += s["qty"]
                self.inventory.pop(k)
                continue
            ratio = s["age"] / shelf
            loss = 0.0
            if heat and not has_fridge and k in ("ice", "milk", "strawberries", "blueberries", "mango", "organic_fruit", "exotic_fruit"):
                loss += 0.05
            if ratio > 0.85 and not has_fridge:
                loss += 0.02
            if loss > 0:
                drop = round(s["qty"] * loss, 3)
                if automation:
                    drop *= 0.8
                s["qty"] = round(s["qty"] - drop, 3)
                lost += drop
                if s["qty"] <= 0.01:
                    self.inventory.pop(k)

        for k, s in list(self.products.items()):
            s["age"] += 1
            shelf = 2 + (1 if has_fridge else 0)
            if k in ("coffee", "cold_brew"):
                shelf += 1
            if s["age"] > shelf:
                lost += s["qty"]
                self.products.pop(k)
        return lost

    # -- valuation -----------------------------------------------------------

    def inventory_value(self, market) -> float:
        value = 0.0
        for k, s in self.inventory.items():
            value += s["qty"] * market.price(self.district, k)
        for k, s in self.products.items():
            value += s["qty"] * data.PRODUCTS[k].anchor * 0.7
        return round(value, 2)

    def equipment_value(self) -> float:
        return round(sum(data.EQUIPMENT[k].cost * 0.6 for k in self.equipment), 2)

    def tier_value(self) -> float:
        return round(sum(t.cost for t in data.TIERS[: self.tier_idx]), 2)

    def net_worth(self, market) -> float:
        return round(self.cash + self.inventory_value(market) +
                     self.equipment_value() + self.tier_value() - self.debt, 2)

    # -- employees -----------------------------------------------------------

    def hire(self, role: str, rng: random.Random) -> bool:
        if role in self.employees or role not in data.EMPLOYEE_ROLES:
            return False
        self.employees[role] = {
            "skill": round(rng.uniform(30, 60), 1),
            "morale": 100.0,
            "days": 0,
        }
        return True

    def fire(self, role: str) -> bool:
        return self.employees.pop(role, None) is not None

    def daily_wages(self) -> float:
        return round(sum(data.EMPLOYEE_ROLES[r].salary for r in self.employees), 2)

    def staff_bonus(self, kind: str) -> float:
        """kind in service | quality | cleanliness | fuel. Pure — no mutation."""
        vals = {
            "cashier": {"service": 12, "quality": 0, "cleanliness": 0},
            "cook": {"service": 0, "quality": 6, "cleanliness": 0},
            "cleaner": {"service": 0, "quality": 0, "cleanliness": 20},
            "driver": {"service": 0, "quality": 0, "cleanliness": 0},
        }
        total = 0.0
        for role, e in self.employees.items():
            eff = (e["skill"] / 50.0) * (0.7 + 0.3 * e["morale"] / 100.0)
            total += vals[role][kind] * eff
        return total

    def tick_staff(self) -> None:
        """Advance staff days-worked and decay morale — once per day."""
        for e in self.employees.values():
            e["morale"] = max(0.0, e["morale"] - 0.8)
            e["days"] += 1

    def snapshot(self) -> dict:
        return {
            "cash": self.cash,
            "loans": [{"principal": l.principal, "rate": l.rate} for l in self.loans],
            "inventory": {k: dict(v) for k, v in self.inventory.items()},
            "products": {k: dict(v) for k, v in self.products.items()},
            "equipment": sorted(self.equipment),
            "tech": sorted(self.tech),
            "tier_idx": self.tier_idx,
            "insurance": sorted(self.insurance),
            "employees": {k: dict(v) for k, v in self.employees.items()},
            "awareness": self.awareness,
            "reputation": self.reputation,
            "week_profit": self.week_profit,
            "sales_tax_bill": self.sales_tax_bill,
            "payroll_accum": self.payroll_accum,
            "cleanliness": self.cleanliness,
            "district": self.district,
            "visited": sorted(self.visited),
        }

    @classmethod
    def restore(cls, snap: dict, difficulty: data.Difficulty) -> "Player":
        p = cls(difficulty)
        p.cash = float(snap["cash"])
        p.loans = [Loan(l["principal"], l["rate"]) for l in snap["loans"]]
        p.inventory = {k: {"qty": float(v["qty"]), "age": int(v["age"])} for k, v in snap["inventory"].items()}
        p.products = {k: {"qty": float(v["qty"]), "age": int(v["age"])} for k, v in snap["products"].items()}
        p.equipment = set(snap["equipment"])
        p.tech = set(snap["tech"])
        p.tier_idx = int(snap["tier_idx"])
        p.insurance = set(snap["insurance"])
        p.employees = {k: dict(v) for k, v in snap["employees"].items()}
        p.awareness = float(snap["awareness"])
        p.reputation = float(snap["reputation"])
        p.week_profit = float(snap["week_profit"])
        p.sales_tax_bill = float(snap["sales_tax_bill"])
        p.payroll_accum = float(snap["payroll_accum"])
        p.cleanliness = float(snap["cleanliness"])
        p.district = snap["district"]
        p.visited = set(snap["visited"])
        return p
