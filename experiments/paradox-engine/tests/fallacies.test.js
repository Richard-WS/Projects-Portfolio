/* fallacies.test.js — golden hits for the Fallacy Foundry pattern library.
 * Each case pins a classic fallacy to a concrete cue phrase; the clean-text
 * case guards against flagging ordinary prose. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const { scan, FALLACIES } = require("../app/fallacies.js");

const ids = (hits) => hits.map((h) => h.id);

test("library exposes eleven fallacy definitions with notes", () => {
  assert.strictEqual(FALLACIES.length, 11);
  FALLACIES.forEach((f) => {
    assert.ok(f.id && f.name && f.note, `missing fields on ${f.id}`);
    assert.ok(Array.isArray(f.patterns) && f.patterns.length > 0, `no patterns on ${f.id}`);
  });
});

test("golden: appeal to popularity ('everyone knows')", () => {
  const hits = scan("Everyone knows that video games cause violence, so we should ban them.");
  assert.ok(ids(hits).includes("ad-populum"));
});

test("golden: slippery slope ('if we allow ... next')", () => {
  const hits = scan("If we allow dogs in parks, next people will bring horses everywhere.");
  assert.ok(ids(hits).includes("slippery-slope"));
});

test("golden: false dilemma ('either ... or')", () => {
  const hits = scan("Either you're with us or you're against us.");
  assert.ok(ids(hits).includes("false-dilemma"));
});

test("golden: ad hominem ('you're just saying that because')", () => {
  const hits = scan("You're just saying that because you're a teacher.");
  assert.ok(ids(hits).includes("ad-hominem"));
});

test("golden: ad hominem on character ('corrupt fraud')", () => {
  const hits = scan("That politician is a corrupt fraud, so we can't trust anything he says.");
  assert.ok(ids(hits).includes("ad-hominem"));
});

test("golden: hasty generalization ('always')", () => {
  const hits = scan("Women are always late for meetings.");
  assert.ok(ids(hits).includes("hasty-generalization"));
});

test("golden: appeal to authority ('experts agree')", () => {
  const hits = scan("Experts agree that breakfast is the most important meal of the day.");
  assert.ok(ids(hits).includes("appeal-to-authority"));
});

test("golden: loaded language ('outrageous')", () => {
  const hits = scan("The committee's decision is simply outrageous and absurd.");
  assert.ok(ids(hits).includes("loaded-language"));
});

test("golden: straw man ('what you're really saying is')", () => {
  const hits = scan("What you're really saying is that you want to destroy the economy.");
  assert.ok(ids(hits).includes("straw-man"));
});

test("golden: appeal to emotion ('think of the children')", () => {
  const hits = scan("We must ban this game — think of the children!");
  assert.ok(ids(hits).includes("appeal-to-emotion"));
});

test("golden: false cause ('correlation means causation')", () => {
  const hits = scan("Ice cream sales and drowning rates rise together — correlation means causation.");
  assert.ok(ids(hits).includes("false-cause"));
});

test("golden: circular reasoning ('X because X')", () => {
  const hits = scan("The book is true because the book says so.");
  assert.ok(ids(hits).includes("circular-reasoning"));
});

test("golden: hits come back in text order with positions", () => {
  const scanned = "Everyone knows this. Either you agree or you don't.";
  const hits = scan(scanned);
  assert.deepStrictEqual(ids(hits), ["ad-populum", "false-dilemma"]);
  assert.ok(hits[0].index < hits[1].index);
  hits.forEach((h) => {
    assert.strictEqual(scanned.slice(h.index, h.index + h.length), h.phrase);
  });
});

test("clean, ordinary prose is not flagged", () => {
  const hits = scan("The kettle boils when the water reaches one hundred degrees.");
  assert.deepStrictEqual(hits, []);
});

test("a single pattern match is reported once", () => {
  const hits = scan("Everyone knows it, and everyone knows it twice.");
  assert.strictEqual(ids(hits).filter((id) => id === "ad-populum").length, 2);
});
