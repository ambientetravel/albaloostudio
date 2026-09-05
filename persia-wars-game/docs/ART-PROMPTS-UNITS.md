# Unit prompts — the twenty-one, now with people in them

Four are done: Persian Archer, Shield-bearer, Median Spearman, Persian Cavalry —
their names are in the table below. These are the other twenty-one, each complete
and self-contained. Copy one whole block; do not trim the first three paragraphs,
they are what makes the cut-out tool work and what keeps the units apart at
thumbnail size.

## The names, and what they are and are not

**Every unit is now a person, not a category.** "Persian Archer" cannot be
described in four words because nobody is there; Karkish can.

**The card carries the name; the contingent becomes the subtitle.** The gear, the
dress and the tactics stay exactly as attested — nothing about the history moves.
What changes is that somebody is wearing it.

**These individuals are fictional. The names are not.** Each is a real
period-appropriate name for that people — several are ordinary names out of the
**Persepolis Fortification Tablets**, the Achaemenid administration's own clay
records. **No card is named after a specific historical person**, deliberately:
Hydarnes actually commanded the Immortals, so the Immortal is NOT called Hydarnes.
The codex line for every unit reads *"a soldier of the X, named for this game."*

*One weak spot, stated: ancient Colchian personal names are barely attested.
Saulakes comes from Pliny, who names a Colchian king. It is the thinnest of the
twenty-five and if a better source turns up, change it.*

| # | name | contingent | age band |
|---|---|---|---|
| — | **Karkish** | Persian Archer *(done)* | 20s |
| — | **Rausha** | Shield-bearer *(done)* | 30s |
| — | **Datama** | Median Spearman *(done)* | 40s |
| — | **Sataspa** | Persian Cavalry *(done)* | 30s |
| 1 | Shutruk | Kissian Levy | **17** |
| 2 | Artavazda | Immortal | 40 |
| 3 | Oxyartes | Bactrian Archer | 30s |
| 4 | **Zarina** | Saka Horse-archer | 20s · **woman** |
| 5 | Vahuka | Caspian Skirmisher | 20s |
| 6 | Balatu | Assyrian Clubman | 50s |
| 7 | Korylas | Paphlagonian Javelineer | 20s |
| 8 | Zamaspa | Sagartian Lassoer | 30s |
| 9 | Sanjaya | Indian Cane-bow Archer | 20s |
| 10 | Zabbai | Arabian Camel Rider | 50s |
| 11 | Bithys | Thracian Peltast | 20s |
| 12 | Myrsos | Lydian Hoplite | 30s |
| 13 | Saulakes | Colchian Shieldman | 20s |
| 14 | Tiridat | Armenian Lancer | 30s |
| 15 | Psamtik | Egyptian Marine | 40s |
| 16 | Alara | Ethiopian Bowman | 20s |
| 17 | Kleon | Greek Mercenary Hoplite | 40s |
| 18 | Mithradat | Scythed Chariot *(the driver)* | 20s |
| 19 | Farnah | Chorasmian Rider | 30s |
| 20 | **Ajita** | War Elephant *(the elephant)* | mahout is **14** |
| 21 | Ushtana | Apple-bearer | **60s** |

**Four age bands now, from fourteen to sixty**, where before there was one. A
roster with one age band looks like a toy; this one looks like a people.

## Zarina, and why the Saka archer is a woman

**Because the graves say so.** Across the Eurasian steppe, excavation has
repeatedly recovered **women buried with weapons** — bows, arrowheads, horse
gear — and in examined weapon-burials the female share runs to roughly a fifth.
That is physical evidence, not literature, and it is the archaeology underneath
Herodotus's Amazon stories. **The Saka were an Achaemenid contingent, so a woman
on a Saka horse is a grave good, not an invention.**

This is the ONLY unit that changes sex, and it changes on evidence. The Immortals
stay male, the Lydian phalanx stays male, and they stay that way for the same
reason Apranik is not in this game.

**Next cheapest, same evidence base:** the **Chorasmian Rider (19)** and the
**Sagartian Lassoer (8)** come from the same steppe world. Either can be made a
woman by changing one sentence, whenever you want a second.

## The appeal pass — applies to all twenty-five

The prompts below were written for accuracy and got it. They were not written for
charm, and charm is what makes a child want the next card. Add to every one:

- **They look at you.** Eye contact. Not one of the current twenty-five does this,
  and it is the single biggest difference between a troop type and a person.
- **One feature pushed 30% past life** — the camel rider's absurd saddle height,
  the Sagartian's oversized coil of rope, Alara's bow taller than he is. One per
  card, no more.
- **Warmth, not grimness.** Dignified was right; dour was not. These are
  children's cards.

Every kit description below is what Herodotus actually records for that people.
Nothing here is invented. Where a detail is uncertain it has been left out
rather than guessed.

## Three things learned the hard way

**One connected shape.** `tools/spriteprep.py` keeps the single largest
connected component and deletes everything else. A bow held away from the body,
a thrown javelin, a rope with a gap in it — all get silently deleted. The
Wheeling Line emblem lost its shields exactly this way.

**Must float on the grey.** A subject that fills its own frame cannot be cut
out at all: the flood fill works inward from the four corners and finds nothing
to fill. The rejected Loosed Rein emblem failed on this.

**The 22px column decides.** Units are drawn at 22–85px. Five archers holding
bows will be the same picture unless each has a silhouette hook — a shaggy
cloak, a pointed cap, a bow taller than the man. The hook is called out in each
prompt below and is the part not to drop.

## Collision risks to watch

- **Myrsos vs Kleon** — both in Greek armour. Kept apart by crest direction and
  shield device only. Generate side by side and check before accepting either.
  **Now also by age and face:** Myrsos is thirty and expensively equipped,
  Kleon is forty-five and scarred. That difference does more work than the crest.
- **Tiridat vs Farnah** — both cavalry in soft caps. Kept apart by the level
  lance versus the bow.
- **The five archers** — Karkish (done), Oxyartes, Vahuka, Sanjaya, Alara.
  Hooks: plain, short-spear-as-well, shaggy goatskin, white cotton, and a bow
  taller than the man. **Zarina is a sixth archer but is mounted**, so she does
  not compete in this group.

## A side effect worth taking

**All twenty-five names fit in nine characters** — the tested ledger ceiling,
where 'Chorasmian' needed 49px in a 40px box and ellipsised. The longest is
**Artavazda**, exactly nine. So when these land in `units.json`, the
`SHORT_NAME` map in `src/ui/labels.ts` can be **deleted rather than rewritten**:
the character name IS the short name. That is one fewer thing to keep in sync,
and it was built to solve a problem the names remove.

---

## 1. Shutruk — *Kissian Levy — infantry*

**Card name: Shutruk. Subtitle: Kissian Levy.** About seventeen. First campaign, gear that does not fit him yet.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: a soldier of the Kissian levy from the country around Susa, wearing
exactly the Persian kit — a knee-length sleeved tunic patterned in ochre and
lapis over trousers, a short spear held upright in the right hand, a tall wicker
shield resting against the left leg, a bow and quiver slung at the back — but
with a cloth TURBAN wound about the head instead of the soft Persian cap. The
turban is the silhouette hook and must be a clear rounded mass, unmistakable
against a capped Persian at thumbnail size.

---

## 2. Artavazda — *Immortal — heavy infantry*

**Card name: Artavazda. Subtitle: Immortal.** Forty. Entirely unhurried — he has done this many times.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: a soldier of the king's guard, the corps the Greeks called the
Immortals, in the manner of the Persepolis reliefs — a long richly patterned
sleeved robe in deep oxblood and gold, a soft cloth cap covering the head and
neck, a short spear held vertically in both hands with the butt near the ground,
a large bow and a full quiver slung across the back, and a tall rectangular
WICKER shield standing beside him at full body height, its woven texture clearly
drawn. The full-height woven shield plus the bow at the back is the silhouette
hook. Bearing calm and formal, not aggressive.

---

## 3. Oxyartes — *Bactrian Archer — archer*

**Card name: Oxyartes. Subtitle: Bactrian Archer.** Thirties. Mountain-weathered, eyes narrowed from long distances.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: an archer from Bactria in the far north-east of the empire, in a soft
Median-style cap whose peak curves forward over the brow, a belted knee-length
tunic and trousers in ochre and dull green, holding a bow of REED slanted down
in the left hand with its lower tip touching the ground beside his foot, and
carrying a SHORT SPEAR upright in the right hand as well. Carrying both bow and
spear at once is the silhouette hook — it is what separates him from every other
archer in the set.

---

## 4. Zarina — *Saka Horse-archer, horse-archer*

**Card name: Zarina. Subtitle: Saka Horse-archer.** **A WOMAN, late twenties.**
Calm, level, entirely ordinary among her own people — see the evidence note above.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single mounted soldier, full body of horse and rider with all
four hooves visible, facing three-quarters to the right, centred, whole and
uncropped, generous empty margin on all four sides. Flat, even, mid-grey
background, one solid colour, no gradient, no vignette, no texture, no scenery,
no ground, no floor line. The figure must float on the grey — NOT a tile, NOT a
scene, NOT a square panel — and must not touch or fill the edges of the image.
No text, no letters, no numerals, no signature, no watermark, no logo, no
border, no frame, no UI. Square, 2048x2048.

Silhouette: horse and rider together must be ONE single connected shape. Every
weapon and item must physically touch the body — nothing floating separately, NO
ARROWS IN FLIGHT, no gaps between hand and weapon. The pose must be readable in
pure black silhouette at thumbnail size.

Subject: a Saka (Scythian) horse-archer — **a woman in her late twenties** — shooting a recurved composite bow from the saddle of a small, shaggy steppe pony. She wears the Saka POINTED CAP: tall, soft, bending forward at the tip, which is the single most recognisable thing about this people and is the silhouette hook together with the horse. Trousers, boots, and a long-sleeved patterned coat belted at the waist, with a gorytos — the combined bow-case and quiver — at her left hip. Hair braided and tucked up under the cap; one small gold animal-style plaque at the collar. She is dressed for cold and for hard riding **exactly as the men of her people are — trousers, coat, boots, everything covered; no skin beyond hands and face.** Composed and level, mid-draw, not fierce and not snarling. She is not posed as an exception; she is a soldier of a people who buried their women with bows.

---

## 5. Vahuka — *Caspian Skirmisher — archer*

**Card name: Vahuka. Subtitle: Caspian Skirmisher.** Mid-twenties, lean and restless, already eyeing the next bit of cover.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: a light skirmisher from the Caspian shore, wrapped in a heavy SHAGGY
GOAT-SKIN CLOAK with the rough hair clearly visible, its bulk breaking his
outline at the shoulders. He holds a reed bow low in one hand and wears a short
sword at his hip. Bare-headed or in a plain cloth wrap. The shaggy irregular
cloak is the silhouette hook — at thumbnail size he must read as fur where the
other archers read as clean cloth.

---

## 6. Balatu — *Assyrian Clubman — heavy infantry*

**Card name: Balatu. Subtitle: Assyrian Clubman.** Fifties. Big, slow-moving, completely calm.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: an Assyrian levy soldier in a stiff white LINEN breastplate over a
tunic, wearing a bronze helmet of an unusual twisted, banded construction, and
resting a heavy wooden CLUB STUDDED WITH IRON on his shoulder with both hands.
A shield on his back and a dagger at his belt. The thick club shape held clear
of the head against the shoulder is the silhouette hook. Powerful and solid in
build, but calm and upright — not snarling, not mid-swing.

---

## 7. Korylas — *Paphlagonian Javelineer — infantry*

**Card name: Korylas. Subtitle: Paphlagonian Javelineer.** Early twenties. Bright-eyed and plainly proud of that helmet.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, NO
JAVELIN IN FLIGHT, no gaps between hand and weapon. The pose must be readable in
pure black silhouette at thumbnail size.

Subject: a Paphlagonian javelineer from the Black Sea coast of Anatolia, in a
plaited woven helmet, a short tunic, and distinctive KNEE-HIGH BOOTS. He carries
a SMALL round shield on his left arm and holds a BUNDLE OF THREE JAVELINS
together in his right fist, points up, all three touching each other and his
hand. The tall boots plus the fan of three javelin shafts is the silhouette hook.

---

## 8. Zamaspa — *Sagartian Lassoer — cavalry*

**Card name: Zamaspa. Subtitle: Sagartian Lassoer.** Thirties. Watchful; the hands never stop moving.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single mounted soldier, full body of horse and rider with all
four hooves visible, facing three-quarters to the right, centred, whole and
uncropped, generous empty margin on all four sides. Flat, even, mid-grey
background, one solid colour, no gradient, no vignette, no texture, no scenery,
no ground, no floor line. The figure must float on the grey — NOT a tile, NOT a
scene, NOT a square panel — and must not touch or fill the edges of the image.
No text, no letters, no numerals, no signature, no watermark, no logo, no
border, no frame, no UI. Square, 2048x2048.

Silhouette: horse and rider together must be ONE single connected shape. Every
item must physically touch the body — nothing floating separately, no gaps. The
rope must be a CLOSED CONTINUOUS LOOP whose line touches the rider's hand at
every point along it, never a floating circle. The pose must be readable in pure
black silhouette at thumbnail size.

Subject: a Sagartian nomad horseman wearing NO ARMOUR AT ALL — just a plain
belted tunic and trousers in undyed wool and a dagger at the belt — swinging a
large open LOOP OF TWISTED LEATHER ROPE above and slightly ahead of him, the
rope's tail running unbroken down into his raised right hand. The big open
rope loop is the silhouette hook and must be the widest thing in the image after
the horse. Nobody is caught in it — the loop is empty.

---

## 9. Sanjaya — *Indian Cane-bow Archer — archer*

**Card name: Sanjaya. Subtitle: Indian Cane-bow Archer.** Twenties. Precise — the stillest figure in the whole set.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: an archer from the Indus lands in unbleached WHITE COTTON — a wrapped
lower garment and a cloth over one shoulder, which a Greek audience found
remarkable because it was neither wool nor linen. Bare-headed, dark hair tied
back. He holds a long slim bow of CANE vertically at his side, its lower tip
resting on the ground beside his foot, and wears a quiver of cane arrows with
iron points. The pale cotton against dark hair, bare head, and the tall thin
vertical bow line is the silhouette hook.

---

## 10. Zabbai — *Arabian Camel Rider — cavalry*

**Card name: Zabbai. Subtitle: Arabian Camel Rider.** Fifties, sun-creased, faintly amused by everyone down at ground level.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single mounted figure, full body of camel and rider with all
four feet visible, facing three-quarters to the right, centred, whole and
uncropped, generous empty margin on all four sides. Flat, even, mid-grey
background, one solid colour, no gradient, no vignette, no texture, no scenery,
no ground, no floor line. The figure must float on the grey — NOT a tile, NOT a
scene, NOT a square panel — and must not touch or fill the edges of the image.
No text, no letters, no numerals, no signature, no watermark, no logo, no
border, no frame, no UI. Square, 2048x2048.

Silhouette: camel and rider together must be ONE single connected shape. Every
weapon and item must physically touch the body — nothing floating separately, no
arrows in flight, no gaps between hand and weapon. The pose must be readable in
pure black silhouette at thumbnail size.

Subject: an Arabian archer riding a single-humped CAMEL at a walk, seated high
behind the hump on a patterned saddle-cloth in ochre and oxblood. He wears a
long girded mantle and a cloth head-wrap, and carries a LONG BOW THAT CURVES
BACKWARDS at its tips, held upright in his right hand against his shoulder. The
camel's hump, long neck and high leggy stance is the silhouette hook — it must
be impossible to mistake for a horse at thumbnail size.

---

## 11. Bithys — *Thracian Peltast — infantry*

**Card name: Bithys. Subtitle: Thracian Peltast.** Twenties, grinning, wearing the cold-weather cloak like a boast.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
javelin in flight, no gaps between hand and weapon. The pose must be readable in
pure black silhouette at thumbnail size.

Subject: a Thracian peltast in a FOX-SKIN CAP with the fox's tail hanging down
behind his neck, a mantle of many colours in ochre, oxblood and cream over a
short tunic, and soft fawnskin boots. On his left arm a small CRESCENT-SHAPED
pelta shield with the curved bite cut out of its top edge; in his right hand two
javelins held together. The crescent shield plus the hanging fox tail is the
silhouette hook — the notched shield outline must survive at thumbnail size.

---

## 12. Myrsos — *Lydian Hoplite — heavy infantry*

**Card name: Myrsos. Subtitle: Lydian Hoplite.** Thirties. Expensive equipment, and he knows exactly what it cost.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: a soldier from Persian-ruled Sardis fighting in Greek armour — a bronze
helmet with a LOW SIDEWAYS CREST running ear to ear across the top, a bronze
cuirass worn over a patterned Anatolian tunic in ochre and lapis with a
decorative fringed hem showing beneath it, greaves, a large round shield held
edge-on at his left side, and a spear upright in his right hand. The sideways
ear-to-ear crest and the patterned fringed hem below the armour are the
silhouette hooks — he must NOT be confusable with the Greek Mercenary Hoplite,
who has a front-to-back crest and a plain hem.

---

## 13. Saulakes — *Colchian Shieldman — infantry*

**Card name: Saulakes. Subtitle: Colchian Shieldman.** Twenties. Quiet — from very far away, and aware of it.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: a soldier from Colchis on the eastern shore of the Black Sea, wearing a
helmet carved from WOOD — angular, plank-like, clearly not metal — over a plain
belted tunic. He carries a SMALL round shield of raw untanned OX-HIDE with the
hair still on it and the hide's irregular edge visible, and a short spear in his
right hand, with a sword at his belt. The blocky wooden helmet plus the small
rough hide shield is the silhouette hook.

---

## 14. Tiridat — *Armenian Lancer — cavalry*

**Card name: Tiridat. Subtitle: Armenian Lancer.** Thirties, upright. The horse is better cared for than the man.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single mounted soldier, full body of horse and rider with all
four hooves visible, facing three-quarters to the right, centred, whole and
uncropped, generous empty margin on all four sides. Flat, even, mid-grey
background, one solid colour, no gradient, no vignette, no texture, no scenery,
no ground, no floor line. The figure must float on the grey — NOT a tile, NOT a
scene, NOT a square panel — and must not touch or fill the edges of the image.
No text, no letters, no numerals, no signature, no watermark, no logo, no
border, no frame, no UI. Square, 2048x2048.

Silhouette: horse and rider together must be ONE single connected shape. Every
weapon and item must physically touch the body — nothing floating separately, no
gaps between hand and weapon. The pose must be readable in pure black silhouette
at thumbnail size.

Subject: an Armenian highland horseman on a notably strong deep-chested horse —
Armenia paid its tribute to the Great King in horses, and the animal should look
like the point of the picture. He wears a soft PHRYGIAN CAP whose peak flops
forward over the brow, a patterned tunic and trousers, and carries a LONG LANCE
held LEVEL AND HORIZONTAL across the horse's neck, pointing right. The
horizontal lance line plus the forward-flopping cap peak is the silhouette hook,
and is what keeps him apart from the Chorasmian Rider.

---

## 15. Psamtik — *Egyptian Marine — heavy infantry*

**Card name: Psamtik. Subtitle: Egyptian Marine.** Forties, seafarer’s build, thoroughly unimpressed.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: an Egyptian ship-fighter in a plaited woven helmet and a corselet,
holding a GREAT LONG-HANDLED BATTLE-AXE upright in both hands with its wide
crescent blade held clear above his shoulder, and carrying a CONCAVE shield with
a notably BROAD RAISED RIM on his left arm. A long knife at his belt. The wide
axe-head silhouetted clear of the body, plus the deep-rimmed shield, is the
silhouette hook. The axe is held at rest, not raised to strike.

---

## 16. Alara — *Ethiopian Bowman — archer*

**Card name: Alara. Subtitle: Ethiopian Bowman.** Twenties. Tall — the tallest silhouette in the set, and it should read as such.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and dignified portrayal of a
real historical people — no caricature, no exaggerated features, no bare-savage
or primitive styling. He is a soldier of the Great King like any other.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: a bowman from Nubia standing tall and composed, a spotted leopard skin
worn over one shoulder across a plain tunic, holding a BOW OF PALM-WOOD STRIPS
THAT IS TALLER THAN HE IS — roughly four cubits, its upper tip well above his
head and its lower tip resting on the ground beside his foot. At his back a
quiver of short arrows tipped with sharpened STONE rather than iron. The
enormous bow overtopping the figure's own head is the silhouette hook and is the
single most important element — it must be unmistakable at 22 pixels.

---

## 17. Kleon — *Greek Mercenary Hoplite — heavy infantry*

**Card name: Kleon. Subtitle: Greek Mercenary Hoplite.** Forties. Scarred kit, in it for the pay, not hiding it.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: a Greek hoplite in Persian pay — a bronze Corinthian helmet pushed back
on the head with a TALL CREST RUNNING FRONT TO BACK from brow to nape, a plain
undecorated linen corselet, greaves, a plain oxblood cloak, and a large round
shield turned to show its FACE to the viewer with a simple bold painted device
on it. Spear upright in the right hand. The tall front-to-back crest and the
face-on decorated shield are the silhouette hooks — he must NOT be confusable
with the Lydian Hoplite, whose crest runs sideways and whose shield is edge-on.

---

## 18. Mithradat — *Scythed Chariot — chariot*

**Card name: Mithradat. Subtitle: Scythed Chariot.** The DRIVER is the character — twenties, braced, leaning into it. He is why this card is not just a machine.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single chariot with its team, full body with all wheels and
hooves visible, facing three-quarters to the right, centred, whole and
uncropped, generous empty margin on all four sides. Flat, even, mid-grey
background, one solid colour, no gradient, no vignette, no texture, no scenery,
no ground, no floor line. The subject must float on the grey — NOT a tile, NOT a
scene, NOT a square panel — and must not touch or fill the edges of the image.
No text, no letters, no numerals, no signature, no watermark, no logo, no
border, no frame, no UI. Square, 2048x2048.

Silhouette: chariot, driver and both horses must be ONE single connected shape.
Every part must physically touch — traces, yoke, reins and blades all joined, no
floating pieces, no gaps. The shape must be readable in pure black silhouette at
thumbnail size.

Subject: a Persian war chariot drawn by TWO horses side by side, a light open
car with a single driver standing in it holding the reins, and long curved
BLADES BOLTED OUT FROM THE WHEEL HUBS on the near side, projecting clearly
beyond the wheel rim. The wide low wheeled mass with blades jutting sideways is
the silhouette hook. No victims, no blood, nothing being struck — the chariot
stands alone.

---

## 19. Farnah — *Chorasmian Rider — cavalry*

**Card name: Farnah. Subtitle: Chorasmian Rider.** Thirties. Oasis country, careful with everything.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single mounted soldier, full body of horse and rider with all
four hooves visible, facing three-quarters to the right, centred, whole and
uncropped, generous empty margin on all four sides. Flat, even, mid-grey
background, one solid colour, no gradient, no vignette, no texture, no scenery,
no ground, no floor line. The figure must float on the grey — NOT a tile, NOT a
scene, NOT a square panel — and must not touch or fill the edges of the image.
No text, no letters, no numerals, no signature, no watermark, no logo, no
border, no frame, no UI. Square, 2048x2048.

Silhouette: horse and rider together must be ONE single connected shape. Every
weapon and item must physically touch the body — nothing floating separately, no
arrows in flight, no gaps between hand and weapon. The pose must be readable in
pure black silhouette at thumbnail size.

Subject: a horseman from Chorasmia on the lower Oxus, at the empire's
north-eastern edge, equipped exactly as the Bactrian foot are — a soft
Median-style cap with a forward-curving peak, a belted tunic and trousers in
ochre and dull green — sitting upright with a REED BOW held VERTICALLY in his
left hand against his shoulder and a short spear slung behind. The upright
vertical bow beside the body is the silhouette hook, and is what keeps him apart
from the Armenian Lancer's horizontal lance.

---

## 20. Ajita — *War Elephant — elephant*

**Card name: Ajita. Subtitle: War Elephant.** Name the ELEPHANT, not the man — she is Ajita. The mahout behind her ears is a BOY OF ABOUT FOURTEEN, and he is the youngest face in the game.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. The animal must be treated with dignity —
not frightened, not maddened, not harmed.

Composition: one single elephant with its driver, full body with all four feet
visible, facing three-quarters to the right, centred, whole and uncropped,
generous empty margin on all four sides. Flat, even, mid-grey background, one
solid colour, no gradient, no vignette, no texture, no scenery, no ground, no
floor line. The subject must float on the grey — NOT a tile, NOT a scene, NOT a
square panel — and must not touch or fill the edges of the image. No text, no
letters, no numerals, no signature, no watermark, no logo, no border, no frame,
no UI. Square, 2048x2048.

Silhouette: elephant and driver must be ONE single connected shape. Every strap,
cloth and item must physically touch the animal — nothing floating separately,
no gaps. The shape must be readable in pure black silhouette at thumbnail size.

Subject: an Indian war elephant standing calmly, walking pace, with a patterned
caparison cloth in oxblood and gold over its back and a single driver seated at
its neck. Trunk curled DOWNWARD and inward, not raised or trumpeting. Ears and
tusks clearly drawn. No howdah tower, no armour plating, no weapons — the
sources record fifteen elephants in the Persian line at Gaugamela but say
nothing about how they were fitted out, so nothing is invented here. The
unmistakable elephant profile is the silhouette hook.

---

## 21. Ushtana — *Apple-bearer (Melophoros) — heavy infantry*

**Card name: Ushtana. Subtitle: Apple-bearer (Melophoros).** Sixties. Palace guard, ceremonial duty, and the oldest face in the set.

Style: hand-painted historical game art, Achaemenid Persian, warm ochre /
oxblood / lapis / gold palette, matte gouache texture, clean readable shapes, no
photorealism, no anime, no 3D render look. Illustrated for a children's
educational game — dignified, never cartoonish, never grim. No blood, no wounds,
no dismemberment. No modern objects. Respectful and accurate portrayal of a real
historical people — no caricature, no exaggerated features.

Composition: one single soldier, standing, full body with both feet visible,
facing three-quarters to the right, centred, whole and uncropped, generous empty
margin on all four sides. Flat, even, mid-grey background, one solid colour, no
gradient, no vignette, no texture, no scenery, no ground, no floor line. The
figure must float on the grey — NOT a tile, NOT a scene, NOT a square panel —
and must not touch or fill the edges of the image. No text, no letters, no
numerals, no signature, no watermark, no logo, no border, no frame, no UI.
Square, 2048x2048.

Silhouette: the figure must be ONE single connected shape. Every weapon, shield,
cloak and item must physically touch the body — nothing floating separately, no
detached projectiles, no gaps between hand and weapon. The pose must be readable
in pure black silhouette at thumbnail size.

Subject: one of the thousand noble spearmen who stood closest to the Great King,
in the most sumptuous version of Persian court dress — a long pleated robe to
the ankles in deep oxblood and gold with a patterned border, a soft fluted cloth
cap, no armour at all. He holds a spear POINT-DOWN in the ceremonial manner, so
that its butt end is UPPERMOST, and that butt is a large GOLDEN SPHERE like a
pomegranate, held at about head height. The gold sphere at the top of an
inverted spear, above a long unarmoured robe, is the silhouette hook — no other
unit in the set has a ball on a stick.
