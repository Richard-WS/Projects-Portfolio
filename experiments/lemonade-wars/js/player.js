// Player state — direct port of player.py: cash, loans, inventory,
// equipment, staff, reputation. Pure simulation state, no UI.
"use strict";

import { EQUIPMENT, INGREDIENTS, PRODUCTS, START_DISTRICT, START_LOAN, START_LOAN_RATE, START_REPUTATION, TIERS } from "./data.js";

const round2 = (v) => Math.round(v * 100) / 100;
const round3 = (v) => Math.round(v * 1000) / 1000;

export class Loan {
  constructor(principal, rate) {
    this.principal = Number(principal);
    this.rate = Number(rate);
  }
}

export class Player {
  constructor(difficulty) {
    // The starting cash plus the proceeds of the $2,000 business loan
    // (the loan itself is recorded as a liability).
    this.cash = round2(difficulty.start_cash + START_LOAN);
    this.loans = [new Loan(START_LOAN, START_LOAN_RATE)];
    this.inventory = {}; // ing -> {qty, age}
    this.products = {}; // key -> {qty, age}
    this.equipment = new Set();
    this.tech = new Set();
    this.tier_idx = 0;
    this.insurance = new Set();
    this.employees = {}; // role -> {skill, morale, days}
    this.awareness = 5.0;
    this.reputation = START_REPUTATION;
    // weekly finance
    this.week_profit = 0.0;
    this.sales_tax_bill = 0.0;
    this.payroll_accum = 0.0;
    this.cleanliness = 60.0;
    this.district = START_DISTRICT;
    this.visited = new Set([START_DISTRICT]);
  }

  // -- money ---------------------------------------------------------------

  get debt() {
    return this.loans.reduce((s, l) => s + l.principal, 0);
  }

  tier() {
    return TIERS[this.tier_idx];
  }

  capacity() {
    let cap = this.tier().storage;
    if (this.equipment.has("squeezer")) cap += 10;
    if (this.equipment.has("juicer")) cap += 15;
    if (this.equipment.has("delivery_vehicle")) cap += 25;
    if (this.equipment.has("storefront")) cap += 100;
    return cap;
  }

  storageUsed() {
    let used = 0;
    for (const s of Object.values(this.inventory)) used += s.qty;
    for (const s of Object.values(this.products)) used += s.qty;
    return used;
  }

  storageRoom() {
    return Math.max(0.0, this.capacity() - this.storageUsed());
  }

  // -- inventory -----------------------------------------------------------

  stock(ing) {
    return this.inventory[ing]?.qty ?? 0.0;
  }

  productStock(key) {
    return this.products[key]?.qty ?? 0.0;
  }

  buyIngredient(ing, qty, price, room = 1e9) {
    qty = round3(Number(qty));
    if (qty <= 0) return false;
    const cost = round2(qty * price);
    if (cost > this.cash + 1e-6) return false;
    if (qty > room + 1e-6) return false;
    this.cash = round2(this.cash - cost);
    const stock = (this.inventory[ing] ??= { qty: 0.0, age: 0 });
    stock.qty = round3(stock.qty + qty);
    return true;
  }

  consume(ing, qty) {
    const stock = this.inventory[ing];
    if (!stock || stock.qty < qty - 1e-6) return false;
    stock.qty = round3(stock.qty - qty);
    if (stock.qty <= 0.01) delete this.inventory[ing];
    return true;
  }

  addProducts(key, qty) {
    const stock = (this.products[key] ??= { qty: 0.0, age: 0 });
    stock.qty = round3(stock.qty + qty);
  }

  ingredientFreshness(product) {
    const used = product.base_recipe;
    let total = 0.0;
    let weightSum = 0.0;
    for (const [k, units] of Object.entries(used)) {
      const inv = this.inventory[k];
      if (!inv || inv.qty <= 0) {
        total += 1.0;
        weightSum += units;
        continue;
      }
      const shelf = Math.max(1, INGREDIENTS[k].shelf);
      total += Math.min(1.0, inv.age / shelf) * units;
      weightSum += units;
    }
    return total / Math.max(weightSum, 1e-6);
  }

  spoilage(game = null) {
    // Age everything one day; return units lost (stats).
    let lost = 0.0;
    const heat = game !== null && game.world.weatherAt(this.district).key === "heat_wave";
    const hasFridge = this.equipment.has("refrigeration");
    const automation = this.tech.has("inventory_automation");
    const chilled = new Set(["ice", "milk", "strawberries", "blueberries", "mango", "organic_fruit", "exotic_fruit"]);

    for (const [k, s] of Object.entries(this.inventory)) {
      s.age += 1;
      const shelf = INGREDIENTS[k].shelf;
      if (s.age > shelf) {
        lost += s.qty;
        delete this.inventory[k];
        continue;
      }
      const ratio = s.age / shelf;
      let loss = 0.0;
      if (heat && !hasFridge && chilled.has(k)) loss += 0.05;
      if (ratio > 0.85 && !hasFridge) loss += 0.02;
      if (loss > 0) {
        let drop = round3(s.qty * loss);
        if (automation) drop *= 0.8;
        s.qty = round3(s.qty - drop);
        lost += drop;
        if (s.qty <= 0.01) delete this.inventory[k];
      }
    }

    for (const [k, s] of Object.entries(this.products)) {
      s.age += 1;
      let shelf = 2 + (hasFridge ? 1 : 0);
      if (k === "coffee" || k === "cold_brew") shelf += 1;
      if (s.age > shelf) {
        lost += s.qty;
        delete this.products[k];
      }
    }
    return lost;
  }

  // -- valuation -----------------------------------------------------------

  inventoryValue(market) {
    let value = 0.0;
    for (const [k, s] of Object.entries(this.inventory)) {
      value += s.qty * market.price(this.district, k);
    }
    for (const [k, s] of Object.entries(this.products)) {
      value += s.qty * PRODUCTS[k].anchor * 0.7;
    }
    return round2(value);
  }

  equipmentValue() {
    let v = 0;
    for (const k of this.equipment) v += EQUIPMENT[k].cost * 0.6;
    return round2(v);
  }

  tierValue() {
    let v = 0;
    for (let i = 0; i < this.tier_idx; i++) v += TIERS[i].cost;
    return round2(v);
  }

  netWorth(market) {
    return round2(
      this.cash + this.inventoryValue(market) + this.equipmentValue() + this.tierValue() - this.debt
    );
  }

  // -- employees -----------------------------------------------------------

  hire(role, rng) {
    if (this.employees[role] || !EMPLOYEE_ROLE_KEYS.has(role)) return false;
    this.employees[role] = {
      skill: round1(rng.uniform(30, 60)),
      morale: 100.0,
      days: 0,
    };
    return true;
  }

  fire(role) {
    return delete this.employees[role];
  }

  dailyWages() {
    let w = 0;
    for (const role of Object.keys(this.employees)) w += EMPLOYEE_ROLES[role].salary;
    return round2(w);
  }

  staffBonus(kind) {
    // kind in service | quality | cleanliness | fuel. Pure — no mutation.
    const vals = {
      cashier: { service: 12, quality: 0, cleanliness: 0 },
      cook: { service: 0, quality: 6, cleanliness: 0 },
      cleaner: { service: 0, quality: 0, cleanliness: 20 },
      driver: { service: 0, quality: 0, cleanliness: 0 },
    };
    let total = 0.0;
    for (const [role, e] of Object.entries(this.employees)) {
      const eff = (e.skill / 50.0) * (0.7 + (0.3 * e.morale) / 100.0);
      total += vals[role][kind] * eff;
    }
    return total;
  }

  tickStaff() {
    for (const e of Object.values(this.employees)) {
      e.morale = Math.max(0.0, e.morale - 0.8);
      e.days += 1;
    }
  }

  snapshot() {
    return {
      cash: this.cash,
      loans: this.loans.map((l) => ({ principal: l.principal, rate: l.rate })),
      inventory: Object.fromEntries(Object.entries(this.inventory).map(([k, v]) => [k, { ...v }])),
      products: Object.fromEntries(Object.entries(this.products).map(([k, v]) => [k, { ...v }])),
      equipment: [...this.equipment].sort(),
      tech: [...this.tech].sort(),
      tier_idx: this.tier_idx,
      insurance: [...this.insurance].sort(),
      employees: Object.fromEntries(Object.entries(this.employees).map(([k, v]) => [k, { ...v }])),
      awareness: this.awareness,
      reputation: this.reputation,
      week_profit: this.week_profit,
      sales_tax_bill: this.sales_tax_bill,
      payroll_accum: this.payroll_accum,
      cleanliness: this.cleanliness,
      district: this.district,
      visited: [...this.visited].sort(),
    };
  }

  static restore(snap, difficulty) {
    const p = new Player(difficulty);
    p.cash = Number(snap.cash);
    p.loans = snap.loans.map((l) => new Loan(l.principal, l.rate));
    p.inventory = Object.fromEntries(Object.entries(snap.inventory).map(([k, v]) => [k, { qty: Number(v.qty), age: Number(v.age) }]));
    p.products = Object.fromEntries(Object.entries(snap.products).map(([k, v]) => [k, { qty: Number(v.qty), age: Number(v.age) }]));
    p.equipment = new Set(snap.equipment);
    p.tech = new Set(snap.tech);
    p.tier_idx = Number(snap.tier_idx);
    p.insurance = new Set(snap.insurance);
    p.employees = Object.fromEntries(Object.entries(snap.employees).map(([k, v]) => [k, { ...v }]));
    p.awareness = Number(snap.awareness);
    p.reputation = Number(snap.reputation);
    p.week_profit = Number(snap.week_profit);
    p.sales_tax_bill = Number(snap.sales_tax_bill);
    p.payroll_accum = Number(snap.payroll_accum);
    p.cleanliness = Number(snap.cleanliness);
    p.district = snap.district;
    p.visited = new Set(snap.visited);
    return p;
  }
}

import { EMPLOYEE_ROLES } from "./data.js";
const EMPLOYEE_ROLE_KEYS = new Set(Object.keys(EMPLOYEE_ROLES));
const round1 = (v) => Math.round(v * 10) / 10;
