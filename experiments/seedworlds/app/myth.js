/* myth.js — the Telling: a creation story that quotes the world itself.
 *
 * The myth is assembled from sentence skeletons, but every name inside it is
 * real: the sea, the mountains, the rivers and the creatures that were
 * generated for this seed. Read the story, then find the places in the Land
 * tab — they are the same places.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./language.js"), require("./land.js"));
  } else {
    root.Seedworlds = root.Seedworlds || {};
    root.Seedworlds.myth = factory(root.Seedworlds.language, root.Seedworlds.land);
  }
}(typeof self !== "undefined" ? self : this, function (language, land) {
  "use strict";

  const { capitalize, wordFor } = language;

  function makeMyth(rng, language, land, bestiary) {
    const say = (c) => wordFor(language, c);
    const cap = capitalize;
    const region = (kind) => land.regions.find((r) => r.kind === kind) || null;
    const FALLBACK = {
      sea: "the sea", mountain: "the mountains", forest: "the forest",
      jungle: "the jungle", desert: "the desert", river: "the river", lake: "the lake",
    };
    /* Region names carry their own "The"; strip it so prose reads
     * "the Hoit Waters", not "the The Hoit Waters". */
    const proseName = (r) => r.name.replace(/^The\s+/, "");
    const feat = (kind) => {
      const r = region(kind);
      return r ? proseName(r) : FALLBACK[kind] || "the " + kind;
    };

    const creatures = bestiary;
    const c1 = rng.pick(creatures);
    const others = creatures.filter((c) => c !== c1);
    const c2 = rng.pick(others);

    const creator = cap(say("god")) + " " + rng.pick([
      "who walks the " + say("sky"),
      "of the " + feat("sea"),
      "who made the " + say("moon"),
      "who carries the " + say("star") + language.plural,
    ]);

    const sentences = [];

    sentences.push(rng.pick([
      "Before " + say("water") + ", there was only " + say("wind") + ".",
      "In the beginning the world was " + say("ash") + " and " + say("wind") + ".",
      "Before the " + say("star") + language.plural + ", nothing spoke.",
    ]));

    sentences.push(rng.pick([
      "The " + creator + " " + rng.pick(["dug", "wept", "carved", "breathed"]) + " the " + feat("sea") + " into being.",
      "The " + creator + " spilled the " + feat("sea") + " across the low places.",
    ]));

    sentences.push(rng.pick([
      "Then " + rng.pick(["they", "the " + creator]) + " raised the " + feat("mountain") + " as a backrest for the " + say("sky") + ".",
      "The " + say("sky") + " pressed down, and the " + feat("mountain") + " grew to hold it up.",
      "Where " + rng.pick(["they", "the " + creator]) + " rested, the " + feat("forest") + " climbed out of the ground.",
    ]));

    sentences.push(rng.pick([
      "From " + say("stone") + " and " + say("rain") + " came " + c1.name + ".",
      cap(c1.name) + " was born of the " + feat("forest") + "'s first shadow.",
      "The " + creator + " shaped " + c1.name + " from leftover " + say("blood") + " and " + say("bone") + ".",
    ]));

    sentences.push(rng.pick([
      cap(c1.name) + " walked the length of " + feat("river") + " and never once drank.",
      "It was " + c1.name + " who taught the " + say("bird") + language.plural + " to " + say("song") + ".",
      cap(c1.name) + " carried " + say("fire") + " from the " + feat("mountain") + " to the " + feat("forest") + ".",
    ]));

    sentences.push(rng.pick([
      "Then the " + creator + " made " + c2.name + " as " + rng.pick(["a warning", "a friend", "a mirror"]) + " to " + c1.name + ".",
      cap(c2.name) + " followed " + c1.name + " out of " + say("fear") + ", and has never left.",
    ]));

    sentences.push(rng.pick([
      "That is why " + c2.name + " " + rng.pick([
        "keeps to the " + feat("river") + " to this day",
        "hunts by " + say("moon") + "light",
        "is never seen by the " + say("people"),
      ]) + ".",
      "And that is why the " + say("sea") + " still tastes of " + say("salt") + ".",
    ]));

    const title = rng.pick([
      "The " + cap(say("god")) + " of the " + cap(say("moon")),
      "How the " + cap(say("sea")) + " Was Made",
      "The " + cap(say("star")) + " That Stayed",
    ]);

    /* Refs: scan the finished text for real names so the viewer can
     * highlight them and link back to the Land and the Bestiary. */
    const text = sentences.join(" ");
    const refRegions = land.regions
      .filter((r) => text.includes(r.name))
      .map((r) => ({ name: r.name, kind: r.kind }));
    const refCreatures = creatures
      .filter((c) => text.includes(c.name))
      .map((c) => ({ name: c.name }));
    const refWords = language.words
      .filter((w) => text.includes(w.word))
      .map((w) => w.concept);

    return {
      title,
      sentences,
      refs: { regions: refRegions, creatures: refCreatures, words: refWords },
    };
  }

  return { makeMyth };
}));
