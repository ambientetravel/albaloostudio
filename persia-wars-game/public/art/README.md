# Art assets

Drop files here and the game picks them up automatically. Nothing needs a code
change, and every screen falls back cleanly when a file is missing — so a
half-filled folder never breaks anything.

## Intro splash

| File | Used by |
|---|---|
| `anshan-splash.png` | `src/ui/LoadingScreen.tsx` — the boot splash. Landscape, 1600×900 or larger. Falls back to the layered placeholder in `src/ui/SplashArt.tsx`. |

## Arena media — one convention for all thirteen grounds

```
art/arenas/<slug>.mp4    the battlefield's loading film
art/arenas/<slug>.png    lobby still
```

**The `.mp4` is the loading screen.** It plays full-bleed on the matchmaking
screen while the battlefield loads and an opponent is being found, runs to its
natural end, then fades off. Portrait works well (the Anshan clip is 720×1280).
Around **10 seconds** is right: it is also what times the search for a human, so
much shorter feels rushed and much longer makes every match slow to start.

**The `.png` is the lobby panel** — a calm still behind the BATTLE button. An
arena with no still gets a themed skyline in its own colours instead.

**Keep panels around 768px wide.** They render about 400px across, so 768 covers
retina with room to spare. The Ecbatana source arrived at 1536×2730 / 10 MB and
was downscaled to 768 / 2.4 MB to match Anshan — four times the pixels for the
same on-screen size is four times the download for nothing.

| # | Slug | Arena | Video | Still |
|---|---|---|---|---|
| 1 | `anshan` | Anshan | ✅ | ✅ |
| 2 | `ecbatana` | Ecbatana | ✅ | ✅ |
| 3 | `sardis` | Sardis | — | — |
| 4 | `bactra` | Bactra | — | — |
| 5 | `babylon` | Babylon | — | — |
| 6 | `pasargadae` | Pasargadae | — | — |
| 7 | `memphis` | Memphis | — | — |
| 8 | `bisotun` | Bisotun | — | — |
| 9 | `susa` | Susa | — | — |
| 10 | `gandara` | Gandara | — | — |
| 11 | `persepolis` | Persepolis | — | — |
| 12 | `royal-road` | The Royal Road | — | — |
| 13 | `persian-gates` | The Persian Gates | — | — |

Art direction for each ground — what it should look like, what is contested
about it, and the Encyclopædia Iranica links — is in
[`docs/BATTLEGROUNDS.md`](../../docs/BATTLEGROUNDS.md).

## When a new clip lands, tune its theme

Each arena re-skins the whole interface (`src/ui/arenaTheme.ts`). The twelve
themes without footage are read from each ground's art note and are a guess
until their clip arrives. To tune one:

1. Drop `art/arenas/<slug>.mp4` in.
2. Open **`http://localhost:5183/?themelab`** — a dev-only tool, never linked
   from the game and code-split out of the main bundle.
3. Click that arena. It samples seven frames, pulls a sky / mid / ground band
   and the most saturated colour, snaps each toward the nearest Achaemenid hue,
   and prints a block ready to paste into `arenaTheme.ts`.
4. **Then look at it.** The sampler is a first pass, not the answer — it reports
   what the footage averages to, which is not always what the screen wants.
   Anshan is the worked example: the clip averages to warm sand throughout, so
   the sampler proposes a sand sky, but the hand-tuned theme keeps a pale sky
   above the earth because a sky-to-ground gradient gives the UI depth that a
   flat sand field does not.

The snapping matters. Raw sampled colour across thirteen clips would give
thirteen unrelated schemes; pulling each toward a palette hue keeps the whole
ladder recognisably the same game.

## What is still procedural

The battle canvas draws its own ground. Arena 1 is a lapis-and-gold fighting
platform set in a mud-brick city, matching the Anshan key art; arenas 2–13 fall
back to the scenario's own terrain until each gets its own treatment in
`src/render/BattleCanvas.tsx`. Unit and badge artwork is still procedural
throughout (`src/render/silhouettes.ts`, `src/ui/UnitGlyph.tsx`).


## Portraits

The two figures flanking the lobby title come from `figures` on the arena in
`arenas.json`, and their art is looked up at:

```
art/portraits/<slug>-left.png
art/portraits/<slug>-right.png
```

Round crops work best; they render inside a gold ring at about 62px. Missing
files fall back to a procedural relief-style profile.

Only Anshan has figures so far — *King of Anshan and Susa* and a *Sumerian
Governor*, both attested styles for the place. An arena with no `figures` block
renders without medallions rather than inventing people for it.

## Reference

`art/ref/` holds the supplied mockups. They are not loaded by the game; they are
there so the layout can be checked against the brief.
