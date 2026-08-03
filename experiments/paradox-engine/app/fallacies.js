/* fallacies.js — the Fallacy Foundry: a local, heuristic pattern library
 * that flags suspicious argument moves in pasted text.
 *
 * It is deliberately NOT a judge: it finds the *shapes* of classic
 * fallacies — cue phrases, loaded wording, argument skeletons — and lets
 * you decide. Everything runs in the browser; pasted text never leaves
 * the page.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else {
    root.ParadoxEngine = root.ParadoxEngine || {};
    root.ParadoxEngine.fallacies = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var FALLACIES = [
    {
      id: "ad-populum",
      name: "Appeal to popularity",
      patterns: [
        /everyone (knows|agrees|says|thinks|does)/gi,
        /most people (believe|think|say|agree)/gi,
        /it'?s common knowledge/gi,
        /popular opinion (says|holds)/gi,
        /everybody (does|knows|says)/gi,
        /no one (thinks|believes|doubts)/gi
      ],
      note: "Popularity is not evidence: how many people believe a thing says nothing about whether it is true."
    },
    {
      id: "slippery-slope",
      name: "Slippery slope",
      patterns: [
        /if we (allow|let|legalize|ban|give|accept) [^.!?\n]{0,50}?(then|next|soon)\b/gi,
        /next thing you know/gi,
        /it starts with/gi,
        /before long,?/gi,
        /first they (come|take|ban|outlaw)/gi
      ],
      note: "One step is treated as inevitably leading to a chain of ever-worse steps — with no evidence for the chain."
    },
    {
      id: "false-dilemma",
      name: "False dilemma",
      patterns: [
        /either ([\w'\u2019]+(?: [\w'\u2019]+){0,4}) or/gi,
        /there are (only|exactly) two (options|choices|sides)/gi,
        /you'?re either with us or/gi,
        /the only (option|choice|alternative|answer) is/gi,
        /(all or nothing|my way or the highway)/gi,
        /no in-?between/gi
      ],
      note: "Only two options are presented when more exist — check whether a third way was quietly removed."
    },
    {
      id: "ad-hominem",
      name: "Ad hominem",
      patterns: [
        /you'?re just (saying|bitter|jealous|biased|angry)/gi,
        /you (only )?think that because/gi,
        /of course [\w'\u2019 ]+ would say/gi,
        /[\w'\u2019 ]+ has an agenda/gi,
        /don'?t (trust|listen to|believe) [\w'\u2019 ]+[,.]? (he|she|they)'?s/gi,
        /[\w'\u2019 ]+ is (a |an )?(corrupt|fraud|liar|hypocrite|partisan)/gi
      ],
      note: "The person is attacked instead of the argument — a bad character does not make a claim false."
    },
    {
      id: "hasty-generalization",
      name: "Hasty generalization",
      patterns: [
        /\b(always|never)\b/gi,
        /\bevery (single )?[\w']+/gi,
        /\ball [\w'\u2019 ]+ (are|do|is)\b/gi,
        /\bno (one|body) ever/gi
      ],
      note: "A universal claim from a small sample — check how many cases actually back it up."
    },
    {
      id: "appeal-to-authority",
      name: "Appeal to authority",
      patterns: [
        /experts (agree|say|believe|warn)/gi,
        /scientists (say|agree|have proven|warn)/gi,
        /doctors (say|recommend|warn)/gi,
        /studies (show|prove|say|suggest)/gi,
        /research (shows|proves|says|suggests)/gi,
        /the (government|academy|institute|board) (says|has proven|concluded)/gi,
        /[A-Z][a-z]+ (University|Institute|College) (study|research|found|proved)/gi
      ],
      note: "An appeal to an unnamed authority — legitimate appeals name their source and check it applies."
    },
    {
      id: "loaded-language",
      name: "Loaded language",
      patterns: [
        /\b(disgraceful|outrageous|ridiculous|absurd|crazy|stupid|corrupt|evil|fraudulent|disgusting|pathetic|treasonous)\b/gi
      ],
      note: "Emotionally charged wording can load the conclusion before the argument starts."
    },
    {
      id: "straw-man",
      name: "Straw man",
      patterns: [
        /what you'?re (really )?saying is/gi,
        /so you think/gi,
        /you (just|basically) (want|think|believe)/gi,
        /in other words,? you/gi,
        /your (real|true|actual) argument is/gi,
        /[\w'\u2019 ]+ wants (everyone|people) to/gi
      ],
      note: "The opponent's position is restated as an easier-to-attack version — check it is what they actually said."
    },
    {
      id: "false-cause",
      name: "False cause",
      patterns: [
        /because [^.,;:!?]{0,60} happened,? (then )?[^.,;:!?]{0,60}(therefore|so|which is why|that'?s why)/gi,
        /correlation (proves|means) causation/gi
      ],
      note: "Sequence is treated as causation — X happening before Y does not make X the cause of Y."
    },
    {
      id: "appeal-to-emotion",
      name: "Appeal to emotion",
      patterns: [
        /think of the children/gi,
        /imagine if it (happened|were) to (your|our) (family|child|mother|father|children)/gi,
        /this could happen to you/gi,
        /if you don'?t (do|support|vote|act)[^.,;:!?]{0,60}(will|then|next)/gi
      ],
      note: "Fear or pity is doing the work that evidence should do — the feeling is real, the link still needs proof."
    },
    {
      id: "appeal-to-ignorance",
      name: "Appeal to ignorance",
      patterns: [
        /you can'?t (prove|disprove) (it|that|this)/gi,
        /no one has (ever )?(shown|proven|disproven|disproved)/gi,
        /there'?s no evidence (against|for|that)/gi,
        /can'?t (be )?proven (wrong|right|false|true)/gi
      ],
      note: "Lack of disproof is treated as proof — the absence of evidence is not evidence of absence."
    }
  ];

  /* Stop words used by the circularity pass (kept deliberately small —
   * only the words that would flood keyword overlap). */
  var STOP = new Set(("the and that this with from have has had will would should could can they them their " +
    "there these those then than just very really because what when where which while who whom whose your you " +
    "are was were been being is its not but for all any some more most other such only own same so too also " +
    "how why he she him her his hers we our us it").split(" "));

  function keywords(text) {
    return text.toLowerCase()
      .replace(/[^a-z0-9'\u2019 ]/g, " ")
      .split(/\s+/)
      .filter(function (w) { return w.length >= 4 && !STOP.has(w); });
  }

  /* Circular reasoning can't be caught by a phrase list — it lives in the
   * shape of a sentence: the same key terms on both sides of a "because". */
  function circularPass(text) {
    var hits = [];
    var m;
    var sentenceRe = /[^.!?]+[.!?]+/g;
    while ((m = sentenceRe.exec(text)) !== null) {
      var sentence = m[0].trim();
      var bc = sentence.toLowerCase().indexOf("because");
      if (bc === -1) continue;
      var before = keywords(sentence.slice(0, bc));
      var after = keywords(sentence.slice(bc + "because".length));
      var smaller = Math.min(before.length, after.length);
      if (smaller < 2) continue;
      var overlap = before.filter(function (k) { return after.indexOf(k) !== -1; }).length;
      if (overlap / smaller >= 0.5) {
        hits.push({
          id: "circular-reasoning",
          name: "Circular reasoning",
          index: m.index,
          length: sentence.length,
          phrase: sentence,
          note: "The claim and its justification share the same key terms — the conclusion is restating its own premise."
        });
      }
    }
    return hits;
  }

  /* Scan text and return every suspected fallacy hit, in text order. */
  function scan(text) {
    var hits = [];
    FALLACIES.forEach(function (f) {
      f.patterns.forEach(function (re) {
        var m;
        while ((m = re.exec(text)) !== null) {
          hits.push({
            id: f.id,
            name: f.name,
            index: m.index,
            length: m[0].length,
            phrase: m[0],
            note: f.note
          });
          if (re.lastIndex === m.index) re.lastIndex++;
        }
        re.lastIndex = 0;
      });
    });
    circularPass(text).forEach(function (h) { hits.push(h); });
    hits.sort(function (a, b) { return a.index - b.index; });
    return hits;
  }

  return {
    FALLACIES: FALLACIES,
    scan: scan,
    circularPass: circularPass
  };
}));
