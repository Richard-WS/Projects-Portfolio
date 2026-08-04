// Ingredient market — direct port of market.py: per-district prices that
// drift daily, plus temporary event modifiers (shortages, gluts, import
// delays...).
"use strict";

import { DISTRICTS, INGREDIENTS } from "./data.js";

export class IngredientMarket {
  constructor(rng, districts = null, ingredients = null, skipInit = false) {
    this.rng = rng;
    this.districts = districts || Object.keys(DISTRICTS);
    this.ingredients = ingredients || Object.keys(INGREDIENTS);
    this.prices = {}; // [district][ingredient]
    this.modifiers = {}; // ingredient -> multiplier
    // skipInit: restore path must NOT consume rng draws, or the restored
    // stream advances past the saved position (breaks deterministic reloads)
    if (!skipInit) this._initPrices();
  }

  _initPrices() {
    for (const d of this.districts) {
      const mult = DISTRICTS[d].cost_mult;
      this.prices[d] = {};
      for (const [k, ing] of Object.entries(INGREDIENTS)) {
        const raw = ing.base * mult * this.rng.uniform(0.90, 1.10);
        this.prices[d][k] = round3(Math.min(Math.max(raw, ing.base * 0.5), ing.base * 2.4));
      }
    }
  }

  dailyUpdate() {
    for (const d of this.districts) {
      const mult = DISTRICTS[d].cost_mult;
      for (const [k, ing] of Object.entries(INGREDIENTS)) {
        const p = this.prices[d][k];
        const walk = 1.0 + ing.vol * this.rng.gauss(0.0, 1.0) + 0.001;
        let np = p * walk;
        // keep district relativity sane: never walk outside [pmin,pmax]
        const lo = Math.max(ing.base * 0.5, ing.base * mult * 0.45);
        const hi = Math.min(ing.base * 2.4, ing.base * mult * 2.1);
        this.prices[d][k] = round3(Math.min(Math.max(np, lo), hi));
      }
    }
  }

  price(district, ing) {
    const p = this.prices[district][ing];
    return round3(p * (this.modifiers[ing] ?? 1.0));
  }

  setModifier(ing, mult) {
    this.modifiers[ing] = mult;
  }

  clearModifiers() {
    this.modifiers = {};
  }

  snapshot() {
    return { prices: this.prices, modifiers: this.modifiers, rng: this.rng.snapshot() };
  }

  static restore(rng, snap) {
    const m = new IngredientMarket(rng, null, null, true); // no rng draws
    m.prices = {};
    for (const [d, row] of Object.entries(snap.prices)) {
      m.prices[d] = {};
      for (const [k, v] of Object.entries(row)) m.prices[d][k] = Number(v);
    }
    m.modifiers = {};
    for (const [k, v] of Object.entries(snap.modifiers ?? {})) m.modifiers[k] = Number(v);
    return m;
  }
}

export function round3(v) {
  return Math.round(v * 1000) / 1000;
}
