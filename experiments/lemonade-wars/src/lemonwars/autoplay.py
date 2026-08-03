"""Autoplay: a scripted player used by the headless smoke tests (and a fun
"let it run" demo). It plays a complete day with a simple greedy policy —
restock for the active recipe, produce, price near the market reference, run
a cheap ad, upgrade when affordable, occasionally travel — then ends the day.
"""

from __future__ import annotations

from . import data
from .customers import reference_price


class Autoplay:
    def __init__(self, rng=None, travel_every: int = 4):
        self.rng = rng
        self.travel_every = travel_every

    def play_day(self, game) -> None:
        assert game.phase == "planning", f"autoplay called in phase {game.phase}"

        p = game.player
        product = data.PRODUCTS[game.active_product]
        usage = game.recipe.usage(product)
        per_cup = sum(usage.values())

        # 1. size production to what the market will actually buy (fresh
        # drinks spoil in ~3 days, so overstocking is a real loss)
        from .customers import expected_customers

        target_cups = int(expected_customers(game) * 1.15) + 5
        target_cups = min(target_cups, 150, int(p.storage_room() / (per_cup + 1.0)))

        # 2. restock ingredients for the target batch (keep ~15% free)
        for ing, units in usage.items():
            have = p.stock(ing)
            need = units * target_cups - have
            if need > 0:
                price = game.local_price(ing)
                affordable = int(p.cash / max(price, 0.01))
                qty = min(need, affordable, p.storage_room())
                if qty > 0:
                    game.buy(ing, qty)

        # 3. produce to top up toward the target (don't pile onto old stock)
        have_products = p.product_stock(game.active_product)
        if have_products < target_cups:
            batch = target_cups - int(have_products)
            if batch >= 10:
                game.produce(batch)

        # 3. price near reference, drifting up with reputation
        ref = reference_price(game)
        game.set_price(round(ref * (1.02 - p.reputation / 3000.0), 2))

        # 4. keep awareness up with cheap ads
        if p.awareness < 35 and p.cash > 400:
            for ad in data.ADS:
                if ad.cost <= 300 and p.cash > ad.cost + 200:
                    game.run_ad(ad.key)
                    break

        # 5. upgrades only once comfortably profitable (never eat the float)
        if p.cash > 2500:
            for eq in data.EQUIPMENT.values():
                if eq.key not in p.equipment and eq.cost < p.cash * 0.5:
                    if eq.requires is None or eq.requires in p.equipment:
                        game.buy_equipment(eq.key)
                        break
            for t in data.TECH.values():
                if t.key not in p.tech and t.cost < p.cash * 0.5:
                    if t.requires is None or t.requires in p.tech:
                        game.buy_tech(t.key)
                        break
            nxt = data.TIERS[p.tier_idx + 1] if p.tier_idx + 1 < len(data.TIERS) else None
            if nxt and nxt.cost < p.cash * 0.5:
                game.upgrade_tier()

        # 6. staff when revenue justifies it
        if p.cash > 3000:
            if "cashier" not in p.employees:
                game.hire("cashier")
            if "cook" not in p.employees and p.cash > 5000:
                game.hire("cook")

        # 7. travel every few days to a better district
        if game.day % self.travel_every == 0 and p.cash > 150:
            best = p.district
            best_score = 0.0
            season = data.season_for_day(game.day)
            for key, d in data.DISTRICTS.items():
                if key == p.district:
                    continue
                score = d.demand * (1.0 - d.competition * 0.5) * \
                    (1.25 if d.key in ("waterfront", "beach") and season.key == "summer" else 1.0)
                if score > best_score:
                    best_score, best = score, key
            if best != p.district:
                game.travel(best)

        # 8. emergency loan if broke, repay if flush
        if p.cash < 200 and p.debt < 4000:
            for opt in data.LOAN_OPTIONS:
                if opt.amount == 2000 and p.debt + 2000 <= data.MAX_DEBT:
                    game.take_loan(opt.key)
                    break
        if p.cash > 6000 and p.debt > 0:
            game.repay_loan(min(2500.0, p.cash - 3500.0))

        # 9. end the day
        game.end_day()
