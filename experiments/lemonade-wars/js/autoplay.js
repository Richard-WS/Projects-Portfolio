// Autoplay: a scripted player used by tests and the "let it run" demo.
// Direct port of autoplay.py — a simple greedy policy that plays a complete
// day: restock, produce, price near reference, cheap ad, upgrade when
// affordable, occasionally travel, then end the day.
"use strict";

import { ADS, DISTRICTS, EQUIPMENT, PRODUCTS, season_for_day, TECH, TIERS } from "./data.js";
import { expectedCustomers, referencePrice } from "./customers.js";

export class Autoplay {
  constructor(travelEvery = 4) {
    this.travelEvery = travelEvery;
  }

  playDay(game) {
    if (game.phase !== "planning") throw new Error(`autoplay called in phase ${game.phase}`);

    const p = game.player;
    const product = PRODUCTS[game.active_product];
    const usage = game.recipe.usage(product);
    let perCup = 0;
    for (const v of Object.values(usage)) perCup += v;

    // 1. size production to what the market will actually buy
    let targetCups = Math.floor(expectedCustomers(game) * 1.15) + 5;
    targetCups = Math.min(targetCups, 150, Math.floor(p.storageRoom() / (perCup + 1.0)));

    // 2. restock ingredients for the target batch
    for (const [ing, units] of Object.entries(usage)) {
      const have = p.stock(ing);
      const need = units * targetCups - have;
      if (need > 0) {
        const price = game.localPrice(ing);
        const affordable = Math.floor(p.cash / Math.max(price, 0.01));
        const qty = Math.min(need, affordable, p.storageRoom());
        if (qty > 0) game.buy(ing, qty);
      }
    }

    // 3. produce to top up toward the target
    const haveProducts = p.productStock(game.active_product);
    if (haveProducts < targetCups) {
      const batch = targetCups - Math.floor(haveProducts);
      if (batch >= 10) game.produce(batch);
    }

    // 3. price near reference, drifting up with reputation
    const ref = referencePrice(game);
    game.setPrice(round2(ref * (1.02 - p.reputation / 3000.0)));

    // 4. keep awareness up with cheap ads
    if (p.awareness < 35 && p.cash > 400) {
      for (const ad of ADS) {
        if (ad.cost <= 300 && p.cash > ad.cost + 200) {
          game.runAd(ad.key);
          break;
        }
      }
    }

    // 5. upgrades only once comfortably profitable
    if (p.cash > 2500) {
      for (const eq of Object.values(EQUIPMENT)) {
        if (!p.equipment.has(eq.key) && eq.cost < p.cash * 0.5) {
          if (eq.requires === null || p.equipment.has(eq.requires)) {
            game.buyEquipment(eq.key);
            break;
          }
        }
      }
      for (const t of Object.values(TECH)) {
        if (!p.tech.has(t.key) && t.cost < p.cash * 0.5) {
          if (t.requires === null || p.tech.has(t.requires)) {
            game.buyTech(t.key);
            break;
          }
        }
      }
      const nxt = TIERS[p.tier_idx + 1];
      if (nxt && nxt.cost < p.cash * 0.5) game.upgradeTier();
    }

    // 6. staff when revenue justifies it
    if (p.cash > 3000) {
      if (!p.employees.cashier) game.hire("cashier");
      if (!p.employees.cook && p.cash > 5000) game.hire("cook");
    }

    // 7. travel every few days to a better district
    if (game.day % this.travelEvery === 0 && p.cash > 150) {
      let best = p.district;
      let bestScore = 0.0;
      const season = season_for_day(game.day);
      for (const [key, d] of Object.entries(DISTRICTS)) {
        if (key === p.district) continue;
        let score = d.demand * (1.0 - d.competition * 0.5);
        if ((d.key === "waterfront" || d.key === "beach") && season.key === "summer") score *= 1.25;
        if (score > bestScore) {
          bestScore = score;
          best = key;
        }
      }
      if (best !== p.district) game.travel(best);
    }

    // 8. emergency loan if broke, repay if flush
    if (p.cash < 200 && p.debt < 4000) {
      for (const opt of LOAN_OPTIONS) {
        if (opt.amount === 2000 && p.debt + 2000 <= 6000) {
          game.takeLoan(opt.key);
          break;
        }
      }
    }
    if (p.cash > 6000 && p.debt > 0) {
      game.repayLoan(Math.min(2500.0, p.cash - 3500.0));
    }

    // 9. end the day
    game.endDay();
  }
}

import { LOAN_OPTIONS } from "./data.js";
const round2 = (v) => Math.round(v * 100) / 100;
