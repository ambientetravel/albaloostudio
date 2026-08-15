# Concept v0.2 — audit and specification

Response to `iranian_history_battle_game_concept_v0_1.md` §19. Twelve deliverables,
audit first.

**Status of the ask.** v0.1 §19 says "do not begin production implementation yet."
That instruction assumed a green field. It is not one — there is a working build with
a deterministic simulation, verified online lockstep, 13 arenas, 25 researched units
and 75 passing tests. So this document does two things: it answers §19 as a design
response, and it marks each item **BUILT**, **CHANGES**, or **NEW** against what
exists. Nothing in the existing game has been torn out on the strength of this
document alone.

**Engine.** v0.1 §19 assumes Unity/C# "unless a better engine is strongly justified."
The justification exists and is not a preference:

| v0.1 §17 technology requirement | Status today |
|---|---|
| Deterministic combat simulation | Built. Same seed + same decisions → byte-identical logs, verified across two live clients. |
| Decision providers (bot / recorded / live) | Built for human, bot and live network. |
| Server-controlled seeds and match results | Built. The server owns the seed and the arena and never simulates. |
| Replay log with seed, version, ordered decisions | Built. |
| Remote balance configuration | Content is JSON; balance constants are exported and read by the rules screen. |

Rewriting in Unity discards a proven deterministic core to gain nothing the concept
asks for. **Recommendation: stay on TypeScript. Requires product-owner sign-off.**

---

## 1. Contradiction and risk audit

Fourteen findings. Six are material.

### 1.1 — MATERIAL — "four to six minutes" is not what first-to-4 produces

v0.1 §6.1 gives per-round timings; §5.2 and §18 assert a four-to-six-minute match.
Working it through:

Round = draft 8–12s + placement 5–8s + combat 20–30s + transition 3–5s = **36–55s**.

First-to-4 over max 7 rounds, evenly matched players:

| Rounds | Probability | Length at 45s/round |
|---|---|---|
| 4 (a sweep) | 12.5% | 3:00 |
| 5 | 25% | 3:45 |
| 6 | 31.25% | 4:30 |
| 7 | 31.25% | 5:15 |

Mean 5.81 rounds ≈ **4:22**. The mean lands in the stated window, but **37.5% of
matches end in four or five rounds**, i.e. under four minutes. §18's acceptance test
"a match usually finishes in four to six minutes" would fail on more than a third of
matches while the design is working correctly.

**Resolution.** Scale combat length with army size, which happens naturally — round 1
is one squad per side, round 7 is seven. Budget combat at 12s in round 1 rising to
35s in round 7. Then restate the target honestly as **3:00–6:00, mean 4:30**, and
rewrite the §18 criterion to "90% of matches finish between 3 and 6.5 minutes."

### 1.2 — MATERIAL — the Army Ledger makes rounds near-symmetric, and that is a snowball risk in disguise

v0.1 §6.2 has both players draft every round regardless of who won. So after round 3
both armies contain exactly three cards. The only asymmetry is the score.

That is the opposite of a snowball in resources — and it creates a worse problem.
If player A's round-1 composition beats B's, and both keep drafting from the same
kind of pool, **A tends to keep winning for compositional reasons, not luck**. A 4–0
is not a rare blowout; it is the expected result whenever one player drafts a
counter the other cannot answer. The comeback system in §8 (one extra card, one
reroll) is the only counterweight and it is weak.

**Resolution — three changes, all visible to the player:**

1. **The round loser drafts second and sees the winner's pick.** Information as
   compensation, not power. Currently v0.1 does not say who drafts first.
2. **Offers are weighted toward counters of what the opponent already fields.** Not
   guaranteed — v0.1 §8 correctly forbids "a guaranteed perfect counter" — but
   weighted. A player being beaten by cavalry should see more spears than the base
   rate.
3. **Cap tier stacking**: a unit may not exceed Tier II before round 4, or Tier III
   before round 6. Stops an early lead compounding into an unanswerable Elite squad.

This needs playtesting before it is trusted. Flagged as the single largest design
risk in v0.1.

### 1.3 — MATERIAL — two mechanisms do the same job: duplicate-merge and Upgrade cards

§6.2 example: "Round 3: choose Archer again — Archer becomes Tier II."
§6.4: "**Upgrade:** improves a unit already in the Army Ledger."

Both raise the power of an existing squad. If both exist, the Upgrade card is a
worse duplicate and players will learn to ignore one.

**Resolution — split them cleanly along an axis the player can feel:**

- **Duplicate unit card → tier up.** Numbers: more men, more HP, more damage. Levy →
  Trained → Veteran → Elite.
- **Upgrade card → a trait, never a tier.** Behaviour: *Ready Volley* (archers fire
  before contact), *Locked Shields* (spears resist cavalry, lose pursuit). Sideways,
  not upward.

Then §6.4's requirement that the card explain a consequence rather than a percentage
works for both.

### 1.4 — MATERIAL — the deck-versus-draft question is still unresolved

§5.2 has the player bring "approximately eight eligible unit and doctrine cards."
§6.1 has them choose one of three each round. v0.1 never says where the three come
from.

- If offers are drawn **from your eight**, then over seven rounds you see nearly your
  whole deck. Drafting becomes ordering, not choosing, and deck-building is the real
  game. That contradicts §18's success criterion about drafting being the thing new
  users must understand.
- If offers are drawn **from a global pool**, the eight-card deck does nothing and
  §5.2 is decoration.

**Resolution.** The deck is the **seed pool, not the offer pool**. Each round the
three offers are composed as: one card drawn from your deck, one tier-up or Upgrade
generated from what is already in your Ledger, and one wildcard drawn from the arena
pool. Your deck shapes the match without determining it, and every offer stays
legible. This has been an open question in this project since the first build; it is
now answered.

### 1.5 — MATERIAL — the finished Pasargadae is standing behind the battle that preceded it

§3.3 forbids the completed palace-and-garden complex appearing behind Cyrus during the
revolt. **The current build does exactly this**, by a route §3.3 did not anticipate:

- the scenario `pasargadae-550` is a 550 BCE battle named "Pasargadae";
- arena 6 is the built capital, `c. 546–530 BCE`, art-noted "isolated stone pavilions…
  the plain gabled tomb on its stepped plinth";
- **any scenario can be played at any arena**, so the 550 revolt is routinely fought
  in front of a capital that did not yet exist, and in front of Cyrus's tomb.

There is a second problem in the naming. That the battle happened *at* Pasargadae
comes from Strabo, five centuries later. Our own arena entry already says so. Calling
the scenario "Pasargadae" asserts more than the evidence carries.

**Resolution — two edits, both small:**

1. Rename the scenario to **"The Plain before Pasargadae"**, site "Murghab plain,
   Fars", matching v0.1 §11's own mission name, and add the Strabo attribution to its
   disputed list.
2. State in the UI that **an arena is a venue, not the battle's location** — it is
   the ladder rung you are competing at. Otherwise every scenario/arena pair is a
   potential anachronism: a 550 BCE revolt at Persepolis (begun 518 BCE) is the same
   error wearing different clothes.

### 1.6 — MATERIAL — purchasable commanders cannot be normalised the way stats can

§7 makes commanders change strategy. §16 lets purchases unlock them faster. §9.2
forbids a bought commander being "strictly better."

Stat normalisation solves *strictly better*. It does not solve *more options*. In a
counter-based game, owning eight commanders against someone's two is a real
advantage even when every commander is individually balanced, because you pick the
one that answers their deck.

**Resolution.** Ranked draws from a **rotating free roster plus what you own** — the
MOBA solution, well understood by players. Rotation must be large enough that no
ranked player is ever choosing from fewer than, say, six. Cosmetics and campaign
content carry monetisation; commander access does not.

### 1.7 — the Rally reroll may arrive after it can matter

§8 grants a reroll "after losing two consecutive rounds." At 0–2 in a first-to-4 you
must take four of the remaining five. The reroll is granted at the point where it is
least likely to change the result, and §8 does not say whether it re-triggers at
0–3, or after 1–3, or whether unused rerolls bank.

**Resolution.** Trigger on **score deficit, not consecutive losses** — the deficit is
what the player actually feels. See §3 below for three complete alternatives.

### 1.8 — the choice-space arithmetic is right but oversold

§6.5's `3^7 = 2,187` and `2,187² = 4,782,969` are both correct. But first-to-4 means
most matches run 4–6 rounds, so the realistic per-player figure is `3^4`–`3^6`, i.e.
**81 to 729**, and offers are conditioned on previous picks so the true count is
lower again. The structure is still ample. Quote the honest number; the inflated one
invites a reviewer to catch it.

### 1.9 — the MVP card budget is already exceeded

§17 asks for "approximately 12–16 unit/doctrine cards total." The build has **25
verified units**. These are different objects: the 25 are the Arena ladder pool
spread across 13 rungs; the 12–16 are an MVP deck. Reconcile by declaring the 25 the
Season One pool and drawing the MVP set from it — do not delete researched content to
hit a number written before it existed.

### 1.10 — thirteen arenas and thirteen books are different thirteens

The build has 13 arenas, all Achaemenid places, Anshan → the Persian Gates. §12 has
13 campaign books spanning 550 BCE – 651 CE. Two unrelated ladders of the same length
will be conflated by everyone who reads the marketing.

**Resolution**, which §11 already implies with "Open Arena Season One: Persia and
Media": **arenas are seasonal ladder rungs; books are campaign content.** Season One's
13 arenas are Achaemenid. Book 9 ships with a Parthian season. Say this once, loudly,
in the design doc and in the Scrolls.

### 1.11 — chronology of §12 checks out; one entry needs a caveat

Verified in order: Cyrus c. 550 → Sardis 547/6 → Babylon 539 → Egypt 525 → Darius's
accession 522/1 → Ionian revolt 499–493 and Marathon 490 → Xerxes 480–79 → Alexander
334–330 → Parthian emergence c. 247 → Carrhae 53 BCE → Ardashir 224 CE → Valerian
260 → Qadisiyya c. 636 and Nahavand 642. **Chronologically sound.**

Two notes. **Book 2's date is not as firm as the list implies** — the 547 BCE reading
of the Nabonidus Chronicle for the Lydian campaign is contested, some scholars read
the damaged sign as Urartu rather than Lydia. It belongs in §10 below. And the
330 BCE – 247 BCE Seleucid gap between books 8 and 9 is a deliberate omission, not an
error; say so, or a reviewer will assume the latter.

### 1.12 — one existing arena is ordered by its end date, not its founding

Arena 5 is Babylon (539 BCE), arena 6 Pasargadae (`c. 546–530`, ordered on −530).
Pasargadae was *begun* around 546, before Babylon fell. The ladder is monotonic only
because the later date was used. Defensible — the rung represents the finished
capital — but it should be a stated convention rather than an accident, because the
"never goes backwards in time" test currently enforces it silently.

### 1.13 — "no open chat" must extend to player names

§15 bars open chat at launch and prescribes emotes. Names are user-generated content
shown by one child to another and carry the same duty. Already handled in the build —
normalisation defeating padding, repeats and character substitution, impersonation
refused separately from profanity — but §15 should say so explicitly rather than
leaving names outside the guardrail.

### 1.14 — v0.1 does not carry the project's two standing hard rules

Neither appears in v0.1 and both override it:

- **«خلیج فارس» / Persian Gulf. Never "Arabian Gulf",** on every map, label and codex
  entry, including any relabelled source data.
- **Never invent a rate, date, inclusion, outcome, unit or king.** Where evidence is
  absent, the game says it is absent.

Add both to §15.

---

## 2. Refined seven-round match specification

**CHANGES** — the build currently runs one draft of four units and one battle.

### 2.1 Shape

```
match := commander select → [ round × 4..7 ] → result
round := offer → pick → resolve → score
```

First to **4** round wins. Maximum 7. At 3–3, round 7 is announced as the **Final
Clash** (v0.1 §6.1).

### 2.2 Round budget

Combat scales with the Ledger, per finding 1.1:

| Round | Squads/side | Offer | Placement | Combat | Transition | Round |
|---|---|---|---|---|---|---|
| 1 | 1 | 8s | — | 12s | 4s | 24s |
| 2 | 2 | 9s | 5s | 16s | 4s | 34s |
| 3 | 3 | 10s | 5s | 20s | 4s | 39s |
| 4 | 4 | 10s | 6s | 24s | 4s | 44s |
| 5 | 5 | 11s | 6s | 28s | 4s | 49s |
| 6 | 6 | 11s | 7s | 32s | 4s | 54s |
| 7 | 7 | 12s | 7s | 35s | 6s | 60s |

4–0 sweep 2:21 · 4–3 full match 5:44 · **mean ≈ 4:20**.

Formation placement is off in rounds 1 and 7 for opposite reasons: nothing to place
in round 1, and the Final Clash should not open with a fiddly interaction.

### 2.3 Offer composition (resolves finding 1.4)

Three cards, each from a different source, so no offer is ever three of a kind:

| Slot | Source | Purpose |
|---|---|---|
| A | the player's 8-card warband | the deck matters |
| B | tier-up or Upgrade of something already in the Ledger | reward commitment |
| C | arena pool wildcard, counter-weighted against the opponent's Ledger | keep it live |

Slot C's weighting is capped: a counter-class is at most **2×** its base draw rate
(never guaranteed — v0.1 §8).

Slot B is unavailable in round 1 (empty Ledger); round 1 offers three from slot A.

### 2.4 Ledger and tier caps (resolves 1.2, 1.3)

- Battlefield resets each round; the Ledger persists (§6.2).
- Maximum **6 distinct squads** on the field; a 7th pick must be a tier-up or Upgrade.
  Keeps portrait legible in round 7 (§18).
- Duplicate → tier up. **Tier II from round 3, Tier III from round 5, Tier IV from
  round 7.**
- Upgrade cards grant traits and never a tier.

### 2.5 Draft order

The **loser of the previous round picks second and sees the winner's card** (finding
1.2). Round 1 order is decided by the match seed and shown.

---

## 3. Three comeback systems

All satisfy §8: visible, no hidden damage bonus, no weakening of the leader, no
guaranteed perfect counter.

### A — Widened offer (v0.1 §8 as written, deficit-triggered)

At a deficit of 1, next offer is 4 cards; at 2 or more, 5 cards.

**For:** trivial to explain and to build; already partly in the codebase.
**Against:** more cards is a weak lever when the problem is compositional. A fifth
card you cannot use does not close a 0–3.
**Verdict:** floor, not ceiling. Ship it as the baseline.

### B — Rally reroll (recommended)

A meter fills by 1 per round lost, empties on any win. At 2, the player holds one
**Rally** token: reroll the current offer, once, visibly, with a 3-second animation
both players see.

**For:** agency rather than charity — the player chooses when to spend it. Visible to
the opponent, so it reads as a rule, not a rubber band. Empties on a win, so it
cannot bank into a runaway.
**Against:** a second decision layer in an 8–12 second window; needs its own
onboarding beat.
**Verdict:** **recommended.** Pair with A. Deficit-triggered per finding 1.7, not
consecutive-loss-triggered.

### C — Counter-weighted offers

No new resource. The trailing player's slot C weighting rises from 2× to 3×.

**For:** invisible in the UI but honest in the rules, and it targets the actual
failure mode from finding 1.2 — being beaten by a composition you have no answer to.
**Against:** invisible is the risk. Players who cannot see a comeback system do not
feel hope, which is what §18 asks it to create. And it edges toward the "guaranteed
perfect counter" §8 forbids if the multiplier goes higher.
**Verdict:** use as a **quiet floor beneath A and B**, capped at 3×, and disclose it
in the Scrolls rules page. A rule the player can read is not a hidden rubber band.

**Recommendation: A + B shipped, C at 3× disclosed in the rulebook.**

---

## 4. Card taxonomy and a sixteen-card set

**CHANGES** — units exist; Upgrade and Doctrine are new.

```
Card
├── Unit      → adds a squad, or tiers one up if already present
├── Upgrade   → grants a trait to one squad; never a tier
└── Doctrine  → army-wide behaviour: formation, target priority, morale, terrain
```

Sixteen cards for the MVP, drawn from the 25 already researched (finding 1.9). Tier
names per §6.3: Levy → Trained → Veteran → Royal.

**Units (8)** — all present in the build and verified:

| Card | Class | Role |
|---|---|---|
| Median Spearman | infantry | holds the centre |
| Shield-bearer | infantry | the front rank, the wicker wall |
| Persian Archer | archer | the empire's real weapon |
| Persian Cavalry | cavalry | flank pressure |
| Immortal | heavy infantry | the king's guard |
| Kissian Levy | infantry | cheap body |
| Bactrian Archer | archer | range |
| Saka Horse-archer | horse-archer | refuses contact |

**Upgrades (5)** — NEW, consequence-worded per §6.4:

| Card | Applies to | Reads as |
|---|---|---|
| Ready Volley | archers | "Archers loose before contact, but are caught flat-footed if reached." |
| Locked Shields | infantry | "Spearmen hold against horses. They will not pursue." |
| Long Reach | spear infantry | "Strikes first in a clash. No effect at range." |
| Wheeling Line | cavalry | "Enters from the flank after the lines meet." |
| Loosed Rein | horse-archer | "Gives ground faster while shooting. Slower to close." |

**Doctrines (3)** — NEW, army-wide:

| Card | Reads as |
|---|---|
| The Centre Holds | "The middle stands firm. The wings give ground." |
| Shoot the Horses | "Every archer targets riders first, whatever else is closer." |
| Broken Ground | "Your army fights better in a pass. Worse on open plain." |

Every card keeps its existing `sourceRefs` and confidence label. Upgrades and
Doctrines are gameplay abstractions and must be labelled **Reconstructed for
gameplay** (§3.4) — they are not attested formations with attested names.

---

## 5. Commander kits

**NEW.** Per §7: one passive, one charged order, one doctrine affinity. Strategically
different, not numerically superior (§9.2).

### Cyrus — Coalition

- **Passive · Many Peoples.** Each *distinct* class in your Ledger adds cohesion;
  the army holds longer before breaking. Four classes is a real bonus, four copies of
  one is none.
- **Order · The Line Reforms** (charges over ~20s of combat). Broken squads rally
  once, at reduced strength.
- **Affinity.** Slot C offers lean toward classes he does not yet field.

Plays wide. Punished by a focused counter-comp; rewarded for answering everything.

### Astyages — Royal Muster

- **Passive · The King's Levy.** Round 1 and 2 offers include one Tier-II card
  outright. He starts ahead.
- **Order · Muster Again.** Once per match, immediately tier up one squad, mid-combat.
- **Affinity.** Slot C leans toward what he *already* fields — deeper, not wider.

Plays tall. Strong early, and the tier caps in §2.4 are what stop him running away
with it. If he does not close by round 5 he is fighting Cyrus's wide army with a
narrow one.

**The balance claim, stated as a test rather than an assertion:** across 200 simulated
matches at equal skill, neither commander should exceed a 55% win rate, and each
should beat the other in at least one identifiable band of match length. Untested —
this is a hypothesis, not a result.

### Harpagus — Divided Loyalty (post-MVP)

§7 proposes an information/defection kit. Held back: defection is the most historically
loaded mechanic in Book One and needs its dossier before it is designed.

---

## 6. Simulation and decision-provider architecture

**BUILT** — this section documents what exists and names the two gaps.

```
Match (server-owned)
  ├─ seed            server-generated, never client-supplied
  ├─ arena           min(playerA.arena, playerB.arena)
  └─ rounds[]
       ├─ offers     derived from (seed, round, ledgerA, ledgerB) on BOTH clients
       ├─ decisions  relayed and validated, never trusted
       └─ log        (scenario, ledgers, seed) → deterministic BattleLog
```

The rule that makes this work: **the server never simulates.** It pairs players, owns
the seed, validates that a pick was one of the three the client was actually offered,
and relays. Both clients then run the identical simulation. Cheating a pick fails
validation; cheating a result is impossible because the opponent computes it too.

Decision providers, per §10 — three of four exist:

| Provider | Status |
|---|---|
| `HumanDecisionProvider` | Built |
| `BotDecisionProvider` | Built. Uneven, human-like hesitation; three personalities still to write. |
| `LiveNetworkDecisionProvider` | Built and verified across two clients. |
| `RecordedRivalDecisionProvider` | **Gap.** The replay log carries everything needed; nothing reads it back. |

Second gap: **offers must become a function of both Ledgers** (§2.3 slot C), which
means the offer derivation now depends on match state both clients share. It stays
deterministic — both sides know both Ledgers — but the current pure `(seed, step)`
derivation must be widened to `(seed, round, ledgerA, ledgerB)` **on both the client
and the Node server**, which share that module by design.

---

## 7. Data schema

**CHANGES** — additive. Existing content stays valid.

```ts
type Confidence =            // v0.1 §3.4, replaces the current boolean
  | 'attested'
  | 'probable'
  | 'traditional-account'
  | 'reconstructed-for-gameplay'
  | 'fictional';

interface Card {
  id: string;
  kind: 'unit' | 'upgrade' | 'doctrine';
  name: string;
  blurb: string;                  // 9–11 reading
  blurbOlder: string;             // 12–14 reading
  consequence: string;            // §6.4: what it does, in words, never a %
  confidence: Confidence;
  sourceRefs: string[];
  disputed: string[];
  era: string;
  arena: number;                  // ladder gate
  earliestAttested: number | null;// history gate — outranks the ladder
}

interface UnitCard extends Card {
  kind: 'unit';
  class: UnitClass;
  tiers: [TierStats, TierStats, TierStats, TierStats];  // Levy→Trained→Veteran→Royal
  counters: UnitClass[];
  counteredBy: UnitClass[];
}

interface UpgradeCard extends Card { kind: 'upgrade'; appliesTo: UnitClass[]; trait: TraitId }
interface DoctrineCard extends Card { kind: 'doctrine'; effect: DoctrineId }

interface LedgerEntry { cardId: string; tier: 1|2|3|4; traits: TraitId[] }

interface Commander {
  id: string; name: string;
  passive: { id: string; reads: string };
  order:   { id: string; reads: string; chargeSeconds: number };
  affinity: 'wide' | 'deep';
  confidence: Confidence; sourceRefs: string[]; disputed: string[];
}

interface RoundRecord { round: number; offers: Record<Side, string[]>; picks: Record<Side, string>;
                        rallyUsed: Record<Side, boolean>; winner: Side | 'draw'; ticks: number }

interface MatchReplay {                       // §17: seed, version, ordered decisions
  version: string; seed: number; arena: number; scenario: string;
  commanders: Record<Side, string>;
  warbands: Record<Side, string[]>;           // the 8-card decks
  rounds: RoundRecord[];
  score: Record<Side, number>;
}
```

`Confidence` is the one breaking change. Migration: current `verified: true` → attested
or probable per record (needs the historian pass in §10, not a blanket rewrite);
`verified: false` → reconstructed-for-gameplay. The Scrolls already surfaces `disputed`
and sources, so the label slots into a shipped UI.

---

## 8. Wireframes

Portrait, per §13.1. **The draft moves onto the battlefield** — v0.1 §13.1 says cards
slide up from the bottom, and with seven rounds you must never leave the field.

### Battle screen

```
┌──────────────────────────────┐
│ ◄ Astyages    ●●○○    Cyrus ►│  commander portraits, round score
│        ROUND 4 · 2–1          │
├──────────────────────────────┤
│  ▲ opponent ledger, 4 squads  │  top edge
│                               │
│         [ battlefield ]       │  large, uncluttered; spectators
│         portrait, tall        │  and standards outside the path
│                               │
│  ▼ your ledger, 4 squads      │  bottom edge — yours is nearest you
├──────────────────────────────┤
│ [ORDER ⚡]        speed 1× 2× │  commander order when charged
└──────────────────────────────┘
```

Built already: portrait field, player at the bottom, per-unit motion, arena-coloured
floor. New: score row, ledger banding, order button.

### Draft overlay — over the field, not instead of it

```
│         [ battlefield, dimmed 40% ]         │
│                                             │
│   ┌────────┐  ┌────────┐  ┌────────┐        │
│   │ deck   │  │ tier-up│  │ wild   │        │  slots A · B · C
│   │ Archer │  │ Spear  │  │ Saka   │        │
│   │        │  │  →II   │  │  ⚑     │        │
│   │"fires  │  │"holds  │  │"refuses│        │  consequence, not %
│   │ early" │  │ horses"│  │contact"│        │
│   └────────┘  └────────┘  └────────┘        │
│         [ ⟳ RALLY ]      0:08               │  reroll only when held
```

### Capital screen (§3.3 epilogue)

```
│   PASARGADAE                    │
│   ┌───────────────────────┐     │
│   │  camp → capital art   │     │  evolves with campaign progress
│   └───────────────────────┘     │
│   Gardens ✓  Hall ○  Tomb 🔒    │  cosmetic + narrative only
│   "Book One complete"           │  never a ranked stat
```

---

## 9. Book One — fourteen missions

**NEW.** v0.1 §11's structure, with the corrections from findings 1.5 and 1.11 folded
in. Every mission carries a confidence label; the chapter as a whole is a **dramatic
reconstruction**, and the game says so on entry.

### Chapter One — King of Anshan

| # | Mission | Teaches | Confidence |
|---|---|---|---|
| 1 | The Small Court | interface; pick a commander doctrine | reconstructed |
| 2 | Rally the Households | first Unit draft | reconstructed |
| 3 | Roads of Fars | terrain reading | reconstructed |
| 4 | The Tribal Council | non-battle; shapes the starting warband | reconstructed |
| 5 | Border Warning | first full round-based battle | reconstructed |
| 6 | A Kingdom Divided | cohesion vs speed vs defence | reconstructed |
| 7 | The Refusal | Cyrus rejects Median overlordship | traditional account |

### Chapter Two — The Median War

| # | Mission | Teaches | Confidence |
|---|---|---|---|
| 8 | The First Advance | facing a stronger Ledger | reconstructed |
| 9 | Broken Ground | the pass; the Broken Ground doctrine | reconstructed |
| 10 | Retreat to Persis | **win by surviving, not destroying** | reconstructed |
| 11 | The Camp Holds | protect supply and standards | reconstructed |
| 12 | Divided Loyalties | the defection mechanic | traditional account |
| 13 | The Plain before Pasargadae | formations; final doctrine | traditional account |
| 14 | The Last Stand | Astyages; unlocks Ecbatana + the capital | probable |

Mission 10 is the most important one in the book. A campaign that only ever asks you
to destroy the enemy cannot teach that Cyrus's revolt included retreat, or that
losses are worth understanding — which is the whole premise (§4, and the project's
standing rule that losses are taught as honestly as wins).

Mission 14 is **probable**, not attested: that Astyages was defeated and handed over
by his own army is in the Nabonidus Chronicle, a near-contemporary source. That the
battle happened *at Pasargadae* is Strabo, five centuries later — hence mission 13's
name, and finding 1.5.

**Counter-History** (§4) unlocks on completing the book: replay as Media, labelled
alternate history, with the documented outcome shown at the end.

---

## 10. Claims requiring specialist verification

Nothing below ships as fact until a specialist signs it off.

| # | Claim | Why it is uncertain |
|---|---|---|
| 1 | The 550 BCE battle took place at Pasargadae | Strabo only, c. 5 centuries later. Finding 1.5. |
| 2 | Cyrus's age or "youth" at the revolt | §3.1 — birth date unknown. Do not state an age. |
| 3 | The 547 BCE date for the Lydian campaign | The Nabonidus Chronicle sign is damaged; Urartu is a live reading. Finding 1.11. |
| 4 | Harpagus's role and motive | Herodotus, heavily novelised. Gates the commander kit in §5. |
| 5 | Any named Achaemenid "formation" or drill | Upgrade/Doctrine names are gameplay abstractions. Label reconstructed. |
| 6 | Anshan as Persian rather than Elamite at Cyrus's accession | §3.2 — the transition is contested. |
| 7 | Median army composition c. 550 | Largely inferred from later Persian evidence. |
| 8 | Scythed chariot before c. 401 BCE | Already enforced by the date gate; keep it. |
| 9 | Unit costume and colour | §13.3 — palettes are stylised, not reconstructions. |
| 10 | Cambyses in Egypt | §12 book 4 — the hostile tradition is very hostile. Needs care. |
| 11 | Qadisiyya's date and course | §12 book 13 — sources conflict; conquest was prolonged. |
| 12 | Every museum photograph and modern reconstruction | §13.3 — old subject, modern copyright. Licence review. |

---

## 11. Prototype backlog

Two-week milestones. M1–M3 are the concept; M4–M6 are the campaign.

**M1 — the round loop.** Ledger; rounds; first-to-4; scaled round budget; three-slot
offers; draft overlay on the field. *Done when a 7-round match runs end to end
against a bot with the score reading correctly.*

**M2 — the card system. ✅ DONE.** Upgrade and Doctrine kinds; consequence text;
the `Confidence` migration. (Tiers and tier caps shipped in M1.) Verified: an
Upgrade grants a trait and leaves the rank untouched, a duplicate raises the rank
and leaves the traits untouched, and every one of the eight new cards is measured
doing what its own text says — including its cost. See DECISIONS.md, including
the trait that turned out to promise something the unit already had.

**M3 — commanders and comeback.** Cyrus and Astyages; passives, orders, affinity;
comeback A+B+C. *Done when 200 simulated matches put neither commander above 55%.*

**M4 — campaign frame.** Mission map; setup and "What we know" cards; rewards that
grant breadth not power; capital screen v1.

**M5 — Book One content. ✅ DONE.** All 14 Historical Battle Dossiers, with a
shared book-level evidence base; the "what we know" card after a mission;
Counter-History. Every dossier leads with what must NOT be claimed — including
the Cyrus Cylinder-as-human-rights misreading, barred by name. Counter-History
opens only after the historical path, tracks separately and pays nothing.
Mission 10's survival objective shipped in M4. See DECISIONS.md, including the
four dossiers that had Herodotus filed as contemporary evidence.

**M6 — recorded rivals. ✅ DONE.** Three bot personalities — massing, drilling,
planning — differing in which card KIND they spend a pick on, every pairing
inside 35-65% with the side advantage cancelled. A recorder storing a match as
its decisions (867 bytes for seven rounds, replaying to a byte-identical
`MatchState`). And a recorded rival that drafts a real person's picks, verified
live taking 4 of 4 rounds from a stored tape with its ledger matching that
person's exactly.

Backfill is labelled honestly, and the labelling is the interesting part. The
nameplate says "replaying a real game" only once a round has ACTUALLY come from
the tape, because at the start of a match the game cannot know how much of the
rival will be a person — a recording is a decision sequence, not a script, and
the offer often does not contain the card it wants. The exact figure is stated
on the result screen afterwards, where it can be true. See DECISIONS.md.

---

## 11a. After M6

M1–M6 are complete; the concept defines nothing beyond them. What is left is not
another design milestone but the work of shipping, and most of it is blocked on
something other than code:

**Art.** 39 of 71 pieces outstanding — 11 arenas, 2 commanders, 5 capital, 4
codex figures, 14 mission images, and the one rejected card (`loosed-rein`).
All 25 units and 7 of 8 cards are in. Prompts and the cut-out pipeline exist;
this is generation time, not engineering.

**Audio.** Nothing at all. Blocked on the SUNO tracks.

**Specialist historical review.** Every dossier is marked `drafted`. §10 lists
twelve claims that must not ship as fact without a sign-off. This needs a
historian, not a developer.

**Shipping — M7, started.** No age gate, and that is the decision rather than an
omission. One was built — birth year, three brackets, typed names for adults —
and then removed, because it was the wrong shape for this game. The audience is
nine to fourteen, so the adult path served almost nobody; the bracket was read
for exactly one decision; and §17 rules out chat, clans and subscriptions, so
nothing else would ever read it.

**One profile, one reading.** The `kid`/`older` toggle is gone. It was not a
reading-age feature — 24 of 25 units named a source in the long blurb and 1 of
25 did in the short one, so the toggle was the evidence layer and it defaulted
to off. Both texts are now shown to everyone: the hook on the card, the sourced
paragraph in the codex detail beneath it. The fields are `blurb` and `evidence`
— they were `blurb`/`blurbOlder`, which went on claiming an age split after the
product had stopped making one.

**Nobody types a name.** Every player picks one from a closed set of 144
adjective-noun titles. A gate manages a risk; deleting the free-text field
removes it. There is now no user-generated text anywhere in the product, which
means: one screen fewer before a child can play, no birth year asked, no age
stored even as a bracket, and no profanity list to build or maintain in any
language. The server checks set MEMBERSHIP rather than string shape, so a
modified client cannot put arbitrary text in front of another player at all.

Still open in M7: mobile packaging (Capacitor), account persistence beyond
localStorage, and store compliance paperwork. The moderation list that was on
this list is no longer needed — there is nothing left for it to moderate.
Explicitly out, per §17: live ranked, clans, chat, subscriptions, loot boxes, fantasy
units, the other twelve books, a city builder.

---

## 12. Acceptance tests

Per subsystem. The existing 75 tests stay and are extended.

**Determinism** — same version + seed + ordered decisions → identical log, asserted
byte-for-byte across browser and Node. *Exists; extend to the round loop.*

**Offers** — both clients derive identical offers from `(seed, round, ledgerA,
ledgerB)`; slot C's counter-weighting never exceeds its cap; slot B is absent in
round 1; an offer is never three cards of one kind.

**Ledger** — never exceeds 6 distinct squads; a 7th pick can only tier or upgrade;
tier caps hold at rounds 3/5/7; the battlefield resets but the Ledger does not.

**Match** — ends at exactly 4 wins; never exceeds 7 rounds; 3–3 flags the Final
Clash; a 4–0 completes in under 3 minutes and a 4–3 in under 6:30 (finding 1.1).

**Comeback** — a widened offer only ever appears at a deficit; Rally is granted at
deficit 2 and cleared on a win; Rally is never granted twice unspent; no code path
alters damage based on score. *This last one is a test that greps the simulation for
any score dependency — §8's "no secret damage bonus" enforced mechanically.*

**Content** — no record ships without a confidence label and a source; the date gate
outranks the ladder gate; no unit appears in a scenario predating its earliest
attestation; **no string in the content tree contains "Arabian Gulf"**; every arena's
year is monotonic, with arena 6's end-date convention declared (finding 1.12).

**Online** — the server never simulates; a pick outside the three offered is refused;
the match arena is the lower of the two; a mid-match disconnect resolves without
corrupting either replay.

**Readability** — round 7 with 6 squads a side renders legibly at 375×812 with no
scrolling on any screen. *The no-scroll constraint is already enforced and verified.*

---

## Appendix — what exists, what changes

| Concept area | Status |
|---|---|
| Deterministic sim, server-owned seeds, replay log | **Built** |
| Online lockstep, arena = min of both players | **Built** |
| Portrait battlefield, player at the bottom, per-unit motion | **Built** |
| 13 arenas, 25 verified units, date + ladder gates | **Built** |
| Rules exposed in-game from the enforcing code | **Built** |
| Name moderation | **Built** |
| One draft of 4 → one battle | **Replaced** by the 7-round loop |
| Binary verified/disputed | **Replaced** by 5-level confidence |
| Comeback = widened final pick | **Replaced** by A+B+C |
| Upgrade and Doctrine cards, tiers | **New** |
| Commanders | **New** |
| Chronicle campaign, capital, Counter-History | **New** |
| Recorded-rival provider | **New** |

**Decisions needing the product owner:** the engine (stay on TypeScript);
the deck-as-seed-pool resolution in 1.4; rotating commander access in 1.6; renaming
the 550 scenario in 1.5; and whether "Empires Unbound / Rise of Cyrus" replaces
"Persia at War" as the shipped name.
