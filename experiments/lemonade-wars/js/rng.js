// Seeded random number generator (mulberry32). The Python core uses
// random.Random; this mirrors its interface (random, uniform, gauss, choices,
// choice, randint, shuffle) so seeded runs are deterministic and testable.
//
// The generator state is kept in an object so save/load can snapshot the
// exact mid-stream position and resume identically.
"use strict";

export function mulberry32(seed) {
  const s = { a: seed >>> 0 };
  const f = () => {
    s.a = (s.a + 0x6d2b79f5) | 0;
    let t = Math.imul(s.a ^ (s.a >>> 15), 1 | s.a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  f.state = () => ({ a: s.a });
  f.fromState = (st) => {
    s.a = st.a >>> 0;
    return f;
  };
  return f;
}

export class RNG {
  constructor(seed = Date.now() >>> 0) {
    this._seed = seed >>> 0;
    this._f = mulberry32(this._seed);
  }

  get seed() {
    return this._seed;
  }

  random() {
    return this._f();
  }

  uniform(a, b) {
    return a + (b - a) * this._f();
  }

  // Box-Muller approximation, matching random.gauss distribution shape.
  gauss(mu = 0.0, sigma = 1.0) {
    let u = 0;
    let v = 0;
    while (u === 0) u = this._f();
    while (v === 0) v = this._f();
    const z = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    return mu + z * sigma;
  }

  // Python random.choices: pick k items from population with weights.
  choices(population, weights, k = 1) {
    if (weights) {
      const total = weights.reduce((a, b) => a + b, 0);
      const out = [];
      for (let i = 0; i < k; i++) {
        let r = this._f() * total;
        let idx = 0;
        for (let j = 0; j < weights.length; j++) {
          r -= weights[j];
          if (r <= 0) {
            idx = j;
            break;
          }
        }
        out.push(population[idx]);
      }
      return k === 1 ? out[0] : out;
    }
    const out = [];
    for (let i = 0; i < k; i++) out.push(population[Math.floor(this._f() * population.length)]);
    return k === 1 ? out[0] : out;
  }

  choice(population) {
    return population[Math.floor(this._f() * population.length)];
  }

  randint(lo, hi) {
    return lo + Math.floor(this._f() * (hi - lo + 1));
  }

  shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(this._f() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  // Serializable state so saves restore the exact RNG position (mid-stream).
  snapshot() {
    return { seed: this._seed, state: this._f.state() };
  }

  static restore(snap) {
    const rng = new RNG(snap.seed);
    if (snap.state) rng._f = rng._f.fromState(snap.state);
    return rng;
  }
}
