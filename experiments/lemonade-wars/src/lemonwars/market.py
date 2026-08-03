"""Ingredient market: per-district prices that drift daily, plus temporary
event modifiers (shortages, gluts, import delays...)."""

from __future__ import annotations

import random

from . import data


class IngredientMarket:
    """Owns the price for every ingredient in every district.

    prices[district][ingredient] is the walk price; modifiers[ingredient] is a
    temporary multiplier applied on top (set by market events for a few days).
    """

    def __init__(self, rng: random.Random, districts=None, ingredients=None):
        self.rng = rng
        self.districts = districts or list(data.DISTRICTS)
        self.ingredients = ingredients or list(data.INGREDIENTS)
        self.prices: dict[str, dict[str, float]] = {}
        self.modifiers: dict[str, float] = {}
        self._init_prices()

    def _init_prices(self) -> None:
        for d in self.districts:
            mult = data.DISTRICTS[d].cost_mult
            self.prices[d] = {}
            for k, ing in data.INGREDIENTS.items():
                raw = ing.base * mult * self.rng.uniform(0.90, 1.10)
                self.prices[d][k] = round(min(max(raw, ing.pmin), ing.pmax), 3)

    def daily_update(self) -> None:
        for d in self.districts:
            mult = data.DISTRICTS[d].cost_mult
            for k, ing in data.INGREDIENTS.items():
                p = self.prices[d][k]
                walk = 1.0 + ing.vol * self.rng.gauss(0.0, 1.0) + 0.001
                p *= walk
                # keep district relativity sane: never walk outside [pmin,pmax]
                lo, hi = max(ing.pmin, ing.base * mult * 0.45), min(ing.pmax, ing.base * mult * 2.1)
                self.prices[d][k] = round(min(max(p, lo), hi), 3)

    def price(self, district: str, ing: str) -> float:
        p = self.prices[district][ing]
        return round(p * self.modifiers.get(ing, 1.0), 3)

    def set_modifier(self, ing: str, mult: float) -> None:
        self.modifiers[ing] = mult

    def clear_modifiers(self) -> None:
        self.modifiers.clear()

    def snapshot(self) -> dict:
        return {"prices": self.prices, "modifiers": self.modifiers,
                "rng": self.rng.getstate()}

    @classmethod
    def restore(cls, rng: random.Random, snap: dict) -> "IngredientMarket":
        m = cls(rng)
        m.prices = {d: {k: float(v) for k, v in row.items()} for d, row in snap["prices"].items()}
        m.modifiers = {k: float(v) for k, v in snap.get("modifiers", {}).items()}
        if "rng" in snap:
            st = snap["rng"]  # JSON turned the state tuple into lists
            m.rng.setstate((st[0], tuple(st[1]), st[2]))
        return m
