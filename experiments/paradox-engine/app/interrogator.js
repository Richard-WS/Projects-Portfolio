/* interrogator.js — the Socratic Interrogator: a structural examiner of
 * beliefs.
 *
 * You type a claim; it asks "why", then asks "why" again, building a tree
 * of justifications. It cannot judge whether a belief is true — it judges
 * only its structure, deterministically, with no AI:
 *
 *   circular      — a justification restates an ancestor in new words
 *   contradiction — a justification directly contradicts an ancestor
 *   unsupported   — the chain ends in "I don't know" (an assumption)
 *
 * The engine is pure data in / data out: a claim and a list of answers
 * become a node tree plus structural findings.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else {
    root.ParadoxEngine = root.ParadoxEngine || {};
    root.ParadoxEngine.interrogator = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX_DEPTH = 6;

  /* The interrogator's question bank, rotated by depth. */
  var QUESTIONS = [
    "Why do you believe that?",
    "What makes that true?",
    "How would you know?",
    "What is that based on?",
    "What would change your mind?",
    "Where does that assumption come from?",
    "Can you support that with anything else?",
    "Is that a fact or an assumption?"
  ];

  var STOP = new Set(("the and that this with from have has had will would should could can " +
    "they them their there these those then than just very really because what when where " +
    "which while who whom whose your you are was were been being is its not but for all any " +
    "some more most other such only own same so too also how why he she him her his hers we " +
    "our us it are is").split(" "));

  function keywords(text) {
    return String(text).toLowerCase()
      .replace(/[^a-z0-9'\u2019 ]/g, " ")
      .split(/\s+/)
      .filter(function (w) { return w.length >= 4 && !STOP.has(w); });
  }

  /* Word-level negation test: does this sentence deny something? */
  var NEGATION = /(^|[^a-z])(not|never|no|isn'?t|aren'?t|doesn'?t|don'?t|cannot|can'?t)([^a-z]|$)/i;

  function questionFor(depth) {
    return QUESTIONS[(depth - 1) % QUESTIONS.length];
  }

  /* Build the justification tree from a claim and the answers given.
   * `answers` is a list of strings (a justification) or nulls
   * ("I don't know"). */
  function buildTree(claim, answers) {
    var nodes = [{ depth: 0, question: null, answer: String(claim), kind: "claim" }];
    var n = Math.min(answers.length, MAX_DEPTH);
    for (var d = 0; d < n; d++) {
      var a = answers[d];
      var text = a === null || a === undefined ? null : String(a);
      nodes.push({
        depth: d + 1,
        question: questionFor(d + 1),
        answer: text,
        kind: text === null ? "unknown" : "justification"
      });
    }
    return analyze(nodes);
  }

  /* Structural analysis: circularity, contradiction, unsupported leaves. */
  function analyze(nodes) {
    var findings = [];

    function overlapRatio(kwA, kwB) {
      var smaller = Math.min(kwA.length, kwB.length);
      if (smaller === 0) return 0;
      var common = kwA.filter(function (k) { return kwB.indexOf(k) !== -1; }).length;
      return common / smaller;
    }
    function ancestorLabel(idx) {
      return idx === 0 ? "the original claim" : "the answer at depth " + nodes[idx].depth;
    }

    nodes.forEach(function (node, idx) {
      if (idx === 0 || node.kind !== "justification") return;
      var kw = keywords(node.answer);
      var isNeg = NEGATION.test(node.answer);

      for (var a = 0; a < idx; a++) {
        var anc = nodes[a];
        if (!anc.answer) continue;
        var r = overlapRatio(kw, keywords(anc.answer));
        if (r >= 0.6) {
          if (isNeg !== NEGATION.test(anc.answer)) {
            node.contradicts = node.contradicts || [];
            node.contradicts.push(a);
            findings.push({
              type: "contradiction", index: idx, ref: a,
              message: "Answer at depth " + node.depth + " contradicts " + ancestorLabel(a) + " — one of them has to give."
            });
            return; /* one finding per node is enough for the tree view */
          }
          if (a !== 0 || idx > 0) {
            node.restates = node.restates || [];
            node.restates.push(a);
            findings.push({
              type: "circular", index: idx, ref: a,
              message: "Answer at depth " + node.depth + " restates " + ancestorLabel(a) + " in other words — the reasoning is circular."
            });
            return;
          }
        }
      }
    });

    nodes.forEach(function (node, idx) {
      if (node.kind === "unknown") {
        findings.push({
          type: "unsupported", index: idx,
          message: "The chain ends in an unexamined assumption at depth " + node.depth + "."
        });
      }
    });
    if (nodes.length === 1) {
      findings.push({
        type: "unsupported", index: 0,
        message: "No justification was offered at all — the claim rests on nothing examined."
      });
    }
    if (findings.length === 0) {
      findings.push({
        type: "unexamined", index: nodes.length - 1,
        message: "The chain reaches its depth limit — the deepest answer remains unexamined."
      });
    }

    return { claim: nodes[0].answer, nodes: nodes, findings: findings };
  }

  return {
    MAX_DEPTH: MAX_DEPTH,
    QUESTIONS: QUESTIONS,
    questionFor: questionFor,
    buildTree: buildTree,
    analyze: analyze
  };
}));
