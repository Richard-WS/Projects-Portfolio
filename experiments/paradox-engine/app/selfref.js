/* selfref.js — the Self-Reference Lab: a small truth engine for a system
 * of sentences that talk about each other's truth.
 *
 * Sentences are either base facts (assigned true or false by you) or claims
 * of the form "sentence X is true / false / meaningless" — X may be the
 * sentence itself. The engine finds the least fixed point under strong
 * Kleene semantics, then classifies every sentence:
 *
 *   TRUE / FALSE  — forced by the system (grounded)
 *   UNGROUNDED    — consistent either way, nothing forces a value
 *   PARADOX       — no consistent truth assignment exists at all
 *
 * Some claim systems never settle (e.g. "this sentence is meaningless"
 * flips true, false, true, ... forever) — the engine detects the
 * oscillation and reports those sentences as paradoxical. Pure data in,
 * plain data out, so the tests can freeze golden verdicts for the classic
 * paradoxes.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else {
    root.ParadoxEngine = root.ParadoxEngine || {};
    root.ParadoxEngine.selfref = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var T = "T", F = "F", U = "U";

  /* The value of a sentence that asserts `claim` about a target whose
   * current value is `v`, under strong Kleene logic.
   *
   * "X is meaningless" means "X is not true and X is not false" — a
   * conjunction of two negations. In Kleene logic ¬U is U, so the claim
   * about an undefined X is itself undefined (U ∧ U = U). Only a target
   * with a definite value makes "meaningless" evaluate to false. */
  function applyClaim(claim, v) {
    if (claim === "true") return v;
    if (claim === "false") return v === U ? U : (v === T ? F : T);
    return v === U ? U : F; /* "X is meaningless" */
  }

  /* Least fixed point starting from the base facts. Returns
   * { val, oscillates, oscillators }. If the iteration starts cycling
   * (a sentence flipping between values forever), the cycle is measured
   * and the flipping sentences are reported — their values are reset to
   * undefined so they classify as paradoxical. */
  function fixedPoint(sentences) {
    var val = new Map();
    sentences.forEach(function (s) {
      val.set(s.id, s.target === null ? (s.fact ? T : F) : U);
    });

    function sweep() {
      sentences.forEach(function (s) {
        if (s.target === null) return;
        val.set(s.id, applyClaim(s.claim, val.get(s.target)));
      });
    }
    function signature() {
      return sentences.map(function (s) { return val.get(s.id); }).join("\u0001");
    }

    var states = new Map(); /* state signature -> first iteration it appeared */
    /* The state space is 3^n (each sentence T / F / U). Iterating past
     * 3^n + 2 guarantees a repeat is caught by the pigeonhole principle. */
    var maxIter = Math.pow(3, sentences.length) + 2;
    for (var iter = 0; iter < maxIter; iter++) {
      var sig = signature();
      if (states.has(sig)) {
        /* State repeated: the system is cycling. Measure one full cycle
         * to separate sentences that converged from sentences that flip. */
        var cycleLen = iter - states.get(sig);
        var seenVals = new Map();
        sentences.forEach(function (s) { seenVals.set(s.id, new Set()); });
        for (var k = 0; k <= cycleLen; k++) {
          sentences.forEach(function (s) { seenVals.get(s.id).add(val.get(s.id)); });
          sweep();
        }
        var out = { val: new Map(), oscillates: true, oscillators: [] };
        sentences.forEach(function (s) {
          var set = seenVals.get(s.id);
          if (set.size === 1) out.val.set(s.id, set.values().next().value);
          else { out.val.set(s.id, U); out.oscillators.push(s.id); }
        });
        return out;
      }
      states.set(sig, iter);
      var before = signature();
      sweep();
      if (signature() === before) break; /* converged */
    }
    return { val: val, oscillates: false, oscillators: [] };
  }

  /* Every consistent total (T/F) assignment of the system, if any.
   * Exhaustive — the lab is capped at a handful of sentences on purpose. */
  function consistentAssignments(sentences) {
    var n = sentences.length;
    var out = [];
    for (var mask = 0; mask < (1 << n); mask++) {
      var assign = new Map();
      sentences.forEach(function (s, i) {
        assign.set(s.id, (mask >> i) & 1 ? T : F);
      });
      var ok = true;
      for (var i = 0; i < n; i++) {
        var s = sentences[i];
        if (s.target === null) {
          if (assign.get(s.id) !== (s.fact ? T : F)) { ok = false; break; }
          continue;
        }
        var want = applyClaim(s.claim, assign.get(s.target));
        if (want === U || want !== assign.get(s.id)) { ok = false; break; }
      }
      if (ok) out.push(assign);
    }
    return out;
  }

  function anyUndefined(fp, sentences) {
    return sentences.some(function (s) { return fp.get(s.id) === U; });
  }

  /* Full evaluation: fixed point, consistency, system verdict, and a
   * per-sentence verdict. In a paradoxical system every sentence whose
   * value never settles is itself reported as a paradox. */
  function evaluate(sentences) {
    var fpResult = fixedPoint(sentences);
    var fp = fpResult.val;
    var consistent = consistentAssignments(sentences);
    var system = consistent.length === 0 ? "PARADOX"
      : anyUndefined(fp, sentences) ? "UNGROUNDED" : "GROUNDED";

    var verdicts = sentences.map(function (s) {
      if (s.target === null) {
        return { id: s.id, verdict: s.fact ? "TRUE" : "FALSE", grounded: true };
      }
      var v = fp.get(s.id);
      if (v !== U) return { id: s.id, verdict: v === T ? "TRUE" : "FALSE", grounded: true };
      if (system === "PARADOX") return { id: s.id, verdict: "PARADOX", grounded: false };
      return { id: s.id, verdict: "UNGROUNDED", grounded: false };
    });

    return {
      sentences: sentences,
      fixedPoint: Object.fromEntries(fp),
      consistent: consistent.length > 0,
      system: system,
      oscillators: fpResult.oscillators,
      verdicts: verdicts
    };
  }

  return {
    applyClaim: applyClaim,
    fixedPoint: fixedPoint,
    consistentAssignments: consistentAssignments,
    evaluate: evaluate
  };
}));
