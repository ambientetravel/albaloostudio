# The name

*"Persia at War" was a working title. Two things are wrong with it and the
second is the bigger one.*

## What is actually wrong

**"War" is the smaller problem.** It narrows a game whose best material is not
combat at all — the Anjoman is scientists and poets, the arenas are CITIES, the
board is a carpet, and the honesty layer is the whole reason the thing exists.
It also reads badly to a parent scanning a store listing for a nine-year-old,
which is the person who actually has to press buy.

**"Persia" is the bigger problem, and it is structural.** A nation cannot
contain the roadmap. The game already reaches Sardis, Memphis, Babylon, Bactra
and Gandara — Turkey, Egypt, Iraq, Afghanistan, Pakistan — and the commander
roster runs 550 BCE to 1739 CE. Naming it for one nation makes every expansion
look like an annexe. **"Age of Empires" and "Civilization" are containers.
"Persia at War" is a label.**

The name has to hold: many peoples, a very long time, and the fact that this is
about how civilisations *lasted*, not only how they fought.

---

## 1 · THE ROYAL ROAD  — *recommended*

**راه شاهی**

Darius's post road, Sardis to Susa, roughly 2,400 km, with relay stations the
whole way. Herodotus describes it and it is already **arena 12 in this game**.

**Why it is the strongest option:**

- **It literally runs from Turkey to Iran.** The expansion he described is the
  road's own route. Anatolia is not an annexe on this map, it is the western end.
- **It is real and sourced**, which matters for a game whose entire promise is
  that it does not invent.
- **A road is longevity.** Messengers, trade, thirty centuries of traffic — the
  opposite of a war word, and it carries the "how they lasted" idea without
  having to say it.
- **It is a container.** Anything the road touched belongs, and the road touched
  most of the old world.
- **It draws.** A milestone, a rider, a road running to the horizon. Better icon
  material than a sword.

*Subtitle: "the battles that made the old world" — or drop the subtitle
entirely, which is usually the braver call.*

*Risk: could read as a travel app in isolation. The icon has to do work.*

## 2 · SIMORGH

**سیمرغ**

The bird of the Shahnameh — she raises Zal, tells Zal how to deliver Rostam, and
heals them both. And in Attar's *Conference of the Birds*, thirty birds cross
the world to find the Simorgh and discover that they ARE her: **si morgh, thirty
birds.** A twelfth-century pun that means the thing you were seeking was the
gathering of you all along.

- **Wisdom-as-collective is this game's actual shape** — a draft of many peoples
  into one army, and an Anjoman of many minds.
- **Pan-regional.** Anka in Turkish and Arabic, Huma across the same world. It
  does not belong to one modern country.
- **Ownable and unmistakable.** No other game on a shelf is called this, and it
  makes a superb single icon.

*Risk: says nothing about what the game IS, so it needs a subtitle and will
carry more marketing weight. And it is mythological, in a game that sells
itself on not inventing — although the game already has a legend tier and this
would be a brand, not a claim.*

## 3 · FARR

**فرّ / خوارنه — khvarenah**

The glory that makes a ruler legitimate **and departs when he acts unjustly.**
Jamshid loses it to pride. It is the Iranian idea that authority is earned and
can be forfeited.

- **It is the moral spine of this roster.** Four of nine commanders end in
  defeat. A name meaning "the glory that can be lost" is not decoration, it is
  the thesis.
- Short, hard, good in any language, one syllable.

*Risk: opaque outside Persian-speaking families. It teaches a word, which suits
the project, but a nine-year-old in Toronto cannot guess it.*

## 4 · CROSSROADS OF EMPIRES

Descriptive, container-shaped, needs no glossary, and says exactly what the
region was: the place everything passed through.

*Risk: the safest and the least memorable. It sounds like a documentary rather
than a game a child asks for by name.*

## 5 · THE HUNDRED CITIES

Bactra was called the mother of cities. **Every arena in this game is a city** —
Anshan, Ecbatana, Sardis, Babylon, Susa, Persepolis, Memphis. Cities are what
civilisations leave behind, and counting them is counting endurance rather than
conquest.

*Risk: sounds like a builder or a 4X. Sets an expectation the battle loop then
has to correct.*

## 6 · KHERAD

**خرد — wisdom, reason**

Avestan *xratu*, and the first significant word of the Shahnameh: Ferdowsi opens
in the name of the lord of soul and **kherad**.

*Honest verdict: the most beautiful of these and the weakest title. It names a
virtue rather than a world, and virtues do not make icons.*

## 7 · THE LONG MEMORY

What the region actually has that others do not — continuous record, in
inscription, coin and poem, across three thousand years.

*Risk: literary, adult, and quiet. A great tagline. Probably not a title for a
twelve-year-old.*

---

## Recommendation

**THE ROYAL ROAD**, with **SIMORGH** as the alternative if brand
distinctiveness beats descriptiveness.

The Royal Road wins on the specific thing that prompted this: it is *already the
route he wants to expand along*. Turkey is not an addition to a Persian game, it
is the western terminus of the thing the game is named for. Nothing else on the
list solves the expansion problem that cleanly, and the rest solve it by being
vague.

## What renaming actually costs

Small, and worth doing before launch rather than after:

- The repo directory and the `<title>`.
- **`localStorage` keys**, currently `persia-at-war/recordings/v1`. A rename
  orphans every saved recording unless it is migrated — one branch on read.
- The docs folder, which says the old name in about a dozen places.
- Nothing in `sim/`, nothing in the content data, no art.
