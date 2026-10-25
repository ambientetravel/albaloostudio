# Handoff: traffic for cruise24.me (route guides + Gulf-resident visa pages)

From session "24-hour project strategy", 25 Oct 2026, at Alireza's request.
Owner: session "Cruise24.me website tools".

## Why

cruise24.me has never had a real enquiry. The form is not the problem: it was
tested end to end on 25 Oct, server and real phone-size browser on index.html
and contact.html, via `.github/workflows/cruise24-form-check.yml`. The problem is
traffic, measured on 25 Oct:

| Measure | Value |
|---|---|
| Google, 90 days | 67 queries, 596 impressions, **10 clicks**, all on brand terms (cruise24 / cruise 24) |
| Sitemap URLs | 1,715 |
| Ever surfaced in Google | 269 (16%) |
| Never surfaced | 1,447 |
| leads.php, all time before tests | 0 |

## Item 2: route guide pages where Google already shows the site

Google already tests cruise24.me for these, at positions 40–70, with nothing
strong enough to rank on:

| Topic | Impressions (90 d) | Position |
|---|---:|---:|
| Scenic river cruise Amsterdam ↔ Zurich | 61 | ~40 |
| River cruise Prague ↔ Amsterdam (all word orders) | ~41 | ~42 |
| Rivers of West Africa / Cape Verde archipelago | ~45 | 47–70 |
| Scenic Budapest ↔ Bucharest / Amsterdam | ~10 | 44–68 |
| Small ships Venice → Dubrovnik | 3 | 71 |
| Buenos Aires ↔ Valparaíso | 3 | 58 |

Build about 10 route guides, one per route the feed actually sells:
- What the route is.
- Ships and lines on it, **from the live feed only**.
- Departures listed by linking to the existing sailing pages, so the 1,447
  unseen pages get inbound links.
- Visa line per itinerary, from `cruise24-ir/_visa.py` rules.
- Enquiry form.

Pick the 10 by impressions above, plus whatever the feed carries most. Re-run
`query-report.yml` (domain cruise24.me) for fresh numbers before choosing.

## Item 3: Gulf-resident visa pages (English)

cruise24.me's distinct angle is a Middle East resident asking practical
questions. Draft at least these three:
1. Which cruises can I take on a UAE (or GCC) residence visa? Answer from feed
   itineraries, grouped visa-free / easy visa / Schengen / national visa.
2. Do I need a Schengen visa for a Mediterranean cruise? Any Greek, Italian,
   Spanish or French port makes it Schengen, even sailing from Istanbul.
3. Cruises from Dubai, Doha and Jeddah: what sails, when, and the visa for each.

**Demand is unmeasured for English.** The "206 of 769 terms" Gulf figure is
Farsi demand for cruise24.ir and does not transfer. Check English volume with
Agent 7 / Keyword Planner before choosing more than these three.

## Rules (CLAUDE.md, non-negotiable)

- «خلیج فارس» / **Persian Gulf**, never "Arabian Gulf".
- Visa: only AROYA Türkiye+Egypt routes and Seychelles are visa-free; the
  Persian Gulf and Dubai are *easy visa*; any Greek, Italian, Spanish or French
  port makes the sailing Schengen.
- Never invent a rate, a departure date, an inclusion or a photo credit. Feed
  data only; if it isn't there, say so.
- No company name in outbound API headers.

## Publishing path

Every page goes through review, never straight live. It arrives as a draft
(Agent 2 / `static_bundle`, or a PR on this repo), appears in the Albaloo Ops
Review tab (https://albaloo-ops-core.base44.app), and Alireza presses Publish.
Then build the deploy bundle and write the cPanel upload steps in the same turn.
Add each new URL to `sitemap.xml`, and diff it against live after deploy.

## Done means

Drafts are in the Review queue with their numbers: pages, words, feed sailings
linked, visa lines. After publish: live 200s, sitemap diffed, IndexNow pinged.
Re-measure with `query-report.yml` and `index-coverage.yml` in about 3 weeks.

## Not done

- No pages written yet.
- No ad spend (Alireza's call).
- No English keyword research yet.
- 3 TEST enquiries ("PIPELINE TEST", pipeline-test@cruise24.me) are in
  leads.php on purpose. Agent 4 will see them. Ignore them.
