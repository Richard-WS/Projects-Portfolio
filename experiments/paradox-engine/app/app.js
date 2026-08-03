/* app.js — the Paradox Engine viewer.
 *
 * Boots on DOMContentLoaded, routes tabs through the URL hash, and wires
 * the four exhibits to their engines (selfref.js, fallacies.js,
 * interrogator.js, preferences.js). No dependencies, no network.
 */
(function () {
  "use strict";

  var TAB_NAMES = ["interrogator", "fallacies", "selfref", "preferences"];
  var $ = function (id) { return document.getElementById(id); };

  /* ---------------------------------------------------------------- */
  /* Tabs                                                              */
  /* ---------------------------------------------------------------- */

  function activateTab(name) {
    TAB_NAMES.forEach(function (n) {
      var btn = $("tab-" + n);
      if (btn) btn.className = "tab-btn" + (n === name ? " active" : "");
      var pane = $("pane-" + n);
      if (pane) pane.className = "pane" + (n === name ? "" : " hidden");
    });
    location.hash = name;
  }

  TAB_NAMES.forEach(function (n) {
    var btn = $("tab-" + n);
    btn.addEventListener("click", function () { activateTab(n); });
  });

  /* ---------------------------------------------------------------- */
  /* Socratic Interrogator                                             */
  /* ---------------------------------------------------------------- */

  var intState = { claim: "", answers: [], depth: 0 };

  function intBegin() {
    var claim = $("int-claim").value.trim();
    if (!claim) return;
    intState.claim = claim;
    intState.answers = [];
    intState.depth = 1;
    $("int-flow").className = "box";
    $("int-answer").value = "";
    $("int-tree").innerHTML = "";
    $("int-question").textContent = ParadoxEngine.interrogator.questionFor(1);
    $("int-answer").focus();
  }

  function intNext() {
    if (intState.depth > ParadoxEngine.interrogator.MAX_DEPTH) {
      intFinish();
      return;
    }
    $("int-question").textContent = ParadoxEngine.interrogator.questionFor(intState.depth);
  }

  function intAnswer() {
    var text = $("int-answer").value.trim();
    if (!text) return;
    intState.answers.push(text);
    intState.depth += 1;
    $("int-answer").value = "";
    intNext();
  }

  function intDunno() {
    intState.answers.push(null);
    intFinish();
  }

  function intFinish() {
    var tree = ParadoxEngine.interrogator.buildTree(intState.claim, intState.answers);
    $("int-flow").className = "box hidden";
    renderIntTree(tree);
  }

  function intRestart() {
    intState = { claim: "", answers: [], depth: 0 };
    $("int-flow").className = "box hidden";
    $("int-tree").innerHTML = "";
    $("int-claim").value = "";
  }

  function renderIntTree(tree) {
    var wrap = $("int-tree");
    wrap.innerHTML = "";
    var claim = document.createElement("div");
    claim.className = "claim";
    claim.textContent = "\u201C" + tree.claim + "\u201D";
    wrap.appendChild(claim);

    tree.nodes.slice(1).forEach(function (node) {
      var el = document.createElement("div");
      el.className = "node";
      var q = document.createElement("div");
      q.className = "q";
      q.textContent = node.question;
      el.appendChild(q);
      var a = document.createElement("div");
      if (node.kind === "unknown") {
        a.className = "unknown";
        a.textContent = "(I don't know — an assumption)";
      } else {
        a.className = "a";
        a.textContent = node.answer;
      }
      el.appendChild(a);
      wrap.appendChild(el);
    });

    var findings = document.createElement("div");
    findings.className = "findings";
    tree.findings.forEach(function (f) {
      var el = document.createElement("div");
      el.className = "finding " + f.type;
      el.textContent = f.message;
      findings.appendChild(el);
    });
    wrap.appendChild(findings);
  }

  $("int-begin").addEventListener("click", intBegin);
  $("int-answer-btn").addEventListener("click", intAnswer);
  $("int-dunno").addEventListener("click", intDunno);
  $("int-restart").addEventListener("click", intRestart);
  $("int-answer").addEventListener("keydown", function (e) {
    if (e.key === "Enter") intAnswer();
  });
  $("int-preset-book").addEventListener("click", function () { $("int-claim").value = "The book is trustworthy."; intBegin(); });
  $("int-preset-coffee").addEventListener("click", function () { $("int-claim").value = "Coffee is good for you."; intBegin(); });
  $("int-preset-ghosts").addEventListener("click", function () { $("int-claim").value = "Ghosts exist."; intBegin(); });

  /* ---------------------------------------------------------------- */
  /* Fallacy Foundry                                                   */
  /* ---------------------------------------------------------------- */

  var FAL_EXAMPLE = [
    "Everyone knows that video games cause violence. If we allow violent games, ",
    "next thing you know we'll have no morals at all. Either you support a total ",
    "ban or you're part of the problem. Of course the game companies would say ",
    "otherwise — they're just greedy. Studies show games are dangerous, and ",
    "anyone who disagrees is probably a gamer. It's outrageous that we even ",
    "debate this."
  ].join("");

  function falScan() {
    var text = $("fal-text").value;
    var hits = ParadoxEngine.fallacies.scan(text);
    renderFalResults(text, hits);
  }

  function renderFalResults(text, hits) {
    var wrap = $("fal-results");
    wrap.innerHTML = "";
    if (!text.trim()) return;

    var annotated = document.createElement("div");
    annotated.className = "annotated";
    var cursor = 0;
    hits.forEach(function (h) {
      if (h.index > cursor) annotated.appendChild(document.createTextNode(text.slice(cursor, h.index)));
      var mark = document.createElement("mark");
      mark.textContent = text.slice(h.index, h.index + h.length);
      annotated.appendChild(mark);
      cursor = h.index + h.length;
    });
    if (cursor < text.length) annotated.appendChild(document.createTextNode(text.slice(cursor)));
    wrap.appendChild(annotated);

    if (hits.length === 0) {
      var none = document.createElement("p");
      none.className = "muted";
      none.textContent = "No known fallacy shapes found. Either the argument is clean — or the fallacies are hiding in unfamiliar phrasing.";
      wrap.appendChild(none);
      return;
    }

    var list = document.createElement("div");
    list.className = "findings";
    var seen = new Set();
    hits.forEach(function (h) {
      var key = h.id + ":" + h.index + ":" + h.length;
      if (seen.has(key)) return;
      seen.add(key);
      var el = document.createElement("div");
      el.className = "fal-hit";
      var name = document.createElement("b");
      name.textContent = h.name;
      el.appendChild(name);
      var phrase = document.createElement("div");
      phrase.className = "phrase";
      phrase.textContent = "\u201C" + h.phrase + "\u201D";
      el.appendChild(phrase);
      var note = document.createElement("div");
      note.className = "note";
      note.textContent = h.note;
      el.appendChild(note);
      list.appendChild(el);
    });
    wrap.appendChild(list);
  }

  $("fal-scan").addEventListener("click", falScan);
  $("fal-example").addEventListener("click", function () {
    $("fal-text").value = FAL_EXAMPLE;
    falScan();
  });

  /* ---------------------------------------------------------------- */
  /* Self-Reference Lab                                                */
  /* ---------------------------------------------------------------- */

  var TYPES = [
    ["fact-true", "Fact: true"],
    ["fact-false", "Fact: false"],
    ["says-true", "\u201CX is true\u201D"],
    ["says-false", "\u201CX is false\u201D"],
    ["says-meaningless", "\u201CX is meaningless\u201D"]
  ];

  var PRESETS = {
    liar: {
      label: "The liar",
      sentences: [{ text: "This sentence is false.", type: "says-false", target: "self" }]
    },
    strengthened: {
      label: "The strengthened liar",
      sentences: [{ text: "This sentence is not true.", type: "says-false", target: "self" }]
    },
    truthteller: {
      label: "The truth-teller",
      sentences: [{ text: "This sentence is true.", type: "says-true", target: "self" }]
    },
    meaningless: {
      label: "The meaningless one",
      sentences: [{ text: "This sentence is meaningless.", type: "says-meaningless", target: "self" }]
    },
    mutual: {
      label: "Mutual admiration",
      sentences: [
        { text: "Sentence B is true.", type: "says-true", target: "B" },
        { text: "Sentence A is true.", type: "says-true", target: "A" }
      ]
    },
    chain: {
      label: "A grounded chain",
      sentences: [
        { text: "Sentence B is true.", type: "says-true", target: "B" },
        { text: "Sentence C is true.", type: "says-true", target: "C" },
        { text: "The sky is blue.", type: "fact-true", target: "self" }
      ]
    }
  };

  var srModel = PRESETS.liar.sentences.map(function (s) { return { text: s.text, type: s.type, target: s.target }; });

  var LETTERS = "ABCDEF";

  function srRenderRows() {
    var rows = $("sr-rows");
    rows.innerHTML = "";
    srModel.forEach(function (s, i) {
      var row = document.createElement("div");
      row.className = "sr-row";

      var text = document.createElement("input");
      text.id = "sr-row-" + i + "-text";
      text.value = s.text;
      row.appendChild(text);

      var typeSel = document.createElement("select");
      typeSel.id = "sr-row-" + i + "-type";
      TYPES.forEach(function (t) {
        var opt = document.createElement("option");
        opt.value = t[0];
        opt.textContent = t[1];
        if (t[0] === s.type) opt.selected = true;
        typeSel.appendChild(opt);
      });
      row.appendChild(typeSel);

      var targetSel = document.createElement("select");
      targetSel.id = "sr-row-" + i + "-target";
      var options = [{ v: "self", l: "itself" }].concat(
        LETTERS.slice(0, srModel.length).split("").filter(function (L) { return L !== LETTERS[i]; })
          .map(function (L) { return { v: L, l: "sentence " + L }; })
      );
      options.forEach(function (o) {
        var opt = document.createElement("option");
        opt.value = o.v;
        opt.textContent = o.l;
        if (o.v === s.target) opt.selected = true;
        targetSel.appendChild(opt);
      });
      row.appendChild(targetSel);

      var del = document.createElement("button");
      del.id = "sr-row-" + i + "-del";
      del.className = "del";
      del.textContent = "\u00D7";
      row.appendChild(del);
      document.getElementById(del.id).addEventListener("click", function () {
        srModel.splice(i, 1);
        srRenderRows();
      });

      rows.appendChild(row);
    });
  }

  function srAdd() {
    if (srModel.length >= LETTERS.length) return;
    srModel.push({ text: "Sentence " + LETTERS[srModel.length] + " is true.", type: "says-true", target: "self" });
    srRenderRows();
  }

  function srCollect() {
    return srModel.map(function (s, i) {
      var id = LETTERS[i];
      var type = $("sr-row-" + i + "-type").value;
      var target = $("sr-row-" + i + "-target").value;
      target = target === "self" ? id : target;
      var text = $("sr-row-" + i + "-text").value || ("Sentence " + id);
      var eng = { id: id, text: text };
      if (type === "fact-true") { eng.target = null; eng.fact = true; }
      else if (type === "fact-false") { eng.target = null; eng.fact = false; }
      else {
        eng.target = target;
        eng.claim = type === "says-true" ? "true" : type === "says-false" ? "false" : "meaningless";
      }
      return eng;
    });
  }

  function srEvaluate() {
    var sentences = srCollect();
    var r = ParadoxEngine.selfref.evaluate(sentences);
    renderSrResult(r);
  }

  function renderSrResult(r) {
    var wrap = $("sr-result");
    wrap.innerHTML = "";

    var banner = document.createElement("div");
    banner.className = "system " + r.system;
    var label = {
      GROUNDED: "This universe is consistent and fully decided.",
      UNGROUNDED: "This universe is consistent, but some sentences can never be pinned down.",
      PARADOX: "This universe is a paradox — no consistent assignment of truth exists."
    }[r.system];
    banner.textContent = label;
    wrap.appendChild(banner);

    var table = document.createElement("table");
    table.className = "h2h";
    r.verdicts.forEach(function (v) {
      var tr = document.createElement("tr");
      var idCell = document.createElement("th");
      idCell.textContent = v.id;
      tr.appendChild(idCell);
      var textCell = document.createElement("td");
      textCell.textContent = sentencesToText(r, v.id);
      tr.appendChild(textCell);
      var badgeCell = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "verdict " + v.verdict;
      badge.textContent = v.verdict;
      badgeCell.appendChild(badge);
      tr.appendChild(badgeCell);
      table.appendChild(tr);
    });
    wrap.appendChild(table);

    if (r.oscillators && r.oscillators.length) {
      var osc = document.createElement("p");
      osc.className = "muted";
      osc.textContent = "These sentences never settle: " + r.oscillators.join(", ") + ".";
      wrap.appendChild(osc);
    }
  }

  function sentencesToText(r, id) {
    var s = r.sentences.filter(function (x) { return x.id === id; })[0];
    return s ? s.text : id;
  }

  function srShare() {
    var payload = srModel.map(function (s) {
      return [encodeURIComponent(s.text), s.type, s.target].join("|");
    }).join("~");
    location.hash = "selfref/" + payload;
    var msg = "Share link: " + location.href;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(location.href).catch(function () {});
    } else {
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = msg;
      $("sr-result").appendChild(p);
    }
  }

  function srLoadPreset(key) {
    var p = PRESETS[key];
    if (!p) return;
    srModel = p.sentences.map(function (s) { return { text: s.text, type: s.type, target: s.target }; });
    srRenderRows();
    srEvaluate();
  }

  $("sr-add").addEventListener("click", srAdd);
  $("sr-eval").addEventListener("click", srEvaluate);
  $("sr-share").addEventListener("click", srShare);
  $("sr-presets").addEventListener("click", function () {
    var list = $("sr-preset-list");
    if (list.innerHTML !== "") { list.innerHTML = ""; return; }
    Object.keys(PRESETS).forEach(function (key) {
      var b = document.createElement("button");
      b.textContent = PRESETS[key].label;
      b.addEventListener("click", function () { srLoadPreset(key); });
      list.appendChild(b);
    });
  });

  /* ---------------------------------------------------------------- */
  /* Preference Paradox                                                */
  /* ---------------------------------------------------------------- */

  var pfState = { items: [], pairs: [], picks: [], idx: 0 };

  function pfStart() {
    var items = $("pf-items").value.split("\n").map(function (s) { return s.trim(); }).filter(Boolean);
    if (items.length < 3 || items.length > 6) {
      $("pf-progress").textContent = "Give me 3 to 6 things to rank.";
      $("pf-progress").className = "muted";
      return;
    }
    pfState.items = items;
    pfState.pairs = ParadoxEngine.preferences.matchups(items);
    pfState.picks = new Array(pfState.pairs.length).fill(null);
    pfState.idx = 0;
    $("pf-setup").className = "box hidden";
    $("pf-matchup").className = "box";
    $("pf-result").innerHTML = "";
    pfRenderMatchup();
  }

  function pfRenderMatchup() {
    var pair = pfState.pairs[pfState.idx];
    $("pf-left").textContent = pair[0];
    $("pf-right").textContent = pair[1];
    $("pf-progress").textContent = "Matchup " + (pfState.idx + 1) + " of " + pfState.pairs.length;
  }

  function pfPick(winner) {
    var pair = pfState.pairs[pfState.idx];
    var loser = pair[0] === winner ? pair[1] : pair[0];
    pfState.picks[pfState.idx] = { winner: winner, loser: loser };
    pfState.idx += 1;
    if (pfState.idx >= pfState.pairs.length) pfFinish();
    else pfRenderMatchup();
  }

  function pfFinish() {
    $("pf-matchup").className = "box hidden";
    var r = ParadoxEngine.preferences.analyze(pfState.items, pfState.picks);
    renderPfResult(r);
  }

  function renderPfResult(r) {
    var wrap = $("pf-result");
    wrap.innerHTML = "";

    var banner = document.createElement("div");
    if (r.transitive) {
      banner.className = "system GROUNDED";
      banner.textContent = "Your preferences are consistent — no cycles found.";
    } else {
      banner.className = "system PARADOX";
      banner.textContent = "Your preferences contradict themselves. Congratulations, you are human.";
    }
    wrap.appendChild(banner);

    var h2h = document.createElement("table");
    h2h.className = "h2h";
    var head = document.createElement("tr");
    var corner = document.createElement("th");
    corner.textContent = "beats?";
    head.appendChild(corner);
    r.items.forEach(function (it) {
      var th = document.createElement("th");
      th.textContent = it;
      head.appendChild(th);
    });
    h2h.appendChild(head);
    r.items.forEach(function (row) {
      var tr = document.createElement("tr");
      var label = document.createElement("th");
      label.textContent = row;
      tr.appendChild(label);
      r.items.forEach(function (col) {
        var td = document.createElement("td");
        var v = r.h2h[row][col];
        td.textContent = v === "win" ? "\u2713" : v === "loss" ? "\u2717" : v === "-" ? "\u2013" : "\u00B7";
        if (v === "win") td.className = "good";
        if (v === "loss") td.style.color = "#ff7b72";
        tr.appendChild(td);
      });
      h2h.appendChild(tr);
    });
    wrap.appendChild(h2h);

    if (r.condorcet.length) {
      var c = document.createElement("p");
      c.className = "good";
      c.textContent = "Condorcet winner: " + r.condorcet.join(", ") + " — beats every other option head-to-head.";
      wrap.appendChild(c);
    } else {
      var nc = document.createElement("p");
      nc.className = "muted";
      nc.textContent = "No Condorcet winner — no single option beats all the others.";
      wrap.appendChild(nc);
    }

    r.cycles.forEach(function (cycle) {
      var p = document.createElement("p");
      p.className = "cycle";
      p.textContent = "Preference cycle: " + cycle.join(" > ") + ".";
      wrap.appendChild(p);
    });

    var rank = document.createElement("p");
    rank.className = "muted";
    rank.textContent = "Pairwise ranking: " + r.ranking.join(" > ") + " (win/loss tally, ties alphabetical).";
    wrap.appendChild(rank);
  }

  $("pf-start").addEventListener("click", pfStart);
  $("pf-left").addEventListener("click", function () { pfPick($("pf-left").textContent); });
  $("pf-right").addEventListener("click", function () { pfPick($("pf-right").textContent); });

  /* ---------------------------------------------------------------- */
  /* Boot                                                              */
  /* ---------------------------------------------------------------- */

  function boot() {
    srRenderRows();
    srEvaluate();

    var h = location.hash.replace(/^#/, "");
    if (h.indexOf("selfref/") === 0) {
      var payload = h.slice("selfref/".length);
      var parts = payload.split("~").map(function (chunk) {
        var f = chunk.split("|");
        return { text: decodeURIComponent(f[0]), type: f[1], target: f[2] };
      });
      if (parts.length && parts[0].type) {
        srModel = parts;
        srRenderRows();
        srEvaluate();
      }
      activateTab("selfref");
    } else if (TAB_NAMES.indexOf(h) !== -1) {
      activateTab(h);
    }
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
