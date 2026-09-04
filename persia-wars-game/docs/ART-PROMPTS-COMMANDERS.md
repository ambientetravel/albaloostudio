# Commander portraits — the eight

**Pipeline:** Midjourney first for the painterly quality, then Nano Banana via
Gemini for the consistency pass and any fixes. Same combination that produced
the arenas.

**Format:** `--ar 3:4`, chest-up. Crops cleanly to the 26px picker and to a
circular badge, and works as a full card.

**Consistency:** generate **Shapur I first** — he has the richest attested
regalia and a surviving relief. Once one is approved, lock its `--sref` and run
the remaining seven against it so all eight read as one set.

## What "precise" means here, and it is the whole job

**Five of the eight have surviving contemporary images. Three do not.**

| | likeness | from |
|---|---|---|
| Darius | **yes** | Bisotun and Persepolis reliefs |
| Ardashir I | **yes** | Naqsh-e Rostam investiture relief, coins |
| Shapur I | **yes** | Naqsh-e Rostam and Bishapur reliefs, coins |
| Shah Ismail I | **yes** | contemporary Italian and Persian painting |
| Nader Shah | **yes** | contemporary portraits |
| Cyrus | **no** | period dress only — the Pasargadae winged figure is disputed |
| Surena | **no** | Parthian sculpture of the period only |
| Rostam Farrokhzad | **no** | late Sasanian armour only |

The three without a likeness are **reconstructions from period dress, not
portraits**, and their codex entries must say so in those words. This is the
same rule that governs every unit in the game.

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

## 3. ARDASHIR I  →  `src/assets/commanders/ardashir-i.png`

*Founder of the Sasanian empire, r. 224–242 CE*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: The first Sasanian king, vigorous and in his prime. His crown must be clearly DIFFERENT from Shapur's: a plain DIADEM band with fluttering ribbons, surmounted by the KORYMBOS — the globe of hair bound in silk — but WITHOUT the crenellated battlement band. Thick hair in a bushy mass, a rounded curled beard. Lamellar armour at the shoulders under a plain heavy robe. Harder and less ornate than his son. Reference: the Naqsh-e Rostam investiture relief and his coinage — a real attested likeness.

---

## 4. SHAH ISMAIL I  →  `src/assets/commanders/shah-ismail.png`

*Founder of the Safavid dynasty, r. 1501–1524 CE*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: A young Safavid ruler, early twenties, notably youthful for a king. The identifying feature is the TAJ-E HAYDARI: a tall RED CAP rising to a point, divided into TWELVE VERTICAL GORES, with a white turban wound around its base — the headgear that gave the Qizilbash their name. Reddish hair and a short reddish beard, which contemporaries recorded. A silk robe with a patterned sash, a curved sword hilt just visible at the waist. Confident and very young. Reference: contemporary Italian and Persian painting — a real attested likeness.

---

## 5. NADER SHAH  →  `src/assets/commanders/nader-shah.png`

*Afsharid ruler and conqueror, r. 1736–1747 CE*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: An eighteenth-century Persian conqueror in his fifties, weathered and severe. The identifying feature is the KOLAH-E NADERI: a distinctive cap rising to FOUR SEPARATE PEAKS, jewelled, sometimes with an aigrette and a plume. A heavy dark MOUSTACHE and no full beard. A fur-trimmed coat over patterned silk, a jewelled belt. The face of a soldier rather than a courtier — direct, hard, unornamented. Reference: contemporary eighteenth-century portraits — a real attested likeness.

---

## 6. CYRUS THE GREAT  →  `src/assets/commanders/cyrus-the-great.png`

*Founder of the Achaemenid empire, r. c. 559–530 BCE — NO SURVIVING LIKENESS*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: RECONSTRUCTION FROM PERIOD DRESS, NOT A PORTRAIT. No image of Cyrus survives; the winged figure at Pasargadae is disputed and is NOT him. So: a Persian king of the mid-sixth century BCE in the dress of his own time and NOT in the later Persepolis royal style — a SOFT ROUNDED CLOTH CAP or plain fillet, NOT the crenellated crown, which belongs to Darius's era and would be an anachronism. A plain sleeved robe of good wool with a simple patterned border, a plain gold torque. A beard of moderate length, less formally dressed than the Persepolis convention. Older, watchful, unostentatious — a man other peoples chose to follow. Deliberately restrained.

---

## 7. SURENA  →  `src/assets/commanders/surena.png`

*Parthian commander at Carrhae, 53 BCE — NO SURVIVING LIKENESS*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: RECONSTRUCTION FROM PARTHIAN SCULPTURE, NOT A PORTRAIT. A Parthian nobleman in his thirties, in the dress of the first century BCE: a belted TUNIC over loose TROUSERS, and hair worn in a thick bushy mass parted in the middle and held by a plain DIADEM with ribbons — the Parthian fashion. A neat pointed beard. Plutarch records that he was tall and strikingly handsome and dressed his hair with care, so the vanity is attested and should show. Scale armour visible at one shoulder, a composite bow's tip just entering the frame. Reference: the Shami bronze and Parthian relief sculpture.

---

## 8. ROSTAM FARROKHZAD  →  `src/assets/commanders/rostam-farrokhzad.png`

*Sasanian commander at Qadisiyya, c. 636 CE — NO SURVIVING LIKENESS*

Style: hand-painted historical portrait for a children's educational game, Persian/Iranian, matte gouache and oil texture with visible brushwork, warm ochre and oxblood with lapis blue and gold, deep shadow, painterly and dignified — the look of a museum illustration rather than a comic. No photorealism, no anime, no 3D render, no digital airbrush. Respectful and accurate portrayal of a real historical person: no caricature, no exaggerated features, no snarling, no blood, no weapons raised to strike. --ar 3:4

Composition: a single figure, chest-up portrait, facing three-quarters, eyes to the viewer, filling the frame with a little headroom. Plain dark painterly background with a subtle warm vignette — no scenery, no landscape, no throne, no crowd, no border, no frame. No text, no letters, no signature, no watermark, no logo.

Subject: RECONSTRUCTION FROM LATE SASANIAN ARMOUR, NOT A PORTRAIT. A Sasanian general in his forties, near the end of the empire and knowing it. A tall conical HELMET with a mail AVENTAIL falling to the shoulders, framing the face. LAMELLAR armour of small overlapping plates over a mail shirt. A curled beard in the Sasanian manner. No crown — he is a commander, not a king. The expression should be tired and resolute rather than defiant: a competent man in a losing position, which is exactly what he was. Reference: the Taq-e Bostan reliefs and late Sasanian armour finds.

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
