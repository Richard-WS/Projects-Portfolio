/* preferences.test.js — golden tournaments for the Preference Paradox Lab.
 * Each case freezes a completed preference graph and its verdict. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const { matchups, analyze, findCycles } = require("../app/preferences.js");

/* Tournament builders */
function picksFor(pairs, choice) {
  /* choice: "first" | "second" — picks the earlier/later option of every pair */
  return pairs.map((p) => (choice === "first" ? { winner: p[0], loser: p[1] } : { winner: p[1], loser: p[0] }));
}

test("matchups: four items produce six pairs", () => {
  const pairs = matchups(["A", "B", "C", "D"]);
  assert.strictEqual(pairs.length, 6);
  assert.deepStrictEqual(pairs[0], ["A", "B"]);
  assert.deepStrictEqual(pairs[5], ["C", "D"]);
});

test("golden: a transitive set has a Condorcet winner and no cycles", () => {
  const items = ["A", "B", "C"];
  const pairs = matchups(items);
  /* A > B, B > C, A > C */
  const picks = [
    { winner: "A", loser: "B" },
    { winner: "A", loser: "C" },
    { winner: "B", loser: "C" },
  ];
  const r = analyze(items, picks);
  assert.strictEqual(r.transitive, true);
  assert.deepStrictEqual(r.cycles, []);
  assert.deepStrictEqual(r.condorcet, ["A"]);
  assert.strictEqual(r.wins.A, 2);
  assert.strictEqual(r.wins.C, 0);
  assert.deepStrictEqual(r.ranking, ["A", "B", "C"]);
});

test("golden: A > B > C > A is a preference cycle with no winner", () => {
  const items = ["A", "B", "C"];
  const picks = [
    { winner: "A", loser: "B" },
    { winner: "C", loser: "A" },
    { winner: "B", loser: "C" },
  ];
  const r = analyze(items, picks);
  assert.strictEqual(r.transitive, false);
  assert.strictEqual(r.cycles.length, 1);
  assert.deepStrictEqual(r.cycles[0], ["A", "B", "C", "A"]);
  assert.deepStrictEqual(r.condorcet, []);
});

test("golden: a four-item cycle D > A > B > C > D (canonical form)", () => {
  const items = ["A", "B", "C", "D"];
  const picks = [
    { winner: "A", loser: "B" },
    { winner: "A", loser: "C" },
    { winner: "D", loser: "A" },
    { winner: "B", loser: "C" },
    { winner: "B", loser: "D" },
    { winner: "C", loser: "D" },
  ];
  const r = analyze(items, picks);
  assert.strictEqual(r.transitive, false);
  /* Three distinct cycles: D>A>B>C>D, D>A>B>D, D>A>C>D (canonicalized
   * to start at A). The first found is the longest. */
  assert.strictEqual(r.cycles.length, 3);
  assert.deepStrictEqual(r.cycles[0], ["A", "B", "C", "D", "A"]);
  assert.deepStrictEqual(r.condorcet, []);
});

test("golden: one clearly dominant option is the Condorcet winner", () => {
  const items = ["A", "B", "C", "D"];
  const picks = picksFor(matchups(items), "first"); /* A beats everyone */
  const r = analyze(items, picks);
  assert.deepStrictEqual(r.condorcet, ["A"]);
  assert.strictEqual(r.transitive, true);
  assert.deepStrictEqual(r.ranking, ["A", "B", "C", "D"]);
});

test("unanswered matchups are ignored", () => {
  const items = ["A", "B"];
  const r = analyze(items, [null]);
  assert.deepStrictEqual(r.condorcet, []);
  assert.strictEqual(r.transitive, true);
  assert.strictEqual(r.wins.A, 0);
});

test("ranking breaks ties deterministically", () => {
  const items = ["B", "A", "C"];
  /* all matchups answered in favour of the first alphabetically: A beats B and C */
  const picks = [
    { winner: "A", loser: "B" },
    { winner: "A", loser: "C" },
    { winner: "C", loser: "B" },
  ];
  const r = analyze(items, picks);
  assert.deepStrictEqual(r.ranking, ["A", "C", "B"]);
});

test("findCycles is deterministic across runs", () => {
  const items = ["A", "B", "C"];
  const picks = [
    { winner: "A", loser: "B" },
    { winner: "C", loser: "A" },
    { winner: "B", loser: "C" },
  ];
  const r = analyze(items, picks);
  const again = analyze(items, picks);
  assert.deepStrictEqual(r.cycles, again.cycles);
});
