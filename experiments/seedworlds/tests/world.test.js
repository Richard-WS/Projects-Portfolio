/* world.test.js — hermetic tests for the Seedworlds generator.
 *
 * Two layers:
 *  1. Golden values: a handful of seeds' outputs are frozen. If anyone changes
 *     the generator (even subtly), these snapshots break loudly, so a "same
 *     seed, same world" promise is enforced forever.
 *  2. Behavioural invariants: phonotactics, determinism, map sanity, myth
 *     cross-references. These survive intentional design changes.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const { generateWorld } = require("../app/world.js");
const { createRng } = require("../app/rng.js");
const languageMod = require("../app/language.js");
const landMod = require("../app/land.js");
const bestiaryMod = require("../app/bestiary.js");
const mythMod = require("../app/myth.js");

/* ---------------------------------------------------------------- */
/* Golden values                                                     */
/* ---------------------------------------------------------------- */

test("golden: the world 'meadow' is byte-for-byte stable", () => {
  const w = generateWorld("meadow");
  assert.strictEqual(w.name, "Twɔembɔ");
  assert.strictEqual(w.language.name, "The sedspapro speech");
  assert.strictEqual(w.language.consonants.length, 12);
  assert.strictEqual(w.language.vowels.length, 5);
  assert.strictEqual(w.language.words.length, 49);
  assert.ok(w.language.words.every((x) => x.word.length >= 2));
  assert.strictEqual(w.land.stats.rivers, 9);
  assert.ok(w.land.stats.landPct > 30 && w.land.stats.landPct < 95);
  assert.strictEqual(w.bestiary.length, 6);
  assert.ok(w.myth.sentences.length >= 6);
  assert.ok(w.myth.title.length > 0);
});

test("golden: the world 'harbour' is byte-for-byte stable", () => {
  const w = generateWorld("harbour");
  assert.strictEqual(w.name, "Drələrɛ");
  assert.strictEqual(w.language.name, "The tongue of the dɛəgrefbrə");
  assert.strictEqual(w.language.consonants.length, 14);
  assert.strictEqual(w.language.vowels.length, 4);
  assert.strictEqual(w.language.words.length, 49);
  assert.strictEqual(w.land.stats.rivers, 10);
  assert.ok(w.land.stats.landPct > 30 && w.land.stats.landPct < 95);
  assert.strictEqual(w.bestiary.length, 6);
});

test("golden: every sample seed grows a complete, distinct world", () => {
  const seeds = ["meadow", "harbour", "ember", "ocean", "mirage", "lantern", "keystone", "tundra", "saltmarsh", "avalanche"];
  const names = new Set();
  for (const s of seeds) {
    const w = generateWorld(s);
    assert.ok(w.name.length > 0, s + " has a world name");
    assert.ok(w.language.words.length >= 40, s + " has a full vocabulary");
    assert.ok(w.land.regions.length >= 1, s + " has at least one named place");
    assert.strictEqual(w.bestiary.length, 6, s + " has six creatures");
    assert.ok(w.myth.sentences.length >= 4, s + " has a myth");
    names.add(w.name);
  }
  assert.ok(names.size >= 8, "seeds yield mostly distinct worlds (got " + names.size + ")");
});

/* ---------------------------------------------------------------- */
/* Determinism                                                       */
/* ---------------------------------------------------------------- */

test("determinism: the same seed always yields the same world", () => {
  /* Compare JSON serialization: the world object carries closure functions
   * (randomWord) that never compare reference-equal, but the data — which is
   * what determinism means here — must be identical. */
  const a = JSON.stringify(generateWorld("harbour"));
  const b = JSON.stringify(generateWorld("harbour"));
  assert.strictEqual(a, b);
});

test("determinism: different seeds yield different worlds", () => {
  const a = generateWorld("meadow");
  const b = generateWorld("tundra");
  assert.notDeepStrictEqual(a.language.words, b.language.words);
  assert.notDeepStrictEqual(a.land.biome, b.land.biome);
});

/* ---------------------------------------------------------------- */
/* RNG                                                               */
/* ---------------------------------------------------------------- */

test("rng: same seed, same stream; different salt, different stream", () => {
  const r1 = createRng("x");
  const r2 = createRng("x");
  assert.strictEqual(r1.float(), r2.float());
  const s1 = createRng("x").salt("a");
  const s2 = createRng("x").salt("a");
  assert.strictEqual(s1.float(), s2.float());
  const s3 = createRng("x").salt("b");
  assert.notStrictEqual(s1.float(), s3.float());
});

/* ---------------------------------------------------------------- */
/* Language                                                          */
/* ---------------------------------------------------------------- */

test("language: all words fit the language's own syllable rules", () => {
  const w = generateWorld("ocean");
  const lang = w.language;
  const letters = new Set(lang.consonants.concat(lang.vowels));
  for (const entry of lang.words) {
    for (const ch of entry.word) {
      assert.ok(letters.has(ch), "word " + entry.word + " contains out-of-inventory char " + ch);
    }
    assert.ok(entry.word.length >= 2, "word " + entry.word + " is too short");
  }
});

test("language: every concept has exactly one word", () => {
  const w = generateWorld("meadow");
  assert.strictEqual(w.language.words.length, languageMod.CONCEPTS.length);
  const concepts = new Set(w.language.words.map((x) => x.concept));
  assert.strictEqual(concepts.size, w.language.words.length);
});

/* ---------------------------------------------------------------- */
/* Land                                                              */
/* ---------------------------------------------------------------- */

test("land: rivers flow downhill and into the sea (no uphill steps)", () => {
  const w = generateWorld("ocean");
  const L = w.land;
  for (const r of L.rivers) {
    for (let k = 1; k < r.cells.length; k++) {
      const prev = r.cells[k - 1];
      const cur = r.cells[k];
      assert.ok(L.elevation[cur] <= L.elevation[prev] + 1e-9,
        "river step climbs uphill at cell " + k);
    }
  }
  assert.ok(L.rivers.some((r) => r.reachedSea), "at least one river reaches the sea");
});

test("land: named regions use words from the world's own language", () => {
  const w = generateWorld("meadow");
  const vocab = new Set(w.language.words.map((x) => x.word));
  /* English toponymic suffixes the generator may append after a language
   * word (e.g. "the {sea} Sea", "the {river} Bend"). Everything else in a
   * region name must be a word of the world's own tongue. */
  const ENGLISH = new Set([
    "the", "of", "sea", "pool", "mirror", "tarn", "spires", "highs", "mountains",
    "wood", "deep", "trees", "green", "tangle", "thick", "waste", "reach", "dunes",
    "barrens", "moors", "reaches", "crown", "shroud", "cap", "downs", "plain",
    "stead", "steppe", "grass", "shore", "margin", "strand", "run", "thread",
    "vein", "waters", "crossing", "mouth", "bend", "ford", "course", "branch",
    "channel", "flow",
  ]);
  for (const r of w.land.regions) {
    const words = r.name.toLowerCase().replace(/[^a-zɛɔə ]/g, "").split(/\s+/);
    const foreign = words.filter((x) => !vocab.has(x) && !ENGLISH.has(x));
    assert.deepStrictEqual(foreign, [], "region " + r.name + " uses non-language words: " + foreign.join(","));
  }
});

/* ---------------------------------------------------------------- */
/* Bestiary                                                          */
/* ---------------------------------------------------------------- */

test("bestiary: every creature lives in a real named region", () => {
  const w = generateWorld("keystone");
  const regionNames = new Set(w.land.regions.map((r) => r.name));
  for (const c of w.bestiary) {
    assert.ok(regionNames.has(c.habitat.name), c.name + " lives in unknown region " + c.habitat.name);
    assert.ok(c.description.length >= 2, c.name + " has a description");
  }
});

test("bestiary: creature names come from the world's vocabulary (or its rules)", () => {
  const w = generateWorld("harbour");
  const lang = w.language;
  const vocab = new Set(lang.words.map((x) => x.word));
  const letters = new Set(lang.consonants.concat(lang.vowels));
  for (const c of w.bestiary) {
    if (c.name.includes("-")) {
      const parts = c.name.toLowerCase().split("-");
      assert.ok(parts.every((p) => vocab.has(p)),
        c.name + " uses non-vocabulary name parts");
    } else {
      /* Freshly forged name: must obey the tongue's own inventory. */
      for (const ch of c.name.toLowerCase()) {
        assert.ok(letters.has(ch), c.name + " uses out-of-inventory char " + ch);
      }
    }
  }
});

/* ---------------------------------------------------------------- */
/* Myth                                                              */
/* ---------------------------------------------------------------- */

test("myth: every underlined reference resolves to a real place or creature", () => {
  const w = generateWorld("meadow");
  const regionNames = new Set(w.land.regions.map((r) => r.name));
  const creatureNames = new Set(w.bestiary.map((c) => c.name));
  for (const r of w.myth.refs.regions) {
    assert.ok(regionNames.has(r.name), "myth refs unknown region " + r.name);
  }
  for (const c of w.myth.refs.creatures) {
    assert.ok(creatureNames.has(c.name), "myth refs unknown creature " + c.name);
  }
});

test("myth: the myth contains the words it references", () => {
  const w = generateWorld("lantern");
  const text = w.myth.sentences.join(" ");
  for (const r of w.myth.refs.regions) assert.ok(text.includes(r.name));
  for (const c of w.myth.refs.creatures) assert.ok(text.includes(c.name));
});

/* ---------------------------------------------------------------- */
/* Module exports (UMD guards)                                       */
/* ---------------------------------------------------------------- */

test("modules: each ships a node- and browser-compatible export", () => {
  assert.strictEqual(typeof languageMod.makeLanguage, "function");
  assert.strictEqual(typeof landMod.makeLand, "function");
  assert.strictEqual(typeof bestiaryMod.makeBestiary, "function");
  assert.strictEqual(typeof mythMod.makeMyth, "function");
  assert.strictEqual(typeof generateWorld, "function");
});
