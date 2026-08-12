# Albaloo Orchestration Pipeline — Architecture

**A seven-agent SEO, GEO and revenue pipeline for the Mozaffari travel portfolio.**

| | |
|---|---|
| **Architect & Owner** | Alireza Mozaffari |
| **Architecture credit** | **Albaloo Studio** — [albaloostudio.com](https://albaloostudio.com) |
| **Document version** | 2.0.0 |
| **Payload schema version** | `1.0` |
| **Status** | All seven agents implemented and running in GitHub Actions. Agents 1 → 2 → 3 chain nightly on one trigger; 5+6 and 7 run weekly; 4 is dispatch-only until a lead source exists |

> This infrastructure — the orchestration model, the message envelope, the
> compliance gate and the agent contracts described below — is authored under
> and credited to **Albaloo Studio**. Every generated artefact (page footer,
> campaign log row, run manifest, JSON envelope) carries the
> `architecture_credit: "Albaloo Studio"` field. See
> [§9 Credit & attribution](#9-credit--attribution).

---

## 1. The portfolio

Nine brands, ten Search Console properties (boutimar runs a `.com` and a
`.ir` property against one brand — they are separate sites with separate
languages and separate sitemaps, so they are separate rows everywhere below).

| # | Domain | Brand | Locale | Market | CMS / stack | Property type |
|---|--------|-------|--------|--------|-------------|---------------|
| 1 | `boutimar.com` | Boutimar | `en` | International B2C/B2B | WordPress + Elementor + Woo | `sc-domain:boutimar.com` |
| 2 | `boutimar.ir` | Boutimar (Farsi) | `fa-IR` | Iran domestic | Static build + PHP API (Netafraz) | `sc-domain:boutimar.ir` |
| 3 | `exploreorient.com` | Explore Orient | `en` | Inbound Orient portal | Astro 5 (static) | `sc-domain:exploreorient.com` |
| 4 | `ambientetravel.com` | Ambiente Travel | `en` / `de` | DMC / MICE | base44 | `sc-domain:ambientetravel.com` |
| 5 | `cruisebaz.com` | CruiseBaz | `fa-IR` | Iran cruise D2C | base44 | `sc-domain:cruisebaz.com` |
| 6 | `cruise24.ir` | Cruise24 | `fa-IR` | Iran cruise D2C | Static (hand-built) | `sc-domain:cruise24.ir` |
| 7 | `cruiseshop.ir` | CruiseShop | `fa-IR` | Iran cruise retail | Static (hand-built) | `sc-domain:cruiseshop.ir` |
| 8 | `dmciran.ir` | DMC Iran | `fa-IR` / `en` | Inbound DMC | Static (hand-built) | `sc-domain:dmciran.ir` |

The authoritative machine-readable copy of this table lives in
[`sites.yml`](sites.yml). Agent 1 reads it at boot; nothing else in the pipeline
hardcodes a domain.

---

## 2. System map

Five workflows. Three of them chain off one nightly trigger; two run weekly;
one waits for input that does not exist yet.

```
04:15 UTC daily
   │
   ▼
┌─ agent1-seo-scout.yml ─────────────────────────────────────────────┐
│ AGENT 1 — SEO SCOUT                                                │
│   Search Console (10 properties, 1 service account)                │
│   × sitemap + live crawl  =  demand − supply  =  gap set           │
│   → Claude ranks and clusters → content.brief.v1                   │
│   artifact: seo-scout-run                                          │
└────────────────────────────┬───────────────────────────────────────┘
                             │ workflow_run (success only)
                             ▼
┌─ agent2-writer.yml ────────────────────────────────────────────────┐
│ AGENT 2 — WRITER                                                   │
│   reads the briefs artifact — no webhook, no signature             │
│   → Gemini drafts → compliance gate on the OUTPUT                  │
│   → CMS adapter → publishing.event.v1                              │
│   artifact: agent2-written                                         │
└────────────────────────────┬───────────────────────────────────────┘
                             │ workflow_run (success only)
                             ▼
┌─ agent3-broadcaster.yml ───────────────────────────────────────────┐
│ AGENT 3 — BROADCASTER                                              │
│   SKIPS any event whose live_url is null — you cannot broadcast    │
│   a page that does not exist                                       │
│   → Claude writes per-channel copy → gate → scheduler → queue      │
│   → campaign.log.v1        artifact: agent3-broadcast              │
└────────────────────────────┬───────────────────────────────────────┘
                             │ (manual, when leads exist)
                             ▼
┌─ agent4-sales-closer.yml ──────────────────────────────────────────┐
│ AGENT 4 — SALES CLOSER          dispatch-only, no cron             │
│   redact → attribute to a campaign → Claude qualifies              │
│   → gate the drafted reply → escalate or queue for a human         │
│   NO delivery path exists in the code. 0 sent, by construction.    │
└────────────────────────────────────────────────────────────────────┘

Mondays 05:00 UTC                    Mondays 05:30 UTC
┌─ agent5-site-audit.yml ──────┐     ┌─ agent7-keyword-geo.yml ─────┐
│ AGENT 5 — AUDITOR            │     │ AGENT 7 — KEYWORD & GEO      │
│   crawls every active site,  │     │   per-country visibility     │
│   no credentials needed      │     │   from the GSC country       │
│ AGENT 6 — ANALYST            │     │   dimension Agent 1 already  │
│   audit + demand → strategy, │     │   fetches; market-alignment  │
│   calendar, paste-ready      │     │   check; Keyword Planner     │
│   JSON-LD                    │     │   where Ads actually operates│
└──────────────────────────────┘     └──────────────────────────────┘

on push to main (site files only)
┌─ deploy-albaloostudio.com ───────────────────────────────────────────┐
│   stages an ALLOWLIST of 13 files, never a repo mirror — the repo    │
│   root is both the docroot and the whole workspace                   │
└──────────────────────────────────────────────────────────────────────┘
```

Every stage degrades rather than failing: a missing model key runs the
structural path, an ungranted property is skipped and named, an unimplemented
adapter stages a draft. The point is that a red run means something is actually
wrong.

### 2.1 Why the internal hops are NOT webhooks any more

**Superseded 11 Aug 2026.** This section used to argue that signed HTTP POST was
the lowest common denominator because Agents 2 and 3 would run on platforms
(base44, Make.com) exposing an HTTP endpoint and nothing else.

base44 turned out not to be able to run Agent 2 at all:

* Six of the ten sites need **git or filesystem writes** it does not have —
  `astro_pr` opens a pull request; `static_bundle` and `boutimar_ir_static`
  write files. Only the two base44-hosted sites were native to it.
* The contract requires verifying an HMAC over the **raw request bytes** before
  parsing. Hosted builders hand you a parsed object; re-serialising changes key
  order and separators and the MAC never matches.
* It must answer `202` in about two seconds and then draft for 30–90 s. That is
  background work, not a request handler.

So Agents 2 and 3 moved into GitHub Actions alongside Agent 1, and the webhook
between them **disappeared rather than being reimplemented**. Each stage reads
the previous stage's uploaded artifact directly, triggered by `workflow_run`.
No signature to verify, no endpoint to keep alive, and no `AGENT2_WEBHOOK_URL`
— the secret whose absence killed the nightly cron on 9 Aug 2026, because a
scheduled run supplies no inputs and so demanded a delivery endpoint that did
not exist.

Fewer moving parts, not more. The envelope stayed exactly as it was: every
payload still carries `message_id`, `idempotency_key`, `attempt` and a
dead-letter destination, so the transport can become a queue later by replacing
one function.

**Signed HTTP POST is still the design for anything genuinely external** —
Agent 3 → the scheduler (Make.com), and Agent 4's lead pull. §3.4 governs those.

### 2.2 Delivery semantics

* **At-least-once.** Agent 1 retries 5xx and 429 with exponential backoff
  (1s, 2s, 4s, 8s, 16s + jitter). 4xx other than 429 is terminal.
* **Consumers must be idempotent.** `envelope.idempotency_key` is a SHA-256 of
  `{domain}|{primary_keyword}|{target_url_path}` — stable across reruns, so a
  duplicate brief for the same gap is a no-op, not a second article.
* **Dead letters.** After the final retry the payload is written to
  `runs/<run_id>/dlq/<message_id>.json` in the Actions artifact and the run is
  marked failed. Nothing is silently dropped.

---

## 3. Authentication & identity

### 3.1 The unified Google Search Console strategy

The historical data is split across **several** Google accounts — at least
`alimozzarella@`, `contactmozaffari@`, and brand-specific ones such as
`ambienteturizm@` and `cruisebazonline@`. (This document originally said "two";
a live check on 6 Aug 2026 found those two own only three of the eight
properties.) **A service account cannot inherit that access.** There is no API call that merges two consumer
Google accounts. What a service account *can* do is be granted access on each
property individually, which produces a single credential that reads all eight.

**The strategy is therefore: one service account, granted once per owning account.**

```
                       ┌─────────────────────────────────────┐
   alimozzarella@   ───┤                                     │
   (owner of a subset)  │   Search Console → Settings →      │
                        │   Users and permissions →          │
                        │   Add user:                        │
   contactmozaffari@ ──┤   albaloo-orchestrator@<project>    │
   (owner of the rest)  │   .iam.gserviceaccount.com         │
                        │   Permission: **Restricted**        │
                        └──────────────┬──────────────────────┘
                                       ▼
                       one JSON key → GH secret GOOGLE_SERVICE_ACCOUNT_JSON
                                       ▼
                       sites().list() returns all 8 properties
```

Setup, once:

1. GCP project `albaloo-orchestrator`. Enable **Google Search Console API**
   (`searchconsole.googleapis.com`).
2. Create service account `albaloo-orchestrator`. Create a JSON key. This key
   is the *only* Google credential the pipeline ever holds.
3. Sign in to Search Console as **alimozzarella@gmail.com**. For each property
   that account owns: Settings → Users and permissions → Add user → the service
   account e-mail → **Restricted** (read-only is all Agent 1 needs).
4. Repeat signed in as **contactmozaffari@gmail.com** for the remaining
   properties.
5. Verify: `python agent1_seo_scout.py --list-properties` must print eight rows.
   If it prints fewer, step 3/4 was missed on the difference — the script names
   the missing ones explicitly.

Notes that matter in practice:

* **Restricted, not Full.** Agent 1 only calls `sites.list` and
  `searchanalytics.query`. Full permission would additionally allow sitemap
  submission and URL removal — needless blast radius for a cron job.
* **Domain properties preferred** (`sc-domain:…`) so `www`, apex and both
  schemes roll up into one row. Boutimar.ir's `www` → apex 301 already assumes
  this.
* **Google Workspace domain-wide delegation is not used and not needed.** It
  only applies to Workspace tenants; both accounts here are consumer Gmail.
  Delegation would be the wrong tool and would require Workspace admin.
* **Data floor.** Search Console data lags ~2 days and omits low-volume queries.
  Agent 1 queries `today-3d` back, never `today`.

### 3.2 LLM providers — who does what and why

| Provider | Library | Used by | Job | Rationale |
|----------|---------|---------|-----|-----------|
| **OpenAI** | `openai` | Agent 1 | Gap analysis, intent classification, priority scoring, outline | Strict JSON-schema structured output; the step is analytical, not stylistic |
| **Google Gemini** | `google-generativeai` | Agent 2 | Long-form drafting, fa-IR and en | Large context — the whole brief plus existing site pages plus brand-voice corpus fit in one call |
| **Anthropic Claude** | `anthropic` | Agents 3 and 4 | Channel copy; lead qualification | Best register control for B2B vs D2C tone shifts, and for a reply a human will actually send |

Model IDs are **configuration, not code** — `OPENAI_MODEL`, `GEMINI_MODEL`,
`ANTHROPIC_MODEL` env vars, with defaults in `config.py`. Never pin a model in a
prompt string.

### 3.3 Secret inventory

Everything runs in one repository's Actions environment, so "where it lives" is
the same answer for all of them. What differs is what happens when one is
missing — and the answer is never "the run fails silently".

| Secret | Consumed by | Absent ⇒ |
|--------|-------------|----------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Agents 1, 7 | exit 2 — nothing can be scouted |
| `ANTHROPIC_API_KEY` | Agents 1, 3, 4 | Agent 1 falls back to deterministic ranking; 3 and 4 run `--no-llm` |
| `GEMINI_API_KEY` | Agent 2 | runs `--no-llm`: parsing, gate, adapters and event assembly still exercised |
| `WEBHOOK_SIGNING_SECRET` | Agent 3 → scheduler, Agent 4 lead pull | the lead pull warns loudly and goes unsigned |
| `SCHEDULER_BASE_URL` · `SCHEDULER_API_KEY` | Agent 3 | backend stays `file`; posts queue to disk |
| `ASTRO_REPO` · `ASTRO_GITHUB_TOKEN` | Agent 2 | `astro_pr` writes to `bundles/` instead of opening a PR |
| `WORDPRESS_USER` · `WORDPRESS_APP_PASSWORD` | Agent 2 | unused — no property runs WordPress since 11 Aug 2026 |
| `ALBALOO_FTP_*` | deploy workflow | albaloostudio.com does not deploy |
| `OPENAI_API_KEY` | Agent 1 (only if `GAP_ANALYSIS_PROVIDER=openai`) | irrelevant on the Anthropic default |

**Withdrawn:** `AGENT2_WEBHOOK_URL` and `AGENT3_WEBHOOK_URL`. Those hops are
artifact reads now (§2.1).

No secret is ever written into a payload, a log line or a run artifact.
`config.redact()` scrubs anything matching `(?i)(key|token|secret|password)`
before logging, and it is applied to exception text too — a 401 body can carry
the credential that caused it.

### 3.4 Webhook signing

Every POST between agents carries:

```
X-Albaloo-Signature:  sha256=<hex hmac>
X-Albaloo-Timestamp:  1754467200          # unix seconds
X-Albaloo-Message-Id: 0f6c…                # = envelope.message_id
Content-Type:         application/json
User-Agent:           albaloo-orchestrator/1.0 (+https://albaloostudio.com)
```

`hmac_sha256(secret, f"{timestamp}.{raw_body}")`, compared with
`hmac.compare_digest`. Requests older than **300 seconds** are rejected `401`
regardless of a valid signature — that is the replay window. The signature is
computed over the **raw bytes**, so the receiver must not re-serialise before
verifying (FastAPI: `await request.body()`, then parse).

---

## 4. JSON handoff schemas

All three payloads share one envelope. JSON Schema files:
[`schemas/content.brief.v1.json`](schemas/content.brief.v1.json),
[`schemas/publishing.event.v1.json`](schemas/publishing.event.v1.json),
[`schemas/campaign.log.v1.json`](schemas/campaign.log.v1.json).

### 4.0 The shared envelope

```jsonc
{
  "schema_version": "1.0",
  "envelope": {
    "message_id":        "01J8QK7X2N4P0000000000",   // ULID, unique per delivery
    "correlation_id":    "run_20260806T0415Z_a91c",  // constant for a whole run — trace 1→4
    "causation_id":      "01J8QK7X2N4P…",            // message_id of the message that caused this one (null at Agent 1)
    "idempotency_key":   "sha256:9f2c…",             // stable across reruns of the same gap
    "message_type":      "content.brief",            // content.brief | publishing.event | campaign.log
    "emitted_at":        "2026-08-06T04:17:22Z",     // RFC3339 UTC, always Z
    "emitted_by":        "agent1.seo_scout",
    "target":            "agent2.writer",
    "attempt":           1,
    "environment":       "production",               // production | staging | dry-run
    "architecture_credit": "Albaloo Studio",
    "owner":             "Alireza Mozaffari"
  },
  "...": "message-type-specific body"
}
```

Field rules that apply everywhere:

* Timestamps: RFC3339, UTC, `Z` suffix. Never local time, never Jalali in a
  payload — Jalali is a **presentation** concern and belongs in rendered copy
  only.
* Money: `{"amount": 1490.00, "currency": "EUR"}`. Never a bare number, never a
  formatted string. `null` is legal and means *unknown*; `0` never means unknown.
* Language: BCP-47 (`fa-IR`, `en`, `de`). Not `farsi`, not `persian`.
* Unknown fields MUST be preserved by consumers on forward (Agent 2 copies
  unrecognised keys into `publishing.event.source_brief.passthrough`) so a
  producer can add a field without a lockstep deploy.
* `schema_version` is major.minor. A consumer accepts the same major.

---

### 4.1 `content.brief.v1` — Agent 1 ➜ Agent 2

**Transport:** written to `runs/<run_id>/briefs/` and uploaded as the `seo-scout-run` artifact; Agent 2 reads it on `workflow_run`. The FastAPI reference implementation still accepts `POST /webhooks/content-brief` → `202`.
**Response body:** `{"accepted": true, "message_id": "…", "job_id": "…"}`

```jsonc
{
  "schema_version": "1.0",
  "envelope": { /* §4.0, message_type: "content.brief", target: "agent2.writer" */ },

  "site": {
    "domain":        "boutimar.ir",
    "property_uri":  "sc-domain:boutimar.ir",
    "brand":         "Boutimar",
    "locale":        "fa-IR",
    "market":        "IR",
    "base_url":      "https://boutimar.ir",
    "cms": {
      "type":        "static",              // wordpress | astro | base44 | static
      "adapter":     "boutimar_ir_static",  // which Agent 2 CMS adapter to use
      "content_root":"/pages/",
      "publish_mode":"draft"                // draft | scheduled | publish  (see §8 open question O-3)
    }
  },

  "opportunity": {
    "gap_type":        "missing_page",
    // missing_page | thin_content | cannibalisation | stale_content |
    // serp_feature_loss | competitor_outranking | untranslated
    "primary_keyword": "تور کشتی کروز خلیج فارس",
    "keyword_locale":  "fa-IR",
    "secondary_keywords": ["کروز خلیج فارس قیمت", "کشتی کروز دبی به قطر"],
    "search_intent":   "commercial",        // informational | commercial | transactional | navigational
    "gsc": {
      "date_range":    { "start": "2026-05-09", "end": "2026-08-03" },
      "impressions":   4820,
      "clicks":        61,
      "ctr":           0.0127,
      "avg_position":  18.4,
      "best_position": 11.2,
      "trend_28d":     "rising",            // rising | flat | falling
      "top_country":   "irn",               // GSC uses ISO-3166-1 alpha-3, lowercase
      "current_url":   null,                // URL currently ranking, null if none
      "device_split":  { "mobile": 0.78, "desktop": 0.20, "tablet": 0.02 }
    },
    "serp": {
      "checked_at":    "2026-08-06T04:16:02Z",
      "competitors":   [
        { "rank": 1, "domain": "cruisebaz.com", "title": "…", "word_count": 1840 },
        { "rank": 2, "domain": "example.ir",    "title": "…", "word_count": 1210 }
      ],
      "features":      ["people_also_ask", "image_pack"],
      "source":        "gsc_inference"      // gsc_inference | serp_api | manual
    },
    "priority_score":  87,                  // 0–100, produced by the OpenAI step
    "priority_inputs": { "volume": 0.9, "position_proximity": 0.8, "commercial_value": 0.95, "effort": 0.4 },
    "rationale":       "4.8k impressions at position 18 with no page covering the query on this domain; …"
  },

  "brief": {
    "working_title":     "کروز خلیج فارس: راهنمای کامل ۱۴۰۵",
    "content_type":      "guide",           // guide | landing | itinerary | comparison | faq | news | translation
    "target_url_path":   "/cruise/persian-gulf-guide",
    "language":          "fa-IR",
    "word_count_target": { "min": 1400, "max": 1900 },
    "reading_level":     "general",
    "tone":              "poetic-luxury",   // brand-voice profile key, see §7.4
    "outline": [
      { "h": 2, "heading": "چرا خلیج فارس؟", "must_cover": ["فاصله پرواز از تهران", "فصل سفر"] },
      { "h": 2, "heading": "مسیرها و بنادر",  "must_cover": ["دبی", "ابوظبی", "دوحه"] },
      { "h": 2, "heading": "ویزا و مدارک",    "must_cover": ["ویزای آسان — نه بدون ویزا"] }
    ],
    "must_include":  ["خلیج فارس", "کابین", "ترانسفر فرودگاهی"],
    "must_avoid":    ["خلیج عربی", "بدون ویزا", "تضمین قیمت"],
    "internal_links": [
      { "url": "/cruise/aroya", "anchor": "کروز آرویا", "reason": "sibling product" }
    ],
    "external_sources": [
      { "url": "https://…", "use": "port fee reference", "cite": true }
    ],
    "schema_org":    ["Article", "FAQPage", "BreadcrumbList"],
    "meta": {
      "title":       "کروز خلیج فارس ۱۴۰۵ | بوتیمار",
      "description": "…",
      "og_image_hint": "cruise ship at dusk, Persian Gulf"
    },
    "media": {
      "hero_required": true,
      "allowed_sources": ["licensed_library", "supplier_press_kit"],
      "credit_required": true               // an image with no known credit is NOT used (§7.3)
    },
    "data_dependencies": [
      { "field": "price_from", "source": "https://boutimar.ir/api/cruises.php", "required": false }
    ]
  },

  "compliance": {
    "profile":              "boutimar_v1",
    "persian_gulf_only":    true,   // «خلیج فارس» / Persian Gulf. "Arabian Gulf" is a hard fail.
    "visa_accuracy":        true,   // only AROYA Türkiye+Egypt and Seychelles are visa-free
    "no_invented_facts":    true,   // no rate, date, inclusion or photo credit that is not in data_dependencies
    "brand_neutral_embed":  false,  // true only for partner-widget content
    "sanctions_check":      true,   // no US/OFAC-exposed third party wired in
    "blocking":             true    // a violation blocks publication; it does not warn
  },

  "routing": {
    "callback_url": "https://…/agent3/publishing",  // where Agent 2 posts next
    "priority":     "high",                          // high | normal | low
    "deadline":     "2026-08-09T00:00:00Z",
    "dry_run":      false
  }
}
```

---

### 4.2 `publishing.event.v1` — Agent 2 ➜ Agent 3

**Transport:** written to `written/events/` and uploaded as the `agent2-written` artifact; Agent 3 reads it on `workflow_run`. The reference listener still accepts `POST /webhooks/publishing` → `202`, and `routing.callback_url` still routes there when one is supplied.

```jsonc
{
  "schema_version": "1.0",
  "envelope": { /* §4.0, message_type: "publishing.event", causation_id = brief's message_id */ },

  "source_brief": {
    "message_id":      "01J8QK7X2N4P0000000000",
    "correlation_id":  "run_20260806T0415Z_a91c",
    "primary_keyword": "تور کشتی کروز خلیج فارس",
    "gap_type":        "missing_page",
    "passthrough":     { }                  // unrecognised keys from the brief, preserved verbatim
  },

  "publication": {
    "status":        "published",           // published | scheduled | draft | failed
    "live_url":      "https://boutimar.ir/cruise/persian-gulf-guide",
    "canonical_url": "https://boutimar.ir/cruise/persian-gulf-guide",
    "cms":           { "type": "static", "adapter": "boutimar_ir_static", "record_id": "pg-guide-1405" },
    "published_at":  "2026-08-06T05:02:11Z",
    "scheduled_for": null,
    "language":      "fa-IR",
    "word_count":    1663,
    "reading_time_min": 7,
    "hero_image": {
      "url":     "https://boutimar.ir/img/gulf-hero.webp",
      "alt":     "کشتی کروز در خلیج فارس هنگام غروب",
      "credit":  "MSC Cruises press kit",
      "license": "supplier_press_kit"       // null credit + null license ⇒ image omitted, never guessed
    },
    "indexation": { "sitemap_updated": true, "robots": "index,follow", "submitted_to_gsc": false }
  },

  "content_summary": {
    "title":            "کروز خلیج فارس: راهنمای کامل ۱۴۰۵",
    "meta_description": "…",
    "key_points": [
      "چهار بندر در هفت شب",
      "ویزای آسان امارات — نه بدون ویزا",
      "پرواز مستقیم تهران–دبی"
    ],
    "primary_keyword":  "تور کشتی کروز خلیج فارس",
    "audience":         "d2c",              // d2c | b2b | both
    "offer": {
      "has_offer":      true,
      "product_ref":    "msc-gulf-7n",
      "price_from":     { "amount": 899.00, "currency": "EUR" },
      "price_source":   "https://boutimar.ir/api/cruises.php",
      "price_asof":     "2026-08-06T04:40:00Z",
      "departure_window": { "start": "2026-11-01", "end": "2027-03-31" },
      "visa_regime":    "easy_visa"         // visa_free | easy_visa | schengen | visa_required
    },
    "quotable_lines": [                     // Agent 3 may reuse these verbatim; anything else it must write fresh
      "هفت شب، چهار بندر، و یک دریا که نامش را قرن‌هاست می‌دانیم."
    ]
  },

  "distribution_hints": {
    "channels":        ["instagram", "telegram", "linkedin"],
    "b2b_angle":       "commission structure and group allotment for agencies",
    "d2c_angle":       "seven nights, four ports, direct flight from Tehran",
    "cta_url":         "https://boutimar.ir/cruise/persian-gulf-guide",
    "utm":             { "source": "{channel}", "medium": "social", "campaign": "gulf-guide-1405" },
    "hashtags_allowed": true,
    "embargo_until":   null,
    "assets": [
      { "type": "image", "url": "https://…/gulf-hero.webp", "aspect": "16:9", "credit": "MSC Cruises press kit" }
    ]
  },

  "compliance": {
    "profile":      "boutimar_v1",
    "checks_run":   ["persian_gulf_only", "visa_accuracy", "no_invented_facts", "sanctions_check"],
    "checks_passed": true,
    "violations":   [],                     // [{ "rule": "persian_gulf_only", "excerpt": "…", "action": "blocked" }]
    "reviewed_by":  "agent2.writer",
    "human_review_required": false
  },

  "generation": {
    "provider": "gemini", "model": "<from GEMINI_MODEL>",
    "input_tokens": 18422, "output_tokens": 3140,
    "attempts": 1, "duration_ms": 41880
  }
}
```

---

### 4.3 `campaign.log.v1` — Agent 3 ➜ Agent 4 / warehouse

```jsonc
{
  "schema_version": "1.0",
  "envelope": { /* §4.0, message_type: "campaign.log", causation_id = publishing event's message_id */ },

  "source_publication": {
    "message_id": "…", "correlation_id": "run_20260806T0415Z_a91c",
    "live_url":   "https://boutimar.ir/cruise/persian-gulf-guide",
    "brand":      "Boutimar", "language": "fa-IR"
  },

  "campaign": {
    "campaign_id": "gulf-guide-1405",
    "objective":   "traffic",               // awareness | traffic | lead | booking
    "audience":    "d2c",
    "window":      { "start": "2026-08-06T09:00:00Z", "end": "2026-08-20T09:00:00Z" }
  },

  "posts": [
    {
      "channel":       "linkedin",          // linkedin | instagram | telegram | x | facebook | email
      "audience":      "b2b",
      "account_ref":   "boutimar-b2b",
      "status":        "scheduled",         // scheduled | published | failed | cancelled
      "scheduled_for": "2026-08-06T09:00:00Z",
      "published_at":  null,
      "external_id":   "urn:li:share:7…",
      "permalink":     null,
      "copy": {
        "body":     "…",
        "hashtags": ["#cruise", "#travelagents"],
        "cta_url":  "https://boutimar.ir/cruise/persian-gulf-guide?utm_source=linkedin&utm_medium=social&utm_campaign=gulf-guide-1405",
        "language": "en",
        "hash":     "sha256:1c4a…"          // dedupe guard: never post identical copy twice to one channel
      },
      "assets": [ { "type": "image", "url": "https://…" } ],
      "error":  null
    }
  ],

  "tracking": {
    "utm_campaign": "gulf-guide-1405",
    "short_links":  [ { "channel": "instagram", "short": "https://btmr.ir/g5", "target": "https://…" } ],
    "landing_paths": ["/cruise/persian-gulf-guide"]
  },

  "lead_routing": {                          // consumed by Agent 4
    "inboxes":               ["site_chat", "whatsapp", "instagram_dm"],
    "qualification_profile": "cruise_d2c_v1",
    "price_source":          "https://boutimar.ir/api/cruises.php",
    "quote_policy":          "live_feed_only",   // Agent 4 never states a price not present in the feed
    "high_value_threshold":  { "amount": 15000, "currency": "EUR" },
    "escalate_to":           "alireza",
    "auto_escalate_signals": ["group", "MICE", "charter", "corporate", "incentive", "شرکتی", "گروهی"]
  },

  "compliance": { "profile": "boutimar_v1", "checks_passed": true, "violations": [] }
}
```

---

### 4.4 Error envelope (any agent ➜ DLQ)

```jsonc
{
  "schema_version": "1.0",
  "envelope": { /* message_type: "pipeline.error" */ },
  "error": {
    "stage":        "agent2.writer",
    "kind":         "compliance_violation",   // transport | auth | provider | validation | compliance_violation | cms
    "message":      "Output contained a blocked term",
    "retryable":    false,
    "attempts":     1,
    "original_message_id": "01J8QK…",
    "detail":       { "rule": "persian_gulf_only", "excerpt": "…" }
  },
  "payload": { /* the message that failed, verbatim */ }
}
```

---

## 5. Agent contracts

### Agent 1 — SEO Scout

* **Runtime:** GitHub Actions, `ubuntu-latest`, Python 3.11, cron `15 4 * * *`
  (04:15 UTC) plus `workflow_dispatch`.
* **Reads:** GSC `sites.list`, `searchanalytics.query`; each site's
  `sitemap.xml`; optionally the live HTML of the top-ranking own URL.
* **Writes:** nothing outside the run artifact. It never mutates a site.
* **Emits:** `content.brief.v1`, at most `MAX_BRIEFS_PER_RUN` (default 5) per
  domain, ranked by `priority_score`.
* **Rate limits:** GSC allows 1,200 queries/min/user, 200/min/site. The client
  serialises per-site queries and sleeps 250 ms between pages.
* **Cost ceiling:** one OpenAI call per domain per run, batched over the domain's
  gap candidates — not one call per keyword.
* **Failure mode:** one domain failing does not abort the run; it is recorded in
  the run manifest and the remaining domains proceed.

### Agent 2 — The Writer

* **Runtime:** `agent2_writer_batch.py` in GitHub Actions, reading Agent 1's
  artifact. `agent2_writer_listener.py` remains the FastAPI reference
  implementation and is what `selfcheck.py` exercises over HTTP; base44 was
  evaluated and rejected (§2.1). The contract is still the payload, not the
  platform — the platform simply had to be able to write files and open pull
  requests.
* **Adapters:** an adapter must NEVER report a URL it did not create. Anything
  unimplemented returns `live_url: null` with the intended path alongside it.
  `publishing.event.v1` originally *required* `live_url` to be a string, which
  made honesty impossible and produced phantom URLs for five of ten sites; it
  is nullable as of 11 Aug 2026.
* **Concurrency:** one draft per `idempotency_key` at a time; a second delivery
  of the same key while the first is in flight returns `200` with the existing
  `job_id`.
* **Timeout budget:** Gemini call 180 s, CMS push 60 s, whole job 300 s.
* **Never publishes over an existing URL** without `brief.site.cms.publish_mode`
  = `publish` **and** a matching `gap_type` of `thin_content` / `stale_content`.
  A `missing_page` brief whose target path already exists is a hard error, not
  an overwrite.

### Agent 3 — Broadcaster

* Writes **no** new factual claims. It may only recombine
  `content_summary.key_points`, `quotable_lines` and `offer` — everything else
  is a link to the article. This is the mechanism that prevents an invented rate
  from reaching Instagram.
* Schedules, does not publish immediately, unless `priority: "high"`.
* Posting to a live social account is an **outbound action** and, per the
  operating rules of this repo, requires standing per-channel authorisation
  recorded in `sites.yml` → `channels[].autopost: true`. Default is `false`
  (compose + queue for approval).

### Agent 4 — Sales Closer

* Qualifies; does not contract. It may quote **only** figures present in the
  live rate feed named in `lead_routing.price_source`, and must state the
  `price_asof` timestamp.
* Escalates to human on: value ≥ `high_value_threshold`, any
  `auto_escalate_signals` term, any request for a written proposal, any
  complaint, any refund or cancellation question.
* Never handles payment, card data or passport numbers. It collects intent and
  hands off.

---

### Agents 5 & 6 — Auditor and Analyst

* **Runtime:** `agent5-site-audit.yml`, Mondays 05:00 UTC. **No credentials of
  any kind** — Agent 5 crawls the live sites over HTTP, which is why it covers
  ten properties while Agent 1 covers only the granted ones.
* **Agent 5** produces technical, GEO and content findings per site.
* **Agent 6** turns audit + demand into strategy: a five-tier ordering, a topic
  map, a twelve-week calendar and paste-ready JSON-LD.
* **The score is sample-independent.** It began as a linear finding count, so it
  moved with `--sample` and three sites scored 0 at ten pages. Site-scope
  findings now count once; page-scope findings count as the fraction of sampled
  pages they affect. `audit_sample_pages` is **pinned at 10** in `sites.yml` and
  the cron never overrides it — changing the pin restarts the trend line.
* **Every recommendation carries evidence or it does not ship** —
  `Recommendation.valid()`. `OUT_OF_SCOPE` states five blind spots explicitly,
  including no JS rendering and no measured AI citations.

### Agent 7 — Keyword & Geo Scout

* **Runtime:** `agent7-keyword-geo.yml`, Mondays 05:30 UTC, after the audit so a
  week's reports land together.
* **Reads data that was already being thrown away.** Agent 1 queries Search
  Console with the `["query","country"]` dimension pair and keeps only the top
  country — boutimar.com returns 768 query×country rows across 74 countries
  every run. Agent 7 reads all of it.
* **Position is impression-weighted, never a plain mean.** A country where one
  obscure query sits at position 1 and forty real ones sit at 40 is not a
  country you rank in, and an unweighted average says it is.
* **Opportunities exclude the `absent` band.** A country at position 60 does not
  need optimisation; it needs a decision about whether to compete there, and
  dressing that up as an SEO task wastes a quarter.
* **Keyword Planner is unavailable for the Iran-market sites.** Google Ads does
  not operate there, so `keyword_planner_status()` reports `market_not_served`
  rather than pretending to be broken. Search Console geo data is the better
  signal there anyway: it measures what Iranian searchers actually did rather
  than estimating advertiser demand. See [SETUP-KEYWORD-PLANNER.md](SETUP-KEYWORD-PLANNER.md).

---

## 6. Run lifecycle & observability

```
run_id = run_<UTC compact timestamp>_<4 hex>      e.g. run_20260806T0415Z_a91c
       = envelope.correlation_id for every message the run produces
```

Every run writes `runs/<run_id>/manifest.json`:

```jsonc
{
  "run_id": "run_20260806T0415Z_a91c",
  "started_at": "2026-08-06T04:15:00Z", "finished_at": "2026-08-06T04:19:41Z",
  "architecture_credit": "Albaloo Studio",
  "domains": [
    { "domain": "boutimar.ir", "status": "ok", "gsc_rows": 4211, "candidates": 34,
      "briefs_emitted": 5, "delivered": 5, "dlq": 0, "duration_ms": 61220 }
  ],
  "totals": { "briefs_emitted": 18, "delivered": 17, "dlq": 1 },
  "cost": { "openai_input_tokens": 91204, "openai_output_tokens": 8811 }
}
```

Uploaded as a GitHub Actions artifact with 90-day retention. `correlation_id`
threads a single opportunity from GSC row → brief → article → post → lead, which
is the only way to answer "did this pipeline make money".

---

## 7. The compliance gate

Non-negotiable rules, enforced **twice**: injected into every prompt as a system
constraint, and re-checked against generated output before anything is
published. A prompt instruction alone is not enforcement.

### 7.1 Persian Gulf

`خلیج فارس` / *Persian Gulf*. **"Arabian Gulf" / «خلیج عربی» is a hard fail** —
in body copy, headings, alt text, meta, schema, social copy, and in any
relabelled third-party source data. ("Arabian Sea" / «دریای عرب» is a different
body of water and is left alone — the checker matches *Gulf*, not *Arabian*.)

### 7.2 Visa accuracy

* **Visa-free:** AROYA's Türkiye + Egypt routes, and Seychelles. That is the
  entire list.
* **Easy visa (not visa-free):** Persian Gulf itineraries, Dubai.
* **Schengen:** any Greek, Italian, Spanish or French port — including a sailing
  that departs Istanbul. One Schengen port makes the whole itinerary Schengen.
* Blocked phrases in any language: "no visa", "visa-free", «بدون ویزا»,
  «بدون نیاز به ویزا» — unless the itinerary is on the visa-free list above.

### 7.3 Never invent

No rate, no departure date, no inclusion, no photo credit that is not present in
`brief.data_dependencies` / `publication.hero_image`. If the data is absent, the
copy says it is absent. A price with no `price_asof` is not a price.

### 7.4 Brand & scope

* The partner **embed widget stays brand-neutral** — no «بوتیمار», no links to
  boutimar.ir. It runs inside partner agency sites.
* The CruiseHost contract belongs to **Ambiente Tours**, not Boutimar — no
  company name in outbound API headers.
* Brand voice for Boutimar long-form is poetic, experience-led luxury
  storytelling — a senior guide, not a guidebook. Evocative *and* specific, and
  never fabricated.

### 7.5 Sanctions

Any third-party service wired into the pipeline is checked for US/OFAC exposure
before integration; payment rails are EU only. Flagged, not silently adopted.

### 7.6 Implementation

`compliance.py` exposes `check(text, profile) -> list[Violation]`. Agent 1 runs
it on the brief it produces; Agent 2 runs it on the Gemini output *before* the
CMS push; Agent 3 runs it on each piece of channel copy. `blocking: true` means
a violation raises and the payload goes to the DLQ — it does not warn and
continue.

---

## 8. Open decisions

These are the assumptions currently baked into the schemas and the code. Each
one is a single-field change if the answer differs.

| # | Decision | Assumed | Impact if changed |
|---|----------|---------|-------------------|
| O-1 | boutimar.com and boutimar.ir as separate GSC properties | Yes — separate rows, separate briefs | Merge → one `site` block with a `locales[]` array |
| O-2 | Farsi drafting locale tag | `fa-IR` everywhere; Jalali dates only in rendered copy, never in payloads | Add `calendar` to `brief` |
| O-3 | ~~Agent 2 publish mode~~ | **Settled: `draft`, and the platform changed.** Agent 2 runs in GitHub Actions, not base44 (§2.1). `astro_pr` opens a pull request — for a file-generated site a PR *is* the draft: reviewable, diffable, revertible | Set `cms.publish_mode: "publish"` per site — but the WordPress adapter also hard-codes `draft`, deliberately |
| O-4 | SERP data source | **Still inferred from GSC only.** This blocks the one measured filter we cannot apply: >7 of 10 major brands on page one means a query is walled off (76% of stable AI citations go to brands). `competition_verdict()` implements the threshold and returns `unknown` without a SERP source — and an unknown verdict never filters a brief out | Wire a SERP provider; the filter starts working with no code change |
| O-5 | ~~Agent 3 autopost~~ | **Settled: composes and queues through the scheduler.** Live posting needs `ALLOW_AUTOPOST=1` **and** `channels[].autopost: true` — two independent yeses | Set both to go live per channel |
| O-6 | Price data | Only boutimar.ir has a live rate feed; other domains emit `offer.has_offer: false`, and Agent 4 quotes nothing for them | Add `data_dependencies` per site |
| O-7 | ~~Transport~~ | **Settled: artifacts internally, signed HTTP externally.** 1→2→3 read the previous stage's artifact via `workflow_run`. Signed POST remains for Agent 3 → scheduler and Agent 4's lead pull | Swap for a queue client; schemas unchanged either way |
| O-8 | ~~Scheduler backend~~ | **Settled: Zernio/Late.** Payload shape verified against the live API 2026-08-06 (`POST /api/v1/posts`, bearer token, `isDraft` for held posts). Default backend stays `file` | Set `SCHEDULER_BACKEND=zernio` + `SCHEDULER_API_KEY` |
| O-10 | Social accounts | The only connected account is a personal hobby page and is **not** wired to any brand. Every `account_ref` is `null` — see [SETUP-SOCIAL.md](SETUP-SOCIAL.md). One Telegram channel makes the pipeline deliver | Connect per brand, paste IDs into `sites.yml` |
| O-13 | ~~Audit score comparability~~ | **Settled.** The score was a linear finding count, so it scaled with sample size — three sites hit 0 at `--sample 10`. Now site-scope findings count once and page-scope ones count as the fraction of pages affected, and `audit_sample_pages` is pinned at 10 | Change the pin only with the understanding that it restarts the trend |
| O-12 | Entity owning Meta/LinkedIn assets | Recommended: **Ambiente Tours GmbH**, matching the EU-only payment rail. Iranian-registered business accounts on Meta/LinkedIn risk termination without notice | Register under the German entity before building a follower base |
| O-11 | **Imagery** | Instagram rejects text-only posts, and Agent 2 refuses to caption an image whose credit it does not know — so Instagram posts are `blocked`. Nothing in the pipeline sources licensed imagery | Wire a licensed library or supplier press-kit source into `distribution_hints.assets` |
| O-9 | The `.ir` sites | Static → `static_bundle`. dmciran.ir and cruiseshop.ir are being rebuilt as JSON-driven static like boutimar.com | Move to `astro_pr` once they land in git repos |
| O-14 | ~~WordPress anywhere~~ | **Settled: nowhere.** boutimar.com was assumed WordPress and is a JSON-driven Astro build; dmciran.ir was WordPress and is being rebuilt. The adapter is written, tested and unused | Point `wordpress_rest` at a site if one ever runs WordPress |
| O-15 | Question-shaped headings | **Downgraded on evidence.** A 100-query AI Overview study found question-format titles had *no* correlation with citation, alongside heavy formatting and fact density. What did correlate: agreeing with the consensus number (+12) and matching the answer's geographic scope (+14). Agent 1 no longer requires them; Agent 6 keeps the finding for readers and valid schema, not as a citation lever | Re-promote only if measurement changes |

---

## 9. Credit & attribution

The `architecture_credit: "Albaloo Studio"` field is **mandatory** in every
envelope and is validated on receipt — a payload missing it is rejected `400`.
It also appears in:

* `runs/<run_id>/manifest.json` — every run manifest
* the generated page footer emitted by Agent 2's CMS adapters:
  `Pipeline architecture by Albaloo Studio — albaloostudio.com`
* the `User-Agent` of every outbound HTTP request the pipeline makes
* the header comment of every source file in this directory

---

## 10. Layout

```
orchestrator/
├── ARCHITECTURE.md            ← this document
├── requirements.txt
├── config.py                  ← env loading, model IDs, site registry loader
├── compliance.py              ← §7, the enforcing implementation
├── agent1_seo_scout.py        ← GSC → OpenAI → webhook
├── agent2_writer_listener.py  ← FastAPI → Gemini → CMS → webhook (reference impl)
├── agent3_broadcaster.py      ← FastAPI → Claude → scheduler → webhook
├── agent4_sales_closer.py     ← FastAPI → Claude → qualify → escalate
├── scheduler.py               ← file / zernio / webhook backends
├── SETUP-GSC.md               ← the Search Console grant (do this first)
├── SETUP-SOCIAL.md            ← what to connect where
├── BASE44-AGENT2.md           ← what the base44 Super Agent must implement
├── selfcheck.py               ← assertions, no network, no API keys
├── sites.yml                  ← the 8 properties, machine-readable
├── .env.example
├── schemas/
│   ├── content.brief.v1.json
│   ├── publishing.event.v1.json
│   └── campaign.log.v1.json
└── (repo root) .github/workflows/agent1-seo-scout.yml
```

---

*Architecture by **Albaloo Studio** — albaloostudio.com. Owner: Alireza Mozaffari.*

---

## 10. What changed in 2.0.0

Version 1.0.0 described a design. This describes what runs. The gap between the
two is worth recording, because most of it was found by running things rather
than reading them.

| | 1.0.0 said | 2.0.0 |
|---|---|---|
| Agents | four | **seven** — 5, 6 and 7 existed and were undocumented |
| Properties | eight | **ten** — cruise24.me and albaloostudio.com added |
| Agent 2 host | base44 | **GitHub Actions** — base44 could not do git or file writes, could not give raw bytes for the HMAC, and could not hold a 90-second job |
| Internal transport | signed HTTP POST | **artifact reads on `workflow_run`** — the webhook was deleted, not reimplemented |
| `AGENT2_WEBHOOK_URL` | required | **gone.** Its absence killed the nightly cron on 9 Aug; a scheduled run supplies no inputs and so demanded a live endpoint |
| Adapters | assumed to publish | **five of ten reported URLs for pages that never existed.** The schema *required* a `live_url` string, which made honesty impossible |
| Agent 3 | broadcast anything it received | **skips events with no `live_url`** — posting a link to a staged draft sends readers to a 404 |
| boutimar.com | WordPress | **Astro, JSON-driven.** So was the WordPress adapter's second home. No property runs WordPress |
| Question headings | a GEO win | **no measured citation benefit.** Kept for readers and valid schema, not sold as a lever |
| Briefs | keyword + outline | **consensus range first, then a fact nobody else has** — the two things that did measure |

The one thing that did not change is the compliance gate's remit. It got
sharper — a claim is judged in its clause, not as a term anywhere — but «خلیج
فارس», the visa rules and never-invent-a-figure are exactly what they were.

---
