/* language.js — the Tongue: phonemes, syllable rules and a working vocabulary.
 *
 * A Seedworld language is built from a deterministic stream: pick consonants
 * and vowels, pick syllable templates, then generate one word per concept.
 * Every word is stable for a given seed, so a creature or a myth can quote
 * the language and stay consistent forever.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.Seedworlds = root.Seedworlds || {};
    root.Seedworlds.language = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const CONSONANT_POOL = ["p","b","t","d","k","g","f","v","s","z","m","n","l","r","w","j","h"];
  const VOWEL_POOL = ["a","e","i","o","u","ɛ","ɔ","ə"];
  const TEMPLATE_POOL = ["CV","CVC","CVV","CCV","VCV","CVCV","CVCC","CCVC","VC"];

  /* Clusters are kept to real speech sounds, not random pairings. */
  const ONSET_CLUSTERS = ["pl","pr","bl","br","kl","kr","gl","gr","tr","dr","st","sk","sp","sl","sw","kw","tw","dw"];
  const CODA_CLUSTERS = ["lt","ld","lk","rk","rd","rt","nt","nd","mp","mb","nk","st","sk","sp","ls","rs"];

  /* The concepts every tongue must have a word for. Other generators reach
   * into this list to name creatures, places and stories. */
  const CONCEPTS = [
    { category: "element", word: "water" }, { category: "element", word: "sea" },
    { category: "element", word: "rain" }, { category: "element", word: "snow" },
    { category: "element", word: "ice" }, { category: "element", word: "fire" },
    { category: "element", word: "ash" }, { category: "element", word: "stone" },
    { category: "element", word: "sand" }, { category: "element", word: "salt" },
    { category: "element", word: "wind" }, { category: "element", word: "sky" },
    { category: "element", word: "star" }, { category: "element", word: "moon" },
    { category: "element", word: "sun" }, { category: "element", word: "cloud" },
    { category: "land", word: "mountain" }, { category: "land", word: "river" },
    { category: "land", word: "forest" }, { category: "land", word: "jungle" },
    { category: "land", word: "desert" }, { category: "land", word: "tundra" },
    { category: "land", word: "plains" }, { category: "land", word: "valley" },
    { category: "body", word: "eye" }, { category: "body", word: "hand" },
    { category: "body", word: "heart" }, { category: "body", word: "blood" },
    { category: "body", word: "bone" }, { category: "body", word: "wing" },
    { category: "body", word: "fang" }, { category: "body", word: "claw" },
    { category: "kin", word: "mother" }, { category: "kin", word: "father" },
    { category: "kin", word: "child" }, { category: "kin", word: "people" },
    { category: "living", word: "bird" }, { category: "living", word: "fish" },
    { category: "living", word: "wolf" }, { category: "living", word: "herd" },
    { category: "culture", word: "house" }, { category: "culture", word: "boat" },
    { category: "culture", word: "song" }, { category: "culture", word: "death" },
    { category: "culture", word: "love" }, { category: "culture", word: "fear" },
    { category: "culture", word: "war" }, { category: "culture", word: "god" },
    { category: "culture", word: "hunger" },
  ];

  function capitalize(s) {
    if (!s) return s;
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function wordFor(language, concept) {
    const hit = language.words.find((w) => w.concept === concept);
    return hit ? hit.word : concept;
  }

  function makeLanguage(rng, opts) {
    const consonants = rng.sample(CONSONANT_POOL, rng.int(10, 14));
    const vowels = rng.sample(VOWEL_POOL, rng.int(4, 6));

    /* Clusters are kept to real speech sounds — and only sounds that are
     * actually in this tongue's inventory. */
    const onsetClusters = ONSET_CLUSTERS.filter((cl) => [...cl].every((ch) => consonants.includes(ch)));
    const codaClusters = CODA_CLUSTERS.filter((cl) => [...cl].every((ch) => consonants.includes(ch)));

    /* Four syllable templates; always keep one pure CV and one that can end
     * in a consonant so words have a bit of bite. */
    const templates = rng.shuffle(TEMPLATE_POOL).slice(0, 4);
    if (!templates.includes("CV")) templates[0] = "CV";
    if (!templates.some((t) => /C$/.test(t))) templates[1] = rng.pick(["CVC", "CVCC", "CCVC"]);

    function clusterOr(r, pool, prev) {
      /* Prefer a licensed cluster from the pool; if the pool is empty (the
       * tongue lacks the letters for any), fall back to two single
       * consonants. Never repeats the previous sound. */
      let cl = null;
      for (let guard = 0; guard < 8 && cl === null; guard++) {
        if (pool.length) {
          cl = r.pick(pool);
        } else {
          let a = r.pick(consonants);
          let b = r.pick(consonants);
          let g = 0;
          while (b === a && g++ < 8) b = r.pick(consonants);
          cl = a + b;
        }
        if (cl === prev) cl = null;
      }
      return cl;
    }

    /* One syllable from the template set. Neighbouring identical sounds are
     * avoided so words roll off the tongue. */
    function syllable(r) {
      const tmpl = r.pick(templates);
      let out = "";
      let prevC = null;
      let prevV = null;
      for (let i = 0; i < tmpl.length; i++) {
        const ch = tmpl[i];
        if (ch === "C") {
          const paired = tmpl[i + 1] === "C";
          if (paired && i === 0) {
            /* Onset cluster at the start of the syllable. */
            const cl = clusterOr(r, onsetClusters, prevC);
            out += cl;
            prevC = cl;
            i += 1;
          } else if (paired) {
            /* Coda cluster at the end of the syllable. */
            const cl = clusterOr(r, codaClusters, prevC);
            out += cl;
            prevC = cl;
            i += 1;
          } else {
            let c = r.pick(consonants);
            let guard = 0;
            while (c === prevC && guard++ < 8) c = r.pick(consonants);
            out += c;
            prevC = c;
          }
        } else {
          let v = r.pick(vowels);
          let guard = 0;
          while (v === prevV && guard++ < 8) v = r.pick(vowels);
          out += v;
          prevV = v;
        }
      }
      return out;
    }

    function wordParts(r, minSyl, maxSyl) {
      const n = r.int(minSyl || 1, maxSyl || 3);
      const syllablesOut = [];
      let w = "";
      for (let i = 0; i < n; i++) {
        let s = syllable(r);
        let guard = 0;
        while (w.endsWith(s) && guard++ < 6) s = syllable(r);
        w += s;
        syllablesOut.push(s);
      }
      return { word: w, syllables: syllablesOut };
    }

    /* One word per concept, each from its own sub-stream so the vocabulary
     * never depends on the order concepts are generated in. */
    const used = new Set();
    const words = CONCEPTS.map((c) => {
      const stream = rng.salt("vocab:" + c.word);
      let parts = null;
      for (let attempt = 0; attempt < 10; attempt++) {
        parts = wordParts(stream.salt("a" + attempt), 2, 3);
        if (!used.has(parts.word)) break;
      }
      used.add(parts.word);
      return {
        concept: c.word,
        category: c.category,
        word: parts.word,
        syllables: parts.syllables,
      };
    });

    /* Endonym: the language names itself after its own people or a word it
     * holds dear. */
    const lookup = {};
    for (const w of words) lookup[w.concept] = w.word;
    const say = (concept) => lookup[concept] || concept;
    const name = capitalize(
      rng.pick([
        "the tongue of the " + say("people"),
        "the speech of the " + say("people"),
        "the " + say("star") + " voice",
        "the " + say("house") + " speech",
      ])
    );

    /* Plurals are not English: the tongue makes its own. */
    const plural = rng.pick(["s", "en", "a", "im", "on", "li"]);

    return {
      name,
      consonants,
      vowels,
      templates,
      plural,
      words,
      /* A word straight from the tongue's own rules (used for proper nouns). */
      randomWord: (r, minSyl, maxSyl) => wordParts(r, minSyl || 1, maxSyl || 3).word,
    };
  }

  return { CONCEPTS, capitalize, wordFor, makeLanguage };
}));
