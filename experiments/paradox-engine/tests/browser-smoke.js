/* browser-smoke.js — boots the Paradox Engine viewer with a stubbed DOM
 * (no browser needed) and drives all four exhibits end to end: tab
 * routing, interrogation, fallacy scan, self-reference evaluation and
 * the preference tournament. */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const APP = path.join(__dirname, "..", "app");

/* --- Minimal DOM stub ---------------------------------------------------- */
const elements = new Map();
const listeners = new Map();

function makeEl(id) {
  const node = {
    id, tagName: id, children: [], style: {}, dataset: {},
    textContent: "", value: "", className: "", selected: false,
    _display: "", title: "", type: "", _html: "",
    appendChild(c) { node.children.push(c); return c; },
    replaceChildren(...cs) { node.children = cs; },
    focus() {}, blur() {},
    addEventListener(ev, fn) { listeners.set(id + ":" + ev, fn); },
    getContext() {
      return {
        canvas: node,
        fillStyle: "", strokeStyle: "", lineWidth: 1, font: "",
        fillRect() {}, clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {},
        arc() {}, fill() {}, stroke() {}, closePath() {}, setLineDash() {},
        measureText() { return { width: 10 }; },
      };
    },
  };
  Object.defineProperty(node, "display", {
    get() { return node._display; },
    set(v) { node._display = v; },
  });
  /* innerHTML behaves like the browser: assigning "" clears children. */
  Object.defineProperty(node, "innerHTML", {
    get() { return node._html; },
    set(v) { node._html = v; if (v === "") node.children = []; },
  });
  return node;
}

function $(id) {
  if (!elements.has(id)) {
    const n = makeEl(id);
    elements.set(id, n);
    if (id === "tabs") n.appendChild(makeEl("tab-child"));
  }
  return elements.get(id);
}

const domListeners = {};
global.document = {
  getElementById: $,
  createElement(tag) { return makeEl(tag); },
  createTextNode(t) { return { nodeType: 3, text: t }; },
  addEventListener(ev, fn) { domListeners[ev] = fn; },
  querySelector() { return makeEl("qs"); },
};
global.window = global;
global.location = { hash: "", href: "https://example.test/index.html" };
global.history = { replaceState() {} };
Object.defineProperty(global, "navigator", { value: { userAgent: "node-smoke" }, configurable: true });
global.performance = { now: () => Date.now() };
global.requestAnimationFrame = (fn) => { fn(); return 1; };

/* --- Load scripts in index.html order ------------------------------------ */
const order = ["selfref.js", "fallacies.js", "interrogator.js", "preferences.js", "app.js"];
for (const f of order) {
  const code = fs.readFileSync(path.join(APP, f), "utf8");
  vm.runInThisContext(code, { filename: f });
}

/* --- Drive the app -------------------------------------------------------- */
const results = [];
function ok(name, cond) { results.push([cond ? "ok" : "FAIL", name]); }

/* Walk the stub DOM and collect every piece of text (textContent + text
 * nodes), the way innerText would behave in a real browser. */
function allText(node) {
  if (!node) return "";
  if (node.nodeType === 3) return node.text || "";
  let out = node.textContent || "";
  if (node.children) for (const c of node.children) out += allText(c);
  return out;
}
function findChild(node, className) {
  if (!node || !node.children) return null;
  for (const c of node.children) {
    if (c.className === className) return c;
  }
  return null;
}

const boot = domListeners["DOMContentLoaded"];
if (typeof boot !== "function") { console.error("boot handler missing"); process.exit(1); }
boot();

/* Tabs */
ok("default tab is interrogator", !$("pane-interrogator").className.includes("hidden"));
listeners.get("tab-fallacies:click")();
ok("tab switch shows fallacies", $("pane-fallacies").className === "pane" && $("pane-interrogator").className.includes("hidden"));
listeners.get("tab-selfref:click")();
ok("tab switch shows selfref", $("pane-selfref").className === "pane");
listeners.get("tab-preferences:click")();
ok("tab switch shows preferences", $("pane-preferences").className === "pane");
listeners.get("tab-interrogator:click")();
ok("tab switch returns to interrogator", $("pane-interrogator").className === "pane");

/* Socratic Interrogator */
$("int-claim").value = "The book is trustworthy.";
listeners.get("int-begin:click")();
ok("interrogation starts with a question", $("int-question").textContent === "Why do you believe that?");
$("int-answer").value = "Because the book says it is trustworthy.";
listeners.get("int-answer-btn:click")();
ok("second question asked", $("int-question").textContent === "What makes that true?");
$("int-answer").value = "Because the book is trustworthy.";
listeners.get("int-answer-btn:click")();
listeners.get("int-dunno:click")();
const treeText = allText($("int-tree"));
ok("tree rendered", $("int-tree").children.length > 0);
ok("circular reasoning flagged", /circular/i.test(treeText));
ok("unexamined assumption flagged", /assumption/i.test(treeText));

/* Fallacy Foundry */
$("fal-text").value = "Everyone knows that video games cause violence. Either you support a total ban or you're part of the problem.";
listeners.get("fal-scan:click")();
const falText = allText($("fal-results"));
const annotated = findChild($("fal-results"), "annotated");
ok("fallacy scan flags ad populum", /Appeal to popularity/.test(falText));
ok("fallacy scan flags false dilemma", /False dilemma/.test(falText));
ok("annotated text has highlights", annotated !== null && annotated.children.some((c) => c.tagName === "mark"));

/* Self-Reference Lab */
$("sr-row-0-text").value = "This sentence is false.";
$("sr-row-0-type").value = "says-false";
$("sr-row-0-target").value = "self";
listeners.get("sr-eval:click")();
const srText = allText($("sr-result"));
ok("liar evaluates to a paradox", /This universe is a paradox/.test(srText) && /PARADOX/.test(srText));
listeners.get("sr-add:click")();
ok("sentence row can be added", typeof listeners.get("sr-row-1-del:click") === "function");
listeners.get("sr-row-1-del:click")();
ok("sentence row can be removed", $("sr-rows").children.length === 1);
listeners.get("sr-share:click")();
ok("share link encodes state in hash", location.hash.indexOf("selfref/") === 0);

/* Preference Paradox */
$("pf-items").value = "Coffee\nTea\nHot chocolate";
listeners.get("pf-start:click")();
ok("first matchup rendered", $("pf-left").textContent === "Coffee" && $("pf-right").textContent === "Tea");
listeners.get("pf-left:click")();
ok("second matchup rendered", $("pf-left").textContent === "Coffee" && $("pf-right").textContent === "Hot chocolate");
listeners.get("pf-left:click")();
ok("third matchup rendered", $("pf-left").textContent === "Tea" && $("pf-right").textContent === "Hot chocolate");
listeners.get("pf-left:click")();
const pfText = allText($("pf-result"));
ok("preference verdict rendered", /consistent|cycle/i.test(pfText));
ok("Condorcet winner named", /Condorcet winner: Coffee/.test(pfText));

let pass = 0, fail = 0;
for (const [s, n] of results) { console.log("  " + s + "  " + n); s === "ok" ? pass++ : fail++; }
console.log("\n" + pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
