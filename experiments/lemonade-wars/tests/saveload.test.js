// Save/load round-trips — the whole game serializes to JSON and back
// without losing state, across a mid-campaign run.
"use strict";

import { test } from "node:test";
import assert from "node:assert/strict";

import { GameState, gameFromDict, gameToDict } from "../js/sim.js";
import { Autoplay } from "../js/autoplay.js";

function runToDay(n, seed = 5) {
  const g = new GameState("normal", seed, 60);
  const ap = new Autoplay();
  for (let i = 0; i < n; i++) {
    ap.playDay(g);
    g.nextDay();
  }
  return g;
}

test("full game JSON round-trip preserves everything", () => {
  const g = runToDay(12, 99);
  const d = gameToDict(g);
  const g2 = gameFromDict(d);
  assert.equal(g2.day, g.day);
  assert.equal(g2.phase, g.phase);
  assert.equal(g2.player.cash, g.player.cash);
  assert.equal(g2.player.debt, g.player.debt);
  assert.equal(g2.player.reputation, g.player.reputation);
  assert.equal(g2.player.district, g.player.district);
  assert.equal(g2.player.awareness, g.player.awareness);
  assert.equal(g2.active_product, g.active_product);
  assert.equal(g2.price, g.price);
  assert.deepEqual(g2.player.inventory, g.player.inventory);
  assert.deepEqual(g2.player.products, g.player.products);
  assert.deepEqual([...g2.player.equipment].sort(), [...g.player.equipment].sort());
  assert.deepEqual([...g2.player.tech].sort(), [...g.player.tech].sort());
  assert.deepEqual([...g2.player.visited].sort(), [...g.player.visited].sort());
  assert.deepEqual(g2.market.prices, g.market.prices);
  assert.deepEqual(g2.world.weather, g.world.weather);
  assert.equal(g2.world.fuel_price, g.world.fuel_price);
  assert.deepEqual(g2.stats, g.stats);
  assert.deepEqual(g2.ads_active, g.ads_active);
  assert.deepEqual(g2.demand_modifiers, g.demand_modifiers);
});

test("JSON round-trip preserves the rng stream (same next rolls)", () => {
  const g = runToDay(5, 7);
  const g2 = gameFromDict(gameToDict(g));
  // both should now roll the same weather
  g.nextDay();
  g2.nextDay();
  assert.deepEqual(g.world.weather, g2.world.weather, "weather stream matches");
  assert.deepEqual(g.market.prices, g2.market.prices, "market stream matches");
});

test("save string round-trips through JSON.parse", () => {
  const g = runToDay(8, 21);
  const json = g.save();
  const g2 = GameState.load(json);
  assert.ok(g2);
  assert.equal(g2.day, g.day);
  assert.equal(g2.player.cash, g.player.cash);
});

test("load of garbage returns null, not crash", () => {
  assert.equal(GameState.load(null), null);
  assert.equal(GameState.load(""), null);
  assert.equal(GameState.load("{not json"), null);
  assert.equal(GameState.load('{"version":999}'), null);
});
