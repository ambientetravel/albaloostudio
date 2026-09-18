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
- **A summary may name the route your product actually operates.** The rule that
  an article must not assert a land border is "open" governs the writer's evergreen
  prose — nobody re-reads a blog guide when a crossing closes. It does NOT mean a
  feed must strip operational truth: an operated, request-based itinerary with a
  DMC behind it may state the crossing it runs (its summary can say "over the
  Sadakhlo crossing to Tbilisi"), because that describes what the product does, not
  what is permanently true of the border. Describe the product honestly; the
  pipeline keeps the evergreen framing on its side. Do not, though, dress an
  aspiration as an operation — name only routes you actually run.
- List everything the site sells that a guide article could reference; the
  pipeline caps at 60 entries **after relevance-ranking them against the brief**
  (keyword, title, must-include, url path), with a guard that keeps at least one of
  every product `type` you ship. So a 159-offering feed is fine — order it by your
  own priority and the pipeline floats the ones that matter to each article to the
  top; you do not need to pre-trim to 60.

## How the writer uses it
Injected into the draft prompt as `site_offerings`. The rules: name a relevant
offering by its exact `title` and link its `url`; never invent one; never state or
imply the house lacks a product. If the feed is missing or unreachable, the writer
is told the catalogue could not be loaded and still must not deny any product —
it writes "available on enquiry" instead.

## The feed is reviewed copy, not convenience text
Every factual claim in a `summary` — a duration, a transport mode, a route — is
ground truth to the writer, and it will amplify it into confident prose. On 18 Sep
a tour summary said three cities were "linked by high-speed rail"; one leg is
actually a road crossing, and the drafted article promised a customer "move between
them by rail in an afternoon". The writer did nothing wrong — it grounded itself in
the catalogue exactly as designed. **That is the failure mode grounding creates:
a wrong fact in the feed ships with more confidence than the model would have
invented on its own.** So treat the feed as customer-facing copy that has been
fact-checked, not as a scratch dump of your database. If a claim is only true for
part of a product, say which part in the summary or leave it out — do not round it
up. Sweep an existing feed for this the way you would proofread a landing page.

## A feed is a syndication surface, not just a read
The pipeline is not the only consumer. A public `/inventory/*.json` is fetched by
whatever reads it — the writer here, another brand's site, a partner. On 18 Sep an
exploreorient feed carried "our Tehran office" wording that breached the European-
brand separation rule, and seven of those records had already syndicated to Ambiente
Travel. A phrasing mistake in a feed does not stay in the feed; it travels to every
consumer with the feed's authority. Review a feed as a published surface, and when
you fix a claim, assume something downstream already cached the wrong one — tell the
consumers to re-pull. (This pipeline holds no cache: it fetches every feed live on
each run, so a corrected feed is picked up on the next cycle with nothing to purge.)

## Companion feed: `access.v1` for entry/visa facts
Products belong in `offer_feed`; a country's entry regime does not, so a visa or
entry guide had nothing real to ground on and hedged generically. A site may also
publish an **access.v1** feed (exploreorient: `/inventory/access.json`), set as
`access_feed:` in sites.yml. Per country: a verbatim, **nationality-qualified**
`regime`, `lead_time`, `status`, the house's own `handling` (the GBAO permit, a
Turkmenistan LOI), `url`, and `guarantee: false`, under a top-level `disclaimer`.
Same discipline as offer.v1, with its own build guards: **"visa-free" may never
stand unqualified**, no dated claims, no price-like data. The writer quotes a
`regime` whole (the qualifier is part of the fact), names the `handling`, and never
implies a regime is permanent — access data decays faster than a product catalogue
and nobody re-reads a published guide.

**A permit narrower than its country must state its boundary.** A country-level
record with a country-level `handling` note invites the writer to attach the permit
to any product in that country — and it will. Tajikistan's GBAO permit covers only
Gorno-Badakhshan (the Pamirs); a draft joined it to a Fann Mountains tour in the
west that never enters GBAO, telling travellers to get paperwork they don't need.
The quote was accurate; the join was wrong, and no field check catches a bad join.
So give any sub-national permit an optional **`scope`** naming exactly where it
applies and where it does not ("…the Fann Mountains and Penjikent lie outside GBAO
and need no permit"). The writer honours it: it will not pair a permit with a
product unless that product plainly falls inside the scope. This recurs — Saudi's
Royal Commission zones and Iran's regional permits are the same shape.

## Adding a new site
Set `offer_feed:` (and optionally `access_feed:`) in its sites.yml block, build the
export to this contract, deploy it. Nothing else in the pipeline changes.
