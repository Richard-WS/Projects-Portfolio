/* bestiary.js — the creatures of the world.
 *
 * Six creatures, each named from the world's own tongue, each living in a
 * real region of the generated map. Their size, diet and habits are drawn
 * from the same stream as everything else, so the same seed always yields
 * the same six neighbours.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./language.js"), require("./land.js"));
  } else {
    root.Seedworlds = root.Seedworlds || {};
    root.Seedworlds.bestiary = factory(root.Seedworlds.language, root.Seedworlds.land);
  }
}(typeof self !== "undefined" ? self : this, function (language, land) {
  "use strict";

  const { capitalize, wordFor } = language;

  const SIZES = ["palm-sized", "fox-sized", "horse-sized", "house-sized", "hill-sized"];

  const TRAITS = [
    "burrow", "glow faintly at night", "travel in herds", "camouflage against the ground",
    "climb sheer cliffs", "swim whole rivers", "hibernate through the cold",
    "migrate with the rains", "carry venom", "tunnel under roots", "mimic travellers' calls",
    "hoard stones", "sing at the moon", "never sleep", "shed their skin", "walk on water",
  ];

  const DIET_BY_BIOME = {
    desert: ["scavenger", "scavenger", "omnivore", "hunter"],
    tundra: ["grazer", "hunter", "omnivore"],
    snow: ["grazer", "hunter", "omnivore"],
    jungle: ["hunter", "hunter", "omnivore", "grazer"],
    forest: ["hunter", "omnivore", "grazer"],
    plains: ["grazer", "grazer", "omnivore", "hunter"],
    steppe: ["grazer", "grazer", "omnivore", "hunter"],
    mountain: ["hunter", "grazer", "omnivore"],
    coast: ["hunter", "omnivore", "scavenger"],
    river: ["hunter", "omnivore", "scavenger"],
    lake: ["hunter", "omnivore", "scavenger"],
  };

  const NAME_WORDS = {
    grazer: ["herd", "plains", "valley", "tundra", "river", "moon"],
    hunter: ["fang", "claw", "wolf", "eye", "hunger", "bone"],
    scavenger: ["bone", "ash", "fang", "wind", "sand", "death"],
    omnivore: ["hand", "fire", "ash", "forest", "house", "stone"],
  };

  const WATER_WORDS = ["fish", "sea", "rain", "salt"];

  const ACTIONS = {
    grazer: ["It grazes the {plains} at {sun}fall.", "It follows the rains across the {plains}."],
    hunter: ["It hunts by {eye} and by smell.", "It watches from the {stone} until dark."],
    scavenger: ["It follows the {bird}{p}.", "It arrives where the {death} has been."],
    omnivore: ["It raids the {house}{p} of the {people}.", "It will eat anything that holds still."],
  };

  const BODY_LINES = [
    "Its {fang} never stops growing.",
    "Its {claw}{p} glint in the {moon}light.",
    "Its {eye} never blinks.",
    "Its {bone}{p} ring like {song}.",
    "Its {wing}{p} are useless on the ground.",
    "Its {heart} beats once a minute.",
  ];

  function pickDiet(rng, kind, biome) {
    const pool = DIET_BY_BIOME[kind === "river" || kind === "lake" ? kind : biome] || DIET_BY_BIOME.forest;
    return rng.pick(pool);
  }

  function makeBestiary(rng, language, land) {
    const creatures = [];
    const habitats = land.regions.filter((r) => r.kind !== "sea");
    const traits = rng.sample(TRAITS, 6);

    for (let i = 0; i < 6; i++) {
      /* Each creature draws from its own sub-stream, so no two creatures'
       * fates are entangled and traits stay distinct. */
      const cr = rng.salt("creature:" + i);

      /* Habitat weighted by size, so creatures favour the big places.
       * Worlds with almost no land fall back to a generic home. */
      let habitat = null;
      if (habitats.length) {
        const total = habitats.reduce((s, r) => s + r.area, 0) || 1;
        let roll = cr.float() * total;
        habitat = habitats[0];
        for (const r of habitats) {
          roll -= r.area;
          if (roll <= 0) { habitat = r; break; }
        }
      } else {
        habitat = { kind: "plains", biome: "plains", name: "the open land", area: 1 };
      }

      const diet = pickDiet(cr, habitat.kind, habitat.biome);

      /* A name from the tongue: either two apt words, or a fresh one. */
      let name;
      if (cr.chance(0.55)) {
        const pool = NAME_WORDS[diet].concat(
          habitat.kind === "river" || habitat.kind === "lake" || habitat.kind === "coast" ? WATER_WORDS : []
        );
        const [w1, w2] = cr.sample(pool, 2);
        name = capitalize(wordFor(language, w1)) + "-" + capitalize(wordFor(language, w2));
      } else {
        name = capitalize(language.randomWord(cr.salt("name"), 2, 3));
      }

      const size = cr.pick(SIZES);

      /* Habitat names carry their own "The"; prose wants "of the Hoit Margin". */
      const habitatProse = habitat.name.replace(/^The\s+/, "");

      const sentences = [
        "The " + name + " is a " + size + " " + diet + " of the " + habitatProse + ", known to " + traits[i] + ".",
      ];
      const subst = (s) => s.replace(/\{(\w+)\}/g, (_, c) => c === "p" ? language.plural : wordFor(language, c));
      const act = cr.pick(ACTIONS[diet]);
      sentences.push(subst(act));
      const body = cr.pick(BODY_LINES);
      sentences.push(subst(body));

      creatures.push({
        id: i,
        name,
        size,
        diet,
        trait: traits[i],
        habitat: { kind: habitat.kind, name: habitat.name },
        description: sentences,
      });
    }

    return creatures;
  }

  return { SIZES, TRAITS, makeBestiary };
}));
