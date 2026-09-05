# Persia at War — production state

*Single source of truth for picking this up cold. Updated 5 Sep 2026.*

## What it is

A standalone educational draft + auto-battler on real Iranian battles, ages
9–14, aimed especially at the Iranian diaspora. **Not a Boutimar product.**
React 19 + Vite 7 + TS 5.7, PixiJS v8 battle canvas, Zustand 5. Node 24 type
stripping — the socket server loads `src/sim/roundCore.ts` and
`src/game/playerNames.ts` verbatim, so those need explicit `.ts` import
extensions.

**249 tests, tsc clean.** `npx vitest run` · `npx tsc --noEmit`.

## The rules that are not negotiable

- **Never invent a date, an outcome, a unit, or a king.** If the data is not
  there, the game says it is not there.
- **Teach losses as honestly as wins.** Four of nine commanders end in defeat.
- **«خلیج فارس» / Persian Gulf. Never "Arabian Gulf".**
- No modern Iranian wars in the core. No gore. No ethnic caricature. No modern
  political reading in either direction. **Medes must not be villains.**
- **Apranik is the test case.** Four famous "Persian women warriors" have no
  ancient source. The game does not carry them, and the same standard applies to
  our own art — see `DESIGN-WOMEN.md`.

## Built and working

| | state |
|---|---|
| Deterministic sim | `(scenario, ledgers, seed, round) → BattleLog`. `sim/` imports no React, no Pixi, never reads a clock |
| Online play | Server pairs, validates picks against its own derived offers, detects desync from both clients. **The server never simulates.** |
| Recorder | 867 bytes/match, byte-identical replay, honest `recorded:false` when it falls back |
| Progression | Trophies, arenas, card levels, coins |
| Two modes | **THE CHRONICLE** (14 missions) and **BATTLE** (first-to-4-of-7). Same engine; `winsNeeded` is per-match |
| Rival styles | massing / drilling / planning, measured over 200-match sweeps |
| Escalation | accelerating curve, 4.52× → 5.38×, zero regressions |
| **Unit names** | all 25 are people; `contingent` carries the troop type; `SHORT_NAME` deleted |

**Art in hand:** 25/25 units, 7/8 cards, 4/13 arenas.

## Outstanding — art

| what | count | prompts ready? |
|---|---|---|
| **Zarina** (regenerate as a woman) | 1 | **yes** — `ART-PROMPTS-UNITS.md` §4 |
| Arenas | 9 | yes — `ART-PROMPTS-ARENAS.md` |
| Commander portraits | 9 | yes — `ART-PROMPTS-COMMANDERS.md` |
| Capital / kings / missions | 23 | no |
| `loosed-rein` card | 1 | rejected once — filled its own frame, so the flood fill had nothing to bite |

**Pipeline:** Midjourney for the painterly pass, then Nano Banana via Gemini for
consistency and fixes. Then `tools/spriteprep.py`, which keeps the **single
largest connected component** — anything not physically touching the body is
silently deleted, which is how the Wheeling Line emblem lost its shields.

## Outstanding — design agreed, nothing built

- **v0.3 commander layer.** Nine commanders, kits written, campaigns sketched.
  Only Cyrus and Astyages exist in code. **36 pairings × both sides = 72 sweeps.**
- **The Anjoman** — انجمن فرزانگان. Giants of science and poetry as powers, each
  derived from actual work. The player visits, not the commander, which is what
  makes the anachronism honest.
- **Festivals** as live-ops. Client-computable, so no server needed for the
  trigger — but "leaves a mark" needs accounts, and there are none.
- **Women** across three tiers — commanders (Artemisia, Purandokht), Anjoman
  (Mirzakhani first), spells (Scheherazade, Gordafarid).
- **Unit appeal pass** — eye contact, one feature pushed 30%, four age bands.

## Blocked, and on what

- **Audio** — SUNO.
- **Specialist historical review** — a historian. Nothing here has had one.
- **Ismail's campaign** — `musketeer` and `artillery` exist as types with no
  data, and losing to gunpowder is his entire teaching point.
- **Persistence beyond localStorage** — one key, one browser.
- **Capacitor packaging** for M7.

## Traps that have already cost time

- **The Browser pane reports `hidden` during JS execution, so rAF pauses and
  animations freeze.** I once diagnosed a bug that was entirely my harness.
  To verify motion: lengthen the animation to 20s, photograph, restore.
- **Framer-motion writes inline `transform`.** A CSS transform on the same
  element loses silently.
- **`git add -A` from the parent directory sweeps embedded repos.** Add narrowly.
- **The rival harness must play both sides.** Measured one way, the same matchup
  reads 34% or 66% purely by alphabetical order.
- **iranicaonline.org 403s automated fetches.**
- **The socket server does not hot-reload.**
- **Never infer "shipped" from "edited."** Diff against what is actually running.

## Document map

| file | what is in it |
|---|---|
| `../DECISIONS.md` | **read first** — repo root, not docs/. Several decisions were reversed on review |
| `../README.md`, `../TESTING.md`, `../DEPLOY.md` | repo root |
| `CONCEPT-v0.2.md` | the core design |
| `DESIGN-v0.3-COMMANDERS.md` | the commander turn, and what the ninth costs |
| `COMMANDER-ROSTER.md` | the nine, with kits and campaigns |
| `DESIGN-ANJOMAN.md` | giants, powers, festivals, monetisation line |
| `DESIGN-WOMEN.md` | attested vs invented; singers; Esther; Shahnameh; modern |
| `DESIGN-UNIT-APPEAL.md` | why the units are not characters yet |
| `ART-PROMPTS-*.md` | units (25), arenas (11), commanders (9) |
| `ART-BRIEF.md` | house style |
