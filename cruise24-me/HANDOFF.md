# cruise24.me — Cruise24, handoff

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari
Written 27 Sep 2026 by session `Cruise24.me website tools`, taking over the
claude.ai chat "building a professional cruise website".

## What this is

**Cruise24** is the brand, at **cruise24.me**: it brings the world of cruising to
the Middle East market. Ocean, river and all-suite luxury journeys worldwide,
sold to travellers in the region. "Excellent cruise deals of the Middle East"
in the logo means the market, not the cruising area (Alireza, 27 Sep).
**AmbiMare** stays only as the wordmark beside the logo in the header, and as
an `alternateName` in the home page's JSON-LD. Ambiente Tours GmbH remains the
legal entity on the imprint, privacy and booking conditions pages. cruise24.ir
is still the Farsi B2C twin. The chat produced two artifacts; both are in this
folder.

| File | What | Status |
|---|---|---|
| `conditions.html` | Booking conditions, English only (rewritten 28 Sep: no German headings, no notes to the owner on the page). Covers both roles: travel agent for a cruise on its own, Ambiente Tours GmbH as organiser for packages. No gaps left; terms that vary by booking are stated as "in the offer and the confirmation". Decisions taken in the text are listed in `HANDOFF-legal.md`. | Drafted; needs a travel-law read |
| `assets/logo*.png`, `favicon-*.png`, `og-image.jpg` | The logo Alireza supplied on 27 Sep (kept as `logo-as-supplied.png`, 1080²; corrected master `logo-master.png`), cut into transparent ink and white lockups, a nav mark without the tagline, favicons at 32/180/512 and a 1200×630 Open Graph card. Every page links the icons and the OG image; the home page's JSON-LD carries `logo` and `sameAs` for the Facebook and Instagram pages. | Done |
| `imprint.html`, `privacy.html` | Imprint (§ 5 DDG / § 18 MStV) and GDPR Art. 13 notice, English only since 28 Sep. Missing company facts show as short highlighted labels: 9 on the imprint, 4 on the privacy page, all listed in `HANDOFF-legal.md`. The privacy page now says all media, fonts and scripts are self-hosted (true since `media/index.json` covers every `data-media` URL). | Not publishable until the labels are filled |
| `destinations.html`, `contact.html` | Added last on 27 Sep. Twelve region cards (the home page's eleven Explora regions plus the rivers), each with season, lines and the visa position under the house rule; contact page with the request form, the three offices from v1 and a three-step "what happens next". Nav on every page now points at these instead of the home-page anchors. | Verified with the rest, below |
| `lines.html`, `journal.html` | **v1's inner views, now real pages** (27 Sep). `lines.html` is **Lines & ships** since 28 Sep: the line profiles, each linking to its own sailings, then the nine ship entries with photos (`#ships`). `journal.html` has the Kuşadası port guide in full. | Verified on mobile 28 Sep |
| `ships.html`, `itineraries.html` | **Redirects since 28 Sep** (meta refresh + JS + canonical, `noindex`): ships to `lines.html#ships`, itineraries to `destinations.html#itineraries`, where the Aegean worked example, its route map (ports by coordinates) and the seven seasonal routes now live. Kept so old links and bookmarks still land. Not in the sitemap. | Done |
| `mice.html` | **MICE at sea** (28 Sep): events a ship does well (incl. private celebrations, `#celebrations`), three ways to take a ship (suites, allocation, full charter), Explora Journeys / Silversea / MSC Cruises, the Explore Orient land-and-sea partnership (`#explore-orient`), and brief-to-gangway steps. Explora and Silversea facts are from their own MICE pages, fetched 28 Sep 2026 and cited on the page; MSC's MICE page is not reachable from this environment (`*.msccruises.com` blocked), so the MSC card only uses figures already on the site. | Verified on mobile 28 Sep |
| `about.html` | **About** (28 Sep): Cruise24, the AmbiMare wordmark, Ambiente Group with Ambiente Tours GmbH (Rennerod, DACH) and Ambiente Turizm Seyahat (Kuşadası, MENAT), and the group companies (Explore Orient, Ambiente Travel, AmbiMedi, AmbiEvent). No dates, sizes or licences claimed. | Verified on mobile 28 Sep |
| `index.html` | **v2, the one to ship.** Single page, full-screen video hero, stacked "life on board" panels, 11 destination tiles with hover video, horizontal ship rail, Explora inclusions list, journal, request form. Media referenced from Explora Journeys' CDN via `data-media` attributes. | Renders clean; media not yet local (see below) |
| `_v1-illustrated.html` | v1, the earlier hash-routed SPA with **no external media** (SVG ships, waves, deck cut-away, route map) and five inner views: Ships, Cruise lines, Itineraries (worked Aegean example day by day), Journal (Kuşadası port guide in full), Contact. | Reference and content source; not linked, blocked in robots.txt |
| `download_media.py` | The tool the chat could not run: fetches every `data-media` / `data-media-mobile` / `data-poster` URL into `media/` and writes `media/index.json`, which the page's resolver reads at load. Stdlib only. `--check` verifies the index against the page. Since 27 Sep it also carries three ideas from the chat's own original script, which Alireza uploaded: full-size Scene7 renditions (`?wid=2560&fmt=jpeg&qlt=90` on `dm.explorajourneys.com/is/image/…`), a `Referer: https://explorajourneys.com/` header sent only to Explora's hosts, and six parallel downloads (`--workers`). That script needed a `media_manifest.json` of ~400 files that never reached the repo; this one reads the URLs from the pages. | Tested end to end against a local fixture server (same-basename URLs, suffix-less URLs, 404s, re-runs) |
| `assets/site.css`, `assets/site.js` | The page CSS and the media resolver / nav script, pulled out of `index.html` so five pages share one copy. The home-page GSAP choreography stays inline in `index.html`. | Done |
| `assets/fonts/` | Cormorant Garamond + Manrope, **self-hosted** (6 woff2, 204 KB, latin + latin-ext). No call to Google on page load. Ambiente Tours GmbH is a German company; LG München (2022) fined a site for hot-linking Google Fonts. | Done, verified loading in Chromium |
| `assets/vendor/` | GSAP 3.12.5 + ScrollTrigger from the npm package, replacing the cdnjs links. | Done, verified `gsap` and `ScrollTrigger` defined |
| `robots.txt`, `sitemap.xml` | Ten URLs. cruise24.me today serves a GoDaddy sitemap *index* resolving to 2 URLs; this replaces it once the site moves. | Written |

Changes made to `index.html` versus the artifact, all in `<head>` or the
resolver script, none in the copy:

- Google Fonts `<link>`s → `assets/fonts/fonts.css`; cdnjs → `assets/vendor/`.
- Added `rel=canonical`, Open Graph tags, `theme-color`, and a JSON-LD
  `TravelAgency` block (name, URL, parent Ambiente Tours GmbH, Rennerod). No
  phone, email, rate or date was added — none exists in the source.
- The "Preview: photos and video load from the media folder" badge now
  removes itself once `media/index.json` has entries.

## Inventory: CruiseHost direct + Variety's own site (27 Sep, late)

**Why:** "View journeys" led to the enquiry form; nothing was backed by sailing data.
Alireza set the direction: .ir is a sales and sanctions barrier, so cruise24.me must
not depend on it; focus on Explora Journeys, Silversea and similar luxury lines, plus
Variety (Greek islands, Kuşadası) and Scenic (river); Türkiye, Greece and Italy first,
every other destination kept.

**The method** came from boutimar.ir (`ambientetravel/boutimarfarsi`,
`data/cruisehost/cruisehost_sync.py`): CruiseHost CPX, aid 204622, the Ambiente Tours
contract. cruise24.me now calls CruiseHost directly; nothing here touches .ir.

**What was fetched on 27 Sep** (`sync/cruisehost_sync.py --full --write`, 254 pages,
3 to 6 s apart, neutral User-Agent):

| Line | CruiseHost code | Scope | Departures | Itineraries | In Türkiye/Greece/Italy |
|---|---|---|---:|---:|---:|
| Explora Journeys | EXP | everywhere | 404 | 352 | 105 |
| Silversea | SSE | everywhere | 529 | 369 | 77 |
| Scenic, ocean | SLC | everywhere | 125 | 99 | |
| Scenic, river | SLC | everywhere | 1,082 | 528 | 49 (Scenic total) |
| Seabourn | SBN | Mediterranean | 81 | 77 | 74 |
| Regent Seven Seas | REG | Mediterranean | 71 | 70 | 63 |
| Ponant | COM | Mediterranean | 107 | 89 | 72 |
| SeaDream | SDM | Mediterranean | 26 | 24 | 17 |
| Sea Cloud | SCD | Mediterranean | 26 | 25 | 16 |
| Star Clippers | CLP | Mediterranean | 75 | 51 | 47 |
| Variety Cruises | not in CruiseHost | varietycruises.com | 323 | 19 | 8 |
| **Total** | | | **2,849** | **1,703** | **528** |

Line codes were confirmed from CruiseHost's own line list (`Search/count/json`), not
guessed. **Trap found:** CruiseHost silently ignores an unknown line name and returns the
WHOLE catalogue (53,262); `--discover` now rejects any name CruiseHost does not echo back.
Also: the total lives in `count`, not `allentries` as boutimar.ir's notes say.

"Similar lines" are Mediterranean-only on purpose. Growing them into more areas is one
word per line in `LINES` (`"scope": "focus"` -> `"all"`), then a `--full --write`.

**Variety** is not in CruiseHost. `sync/variety_sync.py` reads its 24 cruise pages: the
schema.org route, day titles, included / not included, and every departure from the
page's booking data with EUR fares. The "from" is the cheapest cabin category that still
has cabins (Variety's own site does the same: 9 Oct 2026 shows Category B because C is
full); a departure with none left shows "Sold out". One cruise (Croatia island hopping)
has no booking data on its page, only USD prices, so its dates show and the fare is "on
request" rather than a converted figure. 5 of 24 cruises show no departures on the site.

**Build** (`build_journeys.py`, ~2 s): 1,703 pages in `journeys/`, `journeys.html` (37 KB,
36 cards in the HTML, the rest paged 24 at a time from `data/journeys-index.json`, 624 KB,
86 KB gzipped), `ports.html`, home search months, destination counts, sitemap.
**Filter links:** `journeys.html#<area>.<month>[.<line>]`, e.g. `#greece.2027-05`,
`#all.any.silversea`, `#rivers.any.scenic` (`all`/`any` = no filter; line values are the
`f-line` option slugs). `lines.html` links each line this way; an in-page hash change resets
any part it leaves out.
**Generated files are not in git** (`journeys/`, `data/sailings.json`,
`data/journeys-index.json`): run the build before every deploy bundle.

**Visa accuracy:** `port_countries.py` places 13,642 of 14,208 port calls (96%). What is
left is mostly names that exist in several countries (St. John, St. Georges, Georgetown,
Castro, "Pirau"). Any sailing with an unplaced stop says so on its visa list (285 of
1,703) instead of implying the list is complete. Schengen now includes Romania and
Bulgaria; Serbia, Cyprus, the UK, Ireland, Greenland, the Faroes, Svalbard and French
overseas territories are called out as outside it.

**Photos:** CruiseHost ship photos (61, 8.6 MB) in `media/cruisehost/`, named by CruiseHost
ship code (MW = MSC World Europa, WE/W9 = Celestyal Journey/Discovery, 03/11 = nickoVision/
nickoSpirit, all checked by eye); Explora keeps its own imagery; Variety uses the yacht and
destination photos from the boutimar.ir repo. `media/lines/` holds photos taken from the
lines' own sites (28 Sep 2026): `arosa-sena.jpg` (a-rosa.de, A-ROSA drone shot, no credit
given on the page) and `silver-by-amadeus.jpg` (amadeus-flusskreuzfahrten.de, file credit
"(c) Martin de Bock", cropped to the ship). Amadeus's own page now calls Silver III
"Silver by AMADEUS" (same 2016 build, 168 guests, photos still filed as Silver III); the
site uses the new name. AROYA's own site (aroya.com) sits behind a Cloudflare bot check, so
its card uses `aroya-rhodes.jpg` from Wikimedia Commons instead: "Aroya moored at Quay in
Port of Rhodes 29 July 2025" by Pjotr Mahhonin, CC BY-SA 4.0, cropped. The licence needs the
visible credit and licence link on the card (they are there) and keeps the crop under
CC BY-SA 4.0. Wikipedia confirms the ship's history: built 2017 as World Dream, Manara in
2023, AROYA since July 2024. Note: the Commons API rate-limits this environment's shared
address (HTTP 429); the ordinary file pages and upload.wikimedia.org thumbnails work.

**Still blocked (network):** Silversea's photo hosts `cdn.sanity.io` and
`silversea.widen.net`; Variety's `d2koisdtuu1wg4.cloudfront.net` (photos) and
`varietycruises.app.nelios.com` (video); every Scenic domain tried. `assets.msccruises.com`
answers 401 (needs a login). Nothing on the site depends on these.

**Before scheduling the sync:** confirm with CruiseHost that systematic retrieval under
the contract is permitted. Daily: `--rolling 30 --write`; monthly: `--full --write`.

**Do not deploy:** `data/sources/`, `data/data-checks.json`, `data/sailings.json`, `sync/`,
`media-originals/`, `*.py`, `HANDOFF*.md` (incl. `HANDOFF-exploreorient-mice.md`, `HANDOFF-legal.md`), `_v1-illustrated.html`, `social/` (LinkedIn images, copy and Chrome prompt).

## Design, restyled around the logo (27 Sep, later)

The logo is monochrome line art: near-black navy ink (#0c1824) on white with
a pale blue wash (#e2ecf5), heavy geometric numerals, a letterspaced caps
tagline and dotted rules. `assets/site.css` now follows it: ink and wash as
the two backgrounds, one steel-blue accent (#1e4d7a on light, #9fbad6 on
dark) instead of the brass-and-teal pair, Manrope 700 for every heading
instead of the Cormorant serif, kickers as letterspaced caps with a dotted
lead line, 10px corners instead of pills, dotted footer rule. The Cormorant
files stay in `assets/fonts/` but nothing references them; delete when sure.

**The three logo questions, resolved 27 Sep:**
1. Brand is **Cruise24** on every page. AmbiMare stays as the header wordmark.
2. "Of the Middle East" is the market. The home page's title, description,
   kicker, lede, manifesto, footer blurb and JSON-LD `areaServed` now say so.
3. The misspelled tagline ("EXCCELENT" with a broken C) is fixed in
   `assets/logo-master.png`: that one line retyped in Lexend Bold, fitted to the
   original line's measured ink box (210,834)–(874,868), every other pixel
   verified identical. The file as supplied is kept as `logo-as-supplied.png`;
   every cut-out, favicon and the OG card are regenerated from the master.
   If the designer has the source file, their own fix should replace this one.

**Languages, decided 27 Sep:** the contact page stays English, German,
Turkish or Italian. Alireza: leave Arabic and Farsi out.

**Why the preview has no photos or video, two separate blocks:**
1. This cloud container's network policy denies `explorajourneys.com` and
   `dm.explorajourneys.com` (403 on CONNECT), so `download_media.py` cannot
   fetch anything here.
2. The claude.ai artifact preview only shows images and video published with
   the page itself. Its content security policy blocks every other host, so
   the page's fallback to Explora's URLs never loads there either.
Fix: add both hosts to this environment's allowed domains (environment menu
in the session title bar, Edit, Network access), then run the downloader
here and publish `media/` with the page. Sessions on Alireza's Mac have
full internet, which is why other projects could place media directly.

## Verified (headless Chromium, 1440×900 and 390×844, served from this folder)

All ten pages, both widths: 0 JS errors, GSAP and both font families
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

**1. Media: downloaded and web-sized, 27 Sep.** Alireza allowed
`explorajourneys.com` and `dm.explorajourneys.com` in the environment's network
settings. `download_media.py` fetched all 47 URLs (1.1 GB; one Scene7 image
refuses 2560px and is taken at 1920px). `optimize_media.py` then made them
web-sized: 1.1 GB -> 49.7 MB, every file under the preview's 15 MB cap.

| | before | after |
|---|---:|---:|
| largest photo (F1-44.jpg) | 50.9 MB | 513 KB |
| hero video, 1920x1080, full 24.6 s loop | 87.7 MB | 8.1 MB |
| 4K destination loops, now 1280x720, 11 s | ~26 MB each | 1.3–2.4 MB |
| Endless Worlds film, first 12 s only | 377 MB | 895 KB |

Photos are committed (`media/*.jpg|jpeg|webp`, longest edge 2000px).
Videos stay gitignored, 18 files: upload `media/` to the host with the site.
The CDN masters are kept locally in `media-originals/` (gitignored), so
`optimize_media.py --force` can re-encode with different settings.
Verified in Chromium on all content pages at 1440 and 390 wide: every photo
loads from `media/`, zero requests go to Explora. The test browser has no
H.264 decoder, so playback was proven on a throwaway VP9 copy: hero autoplays,
panels play on scroll, destination cards play on hover and stop on leave. The
real files are H.264 High, no audio, index first (`faststart`), 18/18.

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
The same question now covers the CruiseHost ship photos and the A-ROSA and Amadeus
photos in `media/lines/`: agency terms usually allow them, but nobody has checked.

**4. Two copy claims to confirm before launch**, both from the chat:
"Explora I in Port Hercule for the 2027 Grand Prix" (the image path
`f1-2027/` suggests Explora has such a programme, but a departure is a
departure), and "Ambiente has planned quiet European travel for twelve years".

**5. Request form: wired (28 Sep).** Both forms (home, `contact.html`) post to `api/enquiry.php`, which
validates, rate-limits (5 per address per 10 min, address stored hashed), drops bots via a hidden
honeypot, and appends one NDJSON line to `api/data/leads.ndjson.php` in the lead shape the pipeline
reads (`channel: site_form`, `from_ref`, `message`, `landing_path`, `received_at`, plus `sailing_ref`
when the visitor came from a sailing page). The page says "thank you" only when the server confirms;
a failure is shown as a failure, and on the static preview (no PHP) that is what you will see.
`api/leads.php` hands new leads to agent 4, HMAC-signed exactly like every other hop
(`--leads-url https://cruise24.me/api/leads.php`); without a secret it answers 503, never unsigned data.
Stored files cannot be read over the web (the `.php` guard line answers 404 even without `.htaccess`).
On the server: copy `api/config.sample.php` to `api/config.php` and set `signing_secret`, `ip_salt`,
and optionally `notify_to` for a copy to our inbox. Tested on PHP 8.4: all paths, and the signed pull
with the orchestrator's own `config.signed_headers`.

**5a. Deploy bundle: `python3 build_bundle.py`.** It runs a pre-launch check first and refuses to build
while a blocker is open: highlighted gaps, bracket placeholders, "Arabian Gulf", broken internal links,
sitemap pages missing. On 28 Sep the check found 1,881 files, 0 broken links, and two blockers: the
12 legal gaps and `[PHONE]` / `[EMAIL]` on the contact page. `--draft` builds anyway for a staging
upload. The zip stores paths relative to the docroot (extract INTO `public_html`) and a `.sha256`
manifest sits next to it, for diffing the live server after upload.

**6. Legal pages need facts only the company has.** The full list, and the
decisions already written into the text (both roles, insolvency protection,
dispute resolution, no data protection officer), is in `HANDOFF-legal.md`.
Search the three pages for `class="todo"` before go-live: there must be no matches left. The
EU ODR platform was shut down in July 2025, so there is no ODR link.

**6a. Other placeholders**: `[PHONE] · [EMAIL]` on the contact page. The footer no longer carries `[licence numbers]` (removed on
Alireza's instruction, 28 Sep); it presents Ambiente Group with its two companies and markets instead. The TÜRSAB licence line was dropped from the imprint too; the German GmbH is the provider. AmbiMedi and AmbiEvent are named on the About page without links until their sites exist.

**Menu (28 Sep):** Journeys · Destinations · Lines & ships · MICE at sea · Journal · About · Contact. The menu and footer live
in `index.html`; `build_journeys.py` copies them into journeys.html, ports.html and every sailing page, so edit them there and
copy to the other static pages.

**7. Three journal pieces are teasers only.** "Seven nights on the Danube",
"Explora I, deck by deck" and "What a service charge actually is" exist as
three-line summaries in v1 and nowhere else; `journal.html` lists them under
"In the notebook · publishing next" without links rather than pretending
they are articles. The Kuşadası guide is the only full piece.

## Session routing

`.claude/session-routing.json` now routes **cruise24.me** to this session
(`Cruise24.me website tools`). cruise24.ir and book.cruise24.ir stay with
`Cruise24.ir storefront build`. Alireza brought the Cruise24 work here
explicitly on 27 Sep 2026.
