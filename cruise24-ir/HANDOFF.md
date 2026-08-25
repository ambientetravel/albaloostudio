# cruise24.ir — handoff

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari
Written 26 Aug 2026 by session `claude-websitebuilder-49`.

## What this is

Fifteen generated pages for cruise24.ir, built from the live sailing feed at
`https://boutimar.ir/api/cruises.php` (3,485 sailings). Bundle:
`~/Downloads/cruise24-ir-pages-20260826.zip`.

## Why, in one paragraph

cruise24.ir surfaced in Search Console for exactly one keyword. `sitemap.xml`
declared FOUR URLs while **38 pages were live and returning 200** — including
23 ship pages reachable only from the line pages, which were themselves
undeclared. Crawling from the homepage finds 12 of the 38, which is why the
first count here said nine; every URL was later verified by request. `/msc.html` carried 242 words while MSC is 3,237 of the 3,485 sailings.
Separately, a 769-term Farsi demand corpus lives in
`orchestrator/data/cruise-demand-fa.json`, and 752 of those terms return
nothing from any property we own.

## The properties are segmented — do not blur them

| Property | Audience | Keyword set |
|---|---|---|
| **cruise24.ir** | B2C, inside Iran | all 769 Farsi terms — this repo |
| boutimar.ir | B2B, agencies | `b2b-demand-fa.json` — **5 terms; SEO is the wrong channel** |
| cruisebaz.com | diaspora, dual-citizen | `diaspora-demand-en.json` — 21 terms, Persian-themed charters |

**cruisebaz owns all five page-1 rankings we have** — قیمت کروز (3.0), تور کشتی
کروز (7.0), کشتی کروز (7.0), aroya (8.3), عربستان (8.7). Do not build cruise24
pages targeting those five head terms. There is no need: 752 of 769 terms are
absent everywhere, so there is nothing to fight over.

## Files

- `_build.py` — the generator. `python3 _build.py` writes `public/`;
  `--check` verifies what is on disk still matches the feed.
- `_visa.py` — visa truth per sailing, from its real ports.
- `_chrome.py` — nav/footer/head lifted verbatim from the live site 26 Aug.
- `public/` — 15 pages + `sitemap.xml` (**49 URLs**: 38 existing + 15 generated,
  minus 4 line pages that appear in both).

## Rules the generator enforces, not suggests

1. **Nothing is invented.** Every count, ship name, port, night, price and date
   is read from the feed at build time. `priceFrom` is on 3,464 of 3,485
   sailings and the pages say "cheapest starting point", never a made-up rate.
2. **`_build.py` refuses to write a page with zero sailings behind it.**
   The single exception is `cruise-kish.html`, whose entire subject is that no
   line calls at Kish — 21 keyword terms of real demand, zero inventory, and
   the honest answer is the page.
3. **«خلیج فارس» only.** Checked on the generated output, build fails otherwise.
4. **Visa accuracy per sailing.** Persian Gulf and Dubai pages say
   **ویزای آسان** and state in the page that "no visa" is false. Greek, Italian,
   Spanish and French ports force Schengen — which is why `cruise-turkiye.html`
   says Schengen despite Türkiye itself being visa-free. Port matching is by
   explicit list, never substring: «رم» sits inside «مارماریس».

## Two findings that look like data gaps and are not

**celestyal.html and explora.html have ZERO Farsi demand terms.** Not missing
data — nobody searches those brand names in Persian. They belong in the
sitemap and on cruise-lines.html; do not "fix" the zero by hunting for
keywords that do not exist.

**Demand and inventory are inverted, and it is a sourcing signal, not an SEO
one.** Persian Gulf and Dubai are 199 keyword terms against **18 sailings**
(0.5% of the catalogue, and they are the same 18). Mediterranean is **2,445
sailings** against 6 terms. Iranians search the Gulf; the company sells the
Western Med. No amount of page-building fixes that.

## What is NOT done

- **Not deployed.** The zip is built; DirectAdmin upload is a hand-off.
- **Not submitted to Google/Bing.** See the indexing prompt in the session.
- **No internal links from the existing pages into the new ones.** `index.html`
  and `cruise-lines.html` are hand-written and were not touched. Adding links
  from them is the single highest-value follow-up — 15 orphan pages rank far
  worse than 15 linked ones.
- **`cruise-prices.html` is 379 words** and `cruise-kish.html` is 202. Both are
  intentionally short but both are thin; prose would help.
- **Ship pages already exist — 29 of them.** `msc-*.html` (24),
  `celestyal-*.html` (2), `explora-*.html` (3). Live, well-built, and NOT new
  work. Do not build them.
- **The internal link layer does not exist.** Not weak — absent. Every internal
  href across all 38 pages was parsed: `index.html` reaches 4 pages,
  `cruise-lines.html` reaches the 4 line pages, and the line pages link ZERO
  ship pages. **29 of 38 pages have no inbound link from anywhere**, so a
  crawler reaches 9. The sitemap is currently the only way in, and until
  26 Aug it declared four URLs.
- The generated fleet tables now fix most of this: `msc.html` links its 24
  ships, `celestyal.html` its 2, `explora.html` its 3. 29 pages go from
  unreachable to one hop from a hub. `aroya.html` links none, correctly — the
  AROYA ship shares the line's name and would link to itself; `ship_href()`
  refuses any slug that is a line page.
- **None of the 38 pre-existing pages has `rel=canonical`.** The 15 generated
  ones do. Adding it to the hand-written pages is a cheap follow-up.

## Regenerating

The feed changes. `python3 _build.py` is idempotent and safe to re-run; a
re-run after new sailings load will change counts and prices, which is correct.
`--check` in CI would catch a stale deploy.
