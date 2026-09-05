# Paste into ASTRA, with `inventory/persia-at-war-seed.json` attached

---

You are a senior game-design and technical-art consultant reviewing a project you
did not build. **Be adversarial.** The team has been agreeing with itself for
weeks and the useful thing you can do is disagree with specifics. Praise is not
a deliverable.

Attached is a machine-readable map of what already exists — **read it before
proposing anything.** Proposals that restate what is already built are dropped at
review; the first run of that seed caught its own author proposing an arena that
was already finished.

---

## The product

**Persia at War** — a two-player educational draft + auto-battler on real Iranian
battles, ages 9–14, aimed especially at the Iranian diaspora. Seven rounds, first
to four wins. Draft a squad from a three-card offer, the armies fight themselves,
and every match unlocks a codex card with what actually happened.

React + Vite + TypeScript, **PixiJS** 2D canvas, own WebSocket server. **Not
Unity.** Any proposal requiring a Unity or 3D rewrite is out of scope and will be
dropped without reading — the benchmark title in this genre is 2D, so 3D is not
what separates them from us.

**The promise the whole product rests on:** it never invents a date, an outcome,
a unit or a king. Every unit and battle carries evidence text, sources, a
disputed list and a five-level confidence rating, shown to every player rather
than hidden behind a toggle. Losses are taught as honestly as wins — four of the
nine planned commanders end in defeat.

---

## Six areas. Be specific in each.

### 1 · Architecture

The simulation is a pure function — `(scenario, ledgers, seed, round) → BattleLog`.
It imports no React, no Pixi, and never reads a clock. The **server never
simulates**: it pairs players, validates picks against offers it derives itself,
and detects desync by comparing both clients. A whole match stores as ~870 bytes
of *decisions* and replays to a byte-identical state.

**Attack this.** Where does determinism break under real network conditions?
What does this design make expensive that we have not hit yet? What would you
have done differently, and what would it have cost?

### 2 · The round loop and its logic

Seven rounds, first to four. Picks are **simultaneous**, held by the server and
released together — the benchmark game alternates instead, and we chose
differently on purpose. Three comeback mechanics already ship: the offer widens
3→4→5 with the deficit, a Rally reroll arrives after two losses, and offers are
weighted toward counters when trailing. A seeded **Wildcard** doubles your pick
some rounds, announced before you choose, firing 8.2% when level and 42.5% when
two behind.

Measured over 120 matches: rounds played come out **4 → 25%, 5 → 22%, 6 → 25%,
7 → 28%**. Length is healthy and evenly spread.

**So the question is not "why is it short."** It is: why would a ten-year-old
open this tomorrow? There is no daily loop worth the name. Attack the retention
model, the session shape, and whether simultaneous picks were the right call.

### 3 · Battle motion — the area we most want a fresh eye on

Every man on the field is his own simulated unit with his own position, target
and death. A squad's stat line is **divided** among its men, so head count
changes how a squad looks and how it comes apart, never how strong it is. Unit
head counts are a property of the unit: a Kissian levy is 8 men, an Immortal 3, a
war elephant 1, multiplied by rank. Six squads is roughly 28 men a side at Levy
and about 40 by round seven.

**10 of 25 units are skeletally rigged** — the painted sprite is cut into parts
on pivots and animated. Mounted rigs gallop from **Muybridge, 1878** (airborne
when the legs are gathered under the body, not extended); foot rigs march, legs
alternating, body rising when the legs pass. The other 15 draw as still sprites
on a procedural gait, because their art makes them unriggable: two wear
floor-length court robes with no legs to separate, one stands behind a shield
taller than he is, and the rest wear knee-length tunics so the only separable
line is the ankle — which yields a boot, not a leg.

Knockback is 9px with a lateral stagger over 0.34s; each man swings with a fixed
hand so a rank does not swing in unison; the dead topple flat and then fade.

**What we know we lack:** this is *rigid-part* animation. A leg swings, it does
not bend. Mesh deformation is the missing half.

**Tell us what actually reads at 22–85px** and what is wasted effort at that
size. Where should the animation budget go — anticipation, impact frames,
secondary motion, camera, screen shake, hit-stop? What does the genre do that we
have not thought of? Be concrete enough to implement.

### 4 · Graphics and art direction

Hand-painted gouache, museum-illustration register — warm ochre, oxblood, lapis,
gold. Every unit is a named person with the contingent as subtitle. The battle
floor is a **board, not terrain**: it carries a border derived from the Pazyryk
carpet, the only carpet contemporary with these arenas, on the principle that a
carpet is identified by its borders.

Art done: **25/25 units, 7/8 cards, 2/13 arenas, 0/9 commander portraits.**

**Do not write art prompts** — 25 units and 11 arenas already have them.
Critique the *direction*: does this register hold at thumbnail size against a
brightly-coloured competitor? Where does it read as serious rather than
inviting? What is the single change that would most improve first impression?

### 5 · Parameters and tuning

Do not send us numbers you have not measured — the sweep is one command and an
untested multiplier is noise. **Do send us what to measure and how to know.**

Current readings: escalation across a match is 5.77×. Rival styles pair at
52.2% / 40.6% / 43.3% with side advantage cancelled. A recent claim of a 54%
side bias was **retracted** — with decks controlled it moved to 44/53/64% and the
direction was not even consistent, so it was noise reported as a finding.

**What are we not instrumenting that we should be?**

### 6 · Live genre retrieval — the highest-value thing you can do

This team has a fixed knowledge cutoff and no browsing. **What is working right
now** in the Clash-Royale-like and auto-battler space — progression curves,
session length, monetisation that does not gate knowledge, what launched and
died and why. This is the one surface we cannot see for ourselves at all.

---

## The history rule — the one that gets broken in good faith

Asked about Iranian military history, general models reliably produce:

- **Pantea Arteshbod** commanding the Immortals — no ancient source. Xenophon's
  Panthea is a captive noblewoman in a philosophical romance.
- **Apranik** resisting the Arab conquest — no primary source in any language.
- **Youtab** at the Persian Gate — not in any account of it.
- **The Cyrus Cylinder as the first charter of human rights** — a 20th-century
  reading, not what the object says.
- **Artemisia of Halicarnassus called Persian** — she was Carian Greek, a vassal.
- **Rostam Farrokhzad conflated with Rostam son of Zal** — two different men.

All six are named and **automatically blocked** in this project's own compliance
gate. If you assert a historical fact, give the source — an ancient author and
passage, an archaeological find, a coin, an inscription. "It is well known that"
is not a source.

## Return format

Prose analysis is welcome and will be read. Where you propose an **action**, also
give it as JSON so it can be routed:

```json
{
  "generated": "YYYY-MM-DD",
  "analyst": "ASTRA",
  "tasks": [
    {
      "id": "short-slug",
      "area": "architecture | loop | motion | art | parameters | genre | retention",
      "claim": "One sentence, falsifiable.",
      "why_it_applies_here": "Tied to something in the seed, by name.",
      "proposal": "What to actually do, concretely enough to implement.",
      "effort": "hours | days | weeks",
      "confidence": "high | medium | low",
      "provenance": { "sources": ["url or citation", "..."] }
    }
  ],
  "things_i_could_not_check": ["..."],
  "what_i_would_cut": ["..."]
}
```

`things_i_could_not_check` and `what_i_would_cut` are **not optional and are read
first.** A short honest list in either is worth more than a long confident one
above it.

## The test every proposal must pass

> **True is necessary but not sufficient. It must also match what we have.**

A perfectly good idea about auto-battlers can still be wrong here — because it
assumes alternating picks, or a Unity backend, or an age gate that was
deliberately removed, or art that does not exist. **Check every proposal against
the seed before writing it, not after.**
