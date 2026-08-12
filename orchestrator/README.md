# Albaloo Orchestration Pipeline

Seven-agent SEO, GEO and revenue pipeline for the Mozaffari travel portfolio.
Architecture credit: **Albaloo Studio** — [albaloostudio.com](https://albaloostudio.com).
Owner: Alireza Mozaffari.

**[ARCHITECTURE.md](ARCHITECTURE.md) is the specification.** This file is how to run it.

```
GitHub Actions cron
      │
      ▼
Agent 1  SEO Scout      GSC (10 properties, 1 service account) → OpenAI → content.brief.v1
      │
      ▼
Agent 2  Writer         base44 Super Agent — contract in BASE44-AGENT2.md
                        Gemini → compliance gate → CMS → publishing.event.v1
      │
      ▼
Agent 3  Broadcaster    Claude → LinkedIn/Instagram/Telegram copy → campaign.log.v1
      │
      ▼
Agent 4  Sales Closer   inbox + chat → Claude qualify → escalate → draft reply
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill it in
```

Verify the whole thing without a single API key or network call:

```bash
python selfcheck.py
```

433 assertions across all seven agents — config, the compliance gate, gap
detection, payload assembly, JSON-Schema conformance, delivery retry, the
autopost gates, PII redaction, escalation rules, and every HTTP surface. Exit 0
means the pipeline is wired correctly.

## Agent 1 — SEO Scout

**First run? Do [SETUP-GSC.md](SETUP-GSC.md) first** — ~15 minutes, and nothing
in Agent 1 works until it is done.

Confirm the one service account can read all ten Search Console properties.
This is the step that catches "only one of the two Google accounts granted
access":

```bash
python agent1_seo_scout.py --list-properties
```

Then:

```bash
python agent1_seo_scout.py --dry-run                    # build briefs, deliver nothing
python agent1_seo_scout.py --domain boutimar.ir --limit 2
python agent1_seo_scout.py --no-openai                  # deterministic fallback, no LLM
python agent1_seo_scout.py                              # full run
```

Every run writes `runs/<run_id>/` — `manifest.json`, one file per emitted brief,
and `dlq/` for anything that failed delivery or the compliance gate. In CI it is
uploaded as a 90-day artifact.

Exit codes: `0` clean, `1` something was dead-lettered or a domain failed,
`2` the environment cannot support a run.

**A property nobody has granted yet does not fail the run.** It is a
configuration gap, not a failure: it is named at startup, logged at ERROR,
listed under `not_granted` in the manifest, and it persists until a human
clicks *Add user* in whichever Google account owns it. Failing on it would make
the daily cron permanently red, and a cron that is always red is a cron nobody
reads. The `--list-properties` step in CI is the designed place to notice the
gap; the scout's job is to scout what it can see.

## Agents 2, 3 and 4

Agent 2 runs on **base44** in production — [BASE44-AGENT2.md](BASE44-AGENT2.md)
is what that agent must implement. The FastAPI listener here is the reference
implementation and the thing `selfcheck.py` exercises.

```bash
uvicorn agent2_writer_listener:app --port 8080   # reference impl
```

```bash
uvicorn agent3_broadcaster:app --port 8081
```

```bash
uvicorn agent4_sales_closer:app --port 8082
```

| Agent | Route | |
|---|---|---|
| 2 | `POST /webhooks/content-brief` | signed brief in, `202` out, drafting in the background |
| 2 | `GET /jobs/{job_id}` | job status |
| 3 | `POST /webhooks/publishing` | signed publishing event in, `202` out |
| 3 | `GET /campaigns/{campaign_id}` | composed posts and their hold reasons |
| 4 | `POST /webhooks/campaign-log` | registers a campaign for lead attribution |
| 4 | `POST /leads/inbound` | a lead arrives; returns the qualification + draft reply |
| 4 | `GET /leads/{lead_id}` · `GET /escalations` | the human queue |
| all | `GET /healthz` | liveness |

**One worker each.** The idempotency and lead registries are process-local; a
second worker will draft the same article — or qualify the same lead — twice.
Move them to Redis before scaling out.

### Nothing posts and nothing sends without a human

* **Agent 3** composes copy and *queues* it. Live posting needs two independent
  yeses: `ALLOW_AUTOPOST=1` in the environment **and** `autopost: true` on that
  channel in `sites.yml`. Either one missing and the post is held — on the
  `zernio` backend as a dashboard draft, on the default `file` backend as JSON
  on disk that never leaves the machine.
* **Agent 4** drafts replies and never sends one. It quotes only figures present
  in the campaign's live rate feed, always with the `price_asof` timestamp, and
  redacts card numbers, CVVs, passport numbers and IBANs on arrival — before the
  model sees them and before anything is stored.

## The rules this pipeline will not break

Enforced twice — injected into every prompt, then re-checked against the
generated output in [`compliance.py`](compliance.py). A violation blocks
publication and dead-letters the payload; it does not warn and continue.

* **«خلیج فارس» / Persian Gulf.** Never "Arabian Gulf". ("Arabian Sea" is a
  different body of water and is left alone.)
* **Visa accuracy.** Only AROYA's Türkiye+Egypt routes and Seychelles are
  visa-free. Persian Gulf and Dubai are *easy visa*. One Greek, Italian, Spanish
  or French port makes the whole itinerary Schengen — even sailing from Istanbul.
* **Never invent** a rate, a departure date, an inclusion or a photo credit. A
  price with no `price_asof` is not a price.
* **The partner embed stays brand-neutral** — no «بوتیمار», no boutimar.ir links.
* No company name in anything resembling an outbound API header; the CruiseHost
  contract belongs to Ambiente Tours.

### A claim in its clause, not a term anywhere

That distinction is the whole design, and getting it wrong is expensive in both
directions. The first live run (8 Aug 2026) dead-lettered 3 of 7 briefs, and
every one was blocked for stating the visa rule **correctly**: "Türkiye and
Egypt: no visa needed" is true, "Dubai: no visa needed" is the lie, and a
context-blind match cannot tell them apart. The more precisely the model stated
the rule, the more certainly its own brief was thrown away. So:

* **Prohibition fields (`must_avoid`) are never scanned.** Every string in them
  is a forbidden term by definition; scanning them punishes a correct brief for
  correctly forbidding the thing. `compliance.assertive_surface()` strips them
  for every agent.
* **List items are joined with newlines**, so one item's claim cannot borrow its
  neighbour's destination — or its negator.
* **A visa-free claim is read against the destination in its own clause.** A
  forbidden one blocks; a sanctioned exception passes; an easy-visa label means
  the copy is classifying rather than claiming; no destination at all warns.
* **A question is not a claim.** "Is Dubai visa-free?" is the FAQ shape the GEO
  work exists to produce — it warns, and the answer beside it is judged on its
  own.

`persian_gulf_only` gets none of these escapes. It bans a *term*, and "Arabian
Gulf" is wrong in any framing — question, negation or quotation.

## What is not wired yet

* **CMS adapters** stage drafts and return `status: "draft"`. An adapter never
  reports a URL it did not create, so nothing publishes until the real
  WordPress / Astro / base44 implementations are dropped into `push_to_cms`.
  `static_bundle` (the three `.ir` sites) writes a deploy bundle to `bundles/`.
* **No brand social account is connected.** The one account on the scheduler is
  a personal hobby page and is deliberately not wired to any brand — see
  [SETUP-SOCIAL.md](SETUP-SOCIAL.md). Every `account_ref` is `null`, so Agent 3
  composes copy and holds it in the file queue. **One Telegram channel makes the
  pipeline deliver end to end**; it is the only channel with no blockers.
* **Instagram will not accept a text-only post.** Agent 2 emits
  `hero_image: null` whenever there is no credited, licensed image, so Instagram
  posts are held with `status: blocked` rather than failing at publish time.
  Sourcing imagery is the open piece of work here.
* **The audit score is sample-independent but not sample-free.** Site-scope
  findings count once; page-scope findings count as the fraction of sampled
  pages they affect, so a template defect costs the same at 3 pages or 30.
  `audit_sample_pages` is pinned at 10 in `sites.yml` and the weekly cron never
  overrides it — changing it restarts the trend line.
* **SERP data** is inferred from Search Console only; no paid SERP API.
* **Autopost is off** on every channel in `sites.yml`.

## Layout

| | |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | the spec, incl. all three JSON handoff schemas |
| [`sites.yml`](sites.yml) | the 10 properties — the only place a domain is declared |
| [`config.py`](config.py) | env, model IDs, envelope + HMAC signing |
| [`compliance.py`](compliance.py) | the gate |
| [`agent1_seo_scout.py`](agent1_seo_scout.py) | GSC → OpenAI → webhook |
| [`agent2_writer_batch.py`](agent2_writer_batch.py) | **Agent 2 in production** — reads Agent 1's briefs, drafts, gates, publishes |
| [`agent2_writer_listener.py`](agent2_writer_listener.py) | the FastAPI variant — reference impl, kept for the HTTP surface tests |
| [`BASE44-AGENT2.md`](BASE44-AGENT2.md) | what the base44 Super Agent must implement |
| [`agent3_broadcaster.py`](agent3_broadcaster.py) | FastAPI → Claude → scheduler → webhook |
| [`agent4_sales_closer.py`](agent4_sales_closer.py) | FastAPI → Claude → qualify → escalate |
| [`scheduler.py`](scheduler.py) | file / zernio / webhook backends, media pre-flight |
| [`SETUP-GSC.md`](SETUP-GSC.md) | the 15-minute Search Console grant — the one blocking step |
| [`SETUP-SOCIAL.md`](SETUP-SOCIAL.md) | what to connect where, and which entity should own it |
| [`SETUP-DEPLOY.md`](SETUP-DEPLOY.md) | scoped FTP + CI deploys, so no one holds the panel password |
| [`SETUP-DEPLOY-ALBALOO.md`](SETUP-DEPLOY-ALBALOO.md) | albaloostudio.com deploy — publishes an allowlist, never a repo mirror |
| [`SETUP-PLUG-THE-ENDS-IN.md`](SETUP-PLUG-THE-ENDS-IN.md) | **the three remaining edges** — WordPress, Telegram via Make, a lead source |
| [`agent5_site_auditor.py`](agent5_site_auditor.py) | technical + GEO + local crawl, no credentials needed |
| [`agent6_analyst.py`](agent6_analyst.py) | audit + demand → strategy, calendar, paste-ready JSON-LD |
| [`agent7_keyword_scout.py`](agent7_keyword_scout.py) | per-country visibility + market alignment; Keyword Planner where it works |
| [`SETUP-KEYWORD-PLANNER.md`](SETUP-KEYWORD-PLANNER.md) | why the Iranian sites cannot use it, and what replaces it |
| [`selfcheck.py`](selfcheck.py) | 433 assertions, no network |
| [`schemas/`](schemas) | JSON Schema for the three payloads |
| `../.github/workflows/agent1-seo-scout.yml` | weekly scout, Sundays 04:15 UTC |
| `../.github/workflows/agent5-site-audit.yml` | weekly audit + strategy, Mondays 05:00 UTC |
