# bridge/ — Gemini's strategy manifests come in here

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

## What the bridge is, and what it is not

Gemini (external strategist) writes JSON task manifests; they land here via its
GitHub connector; `tools/bridge_ingest.py` validates and routes them; a human
reviews before any agent runs. That is the whole bridge.

It is deliberately NOT a live API between two models, and NOT direct execution
of externally-authored manifests. The same reasoning that retired the base44
webhook applies: producing INTO git is reviewable, replayable, and needs no
credential to time out. A manifest is a PROPOSAL. It is validated, compliance-
prescreened, and read by a person or the normal agent run — never auto-applied,
because a directive that carries a wrong visa claim or an invented rate must be
caught before it becomes a published page, not after.

## Where Gemini adds value, and where it would duplicate work

Feed the bridge what the pipeline CANNOT see for itself:

- **Live-retrieval GEO.** Agent 9 measures base-model recall (browsing off).
  It cannot see Perplexity, AI Overviews, or ChatGPT-with-search. Gemini can.
  A `geo_optimization` task with `provenance.live_retrieval: true` is the
  bridge's highest-value input — it is the one surface the fleet is blind to.
- **Exact schema specs.** `schema_injection` tasks carrying a ready JSON-LD
  block (Event, TouristTrip, Organization, LocalBusiness) that Agent 2 folds
  into a brief's `schema_org`. The audit already flags "no JSON-LD in server
  HTML" as a P1 — a filled spec closes it.
- **Strategic direction** the GSC data does not state: the 2027 B2B pivot,
  MICE positioning, entity maps.

Do NOT route through the bridge what an agent already does better:

- Search Console ingestion. Agent 1 read 5,095 GSC rows last run and scores
  gaps itself. A manifest that just restates a GSC number (`gsc_backed: true`,
  no live-retrieval) is flagged as redundant — the scout will find it anyway.
- Competitor content coverage — Agent 8 already crawls it.
- Site audits — Agent 5.

## The contract

One file per handoff: `manifest-<YYYY-MM-DD>.json`, validating against
`task-manifest.schema.json`. Every task MUST carry `provenance.sources`; a task
with no source is a suggestion, not a directive, and `bridge_ingest.py` rejects
it — the same rule the base44 inbox keeps.

`payload` shapes by `action_type`:

- `content_brief` → `{primary_keyword, target_url_path, angle, must_cover[]}`
  (Agent 1/2 own the final brief; this seeds it.)
- `schema_injection` → `{schema_type, jsonld}` — a complete, valid JSON-LD object.
- `geo_optimization` → `{prompt, observed_answer, brands_named[], gap}` — what a
  live AI answer said and where we were absent.
- `competitor_watch` → `{competitor, url, claim}` — quoted, never paraphrased.
- `audit_fix` → `{issue, fix}` mapping to an Agent 5 finding.

## Non-negotiables that apply to anything arriving here

Same hard rules as everything else in this repo, enforced by the compliance
gate on any output an agent produces from a manifest:

- «خلیج فارس», never «خلیج عربی».
- Visa accuracy: only AROYA Türkiye+Egypt and Seychelles are truly visa-free;
  Persian Gulf and Dubai are EASY VISA; any Greek/Italian/Spanish/French port is
  Schengen. `bridge_ingest.py` prescreens manifests for banned terms.
- Never an invented rate, date, inclusion, or photo credit — even if a manifest
  supplies one. A figure without a named source in `provenance` does not ship.
- The CruiseHost contract belongs to Ambiente Tours; the embed widget stays
  brand-neutral.
