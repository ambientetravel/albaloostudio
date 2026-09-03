# Site-inventory seed for the Gemini bridge

**Why this exists.** Gemini writes bridge manifests without being able to see the
live sites. Across three manifests it proposed a fabricated date (v1), schema that
was already live (v2), and content that was already built (v3) — every time because
it was blind to what the properties already have. This seed is the fix: a live,
read-only map of what exists, handed to Gemini *before* it drafts a manifest.

## Files
- `site-inventory-seed.json` — the seed. Per property: platform, total indexed
  URLs, `section_counts`, `all_pages` (the complete path list for deduping), and
  `key_pages_coverage` (title / meta / H1 / schema @types for landmark pages).
- `crawl.sh` — fetches each property's sitemap(s) → per-domain `_urls.txt`.
- `build_seed.py` — reads the crawl + live-fetches landmark pages → the seed JSON.

## Refresh
```
bash crawl.sh && python3 build_seed.py   # writes site-inventory-seed.json
```
Read-only: it only GETs sitemaps and pages. Re-run before a new Gemini strategy
cycle, or whenever a property ships new sections.

## How Gemini uses it
Paste the JSON (or its bridge connector reads it) as context, with the prompt in
`../README.md`. The rule: before proposing a `content_brief` or `schema_injection`,
check `all_pages` and `key_pages_coverage`. If the page exists and covers the topic,
propose extractable-gap ENRICHMENT, not a new page — and never propose building a
page that is already listed.

## What the first seed already exposed (the kind of thing it prevents)
- **boutimar.com/travel-agents/** already exists and is titled *"B2B Iran Tour
  Operator — Partner with Boutimar DMC & MICE"* — exactly what v3's DMC/B2B task
  proposed to create.
- **boutimar.com/mice/** carries `Service` + `TravelAgency` schema and a full MICE
  offer — v3's MICE task was redundant.
- **cruise24.ir** pages carry **no schema at all** (`schema_types: []`) — so the
  FAQPage / structured-entity gap there is genuinely real, not imagined.
