// Data table invariants — mirrors test_data.py. Every table the sim relies
// on must be internally consistent: recipes reference real ingredients,
// difficulties have sane bounds, districts sum to real mixes, etc.
"use strict";

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ADS, ADVANCED, BASIC, CASH_FLOOR, DIFFICULTIES, DISTRICTS, DEMOGRAPHICS,
  EMPLOYEE_ROLES, EQUIPMENT, FLAVOUR_DIMS, INGREDIENTS, INSURANCE_TYPES,
  LOAN_OPTIONS, LUXURY, MAX_DEBT, PRODUCTS, SEASONS, STAT_KEYS, TECH, TIERS,
  TITLES, WEATHER, season_for_day,
} from "../js/data.js";

test("ingredients have valid fields", () => {
  for (const [key, ing] of Object.entries(INGREDIENTS)) {
    assert.ok(ing.base > 0, `${key} base`);
    assert.ok(ing.shelf >= 1, `${key} shelf`);
    assert.ok(ing.vol >= 0, `${key} vol`);
    assert.ok(ing.name.length > 0, `${key} name`);
  }
});

test("products reference real ingredients and equipment", () => {
  for (const [key, p] of Object.entries(PRODUCTS)) {
    assert.ok(p.anchor > 0, `${key} anchor`);
    for (const ing of Object.keys(p.base_recipe)) {
      assert.ok(INGREDIENTS[ing], `${key} uses unknown ingredient ${ing}`);
    }
    for (const dim of FLAVOUR_DIMS) {
      assert.ok(p.flavor[dim] !== undefined, `${key} flavor missing ${dim}`);
    }
    if (p.requires) assert.ok(EQUIPMENT[p.requires], `${key} requires unknown equipment`);
    // hot is a truthy flag; cold products leave it unset
    assert.ok(p.hot === undefined || typeof p.hot === "boolean", `${key} hot flag`);
  }
});

test("every product has a default recipe", () => {
  for (const key of Object.keys(PRODUCTS)) {
    const p = PRODUCTS[key];
    assert.ok(Object.keys(p.base_recipe).length > 0, `${key} base_recipe empty`);
  }
});

test("equipment and tech have sane costs and descriptions", () => {
  for (const [key, eq] of Object.entries(EQUIPMENT)) {
    assert.ok(eq.cost > 0, `${key} cost`);
    assert.ok(eq.name.length > 0, `${key} name`);
    assert.ok(eq.desc.length > 0, `${key} desc`);
  }
  for (const [key, t] of Object.entries(TECH)) {
    assert.ok(t.cost > 0, `${key} cost`);
    assert.ok(t.name.length > 0, `${key} name`);
    assert.ok(t.desc.length > 0, `${key} desc`);
  }
});

test("difficulties are complete and ordered", () => {
  for (const [key, d] of Object.entries(DIFFICULTIES)) {
    assert.ok(d.start_cash > 0, `${key} start_cash`);
    // days may be null (endless simulation mode) or a positive integer
    assert.ok(d.days === null || d.days > 0, `${key} days=${d.days}`);
    assert.ok(d.event_mult >= 0, `${key} event_mult`);
    assert.ok(d.competitor_mult >= 0, `${key} competitor_mult`);
    assert.ok(d.loan_mult > 0, `${key} loan_mult`);
    assert.ok(d.patience >= 0, `${key} patience`);
    assert.ok(d.name.length > 0, `${key} name`);
    assert.ok(d.key === key, `${key} key mismatch`);
  }
});

test("districts have complete mixes", () => {
  for (const [key, d] of Object.entries(DISTRICTS)) {
    assert.ok(d.demand > 0, `${key} demand`);
    // competition is a 0..1 fraction of sales lost to rivals
    assert.ok(d.competition >= 0 && d.competition <= 1, `${key} competition`);
    assert.ok(d.cost_mult > 0, `${key} cost_mult`);
    assert.ok(d.fuel >= 0, `${key} fuel`);
    const sum = Object.values(d.mix).reduce((a, b) => a + b, 0);
    assert.ok(Math.abs(sum - 1.0) < 1e-6, `${key} mix sums to ${sum}`);
    for (const demog of Object.keys(d.mix)) {
      assert.ok(DEMOGRAPHICS[demog], `${key} mix uses unknown demographic ${demog}`);
    }
  }
});

test("demographics have taste and preferences on all dims", () => {
  for (const [key, d] of Object.entries(DEMOGRAPHICS)) {
    for (const dim of FLAVOUR_DIMS) {
      assert.ok(d.taste[dim] !== undefined, `${key} taste missing ${dim}`);
      assert.ok(d.pref[dim] !== undefined, `${key} pref missing ${dim}`);
    }
    assert.ok(d.price_sens > 0, `${key} price_sens`);
  }
});

test("seasons cover the year and have weights", () => {
  const seen = new Set();
  for (let day = 1; day <= 366; day++) {
    const s = season_for_day(day);
    assert.ok(s, `no season for day ${day}`);
    assert.ok(s.name && s.key, `season ${day} incomplete`);
    seen.add(s.key);
    for (const w of Object.values(s.weather_weights)) assert.ok(w >= 0);
  }
  assert.ok(seen.size >= 4, `only ${seen.size} distinct seasons in a year`);
  assert.ok(Object.keys(SEASONS).length >= 4);
});

test("weather entries are complete", () => {
  for (const [key, w] of Object.entries(WEATHER)) {
    assert.ok(w.name, `${key} name`);
    assert.ok(w.foot > 0, `${key} foot`);
    assert.ok(w.travel_risk >= 0, `${key} travel_risk`);
    assert.ok(typeof w.refresh_shift === "number" && typeof w.warm_shift === "number", `${key} shifts`);
  }
});

test("tiers progress and are affordable-looking", () => {
  for (const [i, t] of TIERS.entries()) {
    assert.ok(t.storage > 0 && t.max_serve > 0 && t.cust_mult > 0, `tier ${i}`);
    assert.ok(t.name.length > 0, `tier ${i} name`);
  }
  for (let i = 1; i < TIERS.length; i++) {
    assert.ok(TIERS[i].storage > TIERS[i - 1].storage, `tier ${i} storage grows`);
    assert.ok(TIERS[i].cust_mult >= TIERS[i - 1].cust_mult, `tier ${i} cust grows`);
  }
});

test("loans, insurance, ads, titles are consistent", () => {
  for (const o of LOAN_OPTIONS) assert.ok(o.amount > 0 && o.rate > 0 && o.key && o.name);
  for (const i of INSURANCE_TYPES) assert.ok(i.premium > 0 && i.key && i.name);
  for (const a of ADS) assert.ok(a.cost > 0 && a.awareness > 0 && a.duration > 0 && a.key && a.name);
  // titles are listed richest -> poorest; thresholds must strictly decrease
  for (const [i, [thr, name]] of TITLES.entries()) {
    assert.ok(name.length > 0, `title ${i}`);
    assert.ok(thr > 0, `title ${i} threshold`);
    if (i > 0) assert.ok(thr < TITLES[i - 1][0], `title ${i} threshold ${thr} < ${TITLES[i - 1][0]}`);
  }
  for (const role of Object.values(EMPLOYEE_ROLES)) assert.ok(role.salary > 0 && role.name);
});

test("stat keys match the sim's expectations", () => {
  assert.ok(STAT_KEYS.includes("revenue"));
  assert.ok(STAT_KEYS.includes("customers"));
  assert.ok(STAT_KEYS.includes("sold"));
  assert.ok(STAT_KEYS.includes("days"));
  assert.ok(STAT_KEYS.includes("profit"));
  assert.ok(STAT_KEYS.includes("expenses"));
});

test("ingredient sets partition sensibly", () => {
  assert.ok(BASIC.length >= 5, "basic ingredients");
  assert.ok(ADVANCED.length >= 1, "advanced ingredients");
  assert.ok(LUXURY.length >= 1, "luxury ingredients");
  const all = new Set([...BASIC, ...ADVANCED, ...LUXURY]);
  assert.ok(all.size === Object.keys(INGREDIENTS).length, "partition covers all ingredients");
});

test("cash/debt floors exist and are sane", () => {
  assert.ok(CASH_FLOOR < 0, "cash floor is negative (bankruptcy threshold)");
  assert.ok(MAX_DEBT > 1000, "debt ceiling exists");
});
