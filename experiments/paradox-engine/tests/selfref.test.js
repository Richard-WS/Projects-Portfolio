/* selfref.test.js — golden verdicts for the Self-Reference Lab truth
 * engine. Every case below is a known result of Kripke-style semantics;
 * if the engine stops agreeing with them, the tests break loudly. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const { evaluate, applyClaim } = require("../app/selfref.js");

/* Sentence builders: base facts and claims. */
function base(id, text, fact) { return { id, text, target: null, fact }; }
function claim(id, target, value) { return { id, text: "", target, claim: value }; }

const verdicts = (r) => Object.fromEntries(r.verdicts.map((v) => [v.id, v.verdict]));

test("applyClaim: strong Kleene truth tables", () => {
  assert.strictEqual(applyClaim("true", "T"), "T");
  assert.strictEqual(applyClaim("true", "F"), "F");
  assert.strictEqual(applyClaim("true", "U"), "U");
  assert.strictEqual(applyClaim("false", "T"), "F");
  assert.strictEqual(applyClaim("false", "F"), "T");
  assert.strictEqual(applyClaim("false", "U"), "U");
  assert.strictEqual(applyClaim("meaningless", "U"), "U");
  assert.strictEqual(applyClaim("meaningless", "T"), "F");
  assert.strictEqual(applyClaim("meaningless", "F"), "F");
});

test("golden: the liar — 'this sentence is false' is a paradox", () => {
  const r = evaluate([claim("A", "A", "false")]);
  assert.strictEqual(r.system, "PARADOX");
  assert.strictEqual(verdicts(r).A, "PARADOX");
});

test("golden: the truth-teller — 'this sentence is true' is ungrounded", () => {
  const r = evaluate([claim("A", "A", "true")]);
  assert.strictEqual(r.system, "UNGROUNDED");
  assert.strictEqual(verdicts(r).A, "UNGROUNDED");
  assert.strictEqual(r.consistent, true);
});

test("golden: 'this sentence is meaningless' is ungrounded, not a paradox", () => {
  /* Under strong Kleene semantics "X is meaningless" = "not true and not
   * false", so the self-claim never forces a value — the sentence stays
   * undefined yet consistent (it could simply be false). */
  const r = evaluate([claim("A", "A", "meaningless")]);
  assert.strictEqual(r.system, "UNGROUNDED");
  assert.strictEqual(verdicts(r).A, "UNGROUNDED");
  assert.strictEqual(r.consistent, true);
  assert.deepStrictEqual(r.oscillators, []);
});

test("golden: a claim about a base fact is grounded", () => {
  const sky = base("B", "the sky is blue", true);
  const r = evaluate([claim("A", "B", "true"), sky]);
  assert.strictEqual(r.system, "GROUNDED");
  assert.strictEqual(verdicts(r).A, "TRUE");
  assert.strictEqual(verdicts(r).B, "TRUE");
});

test("golden: a false claim about a true base fact is grounded false", () => {
  const r = evaluate([claim("A", "B", "false"), base("B", "the sky is blue", true)]);
  assert.strictEqual(verdicts(r).A, "FALSE");
  assert.strictEqual(r.system, "GROUNDED");
});

test("golden: a claim about a false base fact is grounded false", () => {
  const r = evaluate([claim("A", "B", "true"), base("B", "the earth is flat", false)]);
  assert.strictEqual(verdicts(r).A, "FALSE");
});

test("golden: the two-sentence truth-teller is ungrounded", () => {
  const r = evaluate([claim("A", "B", "true"), claim("B", "A", "true")]);
  assert.strictEqual(r.system, "UNGROUNDED");
  assert.strictEqual(verdicts(r).A, "UNGROUNDED");
  assert.strictEqual(verdicts(r).B, "UNGROUNDED");
});

test("golden: A says B false, B says A true — paradox via proxy", () => {
  const r = evaluate([claim("A", "B", "false"), claim("B", "A", "true")]);
  assert.strictEqual(r.system, "PARADOX");
  assert.strictEqual(verdicts(r).A, "PARADOX");
  assert.strictEqual(verdicts(r).B, "PARADOX");
});

test("golden: a three-link chain to a true fact grounds everything", () => {
  const r = evaluate([
    claim("A", "B", "true"),
    claim("B", "C", "true"),
    base("C", "snow is white", true),
  ]);
  assert.strictEqual(r.system, "GROUNDED");
  assert.strictEqual(verdicts(r).A, "TRUE");
  assert.strictEqual(verdicts(r).B, "TRUE");
  assert.strictEqual(verdicts(r).C, "TRUE");
});

test("golden: 'A is meaningless' about a true base fact is grounded false", () => {
  const r = evaluate([claim("A", "B", "meaningless"), base("B", "snow is white", true)]);
  assert.strictEqual(verdicts(r).A, "FALSE");
  assert.strictEqual(r.system, "GROUNDED");
});

test("golden: a base fact alone is grounded and consistent", () => {
  const r = evaluate([base("A", "the earth orbits the sun", true)]);
  assert.strictEqual(r.system, "GROUNDED");
  assert.strictEqual(verdicts(r).A, "TRUE");
});

test("two base facts coexist — the engine has no semantics beyond claims", () => {
  const r = evaluate([
    base("A", "the earth is flat", true),
    base("B", "the earth is round", true),
  ]);
  assert.strictEqual(r.system, "GROUNDED");
  assert.strictEqual(verdicts(r).A, "TRUE");
  assert.strictEqual(verdicts(r).B, "TRUE");
});
