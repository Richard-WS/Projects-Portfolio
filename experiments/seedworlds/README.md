# Seedworlds

**One word. One complete world.**

Type a single word — *meadow*, *harbour*, *ember* — and Seedworlds grows an
entire world from it: a **language** with its own sound rules and vocabulary,
a **land** with biomes, rivers and named places, **six creatures** that live
in those places and carry names from that language, and a **creation myth**
that tells the story of that land in its own words.

Every layer is derived from the seed. The same word always grows the same
world — byte for byte — and every layer is consistent with every other: the
myth names the rivers on the map, the creatures live in regions the
cartographer drew, and the region names come from the same tongue.

**Live demo:** [richard-ws.github.io/Projects-Portfolio/experiments/seedworlds/app/](https://richard-ws.github.io/Projects-Portfolio/experiments/seedworlds/app/)

## The four forges

| Forge | What it grows |
|---|---|
| **The Tongue** | A phoneme inventory, syllable rules, and a 49-word vocabulary (water, love, mountain, fear…) from the seed |
| **The Land** | Value-noise terrain with biomes, downhill-flowing rivers, lakes, and named regions built from the language's words |
| **The Bestiary** | Six creatures — named from the tongue, sized, dieted, and placed in real regions of the map |
| **The Telling** | A creation myth whose every name is a real place or creature from this world |

## How it works

```
app/rng.js        deterministic seed → random streams (xmur3 + mulberry32)
app/language.js   The Tongue   — phonotactics, vocabulary
app/land.js       The Land     — layered value noise, biomes, rivers, toponyms
app/bestiary.js   The Bestiary — creatures bound to real regions
app/myth.js       The Telling  — story assembled from the world's own names
app/world.js      orchestrates the chain from one seed
app/app.js        browser viewer (tabs, canvas map, shareable #seed= URL)
```

All generation is **pure client-side JavaScript with zero dependencies** —
no build step, no server, no API calls. The viewer runs on GitHub Pages and
works with a mouse or touch. A world is shareable: the seed lives in the URL
hash (`…/app/?seed=meadow`).

## Reproduce

```bash
# Tests — hermetic golden-value + invariant suite (node:test)
bash scripts/test.sh
```

The test suite freezes golden outputs for the `meadow` and `harbour` seeds.
If anyone changes the generator, those snapshots break loudly — the promise
"same seed, same world, forever" is enforced by CI.

## Design notes

- **Determinism everywhere.** Each layer draws from its own sub-stream
  (`seed::layer`), so adding a feature to one forge can never silently change
  another forge's output for existing seeds.
- **Phonotactics over randomness.** Syllable templates only ever use licensed
  consonant clusters built from the tongue's own sampled inventory — words are
  alien but pronounceable.
- **Consistency as a feature.** Region names, creature names and myth names all
  resolve against the same vocabulary, so nothing in a world is ever
  "placeholder English."
