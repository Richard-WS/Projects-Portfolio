/* app.js — Seedworlds viewer.
 *
 * Browser-only rendering for the world modules. All generation lives in the
 * other files (pure, node-testable); this file only draws. Zero dependencies.
 * Touch and mouse are handled through pointer events so it works on a phone
 * or a laptop.
 */
(function () {
  "use strict";

  const worldMod = window.Seedworlds.world;

  /* ---------------------------------------------------------------- */
  /* Small DOM helpers                                                 */
  /* ---------------------------------------------------------------- */

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  const $ = (id) => document.getElementById(id);

  /* ---------------------------------------------------------------- */
  /* State                                                             */
  /* ---------------------------------------------------------------- */

  let state = {
    world: null,
    mapMode: "biomes",
    selectedRegion: null,
    tab: "land",
  };

  /* ---------------------------------------------------------------- */
  /* Seed input                                                        */
  /* ---------------------------------------------------------------- */

  const SAMPLE_SEEDS = ["meadow", "harbour", "ember", "ocean", "mirage", "lantern", "keystone", "tundra", "saltmarsh", "avalanche"];

  function readSeedFromHash() {
    const m = /(?:^|[#&])seed=([^&]+)/.exec(location.hash);
    if (m) {
      try { return decodeURIComponent(m[1]); } catch (e) { /* fall through */ }
    }
    return null;
  }

  function writeSeedToHash(seed) {
    try {
      history.replaceState(null, "", "#seed=" + encodeURIComponent(seed));
    } catch (e) { /* file:// may refuse; ignore */ }
  }

  function generate() {
    const seed = $("seed-input").value.trim() || "meadow";
    const t0 = performance.now();
    let world;
    try {
      world = worldMod.generateWorld(seed);
    } catch (e) {
      $("world-name").textContent = "That seed failed to grow";
      console.error(e);
      return;
    }
    state.world = world;
    state.selectedRegion = null;
    $("seed-input").value = seed;
    writeSeedToHash(seed);
    const ms = Math.max(1, Math.round(performance.now() - t0));
    $("world-name").textContent = world.name;
    $("world-meta").textContent =
      "grown from “" + seed + "” in " + ms + " ms · " +
      world.language.words.length + " words · " +
      world.land.regions.length + " named places · " +
      world.bestiary.length + " creatures";
    renderTab();
  }

  function randomSeed() {
    const base = SAMPLE_SEEDS[Math.floor(Math.random() * SAMPLE_SEEDS.length)];
    const suffix = Math.random().toString(36).slice(2, 6);
    $("seed-input").value = base + suffix;
    generate();
  }

  /* ---------------------------------------------------------------- */
  /* Tabs                                                              */
  /* ---------------------------------------------------------------- */

  const TABS = ["land", "tongue", "bestiary", "telling"];

  function setTab(tab) {
    state.tab = tab;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    renderTab();
  }

  function renderTab() {
    const w = state.world;
    if (!w) return;
    TABS.forEach((t) => {
      $("pane-" + t).style.display = t === state.tab ? "" : "none";
    });
    const panes = {
      land: () => renderLand(w),
      tongue: () => renderTongue(w),
      bestiary: () => renderBestiary(w),
      telling: () => renderTelling(w),
    };
    panes[state.tab]();
  }

  /* ---------------------------------------------------------------- */
  /* Land tab                                                          */
  /* ---------------------------------------------------------------- */

  const BIOME_COLORS = {
    ocean: "#1b4d7a",
    coast: "#9ec3d8",
    plains: "#a7c25e",
    steppe: "#c9b458",
    forest: "#2f7a3e",
    jungle: "#1d5c2e",
    desert: "#e0c36a",
    tundra: "#93a9a2",
    snow: "#eef4f8",
    mountain: "#8d8d8d",
  };

  function renderLand(w) {
    const host = $("pane-land");
    host.replaceChildren();
    const L = w.land;
    const canvas = el("canvas");
    canvas.className = "map-canvas";
    canvas.width = L.width * 8;
    canvas.height = L.height * 8;
    host.appendChild(canvas);
    host.appendChild(el("p", "map-hint", "Tap a named place to read its name · toggle the view below"));

    const toggles = el("div", "map-toggles");
    [["biomes", "Biomes"], ["elevation", "Elevation"], ["moisture", "Moisture"]].forEach(([mode, label]) => {
      const b = el("button", "map-toggle" + (state.mapMode === mode ? " active" : ""), label);
      b.type = "button";
      b.addEventListener("click", () => {
        state.mapMode = mode;
        toggles.querySelectorAll(".map-toggle").forEach((x) => x.classList.toggle("active", x === b));
        drawMap();
      });
      toggles.appendChild(b);
    });
    host.appendChild(toggles);

    const legend = el("div", "legend");
    Object.entries(BIOME_COLORS).forEach(([k, c]) => {
      const item = el("span", "legend-item");
      const sw = el("span", "swatch");
      sw.style.background = c;
      item.appendChild(sw);
      item.appendChild(document.createTextNode(L.biomeLabels[k]));
      legend.appendChild(item);
    });
    host.appendChild(legend);

    const info = el("div", "region-info");
    info.id = "region-info";
    host.appendChild(info);

    const ctx = canvas.getContext("2d");
    state._canvas = canvas;
    state._ctx = ctx;
    drawMap();

    /* Pointer hit-testing: find the region under a tap/click. */
    function pickRegion(e) {
      const rect = canvas.getBoundingClientRect();
      const x = Math.floor(((e.clientX - rect.left) / rect.width) * L.width);
      const y = Math.floor(((e.clientY - rect.top) / rect.height) * L.height);
      if (x < 0 || y < 0 || x >= L.width || y >= L.height) return null;
      const idx = y * L.width + x;
      /* Exact region membership: search regions for containment. */
      for (const r of L.regions) {
        if (r.seedCell === idx) return r;
      }
      /* Fallback: nearest named region by seed cell. */
      let best = null;
      let bestD = Infinity;
      const sx = idx % L.width;
      const sy = (idx - sx) / L.width;
      for (const r of L.regions) {
        const rx = r.seedCell % L.width;
        const ry = (r.seedCell - rx) / L.width;
        const d = (rx - sx) * (rx - sx) + (ry - sy) * (ry - sy);
        if (d < bestD) { bestD = d; best = r; }
      }
      return best;
    }

    canvas.addEventListener("pointerdown", (e) => {
      const r = pickRegion(e);
      state.selectedRegion = r;
      showRegionInfo(r);
      drawMap();
    });
  }

  function drawMap() {
    const w = state.world;
    const L = w.land;
    const ctx = state._ctx;
    const mode = state.mapMode;

    const px = L.width * 8;
    const py = L.height * 8;
    ctx.clearRect(0, 0, px, py);

    /* Elevation and moisture are grey gradients; biomes are coloured. */
    let colorFor;
    if (mode === "elevation") {
      colorFor = (i) => {
        const v = L.elevation[i];
        const g = Math.round(40 + v * 200);
        return "rgb(" + g + "," + g + "," + Math.min(255, g + 20) + ")";
      };
    } else if (mode === "moisture") {
      colorFor = (i) => {
        const v = L.moisture[i];
        return "rgb(" + Math.round(220 - v * 160) + "," + Math.round(235 - v * 100) + "," + Math.round(200 + v * 40) + ")";
      };
    } else {
      colorFor = (i) => BIOME_COLORS[L.biome[i]] || "#ccc";
    }

    for (let y = 0; y < L.height; y++) {
      for (let x = 0; x < L.width; x++) {
        const i = y * L.width + x;
        ctx.fillStyle = colorFor(i);
        ctx.fillRect(x * 8, y * 8, 8, 8);
      }
    }

    /* Rivers: a bright line over the map. */
    ctx.strokeStyle = "#45c8f0";
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    for (const r of L.rivers) {
      ctx.beginPath();
      r.cells.forEach((c, k) => {
        const x = (c % L.width) * 8 + 4;
        const y = ((c - (c % L.width)) / L.width) * 8 + 4;
        if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    /* Lakes: fill their cell. */
    ctx.fillStyle = "#45c8f0";
    for (const l of L.lakes) {
      ctx.fillRect(l.x * 8, l.y * 8, 8, 8);
    }

    /* Selected region marker. */
    if (state.selectedRegion) {
      const sx = (state.selectedRegion.seedCell % L.width) * 8 + 4;
      const sy = ((state.selectedRegion.seedCell - (state.selectedRegion.seedCell % L.width)) / L.width) * 8 + 4;
      ctx.strokeStyle = "#ffd54d";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(sx, sy, 14, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  function showRegionInfo(r) {
    const info = $("region-info");
    if (!r) {
      info.textContent = "";
      return;
    }
    info.replaceChildren();
    info.appendChild(el("strong", null, r.name));
    const kindLabel = r.kind === "river" || r.kind === "lake" || r.kind === "sea" ? r.kind : r.biome;
    info.appendChild(el("span", null, " · " + (r.kind === "sea" ? "the open sea" : r.kind) + " · " + r.area + " cells"));
    void kindLabel;
  }

  /* ---------------------------------------------------------------- */
  /* Tongue tab                                                        */
  /* ---------------------------------------------------------------- */

  function renderTongue(w) {
    const host = $("pane-tongue");
    host.replaceChildren();
    const lang = w.language;

    host.appendChild(el("h2", null, lang.name));

    const inventory = el("div", "inventory");
    inventory.appendChild(el("p", null, "Consonants — " + lang.consonants.join(" ")));
    inventory.appendChild(el("p", null, "Vowels — " + lang.vowels.join(" ")));
    inventory.appendChild(el("p", null, "Syllable shapes — " + lang.templates.map((t) => t.replace(/C/g, "K").replace(/V/g, "a")).join(" · ")));
    host.appendChild(inventory);

    const table = el("table", "vocab");
    const thead = el("thead");
    const tr = el("tr");
    tr.appendChild(el("th", null, "Word"));
    tr.appendChild(el("th", null, "Meaning"));
    tr.appendChild(el("th", null, "Category"));
    thead.appendChild(tr);
    table.appendChild(thead);
    const tbody = el("tbody");
    for (const wrd of lang.words) {
      const row = el("tr");
      row.appendChild(el("td", "word", wrd.word));
      row.appendChild(el("td", null, wrd.concept));
      row.appendChild(el("td", "cat", wrd.category));
      tbody.appendChild(row);
    }
    table.appendChild(tbody);
    host.appendChild(table);
  }

  /* ---------------------------------------------------------------- */
  /* Bestiary tab                                                      */
  /* ---------------------------------------------------------------- */

  function renderBestiary(w) {
    const host = $("pane-bestiary");
    host.replaceChildren();
    host.appendChild(el("h2", null, "The creatures of " + w.name));
    const grid = el("div", "creatures");
    for (const c of w.bestiary) {
      const card = el("div", "creature");
      card.appendChild(el("h3", null, c.name));
      const meta = el("p", "creature-meta");
      meta.textContent = c.size + " · " + c.diet + " of " + c.habitat.name;
      card.appendChild(meta);
      for (const s of c.description) {
        card.appendChild(el("p", null, s));
      }
      grid.appendChild(card);
    }
    host.appendChild(grid);
  }

  /* ---------------------------------------------------------------- */
  /* Telling tab                                                       */
  /* ---------------------------------------------------------------- */

  function renderTelling(w) {
    const host = $("pane-telling");
    host.replaceChildren();
    const myth = w.myth;
    host.appendChild(el("h2", null, myth.title));

    const prose = el("div", "myth");
    const text = myth.sentences.join(" ");
    /* Highlight real places and creatures, link them to their tabs. */
    const tokens = [];
    const refs = myth.refs.regions.map((r) => r.name).concat(myth.refs.creatures.map((c) => c.name));
    let rest = text;
    while (rest.length) {
      let hit = null;
      let hitIdx = rest.length;
      for (const r of refs) {
        const i = rest.indexOf(r);
        if (i !== -1 && i < hitIdx) { hitIdx = i; hit = r; }
      }
      if (hit === null) {
        tokens.push({ text: rest, ref: null });
        break;
      }
      if (hitIdx > 0) tokens.push({ text: rest.slice(0, hitIdx), ref: null });
      tokens.push({ text: hit, ref: hit });
      rest = rest.slice(hitIdx + hit.length);
    }
    for (const t of tokens) {
      if (t.ref) {
        const span = el("span", "ref", t.ref);
        const kind = myth.refs.regions.some((r) => r.name === t.ref) ? "a place on the map" : "a creature of the world";
        span.title = "This is " + kind + " — find it in the " + (kind.includes("place") ? "Land" : "Bestiary") + " tab.";
        prose.appendChild(span);
      } else {
        prose.appendChild(document.createTextNode(t.text));
      }
    }
    host.appendChild(prose);
    host.appendChild(el("p", "myth-note", "Every underlined name is real: it was generated for this same seed and exists on the map or in the bestiary."));
  }

  /* ---------------------------------------------------------------- */
  /* Boot                                                              */
  /* ---------------------------------------------------------------- */

  function boot() {
    TABS.forEach((t) => {
      const b = el("button", "tab-btn" + (t === "land" ? " active" : ""), t.charAt(0).toUpperCase() + t.slice(1));
      b.type = "button";
      b.dataset.tab = t;
      b.addEventListener("click", () => setTab(t));
      $("tabs").appendChild(b);
    });

    $("seed-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") generate();
    });
    $("generate-btn").addEventListener("click", generate);
    $("random-btn").addEventListener("click", randomSeed);

    const hashSeed = readSeedFromHash();
    $("seed-input").value = hashSeed || "meadow";
    generate();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
