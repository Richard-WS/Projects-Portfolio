// Recipe designer and product quality model — direct port of recipes.py.
"use strict";

import { FLAVOUR_DIMS, PRODUCTS } from "./data.js";

export const TEMPS = {
  cold: "Cold",
  extra_cold: "Extra Cold",
  frozen: "Frozen",
  hot: "Hot",
  warm: "Warm",
};

export const FRUIT_KEYS = new Set(["lemons", "strawberries", "blueberries", "mango", "lime", "mint", "organic_fruit", "exotic_fruit"]);

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
const round1 = (v) => Math.round(v * 10) / 10;
const round3 = (v) => Math.round(v * 1000) / 1000;

export class Recipe {
  constructor(product_key, sugar = 50, ice = 50, fruit = 50, premium = false, temp = null) {
    this.product_key = product_key;
    this.sugar = clamp(Math.round(sugar), 0, 100);
    this.ice = clamp(Math.round(ice), 0, 100);
    this.fruit = clamp(Math.round(fruit), 0, 100);
    this.premium = Boolean(premium);
    const product = PRODUCTS[product_key];
    this.temp = temp || (product.hot ? "hot" : "extra_cold");
  }

  // -- ingredient usage ---------------------------------------------------

  usage(product = null) {
    product = product || PRODUCTS[this.product_key];
    const out = {};
    const sugarScale = 0.5 + this.sugar / 100.0;
    const iceScale = 0.5 + this.ice / 100.0;
    const fruitScale = 0.5 + this.fruit / 100.0;

    for (const [ing, units] of Object.entries(product.base_recipe)) {
      let u = units;
      if (ing === "sugar") u = units * sugarScale;
      else if (ing === "ice") u = units * iceScale;
      else if (FRUIT_KEYS.has(ing)) u = units * fruitScale;
      out[ing] = u;
    }

    const tempIce = { cold: 1.0, extra_cold: 1.3, frozen: 1.6, hot: 0.0, warm: 0.0 }[this.temp];
    if (out.ice !== undefined) {
      out.ice = out.ice * (product.hot ? tempIce : 1.0);
      if (tempIce === 0.0 && product.hot) delete out.ice;
    }

    if (this.premium) {
      out.premium_sweetener = (out.premium_sweetener ?? 0.0) + 0.5;
      const hasFruit = Object.keys(product.base_recipe).some((k) => FRUIT_KEYS.has(k));
      if (hasFruit) out.organic_fruit = (out.organic_fruit ?? 0.0) + 0.5;
    }
    const clean = {};
    for (const [k, v] of Object.entries(out)) clean[k] = round3(v);
    return clean;
  }

  // -- flavour vector -----------------------------------------------------

  flavour(product = null) {
    product = product || PRODUCTS[this.product_key];
    const f = { ...product.flavor };
    f.sweet += (this.sugar - 50) * 0.35;
    f.fresh -= (this.sugar - 50) * 0.10;
    if (Object.keys(product.base_recipe).some((k) => FRUIT_KEYS.has(k))) {
      f.fresh += (this.fruit - 50) * 0.15;
      f.acid += (this.fruit - 50) * 0.20;
    }
    if (!product.hot) {
      f.refresh += (this.ice - 50) * 0.35;
      f.refresh += { cold: 0, extra_cold: 12, frozen: 18, hot: -15, warm: -10 }[this.temp];
    } else {
      f.warm += this.temp === "hot" ? 10 : -20;
    }
    if (this.premium) f.premium += 25;
    const out = {};
    for (const [k, v] of Object.entries(f)) out[k] = round1(clamp(v, 0, 100));
    return out;
  }

  // -- cost and quality ---------------------------------------------------

  costPerCup(priceFn) {
    const product = PRODUCTS[this.product_key];
    let total = 0.0;
    for (const [ing, units] of Object.entries(this.usage(product))) {
      total += units * priceFn(ing);
    }
    return round3(total);
  }

  quality(game = null, product = null, flavour = null) {
    product = product || PRODUCTS[this.product_key];
    flavour = flavour || this.flavour(product);
    let dist = 0;
    for (const d of FLAVOUR_DIMS) dist += Math.abs(flavour[d] - product.flavor[d]);
    let q = 100.0 - dist / FLAVOUR_DIMS.length;
    if (game !== null) {
      const eq = game.player.equipment;
      if (eq.has("squeezer")) q += 3;
      if (eq.has("juicer")) q += 4;
      if (eq.has("blender") && (product.key === "smoothie" || product.key === "fruit_punch")) q += 5;
      if (eq.has("coffee_machine") && (product.key === "coffee" || product.key === "cold_brew")) q += 4;
      const emp = game.player.employees.cook;
      if (emp) q += emp.skill * 0.06;
      const ratio = game.player.ingredientFreshness(product);
      q -= ratio * 25;
    }
    return round1(clamp(q, 5, 100));
  }

  snapshot() {
    return { product: this.product_key, sugar: this.sugar, ice: this.ice, fruit: this.fruit, premium: this.premium, temp: this.temp };
  }

  static restore(snap) {
    return new Recipe(snap.product, snap.sugar, snap.ice, snap.fruit, snap.premium, snap.temp);
  }
}

export function defaultRecipe(product_key) {
  return new Recipe(product_key);
}
