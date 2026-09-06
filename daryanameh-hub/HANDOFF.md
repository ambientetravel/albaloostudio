# دریانامه hub — handoff

Owner: Alireza Mozaffari · Ambiente Turizm, Kuşadası. Architecture credit: Albaloo Studio — albaloostudio.com.
Owning session: "Daryanameh Farsi cruise domain brainstorm" (see `.claude/session-routing.json`).

## What this is

A static Farsi cruise media site plus PWA, generated from JSON content. Same stack as cruise24.ir and
boutimar.ir (flat HTML on DirectAdmin), so the same deploy process.

    python3 build.py           # content/ + templates/ + static/  ->  public/   (126 pages today)
    python3 build.py --check   # house rules: «خلیج فارس», no "visa-free" on easy-visa ports
    node tools/shots.mjs out/  # icons, screenshots through the scroll film, real offline test

Deploy: upload the contents of `public/` to the document root of daryanameh.com. Nothing else. Verify with
`curl -sI https://daryanameh.com/manifest.webmanifest` (200) and `curl -sI .../sw.js` (200, served from root).

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
- Telegram link is a placeholder handle (`t.me/daryanameh`) until the channel exists.
- Podcast section says «به‌زودی».
- Domain not registered; nothing deployed.
- Fonts load from Google Fonts. Self-host Vazirmatn before launch for readers inside Iran.
