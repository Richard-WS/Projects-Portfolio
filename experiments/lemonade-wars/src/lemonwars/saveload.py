"""JSON save/load. Desktop keeps files in <project>/saves; the web build
disables persistence (the browser filesystem is ephemeral) without breaking
the game — saves simply fall back gracefully."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from . import data
from .market import IngredientMarket
from .player import Player
from .recipes import Recipe
from .world import World

if TYPE_CHECKING:
    from .sim import GameState

VERSION = 1

WEB = sys.platform == "emscripten"


def _rng_to_json(rng: random.Random):
    st = rng.getstate()
    return [st[0], list(st[1]), st[2]]


def _rng_from_json(state) -> random.Random:
    rng = random.Random()
    rng.setstate((state[0], tuple(state[1]), state[2]))
    return rng


def game_to_dict(game) -> dict:
    return {
        "version": VERSION,
        "difficulty": next(k for k, d in data.DIFFICULTIES.items() if d is game.difficulty),
        "seed": game.seed,
        "rng": _rng_to_json(game.rng),
        "day": game.day,
        "phase": game.phase,
        "campaign_days": game.campaign_days,
        "player": game.player.snapshot(),
        "market": game.market.snapshot(),
        "world": game.world.snapshot(),
        "active_product": game.active_product,
        "recipe": game.recipe.snapshot(),
        "price": game.price,
        "ads_active": [list(a) for a in game.ads_active],
        "market_events": {k: list(v) for k, v in game.market_events.items()},
        "demand_modifiers": {k: list(v) for k, v in game.demand_modifiers.items()},
        "messages": game.messages,
        "stats": dict(game.stats),
        "achievements": sorted(game.achievements),
        "health_fails": game.health_fails,
        "game_over": game.game_over,
        "won": game.won,
        "end_reason": game.end_reason,
        "day_start_cash": game.day_start_cash,
        "day_spent": game.day_spent,
    }


def game_from_dict(d: dict) -> "GameState":
    from .sim import GameState

    difficulty_key = d.get("difficulty", "normal")
    game = GameState(difficulty_key=difficulty_key, seed=d.get("seed"),
                     days_override=d.get("campaign_days"))
    game.rng = _rng_from_json(d["rng"])
    game.day = int(d["day"])
    game.phase = d.get("phase", "planning")
    game.player = Player.restore(d["player"], game.difficulty)
    game.market = IngredientMarket.restore(game.rng, d["market"])
    game.world = World.restore(game.rng, d["world"])
    game.active_product = d["active_product"]
    game.recipe = Recipe.restore(d["recipe"])
    game.price = float(d["price"])
    game.ads_active = [list(a) for a in d.get("ads_active", [])]
    game.market_events = {k: list(v) for k, v in d.get("market_events", {}).items()}
    game.demand_modifiers = {k: list(v) for k, v in d.get("demand_modifiers", {}).items()}
    game.messages = list(d.get("messages", []))
    game.stats = dict(d.get("stats", {}))
    for k in data.STAT_KEYS:
        game.stats.setdefault(k, 0.0 if k in ("revenue", "expenses", "ad_spend",
                                              "interest_paid", "taxes_paid",
                                              "best_day_profit", "best_day_revenue") else 0)
    game.stats.setdefault("best_bargain", 0.0)
    game.achievements = set(d.get("achievements", []))
    game.health_fails = int(d.get("health_fails", 0))
    game.game_over = bool(d.get("game_over", False))
    game.won = bool(d.get("won", False))
    game.end_reason = d.get("end_reason", "")
    game.day_start_cash = float(d.get("day_start_cash", game.player.cash))
    game.day_spent = float(d.get("day_spent", 0.0))
    return game


def save(game, save_dir, slot: str = "autosave") -> bool:
    if WEB:
        return False
    try:
        path = Path(save_dir) / f"{slot}.json"
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(game.to_dict(), indent=1))
        return True
    except Exception:
        return False


def load(save_dir, slot: str = "autosave"):
    if WEB:
        return None
    try:
        path = Path(save_dir) / f"{slot}.json"
        if not path.exists():
            return None
        d = json.loads(path.read_text())
        if d.get("version", 0) != VERSION:
            return None
        return game_from_dict(d)
    except Exception:
        return None
