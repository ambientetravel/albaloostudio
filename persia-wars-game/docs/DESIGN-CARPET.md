# The floor of the battlefield

*Answering: carpet patterns on the battle ground, and how the thirteen arenas
split between open air and enclosed.*

## First, the trap — and it is a big one

**Every carpet design you are picturing is Safavid.** The medallion layout, the
Herati field, the boteh (paisley), the garden carpet, the tree of life, the
Tabriz and Kashan and Isfahan schools — **sixteenth and seventeenth century CE.**

**All thirteen arenas are Achaemenid — 559 to 330 BCE.**

That is a **two-thousand-year gap**, and putting a medallion carpet under Cyrus
at Pasargadae is exactly the same error as Cyrus meeting Biruni. It is the kind
of thing one knowledgeable parent spots instantly, and it would undercut the
promise the whole project runs on.

## But the honest answer is better than the invented one

### فرش پازیریک — the Pazyryk carpet

- Excavated **1949** by Sergei Rudenko from a **frozen Scythian burial mound** at
  Pazyryk in the Altai mountains, Siberia. The ice preserved it.
- **Fifth to fourth century BCE** — contemporary with this game's entire span.
- **The oldest knotted pile carpet known to exist.** In the Hermitage.
- The design is astonishingly close to what the game needs: a central field of
  **star-and-cross rosettes**, then a border of **griffins**, then a border of
  **fallow deer**, then an outer border of **horsemen** — riders walking beside
  their horses.
- **Attribution is genuinely disputed** — Achaemenid or Median work, or Saka work
  in a Persian idiom. The game already has a `disputed` field and this is exactly
  what it is for. Saying "we do not know who wove it" is more interesting than
  claiming it.

**And here is the part that makes it worth doing.** It was found in a **Saka
grave** — the same burial culture whose weapon-graves are the reason
**Zarina** is a woman. *The oldest carpet on earth and the bow in her hands come
out of the same ground.* That is one codex entry, and it is a very good one.

### One arena where it is not decoration but the actual plan

**Arena 6, Pasargadae.** Cyrus's royal garden is excavated: a rectangle divided
into four quarters by cut stone water channels. It is commonly called **the
earliest known چهارباغ — chahar bagh**, and the Old Persian word for a walled
garden, ***pairidaeza*, is the root of the word "paradise."**

**The Persian garden carpet is a garden seen from above** — four quarters, water
channels between them. And the battle field is already a rectangle with a grid
and a centre.

So at Pasargadae the ground can be a chahar bagh that is simultaneously the real
excavated garden plan AND the ancestor of the garden carpet, **and neither half
is invented**. That is the best single arena on this page.

## The engineering objection, which is serious

**Units render at 22–85px.** This codebase has already lost one legibility fight
at that scale — six plain infantry at 26px were the same ten-pixel brown smudge,
which is the entire reason a `SHORT_NAME` table had to exist. **A busy Herati
field under the sprites will do the same thing to the battle canvas**, and it
will be worse because it moves.

### The fix is also the historically correct one

**A carpet is identified by its borders.** The border bands are the signature —
it is how you tell a Tabriz from a Kashan across a room.

So: **pattern in the frame, quiet inside.** The battle canvas already draws a
gold frame around the field. Put the carpet's border bands there — griffins,
deer, horsemen — and keep the playing surface a low-contrast ground with at most
a faint ghosted field pattern. **You read "carpet" instantly, and the sprites
stay readable at 22px.** Nothing is given up.

## And the framing that makes all of it honest

**The carpet is not terrain. It is the board.**

Nobody fought a battle on a rug in a field, and the game must not imply they
did. But the battle canvas is already a **board** — a framed rectangle with a
grid and a centre circle. Presenting the board as a carpet says *this is a game
about a battle*, which is true, rather than *they fought on a carpet*, which is
not.

There is also real precedent for it: **Persian miniature painting, and the
Shahnameh manuscript tradition in particular, sets battle scenes on flat,
highly patterned decorative grounds.** A patterned battle ground is native to
Persian visual language, not imported into it.

## The thirteen arenas, split

| | arena | ground |
|---|---|---|
| 1 | Anshan | **enclosed** — Elamite highland citadel |
| 2 | Ecbatana | **enclosed** — the Median walled capital |
| 3 | Sardis | **enclosed** — Lydian citadel |
| 4 | Bactra | **enclosed** — walled city |
| 5 | Babylon | **enclosed** — processional way, glazed brick |
| 6 | **Pasargadae** | **garden** — the chahar bagh, see above |
| 7 | Memphis | **enclosed** — Egyptian temple precinct |
| 8 | Bisotun | **open** — a cliff face in the Zagros |
| 9 | Susa | **enclosed** — the Apadana, glazed-brick archers |
| 10 | Gandara | **open** — the Peshawar valley |
| 11 | Persepolis | **enclosed** — the Apadana, stone floor |
| 12 | The Royal Road | **open** — 2,400 km of it |
| 13 | The Persian Gates | **open** — a mountain gorge |

**Eight enclosed, one garden, four open air.**

**The rule that falls out of this: carpet borders on the nine, real ground on
the four.** Bisotun is a cliff, the Persian Gates is a gorge, the Royal Road is
a road, Gandara is a valley — those are places where the terrain is the point,
and terrain already feeds the simulation through `terrainMultiplier`. Putting a
carpet under a mountain gorge would be the second version of the same mistake.

**The four open arenas get their ground from the land**, and the contrast between
the two kinds is worth having: you can feel when you have marched out of the
palace.

## The expansion payoff — the floor tells you the century

If the game reaches later eras, the carpet advances with it, and **the ground
under your feet becomes a date**:

| era | carpet |
|---|---|
| **Achaemenid** | **Pazyryk** — 5th–4th c. BCE, the oldest that survives |
| **Sasanian** | **بهارستان — the Spring of Khosrow**, the jewelled garden carpet of Ctesiphon. **It does not survive** — it is known only from descriptions, and the sources say it was cut into pieces after the conquest. Legend tier, and **Rostam Farrokhzad's campaign ends at exactly that collapse** |
| **Safavid** | the medallion carpets at last — the **Ardabil Carpet**, 1539–40, signed and dated, in the V&A. This is where the patterns you were picturing genuinely belong |
| **Afsharid** | Nader's era, and later |

**That teaches the history of Persian carpet weaving for free**, as a side effect
of playing, and it does it in the correct order — which is the opposite of what
putting a Safavid medallion under Cyrus would have done.

---

# Correction — regional motifs, and the two-axis rule

**The objection above was over-applied.** It holds for the thirteen Achaemenid
arenas and nowhere else. **Chaldoran is 1514 and it is fought in Azerbaijan, a
day's ride from Tabriz, in the reign of the shah whose capital Tabriz was.** A
Tabriz motif there is not an anachronism — it is the correct carpet, in the
correct place, in the correct decade. Same for Mashhad under Nader.

So the answer is a mix, and the rule that produces it has **two axes, both of
which must pass**:

1. **WHERE** — which regional school belongs to that ground.
2. **WHEN** — whether that school existed yet.

One axis alone gives the wrong answer in both directions: place alone puts a
Safavid medallion under Cyrus; date alone puts a Kerman vase carpet in
Azerbaijan.

## What that produces across the nine commanders

| commander · battle | where | when | floor |
|---|---|---|---|
| Cyrus · Pasargadae | Fars | 550 BCE | **no school exists.** Pazyryk-era ground + the chahar bagh |
| Darius · Bisotun | Kermanshah | 522 BCE | open ground — it is a cliff |
| Surena · Carrhae | Harran | 53 BCE | no school |
| Shapur I · Edessa | upper Mesopotamia | 3rd c. CE | Sasanian; nothing survives |
| Rostam Farrokhzad · Qadisiyya | southern Iraq | 636 CE | **the Spring of Khosrow, which the conquest cut up** |
| Babak · Badhdh | **Azerbaijan** | 816–837 CE | Azerbaijan, **but seven centuries before the Tabriz school**. Highland kilim geometry, not a city medallion |
| Yaqub · Dayr al-Aqul | Sistan → Tigris | 861–879 CE | Sistan/Baluch geometry, same caution |
| **Ismail · Chaldoran** | **West Azerbaijan** | **1514** | **TABRIZ. Both axes pass cleanly — this is the anchor case** |
| **Nader · Karnal** | **Haryana, India** | **1739** | he is fighting the **Mughals on their own ground**, and Mughal carpet weaving is a real school descended from Persian. **Mughal floor, Khorasan borders** — the invasion is in the pattern |

**Babak is the one that tests the rule.** He is in Azerbaijan, which is Tabriz
country — but in the **ninth century**, seven hundred years before the Tabriz
court workshops. He gets highland geometric weaving, not a medallion. **A
designer working from place alone would have got him wrong.**

## The thing this gives the game for free

**The floor goes from anonymous to named.**

Weaving is ancient — Pazyryk proves it at 400 BCE. But the *named regional
schools* — Tabriz, Kashan, Isfahan, Kerman, Mashhad, Qom — crystallise from the
Safavid period onward. So in early arenas the ground is a shared, unattributed
ancient pattern, and as the centuries pass **the floor acquires a hometown.**

That is not a decorative gradient. **It is the actual history of Persian carpet
weaving**, taught as a side effect of playing, in the right order.

*One caution to carry: **Shiraz/Fars** weaving is tribal — Qashqai and Khamseh —
and is documented far later than the court schools. It is not the Safavid peer
of Tabriz and Isfahan, and the codex should not imply it is.*

## And the payoff that makes Chaldoran the best arena in the game

**Ismail loses Chaldoran in August 1514. Selim enters Tabriz the following
month — and the sources record that he carried its craftsmen back to Istanbul.**

So the Tabriz carpet under that battlefield **is what the battle costs.** The
player is standing on the thing that is about to be taken. Nothing has to be
invented, nothing has to be said out loud in the battle itself, and the codex
line writes itself.

**That is the strongest single argument for doing this at all** — it turns the
floor from decoration into a fact about the battle being fought on it.
