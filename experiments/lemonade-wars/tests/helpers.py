"""Shared test helpers."""

from lemonwars import data


def restock(game, cups: int = 80, product_key: str | None = None):
    """Buy exactly what a batch of `cups` needs (plus a small buffer) and
    produce it. Returns the produce() (ok, msg) result."""
    pk = product_key or game.active_product
    product = data.PRODUCTS[pk]
    usage = game.recipe.usage(product)
    for ing, units in usage.items():
        game.buy(ing, round(units * cups * 1.1, 3))
    return game.produce(cups)
