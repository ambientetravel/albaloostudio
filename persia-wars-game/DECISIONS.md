# Persia at War — Decisions Locked (11 Aug 2026)

Answers to the six open questions in `RESEARCH-BRIEF.md` §10, plus the revisions
Alireza made on review the same day. These are settled; re-open only deliberately.

| # | Question | Decision |
|---|---|---|
| 1 | Platform | **Web-first PWA.** React + Vite + TypeScript, PixiJS v8 battle canvas, Zustand state. Capacitor store-wrap only if traction warrants (Phase 3). |
| 2 | Multiplayer | **REVISED — online from day one.** Anyone who opens the game is matched with anyone else on the server. A Node WebSocket matchmaking server ships with the repo (`server/`). vs-AI stays as the offline fallback. Hotseat was **removed**. |
| 3 | Monetisation | **Free, zero commerce code.** No purchase plumbing, no entitlements, no loot boxes. Keeps it school-distributable and out of App Store minors-and-payments scrutiny. |
| 4 | Launch eras | **Achaemenid, Parthian, Sassanian, Safavid, Afsharid, Qajar.** Teaching arc runs bow → horse-archer → cataphract/elephant → musket → combined arms → cannon. Each era carries a famous win *and* a famous loss. |
| 5 | Art direction | **REVISED TWICE — the Achaemenid palette drives the whole UI**, in the Draft Showdown *form* language (chunky rims, top highlights, buttons that press down). Lapis field, gold primary, turquoise secondary, ochre red for danger and for the player's army, stone white text, stone brown ground. Supersedes both the muted miniature scheme and the violet cartoon one. |
| 6 | Fact-checking | **References pass now, historian before public launch.** Every claim carries `sourceRefs`; every contested claim carries a `disputed` note surfaced in-game. |
| 7 | Language | **REVISED — English only.** The bilingual EN/FA model and RTL support were removed on request. |
| 8 | Meta-game | **REVISED — full Clash-Royale-shaped meta.** Lobby, settings sheet, shop and collection, per the supplied reference screenshots. 13 arenas, 25 units, 16 spells, trophy ladder, card levels. |
| 9 | Monetisation (again) | **REVISED — a shop exists, but nothing charges money.** Soft currency (coins, gems) is fully working; every real-money tier is a display-only shell. See "The money question" below. |

## Revisions made on review, 11 Aug 2026

Three changes to the table above, all requested directly:

1. **Online replaces hotseat.** Decision #2 originally deferred networking to
   Phase 2. It is now day one: the menu's first action is PLAY ONLINE, which
   queues the player against anyone else waiting. See "Online play" below.
2. **Palette is cartoon, not miniature.** The reference is Draft Showdown's menu
   — bright violet ground, saturated accents, moulded gold buttons. The old
   ink/parchment scheme is gone from `styles.css` and from the battle canvas.
3. **English only.** Every `{ en, fa }` pair in the content JSON collapsed to a
   plain string, the language toggle and `dir` switch are gone, and
   `src/i18n/` was deleted. Restoring bilingual support means turning those
   `string` fields back into pairs — the schema comment in `content/types.ts`
   says so, so nobody has to rediscover it.

## The money question — read before wiring a payment provider

Decision #3 was "free, zero commerce code". The shop reverses that, and the shop
is built. But three things stop short of a live storefront, deliberately:

1. **Nothing charges money.** There is no payment provider, no store SDK, no
   receipt validation, no age gate. Every euro-priced button opens a dialog
   saying exactly that. Coins and gems earned by playing are real and spend.
2. **No randomised paid packs.** The reference game's Bit Packs give a variable
   number of cards for gems. Here each pack states its exact contents. A
   randomised paid pack is a loot box, and Belgium and the Netherlands have
   treated those as gambling; the UK and EU consumer-protection bodies keep
   circling them. Brief §9 already ruled them out for this audience. Flat,
   disclosed bundles get the same shop slot without the exposure.
3. **No rewarded video ads.** The reference gives away coins for watching one.
   That needs an ad network, and for a 9–14 audience it needs a parental-consent
   flow and a kids-safe ad inventory before a single impression is served.

None of that says do not monetise. It says the parts that need legal and
compliance decisions are the parts I left as a shell, so the decision stays
yours and nothing ships half-wired. What is needed before it goes live:

- An age gate and, for under-13s in the US, a COPPA-compliant consent flow.
- App Store / Play kids-category review — both restrict IAP and ads for children.
- A named legal entity for the Terms and Privacy pages (both are stubs).
- Player-name moderation. Still outstanding, still important.

## Loading screen and motion

Framer Motion (13.1) drives the intro. The splash is a layered SVG so each band
— far ridges, mid ridges, city, foreground dunes — drifts at its own speed and
the scene has depth. The title animates in letter by letter, then a brightness
flare travels through the glyphs.

**Drop the commissioned key art at `public/art/anshan-splash.png`** and the
loading screen switches to it automatically, with a slow push-in instead of
parallax (a single flat image cannot parallax). No code change needed — it
probes for the file on mount and falls back to the placeholder if absent. The
caption drops the word "placeholder" once the real art is in.

`?boot=20000` in the URL holds the splash open for design review.
`prefers-reduced-motion` is honoured: the entrance and the flare both stop.

Of the three tools in the `website-builder-setup` skill, only Framer Motion was
installed. UI/UX Pro Max ships 161 colour palettes and 57 font pairings for
landing pages — this project has one locked palette and would only be fought by
it — and 21st.dev Magic is a React component library for marketing sites that
needs an API key.

## Arena media and the battleground

Each of the thirteen grounds has a media slot, filled or not:

```
public/art/arenas/<slug>.mp4    the battlefield's loading film
public/art/arenas/<slug>.png    lobby still
```

**The clip is the loading screen, not a lobby background.** It plays full-bleed
on the matchmaking screen while the battlefield loads and an opponent is being
found, runs to its natural end, then fades off to reveal the result of the
search. That is also what times the hunt: when the film ends and nobody has
turned up, the computer is offered. With no film for an arena it falls back to a
plain 8-second wait.

`anshan.mp4` is in (10s, 720×1280). The lobby uses a **still** instead — the
panel there needs to sit calmly behind the BATTLE button, and a looping video
fights it. Arenas with no still get a themed skyline in their own colours.

## Every battleground re-skins the game

Climbing the ladder changes the whole interface, not just a panel. Each arena
carries a theme in `src/ui/arenaTheme.ts` — background gradient, panel surfaces,
rims, and a signature accent — written onto the document root as the same
semantic tokens the stylesheet already uses. One variable swap re-skins every
screen at once, so there are thirteen themes rather than thirteen stylesheets.

Anshan is sand and mud-brick under a pale sky. Ecbatana is watered green.
Babylon is glazed blue. Susa is hot yellow-green. Persepolis is gold on lapis.
The Persian Gates is winter rock with an ochre accent. Every colour is a blend
of the six Achaemenid palette hues.

Two things deliberately do **not** change, so the game stays recognisable and
readable wherever you are standing:

- gold stays the primary action, so BATTLE is always the same button;
- text stays stone white on a dark surface, so contrast never depends on which
  arena the player happens to be in.

During a match the theme follows the **match's** arena (the server's, online);
everywhere else it follows the player's own rung.

**The ground you fight on is your rung of the ladder, not the scenario.** At
0 trophies that is Anshan, so Anshan is the first battleground. The scenario
(Pasargadae, the Persian Gates) still supplies the units, the terrain rules and
the codex payload — the arena supplies the place. The battle header names both.

Arena 1 is drawn as a built arena rather than open country: a lapis-and-gold
fighting platform with a patterned centre medallion and gilded corner posts,
set into a mud-brick city, matching the key art. Arenas 2–13 use the scenario's
own terrain until each gets its own treatment.

## The draft pool is gated by arena

**Decided.** The draft pool is every verified unit of the era that the scenario's
date allows *and* the match's arena has unlocked. Anshan drafts from four cards;
the Persian Gates drafts from all twenty-five.

Two gates that teach different things, and they stack rather than replace:

- the **date** gate is history — no scythed chariot at Pasargadae in 550 BCE;
- the **arena** gate is progression — the ladder widens the roster as you climb.

**The arena is a property of the match, never of a player's collection.** That is
the whole reason this is safe: the server derives the identical pool and can keep
validating a pick it never sent. Drafting from a private deck would force the
server to trust each client's inventory over the wire and give the scheme away.

For an online match the server takes the **lower of the two players' arenas**, so
a beginner never faces cards they have not unlocked. Verified over the live
socket: a rookie (arena 1) against a veteran (arena 13) played at arena 1, both
clients agreed on it, every pick came from the four-card pool, and the veteran's
attempt to pick an arena-13 card was rejected with "That card was not on offer".

Two tests hold the line: client and server pools are asserted equal for **every
arena × every scenario**, and arena 1 must offer more cards than an offer is wide
so the bottom of the ladder still presents a real choice.

**Known limitation.** With no server-side accounts the arena is whatever the
client claims. Overstating it only helps against an opponent who is already
higher, and it cannot touch anyone else's ladder — but the real fix is persisted
profiles on the server, which do not exist yet.

The draft screen now names the pool ("Drafting from 4 cards unlocked in Arena 1:
Anshan") and lists the next cards waiting further up, so a thin pool reads as
progress rather than a missing feature.

**Still unresolved: the deck.** The four-card deck in the collection does not
feed the draft — it cannot, for the reason above. Right now it is progression and
codex only, and the lobby's "Your deck · Change" over-promises. Either rename
that strip to something honest, or give the deck a real job (a starting hand, a
ban, a reroll) that does not require the server to trust it.

## The computer opponent

Until there is a real player base, nearly every match is against the computer,
so it is built to behave like a person:

- **It has a name and a badge.** Names are drawn from Achaemenid history and the
  satrapy lists — Vishtaspa, Atossa, Gobryas, Irdabama — so the roster teaches
  something even as a nameplate. Both are derived from the match seed, so a
  replay shows the same face.
- **It hesitates unevenly.** Think time grows with the pick number, varies by a
  wide random factor, and roughly one pick in five is near-instant. Measured
  live: 733, 980, 1828, 1829 ms across one draft. A fixed delay reads as a
  machine immediately.
- **It makes mistakes, less often as you climb.** Skill runs from about 0.35 in
  Anshan to 0.85 at the Persian Gates. Below that threshold it takes the second-
  or third-best card — which is what a person does when a card simply looks good.
- **BATTLE falls back to it.** The matchmaking screen hunts for a human for
  eight seconds, then offers the computer. If the server is unreachable it
  offers immediately. Nobody is left staring at a spinner.

**It is always labelled `computer`.** A child should never be unsure whether the
opponent is a person. That costs nothing and is the kind of thing a game for
nine-year-olds should get right — so the human-like behaviour is in the timing
and the mistakes, never in pretending to be someone.

## Sharing a test build

`npm run share` builds the game and runs one process that serves the static
build **and** the multiplayer sockets on a single port, printing the LAN address
for the team. A plain static host would have shipped a dead BATTLE button:
online play needs this process alive.

Three things were fixed making it shareable, all of which would have hit testers:

1. **A stale service worker white-screened the app on every new build.** The
   worker was cache-first for everything including the document, so a cached
   `index.html` kept pointing at hashed JavaScript that no longer existed and
   the page died with a MIME error. Navigations are network-first now; hashed
   assets stay cache-first, which is safe because a new build asks for new
   filenames.
2. **A busy port crashed with a stack trace.** When the sockets ride an HTTP
   server, `ws` re-emits the HTTP server's errors on itself, and the handler was
   only on the HTTP server. It now prints one line and the remedy.
3. **The feedback widget shipped in normal builds.** `lazy()` emits the chunk
   whatever the flag says, so gating on a runtime boolean was not enough. Vite
   now aliases the module to a stub unless `VITE_TEST_BUILD=1`, and both states
   are verified by grepping the built output.

Feedback is captured in-app and exported as one markdown file. There is no
backend: adding one for an internal test would mean standing up storage and a
privacy story for a children's product, which is not worth it before the game
is worth testing at scale.

## Hosting it

`Dockerfile`, `fly.toml` and `render.yaml` are written; [DEPLOY.md](DEPLOY.md)
has the commands. The deploy itself was not run — this machine has no host CLI
and no account credentials.

**A static host cannot serve this.** Online play needs a live process holding
open sockets, and the game and sockets must share an origin. That rules out
Netlify, Pages, and any plan that sleeps on idle, because a cold start drops
every socket and ends every match in progress.

Exposing it to the internet needed guards a LAN build did not:

| Guard | Why |
|---|---|
| Basic-auth gate + signed cookie | Keeps a team test a team test. The cookie exists because browsers do not resend Basic credentials on a WebSocket handshake. |
| Origin allowlist on the upgrade | Otherwise any website could open a socket from a visitor's browser into the matchmaking queue. |
| Name moderation | Names are the one free-text field one player shows another, and the audience is 9–14. |
| Per-IP and total connection ceilings | The process holds every player in memory. |
| Health endpoint outside the gate | Or the host restarts a healthy server forever. |
| Request handler cannot throw | See below. |

Two bugs found by testing the hardening, both of which would have been live:

1. **One unauthenticated request crashed the whole server.** The Basic-auth
   realm contained an em-dash; HTTP header values are latin1, so Node threw
   `ERR_INVALID_CHAR` and the process died — on the first stranger to open the
   URL without the password. Fixed, and every request handler is now wrapped so
   nothing else can take the process down.
2. **The profanity list silently missed its worst entries.** The normaliser
   collapses repeated letters, so an input of "nigger" arrives as "niger" — and
   the raw list entry never matched. Every banned word containing a double
   letter was inert. Both sides now go through the same normaliser, with
   regression tests.

## Glass over the arena

On the meta screens the arena's own art sits behind the whole interface,
enlarged and pushed back, and the panels above it are translucent — so the lobby
reads as standing *in* Anshan rather than looking at a picture of it.
`src/ui/ArenaBackdrop.tsx` plus the glass rules at the end of `styles.css`.

What is deliberately **not** glass, because legibility comes first:

- **buttons** stay solid — they are the actions and have to pop;
- **the lore scroll** stays parchment — it is paper, not glass;
- **currency pills** stay solid — small text over a photo is the first thing to
  become unreadable;
- **the arena panel's own picture** stays fully opaque and unblurred. It is the
  one sharp window onto the ground; glassing it would defeat having it.

Two passes were needed. The first blurred and dimmed the backdrop so hard
(`blur(9px)`, 72% brightness, a heavy full-height scrim) that it became a flat
tan wash — a duller gradient, not Anshan. Now the blur is 4px and the scrim is
heavy only where the interface needs it: the top band under the currency pills
and the bottom band under the navigation, with the middle left open.

The second pass fixed the title block. It sits directly on the backdrop with no
panel beneath it, so its two dim grey lines were the first casualties of putting
a photograph behind them. A soft radial plate behind the whole block fixes all
three lines at once without dropping a hard-edged box into the middle of the
composition.

Browsers without `backdrop-filter` get solid panels via `@supports not`, rather
than transparent unreadable ones.

## The game frame

The whole app sits inside an ornate border drawn in `src/ui/GameFrame.tsx` —
cuneiform tick strips top and bottom, gold rules down the sides, a lion in each
top corner. It is procedural rather than a bitmap so it scales to any viewport
without a nine-slice and recolours with the arena theme: the frame at Babylon is
the same carving in Babylon's metal.

The bottom two lions were dropped once the navigation moved inside the frame —
they occupied exactly those corners. The bottom band keeps its cuneiform strip,
so the frame still closes.

## The meta-game

Built to the reference screenshots:

- **Lobby** — rebuilt to the supplied mockup: name pill and purse across the
  top; a titled arena plate flanked by two character medallions; trophy bar;
  arena stepper; the battleground panel; the arena's lore on a parchment scroll;
  deck strip; a very large BATTLE button; PRACTICE beneath it.
- **Trophies** — the thirteen grounds as a ladder, each with its date, place,
  trophy requirement and what it unlocks. It doubles as the timeline, because
  the rungs are chronological.
- **Settings sheet** — two tabs. Profile: name with pencil edit, badge picker,
  banner colour from the Achaemenid palette, reading level, and a six-cell stats
  grid (wins, losses, win rate, best trophies, cards collected, battles).
  Settings: SFX and music sliders, haptics, and the legal/account rows. All the
  Settings-tab rows are honest stubs that say so when tapped.
- **Shop** — four tabs: Offers, Card Packs, Gems, Daily.
- **Collection** — Units and Spells tabs, a four-slot battle deck you edit by
  tapping a slot then a card, 25 unit cards and 16 spell cards with arena locks,
  card levels and duplicate-to-upgrade progress.

**Card levels do not affect battles.** Two reasons: online matches stay in
lockstep only because both clients simulate the same squads from the same seed,
and a card you ground for should not beat a card you understood. Levels drive
collection progress and nothing else. Reversing that means making the server
authoritative over stats first.

## The 25 units and 16 spells

**Units are history.** All 25 are attested. The seven from the first pass are
unchanged; the eighteen new ones come from Herodotus' catalogue of Xerxes' army
(Book VII, chapters 61–88, read in the Godley translation) plus Cunaxa and
Gaugamela for the late arrivals. Nothing was invented to fill the roster — the
Sagartian lassoer, the Assyrian iron-studded club and the Ethiopian stone-tipped
arrows are all in the text. Every one of them carries a shared `disputed` note
saying that Herodotus' catalogue is a literary set-piece whose equipment is
better evidence than its numbers.

**Spells are legend, and labelled as such.** The 16 Zauber come from the
Shahnameh and the Avesta. They carry `kind: "legend"`, they are all
`verified: false`, and none of them can be played. Opening one shows a banner
saying it is a story rather than an event and has not been fact-checked. That
distinction is worth keeping even after they are verified — a game teaching
Iranian history should be the thing that tells a child which is which.

A test enforces the whole arrangement: unverified content cannot enter a draft
pool, an arena unlock, or a card reward.

## Online play — how it is built

- **Server:** `server/index.ts`, Node + `ws`, default port 5184 (`WS_PORT`).
  Node runs the TypeScript directly via type stripping, which lets the server
  import `src/sim/draftCore.ts` — so the draft rules exist in exactly one place.
- **What the server does:** pairs waiting players, assigns the match seed,
  enforces turn order, and validates each pick against the offer it derives
  itself from `(seed, step)`. A 25-second turn timer auto-picks so nobody can
  freeze a stranger's game by walking away.
- **What the server does not do:** simulate battles. Both clients hold the same
  seed and both squads and run the identical deterministic sim locally. Verified:
  two browser tabs finished a match with byte-identical logs.
- **No accounts.** A profile is a name plus a badge in `localStorage`. Names are
  sanitised on the client and again on the server.
- **Offline is a first-class state.** If the server is unreachable the menu greys
  out PLAY ONLINE, says "Server unavailable", and vs-AI carries on untouched.

## Still outstanding before any public launch

- **Name moderation.** `sanitizeName` is a shape check — letters, digits, spaces,
  `-` and `_`, capped at 14 characters. It is **not** a profanity filter, and this
  is a children's product where names are shown to strangers. A blocklist or a
  moderation service is required.
- **No abuse controls.** No rate limiting, no reporting, no blocking, no rooms.
- **Deployment.** The server runs locally only. It needs a host, `wss://`, and an
  origin check before it faces the internet.

## The Achaemenid palette — the whole UI

The supplied sheet (MXR-ACH-01 … 06) is now the entire colour scheme. The violet
cartoon scheme is gone.

| Code | Name | Original | Hex | Where it does the work |
|---|---|---|---|---|
| MXR-ACH-01 | Imperial Lapis | لاجوردی شاهنشاهی | `#1f3b6e` | The field, every panel, the battle sky |
| MXR-ACH-02 | Achaemenid Gold | طلایی هخامنشی | `#d4a22b` | Primary action, card faces, the horizon rule |
| MXR-ACH-03 | Stone White | سفید سنگی | `#ede8db` | All body text — warmer than pure white |
| MXR-ACH-04 | Persian Turquoise | فیروزه پارسی | `#2e9c9a` | Secondary action, purchases, side B's army |
| MXR-ACH-05 | Stone Brown | قهوه‌ای سنگ | `#7a5b45` | The ground the battles are fought on |
| MXR-ACH-06 | Ochre Red | قرمز اخرایی | `#b8412a` | Danger, losses, and side A's army |

Six flat colours cannot carry rims, highlights and depth on their own, so each
hue has two or three derived steps (`--lapis-hi`, `--gold-rim`,
`--turquoise-deep`, and so on). Every one of those is a tint or shade of a
palette colour — nothing outside the six was introduced.

**What kept the cartoon feel** is the *form* language, not the colours: thick
dark rims, an inner top highlight on every raised surface, buttons that press
down 4px, generous corner radii, heavy type with a dark shadow. That is what
makes the interface legible to a nine-year-old, and it survives the recolour.

**The colour surface is exactly three files.** If the original sheet has precise
hex values, change them in all three and nothing else needs touching:

- `src/ui/palette.ts` — the banner picker, and the reference copy of the sheet
- `src/styles.css` — the `:root` token block
- `src/render/silhouettes.ts` — the `PALETTE` object Pixi draws the battle with

The one exception is the Sign in with Apple button, which stays black and white
because Apple's brand guidelines require it.

## Art status — read before shipping anything public

No commissioned art exists yet. The battle canvas, unit cards and player badges
render **procedural placeholder shapes** (`src/render/silhouettes.ts` for the
canvas, `src/ui/UnitGlyph.tsx` for the DOM). They are marked as placeholders in
the code and in the UI. They are not the art direction — they are a stand-in so
the loop is playable and testable.

Per §9 of the brief: commission or generate original art. Do **not** scrape
museum or game assets.

## Content rules enforced in code

- **Persian Gulf.** Never "Arabian Gulf". A unit test
  (`src/content/content.test.ts`) fails the build if the string "Arabian Gulf"
  appears anywhere in the content data.
- **No invented facts.** Every `battle`, `king` and `unit` record requires a
  non-empty `sourceRefs`. The same test fails the build if one is empty.
- **Disputes are shown, not hidden.** `disputed[]` entries render in the codex
  under "چه چیزی مورد اختلاف است؟ / What's disputed".
- **Modern wars excluded.** Content data stops at Qajar. The Iran–Iraq War is
  not in the dataset and must not be added to the children's core (§9).

## Two corrections to the brief's §6 roster, found during the references pass

1. **Pasargadae 550 BCE is not a clean battlefield win.** The contemporary
   Babylonian evidence (Nabonidus Chronicle, Nabonidus' 6th year) says Astyages
   mobilised against Cyrus and *his own army mutinied*, bound him, and handed him
   over; Cyrus then took Ecbatana. A pitched "battle of Pasargadae" comes from
   Greek tradition centuries later (Strabo places Cyrus's victory "among the
   Pasargadae"). The date is also contested — 550 by the Chronicle, 553 by the
   Sippar Cylinder. Both are recorded in `battles.json` as `disputed`.
2. **Scythed chariots do not belong in a 550 BCE army.** First firm attestation
   is Cunaxa, 401 BCE. Xenophon's *Cyropaedia* credits Cyrus the Great with
   inventing them, but the *Cyropaedia* is a didactic romance and they are absent
   from the Greek campaigns of Darius and Xerxes. Handled with a per-unit
   `earliestAttested` gate, so the draft pool at Pasargadae excludes them and the
   pool at the Persian Gates includes them. The gate shows the player *why*.

## Scope of the current vertical slice

Achaemenid era only. Two scenarios (Pasargadae 550 BCE, Persian Gates 330 BCE),
seven units, four codex figures. Full loop: profile → draft → auto-battle →
result → codex unlock, playable online against a stranger or offline against the
AI. Do not expand to the other five eras until this is signed off.

---

# M1 — the round loop (Concept v0.2 §11)

The single eight-pick draft is gone. A match is now up to seven rounds, first to
four. `sim/draft.ts` and `sim/draftCore.ts` are deleted rather than kept
alongside — two draft systems would have drifted, which is exactly the failure
CLAUDE.md warns about.

## Decisions taken, and why

1. **Picks inside a round are simultaneous.** Concept v0.2 §2.5 proposed that the
   round's loser pick second and see the winner's card. That is a comeback
   mechanic and it ships with the rest of them in M3. Simultaneous picks halve
   the round, remove the dead "waiting for your opponent" window the old draft
   had, and are simpler to make safe on the wire — the server holds both picks
   and releases them together, so the first pick can never inform the second.
   Verified: a deliberately slow client never receives its opponent's card
   before choosing.

2. **Tiers moved from M2 into M1.** Slot B of every offer is "a tier-up of
   something you already field", so without tiers the three-slot offer is
   incoherent and the Ledger does nothing. M2 keeps the Upgrade and Doctrine
   *card kinds*, traits, and the confidence migration.

3. **A duplicate raises the tier; it never joins twice.** Levy → Trained →
   Veteran → Royal, ×1.0 / 1.25 / 1.55 / 1.9 on attack, armour and health alike
   so the card stays recognisable. Caps by round — II from 3, III from 5, IV only
   in 7 — so an early lead cannot compound into an unanswerable Royal squad.
   Verified: a Trained squad beats a Levy of the same card ~80% of the time, and
   a Royal archer still loses to Trained cavalry, because the triangle outranks
   the ladder.

4. **The warband is the seed pool, not the offer pool.** This closes the
   deck-versus-draft question that had been open since the first build. One card
   of each offer is drawn from the player's deck, one is a tier-up from the
   Ledger, one is an arena wildcard weighted (at most 2×) toward answers to what
   the opponent is fielding. The deck shapes a match without deciding it.

5. **Exhaustion.** Two shield-bearers alone took the better part of a minute to
   kill each other, which no round budget can hold. Past 55% of a round every
   strike lands progressively harder, reaching ×3 at the end. It guarantees a
   round terminates, and it is the honest reading of ancient battle: lines broke
   through exhaustion and loss of cohesion, not by fighting to the last man.
   Without it, rounds time out on a health comparison, which is a coin flip
   wearing a uniform.

6. **The server still never simulates — and now it cannot even see the score.**
   It holds picks, validates them against offers it derives itself, and learns
   each round's winner from *both* clients. Two clients reporting different
   winners is a desync, and the match is stopped rather than allowed to drift.
   This is the cheapest desync detector available and it costs one message.
   Verified live: a sabotaged client is caught and both sides are told.

## Bugs found by verifying rather than assuming

- **The battlefield rendered into a 1639px canvas inside a 500px box.** The
  match screen had `min-height` rather than a definite `height`, so the
  battlefield's grid row was content-sized — while the canvas inside it asked
  for 100% of that row. The ResizeObserver fed each measurement back in and the
  renderer settled far outside the visible area, drawing the whole battle
  off-screen. A definite height breaks the loop.
- **Three separate `str.replace` edits to `server/index.ts` silently did not
  match** and left the old draft code in place. The server booted and then
  crashed on the first pick. Every server edit is now checked by booting it and
  driving a real match through it, not by reading the diff.
- The nameplate was clipped to one letter at 375px: the avatar and the "cpu"
  tag left nine pixels for the name. The corner is now stacked, not a row.

## Still outstanding after M1

- Upgrade and Doctrine cards, traits, and the five-level confidence migration (M2).
- Commanders and the comeback system — A widened offer, B Rally reroll, C
  counter weighting — are M3. The offer's 2× counter weighting is in already as
  the quiet floor.
- Formation placement between the offer and the fight is specified but not built.
- `RecordedRivalDecisionProvider` (M6).

## What M1 measured

Two hundred computer-versus-computer matches, ~1,000 rounds:

| Measurement | Result |
|---|---|
| Rounds that ran to their time limit | **0 of 1,011** |
| Combat per round | 9.4s (round 1) → 14.9s (round 6) |
| Round budget | 22s → 34s |
| Mean rounds per match | 5.05 |
| Total combat per match | mean 61s, worst 121s |
| **4–0 sweeps** | **43%** |

Two things fall out of that.

**The exhaustion ramp works.** Not one round in a thousand was decided by
comparing health bars. Every round ended with a side broken on the field, which
is what the mechanic was for. The budgets are comfortable ceilings rather than
the usual case.

**Concept v0.2 finding 1.2 is confirmed, with a number.** Between evenly matched
players a first-to-4 should sweep 4–0 about 12.5% of the time. Two equally
skilled computers sweep **43%** of the time. A composition that beats the other
one keeps beating it, round after round, exactly as the audit predicted — and
the 2× counter weighting on offer slot C is not enough on its own. This is the
number M3's comeback system exists to move, and it is now pinned in
`sim/pace.test.ts` so it cannot quietly get worse.

---

# M2 — the card system (Concept v0.2 §4, §7, §11)

Two new card kinds, and the five-level confidence scale replacing `verified: boolean`.

## Decisions taken, and why

1. **A rank goes up; a trait goes sideways.** This is the fix for audit finding
   1.3, where a duplicate pick and an Upgrade would both have just made a squad
   stronger and one of them would have become dead weight. A duplicate raises
   rank (numbers). An Upgrade grants a trait (behaviour) and **never** touches
   rank. A Doctrine changes the whole army. Pinned by test in three directions:
   an upgrade adds a trait and leaves the rank alone, a duplicate raises the rank
   and leaves the traits alone, and a doctrine touches neither squad.

2. **Ranks and traits share slot B of the offer.** They are the two ways to
   improve something you already field, so putting them in the same slot makes
   the player choose between going up and going sideways every time it appears.
   A player who always takes the rank is making a choice, not missing a mechanic.

3. **The upgrade's target is chosen by the game, not the player** — the first
   fielded squad of an eligible class that lacks the trait, in draft order. Both
   clients and the server reach the same ledger from the same pick, and the offer
   card names the target so it is never a surprise.

4. **Every trait costs something.** No card is simply better:
   Ready Volley shoots sooner and is caught flat-footed; Locked Shields holds
   horses but will not pursue past the middle of the field; Long Reach strikes
   first in a clash and does nothing at range; Wheeling Line arrives late on the
   flank; Loosed Rein runs faster away and slower in; The Centre Holds firms the
   middle by thinning the wings; Shoot the Horses answers the cavalry while
   nothing answers the centre; Broken Ground wins a gorge and loses a plain.

5. **`verified: boolean` is gone.** A yes/no flag could not tell a contemporary
   inscription from a Greek story written five centuries later, and that
   difference is the game's whole premise. Five levels now: attested, probable,
   traditional account, reconstructed for gameplay, fictional. Shown on the card
   in the codex, and explained in the Scrolls.

6. **The migration was mechanical and is stated in the file**, so it is
   auditable: a record already flagged with a dispute became *probable*, an
   uncontested one *attested*, and the Shahnameh cards *traditional account* —
   real as stories, which is exactly what that level is for. **Nothing was
   upgraded in standing.** Only three units come out as *attested*; that is
   honest, because most of the Achaemenid roster rests on Herodotus. Moving a
   record from probable to attested needs the specialist review in
   CONCEPT-v0.2 §10.

7. **Upgrades and Doctrines carry no date gate.** A way of fighting is not a
   piece of equipment, so no scenario's year rules one out — only the ladder
   does. They are labelled *reconstructed for gameplay* and each says in its own
   disputed list that the name is ours, enforced by a test: an invented card that
   disputes nothing fails the build.

## A bug the tests found that reading would not have

**Locked Shields promised something the unit already had.** The trait added
`cavalry` to the squad's counter list — but every one of the twelve infantry
cards in the game already counters cavalry, so the line was dead code and the
card's stated benefit was already true without it. The test could not even show
it working, because plain infantry already beats cavalry 100% of the time.

Fixed by giving the wall **armour against mounted attackers specifically**, on
top of the triangle, and by measuring the trait in *health remaining* rather
than in win rate — a win-rate comparison against a matchup that is already
saturated can never show anything.

## Still outstanding after M2

- Commanders and the comeback system (M3). The 43% sweep rate from M1 is
  untouched and is still the number M3 has to move.
- Formation placement between the offer and the fight.
- A player-chosen upgrade target, if playtesting shows the automatic one frustrates.
- The specialist pass in CONCEPT-v0.2 §10, which is what can move any record
  from *probable* to *attested*.

## What M2 measured

Two hundred computer-versus-computer matches, same harness as M1:

| Measurement | M1 | M2 |
|---|---|---|
| **4–0 sweeps** | 43% | **34%** |
| Mean rounds | 5.05 | 5.14 |
| Combat per match | 61s | 58s |
| Rounds run to the time limit | 0 / 1,011 | 6 / 1,028 |
| Picks that were a trait or a doctrine | — | **23%** |

**The card system moved the snowball on its own.** Nine points off the sweep
rate, with no comeback mechanic added — because a player being beaten now has
more answers available than "draft another unit", and a doctrine or a trait can
change a losing matchup without needing the right counter to show up. That was
not the goal of M2; it is a side effect worth knowing about, and the bound in
`sim/pace.test.ts` has been tightened from 0.55 to 0.42 to hold it.

Still a long way from the 12.5% two evenly matched players should produce. M3
owns the rest.

---

# M3 — commanders and the comeback (Concept v0.2 §3, §5, §11)

Two commanders with genuinely different kits, and all three comeback systems.

## Decisions taken, and why

1. **A commander's order fires by itself.** v0.1 §7 asks for "one visible
   tactical order charged during the match", which means a button pressed
   mid-combat. That contradicts the game's own printed rule — *once the squads
   are set, the battle plays itself; the draft was the game* — and online it
   would need a mid-combat message whose exact tick both clients agreed on, or
   the match desyncs. So an order fires automatically at a **trigger printed on
   the commander's card**: Cyrus when your first squad falls, Astyages when you
   are two squads down. Predictable, plannable, deterministic, and it keeps the
   auto-battler premise honest. **Flagged for the product owner** as a
   deliberate deviation from §7.

2. **The comeback triggers on score deficit, not consecutive losses** — finding
   1.7. A consecutive-loss trigger arrives at the point where it can least
   change the result, and the deficit is what a player actually feels.

3. **All three systems shipped together**, as §3 recommended:
   - **A** — one behind, four cards; two or more behind, five.
   - **B** — the Rally: two rounds without a win and you hold a reroll. You
     choose when to spend it, it clears on any win so it can never bank, and
     **the opponent is told when you use it**. A comeback they cannot see is
     the rubber band §8 is trying not to be.
   - **C** — the wildcard's counter weighting rises from 2× to 3× while behind.
     Disclosed in the Scrolls, because a rule the player can read is not a
     hidden hand on the scale.

4. **Nothing touches damage, and that is enforced mechanically.** A test greps
   `sim/battle.ts` for `score`, `deficit` and `rally` and fails if any appears.
   The simulation has no way to know who is winning the match, so §8's "no
   secret damage bonus" cannot be violated by accident.

5. **Astyages is the only thing in the game allowed to break the rank cap.**
   His passive puts an already-Trained card in front of him in rounds 1 and 2,
   when the cap is Levy. That is his entire identity — he starts ahead and has
   to close before a wider army outlasts him — and the cap test now pins it as
   the single documented exception rather than being loosened.

6. **The kits are game design and the records say so.** Both men are attested;
   neither is recorded using a battlefield doctrine of any kind. Each commander's
   `disputed` list states that the passive, order and affinity are ours.

## The bug that cost an hour

Client and server disagreed on one card of one offer, three rounds into an
online match. The cause was not in the game: **the wire carries a card's id and
nothing else**, and each side recovers the full card from its own derived offer.
Two fields never cross the wire — Astyages' `startTier` and an upgrade's
`target` — so a card rebuilt from a bare id silently lands at the wrong rank,
and the ledgers diverge a round or two later with no error at the point of
failure.

The real client was always correct; my verification harness was not. The
invariant is now pinned by a test that asserts a rebuilt card lands at rank 1
where the real one lands at rank 2.

## What M3 measured

Two hundred matches, commanders alternating sides so the result is not measuring
who drafts first:

| Measurement | M1 | M2 | M3 |
|---|---|---|---|
| **4–0 sweeps** | 43% | 34% | **28%** |
| **Cyrus win rate** | — | — | **47.7%** (95 of 199 decided) |
| Offers widened by comeback A | — | — | 32.6% |
| Offer windows holding a Rally | — | — | 19.9% |

**The acceptance criterion is met**: neither commander is above 55%. Cyrus 47.7%,
Astyages 52.3% — inside the band, and close enough that the difference is not
distinguishable from noise at this sample size.

The sweep rate has come down 43% → 34% → 28% across the three milestones. The
remaining gap to the 12.5% two evenly matched players would produce is now
mostly the computer drafting consistently well rather than the format
snowballing — a human field will look different, and that is what a playtest is
for.

## A layout bug the widened offer exposed

Comeback A hands the trailing player five cards. The offer grid was built for
exactly three, so cards four and five fell off the bottom of the sheet and took
the Rally button with them — a comeback system the losing player could not
reach. Fixed by laying out 4 as 2×2 and 5 as 3+2, and compacting the cards when
the hand is wide: at five across a card is 95px wide and a counter list like
"Heavy infantry, Infantry, Elephant" wraps to six lines on its own.

## Still outstanding after M3

- Formation placement between the offer and the fight (specified, not built).
- Rotating commander access for ranked — finding 1.6. Nothing is purchasable
  yet, so there is nothing to gate; it matters the day commanders can be bought.
- Harpagus, held back until his dossier exists — defection is the most
  historically loaded mechanic in Book One.
- The Chronicle campaign (M4–M5) and recorded rivals (M6).

---

# M4 — the Chronicle frame (Concept v0.2 §9, §11)

Book One of the campaign: the mission map, the setup and "what we know" cards,
the reward model, and the capital.

## Decisions taken, and why

1. **A campaign mission is shorter than a ranked match.** Fourteen missions at
   four-to-six minutes each is eighty minutes of first-to-4, which nobody
   finishes. Missions ramp: first-to-2 for the opening teaching beats,
   first-to-3 through the middle, first-to-4 for the finale. `WINS_NEEDED` is
   now a parameter rather than a constant, and everything derived from it — the
   round ceiling, the rank cap — scales with it, so a first-to-2 cannot run to
   seven rounds and is not stuck at Levy the whole way.

2. **Missions unlock strictly in order.** A book that can be played out of
   sequence cannot tell a story, and this is a story before it is a ladder.

3. **Three objective types, because "win the battle" cannot carry the book.**
   `defeat` is the normal one. `choice` is a decision with no battle at all —
   mission 4's Tribal Council, where the branch you take is the outcome.
   `survive` is the important one: **mission 10 is won by taking a single round**,
   so a 1–2 scoreline reads *"You got them out"* and completes the mission.
   Verified live. A campaign that only ever rewards annihilation cannot teach
   that a withdrawal was sometimes the right answer, which is most of what
   actually happened in most campaigns.

4. **Rewards are breadth and nothing else** — v0.1 §5.1. A mission can give a
   card, a trait, a doctrine, a commander or a piece of the capital. There is no
   code path in which finishing a mission makes a card you already own hit
   harder, and the result screen says so on the reward itself.

5. **The book mostly hands out ways of fighting rather than units.** Book One is
   a small Persian revolt in 550 BCE; most of the unit roster is empire-wide and
   postdates it by decades or centuries. Upgrades and doctrines carry no date
   gate — a way of fighting is not a piece of equipment — so they are the honest
   thing for this book to grant. All five upgrades and all three doctrines come
   from Book One; only four units do.

6. **The capital is cosmetic, and that is enforced.** A test greps the battle
   simulation for `capital`, `campaign` and `mission` and fails if any appears.
   Pasargadae grows from a camp as the book runs and never touches a number.

7. **The book says it is a reconstruction before the player reads a mission
   name.** v0.1 §11 requires that, and a banner at the top of the map does it.
   Every mission carries its own confidence and its own disputed list, and a test
   fails any mission that disputes nothing or cites nothing.

## Honest about the work not done

Every mission carries `dossier: false`, and a test asserts **14 of 14 dossiers
are still to be written**. That is M5's job, made countable rather than
forgettable — the test fails the day someone marks a dossier done without
writing one, and the mission brief tells the player the full dossier is pending
rather than presenting a stub as finished research.

## Bugs the tests and the walkthrough found

- **Two missions rewarded cards the player already starts with.** "Breadth" that
  hands back a card already in the opening deck is breadth on paper and nothing
  at all in the hand. Caught by a duplicate-reward test, then by a second test
  written specifically to bar starter cards. All sixteen rewards are now unique
  and none is a starter.
- **`.map(tierCapForRound)` broke the moment the function took a second
  argument** — `map` passes the index in as the match length, so the cap test was
  quietly asserting nothing. Fixed, and app code checked for other point-free
  uses of every function that gained an optional parameter. There were none.
- **The result screen said "first to 4" after a first-to-2 mission**, because
  the score line read the ranked constant instead of the match's own target.

## Still outstanding after M4

- **M5**: all fourteen dossiers, and Counter-History (play the book as Media,
  labelled as alternate history with the documented outcome shown at the end).
- Book One's missions all play on one of the two existing scenarios. More
  scenarios would let the map's geography mean something.
- A capital that is drawn rather than listed.

---

# M5 — Book One content (Concept v0.2 §9, §11)

All fourteen Historical Battle Dossiers, and Counter-History.

## The dossiers

v0.1 §14 asks for a dossier per campaign before implementation. Fourteen are
written, in `content/data/dossiers.json`, with a shared book-level evidence base
so the same four facts are not restated fourteen times.

**The field that earns the document is `mustNotClaim`** — the things that are
widely believed, or dramatically convenient, and are not supported. It leads the
sheet, boxed in red, above the evidence. A dossier that lists sources but never
says what must NOT be claimed is a bibliography, not a guard-rail.

The book-level entry bars, by name:

- **The Cyrus Cylinder as a charter of human rights.** It is a Babylonian
  foundation deposit in a long Mesopotamian royal tradition. The modern
  rights reading is a twentieth-century framing the text does not support, it
  circulates very widely, and it circulates hardest in exactly the audience this
  game is for. Barred by name, and a test asserts the bar exists.
- Any specific age for Cyrus at the revolt. His birth date is unknown.
- Herodotus' exposure-and-shepherd story as biography.
- **Medes and Persians as foreign to one another.** Both are Iranian peoples with
  closely related languages. This was a dynastic war, not a clash of
  civilisations, and the Median army is the side that ended it.
- That a single pitched battle decided the war. The near-contemporary evidence
  describes a mutiny.

**Most of the dossiers say "almost nothing".** Six of fourteen missions have any
contemporary evidence of their own; the other eight are scene-setting on a
four-fact frame, and each says so in its first line. A test fails if a majority
ever start claiming evidence.

### What the tests caught

**Four missions had Herodotus or Strabo filed under `specificEvidence`** — the
field for contemporary material. That is precisely the blurring the source
hierarchy forbids: the game may use all five levels but must never present a
lower one as a higher one. Moved to `laterSources`, and a test now fails any
dossier that files Herodotus, Strabo, Ctesias, Xenophon or Nicolaus as
contemporary.

## Counter-History (v0.1 §4)

The book replayed from the Median side. Four rules, all tested:

1. **It does not open until the historical book is finished.** Nobody meets the
   alternate version before the documented one.
2. **It has its own progress list.** Finishing the history does not hand the
   player a finished Counter-History; it starts at mission one.
3. **It pays nothing.** An outcome that did not happen should not reward. This
   needed a guard in *two* places — `completeMission` refuses to record it, and
   the store computes the grant separately and paid out anyway on the first run.
   Caught live, fixed, and pinned by a test that checks both halves exist.
4. **Every result is labelled.** The campaign screen turns red and says "This is
   not what happened"; a win reads *"You changed it. Media did not win this war"*
   and the documented outcome is stated underneath either way.

## The "what we know" card

v0.1 §5.1 step 6. It lands **after** the mission rather than before it, on a
player who now has a reason to care, and it is the dossier's plain-language
field plus the must-not-claims — not a second essay.

## Still outstanding after M5

- **Specialist review.** Every dossier is marked `drafted`. Nothing moves to
  `specialist-reviewed` without an actual specialist, and the twelve claims in
  CONCEPT-v0.2 §10 remain outstanding.
- All fourteen missions play on one of two scenarios. More battlefields would
  make the map's geography mean something.
- A defection mechanic. Mission 12's central event — an army changing sides — is
  currently taught by framing and reward rather than by a system, and its own
  dossier flags that.
- M6: recorded rivals.

## Card emblems land, and one of them fails the only test that matters

Six of the eight Upgrade/Doctrine emblems arrived and are cut out, prepared and
wired into both places a card is drawn: the offer slot in a match, and the
Upgrades and Doctrines list in Scrolls. Verified live in the browser rather than
assumed — the rules list reports all six real filenames, and a driven match
rendered `the-centre-holds.png` in a real `.rule-card`.

**All six honour the no-figure rule.** That rule is not decoration. A unit and a
trait are different kinds of thing, which is the whole of M2, and an emblem with
a soldier on it would quietly undo the distinction the card kinds exist to make.
Card art therefore lives in `src/assets/cards/`, indexed separately from units,
and `UnitGlyph` takes `cardId` rather than reusing `unitId` — so the two can
never be mixed up by a typo.

**`shoot-the-horses` failed.** The emblem is a bundle of arrows with no horse in
it. At the 24px the rules list actually draws, it is not meaningfully different
from `ready-volley`, which is also arrows. Two cards that do opposite things
reading as the same picture is the one art failure that costs the player a
decision, and it is not fixable by making the file better — the horse has to be
in the drawing. Flagged for regeneration, not shipped-and-forgotten.

`the-centre-holds` reads as a uniform grid, losing the solid-centre-thinning-
wings idea, and `broken-ground` reads as a badge rather than a defile. Both are
weaker than they should be but neither collides with another card, so they stay
in while the horse one is redone.

`wheeling-line` and `loosed-rein` were not in the batch and still draw
placeholder shapes — visibly different from the finished six, which is the
point of the per-card fallback.

Art tally: 6 of 8 cards, 4 of 25 units. 61 of 71 pieces outstanding.

## The horse arrives; a chocolate bar is turned away

Second card batch. `shoot-the-horses` came back correct — a riderless oxblood
horse rearing, three gold arrows arcing in — and at 24px it is now a red horse
where `ready-volley` is a thin arrow. The collision that made the two cards the
same picture is gone, which was the only art fault so far that changed how the
game plays. Contact sheet re-run: all seven prepared emblems are distinguishable
in the 24px column.

Two of the four were rejected rather than shipped:

**`the-centre-holds` regenerated as a bar of chocolate.** Dark brown rectangular
segments in a grid, gold-edged, on a cream wrapper. The version already in the
game was weak — a uniform grid that loses the firm-centre idea — but weak and
neutral beats strong and wrong, so the old file stays and the new one was
reverted out of `art-in/` rather than left lying around to be picked up by a
later pass.

**`loosed-rein` came back as a bordered square ground tile of hoofprints.** It
fills its own frame edge to edge, which the cut-out cannot process — the flood
fill works inward from the corners and there is nothing to flood. It would also
read as a brown square at 24px, and it says "tracks" rather than "shoot while
falling back". Deleted; the card keeps its placeholder shape.

`wheeling-line` is in but is a **style outlier**: flat vector, the look of a
corporate logo, with none of the gouache texture the other six share. It was
taken because a legible outlier beats a placeholder and because at 24px style
barely registers — but it should be redone in the painted style.

One side effect worth recording: the emblem was drawn as a gold hook wrapping a
cluster of shields, and `keep_largest_shape` dropped the shields, because they
are a disconnected component. The surviving hook alone actually reads better —
"goes around and comes back" is the mechanic — so this was left. But it is a
reminder that the tool keeps ONE shape, and any emblem built from separate
pieces will lose all but the biggest.

Art tally: 7 of 8 cards, 4 of 25 units. 60 of 71 pieces outstanding.

## The whole roster arrives at once — and the Army Ledger is now the weak link

All 21 remaining units came back in one batch and all 21 cut out on the first
pass. The roster is complete: 25 of 25. Verified in the running game, not
inferred — `artProgress()` reports 25/25 units with an empty missing list, zero
placeholder shapes remain on the units screen, no image 404s, and a driven AI
match rendered sprites on the battlefield with correct team rings and HP bars.
Build clean, 187 tests pass, 1.5 MB for the whole roster.

The silhouette hooks written into the prompts mostly worked. The ones that
carried at 22px: the Ethiopian bow overtopping its own archer, the Indian
archer's white cotton (the brightest thing on the sheet), the Sagartian rope
loop, the camel's hump, the Apple-bearer's gold sphere, the Immortal's and
Shield-bearer's shield slabs, the chariot, the elephant.

**They did not all work, and the honest reading is that six units converge.**
At 22–26px `bactrian-archer`, `colchian-shieldman`, `egyptian-marine`,
`kissian-levy`, `lydian-hoplite` and `paphlagonian-javelineer` are the same
picture: a brown standing figure about ten pixels wide. Three of the four
cavalry converge the same way. Everything separates cleanly from 40px up.

That matters because of exactly one screen. `MatchScreen.tsx:352` draws the Army
Ledger as glyphs at 26px **with no label** — the unit name is in a `title`
attribute, which a phone cannot show. So during a match the player is asked to
tell six squads apart by a picture at the size where six of them look alike.

This is not a regression: before the art, those units drew shared placeholder
silhouettes — twelve infantry all rendering as 'shield' or 'spear' — so the
ledger was strictly less readable than it is now. But it is the next real
problem, and it is a UI problem rather than an art one. Regenerating six good
illustrations to fight a 26px box is the wrong fix; the ledger needs to carry
identity some other way.

Art tally: 25 of 25 units, 7 of 8 cards. 39 of 71 pieces outstanding — all of
them arenas, commanders, capital, codex figures and mission images.

## The Ledger says the name, because at 26px the picture cannot

The Army Ledger drew each squad as a bare 26px glyph. The unit's name existed
only in a `title` attribute — which a phone has no way to show — so during a
match the player was asked to tell six squads apart by a picture at the one size
where six of them look alike. Six plain infantry render as the same brown
ten-pixel figure there, and no redraw fixes a box smaller than the difference.

So the box now holds a picture **and** a word. Identity comes from the word; the
art goes back to being flavour, which is what it is good at.

The word is the DISTINGUISHING one, which is usually the people rather than the
weapon: 'Bactrian' and 'Colchian' separate where 'Archer' and 'Shieldman' would
not. Two entries had to be changed after they were written — Persian Archer and
Persian Cavalry both wanted to be 'Persian', which is the exact failure the
label exists to prevent, so a test now fails on any duplicate.

Everything below was measured in the browser, not estimated:

- **'Chorasmian' needed 49px in a 40px box** and ellipsised. Nine characters is
  the real ceiling at 8px, not the ten I first assumed — 'Sagartian' needs 39px
  and fits exactly. Shortened to 'Chorasm.', and the test now asserts the
  measured number with the measurement written down beside it.
- **The rank badge sat on top of the name** and ate the last letter of 'Camel'.
  It hung 4px below the art; it is now flush with the art's bottom edge. The
  badges were also rehoused onto a `.ledger__art` wrapper so that adding a row
  beneath the art can never push them onto text again.
- **At 320px six squads wrapped to two rows**, taking the band from 60px to
  109px — doubled, on both sides, out of a 700px screen. A 360px tier drops the
  slot to 40px and the gap to 2px: 6x40 + 5x2 = 250 inside the 258px available.
  41px with a 3px gap came to 261 and wrapped by three pixels, which is the kind
  of margin that only a measurement finds.

Verified at 320, 375 and 768, in the offer phase and the battle phase, with an
empty ledger, a single untiered squad, and six squads carrying rank badges and
trait pips. No name ellipsises, no badge overlaps a name, nothing wraps, the
page never scrolls sideways. The battlefield canvas still gets 323x428 on a
375x812 screen.

One thing checked and left alone: the Result screen draws units at 22px but
already prints the full name beside the glyph. The Ledger was the only place a
unit had to be recognised from the picture alone.


## Three rivals, and two things the measurement threw out

The offline opponent differed only by a `skill` scalar — a hit rate, not a
habit. Twenty-four differently-named rivals all drafted the same army, so the
whole offline game had one shape. It now has three, and a rival's habit is
printed on its nameplate beside the CPU tag so it can be learned rather than
guessed at.

**The first design was wrong and the tests said so.** They were written as tall
/ counter-picking / wide. Two of those did not survive contact:

*Counter-weighting is competence, not personality.* The style that weighted the
matchup triangle highest beat the style that weighted it lowest **90% of the
time**. In a game whose core mechanic is a counter triangle, "how much do you
care about counters" is just a difficulty slider wearing a costume. All three
styles now weight it identically, and only after that did every pairing settle
inside 35-65%.

*The harness was measuring the wrong thing.* Sides a and b get different
improvised decks and the simulation is not mirror-symmetric, so a pairing played
from one side alone measures style advantage and side advantage added together.
The same matchup reported as 34% and as 66% depending on which style name sorted
first. Every pairing is now played both ways round and summed.

What survives is which KIND of card a rival spends a pick on — the three kinds
M2 built. Measured over 90 matches each, both ways round:

| style | rank | doctrines | traits | reads as |
|---|---|---|---|---|
| massing | 1.36 | 0.17 | 0.61 | masses its ranks |
| drilling | 1.30 | 0.30 | 1.09 | drills its troops |
| planning | 1.16 | 0.99 | 0.44 | plans the whole line |

Head to head: massing/planning 54.4%, drilling/massing 39.4%, drilling/planning
46.1%, over 180 matches each.

**A correction worth keeping.** Midway through, the scorer was also changed to
stop charging a rank-up the mixed-front penalty — a rank deepens a squad, it does
not widen the front, so the penalty looked like double-counting. It was reverted
for two reasons. It changes what the AI picks under NEUTRAL weights, and it broke
the 200-match commander sweep that M3 was accepted on. And it flattened the rank
column above to 1.42/1.39/1.40 — nothing — which briefly made "goes tall"
look impossible and produced a confident, wrong comment saying so. The reading
that a rank-up is double-penalised is still probably right; it is just not free,
and it is not this piece of work.

The old weights are kept verbatim as `NEUTRAL` and used whenever no opponent is
supplied, so every figure already measured against this AI still means what it
meant. A style is a deviation from something, and that is the something.

**M6 is only part done.** It was specified as `RecordedRivalDecisionProvider`
"reading the existing replay log". There is no replay log — nothing in the game
records a match's decision sequence. Recorded rivals need a recorder first.


## The recorder: 867 bytes is a whole match

M6 asked for a rival that replays "the existing replay log". No such log existed,
so this builds it.

**A match is not stored, its decisions are.** The simulation is already a pure
function — `sim/` imports neither React nor Pixi and never reads a clock — so
there is no reason to keep what happened. Keep the inputs and re-run them: the
battle, the seed, the arena, both decks, both commanders, and then per round the
rerolls each side spent and the two card ids. Measured at **867 bytes for a full
seven-round match**, against however many kilobytes an event log would have been.

Because it is inputs rather than a summary, the test can assert something much
stronger than "looks right": 40 matches replayed to a `MatchState` that is equal
under `JSON.stringify` to the original, and a real match played through the
actual UI did the same — score, ledgers, and every round outcome identical.

**Rerolls had to be in the tape.** Spending a Rally feeds the offer seed, so a
replay that skipped it would derive a different offer and then reject the very
pick it was replaying. They are recorded per round, and `nextRound` clears them
— which is why `recordRound` must be called before `commitPicks`, the single
moment when the picks and the rerolls that produced them are both still present.

**A replay throws rather than improvises.** If a recorded card is not on the
offer it faces, `replay` refuses. A quiet substitution would produce a
plausible-looking match that is not the one recorded, and a plausible wrong
answer is worse here than a crash — the whole value of a recording is that it IS
the match.

**The rival is honest by construction.** `recordedRivalPick` returns
`{ cardId, recorded }`, and `recorded` is false whenever it fell back. That is
not a nicety: a recording is a decision sequence, not a script for the world, so
facing it with a different seed or a different opponent means the stored card is
often simply not on offer — falling back is the normal case. §10's honesty rule
means a rival that is part recording and part scoring function must never be
presented as a person, and the caller cannot know which it got unless the
function says so.

**One thing extracted on the way.** The round seed expression
`(seed ^ ((round * 0x5bf03635) >>> 0)) >>> 0` was copy-pasted in nine places —
the store, four sim tests, three net tests. A recorder replays by re-running
those rounds, so any drift between two copies would produce a replay that
silently diverges from the match it claims to be. It is now `roundSeedFor` in
`roundCore`, with a test asserting it still equals the inlined expression.

Storage is its own localStorage key rather than the save file. The save is
written on nearly every action, and a corrupt or oversized tape must never be
able to take a child's collection down with it. Quota failures, corrupt JSON, a
non-array value and a missing `localStorage` entirely are all covered — the game
plays, it just does not remember matches.


## The recorded rival, and a bug in the thing I had just built

Wiring the rival in immediately exposed a mistake in `recordedRivalPick` from
the previous commit: it read `picks[side]` — the side the rival was PLAYING.
The rival sits on side b; the human was side a. So it would have replayed
whatever sat opposite the person, which is the scoring function this feature
exists to replace. It now reads `picks[rec.human]` and plays those decisions on
whichever side it occupies. Tested by asserting the two sides took different
cards and that the rival wants the human's one.

**A tape is only used from the same battle and the same arena.** Offers derive
from the draft pool, which is a function of both. A tape from anywhere else
would miss nearly every round, and the rival would be the ordinary AI wearing a
"replaying a real game" label — precisely the claim §10 exists to stop. It also
declines about half the time, from the match seed, so a player who has
recordings does not face their own last draft every single match.

**When the claim is made matters more than the wording.** The nameplate says
"replaying a real game" only after a round has actually come from the tape, not
from the start of the match — at the start the game genuinely does not know how
much of the rival will be a person. The exact number is stated on the result
screen, after the fact, where it can be true: "4 of 4 rounds came from a game
somebody really played."

That copy needed fixing after the first live run, which returned 4 of 4 and then
added "The rest the computer chose." There was no rest. All three branches —
all, some, none — are now separate and were checked in the browser.

Verified live rather than assumed: a match where a tape was chosen produced a
rival whose ledger was `spara-bearer, persian-cavalry, persian-archer` against
the tape's human picks of exactly those cards, 4 hits in 4 rounds, with the
nameplate carrying the tape label and the result screen the exact figure.


## The age gate, and the hole it was actually for

M7 begins with the age gate because it blocks a store submission and needs no
art. But a gate that only records a number would be theatre, so the first job
was finding what actually needs gating.

Almost nothing does. Collection, trophies, settings and match recordings are all
localStorage and never leave the device. **Exactly one thing is broadcast to a
stranger: the display name.** And the first screen on a fresh install said
"Choose your name — other players will see this when you play online", with the
placeholder "Your name", to an audience of nine-to-fourteen-year-olds. That is
the hole, and closing it is the whole substance of this work.

Two deliberate choices in the gate itself:

**It asks for a birth year, not "are you over 13?"** A yes/no question with an
obvious right answer teaches a child to lie to it. Nothing on the screen says
what any answer unlocks.

**Only the bracket is stored, never the date.** A birth date is precisely the
data a children's app should not hold, and nothing here needs one. The cost is
that a child who turns 13 stays in the younger bracket until the app's data is
cleared — which is the safe direction to err in.

Under 16 the name is chosen from a shuffle of 144 adjective-noun titles rather
than typed. Teens are included on purpose: GDPR-K's line moves between 13 and 16
by member state, and the safe reading does not depend on knowing where the
player is.

**Three bugs, each caught by the thing built to catch it.**

The test asserting assigned names survive the server's own validation failed
first time: 13 of them were over the 14-character limit, because 'Far-seeing'
and 'Patient' were in the adjective list. A name the server rejects would have
locked a child out of online play altogether — turning a restriction into a ban.

Live, the shuffle produced Swift Lion, Swift Falcon, Swift Archer, Swift Rider.
Stepping by one walked a single row of the table, so a child tapping "give me a
different name" saw twelve nouns before the adjective ever moved. The step is
now coprime with the total.

Also live: the screen showed 'Swift Spear' and the save recorded 'Swift River'.
The store was recomputing a name instead of accepting the one the player had
just chosen. It now keeps any name it would itself have offered, and replaces
only something that could not have come from the shuffle — which keeps it an
enforcement point rather than a second, contradictory generator.

That enforcement is real and was checked by attempting the bypass: calling
`saveProfile('Alireza', …)` directly on the store as a teen saves 'Swift Lion'.
The restriction does not live in the screen that happens to be showing.

**Not legal advice.** The thresholds are a starting position. COPPA says 13,
GDPR-K says 13-16 depending on the country, and the UK's Age Appropriate Design
Code applies to under-18s regardless. A lawyer decides; this provides the
mechanism to implement whatever they decide.


## The age gate is gone, and that is the better answer

Built yesterday, removed today, on a one-line challenge: *why do we have young
and adult from the beginning?*

Checking it rather than defending it settled it in three facts. The audience is
nine to fourteen, so an adult path serves almost nobody — and it existed only to
grant the single privilege that carries all of the risk. The bracket was read
for exactly one decision, whether a name could be typed. And §17 rules out chat,
clans and subscriptions, so nothing else was ever going to read it.

That is a standard compliance pattern applied without asking whether this
product needed it. **A gate manages a risk. Deleting the free-text field removes
it.** Nobody types a name now; everyone picks one from a closed set of 144.

What the removal bought, all of it real:

- One screen fewer before a child can play.
- No birth year asked, and no age stored even as a bracket — the save file no
  longer has the field at all.
- **No profanity list, ever.** It was on the M7 list an hour ago. There is now
  no user-generated text anywhere in the product for it to moderate.
- The server checks set MEMBERSHIP instead of string shape. The old
  `sanitizeName` stripped disallowed characters and truncated to 14, which would
  have passed any slur spelled in letters. A modified client can no longer put
  arbitrary text in front of another player at all.

Two things the sweep turned up. `SettingsModal` had a SECOND name field — a
pencil opening a text input — which the store would now have silently
overruled, so the player would have typed a name and watched it change. It
re-rolls instead. And Vite's HMR kept serving the deleted `AgeGate.tsx` until
the dev server was restarted, which briefly looked like a source error and was
not; the production build was clean throughout.

Verified live on a fresh install: no gate, no text field anywhere, the shuffle
varies both words, the saved name is the one shown, the settings pencil
re-rolls, and `saveProfile('Alireza', …)` called straight on the store saves
'Swift Lion' instead.

Not a loss of expression: a player still chooses from 144 titles plus a badge
and a banner, and 'Quiet Falcon' is a better name for a nine-year-old's warband
than anything they would have typed.


## One profile: the evidence was hiding behind a settings toggle

Same question as the age gate, one screen along — why two versions of a player?
The answer is the same, but the reason is sharper, and it is a number.

The game carried a 'reading level' toggle: `kid` and `older`, with a second
blurb written for 53 pieces of content. It looks like a reading-age feature.
Measured, it is not:

**24 of 25 units name a source in the `older` blurb. 1 of 25 does in the `kid`
blurb.**

So the toggle was never about reading age. It was the evidence layer — Herodotus,
the Persepolis reliefs, the gold daric, the difference between what a source
says and what we infer — and it defaulted to OFF. The half of this game that
teaches how we know things was the half almost nobody would ever see.

So: merged, but by promoting the sourced text rather than deleting it. The
lesson from the age gate applies exactly — **do not make it a mode, make it
structure.**

- The draft card keeps the short line. It has to fit a card, and it is the hook.
- The codex detail now shows BOTH, always, for everyone: the hook, then the
  sourced paragraph, then the source list that was already there.
- The collection detail does the same.
- The `reading` mode, its setting, its type, and the prop threaded through
  UnitCard and four screens are gone.

Verified live: opening Persian Archer in the codex shows the short line, then
"The royal coinage — the gold daric — shows the king himself as an archer, and
the Persepolis reliefs make the bow and quiver the mark of a Persian soldier.
Herodotus equips the Persians with long bows and arrows of reed", then SOURCES.
Three paragraphs where there was one.

Four tests guard it, because a merge like this can quietly become a deletion —
with no toggle left to reveal the long text, a missing `blurbOlder` would just
look like a shorter card. They check it exists for every unit, is not a copy of
the short line, is actually longer, and that at least 22 of 25 still name a
source. The last one is the real guard: it fails on drift back toward unsourced
flavour.

Nothing was thrown away. Both texts are written, both are shown, and the
specialist history review now covers text that players actually read.


## `blurbOlder` was still claiming an audience that no longer exists

Follow-up to the merge, on the right question: is there still a younger
players' version?

Not as a mode — that went with the toggle. But the FIELD was still called
`blurbOlder`, and `summaryOlder` on battles, so the data model went on asserting
an age split the product had stopped making. A name that describes a deleted
feature is a lie the next person has to discover.

The two texts are kept, because they do different jobs — and the jobs are about
length and context, not age:

- **`blurb`** is the hook. It appears on the draft card, which is read in about
  two seconds while choosing under a timer against two other cards. One idea,
  and it has to fit.
- **`evidence`** is the same subject with its attribution — Herodotus, the
  Persepolis reliefs, the gold daric. It appears in the codex, where there is
  room. It is longer because attribution costs words.

An adult drafting needs the short one too; a nine-year-old in the codex can read
the long one. Neither text belongs to an age.

Renamed across 53 data entries in six files, five type declarations, two screens
and the content tests. Verified live afterwards: opening Persian Archer still
gives three paragraphs ending in the daric and the Persepolis reliefs.

## What an afternoon watching the reference game actually taught us

Observed live over iPhone Mirroring rather than from description, so these are
measurements, not impressions. Three findings changed what we know, one of them
by correcting a claim made earlier the same day.

**Our escalation is not flat.** That was said here earlier and it was wrong.
Measured across 60 matches (`sim/escalation.test.ts`), an army goes from 4.0
power in round 1 to 18.1 in round 7 — **4.52x**. The problem is the SHAPE, not
the size: ours adds a near-constant +2.3 every round, which is arithmetic. The
reference game's cards are worth +2 to +5 in its first round and +5 to +8 in its
last, so each round adds MORE than the one before. Linear growth reads as
maintenance; accelerating growth reads as a climax. Same 4x, different feeling.

**The climax round almost never happens.** Of 60 measured matches, 42 reached
round 5 and only 8 reached round 7. The average final army is 4.63 squads
against a cap of 6 — we never even reach our own ceiling. A seventh round we
designed as the peak occurs in about one match in seven.

**Picks are alternating there, simultaneous here.** This was the day's biggest
correction and it came from the person, not the screen: the banner that flies in
at the opponent's end is them TAKING THEIR TURN, not a simultaneous reveal.
Alternating means you see their move and answer it; ours holds both picks and
releases them together, so it is commitment under uncertainty. Both are
defensible and ours was chosen deliberately in the concept — it is load-bearing
for the server design, which validates a pick against its own derived offer and
detects desync from both clients. It must not be changed casually, and it is
NOT changed here.

Smaller, cheap, and clearly worth taking:

- **A commitment beat on tap.** There, choosing a card freezes it for about a
  second while the other two vanish, leaving the chosen one alone before play
  continues. It confirms the input, gives the decision weight, and covers the
  network wait. We have nothing — our card marks itself and sits.
- **A pre-battle beat.** There: round number, then "KÄMPFE!", then a battle
  sound, then the units move — one to two seconds. We cut from offer straight to
  fighting.
- **A timer every round, including offline.** Theirs always runs one, and it is
  where the pressure comes from. Ours runs a clock only in online matches, so
  most of our matches have no pressure at all.

Explicitly NOT taken: no screen shake (they have none), and no hit-stop that the
player noticed. Whatever punch the reference game has comes from timing and
sound, which is cheaper to build than camera effects and easier to get right.

Still unknown, and unknowable through mirroring: the sub-second easing on the
card freeze, and whether the timer bar is linear or accelerates near the end.
Frames arrive about a second apart over the mirror, and there is no audio at
all. That part needs a screen recording.

## The escalation experiment: a late squad is no longer a raw levy

`addPick` set `tier: card.startTier ?? 1`, so a squad recruited in round 7
arrived at Levy — worth exactly what one recruited in round 1 was worth. That
one line was the whole arithmetic curve: every round added the same amount.

New squads now arrive one rank BELOW what the round allows. Measured over 60
matches:

| | round 1 | round 7 | total | shape |
|---|---|---|---|---|
| before | 4.0 | 18.1 | 4.52x | +2.3 flat |
| after | 4.0 | 21.6 | 5.38x | +2.8, +2.4, +2.5, +2.9, +3.2, +3.8 |

The increments now grow through the back half, which is the point — the
reference game's late rounds add more than its early ones, and that is what
makes its round six read as a climax rather than as maintenance.

**Two things broke on the first attempt, and both were worth the trip.**

Arriving AT the round's cap rather than below it gave a squad no headroom: it
could never be ranked up, every duplicate card became useless, and the rank
mechanic died in exactly the rounds it exists for. `pickIsUseful` went false for
a full ledger at round 7 and a test caught it. Arriving one rank below the cap
keeps headroom at every stage.

The first attempt also pushed Cyrus to 58.8% against a 55% ceiling. That is not
a coincidence — Cyrus's passive rewards fielding many DIFFERENT squads, and
making every new squad arrive strong is precisely a buff to breadth, while
Astyages's head start (one card already Trained in the first two rounds) is
worth less when late squads arrive Trained anyway. Backing off to cap-1 brought
it back inside the band without touching either kit.

The full 8.11x version is still on the table, but it needs the commanders
rebalanced for it rather than nudged, and that is a bigger piece of work than
one line.

Still unfixed and now clearer: matches mostly end before the late rounds. Round
7 was reached by 10 matches of 60, up from 8. First-to-four inside seven rounds
means the median match is about five. The escalation now exists; most players
still will not see the top of it.
