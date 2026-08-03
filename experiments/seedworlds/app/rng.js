/* rng.js — deterministic random streams for Seedworlds.
 *
 * Every part of a world derives from one seed string through these streams:
 * same seed, same world, forever. Pure functions only, so the whole thing is
 * unit-testable and the browser build and the tests load the same code.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.Seedworlds = root.Seedworlds || {};
    root.Seedworlds.rng = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* xmur3 string hash — yields 32-bit unsigned integers one at a time. */
  function xmur3(str) {
    let h = 1779033703 ^ str.length;
    for (let i = 0; i < str.length; i++) {
      h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    return function () {
      h = Math.imul(h ^ (h >>> 16), 2246822507);
      h = Math.imul(h ^ (h >>> 13), 3266489909);
      h ^= h >>> 16;
      return h >>> 0;
    };
  }

  /* mulberry32 PRNG — fast 32-bit generator returning floats in [0, 1). */
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* One stable 32-bit integer per seed string. */
  function hashSeed(str) {
    const h = xmur3(String(str));
    return h();
  }

  /* A full stream of helpers, all bound to one seed string.
   * salt() derives an independent sub-stream, so two consumers can draw from
   * the same parent stream without order-dependence. */
  function createRng(seedStr) {
    const rand = mulberry32(hashSeed(seedStr));
    const rng = {
      float: () => rand(),
      int: (min, max) => min + Math.floor(rand() * (max - min + 1)),
      pick: (arr) => arr[Math.floor(rand() * arr.length)],
      chance: (p) => rand() < p,
      shuffle: (arr) => {
        const a = arr.slice();
        for (let i = a.length - 1; i > 0; i--) {
          const j = Math.floor(rand() * (i + 1));
          const t = a[i]; a[i] = a[j]; a[j] = t;
        }
        return a;
      },
      sample: (arr, n) => rng.shuffle(arr).slice(0, n),
      salt: (label) => createRng(String(seedStr) + "::" + String(label)),
    };
    return rng;
  }

  return { xmur3, mulberry32, hashSeed, createRng };
}));
