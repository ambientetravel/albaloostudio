# Paste this into ASTRA, with `inventory/persia-at-war-seed.json` attached

---

You are acting as an outside analyst on a project you did not build. Attached is
a factual map of what already exists. Read it before proposing anything.

**The project.** *Persia at War* — a standalone educational draft + auto-battler
about real Iranian battles, for ages 9–14, especially the Iranian diaspora. Seven
rounds, first to four. Web stack: React + Vite + TypeScript, PixiJS canvas, own
WebSocket server. **Not Unity.** Anything requiring a Unity rewrite is out of
scope and will be dropped without reading.

**The one rule the whole project rests on.** It never invents a date, an outcome,
a unit or a king. Every unit and battle carries evidence text, sources, a
disputed list, and a five-level confidence rating, shown to every player rather
than hidden behind a toggle. Losses are taught as honestly as wins — four of the
nine planned commanders end in defeat.

## What is genuinely wanted

These are the surfaces the project is blind to, in order of value:

1. **Live genre retrieval.** The team building this has a fixed knowledge cutoff
   and no browsing. What is actually working *right now* in the Clash-Royale-like
   and auto-battler space — progression curves, session length, retention hooks,
   what launched and died and why. This is the single most useful thing you can
   provide, because it is the one thing that cannot be reasoned out from here.
2. **Adversarial critique of the round loop.** Measured: of 60 matches, 42 reached
   round 5 and only **10 reached round 7**. The designed climax happens in about
   one match in six. Why does a ten-year-old stop at round three?
3. **Educational-game conventions for ages 9–14.** Reading load, session length,
   how other history games handle uncertainty without being boring.
4. **Retention and soft launch.** There is no daily loop here worth the name.
   Markets, store category, comparable titles, ASO.

## What will be dropped unread

- **Balance numbers.** Measured with harnesses and 275 tests. An opinion about a
  multiplier that has not run the sweep is noise, and the sweep is one command.
- **Any historical claim you cannot source.** See below — this is the hard one.
- Code review, refactors, test strategy, art prompts, anything needing Unity.
- Anything already listed in the seed as built or decided. The first run of this
  seed caught its own author proposing an arena that was already finished.

## The history rule, stated bluntly because it is the one that gets broken

Asked about Iranian military history, general models reliably produce:

- **Pantea Arteshbod** commanding the Immortals — no ancient source. Xenophon's
  Panthea is a captive noblewoman in a philosophical romance.
- **Apranik** resisting the Arab conquest — no primary source in any language.
- **Youtab** at the Persian Gate — not in any account of it.
- **The Cyrus Cylinder as the first charter of human rights** — a 20th-century
  reading, not what the object says.

All four are already named and banned in the project's own data. **If you assert
a historical fact, give the source: an ancient author and passage, an
archaeological find, a coin, an inscription.** "It is well known that…" is not a
source. A claim with no source is dropped at review, and history questions go to
a historian rather than to either of us.

## Return format

One JSON file. Every task carries `provenance.sources` — an array, and an empty
array means the task is a suggestion rather than a directive.

```json
{
  "generated": "YYYY-MM-DD",
  "analyst": "ASTRA",
  "tasks": [
    {
      "id": "short-slug",
      "area": "genre-retrieval | loop-critique | age-conventions | retention | soft-launch",
      "claim": "One sentence, falsifiable.",
      "why_it_applies_here": "Tied to something in the seed, by name.",
      "proposal": "What to actually do.",
      "confidence": "high | medium | low",
      "provenance": { "sources": ["url or citation", "..."] }
    }
  ],
  "things_i_could_not_check": ["..."]
}
```

`things_i_could_not_check` is not optional and is read first. A short honest list
there is worth more than a long confident one above it.

## The test a proposal has to pass

> **True is necessary but not sufficient. It must also match what we have.**

A perfectly good idea about auto-battlers can still be wrong here — because it
assumes alternating picks (ours are simultaneous), or a Unity backend, or an age
gate that was deliberately removed. Check every proposal against the seed before
writing it, not after.
