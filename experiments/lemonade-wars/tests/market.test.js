// Market + world behavior — mirrors test_market.py: seeded price walks stay
// bounded, district relativity holds, weather rolls respect season weights.
"use strict";

import { test } from "node:test";
import assert from "node:assert/strict";

import { IngredientMarket } from "../js/market.js";
import { World, rollWeather } from "../js/world.js";
import { RNG } from "../js/rng.js";
import { DISTRICTS, INGREDIENTS, SEASONS, season_for_day, WEATHER } from "../js/data.js";

test("seeded market prices are deterministic", () => {
  const a = new IngredientMarket(new RNG(7));
  const b = new IngredientMarket(new RNG(7));
  assert.deepEqual(a.prices, b.prices);
});

test("prices start within bounds and stay bounded after 30 days", () => {
  const m = new IngredientMarket(new RNG(11));
  const check = () => {
    for (const d of Object.keys(DISTRICTS)) {
      for (const [k, ing] of Object.entries(INGREDIENTS)) {
        const p = m.prices[d][k];
        assert.ok(p >= ing.base * 0.5, `${d}/${k} too low: ${p}`);
        assert.ok(p <= ing.base * 2.4, `${d}/${k} too high: ${p}`);
      }
    }
  };
  check();
  for (let i = 0; i < 30; i++) m.dailyUpdate();
  check();
});

test("district cost relativity is preserved on average", () => {
  const m = new IngredientMarket(new RNG(5));
  for (let i = 0; i < 20; i++) m.dailyUpdate();
  const cheap = DISTRICTS.industrial.cost_mult;
  const dear = DISTRICTS.stadium.cost_mult;
  const avgCheap = Object.values(INGREDIENTS).reduce((s, ing) => s + m.prices.industrial[ing.key], 0) / Object.keys(INGREDIENTS).length;
  const avgDear = Object.values(INGREDIENTS).reduce((s, ing) => s + m.prices.stadium[ing.key], 0) / Object.keys(INGREDIENTS).length;
  assert.ok(avgCheap < avgDear, `industrial (${avgCheap}) should be cheaper than stadium (${avgDear})`);
});

test("event modifiers apply and clear", () => {
  const m = new IngredientMarket(new RNG(3));
  const before = m.price("downtown", "lemons");
  m.setModifier("lemons", 2.0);
  assert.ok(Math.abs(m.price("downtown", "lemons") / before - 2.0) < 1e-9);
  m.clearModifiers();
  assert.equal(m.price("downtown", "lemons"), before);
});

test("market snapshot/restore round-trips", () => {
  const m = new IngredientMarket(new RNG(9));
  for (let i = 0; i < 5; i++) m.dailyUpdate();
  m.setModifier("sugar", 0.5);
  const snap = m.snapshot();
  const r = IngredientMarket.restore(new RNG(0), snap);
  assert.deepEqual(r.prices, m.prices);
  assert.deepEqual(r.modifiers, m.modifiers);
});

test("world weather is always valid and mostly seasonable", () => {
  const w = new World(new RNG(13));
  w.reset(1);
  for (const d of Object.keys(DISTRICTS)) {
    const key = w.weather[d];
    assert.ok(WEATHER[key], `unknown weather ${key} in ${d}`);
  }
});

test("rollWeather respects season weights (distribution sanity)", () => {
  const rng = new RNG(21);
  const season = season_for_day(90); // summer
  const counts = {};
  for (let i = 0; i < 5000; i++) {
    const k = rollWeather(rng, season);
    counts[k] = (counts[k] ?? 0) + 1;
  }
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  for (const [key, weight] of Object.entries(season.weather_weights)) {
    const share = (counts[key] ?? 0) / total;
    const expected = weight / Object.values(season.weather_weights).reduce((a, b) => a + b, 0);
    assert.ok(Math.abs(share - expected) < 0.04, `${key} share ${share} vs ${expected}`);
  }
});

test("fuel price drifts bounded", () => {
  const w = new World(new RNG(17));
  for (let i = 0; i < 40; i++) w.dailyUpdate(1);
  assert.ok(w.fuel_price >= 2.5 && w.fuel_price <= 6.0, `fuel ${w.fuel_price}`);
});

test("world snapshot/restore round-trips", () => {
  const w = new World(new RNG(23));
  w.reset(60);
  for (let i = 0; i < 3; i++) w.dailyUpdate(60 + i);
  const snap = w.snapshot();
  const r = World.restore(new RNG(0), snap);
  assert.deepEqual(r.weather, w.weather);
  assert.equal(r.fuel_price, w.fuel_price);
});
