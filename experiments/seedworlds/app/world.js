/* world.js — the whole world from one word.
 *
 * generateWorld(seed) chains the four layers: a tongue, a land, its
 * creatures and its story. Everything is derived from the seed through
 * independent streams, so the same seed always grows the same world —
 * byte for byte. The result is plain data, ready to render or to keep.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("./rng.js"),
      require("./language.js"),
      require("./land.js"),
      require("./bestiary.js"),
      require("./myth.js")
    );
  } else {
    root.Seedworlds = root.Seedworlds || {};
    root.Seedworlds.world = factory(
      root.Seedworlds.rng,
      root.Seedworlds.language,
      root.Seedworlds.land,
      root.Seedworlds.bestiary,
      root.Seedworlds.myth
    );
  }
}(typeof self !== "undefined" ? self : this, function (rngMod, languageMod, landMod, bestiaryMod, mythMod) {
  "use strict";

  function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  }

  function generateWorld(seed, opts) {
    const seedStr = String(seed);
    const rng = rngMod.createRng(seedStr);

    const language = languageMod.makeLanguage(rng.salt("language"), opts);
    const land = landMod.makeLand(rng.salt("land"), language, opts);
    const bestiary = bestiaryMod.makeBestiary(rng.salt("bestiary"), language, land);
    const myth = mythMod.makeMyth(rng.salt("myth"), language, land, bestiary);

    /* The world takes its name from one of its own words. */
    const name = capitalize(languageMod.wordFor(language, rng.pick(["sea", "mountain", "valley", "star", "moon"])));

    return { seed: seedStr, name, language, land, bestiary, myth };
  }

  return { generateWorld };
}));
