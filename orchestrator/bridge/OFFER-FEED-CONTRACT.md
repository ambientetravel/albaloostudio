# Offer feed contract — `offer.v1`

## Why
The writer (Agent 2) had no idea what each site actually sells. Told only "never
invent a rate," it defended that rule by *denying products exist* — on 17 Sep it
wrote "Explore Orient does not currently hold a proprietary Silk Road itinerary"
about a site whose flagship IS a Silk Road tour, and "a cruise house first" on a
land-travel guide. It can now be handed each site's real catalogue as ground
truth. This is the contract that catalogue must meet.

## Where it lives
A single public JSON file per site, at the URL in that site's `offer_feed` in
`orchestrator/sites.yml`:

| Site | offer_feed URL | Owning session builds it |
|------|----------------|--------------------------|
| exploreorient.com | `/inventory/offer.json` | Explore Orient — extend `scripts/export-inventory.mjs` |
| boutimar.com | `/offer.json` | Boutimar.com — from cities/hotels/itineraries JSON |
| boutimar.ir | `/offer.json` | boutimar cruise — from the cruise feed (`api/cruises.php`) |
| cruise24.ir | `/offer.json` | Cruise24.ir — from the partner API it already proxies |

It must be served with permissive CORS (the others already are) and be a real
static/generated file, not behind auth — the pipeline fetches it unauthenticated
over HTTPS. It only goes live on the next deploy, so it must ride a deploy bundle
before the pipeline can read it. Until then the writer degrades safely (see below).

## Shape
```json
{
  "schema_version": "offer.v1",
  "site": "exploreorient.com",
  "generated_at": "2026-09-17T10:00:00Z",
  "offerings": [
    {
      "slug": "golden-road-to-samarkand",
      "title": "The Golden Road to Samarkand",
      "type": "tour",
      "summary": "8-day cultural journey across Uzbekistan's Silk Road cities.",
      "url": "https://exploreorient.com/tour/golden-road-to-samarkand/",
      "regions": ["central-asia"],
      "countries": ["uzbekistan"],
      "duration": "8 days",
      "route": ["Tashkent", "Khiva", "Bukhara", "Samarkand"]
    }
  ]
}
```

**Per offering** — the pipeline reads only these keys (`_OFFER_FIELDS` in
`agent2_writer_listener.py`), extra keys are ignored:
- `slug`, `title` (exact, as it should be printed), `type` (`tour` | `corridor` |
  `cruise` | `hotel` | `destination`), `summary`, `url` (absolute, the internal
  link the writer uses), `regions[]`, `countries[]`, `duration`, `route[]` /
  `stops[]`, `groupType`.
- **No price of any kind.** Deliberate: a `priceFrom` becomes a stated rate in
  prose and breaks the never-invent-figures rule. "Priced on request" is the only
  honest phrasing and it needs no field.
- **No counts in `summary`.** Stricter than "no price," and learned from
  cruise24.ir: a summary like "۷۸۲ کروز در ۹ مقصد" is true today and wrong next
  week, but once the writer prints it as a fact in an article it stays wrong
  forever. Keep any digit away from سفر/کروز/کشتی/مقصد/کلاس/حرکت (and their English
  equivalents). Build the export to assert on this and refuse to emit — cruise24's
  build caught 5 stale counts, boutimar cruise's caught more.
- **One offering per product page, never per sailing.** A partner API may hold
  thousands of sailings; a per-sailing feed is meaningless after the 60-entry cap
  and stale within a day. Emit the durable product pages (a cruise line, a
  destination, a ship) ordered by priority, so the first 60 are the ones that
  matter and every `url` is a page that exists.
- **Omit a product that does not exist — do not list a page that says "no."**
  cruise24.ir deliberately leaves `cruise-kish.html` out of its feed: that page
  exists to explain that no cruise departs Kish, Bandar Abbas or Qeshm, and
  listing it as an offering would invite the writer to promote a product that
  isn't real. The honest answer to "cruise from Iran" is that passengers fly to
  Dubai, Abu Dhabi or Doha — the feed carries only things a guest can actually buy.
- **Visa wording is derived, never typed.** Where a `summary` mentions visas, it
  must come from that product's computed per-port verdicts under the hard rules
  (Persian Gulf = easy visa, «بدونِ ویزا» نیست; AROYA only Türkiye+Egypt truly
  visa-free; any Greek/Schengen port needs a Schengen visa even sailing from
  Istanbul). The writer is told never to paraphrase these into «بدون ویزا» — that
  is the one paraphrase that puts a passenger at a counter without a visa.
- List everything the site sells that a guide article could reference; the
  pipeline caps at 60 entries.

## How the writer uses it
Injected into the draft prompt as `site_offerings`. The rules: name a relevant
offering by its exact `title` and link its `url`; never invent one; never state or
imply the house lacks a product. If the feed is missing or unreachable, the writer
is told the catalogue could not be loaded and still must not deny any product —
it writes "available on enquiry" instead.

## Adding a new site
Set `offer_feed:` in its sites.yml block, build the export to this contract, deploy
it. Nothing else in the pipeline changes.
