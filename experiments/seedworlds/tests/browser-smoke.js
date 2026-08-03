/* browser-smoke.js — boots the viewer with a stubbed DOM (no browser needed).
 * Loads every script exactly like index.html does and exercises boot,
 * generate, tab switching and map drawing. */
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
    id, children: [], style: {}, dataset: {},
    textContent: "", innerHTML: "", value: "", className: "",
    _display: "", title: "", type: "",
    appendChild(c) { node.children.push(c); return c; },
    replaceChildren(...cs) { node.children = cs; },
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
global.location = { hash: "" };
global.history = { replaceState() {} };
Object.defineProperty(global, "navigator", { value: { userAgent: "node-smoke" }, configurable: true });
global.performance = { now: () => Date.now() };
global.requestAnimationFrame = (fn) => { fn(); return 1; };
global.devicePixelRatio = 2;

/* --- Load scripts in index.html order ------------------------------------ */
const order = ["rng.js", "language.js", "land.js", "bestiary.js", "myth.js", "world.js", "app.js"];
for (const f of order) {
  const code = fs.readFileSync(path.join(APP, f), "utf8");
  vm.runInThisContext(code, { filename: f });
}

/* --- Drive the app -------------------------------------------------------- */
const results = [];
function ok(name, cond) { results.push([cond ? "ok" : "FAIL", name]); }

/* The app boots on DOMContentLoaded and auto-generates a world. */
const boot = domListeners["DOMContentLoaded"];
if (typeof boot !== "function") { console.error("boot handler missing"); process.exit(1); }
boot();

$("seed-input").value = "harbour";
const gen = listeners.get("generate-btn:click");
if (typeof gen !== "function") { console.error("generate handler missing"); process.exit(1); }
gen();

const name = $("world-name").textContent;
ok("world name rendered", name.length > 0 && name !== "Grow a world from one word");
ok("world meta rendered", $("world-meta").textContent.includes("grown from"));
ok("land pane populated", $("pane-land").innerHTML.length > 0 || $("pane-land").children.length > 0);

// Tab switching: all four panes must exist and be reachable.
ok("4 panes exist", ["land", "tongue", "bestiary", "telling"].every((t) => elements.has("pane-" + t)));

// Canvas map: pane-land should contain a canvas after renderLand.
const landChildren = $("pane-land").children;
const hasCanvas = landChildren.some((c) => c.children && c.children.some((g) => g.getContext));
ok("canvas drawn", hasCanvas);

let pass = 0, fail = 0;
for (const [s, n] of results) { console.log("  " + s + "  " + n); s === "ok" ? pass++ : fail++; }
console.log("\n" + pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
