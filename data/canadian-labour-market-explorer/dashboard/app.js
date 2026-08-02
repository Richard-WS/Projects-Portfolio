/* app.js — Canadian Labour Market Explorer dashboard.
 *
 * Pure chart/data functions are exported for node:test (tests/dashboard.test.js);
 * browser rendering runs only when `document` exists. Zero dependencies.
 */
"use strict";

/* ------------------------------------------------------------------ */
/* Pure helpers (unit-testable)                                        */
/* ------------------------------------------------------------------ */

const METRICS = {
  unemploymentRate: { label: "Unemployment rate", unit: "%", color: "#d62728" },
  employmentThousands: { label: "Employment (000s)", unit: "k", color: "#2ca02c" },
  participationRate: { label: "Participation rate", unit: "%", color: "#1f77b4" },
  youthUnemploymentRate: { label: "Youth unemployment (15–24)", unit: "%", color: "#ff7f0e" },
  primeAgeUnemploymentRate: { label: "Prime-age unemployment (25–54)", unit: "%", color: "#9467bd" },
};

const RECESSIONS = [
  { start: 1981, end: 1982, label: "1981–82" },
  { start: 1990, end: 1991, label: "1990–91" },
  { start: 2008, end: 2009, label: "2008–09" },
  { start: 2020, end: 2020, label: "2020" },
];

function getRegion(data, code) {
  return data.regions.find((r) => r.code === code) || null;
}

function metricValues(region, metric) {
  return region.series.map((p) => ({ year: p.year, value: p[metric] }));
}

function niceTicks(min, max, count) {
  // "Nice" tick spacing: 1/2/5 * 10^n steps.
  if (!isFinite(min) || !isFinite(max) || min === max) return [min];
  const span = max - min;
  const step0 = span / Math.max(count - 1, 1);
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) {
    ticks.push(Math.round(v * 1e9) / 1e9);
  }
  return ticks;
}

function formatPercent(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v.toFixed(1)}%`;
}

function formatThousands(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v >= 1000) return `${(v / 1000).toFixed(2)}M`;
  return `${v.toFixed(0)}k`;
}

function formatMetric(metric, v) {
  return metric === "employmentThousands" ? formatThousands(v) : formatPercent(v);
}

/* Map a data point to SVG pixel coordinates (invertible, pure). */
function svgPoint(x, y, xMin, xMax, yMin, yMax, w, h, pad) {
  const sx = pad.left + ((x - xMin) / (xMax - xMin)) * (w - pad.left - pad.right);
  const sy = h - pad.bottom - ((y - yMin) / (yMax - yMin)) * (h - pad.top - pad.bottom);
  return { x: sx, y: sy };
}

function decadeHighlight(data, decadeLabel) {
  return data.decades.find((d) => d.decade === decadeLabel) || null;
}

/* ------------------------------------------------------------------ */
/* Browser rendering                                                   */
/* ------------------------------------------------------------------ */

async function init(dataPath) {
  const resp = await fetch(dataPath);
  const data = await resp.json();
  render(data);
}

function render(data) {
  const regionSelect = document.getElementById("region");
  const metricsWrap = document.getElementById("metrics");
  const tooltip = document.getElementById("tooltip");

  data.regions.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.code;
    opt.textContent = r.name;
    regionSelect.appendChild(opt);
  });

  Object.keys(METRICS).forEach((key) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "metric-btn" + (key === "unemploymentRate" ? " active" : "");
    btn.dataset.metric = key;
    btn.textContent = METRICS[key].label;
    btn.addEventListener("click", () => {
      document.querySelectorAll(".metric-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      drawChart(data, regionSelect.value, key, tooltip);
    });
    metricsWrap.appendChild(btn);
  });

  regionSelect.addEventListener("change", () => {
    drawChart(data, regionSelect.value, activeMetric(), tooltip);
  });

  renderHighlights(data);
  renderDecades(data);
  drawChart(data, regionSelect.value, "unemploymentRate", tooltip);
}

function activeMetric() {
  const active = document.querySelector(".metric-btn.active");
  return active ? active.dataset.metric : "unemploymentRate";
}

function renderHighlights(data) {
  const h = data.highlights;
  const cards = [
    { k: `Canada unemployment, ${h.latestYear}`, v: formatPercent(h.canadaUnemploymentLatest) },
    { k: `New Brunswick unemployment, ${h.latestYear}`, v: formatPercent(h.newBrunswickUnemploymentLatest) },
    { k: `Canada youth−prime gap, ${h.latestYear}`, v: formatPercent(h.youthPrimeGapLatest) },
    { k: "NB−Canada gap now vs 1970s", v: gapStory(data) },
  ];
  document.getElementById("highlights").innerHTML = cards
    .map((c) => `<div class="card"><div class="k">${c.k}</div><div class="v">${c.v}</div></div>`)
    .join("");
}

function gapStory(data) {
  const seventies = decadeHighlight(data, "1970s");
  const latest = data.decades[data.decades.length - 1];
  if (!seventies || !latest) return "—";
  const change = seventies.gapPp - latest.gapPp;
  return `narrowed ${change.toFixed(1)} pp`;
}

function renderDecades(data) {
  const tbody = document.querySelector("#decades tbody");
  tbody.innerHTML = data.decades
    .map(
      (d) =>
        `<tr><td>${d.decade}</td><td>${d.nbUnemployment.toFixed(1)}</td>` +
        `<td>${d.canadaUnemployment.toFixed(1)}</td><td>${d.gapPp.toFixed(2)}</td></tr>`
    )
    .join("");
}

function drawChart(data, regionCode, metric, tooltip) {
  const region = getRegion(data, regionCode);
  if (!region) return;
  const series = metricValues(region, metric);
  const svg = document.getElementById("chart");
  const W = 860, H = 420, pad = { top: 18, right: 20, bottom: 42, left: 58 };
  const years = series.map((p) => p.year);
  const values = series.map((p) => p.value).filter((v) => v !== null && v !== undefined);
  const xMin = Math.min(...years), xMax = Math.max(...years);
  let yMin = Math.min(...values), yMax = Math.max(...values);
  const span = yMax - yMin || 1;
  yMin -= span * 0.08;
  yMax += span * 0.08;

  const meta = METRICS[metric];
  const ns = "http://www.w3.org/2000/svg";
  let out = "";

  // Recession bands
  RECESSIONS.forEach((rec) => {
    const x1 = svgPoint(rec.start, 0, xMin, xMax, yMin, yMax, W, H, pad).x;
    const x2 = svgPoint(rec.end + 1, 0, xMin, xMax, yMin, yMax, W, H, pad).x;
    out += `<rect class="recession-band" x="${x1}" y="${pad.top}" width="${x2 - x1}" height="${H - pad.top - pad.bottom}"></rect>`;
    out += `<text class="recession-label" x="${(x1 + x2) / 2}" y="${pad.top + 12}" text-anchor="middle">${rec.label}</text>`;
  });

  // Y grid + labels
  const yTicks = niceTicks(yMin, yMax, 6);
  yTicks.forEach((t) => {
    const p = svgPoint(xMin, t, xMin, xMax, yMin, yMax, W, H, pad);
    out += `<line class="grid-line" x1="${pad.left}" y1="${p.y}" x2="${W - pad.right}" y2="${p.y}"></line>`;
    out += `<text class="axis-label" x="${pad.left - 8}" y="${p.y + 4}" text-anchor="end">${t}</text>`;
  });

  // X labels every 5 years
  for (let yr = Math.ceil(xMin / 5) * 5; yr <= xMax; yr += 5) {
    const p = svgPoint(yr, 0, xMin, xMax, yMin, yMax, W, H, pad);
    out += `<text class="axis-label" x="${p.x}" y="${H - pad.bottom + 18}" text-anchor="middle">${yr}</text>`;
  }

  // Y axis label
  out += `<text class="axis-label" x="16" y="${(pad.top + H - pad.bottom) / 2}" transform="rotate(-90 16 ${(pad.top + H - pad.bottom) / 2})" text-anchor="middle">${meta.label} (${meta.unit})</text>`;

  // Line + hover points
  const pts = series.map((p) => svgPoint(p.year, p.value, xMin, xMax, yMin, yMax, W, H, pad));
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  out += `<path d="${line}" fill="none" stroke="${meta.color}" stroke-width="2.5" stroke-linejoin="round"></path>`;
  pts.forEach((p, i) => {
    out += `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.5" fill="${meta.color}" data-year="${series[i].year}" data-value="${series[i].value}"></circle>`;
  });

  svg.innerHTML = out;

  // Hover tooltip
  const circles = svg.querySelectorAll("circle");
  const chartWrap = svg.parentElement;
  const show = (circle) => {
    const year = Number(circle.dataset.year);
    const pt = series.find((s) => s.year === year);
    const r = getRegion(data, regionCode);
    const name = r.name;
    const lines = [
      `<b>${name}, ${year}</b>`,
      `${meta.label}: ${formatMetric(metric, pt.value)}`,
      `Unemployment: ${formatPercent(pt.unemploymentRate)}`,
      `Employment: ${formatThousands(pt.employmentThousands)}`,
    ];
    tooltip.innerHTML = lines.join("<br>");
    tooltip.style.display = "block";
    const wrapRect = chartWrap.getBoundingClientRect();
    const cx = circle.getBoundingClientRect().left - wrapRect.left + circle.getBoundingClientRect().width / 2;
    const cy = circle.getBoundingClientRect().top - wrapRect.top;
    tooltip.style.left = `${Math.min(Math.max(cx - 90, 4), wrapRect.width - 190)}px`;
    tooltip.style.top = `${Math.max(cy - 70, 4)}px`;
  };
  circles.forEach((c) => {
    c.addEventListener("mousemove", () => show(c));
    c.addEventListener("mouseleave", () => { tooltip.style.display = "none"; });
  });
}

/* ------------------------------------------------------------------ */
/* Export                                                              */
/* ------------------------------------------------------------------ */

const ExplorerCore = {
  METRICS,
  RECESSIONS,
  getRegion,
  metricValues,
  niceTicks,
  formatPercent,
  formatThousands,
  formatMetric,
  svgPoint,
  decadeHighlight,
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = ExplorerCore;
}
if (typeof window !== "undefined") {
  window.ExplorerCore = ExplorerCore;
  window.LabourExplorerInit = init;
  document.addEventListener("DOMContentLoaded", () => init("../docs/results/data.json"));
}
