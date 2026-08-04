// GameState — the single orchestrator that owns a campaign. Direct port of
// sim.py. Pure JS, no DOM: the UI layer is a thin renderer on top.
//
// Day structure:
//   planning (day N)  -> player acts (buy / recipe / price / ad / travel)
//   end_day()         -> sell, spoilage, wages, interest, taxes, events
//   report (day N)    -> night report shown to the player
//   next_day()        -> day N+1: weather, market, events rolled
"use strict";

import { BANKRUPTCY_REASONS, DIFFICULTIES, DISTRICTS, EQUIPMENT, INGREDIENTS, INSURANCE_TYPES, MAX_DEBT, PRODUCTS, STAT_KEYS, TECH, TIERS, TITLES, CASH_FLOOR } from "./data.js";
import { checkAchievements, rollBusinessEvent, rollMorningEvent, rollTravelEvent } from "./events.js";
import { expectedCustomers, referencePrice, runSales } from "./customers.js";
import { IngredientMarket } from "./market.js";
import { Loan, Player } from "./player.js";
import { defaultRecipe, Recipe } from "./recipes.js";
import { RNG } from "./rng.js";
import { World } from "./world.js";

const MONEY_STATS = new Set(["revenue", "expenses", "ad_spend", "interest_paid", "taxes_paid", "best_day_profit", "best_day_revenue"]);
const round2 = (v) => Math.round(v * 100) / 100;

function makeStats() {
  const s = {};
  for (const k of STAT_KEYS) s[k] = MONEY_STATS.has(k) ? 0.0 : 0;
  s.best_bargain = 0.0;
  return s;
}

export class GameState {
  constructor(difficulty_key = "normal", seed = null, days_override = null) {
    this.seed = seed;
    this.difficulty = DIFFICULTIES[difficulty_key];
    this.campaign_days = days_override ?? this.difficulty.days;
    this.rng = new RNG(seed ?? (Date.now() >>> 0));

    this.day = 1;
    this.phase = "planning"; // planning | report
    this.player = new Player(this.difficulty);
    this.world = new World(this.rng);
    this.world.reset(1, this.difficulty.weather_mult);
    this.market = new IngredientMarket(this.rng);

    this.active_product = "lemonade";
    this.recipe = defaultRecipe("lemonade");
    this.price = PRODUCTS.lemonade.anchor;

    this.ads_active = []; // [ad_key, days_left]
    this.market_events = {}; // ing -> [mult, days]
    this.demand_modifiers = {}; // name -> [mult, days]
    this.messages = []; // rolling news log
    this.morning_news = [];

    this.stats = makeStats();
    this.achievements = new Set();

    this.health_fails = 0;
    this.game_over = false;
    this.won = false;
    this.end_reason = "";

    this.day_start_cash = this.player.cash;
    this.day_spent = 0.0;
    this.last_report = null;
  }

  // ------------------------------------------------------------------ util

  log(msg) {
    this.messages.push(`Day ${this.day}: ${msg}`);
    if (this.messages.length > 60) this.messages.splice(0, this.messages.length - 60);
  }

  localPrice(ing) {
    let p = this.market.price(this.player.district, ing);
    if (ing === "ice" && this.player.equipment.has("ice_machine")) p *= 0.7;
    return round3(p);
  }

  netWorth() {
    return this.player.netWorth(this.market);
  }

  title() {
    const nw = this.netWorth();
    for (const [threshold, name] of TITLES) {
      if (nw >= threshold) return name;
    }
    return TITLES[TITLES.length - 1][1];
  }

  campaignDayTotal() {
    return this.campaign_days ?? 999999;
  }

  // ------------------------------------------------------------ day cycle

  beginDay() {
    // Roll the new day: weather, market, event decay, morning news.
    this.world.dailyUpdate(this.day, this.difficulty.weather_mult);
    this.market.dailyUpdate();

    // decay market events
    for (const [ing, [mult, days]] of Object.entries(this.market_events)) {
      const nd = days - 1;
      if (nd <= 0) {
        delete this.market_events[ing];
        if (this.market.modifiers[ing] === mult) delete this.market.modifiers[ing];
      } else {
        this.market_events[ing] = [mult, nd];
      }
    }

    // decay demand modifiers
    for (const [name, [mult, days]] of Object.entries(this.demand_modifiers)) {
      const nd = days - 1;
      if (nd <= 0) delete this.demand_modifiers[name];
      else this.demand_modifiers[name] = [mult, nd];
    }

    // fuel modifier decays with the demand modifier that owns it
    if (!this.demand_modifiers.fuel_spike) this.world.fuel_modifier = 1.0;

    // ads expire, awareness decays
    this.ads_active = this.ads_active.map(([k, d]) => [k, d - 1]).filter(([, d]) => d > 0);
    this.player.awareness = round2(Math.max(0.0, this.player.awareness * 0.75));

    // morning news
    this.morning_news = [];
    const headline = rollMorningEvent(this);
    if (headline) {
      this.morning_news.push(headline);
      this.log(headline);
    }
  }

  endDay() {
    // Run the sell phase and everything after it. Returns the report.
    const p = this.player;

    // 1. sell
    const report = runSales(this);
    const revenue = round2(report.revenue);

    // 2. spoilage
    const spoiled = p.spoilage(this);
    this.stats.spoiled_units += spoiled;

    // 3. wages + staff
    const wages = p.dailyWages();
    p.cash = round2(p.cash - wages);
    p.tickStaff();

    // 4. loan interest
    const rep = p.reputation;
    const credit = rep < 40 ? 1.5 : rep < 70 ? 1.0 : 0.7;
    const interest = round2(
      (p.loans.reduce((s, l) => s + l.principal * l.rate, 0) / 365.0) * this.difficulty.loan_mult * credit
    );
    p.cash = round2(p.cash - interest);
    this.stats.interest_paid = round2(this.stats.interest_paid + interest);

    // 5. insurance premiums (weekly)
    let insuranceCost = 0.0;
    if (this.day % 7 === 0) {
      for (const ins of INSURANCE_TYPES) {
        if (p.insurance.has(ins.key)) insuranceCost += ins.premium;
      }
      p.cash = round2(p.cash - insuranceCost);
    }

    // 6. weekly taxes
    let taxTotal = 0.0;
    if (this.day % 7 === 0) {
      const businessTax = round2(Math.max(0.0, p.week_profit) * 0.15);
      const payrollTax = round2(p.payroll_accum * 0.05);
      taxTotal = round2(businessTax + p.sales_tax_bill + payrollTax);
      p.cash = round2(p.cash - taxTotal);
      this.stats.taxes_paid = round2(this.stats.taxes_paid + taxTotal);
      p.week_profit = 0.0;
      p.sales_tax_bill = 0.0;
      p.payroll_accum = 0.0;
    } else {
      p.week_profit = round2(p.week_profit + (revenue - wages - interest - insuranceCost));
      p.payroll_accum = round2(p.payroll_accum + wages);
    }

    // 7. business / crime events
    const nightEvent = rollBusinessEvent(this);
    if (nightEvent) {
      this.log(nightEvent);
      this.stats.events_survived += 1;
    }

    // 8. cleanliness drift
    const cleaner = p.staffBonus("cleanliness");
    p.cleanliness = round1(Math.min(Math.max(p.cleanliness - 1.5 + cleaner * 0.4, 20.0), 100.0));

    // 9. stats + report
    const dayNet = round2(p.cash - this.day_start_cash);
    this.stats.days = this.day;
    this.stats.expenses = round2(this.stats.expenses + wages + interest + insuranceCost + taxTotal);
    this.stats.profit = round2(this.stats.profit + dayNet);
    this.stats.best_day_revenue = Math.max(this.stats.best_day_revenue, revenue);
    this.stats.best_day_profit = Math.max(this.stats.best_day_profit, dayNet);

    this.last_report = {
      day: this.day,
      customers: report.customers,
      sold: report.sold,
      lost: report.lost,
      revenue,
      avg_satisfaction: report.avg_satisfaction,
      repeats: report.repeats,
      quality: report.quality,
      weather: this.world.weatherAt(p.district).key,
      spoiled: round1(spoiled),
      wages,
      interest,
      insurance: insuranceCost,
      taxes: taxTotal,
      spent: round2(this.day_spent),
      net: dayNet,
      night_event: nightEvent,
    };

    // 10. achievements
    for (const name of checkAchievements(this)) {
      this.log(`Achievement unlocked: ${name}!`);
    }

    // 11. bankruptcy checks
    this._checkBankruptcy();

    this.phase = "report";
    return this.last_report;
  }

  _checkBankruptcy() {
    const p = this.player;
    if (p.debt > MAX_DEBT) {
      this.game_over = true;
      this.won = false;
      this.end_reason = BANKRUPTCY_REASONS.debt;
    } else if (p.cash < CASH_FLOOR) {
      this.game_over = true;
      this.won = false;
      this.end_reason = BANKRUPTCY_REASONS.cash;
    } else if (this.health_fails >= 3) {
      this.game_over = true;
      this.won = false;
      this.end_reason = BANKRUPTCY_REASONS.health;
    }
  }

  nextDay() {
    this.day += 1;
    this.day_start_cash = this.player.cash;
    this.day_spent = 0.0;
    if (this.campaign_days && this.day > this.campaign_days) {
      this.game_over = true;
      this.won = true;
      this.end_reason = "campaign";
      return;
    }
    this.phase = "planning";
    this.beginDay();
  }

  // ------------------------------------------------------------ player actions

  buy(ing, qty) {
    const price = this.localPrice(ing);
    const cost = round2(price * qty);
    if (cost > this.player.cash + 1e-6) return false;
    const room = this.player.storageRoom();
    if (qty > room + 1e-6) return false;
    const ok = this.player.buyIngredient(ing, qty, price, room);
    if (ok) {
      this.day_spent = round2(this.day_spent + cost);
      this.stats.bought_units += qty;
      const base = INGREDIENTS[ing].base * DISTRICTS[this.player.district].cost_mult;
      if (base > 0) {
        this.stats.best_bargain = Math.max(this.stats.best_bargain, 1.0 - price / base);
      }
    }
    return ok;
  }

  produce(batchQty) {
    // Produce `batchQty` cups of the active product. Returns [ok, msg].
    const batch = Math.floor(batchQty);
    if (batch <= 0) return [false, "Pick a batch size first."];
    const product = PRODUCTS[this.active_product];
    if (product.requires && !this.player.equipment.has(product.requires)) {
      return [false, `Requires the ${EQUIPMENT[product.requires].name}.`];
    }
    const usage = this.recipe.usage(product);
    const needed = {};
    for (const [k, v] of Object.entries(usage)) needed[k] = round3(v * batch);

    for (const [k, need] of Object.entries(needed)) {
      if (this.player.stock(k) < need - 1e-6) {
        return [false, `Not enough ${INGREDIENTS[k].name} (need ${gfmt(need)}, have ${gfmt(this.player.stock(k))}).`];
      }
    }
    const space = this.player.storageRoom();
    if (batch > space + 1e-6) {
      return [false, `Not enough storage (need ${gfmt(batch)} units, have ${gfmt(space)}).`];
    }
    for (const [k, need] of Object.entries(needed)) this.player.consume(k, need);
    this.player.addProducts(this.active_product, batch);
    this.stats.batches += 1;
    this.stats.recipes_created += 1;
    this.log(`Produced ${batch} ${product.name}.`);
    return [true, `Produced ${batch} ${product.name}.`];
  }

  setRecipe(recipe) {
    this.recipe = recipe;
  }

  setPrice(price) {
    this.price = round2(Math.min(Math.max(price, 0.25), 99.0));
  }

  runAd(key) {
    const ad = ADS_BY_KEY[key];
    if (ad.cost > this.player.cash + 1e-6) return false;
    this.player.cash = round2(this.player.cash - ad.cost);
    this.player.awareness = round2(Math.min(150.0, this.player.awareness + ad.awareness));
    this.ads_active.push([key, ad.duration]);
    this.stats.ad_spend = round2(this.stats.ad_spend + ad.cost);
    this.day_spent = round2(this.day_spent + ad.cost);
    return true;
  }

  travel(to) {
    if (to === this.player.district) return [false, "Already there."];
    const cost = this.world.travelCost(this.player.district, to, this);
    if (cost > this.player.cash + 1e-6) return [false, `Can't afford the trip ($${cost.toFixed(2)}).`];
    this.player.cash = round2(this.player.cash - cost);
    this.day_spent = round2(this.day_spent + cost);
    this.stats.travel_distance += DISTRICTS[to].fuel;
    this.player.district = to;
    this.player.visited.add(to);
    const headline = rollTravelEvent(this);
    if (headline) {
      this.log(headline);
      return [true, `Arrived at ${DISTRICTS[to].name}. ${headline}`];
    }
    return [true, `Arrived at ${DISTRICTS[to].name}.`];
  }

  takeLoan(key) {
    const option = LOAN_OPTIONS_BY_KEY[key];
    if (this.player.debt + option.amount > MAX_DEBT) return false;
    const rep = this.player.reputation;
    const credit = rep < 40 ? 1.5 : rep < 70 ? 1.0 : 0.7;
    const rate = option.rate * credit * this.difficulty.loan_mult;
    this.player.loans.push(new Loan(option.amount, rate));
    this.player.cash = round2(this.player.cash + option.amount);
    this.stats.loans_taken += 1;
    this.log(`Took a ${option.name} ($${option.amount.toFixed(0)}).`);
    return true;
  }

  repayLoan(amount) {
    amount = round2(Math.min(Math.max(amount, 0.0), this.player.cash));
    if (amount <= 0 || this.player.debt <= 0) return false;
    let remaining = amount;
    // pay the most expensive loan first
    const sorted = [...this.player.loans].sort((a, b) => b.rate - a.rate);
    for (const loan of sorted) {
      if (remaining <= 0) break;
      const pay = Math.min(loan.principal, remaining);
      loan.principal = round2(loan.principal - pay);
      remaining = round2(remaining - pay);
    }
    this.player.loans = this.player.loans.filter((l) => l.principal > 0.01);
    this.player.cash = round2(this.player.cash - amount);
    return true;
  }

  buyEquipment(key) {
    const eq = EQUIPMENT[key];
    if (this.player.equipment.has(key) || eq.cost > this.player.cash + 1e-6) return false;
    if (eq.requires && !this.player.equipment.has(eq.requires)) return false;
    this.player.cash = round2(this.player.cash - eq.cost);
    this.player.equipment.add(key);
    this.day_spent = round2(this.day_spent + eq.cost);
    this.log(`Bought the ${eq.name}.`);
    return true;
  }

  buyTech(key) {
    const t = TECH[key];
    if (this.player.tech.has(key) || t.cost > this.player.cash + 1e-6) return false;
    if (t.requires && !this.player.tech.has(t.requires)) return false;
    this.player.cash = round2(this.player.cash - t.cost);
    this.player.tech.add(key);
    this.day_spent = round2(this.day_spent + t.cost);
    this.log(`Unlocked ${t.name}.`);
    return true;
  }

  upgradeTier() {
    if (this.player.tier_idx + 1 >= TIERS.length) return false;
    const nxt = TIERS[this.player.tier_idx + 1];
    if (nxt.cost > this.player.cash + 1e-6) return false;
    this.player.cash = round2(this.player.cash - nxt.cost);
    this.player.tier_idx += 1;
    this.day_spent = round2(this.day_spent + nxt.cost);
    this.log(`Upgraded to a ${nxt.name}.`);
    return true;
  }

  toggleInsurance(key) {
    const ins = INSURANCE_BY_KEY[key];
    if (this.player.insurance.has(key)) {
      this.player.insurance.delete(key);
    } else {
      if (ins.premium > this.player.cash + 1e-6) return false;
      this.player.cash = round2(this.player.cash - ins.premium);
      this.day_spent = round2(this.day_spent + ins.premium);
      this.player.insurance.add(key);
    }
    return true;
  }

  hire(role) {
    return this.player.hire(role, this.rng);
  }

  fire(role) {
    return this.player.fire(role);
  }

  // ------------------------------------------------------------ forecasting

  forecast() {
    // Rough sales estimate for the Sell tab.
    const customers = expectedCustomers(this);
    const stock = this.player.productStock(this.active_product);
    const ref = referencePrice(this);
    const ratio = this.price / Math.max(ref, 0.01);
    const quality = this.recipe.quality(this, PRODUCTS[this.active_product]);
    let buyRate = 0.92 - Math.max(0.0, ratio - 1.0) * 1.2 - (1.0 - quality / 100.0) * 0.22;
    buyRate = Math.min(Math.max(buyRate, 0.04), 0.98);
    const buyers = Math.min(Math.floor(customers * buyRate), stock);
    const revenue = round2(buyers * this.price);
    return { customers: Math.floor(customers), buyers, revenue, stock, quality, reference: ref, ratio };
  }

  // ------------------------------------------------------------ save/load

  toDict() {
    return gameToDict(this);
  }

  static fromDict(d) {
    return gameFromDict(d);
  }

  save() {
    // localStorage save — returns the JSON string for storage.
    return JSON.stringify(this.toDict());
  }

  static load(json) {
    if (!json) return null;
    try {
      return gameFromDict(JSON.parse(json));
    } catch {
      return null;
    }
  }
}

// ---------------------------------------------------------------------------
// Save/load serialization (saveload.py port)
// ---------------------------------------------------------------------------

export const SAVE_VERSION = 1;

export function gameToDict(game) {
  return {
    version: SAVE_VERSION,
    difficulty: game.difficulty.key,
    seed: game.seed,
    rng: game.rng.snapshot(),
    day: game.day,
    phase: game.phase,
    campaign_days: game.campaign_days,
    player: game.player.snapshot(),
    market: game.market.snapshot(),
    world: game.world.snapshot(),
    active_product: game.active_product,
    recipe: game.recipe.snapshot(),
    price: game.price,
    ads_active: game.ads_active.map((a) => [...a]),
    market_events: Object.fromEntries(Object.entries(game.market_events).map(([k, v]) => [k, [...v]])),
    demand_modifiers: Object.fromEntries(Object.entries(game.demand_modifiers).map(([k, v]) => [k, [...v]])),
    messages: [...game.messages],
    stats: { ...game.stats },
    achievements: [...game.achievements].sort(),
    health_fails: game.health_fails,
    game_over: game.game_over,
    won: game.won,
    end_reason: game.end_reason,
    day_start_cash: game.day_start_cash,
    day_spent: game.day_spent,
  };
}

export function gameFromDict(d) {
  const game = new GameState(d.difficulty ?? "normal", d.seed ?? null, d.campaign_days ?? null);
  game.rng = RNG.restore(d.rng ?? { seed: 0 });
  game.day = Number(d.day);
  game.phase = d.phase ?? "planning";
  game.player = Player.restore(d.player, game.difficulty);
  game.market = IngredientMarket.restore(game.rng, d.market);
  game.world = World.restore(game.rng, d.world);
  game.active_product = d.active_product;
  game.recipe = RecipeRestore(d.recipe);
  game.price = Number(d.price);
  game.ads_active = (d.ads_active ?? []).map((a) => [...a]);
  game.market_events = Object.fromEntries(Object.entries(d.market_events ?? {}).map(([k, v]) => [k, [...v]]));
  game.demand_modifiers = Object.fromEntries(Object.entries(d.demand_modifiers ?? {}).map(([k, v]) => [k, [...v]]));
  game.messages = [...(d.messages ?? [])];
  game.stats = { ...makeStats(), ...(d.stats ?? {}) };
  game.achievements = new Set(d.achievements ?? []);
  game.health_fails = Number(d.health_fails ?? 0);
  game.game_over = Boolean(d.game_over);
  game.won = Boolean(d.won);
  game.end_reason = d.end_reason ?? "";
  game.day_start_cash = Number(d.day_start_cash ?? game.player.cash);
  game.day_spent = Number(d.day_spent ?? 0.0);
  return game;
}

import { ADS, LOAN_OPTIONS } from "./data.js";
const ADS_BY_KEY = Object.fromEntries(ADS.map((a) => [a.key, a]));
const LOAN_OPTIONS_BY_KEY = Object.fromEntries(LOAN_OPTIONS.map((o) => [o.key, o]));
const INSURANCE_BY_KEY = Object.fromEntries(INSURANCE_TYPES.map((i) => [i.key, i]));
function RecipeRestore(snap) {
  return Recipe.restore(snap);
}
const round1 = (v) => Math.round(v * 10) / 10;
const round3 = (v) => Math.round(v * 1000) / 1000;
function gfmt(v) {
  return String(Math.round(v * 100) / 100);
}
