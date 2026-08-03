/* interrogator.test.js — structural findings of the Socratic Interrogator.
 * The engine is deterministic: identical answers produce identical trees
 * and findings, which these tests freeze. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const { buildTree, questionFor, QUESTIONS, MAX_DEPTH } = require("../app/interrogator.js");

const types = (t) => t.findings.map((f) => f.type);

test("a single claim with no answers is flagged unsupported", () => {
  const t = buildTree("Coffee is good for you.", []);
  assert.strictEqual(t.nodes.length, 1);
  assert.deepStrictEqual(types(t), ["unsupported"]);
});

test("golden: a restatement in other words is circular", () => {
  const t = buildTree("The book is trustworthy.", ["Because the book says it is trustworthy."]);
  assert.deepStrictEqual(types(t), ["circular"]);
  assert.match(t.findings[0].message, /circular/);
});

test("golden: a direct contradiction of the claim is flagged", () => {
  const t = buildTree("Coffee is good for you.", ["Coffee is not good for you."]);
  assert.deepStrictEqual(types(t), ["contradiction"]);
});

test("a contradiction at depth three vs the claim is still found", () => {
  const t = buildTree(
    "Coffee is good for you.",
    ["It contains antioxidants.", "Antioxidants prevent cell damage.", "Coffee is not good for you."]
  );
  assert.ok(types(t).includes("contradiction"));
});

test("an 'I don't know' leaf is flagged as an unsupported assumption", () => {
  const t = buildTree("Vaccines cause autism.", [null]);
  assert.deepStrictEqual(types(t), ["unsupported"]);
  assert.strictEqual(t.nodes[1].kind, "unknown");
});

test("a well-supported chain has no structural findings", () => {
  const t = buildTree(
    "The kettle boils at 100°C at sea level.",
    ["Water changes state at 100°C.", "Boiling is a state change.", "Sea-level pressure is the standard."]
  );
  assert.deepStrictEqual(types(t), ["unexamined"]);
});

test("question bank rotates and never repeats across six depths", () => {
  const seen = new Set();
  for (let d = 1; d <= MAX_DEPTH; d++) seen.add(questionFor(d));
  assert.strictEqual(seen.size, MAX_DEPTH);
  assert.strictEqual(QUESTIONS.length, 8);
});

test("depth is capped at MAX_DEPTH regardless of answer count", () => {
  const answers = Array(20).fill("Because I said so.");
  const t = buildTree("Something is true.", answers);
  assert.strictEqual(t.nodes.length, MAX_DEPTH + 1);
});

test("golden: a self-grounding chain 'because it's true because it's true'", () => {
  const t = buildTree("The prophecy is real.", ["Because the prophecy says it is real."]);
  assert.strictEqual(types(t).length, 1);
  assert.strictEqual(types(t)[0], "circular");
});

test("key terms shared innocently do not trigger circularity", () => {
  const t = buildTree("The library is open late.", ["Students need a place to study."]);
  assert.ok(!types(t).includes("circular"));
});

test("null answers anywhere in the chain are preserved", () => {
  const t = buildTree("Ghosts exist.", ["I saw one.", null, "It vanished when I blinked."]);
  assert.strictEqual(t.nodes[2].kind, "unknown");
  assert.ok(types(t).includes("unsupported"));
});
