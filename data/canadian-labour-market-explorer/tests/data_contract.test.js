// Contract test: the dashboard must boot against the REAL committed
// data.json produced by the R pipeline (docs/results/data.json), not just
// hand-made fixtures. Regression guard for the snake_case/camelCase
// mismatch that crashed the live page (renderDecades reading
// nbUnemployment while R emits nb_unemployment).
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");

const DATA_PATH = path.join(__dirname, "..", "docs", "results", "data.json");

function mkEl() {
  return {
    innerHTML: "",
    value: "NB",
    dataset: {},
    style: {},
    children: [],
    appendChild(c) { this.children.push(c); return c; },
    addEventListener() {},
    classList: { add() {}, remove() {}, contains() { return false; } },
    querySelectorAll() { return []; },
    parentElement: { getBoundingClientRect() { return { left: 0, top: 0, width: 860, height: 420 }; } },
    getBoundingClientRect() { return { left: 0, top: 0, width: 860, height: 420 }; },
  };
}

test("real data.json exists and parses", () => {
  assert.ok(fs.existsSync(DATA_PATH), "docs/results/data.json is committed");
  const data = JSON.parse(fs.readFileSync(DATA_PATH, "utf8"));
  assert.ok(data.regions.length >= 10, "all provinces + Canada");
  assert.ok(data.decades.length >= 5, "decades table populated");
});

test("real data.json matches what app.js reads (snake_case decades, camelCase series)", () => {
  const data = JSON.parse(fs.readFileSync(DATA_PATH, "utf8"));

  // decades rows must expose the keys renderDecades + gapStory read
  const d = data.decades[0];
  for (const k of ["decade", "nb_unemployment", "canada_unemployment", "gap_pp"]) {
    assert.ok(k in d, `decades row missing key ${k}`);
  }
  assert.equal(typeof d.nb_unemployment, "number");
  assert.equal(typeof d.gap_pp, "number");

  // region series must expose the keys metricValues reads
  const s = data.regions[0].series[0];
  for (const k of ["year", "unemploymentRate", "employmentThousands", "participationRate"]) {
    assert.ok(k in s, `series point missing key ${k}`);
  }
  assert.equal(typeof s.unemploymentRate, "number");

  // highlights must expose what renderHighlights reads
  const h = data.highlights;
  for (const k of ["latestYear", "canadaUnemploymentLatest", "newBrunswickUnemploymentLatest", "youthPrimeGapLatest"]) {
    assert.ok(k in h, `highlights missing key ${k}`);
  }
});

test("render() boots without throwing against the real payload", async () => {
  // Build a DOM + fetch stub, load app.js in browser mode, run init.
  const realData = JSON.parse(fs.readFileSync(DATA_PATH, "utf8"));
  const els = {};
  const mk = () => {
    const el = mkEl();
    el.querySelectorAll = () => [];
    return el;
  };
  global.document = {
    getElementById(id) { return (els[id] ||= mk()); },
    createElement() { return mk(); },
    querySelector(sel) { return (els[sel] ||= mk()); },
    querySelectorAll() { return []; },
    addEventListener() {},
  };
  global.fetch = async () => ({ json: async () => realData });
  const w = (global.window = {});
  delete require.cache[require.resolve("../dashboard/app.js")];
  require("../dashboard/app.js");

  await w.LabourExplorerInit("../docs/results/data.json"); // must not throw

  // Decades table actually rendered rows with the real numbers
  const tbodyHtml = els["#decades tbody"]?.innerHTML || "";
  assert.match(tbodyHtml, /1970s/);
  assert.match(tbodyHtml, /2020s/);
  assert.match(tbodyHtml, /4\.15/, "1970s NB–Canada gap in table");
  assert.match(tbodyHtml, /1\.10/, "2020s NB–Canada gap in table");

  // Highlight cards rendered
  const hiHtml = els["highlights"]?.innerHTML || "";
  assert.match(hiHtml, /Canada unemployment, 2025/);

  // Chart SVG has content
  assert.ok((els.chart?.innerHTML || "").length > 1000, "chart SVG rendered");
});
