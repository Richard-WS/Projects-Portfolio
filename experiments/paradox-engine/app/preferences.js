/* preferences.js — the Preference Paradox Lab: a tournament of your own
 * tastes.
 *
 * Rank a handful of things head-to-head (this or that, this or that...) and
 * the lab builds your preference graph. It then reports what the graph
 * proves about you:
 *
 *   Condorcet winner — an option that beats every other head-to-head
 *   cycles           — A > B > C > A: your tastes contradict themselves
 *   pairwise scores  — a simple win/loss tally (Copeland count)
 *
 * Pure data in, plain data out, fully deterministic for testing.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else {
    root.ParadoxEngine = root.ParadoxEngine || {};
    root.ParadoxEngine.preferences = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Every pairwise matchup in a round-robin: [a, b] with a < b by index. */
  function matchups(items) {
    var pairs = [];
    for (var i = 0; i < items.length; i++) {
      for (var j = i + 1; j < items.length; j++) {
        pairs.push([items[i], items[j]]);
      }
    }
    return pairs;
  }

  /* Analyze a completed tournament.
   * `picks` aligns with matchups(): each entry is { winner, loser } or null
   * (unanswered). Returns the head-to-head table, Condorcet winner(s),
   * preference cycles and a transitive verdict. */
  function analyze(items, picks) {
    var pairs = matchups(items);
    var wins = {};
    var losses = {};
    items.forEach(function (i) { wins[i] = 0; losses[i] = 0; });

    /* head-to-head table: h2h[a][b] is "win" | "loss" | "-" | null */
    var h2h = {};
    items.forEach(function (i) {
      h2h[i] = {};
      items.forEach(function (j) { h2h[i][j] = i === j ? "-" : null; });
    });

    pairs.forEach(function (p, k) {
      var pick = picks[k];
      if (!pick) return;
      wins[pick.winner] = wins[pick.winner] + 1;
      losses[pick.loser] = losses[pick.loser] + 1;
      h2h[pick.winner][pick.loser] = "win";
      h2h[pick.loser][pick.winner] = "loss";
    });

    var condorcet = items.filter(function (i) {
      return items.every(function (j) { return i === j || h2h[i][j] === "win"; });
    });

    var cycles = findCycles(items, h2h);
    var transitive = cycles.length === 0;

    /* Pairwise (Copeland) ranking: wins minus losses, ties broken
     * alphabetically for determinism. */
    var ranking = items.slice().sort(function (a, b) {
      var d = (wins[b] - losses[b]) - (wins[a] - losses[a]);
      return d !== 0 ? d : (a < b ? -1 : a > b ? 1 : 0);
    });

    return {
      items: items.slice(),
      pairs: pairs,
      wins: wins,
      losses: losses,
      h2h: h2h,
      condorcet: condorcet,
      cycles: cycles,
      transitive: transitive,
      ranking: ranking
    };
  }

  /* Enumerate simple directed cycles of length >= 3 in the preference
   * graph (a beats b means an edge a -> b). Deterministic: starts from
   * sorted items and visits neighbours in sorted order; caps at three
   * cycles for the exhibit. */
  function findCycles(items, h2h) {
    var out = [];
    var sorted = items.slice().sort();
    var n = sorted.length;
    var seen = new Set();

    /* Rotate a cycle so its smallest element comes first, then join —
     * this makes [A,B,C,A] and [B,C,A,B] the same key. */
    function canonicalKey(cycle) {
      var body = cycle.slice(0, -1);
      var minIdx = 0;
      for (var i = 1; i < body.length; i++) {
        if (body[i] < body[minIdx]) minIdx = i;
      }
      return body.slice(minIdx).concat(body.slice(0, minIdx)).join("\u0001");
    }

    function dfs(start, path, visited) {
      if (out.length >= 3) return;
      var last = path[path.length - 1];
      var neighbors = sorted.filter(function (x) {
        return h2h[last][x] === "win" && (x === start || !visited[x]);
      });
      neighbors.forEach(function (x) {
        if (x === start) {
          if (path.length >= 2) {
            var cycle = path.concat(x);
            var key = canonicalKey(cycle);
            if (!seen.has(key)) {
              seen.add(key);
              out.push(cycle);
            }
          }
          return;
        }
        visited[x] = true;
        dfs(start, path.concat(x), visited);
        visited[x] = false;
      });
    }

    for (var i = 0; i < n; i++) {
      var s = sorted[i];
      dfs(s, [s], Object.assign({}, { [s]: true }));
      if (out.length >= 3) break;
    }
    return out;
  }

  return {
    matchups: matchups,
    analyze: analyze,
    findCycles: findCycles
  };
}));
