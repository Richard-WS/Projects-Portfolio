// Recipes + player — mirrors test_recipes.py and test_player.py: default
// recipes match the data tables, usage scales with sliders, spoilage ages
// stock, inventory math is exact, net worth reconciles.
"use strict";

import { test } from "node:test";
import assert from "node:assert/strict";

import { Recipe, defaultRecipe, TEMPS } from "../js/recipes.js";
import { Player } from "../js/player.js";
import { RNG } from "../js/rng.js";
import { DIFFICULTIES, DISTRICTS, EQUIPMENT, INGREDIENTS, PRODUCTS, START_LOAN, START_LOAN_RATE } from "../js/data.js";
import { GameState } from "../js/sim.js";

test("default recipes match the product tables", () => {
  for (const [key, p] of Object.entries(PRODUCTS)) {
    const r = defaultRecipe(key);
    assert.equal(r.product_key, key);
    for (const ing of Object.keys(p.base_recipe)) {
      assert.ok(r.usage(p)[ing] > 0, `${key} uses ${ing}`);
    }
  }
});

test("usage scales with sliders", () => {
  const r = defaultRecipe("lemonade");
  const base = r.usage();
  r.sugar = 100;
  r.ice = 100;
  r.fruit = 100;
  const maxed = r.usage();
  assert.ok(maxed.sugar > base.sugar, "more sugar uses more sugar");
  assert.ok(maxed.ice > base.ice, "more ice uses more ice");
  assert.ok(maxed.lemons > base.lemons, "more fruit uses more lemons");
});

test("premium recipe adds sweetener and organic fruit", () => {
  const r = defaultRecipe("lemonade");
  r.premium = true;
  const u = r.usage();
  assert.ok(u.premium_sweetener > 0, "premium sweetener");
  assert.ok(u.organic_fruit > 0, "organic fruit");
});

test("hot products ignore ice but cold products scale it", () => {
  const coffee = defaultRecipe("coffee");
  assert.equal(coffee.usage()["ice"], undefined, "coffee has no ice");
  const lemonade = defaultRecipe("lemonade");
  const cold = lemonade.usage();
  lemonade.temp = "frozen";
  const frozen = lemonade.usage();
  // temp only changes usage for hot products (recipes.py); for cold drinks
  // the temp difference shows up in flavour (refresh), not ingredient math
  assert.equal(frozen.ice, cold.ice, "cold drink ice does not change with temp");
  const fCold = defaultRecipe("lemonade");
  fCold.temp = "cold";
  const fFrozen = defaultRecipe("lemonade");
  fFrozen.temp = "frozen";
  assert.ok(fFrozen.flavour().refresh > fCold.flavour().refresh, "frozen refreshes more");
});

test("flavour vector is within bounds", () => {
  for (const [key] of Object.entries(PRODUCTS)) {
    const r = defaultRecipe(key);
    const f = r.flavour();
    for (const [dim, v] of Object.entries(f)) {
      assert.ok(v >= 0 && v <= 100, `${key} ${dim}=${v}`);
    }
  }
});

test("cost per cup is positive and reasonable", () => {
  for (const [key] of Object.entries(PRODUCTS)) {
    const r = defaultRecipe(key);
    const cost = r.costPerCup(() => 1.0);
    assert.ok(cost > 0.05, `${key} cost ${cost}`);
    assert.ok(cost < 15, `${key} cost ${cost} too high`);
  }
});

test("quality is bounded and improves with equipment", () => {
  const g = new GameState("normal", 99);
  const r = g.recipe;
  const q1 = r.quality(g, PRODUCTS.lemonade);
  g.player.equipment.add("squeezer");
  const q2 = r.quality(g, PRODUCTS.lemonade);
  assert.ok(q1 >= 5 && q1 <= 100, `q1 ${q1}`);
  assert.ok(q2 >= q1, `squeezer should improve quality (${q1} -> ${q2})`);
});

test("player starts with loan + cash per difficulty", () => {
  const p = new Player(DIFFICULTIES.normal);
  assert.equal(p.cash, DIFFICULTIES.normal.start_cash + START_LOAN);
  assert.equal(p.debt, START_LOAN);
  assert.equal(p.loans[0].rate, START_LOAN_RATE);
});

test("buy and consume exact inventory math", () => {
  const p = new Player(DIFFICULTIES.normal);
  assert.ok(p.buyIngredient("lemons", 10, 1.5));
  assert.equal(p.stock("lemons"), 10);
  assert.equal(p.cash, DIFFICULTIES.normal.start_cash + START_LOAN - 15);
  assert.ok(p.consume("lemons", 4));
  assert.equal(p.stock("lemons"), 6);
  assert.ok(!p.consume("lemons", 100), "can't over-consume");
  assert.ok(!p.buyIngredient("lemons", 1e9, 1.5), "can't overspend");
});

test("storage capacity grows with tier and equipment", () => {
  const p = new Player(DIFFICULTIES.normal);
  const base = p.capacity();
  p.equipment.add("squeezer");
  assert.equal(p.capacity(), base + 10);
});

test("spoilage ages and drops old stock", () => {
  const g = new GameState("normal", 3);
  const p = g.player;
  p.buyIngredient("milk", 10, 1.0); // shelf 7
  p.buyIngredient("lemons", 10, 1.0); // shelf 14
  for (let i = 0; i < 8; i++) p.spoilage(g);
  assert.equal(p.stock("milk"), 0, "milk (shelf 7) should be gone after 8 days");
  // lemons only lose stock past 85% of shelf (~11.9 days)
  assert.equal(p.stock("lemons"), 10, "lemons still fresh after 8 days");
  for (let i = 0; i < 7; i++) p.spoilage(g); // now day 15
  assert.ok(p.stock("lemons") < 10, "lemons should lose some after 15 days");
});

test("net worth reconciles cash + inventory + equipment - debt", () => {
  const g = new GameState("normal", 5);
  const p = g.player;
  const before = p.cash;
  p.buyIngredient("lemons", 10, 1.0);
  const nw = p.netWorth(g.market);
  // cash went down by 10, inventory gained 10 lemons at market value
  const expected = p.cash + p.inventoryValue(g.market) + p.equipmentValue() + p.tierValue() - p.debt;
  assert.ok(Math.abs(nw - expected) < 0.01, `nw ${nw} vs ${expected}`);
  assert.ok(before - p.cash >= 9.9, "bought lemons");
});

test("staff hire/fire and bonuses", () => {
  const p = new Player(DIFFICULTIES.normal);
  assert.ok(p.hire("cashier", new RNG(1)));
  assert.ok(!p.hire("cashier", new RNG(1)), "no double hire");
  assert.ok(p.dailyWages() > 0);
  const svc = p.staffBonus("service");
  assert.ok(svc > 0, "cashier boosts service");
  p.fire("cashier");
  assert.equal(p.dailyWages(), 0);
});

test("player snapshot/restore round-trips", () => {
  const p = new Player(DIFFICULTIES.hard);
  p.buyIngredient("sugar", 5, 1.0);
  p.equipment.add("squeezer");
  p.hire("cashier", new RNG(2));
  const r = Player.restore(p.snapshot(), DIFFICULTIES.hard);
  assert.equal(r.cash, p.cash);
  assert.equal(r.stock("sugar"), 5);
  assert.ok(r.equipment.has("squeezer"));
  assert.ok(r.employees.cashier);
  assert.deepEqual(r.loans.map((l) => l.principal), p.loans.map((l) => l.principal));
});
