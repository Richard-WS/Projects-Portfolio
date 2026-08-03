"""World layer: seasons, per-district weather, fuel prices and travel
(everything about *where* the player is and how the environment behaves)."""

from __future__ import annotations

import random

from . import data


def season_for_day(day: int) -> data.Season:
    return data.season_for_day(day)


def roll_weather(rng: random.Random, season: data.Season, weather_mult: float = 1.0) -> str:
    """Pick one weather key from the season's weighted table."""
    weights = dict(season.weather_weights)
    return rng.choices(list(weights), weights=list(weights.values()))[0]


class World:
    """Per-district weather, global fuel price, and travel cost."""

    def __init__(self, rng: random.Random, districts=None):
        self.rng = rng
        self.districts = districts or list(data.DISTRICTS)
        self.weather: dict[str, str] = {}
        self.fuel_price: float = 3.5
        self.fuel_modifier: float = 1.0

    def reset(self, day: int = 1, weather_mult: float = 1.0) -> None:
        season = season_for_day(day)
        base = roll_weather(self.rng, season, weather_mult)
        for d in self.districts:
            # districts mostly share the day's weather, occasionally diverge
            if self.rng.random() < 0.20:
                self.weather[d] = roll_weather(self.rng, season, weather_mult)
            else:
                self.weather[d] = base

    def daily_update(self, day: int, weather_mult: float = 1.0) -> None:
        season = season_for_day(day)
        base = roll_weather(self.rng, season, weather_mult)
        for d in self.districts:
            if self.rng.random() < 0.20:
                self.weather[d] = roll_weather(self.rng, season, weather_mult)
            else:
                self.weather[d] = base
        # fuel price drifts, bounded
        self.fuel_price = round(min(max(self.fuel_price * (1 + 0.05 * self.rng.gauss(0, 1)), 2.5), 6.0), 2)

    def weather_at(self, district: str) -> data.WeatherProfile:
        return data.WEATHER[self.weather.get(district, "sunny")]

    def travel_cost(self, from_d: str, to_d: str, game=None) -> float:
        """Fuel cost in dollars to move between districts."""
        dist = data.DISTRICTS[to_d]
        fuel_units = dist.fuel
        if game is not None and "delivery_vehicle" in game.player.equipment:
            fuel_units *= 0.5
        if game is not None and "driver" in game.player.employees:
            fuel_units *= 0.7
        return round(fuel_units * self.fuel_price * self.fuel_modifier, 2)

    def snapshot(self) -> dict:
        return {"weather": self.weather, "fuel_price": self.fuel_price,
                "fuel_modifier": self.fuel_modifier}

    @classmethod
    def restore(cls, rng: random.Random, snap: dict, districts=None) -> "World":
        w = cls(rng, districts)
        w.weather = dict(snap["weather"])
        w.fuel_price = float(snap["fuel_price"])
        w.fuel_modifier = float(snap.get("fuel_modifier", 1.0))
        return w
