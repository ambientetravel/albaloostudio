# Persia at War — test build

An early build, shared to collect reactions. Roughly a third of the game exists;
the rest is deliberately unfinished, and the list below says which is which so
nobody spends a note on something already known.

---

## Running it

On the machine hosting it:

```bash
npm install
```

```bash
npm run share
```

That builds the game and starts one server that hosts **both** the game and the
online multiplayer on a single port. It prints two addresses:

```
  On this machine   http://localhost:5180
  On the network    http://192.168.1.121:5180   ← give this one to the team
```

Anyone on the same wifi opens the network address — laptop or phone, no install.
It is a PWA, so on a phone "Add to Home Screen" gives it a real app icon and
full screen.

**The host machine has to stay awake and on the same network.** There is no
hosting yet; when the laptop sleeps, the game goes with it.

Port already busy? `WS_PORT=5181 npm run serve`.

---

## Sending feedback back

There is a **✎ button** at the bottom right of every screen. It attaches which
screen you were on, which arena, your trophy count and your screen size — so
just write the opinion.

When you are done, open it again and press **Export notes**. That downloads one
markdown file. Send that file back. Nothing leaves your device until you do.

---

## What is worth looking at

**The loop.** Lobby → BATTLE → draft eight cards → watch the fight → read what
really happened. Does the draft feel like a decision? Does the battle read
clearly enough to see *why* you won or lost?

**The teaching.** Every match ends on "True, or reshaped?" — it tells you the
real historical outcome whether you won or lost. Codex cards under **Scrolls**
carry sources and a "What's disputed" section. Is that interesting or is it
homework?

**The computer opponent.** Almost every match will be against it. It has a name,
hesitates unevenly and makes mistakes. Does it feel like a person? Is it too
easy, too hard?

**Progression.** You start in Anshan with four cards. Winning raises trophies,
which unlocks arenas, which widens the draft pool. **Trophies** tab shows the
whole ladder. Is the climb legible?

**The two finished arenas.** Anshan and Ecbatana have real art, a loading film
and their own colour scheme — the whole interface re-skins as you climb. Compare
them. Arenas 3–13 use placeholder colours.

To see later arenas without grinding, open the browser console and run
`game.setState({ trophies: 2200 })`.

---

## Known and deliberate — please do not report these

| | |
|---|---|
| **Nothing can be bought** | The Bazaar's euro prices are a display shell. No payment provider, no age gate. Coins and gems earned by playing are real and do spend. |
| **Most art is placeholder** | Units, badges, portraits and arenas 3–13 are procedural shapes. Only Anshan and Ecbatana have real art. |
| **No sound** | Not wired at all. The volume sliders do nothing yet. |
| **Spells cannot be played** | All 16 are written but unverified, so they are locked by design. |
| **Only two battles** | Pasargadae and the Persian Gates. The other eras are not built. |
| **Settings rows are stubs** | Language, Terms, Privacy, Credits, Sign in with Apple all say so when tapped. |
| **Your deck does not affect the draft** | Known gap. The draft pool comes from your arena, not your deck — see DECISIONS.md. |
| **Progress is per-device** | No accounts. Clearing site data resets you. |
| **Player names are not moderated** | Shape-checked only. Not safe for strangers yet. |

---

## What we most want to know

1. Does a nine-to-fourteen-year-old understand what to do without being told?
2. Is the history interesting, or does it feel like being taught?
3. Does the counter triangle — infantry beats cavalry, cavalry beats archers,
   archers beat infantry — become obvious through playing, or does it need
   explaining?
4. Is one match the right length?
5. What is missing that you expected to be there?

---

## For the record

Fuller detail lives in the repo: [DECISIONS.md](DECISIONS.md) for every design
call and the ones that were reversed, [docs/BATTLEGROUNDS.md](docs/BATTLEGROUNDS.md)
for the thirteen grounds with their sources, and
[src/content/data/VERIFICATION.md](src/content/data/VERIFICATION.md) for the
history fact-check log.
