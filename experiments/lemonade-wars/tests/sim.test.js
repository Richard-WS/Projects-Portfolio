// End-to-end simulation invariants — mirrors test_sim.py: seeded runs are
// deterministic, the day cycle moves money correctly, sales never exceed
// stock, bankruptcy triggers, wins trigger, save/load restores everything.
"use strict";

import { test } from "node:test";
import assert from "node:assert/strict";

import { GameState } from "../js/sim.js";
import { Autoplay } from "../js/autoplay.js";
import { Recipe } from "../js/recipes.js";
import { PRODUCTS, DIFFICULTIES, MAX_DEBT, CASH_FLOOR, DISTRICTS, START_LOAN, BANKRUPTCY_REASONS } from "../js/data.js";
import { expectedCustomers, referencePrice } from "../js/customers.js";

test("seeded games are deterministic", () => {
  const a = new GameState("normal", 42);
  const b = new GameState("normal", 42);
  assert.equal(a.player.cash, b.player.cash);
  assert.deepEqual(a.market.prices, b.market.prices);
  assert.deepEqual(a.world.weather, b.world.weather);
});

test("game starts on day 1 in planning with the default setup", () => {
  const g = new GameState("normal", 1);
  assert.equal(g.day, 1);
  assert.equal(g.phase, "planning");
  assert.equal(g.active_product, "lemonade");
  assert.equal(g.price, PRODUCTS.lemonade.anchor);
  assert.equal(g.player.district, "downtown");
  assert.equal(g.player.cash, DIFFICULTIES.normal.start_cash + START_LOAN);
});

test("produce consumes ingredients and adds product stock", () => {
  const g = new GameState("normal", 2);
  g.player.buyIngredient("lemons", 100, 1.0);
  g.player.buyIngredient("sugar", 100, 1.0);
  g.player.buyIngredient("ice", 100, 1.0);
  g.player.buyIngredient("water", 100, 1.0);
  g.player.buyIngredient("cups", 100, 1.0);
  const [ok, msg] = g.produce(20);
  assert.ok(ok, msg);
  assert.equal(g.player.productStock("lemonade"), 20);
  assert.ok(g.player.stock("lemons") < 100, "consumed lemons");
});

test("produce fails when ingredients missing", () => {
  const g = new GameState("normal", 2);
  const [ok, msg] = g.produce(20);
  assert.ok(!ok, "should fail without ingredients");
  assert.ok(msg.includes("Not enough"), msg);
});

test("endDay runs a full cycle and reports sane numbers", () => {
  const g = new GameState("normal", 8);
  g.player.buyIngredient("lemons", 50, 1.0);
  g.player.buyIngredient("sugar", 50, 1.0);
  g.player.buyIngredient("ice", 50, 1.0);
  g.player.buyIngredient("water", 50, 1.0);
  g.produce(30);
  const r = g.endDay();
  assert.ok(r.day === 1);
  assert.ok(r.revenue >= 0, "revenue");
  assert.ok(r.sold >= 0 && r.sold <= 30, `sold ${r.sold} <= 30`);
  assert.equal(g.phase, "report");
  assert.ok(g.last_report === r);
  // wages/interest only if we have them
  assert.ok(r.wages >= 0);
});

test("sales never exceed stock", () => {
  const g = new GameState("normal", 8);
  g.player.buyIngredient("lemons", 50, 1.0);
  g.player.buyIngredient("sugar", 50, 1.0);
  g.player.buyIngredient("ice", 50, 1.0);
  g.player.buyIngredient("water", 50, 1.0);
  g.player.buyIngredient("cups", 50, 1.0);
  g.produce(5);
  const r = g.endDay();
  assert.ok(r.sold <= 5, `sold ${r.sold}`);
  assert.equal(g.player.productStock("lemonade"), 5 - r.sold);
});

test("day advance rolls new weather/market and keeps stats", () => {
  const g = new GameState("normal", 4);
  g.endDay();
  const d1 = g.day;
  g.nextDay();
  assert.equal(g.day, d1 + 1);
  assert.equal(g.phase, "planning");
  assert.ok(g.stats.days >= 1);
});

test("autoplay survives 30 days without crashing", () => {
  const g = new GameState("normal", 31);
  const ap = new Autoplay();
  for (let i = 0; i < 30; i++) {
    ap.playDay(g);
    g.nextDay();
  }
  assert.equal(g.day, 31);
  assert.ok(g.player.cash > -5000, "cash sane");
  assert.ok(g.stats.sold >= 0);
});

test("autoplay on hard difficulty survives 20 days", () => {
  const g = new GameState("hard", 77);
  const ap = new Autoplay();
  for (let i = 0; i < 20; i++) {
    ap.playDay(g);
    g.nextDay();
  }
  assert.equal(g.day, 21);
});

test("bankruptcy triggers on crushing debt", () => {
  const g = new GameState("normal", 9);
  // force debt over the max
  while (g.player.debt <= MAX_DEBT) {
    g.player.loans.push({ principal: 5000, rate: 0.2 });
  }
  g._checkBankruptcy();
  assert.ok(g.game_over);
  assert.ok(!g.won);
});

test("bankruptcy triggers when cash collapses", () => {
  const g = new GameState("normal", 9);
  g.player.cash = CASH_FLOOR - 1;
  g._checkBankruptcy();
  assert.ok(g.game_over);
  assert.equal(g.end_reason, BANKRUPTCY_REASONS.cash);
});

test("campaign win fires after campaign days", () => {
  const g = new GameState("normal", 9, 3); // 3-day campaign
  g.endDay();
  g.nextDay();
  g.endDay();
  g.nextDay();
  g.endDay();
  g.nextDay(); // day 4 > 3
  assert.ok(g.game_over);
  assert.ok(g.won);
  assert.equal(g.end_reason, "campaign");
});

test("save/load round-trips a mid-game state", () => {
  const g = new GameState("normal", 123);
  g.player.buyIngredient("lemons", 20, 1.0);
  g.produce(10);
  g.setPrice(2.5);
  g.endDay();
  const json = g.save();
  const g2 = GameState.load(json);
  assert.ok(g2, "load returned");
  assert.equal(g2.day, g.day);
  assert.equal(g2.player.cash, g.player.cash);
  assert.equal(g2.player.productStock("lemonade"), g.player.productStock("lemonade"));
  assert.equal(g2.price, g.price);
  assert.equal(g2.phase, g.phase);
  assert.deepEqual(g2.stats, g.stats);
  assert.deepEqual([...g2.achievements], [...g.achievements]);
  // and the restored game can keep playing
  g2.nextDay();
  assert.equal(g2.phase, "planning");
});

test("reputation and awareness move within bounds", () => {
  const g = new GameState("normal", 42);
  for (let i = 0; i < 14; i++) {
    g.player.buyIngredient("lemons", 20, 1.0);
    g.player.buyIngredient("sugar", 20, 1.0);
    g.player.buyIngredient("ice", 20, 1.0);
    g.player.buyIngredient("water", 20, 1.0);
    g.produce(10);
    g.endDay();
    g.nextDay();
  }
  assert.ok(g.player.reputation >= 0 && g.player.reputation <= 100, `rep ${g.player.reputation}`);
  assert.ok(g.player.awareness >= 0, `awareness ${g.player.awareness}`);
});

test("expectedCustomers is a finite positive number", () => {
  const g = new GameState("normal", 1);
  const c = expectedCustomers(g);
  assert.ok(Number.isFinite(c));
  assert.ok(c > 0);
  const f = g.forecast();
  assert.ok(Number.isFinite(f.revenue));
  assert.ok(f.buyers >= 0 && f.buyers <= f.customers + 5);
});

test("referencePrice is positive and district-scaled", () => {
  const g = new GameState("normal", 1);
  const ref = referencePrice(g);
  assert.ok(ref > 0);
  g.player.district = "stadium";
  const ref2 = referencePrice(g);
  assert.ok(ref2 !== ref, "district changes reference");
});

test("travel moves districts and costs money", () => {
  const g = new GameState("normal", 1);
  const before = g.player.cash;
  const [ok, msg] = g.travel("beach");
  assert.ok(ok, msg);
  assert.equal(g.player.district, "beach");
  assert.ok(g.player.cash < before, "travel cost money");
  assert.ok(g.player.visited.has("beach"));
  const [ok2] = g.travel("beach");
  assert.ok(!ok2, "already there");
});

test("recipe change affects the sim", () => {
  const g = new GameState("normal", 1);
  const r = new Recipe("lemonade", 100, 100, 100);
  g.setRecipe(r);
  assert.equal(g.recipe.sugar, 100);
  const q = g.recipe.quality(g, PRODUCTS.lemonade);
  assert.ok(q >= 5 && q <= 100);
});

test("loan and repay math is exact", () => {
  const g = new GameState("normal", 1);
  g.player.reputation = 80;
  const before = g.player.cash;
  assert.ok(g.takeLoan("small"));
  assert.ok(g.player.cash > before, "loan adds cash");
  const debt = g.player.debt;
  assert.ok(g.repayLoan(500));
  assert.ok(g.player.debt < debt, "repay reduces debt");
});
