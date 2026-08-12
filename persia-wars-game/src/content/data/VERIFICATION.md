# Content verification log

Decision #6: references pass now, historian review before public launch.
Every record in this folder carries `sourceRefs`, and every contested claim
carries a `disputed[]` entry that the game shows the player rather than hides.

> **Note, 11 Aug 2026:** the dataset was converted from bilingual `{ en, fa }`
> pairs to plain English strings on request. No factual content changed in that
> conversion — the Farsi renderings were dropped, the English was untouched.

## Pass 1 — 11 Aug 2026 · Achaemenid vertical slice

Scope: `eras.json` (1), `units.json` (7), `kings.json` (4), `battles.json` (2).

### What was checked and what changed

| Claim as written in RESEARCH-BRIEF.md §6 | Finding | Action |
|---|---|---|
| "Pasargadae / Hyrba, 550 BCE — Cyrus beats Median Astyages → founds empire" | The Nabonidus Chronicle (Nabonidus yr 6) records that Astyages mobilised, **his own troops revolted**, bound him and handed him over; Cyrus then took Ecbatana. A pitched battle at Pasargadae is later Greek tradition — Strabo, 500+ years on, places the victory "among the Pasargadae". | Rewrote the summary around the mutiny. Both readings recorded in `disputed`. |
| Date 550 BCE, given flat | Nabonidus Chronicle → 550; Nabonidus Cylinder of Sippar → 553. | Kept 550 as the headline, recorded the conflict in `disputed` on both the battle and on Cyrus. |
| "Persian Gates, 330 BCE — Ariobarzanes' last stand" | Confirmed. Livius dates it to approximately 20 January 330 BCE. | Kept. |
| Achaemenid signature unit "scythed-chariot" (brief §5 example) | First firm attestation is Cunaxa, **401 BCE**. Xenophon's *Cyropaedia* credits Cyrus the Great with the invention, but it is a didactic romance and the chariots are absent from the Greek campaigns of Darius and Xerxes. | Added `earliestAttested: -401`. The unit is gated out of the Pasargadae pool and the game explains why. |
| — | Achaemenid war elephants: Arrian puts 15 Indian elephants in Darius III's line at Gaugamela, 331 BCE, and among the camp spoils. No source says what they did in the fighting. | Added with `earliestAttested: -331` and a `disputed` note that its in-game strength is a design choice, not a measurement. |
| — | "Immortals": the name reaches us only through Herodotus and his followers. The *anūšiya* ("companions") proposal is discussed but unproven and not universally accepted. No Persian source names the unit. | Recorded in `disputed`. |
| — | "Sparabara": a modern reconstruction from Old Persian *spara*, "shield". The shields, spears and formation are attested; the unit label is modern. | Unit renamed to "Shield-bearer" with the reconstruction flagged in `disputed`. |
| — | Cyrus Cylinder as "first charter of human rights": rejected by specialists. Kuhrt calls the framing an exaggeration; Finkel (British Museum): there were no human rights in antiquity. It follows the Babylonian temple-restoration text tradition. | Recorded in `disputed` on Cyrus. The achievement text describes the object without the modern label. |
| — | Ariobarzanes' sister "Youtab" appears in some popular accounts and in the Wikipedia infobox with no ancient source. | **Omitted entirely.** Not invented, not repeated. |
| — | Ariobarzanes' troop numbers: Arrian's 40,000 infantry / 700 cavalry is described as grossly exaggerated; Iranica suggests 700–2,000. | Both recorded in `disputed`; the game uses neither. |
| — | The shepherd/prisoner who showed Alexander the mountain path mirrors Herodotus's Ephialtes at Thermopylae closely enough that Livius questions it. | Recorded in `disputed`. |

### Sources consulted directly

- Livius — Persian Gate (330 BCE): https://www.livius.org/articles/battle/persian-gate-330-bce/
- Livius — Cyrus the Great: https://www.livius.org/articles/person/cyrus-the-great/
- Livius — Darius III Codomannus: https://www.livius.org/articles/person/darius-iii-codomannus/
- Livius — ABC 7, Nabonidus Chronicle: https://www.livius.org/sources/content/mesopotamian-chronicles-content/abc-7-nabonidus-chronicle/
- Wikipedia — Battle of the Persian Gate, Immortals (Achaemenid Empire), Sparabara, Scythed chariot, Ariobarzanes Satrap of Persis
- Yale Peabody — Irving Finkel on the Cyrus Cylinder: https://peabody.yale.edu/news/finkel_talk

### Known gap in this pass

**Encyclopædia Iranica could not be read directly.** `iranicaonline.org` returns
HTTP 403 to automated fetches, so Iranica article URLs in `sourceRefs` are
recorded as pointers for the human reviewer, not as sources this pass read.
Everything asserted in the data is supported by a source that *was* read
(Livius, Peabody, Wikipedia's cited text). Someone with browser access should
open the Iranica articles during the historian review.

## Pass 2 — 12 Aug 2026 · expanding to 25 units and 16 spells

Scope: 18 new unit cards, 16 spell cards, 13 arenas.

### Units — all 18 grounded in a primary text that was read

The roster was expanded to 25 without inventing anything, by working from
Herodotus' catalogue of Xerxes' army — Book VII, chapters 61–88, in the Godley
translation on Wikisource — plus Cunaxa (401 BCE) and Gaugamela (331 BCE) for
the units that arrive late.

Equipment taken directly from the text, not paraphrased from memory:

| Unit | What Herodotus actually says |
|---|---|
| Median Spearman | Armed as the Persians; turbans not caps; "that fashion of armour is Median, not Persian" |
| Kissian Levy | As the Persians, distinguished only by turbans |
| Assyrian Clubman | Bronze helmets "in an outlandish fashion", linen breastplates, "wooden clubs withal studded with iron" |
| Bactrian Archer | Median-style headgear, native reed bows, short spears |
| Caspian Skirmisher | Cloaks, reed bows of their country, short swords |
| Sagartian Lassoer | No bronze or iron armour, daggers only, ropes of twisted leather with a noose (7.85) |
| Indian Cane-bow Archer | Garments of "tree-wool" (cotton), reed bows, iron-tipped reed arrows |
| Arabian Camel Rider | Girded mantles, long backward-curving bows; camels in the cavalry |
| Paphlagonian Javelineer | Plaited helmets, small shields, short spears, javelins, daggers |
| Thracian Peltast | Fox-skin caps, fawnskin footwear, javelins, small shields, daggers |
| Lydian Hoplite | "Armour was most like to the Greek" |
| Colchian Shieldman | Wooden helmets, small raw-oxhide shields, short spears, swords |
| Armenian Lancer | "Armed like the Phrygians" |
| Ethiopian Bowman | Leopard and lion skins, four-cubit palm-wood bows, stone-tipped arrows, gazelle-horn spears |
| Egyptian Marine | Plaited helmets, concave broad-rimmed shields, boarding spears, great axes, long knives |
| Chorasmian Rider | Armed as the Bactrians; cavalry "equipped as were their foot" |
| Apple-bearer | The thousand nearest the king; fruit-shaped spear counterweight (7.41), gold vs the corps' silver per Heraclides of Cyme |
| Greek Mercenary Hoplite | Not Herodotus — attested from Cunaxa 401 BCE onward; date-gated accordingly |

Every one of these carries a shared `disputed` note recording that the catalogue
is a literary set-piece: its equipment is treated as better evidence than its
troop numbers, which are wildly inflated, and its account of distant peoples
leans on Greek convention.

### Spells — legend, and flagged as unverified

The 16 Zauber come from the Shahnameh and the Avesta. They are **not** history
and are not presented as such: each carries `kind: "legend"`, `confidence: "traditional-account"`,
its source work, and an in-game banner reading "This is a story, not an event."
None of them is playable, and a test prevents unverified content from entering a
draft pool, an arena unlock, or a card reward.

They have **not** had a references pass. The `sourceRefs` on them are pointers
for the reviewer, not sources this pass read. That work is outstanding.

### Sources read in this pass

- Herodotus, *The Persian Wars* (Godley), Book VII —
  https://en.wikisource.org/wiki/Herodotus_The_Persian_Wars_(Godley)/Book_VII
- Livius — "Immortals": https://www.livius.org/articles/concept/immortals/
- Encyclopædia Iranica — Asagarta (via search summary; the site still 403s
  automated fetches): https://www.iranicaonline.org/articles/asagarta/

### Still outstanding before anything is published

1. Historian review of this slice (decision #6).
2. The other five launch eras — Parthian, Sassanian, Safavid, Afsharid, Qajar —
   are not yet written. RESEARCH-BRIEF.md §6 is **seed data, not verified data**.
3. Persian Gulf rule: enforced by test, and no coastal content exists in this
   slice yet. It becomes live content at Hormuz 1622 and Bushehr 1856.
4. Player names are user-generated content shown to strangers. They are shape-
   checked but not moderated — see DECISIONS.md, "Still outstanding".
5. **The 16 spells have had no references pass.** They are marked unverified and
   cannot be played, but the text on them is written from general knowledge of
   the Shahnameh and Avesta and needs checking before it is shown as finished.
6. The 13 arena blurbs are short and lightly sourced. They should get the same
   treatment as the battle cards.

---

## The confidence scale (M2)

`verified: boolean` was replaced with a five-level scale, because a yes/no flag
could not tell a contemporary inscription from a Greek story written five
centuries later — and that distinction is what this game exists to teach.

| Level | Means |
|---|---|
| `attested` | Contemporary evidence: inscription, chronicle, archaeology. |
| `probable` | Modern scholarship agrees; the evidence is indirect. |
| `traditional-account` | A later narrative or a legend. Real as a story, not as an event. |
| `reconstructed-for-gameplay` | Invented to make the game work, and labelled as such. |
| `fictional` | Alternate history. Never enters play. |

**The first pass was mechanical, and deliberately conservative.** A record
already carrying a `disputed` entry became `probable`; an uncontested one became
`attested`; the Shahnameh and Avesta cards became `traditional-account`. Nothing
was raised in standing by the migration.

That leaves **only three units at `attested`** — the Persian Archer, the Persian
Cavalry and the Saka Horse-archer. That is not a gap to be closed by relabelling.
Most of the Achaemenid roster rests on Herodotus' catalogue, which is a later
narrative source written by an opponent, and `probable` is the honest level for
it.

**Moving any record from `probable` to `attested` requires the specialist review
listed in CONCEPT-v0.2 §10.** Do not upgrade a label to make the collection look
better researched than it is.

### Upgrades and doctrines

All eight are `reconstructed-for-gameplay` except *Loosed Rein*, which models a
steppe practice that is genuinely attested across a long period (`probable`).
Their names are ours: no Achaemenid drill command or named formation survives.
Each says so in its own `disputed` list, and a test fails the build if an
invented card disputes nothing.
