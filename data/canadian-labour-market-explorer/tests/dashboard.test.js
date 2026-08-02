// Tests for dashboard/app.js pure functions, using Node's built-in test runner.
// Run: node --test tests/
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const Core = require("../dashboard/app.js");

// Minimal payload in the exact shape build_dashboard_payload produces.
const fixture = {
  meta: { title: "fixture" },
  regions: [
    {
      code: "CA",
      name: "Canada",
      series: [
        { year: 2000, unemploymentRate: 6.0, employmentThousands: 1000, participationRate: 60, youthUnemploymentRate: 12, primeAgeUnemploymentRate: 5 },
        { year: 2001, unemploymentRate: 6.5, employmentThousands: 1010, participationRate: 60, youthUnemploymentRate: 12, primeAgeUnemploymentRate: 5 },
        { year: 2002, unemploymentRate: 7.0, employmentThousands: 1020, participationRate: 60, youthUnemploymentRate: 12, primeAgeUnemploymentRate: 5 },
      ],
    },
  ],
  decades: [
    { decade: "1970s", nbUnemployment: 10.0, canadaUnemployment: 7.0, gapPp: 3.0 },
    { decade: "2000s", nbUnemployment: 9.0, canadaUnemployment: 6.75, gapPp: 2.25 },
  ],
  highlights: { latestYear: 2002, canadaUnemploymentLatest: 7.0, newBrunswickUnemploymentLatest: 9.0, youthPrimeGapLatest: 7.0 },
};

test("getRegion finds a region and returns null for unknown codes", () => {
  const ca = Core.getRegion(fixture, "CA");
  assert.equal(ca.name, "Canada");
  assert.equal(Core.getRegion(fixture, "ZZ"), null);
});

test("metricValues extracts year/value pairs for a metric", () => {
  const vals = Core.metricValues(fixture.regions[0], "unemploymentRate");
  assert.deepEqual(vals, [
    { year: 2000, value: 6.0 },
    { year: 2001, value: 6.5 },
    { year: 2002, value: 7.0 },
  ]);
});

test("niceTicks produces monotonic ticks covering the range", () => {
  const ticks = Core.niceTicks(0, 10, 6);
  assert.equal(ticks[0], 0);
  assert.ok(ticks[ticks.length - 1] >= 10);
  for (let i = 1; i < ticks.length; i++) assert.ok(ticks[i] > ticks[i - 1]);
  // 1/2/5 stepping: 0..10 in steps of 2
  assert.deepEqual(ticks, [0, 2, 4, 6, 8, 10]);
});

test("niceTicks handles degenerate ranges", () => {
  assert.deepEqual(Core.niceTicks(5, 5, 6), [5]);
  assert.deepEqual(Core.niceTicks(4.2, 4.2, 3), [4.2]);
});

test("formatters produce display strings", () => {
  assert.equal(Core.formatPercent(6.4), "6.4%");
  assert.equal(Core.formatPercent(null), "—");
  assert.equal(Core.formatThousands(1000), "1.00M");
  assert.equal(Core.formatThousands(950), "950k");
  assert.equal(Core.formatMetric("unemploymentRate", 6.4), "6.4%");
  assert.equal(Core.formatMetric("employmentThousands", 19000), "19.00M");
});

test("svgPoint maps data coordinates to pixels monotonically", () => {
  const pad = { top: 18, right: 20, bottom: 42, left: 58 };
  const p1 = Core.svgPoint(2000, 0, 2000, 2002, 0, 10, 860, 420, pad);
  const p2 = Core.svgPoint(2002, 10, 2000, 2002, 0, 10, 860, 420, pad);
  assert.ok(p2.x > p1.x, "x increases with year");
  assert.ok(p2.y < p1.y, "y decreases with value (SVG origin top-left)");
  assert.equal(p1.x, pad.left);
  assert.equal(p2.x, 860 - pad.right);
});

test("decadeHighlight finds a decade row", () => {
  const d = Core.decadeHighlight(fixture, "1970s");
  assert.equal(d.gapPp, 3.0);
  assert.equal(Core.decadeHighlight(fixture, "1990s"), null);
});

test("recessions metadata is well-formed", () => {
  Core.RECESSIONS.forEach((r) => {
    assert.ok(r.start <= r.end);
    assert.ok(typeof r.label === "string" && r.label.length > 0);
  });
});
