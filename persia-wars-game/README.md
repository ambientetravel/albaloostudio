# Persia at War

A 2-player educational draft + auto-battler about real Iranian battles, won and
lost, from Elam to the Qajars. Draft an era-appropriate squad, the armies fight
themselves, and every match unlocks a codex card with what actually happened.

Standalone product. Nothing to do with boutimar.com.

- **Sharing it with testers:** [TESTING.md](TESTING.md) — start here to hand it round
- **Hosting it:** [DEPLOY.md](DEPLOY.md) — what a host must support, and why most will not
- **Design & scope:** [RESEARCH-BRIEF.md](RESEARCH-BRIEF.md) — the source of truth
- **Decisions locked:** [DECISIONS.md](DECISIONS.md)
- **The 13 battlegrounds, with Iranica links:** [docs/BATTLEGROUNDS.md](docs/BATTLEGROUNDS.md)
- **Fact-check log:** [src/content/data/VERIFICATION.md](src/content/data/VERIFICATION.md)

## Running it

```bash
npm install
```

`npm run dev` starts **both** the Vite client and the matchmaking server, so
online play works out of the box:

```bash
npm run dev
```

- client → http://localhost:5183
- matchmaking server → ws://localhost:5184 (override with `WS_PORT`)

```bash
npm test
```

```bash
npm run build
```

To run just one half: `npm run dev:client` or `npm run server`.

### Sharing a test build

```bash
npm run share
```

Builds the game and serves it **and** the multiplayer sockets on one port,
printing the LAN address for the team. See [TESTING.md](TESTING.md) for what to
send them. The feedback widget is compiled in only by this command — a normal
`npm run build` does not contain it.

## What exists right now

The **Achaemenid slice**, with the full meta-game around it:

- **Lobby** — currencies, profile card, arena stage, trophy ladder, deck strip,
  BATTLE / PRACTICE, bottom navigation
- **Settings sheet** — profile tab (name, badge, Achaemenid banner colour,
  reading level, stats) and settings tab (audio, haptics, legal, sign-in)
- **Shop** — Offers, Card Packs, Gems, Daily. Soft currency works; real money
  does not (by design — see DECISIONS.md)
- **Collection** — 25 unit cards and 16 spell cards, 13 arenas, a four-slot
  battle deck, card levels and duplicate-to-upgrade
- **Loading screen** — parallax splash and animated logo (Framer Motion)
- **Online play** — matched against anyone else on the server, right now
- **Practice** — a named computer opponent with human-like timing and mistakes,
  always available; BATTLE falls back to it after eight seconds of finding nobody
- Two scenarios: Pasargadae (550 BCE) and the Persian Gates (330 BCE)
- Codex with sources and a "what's disputed" section on every card
- PWA manifest + offline shell

Not built yet: the other five launch eras, playable spells, the micro-quiz,
audio pronunciations, sound, and all commissioned art.

## How it fits together

```
server/
  index.ts        Matchmaking. Node runs this TS directly via type stripping.
src/
  content/        JSON content + schema. All history lives here, not in code.
    data/         eras · arenas · units · spells · kings · battles · VERIFICATION.md
  game/
    progression.ts  Arena ladder, trophies, card levels, soft economy
  sim/            Deterministic, render-free game logic
    battle.ts     The auto-battle. Emits a replayable BattleLog.
    draftCore.ts  Draft rules SHARED with the server — no DOM, no content imports
    draft.ts      Client draft state on top of draftCore
    ai.ts         The offline opponent — drafts to counter what it can see
    rng.ts        Seeded PRNG; same seed ⇒ identical battle
  net/            Wire protocol + reconnecting WebSocket client
  render/         PixiJS playback of a BattleLog. Reads the log, never mutates it.
  state/          Zustand store, save file, and the server message handlers
  ui/             Screens, cards, badges, the Achaemenid banner palette
```

Two splits carry the whole design:

**`sim/` never imports `render/` or React.** A battle is a pure function of
`(scenario, squads, seed) → BattleLog`.

**The server never simulates anything.** It pairs players, picks the seed, and
relays validated picks. Both clients derive every draft offer from `(seed, step)`
using the same `draftCore.ts`, and both run the same sim on the same seed — so
they reach identical results without trusting each other. That is why the server
can validate a pick it never sent: it re-derives the offer the client should have
been looking at. Verified with two live browser tabs producing byte-identical logs.

## Content rules enforced by tests, not by memory

`npm test` fails the build if any of these break:

- The string "Arabian Gulf" appears anywhere in the content
- Any battle, figure or unit ships without a `sourceRefs` entry
- Any player-visible string is blank
- A battle dated after 1925 enters the dataset — modern wars stay out of the
  children's core (brief §9)
- A unit is locked out of a scenario without an explanation the player can read
- The server's draft pool disagrees with the client's, at any scenario
- The same seed produces different offers or a different battle
- **Unverified content reaches play** — no unchecked card can enter a draft
  pool, an arena unlock, or a card reward
- A spell is not labelled as legend, or claims to be verified history
- The arena ladder skips, reverses, or leaves arena 1 without a full starter deck
- A card reward awards something the player's arena has not unlocked
- The client and server draft pools disagree at **any** arena × scenario pair
- The pool narrows as the ladder climbs, or arena 1 offers no real choice

## Adding content

Add to the JSON, not to the code. A new era needs a row in `eras.json`, its units
in `units.json`, its figures in `kings.json` and its battles in `battles.json`.
Every record needs `sourceRefs`, and anything contested goes in `disputed[]` —
the codex renders those under "What's disputed" rather than quietly picking a side.

Two gates decide what can be drafted, and they stack:

- `earliestAttested` gates a unit out of scenarios that predate its first firm
  attestation, and `attestationNote` is what the player reads when they ask why.
  This is how a 550 BCE draft refuses a scythed chariot.
- `arena` gates it behind the ladder. Anshan drafts from four cards, the Persian
  Gates from all twenty-five.

The server applies both independently, so a modified client cannot draft around
either. Online, the match runs at the **lower** of the two players' arenas.

## Before this faces the public

- **Name moderation exists but its word list is a starter, English only.** The
  normalisation is tested and sound; the list needs replacing with a maintained
  multi-language one. See `server/moderation.ts`.
- **Nothing charges money, on purpose.** Every euro-priced button is a shell.
  Wiring a real one needs an age gate, a COPPA consent flow for under-13s in the
  US, kids-category store review, and a legal entity behind the Terms and Privacy
  stubs. Full reasoning in DECISIONS.md, "The money question".
- **No reporting, blocking or muting.** A tester who meets a name that slipped
  through has no way to flag it.
- **The 16 spells have had no references pass.** They are flagged unverified and
  unplayable, but the text needs checking.
- **Deployment.** The server is local-only. It needs a host, `wss://`, and an
  origin check.
- **Art.** Everything visual is placeholder — procedural shapes in
  `render/silhouettes.ts` (canvas) and `ui/UnitGlyph.tsx` (DOM). Commission real
  art; do not scrape museum or game assets (brief §9).
