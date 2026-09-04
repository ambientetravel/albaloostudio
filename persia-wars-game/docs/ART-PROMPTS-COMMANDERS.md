# Commander portraits — the nine

**Pipeline:** Midjourney first for the painterly quality, then Nano Banana via
Gemini for the consistency pass and any fixes. Same combination that produced
the arenas.

**Format:** `--ar 3:4`, chest-up. Crops cleanly to the 26px picker and to a
circular badge, and works as a full card.

**Consistency:** generate **Shapur I first** — he has the richest attested
regalia and a surviving relief. Once one is approved, lock its `--sref` and run
the remaining eight against it so all nine read as one set.

## What "precise" means here, and it is the whole job

**Four of the nine have a surviving contemporary image. Five do not** — and the
balance flipping that way when Babak and Yaqub joined is itself a fact about
Iranian history worth putting in the codex rather than hiding.

| | likeness | from |
|---|---|---|
| Darius | **yes** | Bisotun and Persepolis reliefs |
| Shapur I | **yes** | Naqsh-e Rostam and Bishapur reliefs, coins |
| Shah Ismail I | **yes** | contemporary Italian and Persian painting |
| Nader Shah | **yes** | contemporary portraits |
| Cyrus | **no** | period dress only — the Pasargadae winged figure is disputed |
| Surena | **no** | Parthian sculpture of the period only |
| Rostam Farrokhzad | **no** | late Sasanian armour only |
| Babak Khorramdin | **no** | the Khurramites' red clothing is attested; nothing else is |
| Yaqub ibn al-Layth | **no** | 9th-century Sistani dress only |

The five without a likeness are **reconstructions from period dress, not
portraits**, and their codex entries must say so in those words. This is the
same rule that governs every unit in the game.

**A specific trap for the last two.** Both Babak and Yaqub have famous MODERN
images — 20th-century nationalist statues and book covers, muscular and
sword-raised. Those are not likenesses, they are modern art about a memory, and
a generator asked for "Babak Khorramdin" will reproduce them. The prompts below
describe period dress and say nothing about heroic posture for exactly this
reason.

The identifying regalia below is real and specific. It is what makes these
precise rather than generic — and it is what a generator will get wrong if not
told: Ardashir and Shapur have DIFFERENT crowns, Ismail's cap has twelve gores
for a reason, and Nader's has four peaks.

---

## 1. SHAPUR I  →  `src/assets/commanders/shapur-i.png`

*Sasanian King of Kings, r. 240–270 CE — GENERATE THIS ONE FIRST*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: A Sasanian king in his forties. His crown is the identifying feature and must be exact: a tall CRENELLATED MURAL CROWN — a band of square battlements — surmounted by the KORYMBOS, a large globe of hair gathered up and bound in fine silk. Long hair falling in tight ringlets to the shoulders, and a long square-cut beard, curled and possibly ringed. Heavy gold earrings, a pearl-and-gold collar, a robe of patterned silk over mail at the shoulder. Calm, imperial, entirely unhurried. Reference: the Naqsh-e Rostam and Bishapur rock reliefs and his coin profiles — a real and well-attested likeness.

*After this one is approved, add `--sref <its url>` to the remaining seven.*

---

## 2. DARIUS THE GREAT  →  `src/assets/commanders/darius-the-great.png`

*Achaemenid King of Kings, r. 522–486 BCE*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: An Achaemenid king in middle age. A tall CRENELLATED GOLD CROWN, plain and square-toothed, over hair dressed in tight formal rows of curls. A long SQUARE-CUT BEARD in disciplined horizontal waves — the Persepolis convention, stylised rather than natural. A long sleeved robe with deep vertical pleats, patterned borders, and a wide sash. Gold torque at the throat, plain gold bracelets. Bearing formal and still, as on a relief. Reference: the Bisotun relief and the Persepolis audience reliefs — a real attested royal image.

---

## 3. SHAH ISMAIL I  →  `src/assets/commanders/shah-ismail.png`

*Founder of the Safavid dynasty, r. 1501–1524 CE*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: A young Safavid ruler, early twenties, notably youthful for a king. The identifying feature is the TAJ-E HAYDARI: a tall RED CAP rising to a point, divided into TWELVE VERTICAL GORES, with a white turban wound around its base — the headgear that gave the Qizilbash their name. Reddish hair and a short reddish beard, which contemporaries recorded. A silk robe with a patterned sash, a curved sword hilt just visible at the waist. Confident and very young. Reference: contemporary Italian and Persian painting — a real attested likeness.

---

## 4. NADER SHAH  →  `src/assets/commanders/nader-shah.png`

*Afsharid ruler and conqueror, r. 1736–1747 CE*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: An eighteenth-century Persian conqueror in his fifties, weathered and severe. The identifying feature is the KOLAH-E NADERI: a distinctive cap rising to FOUR SEPARATE PEAKS, jewelled, sometimes with an aigrette and a plume. A heavy dark MOUSTACHE and no full beard. A fur-trimmed coat over patterned silk, a jewelled belt. The face of a soldier rather than a courtier — direct, hard, unornamented. Reference: contemporary eighteenth-century portraits — a real attested likeness.

---

## 5. CYRUS THE GREAT  →  `src/assets/commanders/cyrus-the-great.png`

*Founder of the Achaemenid empire, r. c. 559–530 BCE — NO SURVIVING LIKENESS*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: RECONSTRUCTION FROM PERIOD DRESS, NOT A PORTRAIT. No image of Cyrus survives; the winged figure at Pasargadae is disputed and is NOT him. So: a Persian king of the mid-sixth century BCE in the dress of his own time and NOT in the later Persepolis royal style — a SOFT ROUNDED CLOTH CAP or plain fillet, NOT the crenellated crown, which belongs to Darius's era and would be an anachronism. A plain sleeved robe of good wool with a simple patterned border, a plain gold torque. A beard of moderate length, less formally dressed than the Persepolis convention. Older, watchful, unostentatious — a man other peoples chose to follow. Deliberately restrained.

---

## 6. SURENA  →  `src/assets/commanders/surena.png`

*Parthian commander at Carrhae, 53 BCE — NO SURVIVING LIKENESS*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: RECONSTRUCTION FROM PARTHIAN SCULPTURE, NOT A PORTRAIT. A Parthian nobleman in his thirties, in the dress of the first century BCE: a belted TUNIC over loose TROUSERS, and hair worn in a thick bushy mass parted in the middle and held by a plain DIADEM with ribbons — the Parthian fashion. A neat pointed beard. Plutarch records that he was tall and strikingly handsome and dressed his hair with care, so the vanity is attested and should show. Scale armour visible at one shoulder, a composite bow's tip just entering the frame. Reference: the Shami bronze and Parthian relief sculpture.

---

## 7. ROSTAM FARROKHZAD  →  `src/assets/commanders/rostam-farrokhzad.png`

*Sasanian commander at Qadisiyya, c. 636 CE — NO SURVIVING LIKENESS. NOT the
legendary Rostam of the Shahnameh: no lion skin, no leopard-skin helm, no giant
stature, no mace. This is a real seventh-century general in real armour.*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: RECONSTRUCTION FROM LATE SASANIAN ARMOUR, NOT A PORTRAIT. A Sasanian general in his forties, near the end of the empire and knowing it. A tall conical HELMET with a mail AVENTAIL falling to the shoulders, framing the face. LAMELLAR armour of small overlapping plates over a mail shirt. A curled beard in the Sasanian manner. No crown — he is a commander, not a king. The expression should be tired and resolute rather than defiant: a competent man in a losing position, which is exactly what he was. Reference: the Taq-e Bostan reliefs and late Sasanian armour finds.

---

## 8. BABAK KHORRAMDIN  →  `src/assets/commanders/babak-khorramdin.png`

*Khurramite leader in Azerbaijan, c. 816–837 CE — **no attested likeness, a reconstruction from period dress***

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no mountain, no fortress, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: A highland Iranian leader of the early ninth century, thirties or forties, weathered by twenty years of mountain campaigning. The single identifying feature is COLOUR: he wears DEEP RED — a red wool coat over a red tunic — because his followers were called the sorkh-jamegan, "the red-wearers", and the red clothing is the one visual fact the sources actually record. A plain wound cloth headwrap, not a crown and not a turban of state: he was never a king and must not be dressed as one. Dark hair, a full beard, plain leather belt, no jewellery, no silk, no gold. Wool and leather, mended and worn, the dress of a mountain province rather than a court.

**Do not** give him a crown, a throne, a sword raised overhead, a bared chest, a heroic bodybuilder physique, or a chained-prisoner pose. Every one of those comes from twentieth-century nationalist imagery, not from any source. He is a man in a red coat who held a mountain, and that is the whole picture.

---

## 9. YAQUB IBN AL-LAYTH AL-SAFFAR  →  `src/assets/commanders/yaqub-saffar.png`

*The coppersmith of Sistan, founder of the Saffarid dynasty, c. 861–879 CE — **no attested likeness, a reconstruction from period dress***

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no workshop, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: A ninth-century ruler from Sistan who began as a coppersmith and never lost the look of one. **This is deliberately the plainest portrait of the nine** — set beside Ismail's twelve-gored red cap and Nader's four-peaked crown he should read instantly as the man who came up from a trade. Undyed or dust-brown wool over a simple tunic, a plain cloth headwrap, a leather belt with a working buckle. Sun-dark skin, a short beard, broad hands and heavy forearms — a craftsman's build rather than a courtier's. The one touch of his trade: a small COPPER ornament at the collar or a copper-inlaid belt fitting, warm reddish metal, unpolished. No silk, no gold, no crown, no jewels.

Sources record him as living hard on campaign — barley bread and leeks, sleeping under his shield — and the portrait should carry that rather than any royal dignity. Reference: ninth-century eastern Iranian dress. There is no likeness of him; this is period clothing on a plausible face, and the codex says so.

---

## The Nano Banana pass

Once Midjourney has all eight, hand them to Gemini together and ask for:

1. **One set, not eight images.** Match the lighting direction, background value
   and colour temperature across all eight. Midjourney drifts across a batch even
   with `--sref`.
2. **Crop consistency.** Same headroom, same chest line, eyes on the same
   horizontal. They sit in a grid and any drift shows immediately.
3. **Regalia check against the brief.** Ardashir must NOT have Shapur's
   crenellated band. Ismail's cap must have twelve gores. Nader's must have four
   peaks. A generator will smooth these into a generic crown and it is the
   single most likely failure.
4. **The three reconstructions must not look more certain than the five
   portraits.** Cyrus, Surena and Rostam should read as carefully dressed
   figures, not as documentary likenesses.
