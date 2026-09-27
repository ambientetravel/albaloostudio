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
| `imprint.html`, `privacy.html` | Impressum under § 5 DDG / § 18 MStV and a GDPR Art. 13 notice, in English with the German terms. Every fact not in the source is a highlighted `[placeholder]`: 19 on the imprint, 12 on the privacy page. The privacy text describes what the site really does: no cookies, no analytics, fonts and GSAP self-hosted, server logs, the form, and media loading from Explora's servers until `download_media.py` has run. Supervisory authority named as LfDI Rheinland-Pfalz, Mainz, since the GmbH sits in Rennerod. Linked from every footer. | Drafted; not publishable until the placeholders are filled |
| `destinations.html`, `contact.html` | Added last on 27 Sep. Twelve region cards (the home page's eleven Explora regions plus the rivers), each with season, lines and the visa position under the house rule; contact page with the request form, the three offices from v1 and a three-step "what happens next". Nav on every page now points at these instead of the home-page anchors. | Verified with the rest, below |
| `ships.html`, `lines.html`, `itineraries.html`, `journal.html` | **v1's inner views, now real pages** (added later on 27 Sep). Fleet with the on-board notes, eight line profiles, the Aegean worked example day by day plus seven routes each with its visa line, the Kuşadası port guide in full. Share `assets/site.css` and `assets/site.js` with the home page; the nav marks the current page. Hero images reuse URLs already in the media set, so the download list is unchanged at 47. | Verified with the home page, below |
| `index.html` | **v2, the one to ship.** Single page, full-screen video hero, stacked "life on board" panels, 11 destination tiles with hover video, horizontal ship rail, Explora inclusions list, journal, request form. Media referenced from Explora Journeys' CDN via `data-media` attributes. | Renders clean; media not yet local (see below) |
| `_v1-illustrated.html` | v1, the earlier hash-routed SPA with **no external media** (SVG ships, waves, deck cut-away, route map) and five inner views: Ships, Cruise lines, Itineraries (worked Aegean example day by day), Journal (Kuşadası port guide in full), Contact. | Reference and content source; not linked, blocked in robots.txt |
| `download_media.py` | The tool the chat could not run: fetches every `data-media` / `data-media-mobile` / `data-poster` URL into `media/` and writes `media/index.json`, which the page's resolver reads at load. Stdlib only. `--check` verifies the index against the page. | Tested end to end against a local fixture server (same-basename URLs, suffix-less URLs, 404s, re-runs) |
| `assets/site.css`, `assets/site.js` | The page CSS and the media resolver / nav script, pulled out of `index.html` so five pages share one copy. The home-page GSAP choreography stays inline in `index.html`. | Done |
| `assets/fonts/` | Cormorant Garamond + Manrope, **self-hosted** (6 woff2, 204 KB, latin + latin-ext). No call to Google on page load. Ambiente Tours GmbH is a German company; LG München (2022) fined a site for hot-linking Google Fonts. | Done, verified loading in Chromium |
| `assets/vendor/` | GSAP 3.12.5 + ScrollTrigger from the npm package, replacing the cdnjs links. | Done, verified `gsap` and `ScrollTrigger` defined |
| `robots.txt`, `sitemap.xml` | Nine URLs. cruise24.me today serves a GoDaddy sitemap *index* resolving to 2 URLs; this replaces it once the site moves. | Written |

Changes made to `index.html` versus the artifact, all in `<head>` or the
resolver script, none in the copy:

- Google Fonts `<link>`s → `assets/fonts/fonts.css`; cdnjs → `assets/vendor/`.
- Added `rel=canonical`, Open Graph tags, `theme-color`, and a JSON-LD
  `TravelAgency` block (name, URL, parent Ambiente Tours GmbH, Rennerod). No
  phone, email, rate or date was added — none exists in the source.
- The "Preview: photos and video load from the media folder" badge now
  removes itself once `media/index.json` has entries.

## Verified (headless Chromium, 1440×900 and 390×844, served from this folder)

All nine pages, both widths: 0 JS errors, GSAP and both font families
resolve locally, `aria-current` lands on the right nav item, every internal
link returns 200, no horizontal overflow. Row counts: ships 9, lines 8,
itineraries 15 (8 days + 7 routes), journal 6. Home page detail:

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

Rule checks on every HTML file: «Arabian Gulf» 0 occurrences; the Dubai route
is named "Dubai and the Persian Gulf" and marked easy-visa, not no-visa; the
AROYA Red Sea route says a Saudi visa is needed and that only the line's Egypt
and Türkiye loops are visa-free ("Arabian
Peninsula" appears as Explora's own destination name, which is a different
thing). Visa statements: v1 says Greek ports are Schengen and Türkiye is
visa-free/e-visa — both correct. No rate, departure date or inclusion was
invented by this session; the inclusions list is Explora's own.

## NOT done, and why

**1. Media is not downloaded.** This container's network policy denies
`explorajourneys.com` and `dm.explorajourneys.com` (403 on CONNECT). The nine
pages share 47 distinct media URLs (the inner pages reuse the home page's).
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

**5. The request form posts nowhere**, on the home page and on `contact.html`. `onsubmit` swaps in a thank-you line.
Wire it to whatever the host provides (the boutimar.ir sites use a PHP
endpoint writing `leads.json.php`; that pattern is in the repo). Do not launch
a form that silently drops enquiries.

**6. Legal pages need facts only the company has.** `imprint.html` and
`privacy.html` are drafted with every unknown highlighted in brass: street
address, managing director, register court and HRB number, VAT ID, phone,
email, TÜRSAB licence, the hosting provider (undecided), log retention, and
whether AmbiMare acts as Reisevermittler or Reiseveranstalter on a booking.
That last one decides whether a Sicherungsschein must be issued; do not
guess it. The EU ODR platform was shut down in July 2025, so no ODR link;
the VSBG statement is there with the choice left open.

**6a. Other placeholders**: `[PHONE] · [EMAIL]` on the contact page, `[licence numbers]` in the footer, and the AmbiMedi / AmbiEvent
/ Booking conditions links are `href="#"`. Privacy and Imprint now resolve.

**7. Three journal pieces are teasers only.** "Seven nights on the Danube",
"Explora I, deck by deck" and "What a service charge actually is" exist as
three-line summaries in v1 and nowhere else; `journal.html` lists them under
"In the notebook · publishing next" without links rather than pretending
they are articles. The Kuşadası guide is the only full piece.

## Session routing

`.claude/session-routing.json` now routes **cruise24.me** to this session
(`Cruise24.me website tools`). cruise24.ir and book.cruise24.ir stay with
`Cruise24.ir storefront build`. Alireza brought the AmbiMare work here
explicitly on 27 Sep 2026.
