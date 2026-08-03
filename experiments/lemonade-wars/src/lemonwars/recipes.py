"""Recipe designer and product quality model.

A recipe turns ingredient sliders (sugar / ice / fruit), a premium toggle and
a serving temperature into a flavour vector over the six dimensions used
everywhere else: sweetness, freshness, acidity, refreshment, premium appeal
and warmth. Quality is how close that vector lands to the product's ideal
profile, adjusted for equipment, staff and ingredient freshness.
"""

from __future__ import annotations

import random

from . import data

TEMPS = {
    "cold": "Cold",
    "extra_cold": "Extra Cold",
    "frozen": "Frozen",
    "hot": "Hot",
    "warm": "Warm",
}

FRUIT_KEYS = {"lemons", "strawberries", "blueberries", "mango", "lime", "mint",
              "organic_fruit", "exotic_fruit"}


class Recipe:
    """A configured recipe for one product. Sliders run 0..100."""

    def __init__(self, product_key: str, sugar: int = 50, ice: int = 50,
                 fruit: int = 50, premium: bool = False, temp: str | None = None):
        self.product_key = product_key
        self.sugar = int(min(max(sugar, 0), 100))
        self.ice = int(min(max(ice, 0), 100))
        self.fruit = int(min(max(fruit, 0), 100))
        self.premium = bool(premium)
        product = data.PRODUCTS[product_key]
        self.temp = temp or ("hot" if product.hot else "extra_cold")

    # -- ingredient usage ---------------------------------------------------

    def usage(self, product: data.Product | None = None) -> dict[str, float]:
        """Units of each ingredient consumed per cup at these settings."""
        product = product or data.PRODUCTS[self.product_key]
        out: dict[str, float] = {}
        sugar_scale = 0.5 + self.sugar / 100.0
        ice_scale = 0.5 + self.ice / 100.0
        fruit_scale = 0.5 + self.fruit / 100.0

        for ing, units in product.base_recipe.items():
            if ing == "sugar":
                units *= sugar_scale
            elif ing == "ice":
                units *= ice_scale
            elif ing in FRUIT_KEYS:
                units *= fruit_scale
            out[ing] = units

        temp_ice = {"cold": 1.0, "extra_cold": 1.3, "frozen": 1.6,
                    "hot": 0.0, "warm": 0.0}[self.temp]
        if "ice" in out:
            out["ice"] = out["ice"] * (temp_ice if product.hot else 1.0)
            if temp_ice == 0.0 and product.hot:
                out.pop("ice", None)

        if self.premium:
            out["premium_sweetener"] = out.get("premium_sweetener", 0.0) + 0.5
            has_fruit = any(k in FRUIT_KEYS for k in product.base_recipe)
            if has_fruit:
                out["organic_fruit"] = out.get("organic_fruit", 0.0) + 0.5
        return {k: round(v, 3) for k, v in out.items()}

    # -- flavour vector -----------------------------------------------------

    def flavour(self, product: data.Product | None = None) -> dict[str, float]:
        product = product or data.PRODUCTS[self.product_key]
        f = dict(product.flavor)
        f["sweet"] += (self.sugar - 50) * 0.35
        f["fresh"] -= (self.sugar - 50) * 0.10
        if any(k in FRUIT_KEYS for k in product.base_recipe):
            f["fresh"] += (self.fruit - 50) * 0.15
            f["acid"] += (self.fruit - 50) * 0.20
        if not product.hot:
            f["refresh"] += (self.ice - 50) * 0.35
            f["refresh"] += {"cold": 0, "extra_cold": 12, "frozen": 18,
                             "hot": -15, "warm": -10}[self.temp]
        else:
            f["warm"] += 10 if self.temp == "hot" else -20
        if self.premium:
            f["premium"] += 25
        return {k: round(min(max(v, 0), 100), 1) for k, v in f.items()}

    # -- cost and quality ---------------------------------------------------

    def cost_per_cup(self, price_fn) -> float:
        """price_fn(ingredient_key) -> current local price per unit."""
        product = data.PRODUCTS[self.product_key]
        total = 0.0
        for ing, units in self.usage(product).items():
            total += units * price_fn(ing)
        return round(total, 3)

    def quality(self, game=None, product: data.Product | None = None,
                flavour: dict | None = None) -> float:
        product = product or data.PRODUCTS[self.product_key]
        flavour = flavour or self.flavour(product)
        dims = data.FLAVOUR_DIMS
        dist = sum(abs(flavour[d] - product.flavor[d]) for d in dims)
        q = 100.0 - dist / len(dims)
        if game is not None:
            eq = game.player.equipment
            if "squeezer" in eq:
                q += 3
            if "juicer" in eq:
                q += 4
            if "blender" in eq and product.key in ("smoothie", "fruit_punch"):
                q += 5
            if "coffee_machine" in eq and product.key in ("coffee", "cold_brew"):
                q += 4
            emp = game.player.employees.get("cook")
            if emp:
                q += emp["skill"] * 0.06
            # ingredient freshness penalty
            ratio = game.player.ingredient_freshness(product)
            q -= ratio * 25
        return round(min(max(q, 5), 100), 1)

    def snapshot(self) -> dict:
        return {"product": self.product_key, "sugar": self.sugar, "ice": self.ice,
                "fruit": self.fruit, "premium": self.premium, "temp": self.temp}

    @classmethod
    def restore(cls, snap: dict) -> "Recipe":
        return cls(snap["product"], snap["sugar"], snap["ice"], snap["fruit"],
                   snap["premium"], snap.get("temp"))


def default_recipe(product_key: str) -> Recipe:
    return Recipe(product_key)
