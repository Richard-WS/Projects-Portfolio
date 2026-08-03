/* land.js — the Land: terrain, biomes, rivers, lakes and named regions.
 *
 * Elevation and moisture come from layered value noise; temperature follows
 * latitude. Rivers flow from wet high ground down to the sea by steepest
 * descent, and wherever one stalls a lake forms. The biggest stretches of
 * each biome become named regions — and their names come from the world's
 * own language, so the map and the tongue always agree.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.Seedworlds = root.Seedworlds || {};
    root.Seedworlds.land = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const OCEAN = "ocean";
  const COAST = "coast";
  const PLAINS = "plains";
  const STEPPE = "steppe";
  const FOREST = "forest";
  const JUNGLE = "jungle";
  const DESERT = "desert";
  const TUNDRA = "tundra";
  const SNOW = "snow";
  const MOUNTAIN = "mountain";

  const BIOMES = [OCEAN, COAST, PLAINS, STEPPE, FOREST, JUNGLE, DESERT, TUNDRA, SNOW, MOUNTAIN];

  const BIOME_LABELS = {
    ocean: "Open water", coast: "Coast", plains: "Plains", steppe: "Steppe",
    forest: "Forest", jungle: "Jungle", desert: "Desert", tundra: "Tundra",
    snow: "Snowfield", mountain: "Mountains",
  };

  const SEA_MIN_AREA = 200;

  /* Layered value noise: a lattice of random values at `cell` spacing,
   * smoothly interpolated. Each layer draws from its own stream. */
  function valueNoise(width, height, cell, stream) {
    const gx = Math.ceil(width / cell) + 2;
    const gy = Math.ceil(height / cell) + 2;
    const lattice = [];
    for (let y = 0; y < gy; y++) {
      const row = [];
      for (let x = 0; x < gx; x++) row.push(stream.float());
      lattice.push(row);
    }
    const out = new Array(width * height);
    for (let y = 0; y < height; y++) {
      const fy = y / cell;
      const y0 = Math.floor(fy);
      const ty = fy - y0;
      const sy = ty * ty * (3 - 2 * ty);
      for (let x = 0; x < width; x++) {
        const fx = x / cell;
        const x0 = Math.floor(fx);
        const tx = fx - x0;
        const sx = tx * tx * (3 - 2 * tx);
        const a = lattice[y0][x0];
        const b = lattice[y0][x0 + 1];
        const c = lattice[y0 + 1][x0];
        const d = lattice[y0 + 1][x0 + 1];
        out[y * width + x] = a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
      }
    }
    return out;
  }

  /* Radial falloff pushes the edges underwater so the world is an island
   * (or an archipelago, when the seed asks for one). */
  function falloff(x, y, width, height, power) {
    const nx = (x / width) * 2 - 1;
    const ny = (y / height) * 2 - 1;
    const d = Math.sqrt(nx * nx + ny * ny) / Math.SQRT2;
    return Math.max(0, 1 - Math.pow(d, power));
  }

  function clamp01(v) {
    return v < 0 ? 0 : v > 1 ? 1 : v;
  }

  function biomeAt(elev, moist, temp) {
    if (elev < 0.30) return OCEAN;
    if (elev < 0.36) return COAST;
    if (elev > 0.78) return temp < 0.35 ? SNOW : MOUNTAIN;
    if (temp < 0.26) return elev > 0.55 ? SNOW : TUNDRA;
    if (moist < 0.30) return temp > 0.60 ? DESERT : STEPPE;
    if (moist > 0.78 && temp > 0.55) return JUNGLE;
    if (moist > 0.62 && temp > 0.30) return FOREST;
    if (temp > 0.45) return PLAINS;
    return STEPPE;
  }

  /* Largest 4-connected components of one biome, biggest first. */
  function components(biome, width, height, code) {
    const seen = new Int8Array(width * height);
    const comps = [];
    for (let start = 0; start < biome.length; start++) {
      if (seen[start] || biome[start] !== code) continue;
      const cells = [];
      const stack = [start];
      seen[start] = 1;
      while (stack.length) {
        const idx = stack.pop();
        cells.push(idx);
        const x = idx % width;
        const y = (idx - x) / width;
        if (x > 0 && !seen[idx - 1] && biome[idx - 1] === code) { seen[idx - 1] = 1; stack.push(idx - 1); }
        if (x < width - 1 && !seen[idx + 1] && biome[idx + 1] === code) { seen[idx + 1] = 1; stack.push(idx + 1); }
        if (y > 0 && !seen[idx - width] && biome[idx - width] === code) { seen[idx - width] = 1; stack.push(idx - width); }
        if (y < height - 1 && !seen[idx + width] && biome[idx + width] === code) { seen[idx + width] = 1; stack.push(idx + width); }
      }
      comps.push(cells);
    }
    comps.sort((a, b) => b.length - a.length);
    return comps;
  }

  function makeLand(rng, language, opts) {
    const width = (opts && opts.width) || 96;
    const height = (opts && opts.height) || 64;
    const minRegionArea = (opts && opts.minRegionArea) || 28;

    /* Elevation: three octaves of noise, island-shaped. */
    const eOctaves = [{ cell: 48, w: 0.50 }, { cell: 24, w: 0.30 }, { cell: 12, w: 0.20 }];
    const elevation = new Array(width * height).fill(0);
    let wSum = 0;
    for (let i = 0; i < eOctaves.length; i++) {
      const n = valueNoise(width, height, eOctaves[i].cell, rng.salt("elev" + i));
      const w = eOctaves[i].w;
      for (let k = 0; k < n.length; k++) elevation[k] += n[k] * w;
      wSum += w;
    }
    const archipelago = rng.chance(0.18);
    const power = archipelago ? 1.40 : 2.0;
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const i = y * width + x;
        elevation[i] = (elevation[i] / wSum) * falloff(x, y, width, height, power);
      }
    }

    /* Moisture: two octaves, no falloff. */
    const mOctaves = [{ cell: 24, w: 0.60 }, { cell: 12, w: 0.40 }];
    const moisture = new Array(width * height).fill(0);
    let mSum = 0;
    for (let i = 0; i < mOctaves.length; i++) {
      const n = valueNoise(width, height, mOctaves[i].cell, rng.salt("moist" + i));
      const w = mOctaves[i].w;
      for (let k = 0; k < n.length; k++) moisture[k] += n[k] * w;
      mSum += w;
    }
    for (let k = 0; k < moisture.length; k++) moisture[k] /= mSum;

    /* Temperature: colder toward the top edge, wobbled by one noise layer. */
    const tNoise = valueNoise(width, height, 24, rng.salt("temp"));
    const biome = new Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const i = y * width + x;
        const temp = clamp01(y / height + tNoise[i] * 0.30 - 0.15);
        biome[i] = biomeAt(elevation[i], moisture[i], temp);
      }
    }

    /* Rivers: walk downhill from wet high ground until the sea, or a stall. */
    const sources = [];
    for (let i = 0; i < biome.length; i++) {
      if (biome[i] !== OCEAN && biome[i] !== COAST && moisture[i] > 0.75 && elevation[i] > 0.40) {
        sources.push(i);
      }
    }
    sources.sort((a, b) => moisture[b] - moisture[a]);
    const riverCells = new Int8Array(width * height);
    const stallCount = new Map();
    const rivers = [];
    for (let s = 0; s < Math.min(10, sources.length); s++) {
      let idx = sources[s];
      const path = [];
      const visited = new Set();
      let reachedSea = false;
      for (let step = 0; step < 1500; step++) {
        if (visited.has(idx)) break;
        visited.add(idx);
        path.push(idx);
        if (biome[idx] === OCEAN) { reachedSea = true; break; }
        const x = idx % width;
        const y = (idx - x) / width;
        let best = -1;
        let bestElev = elevation[idx];
        const tryMove = (ni) => {
          if (elevation[ni] < bestElev) { bestElev = elevation[ni]; best = ni; }
        };
        if (x > 0) tryMove(idx - 1);
        if (x < width - 1) tryMove(idx + 1);
        if (y > 0) tryMove(idx - width);
        if (y < height - 1) tryMove(idx + width);
        if (best === -1) {
          stallCount.set(idx, (stallCount.get(idx) || 0) + 1);
          break;
        }
        idx = best;
      }
      if (path.length >= 4) {
        path.forEach((c) => { riverCells[c] = 1; });
        rivers.push({ cells: path, reachedSea, source: sources[s] });
      }
    }

    /* Lakes form where rivers stall; count visits so only real basins count. */
    const lakes = [];
    stallCount.forEach((count, idx) => {
      if (count >= 1) {
        lakes.push({ x: idx % width, y: (idx - idx % width) / width, size: count });
      }
    });

    /* Regions: name the biggest stretch of each land biome, plus the sea,
     * plus every river and lake. Names come from the language. */
    const say = (c) => language.words.find((w) => w.concept === c)?.word || c;
    const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
    const NAME_TEMPLATES = {
      mountain: ["the {mountain} Spires", "the {mountain} Highs", "the {mountain} Mountains"],
      forest: ["the {forest} Wood", "the {forest} Deep", "the {forest} Trees"],
      jungle: ["the {jungle} Green", "the {jungle} Tangle", "the {jungle} Thick"],
      desert: ["the {desert} Waste", "the {desert} Reach", "the {desert} Dunes"],
      tundra: ["the {tundra} Barrens", "the {tundra} Moors", "the {tundra} Reaches"],
      snow: ["the {snow} Crown", "the {snow} Shroud", "the {snow} Cap"],
      plains: ["the {plains} Downs", "the {plains} Plain", "the {plains} Stead"],
      steppe: ["the {plains} Steppe", "the {plains} Grass"],
      coast: ["the {sea} Shore", "the {sea} Margin", "the {sea} Strand"],
    };

    const regions = [];
    let regionId = 0;
    const landBiomes = [MOUNTAIN, FOREST, JUNGLE, DESERT, TUNDRA, SNOW, PLAINS, STEPPE, COAST];
    for (const code of landBiomes) {
      const comps = components(biome, width, height, code);
      for (const cells of comps) {
        if (cells.length < minRegionArea) break;
        const tmpl = rng.pick(NAME_TEMPLATES[code]);
        const name = cap(tmpl.replace(/\{(\w+)\}/g, (_, c) => cap(say(c))));
        regions.push({
          id: regionId++,
          kind: code,
          name,
          biome: code,
          area: cells.length,
          seedCell: cells[0],
        });
        break; /* one named region per land biome */
      }
    }

    /* The sea: the biggest stretch of open water. */
    const seaComps = components(biome, width, height, OCEAN);
    const seaCells = seaComps[0] || [];
    if (seaCells.length >= SEA_MIN_AREA) {
      const tmpl = rng.pick(["the {sea} Sea", "the {sea} Deep", "the {sea} Waters"]);
      regions.push({
        id: regionId++,
        kind: "sea",
        name: cap(tmpl.replace(/\{(\w+)\}/g, (_, c) => cap(say(c)))),
        biome: OCEAN,
        area: seaCells.length,
        seedCell: seaCells[0],
      });
    }

    /* Rivers and lakes as named places too. Rivers shuffle a template pool so
     * no two rivers in a world share a name. */
    const RIVER_TEMPLATES = [
      "the {river} Run", "the {river} Thread", "the {river} Vein",
      "the {river} Crossing", "the {river} Mouth", "the {river} Bend",
      "the {river} Reach", "the {river} Ford", "the {river} Course",
      "the {river} Branch", "the {river} Channel", "the {river} Flow",
    ];
    const riverTemplates = rng.shuffle(RIVER_TEMPLATES);
    for (const r of rivers) {
      if (r.cells.length < 6) continue;
      const tmpl = riverTemplates[regionId % riverTemplates.length] || rng.pick(RIVER_TEMPLATES);
      regions.push({
        id: regionId++,
        kind: "river",
        name: cap(tmpl.replace(/\{(\w+)\}/g, (_, c) => cap(say(c)))),
        biome: "river",
        area: r.cells.length,
        seedCell: r.cells[0],
      });
    }
    for (const l of lakes) {
      const tmpl = rng.pick(["the {moon} Pool", "the {eye} Mirror", "the {star} Tarn"]);
      regions.push({
        id: regionId++,
        kind: "lake",
        name: cap(tmpl.replace(/\{(\w+)\}/g, (_, c) => cap(say(c)))),
        biome: "lake",
        area: l.size,
        seedCell: l.x + l.y * width,
      });
    }

    /* Handy summary numbers for the README and the viewer's info panel. */
    const stats = { width, height, archipelago, biomeCells: {}, rivers: rivers.length, lakes: lakes.length, regions: regions.length };
    for (const b of BIOMES) stats.biomeCells[b] = 0;
    for (let i = 0; i < biome.length; i++) stats.biomeCells[biome[i]] = (stats.biomeCells[biome[i]] || 0) + 1;
    stats.landPct = Math.round((100 * (width * height - stats.biomeCells[OCEAN])) / (width * height) * 10) / 10;

    return {
      width,
      height,
      archipelago,
      elevation,
      moisture,
      biome,
      biomeLabels: BIOME_LABELS,
      rivers: rivers.map((r) => ({ cells: r.cells, reachedSea: r.reachedSea })),
      lakes,
      regions,
      stats,
    };
  }

  return { BIOMES, BIOME_LABELS, makeLand };
}));
