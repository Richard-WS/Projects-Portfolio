// Customer demand and daily sales resolution — direct port of customers.py.
"use strict";

import { DEMOGRAPHICS, DISTRICTS, PRODUCTS, season_for_day } from "./data.js";

// --------------------------------------------------------------------------
// District / demographic fit
// --------------------------------------------------------------------------

export function districtIdeal(game, includeWeather = true) {
  const d = DISTRICTS[game.player.district];
  const ideal = {};
  for (const dim of Object.keys(DEMOGRAPHICS[Object.keys(d.mix)[0]].taste)) ideal[dim] = 0.0;
  for (const [demogKey, share] of Object.entries(d.mix)) {
    const taste = DEMOGRAPHICS[demogKey].taste;
    for (const dim of Object.keys(ideal)) ideal[dim] += taste[dim] * share;
  }
  if (includeWeather) {
    const w = game.world.weatherAt(game.player.district);
    const season = season_for_day(game.day);
    const shift = (w.refresh_shift + season.refresh_shift) * game.difficulty.weather_mult;
    ideal.refresh += shift;
    const shiftW = (w.warm_shift + season.warm_shift) * game.difficulty.weather_mult;
    ideal.warm += shiftW;
    ideal.fresh -= Math.max(0, shift) * 0.3;
  }
  const out = {};
  for (const [dim, v] of Object.entries(ideal)) out[dim] = clamp(v, 0, 100);
  return out;
}

export function productFit(game, flavour, demogKey = null, includeWeather = true) {
  if (demogKey !== null) {
    const demog = DEMOGRAPHICS[demogKey];
    let dist = 0.0;
    let wsum = 0.0;
    for (const dim of Object.keys(flavour)) {
      const w = demog.pref[dim];
      dist += w * Math.abs(flavour[dim] - demog.taste[dim]);
      wsum += w;
    }
    return round1(100.0 - dist / Math.max(wsum, 1e-6));
  }
  const ideal = districtIdeal(game, includeWeather);
  const d = DISTRICTS[game.player.district];
  let dist = 0.0;
  let wsum = 0.0;
  for (const dim of Object.keys(flavour)) {
    let w = 0.0;
    for (const [demogKey, share] of Object.entries(d.mix)) {
      w += DEMOGRAPHICS[demogKey].pref[dim] * share;
    }
    dist += w * Math.abs(flavour[dim] - ideal[dim]);
    wsum += w;
  }
  return round1(100.0 - dist / Math.max(wsum, 1e-6));
}

// --------------------------------------------------------------------------
// Demand
// --------------------------------------------------------------------------

export function expectedCustomers(game) {
  const p = game.player;
  const d = DISTRICTS[p.district];
  const season = season_for_day(game.day);
  const w = game.world.weatherAt(p.district);

  const base = d.demand * season.foot * w.foot * p.tier().cust_mult;

  const repMult = 0.6 + p.reputation / 160.0;
  const awarenessMult = 0.65 + 0.35 * (1.0 - Math.exp(-p.awareness / 120.0));
  const compMult = 1.0 - d.competition * 0.30 * (0.6 + 0.4 * game.difficulty.competitor_mult);
  let techMult = 1.0;
  if (p.tech.has("online_ordering")) techMult *= 1.15;
  if (p.tech.has("delivery_app")) techMult *= 1.10;
  const storefront = p.equipment.has("storefront") ? 1.4 : 1.0;

  const flavour = game.recipe.flavour(PRODUCTS[game.active_product]);
  const fitMult = 0.7 + (0.6 * productFit(game, flavour)) / 100.0;

  let eventMult = 1.0;
  for (const [name, [mult]] of Object.entries(game.demand_modifiers)) eventMult *= mult;

  let cap = p.tier().max_serve;
  if (p.employees.cashier) cap *= 1.10;
  if (p.equipment.has("cash_register")) cap *= 1.15;

  const customers = base * repMult * awarenessMult * compMult * techMult * storefront * fitMult * eventMult;
  return Math.min(Math.max(customers, 5.0), cap);
}

// --------------------------------------------------------------------------
// Sales resolution
// --------------------------------------------------------------------------

export class SalesReport {
  constructor() {
    this.customers = 0;
    this.sold = 0;
    this.lost = 0;
    this.revenue = 0.0;
    this.avg_satisfaction = 0.0;
    this.repeats = 0;
    this.quality = 0.0;
    this.reference = 0.0;
    this.fit = 0.0;
    this.weather_fit = 0.0;
    this.satisfaction_samples = [];
  }
}

export function weatherFitFor(game, temp) {
  const w = game.world.weatherAt(game.player.district);
  const hotDrink = temp === "hot" || temp === "warm";
  if (!hotDrink) {
    if (w.key === "heat_wave" || w.key === "sunny" || w.key === "humid") return 16.0;
    if (w.key === "cold_snap" || w.key === "snow") return -12.0;
    if (w.key === "rain" || w.key === "thunderstorm" || w.key === "windy") return -5.0;
  } else {
    if (w.key === "cold_snap" || w.key === "snow" || w.key === "rain" || w.key === "thunderstorm") return 16.0;
    if (w.key === "heat_wave" || w.key === "sunny" || w.key === "humid") return -14.0;
  }
  return 0.0;
}

export function referencePrice(game) {
  const product = PRODUCTS[game.active_product];
  const d = DISTRICTS[game.player.district];
  return round2(product.anchor * d.cost_mult * (1.0 + game.player.reputation / 600.0));
}

export function runSales(game) {
  const p = game.player;
  const report = new SalesReport();
  const product = PRODUCTS[game.active_product];
  let stock = p.productStock(game.active_product);
  if (stock <= 0.01) {
    report.customers = Math.floor(expectedCustomers(game));
    report.lost = report.customers;
    return report;
  }

  const flavour = game.recipe.flavour(product);
  const quality = game.recipe.quality(game, product, flavour);
  const ref = referencePrice(game);
  const ratio = game.price / Math.max(ref, 0.01);
  const temp = game.recipe.temp;
  const wfit = weatherFitFor(game, temp);

  report.quality = quality;
  report.reference = ref;
  report.weather_fit = wfit;
  report.fit = productFit(game, flavour);

  const demogKeys = Object.keys(DEMOGRAPHICS);
  const d = DISTRICTS[p.district];
  const mixWeights = demogKeys.map((k) => d.mix[k] ?? 0.0);
  const patience = game.difficulty.patience;
  const loyalty = p.tech.has("loyalty") ? 1.2 : 1.0;
  const revenueMult = p.tech.has("predictive_pricing") ? 1.05 : 1.0;
  const serviceClean = 45.0 + p.staffBonus("service") + p.staffBonus("cleanliness") * 0.5;
  const cleanliness = Math.min(100.0, p.cleanliness + p.staffBonus("cleanliness"));

  let totalSat = 0.0;
  const nCustomers = Math.floor(expectedCustomers(game));
  for (let i = 0; i < nCustomers; i++) {
    if (stock <= 0.01) {
      report.lost += 1;
      continue;
    }
    const demog = DEMOGRAPHICS[game.rng.choices(demogKeys, mixWeights)];
    const priceSens = demog.price_sens * patience;
    let buyChance = 0.92 - priceSens * Math.max(0.0, ratio - 1.0) * 1.5 - (1.0 - quality / 100.0) * 0.22;
    buyChance = clamp(buyChance, 0.04, 0.98);
    if (game.rng.random() >= buyChance) continue;

    stock -= 1;
    report.sold += 1;
    let sat =
      0.58 * quality +
      0.10 * productFit(game, flavour, demog.key) +
      0.14 * wfit +
      0.10 * Math.min(100.0, serviceClean) -
      Math.max(0.0, (ratio - 1.0) * priceSens * 40.0);
    sat = clamp(sat, 3.0, 100.0);
    report.satisfaction_samples.push(sat);
    totalSat += sat;

    if (game.rng.random() < (0.04 + (0.5 * sat) / 100.0) * loyalty) report.repeats += 1;
    const priceNow = game.price * revenueMult;
    report.revenue += priceNow;
    p.sales_tax_bill = round2(p.sales_tax_bill + priceNow * 0.08);
  }

  p.products[game.active_product].qty = round3(stock);
  if (stock <= 0.01) delete p.products[game.active_product];

  report.customers = report.sold + report.lost;
  if (report.satisfaction_samples.length > 0) {
    report.avg_satisfaction = round1(totalSat / report.satisfaction_samples.length);
    const delta = clamp((report.avg_satisfaction - 58.0) * 0.015, -2.0, 3.0);
    p.reputation = round1(clamp(p.reputation + delta, 0.0, 100.0));
  }
  if (report.lost > 0) {
    p.reputation = round1(Math.max(0.0, p.reputation - Math.min(3.0, report.lost / 25.0)));
  }

  // stats
  game.stats.customers += report.customers;
  game.stats.sold += report.sold;
  game.stats.lost_sales += report.lost;
  game.stats.repeat_customers += report.repeats;
  game.stats.revenue = round2(game.stats.revenue + report.revenue);
  p.cash = round2(p.cash + report.revenue);
  return report;
}

const round1 = (v) => Math.round(v * 10) / 10;
const round2 = (v) => Math.round(v * 100) / 100;
const round3 = (v) => Math.round(v * 1000) / 1000;
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
