# Persia at War — Deep-Research & Handoff Brief

**Working title:** *Persia at War* (alt: *Empires of Persia*, *Shahnameh Showdown*, *Kings & Cavalry*)
**Type:** 2-player strategic **draft + auto-battler**, educational, about real Iranian battles (won *and* lost) across every era.
**Status:** Research / scoping only. Nothing built. Prepared for hand-off to a fresh Claude Code session.
**Relation to Boutimar:** None. This is a standalone product. Do **not** wire it into boutimar.com.

> Hard content rule carried over from the parent project: **always «خلیج فارس» / Persian Gulf, never "Arabian Gulf"** — applies to every map, label, and codex entry here too. And **never invent** a date, outcome, or unit — every historical claim must be verifiable.

---

## 1. The one-paragraph pitch

Two players each command an Iranian army from a chosen era — Achaemenid Immortals, Parthian horse-archers, Sassanian cataphracts and war-elephants, Safavid Qizilbash and musketeers, Qajar cannon. You **draft** a small squad from era-appropriate unit cards, then the armies **auto-battle** on a historic field. Win or lose, you unlock a **codex card** — the real king, the real battle, what actually happened and why. Matches last minutes. Underneath the fun sits a spine of genuine history: the kingdoms of Iran from Elam to the modern age, taught the way kids actually absorb things — by playing them.

## 2. Reference deconstructed — Draftshowdown (the model to adapt)

The mechanic to borrow, from Draftshowdown (Voodoo/MWM, QuestLab):

- **Draft:** 3 draws × 3 picks; a rotating pool; you pick one card at a time until your squad is set.
- **Signature loadout:** a small fixed load-out (theirs is 4 cards) that expresses a play-style; synergies and counters matter.
- **Auto-battle:** once it starts, units fight automatically — the skill is *pre-battle composition*, not twitch control. Good for kids and for async/turn-based tech.
- **Comeback valve:** the "fourth draw" gives the losing player fresh options — keeps matches tense to the end.
- **Session length:** minutes. "Depth for veterans, accessibility for newcomers."

**What we change:** the reskin is not cosmetic. Units, factions, and battles are *real Iranian history*, and every match ends in an **educational payload**. The draft pool is gated by **era**, so you can't put muskets in an Achaemenid army — that constraint is itself the teaching.

## 3. Audience & educational goals

- **Primary:** kids / families, 9–14, especially the **Iranian diaspora** wanting their children to know the heritage; plus history-curious casual gamers.
- **Secondary:** schools (Iran + diaspora community schools), museums.
- **Learning outcomes:** recognise the sequence of Iranian dynasties; associate famous kings with their era; understand that empires *rise and fall* (wins **and** losses both taught — Marathon and Salamis sit next to Gaugamela); basic geography of the plateau; era-appropriate military technology (bow → cataphract → gunpowder → cannon).
- **Bilingual from day one:** Farsi + English (RTL/LTR both). Consider Arabic/German later (diaspora hubs).

## 4. Core game design

### 4.1 Loop
1. **Choose era/faction** (or draft cross-era in "legends" mode).
2. **Draft** squad from the era pool (3×3 picks; fourth-draw comeback).
3. **Deploy** on a lane/field (simple positioning, optional).
4. **Auto-battle** resolves (rock-paper-scissors + stats + a little variance).
5. **Result** → win/lose, and a **codex unlock** tied to the units/era used.
6. **Progress:** collect codex cards, complete an era, unlock the next.

### 4.2 Combat triangle (the teachable core)
Base triangle, extended per era:
- **Infantry (spearmen)** beat **Cavalry**; lose to **Archers/Ranged**.
- **Archers/Ranged** beat **Infantry**; lose to **Cavalry**.
- **Cavalry** beats **Archers**; loses to **Infantry**.
- **Special/heavy** per era bends the triangle: Immortals (elite infantry), scythed **chariots**, Parthian **horse-archers** (cavalry that shoots — the "Parthian shot"), Sassanian **cataphracts** and **war-elephants**, Safavid **musketeers** and **artillery**, Qajar **field cannon**. Later gunpowder units hard-counter older melee — which teaches *why* Chaldiran and the Qajar wars went the way they did.

### 4.3 Win / lose + "alt-history" hook
- Battles have a **real outcome** (recorded in the codex). The *game* result can diverge — "history says Persia lost Chaldiran to Ottoman cannon; can you rewrite it?" This lets kids lose the game but still learn the true result, and gives replay motivation without falsifying history. The codex always states what *actually* happened.

### 4.4 Eras as factions (draft pools)
Elamite · Median · **Achaemenid** · Seleucid/Hellenistic · **Parthian** · **Sassanian** · early-Islamic Iran · Seljuk/Turco-Persian · Ilkhanid/Mongol · Timurid · **Safavid** · **Afsharid (Nader)** · Zand · **Qajar** · (modern era optional — see §9 sensitivities). Bold = strongest, most iconic starting set for an MVP.

## 5. Content model (data schema)

Everything is **content-as-data** (JSON) so historians/writers can extend it without touching code. Suggested shapes:

```jsonc
// era.json
{ "id": "achaemenid", "name_en": "Achaemenid", "name_fa": "هخامنشی",
  "span": "550–330 BCE", "capital": "Persepolis / Susa / Pasargadae",
  "color": "#6b1f2a", "unlockAfter": "median",
  "signatureUnits": ["immortal","persian-archer","scythed-chariot","cavalry"] }

// unit.json
{ "id": "immortal", "era": "achaemenid", "class": "heavy-infantry",
  "name_en": "Immortal", "name_fa": "جاویدان", "atk": 6, "def": 6, "range": 1,
  "counters": ["cavalry"], "counteredBy": ["archer"],
  "blurb_en": "The 10,000 elite guards, kept always at full strength.",
  "art": "immortal.png" }

// king.json
{ "id": "cyrus", "era": "achaemenid", "name_en": "Cyrus the Great",
  "name_fa": "کوروش بزرگ", "reign": "559–530 BCE",
  "bio_en": "...", "achievement_en": "Founded the empire; the Cyrus Cylinder." }

// battle.json  (also the codex payload)
{ "id": "pasargadae-550", "era": "achaemenid", "year": "550 BCE",
  "name_en": "Battle of Pasargadae", "opponents": ["Persians","Medes"],
  "victor": "Persians", "onIranianSoil": true, "site": "Fars",
  "summary_en": "Cyrus defeats his Median overlord Astyages and founds the empire.",
  "teaches": ["founding of the Achaemenid Empire"], "sourceRefs": ["..."] }
```

The **battle roster in §6 is the seed content** for `battle.json` + `king.json`.

## 6. Historical corpus — battles across all eras (real, seed content)

`✔ soil` = fought on modern-Iranian territory (also usable as a Boutimar itinerary stop). `— abroad` = across a modern border; game/narrative only. **Every date/outcome below must get a fact-check pass before it ships** — these are well-established but history content gets scrutinised.

### Older Persia — Elamite / Median
| Battle | Date | Outcome | Where |
|---|---|---|---|
| Ulai River | 653 BCE | Assyria defeats Elam | ✔ Khuzestan (nr Susa) |
| Sack of Susa | 647 BCE | Assyria razes Elam | ✔ Susa/Shush |
| Fall of Nineveh | 612 BCE | Medes + Babylon destroy Assyria | — Iraq |
| Battle of the Eclipse (Halys) | 585 BCE | Medes vs Lydia, ended by eclipse | — Anatolia |

### Achaemenid
| Battle | Date | Outcome | Where |
|---|---|---|---|
| Pasargadae / Hyrba | 550 BCE | Cyrus beats Median Astyages → founds empire | ✔ Fars |
| Thymbra | 547 BCE | Cyrus beats Croesus of Lydia | — Anatolia |
| Opis | 539 BCE | Cyrus takes Babylon | — Iraq |
| Massagetae (Cyrus's last) | 530 BCE | Cyrus killed (Queen Tomyris) | — Central Asia |
| Bisotun campaigns | 522–521 BCE | Darius I crushes nine rebel kings | ✔ Kermanshah (relief) |
| Marathon | 490 BCE | **Persian defeat** vs Athens | — Greece |
| Thermopylae / Salamis / Plataea | 480–479 BCE | Xerxes: win, then **two defeats** | — Greece |
| Cunaxa | 401 BCE | Artaxerxes II beats Cyrus the Younger; Xenophon's Ten Thousand | — Iraq |

### Macedonian conquest
| Battle | Date | Outcome | Where |
|---|---|---|---|
| Granicus / Issus | 334 / 333 BCE | Alexander beats Persia | — Anatolia |
| Gaugamela | 331 BCE | Alexander beats Darius III | — Iraq |
| **Persian Gates** | 330 BCE | Ariobarzanes' last stand, then falls | ✔ Yasuj/Zagros |
| Burning of Persepolis | 330 BCE | Alexander torches the capital | ✔ Fars |

### Seleucid / Parthian
| Battle | Date | Outcome | Where |
|---|---|---|---|
| **Carrhae** | 53 BCE | Parthians (Surena) annihilate Crassus/Rome — the "Parthian shot" | — Harran (TR/SY) |
| Siege of Phraaspa (Antony) | 36 BCE | Roman invasion of Media fails | ~ NW Iran region |

### Sassanian
| Battle | Date | Outcome | Where |
|---|---|---|---|
| **Hormozdgan** | 224 CE | Ardashir I beats last Parthian king → founds Sassanian Empire | ✔ Fars/Hormozgan (Firuzabad) |
| Misiche | 244 CE | Shapur I beats Roman Gordian III | — Iraq |
| Barbalissos / **Edessa** | 252 / 260 CE | Shapur I **captures Emperor Valerian** | — Syria (relief ✔ Naqsh-e Rostam) |
| Julian's invasion & death | 363 CE | Sassanian strategic win; Julian killed | — Iraq |
| Avarayr | 451 CE | Sassanians vs Armenians (Vardan) — religious war | — Armenia |
| Hephthalite war (Peroz killed) | 484 CE | **Sassanian disaster** in the NE | — NE frontier |
| Nineveh | 627 CE | Heraclius (Byzantium) beats Khosrow II | — Iraq |
| **Nahavand** ("Victory of Victories") | 642 CE | Arabs end the Sassanian Empire | ✔ Hamadan prov. |

### Turco-Persian / Seljuk / Mongol / Timurid
| Battle | Date | Outcome | Where |
|---|---|---|---|
| Dandanaqan | 1040 | Seljuks beat Ghaznavids → new empire | — nr Merv (TM) |
| Manzikert | 1071 | Alp Arslan (Seljuk) beats Byzantium | — E Turkey |
| Sack of Nishapur / Rey / Merv | 1220–21 | **Genghis Khan** razes the cities | ✔ Nishapur, Rey |
| **Siege of Alamut** | 1256 | Hulagu breaks the Ismaili "Assassins" | ✔ Qazvin/Alamut |
| Sack of Baghdad | 1258 | Hulagu ends the Abbasid Caliphate | — Iraq |
| Sack of Isfahan | 1387 | **Timur**; towers of skulls | ✔ Isfahan |
| Ankara | 1402 | Timur captures Ottoman Bayezid I | — Anatolia |
| Otlukbeli | 1473 | Ottomans beat Aq Qoyunlu (Uzun Hasan, Tabriz) | — E Anatolia |

### Safavid
| Battle | Date | Outcome | Where |
|---|---|---|---|
| Ghazdewan | 1512 | **Uzbeks** beat Safavids; Najm-e Sani killed | — Transoxiana |
| **Chaldiran** | 1514 | Ottoman cannon beat Shah Ismail I — fixes the western border & Shia Iran | ✔ W Azerbaijan |
| Jam | 1528 | Tahmasp I beats Uzbeks **with artillery** | ✔ Khorasan |
| **Capture of Hormuz** | 1622 | Shah Abbas I + English EIC take the island from Portugal | ✔ Hormuz I., **Persian Gulf** |
| Recapture of Baghdad | 1623 | Abbas I | — Iraq |
| **Gulnabad** / Fall of Isfahan | 1722 | Afghan Hotaki crush the Safavid army; **end of Safavid glory** | ✔ Isfahan |

### Afsharid (Nader Shah)
| Battle | Date | Outcome | Where |
|---|---|---|---|
| Mehmandoost / Damghan | 1729 | Nader expels the Afghans | ✔ nr Damghan |
| Yeghevard (Baghavard) | 1735 | Nader beats the Ottomans | ~ Caucasus border |
| Coronation at Moghan | 1736 | Nader crowned | ✔ Moghan plain |
| **Karnal** | 1739 | Nader crushes the Mughals → sacks Delhi (Peacock Throne, Koh-i-Noor) | — India |

### Zand & Qajar
| Battle | Date | Outcome | Where |
|---|---|---|---|
| **Siege of Kerman** | 1794 | Agha Mohammad Khan Qajar destroys the last Zand; mass blinding | ✔ Kerman |
| **Aslanduz** | 1812 | **Russia routs Persia** (Abbas Mirza) → Treaty of Gulistan (1813), loss of the Caucasus | ✔ Aras frontier |
| Ganja / Treaty of Turkmenchay | 1826–28 | **Second Caucasus loss** to Russia | — Caucasus |
| Anglo-Persian War / Khushab | 1856–57 | British land at Bushehr; Persia gives up Herat | ✔ Bushehr, **Persian Gulf** |
| **Tabriz Constitutional resistance** | 1908–09 | Sattar Khan holds Tabriz for the Constitution | ✔ Tabriz |

### Modern (handle with care — see §9)
| Battle | Date | Outcome | Where |
|---|---|---|---|
| Anglo-Soviet invasion | 1941 | Allies occupy Iran; Reza Shah abdicates | ✔ nationwide |
| Iran–Iraq War: fall & **liberation of Khorramshahr** | 1980–82 | 34-day fall, then retaken (1982) | ✔ Khuzestan |
| Karbala-5 (Shalamcheh), Fao | 1986–87 | major offensives | ✔ Khuzestan/Arvand |

## 7. Educational layer

- **Codex:** every unit, king, and battle is a collectible card with a short, age-graded blurb, a map pin, and "what really happened." Completing an era's codex unlocks the next era — progression *is* the curriculum.
- **Micro-quiz** between matches (optional, 1 question) for a small reward — retrieval practice.
- **"True or reshaped?"** after each battle: state the real outcome, then let them try to reshape it. Never lets the game's fiction overwrite the fact.
- **Reading level & tone:** two blurb lengths (kid / older) toggled by a profile age. Neutral, non-triumphalist voice — losses taught as plainly as wins.
- **Accessibility:** colour-blind-safe unit types (shape + colour), audio name pronunciations (great for diaspora kids), full RTL Farsi.

## 8. Feasibility — base44 vs Claude Code vs a game engine

**Honest read:**

| Path | Good for | Ceiling |
|---|---|---|
| **base44 (no-code)** | Fastest clickable MVP; hosts the content DB and a **turn-based / hotseat** version well; great for a schools pilot as a web link | Not a game engine — weak on animation, real-time online multiplayer, no push, PWA-only, not in App Store search. An *auto-battler with juice* will fight the platform. |
| **Claude Code + web stack** *(recommended for the real product)* | Full control of the auto-battle sim, animation, content pipeline, bilingual RTL, online multiplayer if wanted | You maintain the code; more up-front build than no-code |
| **Dedicated game engine (Unity/Godot)** | Native iOS/Android, richest juice | Overkill for a card auto-battler; slower iteration; heavier for a solo/small team |

**Recommendation for the hand-off:**
1. **MVP (2–3 wks): hand-built web app**, not base44 — because the whole value is the *battle-resolution engine + content model*, which base44 can store but can't animate. Stack: **React + Vite + TypeScript**, **PixiJS or Phaser 3** for the battle canvas, **Zustand** for state, content in **JSON** (§5). Single-device **hotseat** + **vs-AI**. Ship as a PWA.
2. **Phase 2:** online async multiplayer via **Supabase** (auth, DB, realtime) or **Colyseus** (authoritative rooms) if synchronous.
3. **Phase 3:** wrap the PWA with **Capacitor** for real App/Play store presence if traction warrants.
4. **If Alireza insists on base44 first:** build the **codex + hotseat turn-based** version there as a cheap validator, keep all content in the JSON schema above so it ports out cleanly. Don't attempt real-time online multiplayer on base44.

> Bottom line to tell him: *yes, Claude Code can absolutely build this* — and for an actual game it's the better tool than base44. base44 is the faster way to a rough validator, not the way to the finished product.

## 9. Risks & sensitivities

- **Persian Gulf naming** — non-negotiable (see top). Any Hormuz/Bushehr/coast content says «خلیج فارس» / Persian Gulf.
- **Modern-war content for kids:** keep the **educational kids' core to pre-modern eras** (Elam → Qajar). The Iran–Iraq War is real and huge domestically but is emotionally raw and politically loaded — exclude it from the children's product, or gate it behind an adult "modern era" pack framed as remembrance, never as a toy.
- **Nationalism / neutrality:** teach losses as honestly as wins; avoid triumphalist framing; don't caricature historical opponents (Arabs, Ottomans, Greeks, Russians).
- **Art & IP:** commission or generate original art; do **not** scrape copyrighted game/museum assets. Historical *facts* are free; specific modern illustrations are not.
- **Accuracy:** every codex entry needs a source; run the §6 roster past a historian or solid references before publishing. Mark disputed dates as disputed.
- **App-store review:** war themes + minors can draw scrutiny — lean into the *educational* framing, ratings, and no real-world political messaging.

## 10. Open questions for the hand-off session

1. Platform priority: web-first PWA, or native from the start?
2. Multiplayer: hotseat/vs-AI only for MVP, or online from day one?
3. Monetisation: free (grant/school-funded), one-time paid, or cosmetic packs? (Avoid loot-box mechanics in a kids' educational title.)
4. Which **6 launch eras**? (Suggest: Achaemenid, Parthian, Sassanian, Safavid, Afsharid, Qajar.)
5. Art direction: Shahnameh-miniature style? flat vector? pixel? (Miniature style is distinctive and on-brand for Persian heritage.)
6. Who fact-checks the content — an in-house historian, or a references pass?

## 11. Sources
- Draftshowdown mechanics — https://mwm.ai/apps/draft-showdown/6743368869 · https://game-solver.com/draft-showdown/ · https://www.cityparkgames.com/games/draft-showdown
- base44 game feasibility — https://www.base44guide.io/articles/building-custom-gaming-software-with-base44 · https://www.seeles.ai/resources/blogs/base-44-platform-ai-game-development-seele-comparison · https://base44.com/blog/game-app-development
- Historical battles: to be verified against standard references (Encyclopædia Iranica, Britannica) during content build — **do not publish §6 unchecked.**
