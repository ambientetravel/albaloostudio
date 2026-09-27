# cruise24.me — AmbiMare, handoff

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari
Written 27 Sep 2026 by session `Cruise24.me website tools`, taking over the
claude.ai chat "building a professional cruise website".

## What this is

AmbiMare is the sea collection of Ambiente Group, to live at **cruise24.me**:
ocean, river and all-suite luxury journeys for a world audience (the English
twin of cruise24.ir, which stays Farsi B2C). The chat produced two artifacts;
both are in this folder, unchanged in copy, changed only in plumbing.

| File | What | Status |
|---|---|---|
| `index.html` | **v2, the one to ship.** Single page, full-screen video hero, stacked "life on board" panels, 11 destination tiles with hover video, horizontal ship rail, Explora inclusions list, journal, request form. Media referenced from Explora Journeys' CDN via `data-media` attributes. | Renders clean; media not yet local (see below) |
| `_v1-illustrated.html` | v1, the earlier hash-routed SPA with **no external media** (SVG ships, waves, deck cut-away, route map) and five inner views: Ships, Cruise lines, Itineraries (worked Aegean example day by day), Journal (Kuşadası port guide in full), Contact. | Reference and content source; not linked, blocked in robots.txt |
| `download_media.py` | The tool the chat could not run: fetches every `data-media` / `data-media-mobile` / `data-poster` URL into `media/` and writes `media/index.json`, which the page's resolver reads at load. Stdlib only. `--check` verifies the index against the page. | Tested end to end against a local fixture server (same-basename URLs, suffix-less URLs, 404s, re-runs) |
| `assets/fonts/` | Cormorant Garamond + Manrope, **self-hosted** (6 woff2, 204 KB, latin + latin-ext). No call to Google on page load. Ambiente Tours GmbH is a German company; LG München (2022) fined a site for hot-linking Google Fonts. | Done, verified loading in Chromium |
| `assets/vendor/` | GSAP 3.12.5 + ScrollTrigger from the npm package, replacing the cdnjs links. | Done, verified `gsap` and `ScrollTrigger` defined |
| `robots.txt`, `sitemap.xml` | One URL. cruise24.me today serves a GoDaddy sitemap *index* resolving to 2 URLs; this replaces it once the site moves. | Written |

Changes made to `index.html` versus the artifact, all in `<head>` or the
resolver script, none in the copy:

- Google Fonts `<link>`s → `assets/fonts/fonts.css`; cdnjs → `assets/vendor/`.
- Added `rel=canonical`, Open Graph tags, `theme-color`, and a JSON-LD
  `TravelAgency` block (name, URL, parent Ambiente Tours GmbH, Rennerod). No
  phone, email, rate or date was added — none exists in the source.
- The "Preview: photos and video load from the media folder" badge now
  removes itself once `media/index.json` has entries.

## Verified (headless Chromium, 1440×900 and 390×844, served from this folder)

| Check | Desktop | Mobile |
|---|---|---|
| Page errors (JS) | 0 | 0 |
| GSAP + ScrollTrigger loaded from `assets/vendor/` | yes | yes |
| Cormorant Garamond and Manrope resolved locally | 11 faces loaded | 11 faces loaded |
| Sections present | 11 of 11 | 11 of 11 |
| Horizontal overflow | none (1440 = 1440) | none (390 = 390) |
| Local requests | 9 × 200, 1 × 404 (`media/index.json`, expected before download) | same |
| Failed remote requests | 35, all `explorajourneys.com` / `dm.explorajourneys.com` | 35, same |
| JSON-LD parses | `TravelAgency` | `TravelAgency` |

Rule checks on both HTML files: «Arabian Gulf» 0 occurrences ("Arabian
Peninsula" appears as Explora's own destination name, which is a different
thing). Visa statements: v1 says Greek ports are Schengen and Türkiye is
visa-free/e-visa — both correct. No rate, departure date or inclusion was
invented by this session; the inclusions list is Explora's own.

## NOT done, and why

**1. Media is not downloaded.** This container's network policy denies
`explorajourneys.com` and `dm.explorajourneys.com` (403 on CONNECT). The page
has 47 media URLs (44 `data-media`, 6 posters, 1 mobile hero; 47 distinct).
Run on any machine with normal internet:

    cd cruise24-me
    python3 download_media.py --no-videos     # images first, ~1 min
    python3 download_media.py                 # then the ~20 mp4s
    python3 download_media.py --check         # must print OK

Videos are gitignored (`cruise24-me/media/*` except `index.json` and
`.gitkeep`); commit `index.json`, upload `media/` to the host with the site.
Expect the videos to be large — Explora serves desktop hero clips at tens of
MB each. If total is uncomfortable, `ffmpeg -i in.mp4 -vf scale=1920:-2 -crf 28
-an out.mp4` on the hero and panel clips is the usual fix; the resolver does
not care what is inside the file.

**2. Hosting: the site cannot go where cruise24.me currently is.**
`orchestrator/sites.yml` records cruise24.me on **GoDaddy Website Builder** —
no file access, no API, `adapter: unimplemented`. A static folder with a media
directory needs real hosting: the DirectAdmin account that carries
boutimar.ir / cruise24.ir is the obvious place (add the domain, point DNS).
That is a decision and a DNS change, not a build step. Until then there is
nothing to write a DirectAdmin prompt for.

**3. Explora Journeys media rights.** The footer says "Explora Journeys
imagery used with permission of the line". That sentence came from the chat,
not from a document. Trade partners normally get an asset library under the
line's agency terms; if that agreement exists, keep the line. If not, it
must go before launch — it is a factual claim under the company name.

**4. Two copy claims to confirm before launch**, both from the chat:
"Explora I in Port Hercule for the 2027 Grand Prix" (the image path
`f1-2027/` suggests Explora has such a programme, but a departure is a
departure), and "Ambiente has planned quiet European travel for twelve years".

**5. The request form posts nowhere.** `onsubmit` swaps in a thank-you line.
Wire it to whatever the host provides (the boutimar.ir sites use a PHP
endpoint writing `leads.json.php`; that pattern is in the repo). Do not launch
a form that silently drops enquiries.

**6. Footer placeholders**: `[licence numbers]`, and the AmbiMedi / AmbiEvent
/ Booking conditions / Privacy / Imprint links are `href="#"`. A German
company site legally needs a reachable Impressum and Datenschutz page.

**7. v1's inner pages are not in v2.** The Kuşadası port guide, the Aegean
day-by-day, the eight cruise-line profiles and the fleet notes exist only in
`_v1-illustrated.html`. Worth lifting into real `/journal/`, `/ships/`,
`/lines/` pages — v2 links its journal cards to Explora's site, so today the
only original editorial on the page is two teaser cards.

## Session routing

`.claude/session-routing.json` now routes **cruise24.me** to this session
(`Cruise24.me website tools`). cruise24.ir and book.cruise24.ir stay with
`Cruise24.ir storefront build`. Alireza brought the AmbiMare work here
explicitly on 27 Sep 2026.
