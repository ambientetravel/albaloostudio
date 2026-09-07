# کروزنامه hub — handoff

Owner: Alireza Mozaffari · Ambiente Turizm, Kuşadası. Architecture credit: Albaloo Studio — albaloostudio.com.
Owning session: "Daryanameh Farsi cruise domain brainstorm" (session title predates the rename) (see `.claude/session-routing.json`).

## What this is

A static Farsi cruise media site plus PWA, generated from JSON content. Same stack as cruise24.ir and
boutimar.ir (flat HTML on DirectAdmin), so the same deploy process.

    python3 build.py           # content/ + templates/ + static/  ->  public/   (126 pages today)
    python3 build.py --check   # house rules: «خلیج فارس», no "visa-free" on easy-visa ports
    node tools/shots.mjs out/  # icons, screenshots through the scroll film, real offline test

Deploy: upload the contents of `public/` to the document root of cruisenameh.com. Nothing else. Verify with
`curl -sI https://cruisenameh.com/manifest.webmanifest` (200) and `curl -sI .../sw.js` (200, served from root).

## Adding content — this is the "where do I insert" answer

Every collection is one file in `content/`. Add an object, rebuild, deploy.

| File               | Section                        | Fact keys used in the sidebar                                   |
|--------------------|--------------------------------|-----------------------------------------------------------------|
| ports.json         | بندرنامه                       | country, terminal, walkable, visa, distance_city, unesco_nearby |
| ships.json         | کشتی‌نامه                      | line, year, gt, length_m, guests, cabins, class                 |
| river-ships.json   | کشتی‌های رودخانه‌ای            | line, year, river, length_m, guests, cabins                     |
| lines.json         | خطوط کروز                      | hq, founded, fleet_size, style, iranian_passport                |
| rivers.json        | رودخانه‌ها                     | length_km, countries, season, classic_route                     |
| river-ports.json   | شهرهای رودخانه‌ای              | river, country, dock, unesco_nearby                             |
| excursions.json    | گشت و اقامت کوتاه              | port, duration, type, distance                                  |
| unesco.json        | میراث جهانی نزدیک بندرها       | country, inscribed, nearest_port, distance                      |
| hotels.json        | هتل‌ها                          | chain, city, near_port, opened                                  |
| landmarks.json     | مکان‌های تاریخی                | country, nearest_port, distance, era                            |
| gatherings.json    | نوروز و گردهمایی‌ها            | season, status, city  (+ optional `cta`)                        |
| didyouknow.json    | «می‌دانستید؟» slider           | text, link                                                      |
| glossary.json      | واژه‌نامه                      | term, def                                                       |
| articles/*.md      | مجله                           | front matter: title, date, kicker, summary                      |
| news/*.md          | اخبار                          | front matter: title, date, category, summary, **source**        |
| offers.json        | پیشنهادها (manual part)        | see below                                                       |

Item shape (all collections):

    {"slug": "kusadasi", "title": "کوش‌آداسی", "latin": "Kuşadası", "kicker": "ترکیه · دریای اژه",
     "summary": "one line", "body": ["paragraph", "paragraph"], "facts": {...},
     "related": [{"collection": "unesco", "slug": "ephesus"}],
     "image": {"src": "/img/ports/kusadasi.jpg", "alt": "", "credit": "photographer / licence"},
     "offline": true}

`image` is optional; without it the page shows a colour field. Never fill `credit` with a guess: a photo with
no known credit does not go up. `offline: true` adds the "ذخیره برای خواندن روی کشتی" button (ports have it).
New collection: add a row to `content/collections.json` and a file with the same slug; nav is in `site.json`.

## Offers, prices, itineraries

Two sources, merged at build and refreshed in the browser:

1. The live sailing feed `https://boutimar.ir/api/cruises.php` (same feed cruise24 builds from). Fields used:
   line, ship, region, nights, ports, dates, priceFrom, currency. Visa per sailing is computed from its real
   ports with `cruise24-ir/_visa.py`, the shared classifier. Build-time fetch is attempted; if the feed is
   unreachable the section says so and `static/js/offers.js` retries in the browser. It was unreachable from
   the build sandbox on 6 Sep 2026 (egress policy), so the committed `public/` has zero feed offers.
2. `content/offers.json` → `manual`: hand-entered offers. Each needs `verified_on`; without it the entry is
   ignored, on purpose.

Booking links go to cruise24.ir (`site.json` → `feed.book_url`) and are labelled «آگهی».

## The news desk

`content/news/*.md`, newest first, built to `/news/` and `/news/<slug>/`. Front matter:

    ---
    title: one sentence
    date: 2026-09-06
    category: مسیرها | بندرها | کشتی‌ها | ویزا | ایمنی
    summary: two sentences — what happened and why it matters to a Farsi reader
    source: whose fact this is          # REQUIRED
    source_url: https://...             # optional
    related: ports:kusadasi, lines:aroya
    ---

**A news item without a `source:` line is not published.** Same discipline as an offer
needing `verified_on`: we report other people's facts, so every item says whose fact it
is. The build prints what it held back — watch for `news held back (no source: line)`.
`content/news/_example.md` is the writer's template; files starting with `_` are skipped.

`related:` is `collection:slug` pairs. Use it — a route story that lands the reader on the
port and line pages is the whole reason the news desk sits next to an encyclopaedia.

Body Markdown supports `## heading`, `- list`, `**bold**`, `[link](/path)`, plus three
magazine devices: `> line` is a pull quote, `---` is a chapter rule, and
`![alt](/img/x.webp "credit")` is a full-bleed figure. The last one takes a real credit or
no credit — never a guessed one.

## Syndication — the news column on other sites

Built at every build, no server involved:

- `/news/feed.json` — headline, summary, date, category, source, canonical URL
- `/news/feed.xml` — the same as RSS
- `/embed/news.js` — a drop-in column for a partner site:

      <script src="https://cruisenameh.com/embed/news.js" data-count="5"></script>

  Optional: `data-category`, `data-theme="dark"`, `data-title`. No cookies, no dependencies.

Two rules built into it. **Teasers only, never full text** — the canonical copy stays here
so search engines never have to choose between us and a partner. **No prices in the feed** —
a stale rate republished on someone else's site under our name is the one mistake the
masthead cannot absorb.

This is *not* the offers widget. That one is white-label because it runs as the agency; this
one carries the کروزنامه name, because a wire item is worth nothing without attribution.
Keep them in separate files so nobody merges them.

## Dates — both calendars, always

`jalali.py` converts Gregorian to Solar Hijri with no dependencies (Pournader/Toossi, the
jalaali-js algorithm). `templates/_date.html` is the single partial every date goes through:
Jalali in the reading weight, Gregorian under it in muted type, ISO Gregorian in the
`datetime` attribute so feeds and search engines are unaffected.

    {% with d=item.date, compact=True %}{% include "_date.html" %}{% endwith %}

Omit `compact` for the stacked form used in the news wire. Two traps if you ever touch
`jalali.py`: the algorithm needs division that **truncates toward zero** (Python's `//`
floors and will shift dates by a whole year), and the previous-year branch uses the leap
flag of the year being *left*, not entered. Both were live bugs during the build. It is
verified against nine reference dates and a day-by-day scan from 1990 to 2050.

## The hero film

`static/img/scene-{galataport,ship,balcony,cabin}.webp` are the four hero scenes (1600×900, VP8 WebP,
55–166 KB each). They are AI-generated with Higgsfield (nano_banana_pro, 16:9) on 6 Sep 2026 and every scene
carries the credit «تصویر تولیدشده با هوش مصنوعی (Higgsfield)» in `site.json` → `hero.scenes[].credit` — keep
the credit if the images stay, change it if they are replaced with licensed photographs. The build sandbox
cannot reach the Higgsfield CDN, so the files were moved through the Higgsfield sandbox as base64 chunks and
md5-checked on both ends; if you regenerate, do it from a machine with normal egress.
Shot list, should you reshoot with a camera: (1) Galataport quay at dusk with a ship moored, (2) the ship's
side, rows of balconies, from the quay, (3) a balcony looking through the open door, (4) the cabin interior
with the sea in the glass. Same file names, or edit `site.json` → `hero.scenes`, and the film works unchanged.
The engine is `static/js/hub.js` (no library; a sticky stage scrubbed against scroll with damping).
`prefers-reduced-motion` and no-JS get the cabin scene and the full interface immediately.

## PWA

`manifest.webmanifest`, `sw.js`, `precache.json` (written by the build). Verified in Chromium with the server
killed: a saved port guide opens, an unsaved page shows the offline screen. iOS installs via Share → Add to
Home Screen; Android prompts. Store wrappers (Capacitor, Cafe Bazaar, Myket) are a later step.

## Not done, deliberately

- Port/article photographs. Only the four hero scenes exist (AI-generated, credited); everything else is a colour field until licensed photos exist.
- Newsletter form posts nowhere yet (`site.json` → `channels.newsletter_action`); wire to nitrosend.
- Telegram link is a placeholder handle (`t.me/cruisenameh`) until the channel exists.
- Podcast section says «به‌زودی».
- News is three seed items only; the desk needs 3–6 a week to do its job.
- No Jalali date *input* — front matter dates are ISO Gregorian and converted for display.
- Domain not registered; nothing deployed.
- Fonts load from Google Fonts. Self-host Vazirmatn before launch for readers inside Iran.
