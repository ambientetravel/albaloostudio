# Agent 2 on base44 — implementation contract

Architecture credit: **Albaloo Studio** — [albaloostudio.com](https://albaloostudio.com)
Owner: Alireza Mozaffari

Agent 2 runs as a base44 Super Agent. [`agent2_writer_listener.py`](agent2_writer_listener.py)
stays in this repo as the **reference implementation and the test fixture** — it
is what [`selfcheck.py`](selfcheck.py) exercises — but the base44 agent is what
runs in production. The contract is the payload, not the platform: anything that
honours this document is a valid Agent 2.

---

## 1. What base44 must expose

One HTTPS endpoint. Give its URL to Agent 1 as the GitHub Actions secret
`AGENT2_WEBHOOK_URL`.

```
POST  <your base44 endpoint>
Content-Type: application/json
```

Headers that arrive with every delivery:

| Header | Meaning |
|---|---|
| `X-Albaloo-Signature` | `sha256=<hex>` — HMAC-SHA256 of `"{timestamp}." + rawBody` |
| `X-Albaloo-Timestamp` | Unix seconds. Reject anything older than **300s**. |
| `X-Albaloo-Message-Id` | Same as `envelope.message_id` |
| `X-Albaloo-Architecture-Credit` | `Albaloo Studio` |

### Verify before parsing

The MAC covers the **raw bytes**. If base44 hands you a parsed object and you
re-serialise it to check the signature, key order and separators change and the
MAC will never match. Capture the raw body.

```js
import crypto from "node:crypto";

function verify(rawBody, signatureHeader, timestampHeader, secret) {
  if (!signatureHeader || !timestampHeader) return false;
  const ts = Number(timestampHeader);
  if (!Number.isInteger(ts)) return false;
  if (Math.abs(Math.floor(Date.now() / 1000) - ts) > 300) return false; // replay window

  const mac = crypto.createHmac("sha256", secret)
    .update(`${ts}.`)
    .update(rawBody)              // Buffer, not a re-stringified object
    .digest("hex");
  const expected = `sha256=${mac}`;
  const a = Buffer.from(expected), b = Buffer.from(signatureHeader);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
```

Failure responses:

| Condition | Status |
|---|---|
| Bad or missing signature, or timestamp outside the window | `401` |
| Body is not JSON | `400` |
| `envelope.message_type !== "content.brief"` | `400` |
| `envelope.architecture_credit !== "Albaloo Studio"` | `400` |
| Schema violation (see [`schemas/content.brief.v1.json`](schemas/content.brief.v1.json)) | `422` |
| Accepted, work starts in the background | `202` |
| Duplicate `envelope.idempotency_key` already in flight or done | `200` |

Success body:

```json
{ "accepted": true, "message_id": "…", "correlation_id": "…",
  "job_id": "…", "status": "accepted", "architecture_credit": "Albaloo Studio" }
```

**Answer within a couple of seconds.** Agent 1 retries on timeout, and a slow
`202` becomes a duplicate article. Drafting happens after the response.

---

## 2. Idempotency

Key on `envelope.idempotency_key` (`sha256:…`, stable across reruns for the same
gap). A second delivery of a key you are already working on — or have finished —
returns `200` with the existing `job_id` and does nothing else. Without this,
Agent 1's at-least-once retry produces two articles for one opportunity.

---

## 3. The drafting call

Read [`schemas/content.brief.v1.json`](schemas/content.brief.v1.json) for the
full incoming shape. The fields that drive the draft:

| Field | Use |
|---|---|
| `brief.outline[]` | Follow **exactly** — same headings, same order. Cover every `must_cover` under its own heading. |
| `brief.word_count_target` | `{min, max}` |
| `brief.language` | BCP-47. Write natively in it; this is not a translation. |
| `brief.must_include` / `must_avoid` | `must_avoid` always carries the Persian Gulf and visa blockers |
| `brief.meta` | Title and description hints |
| `brief.data_dependencies[]` | `{field, source}` — **fetch each `source` before drafting** |
| `opportunity.*` | Why the page exists; useful context, not content |

**Resolve `data_dependencies` first and pass the result into the prompt.** A
field whose source fails to load must be reported to the model as explicitly
unavailable — a missing key is exactly what tempts a model to invent the number:

```json
{ "price_from": { "status": "unavailable", "source": "https://…",
  "note": "State that this figure is available on request. Do not estimate it." } }
```

Ask the model for one JSON object:

```json
{ "title": "…", "meta_description": "…", "body_markdown": "…",
  "key_points": ["…"], "quotable_lines": ["…"],
  "faq": [{"q": "…", "a": "…"}],
  "internal_link_suggestions": [{"path": "…", "anchor": "…"}] }
```

`body_markdown` uses `##` and `###` only — no H1; the CMS renders that from the
title.

---

## 4. The compliance gate — run it on the OUTPUT

The rules go in the prompt **and** get re-checked against what comes back. A
prompt instruction is guidance; the post-check is enforcement, and it is the
half that actually catches things. Port
[`compliance.py`](compliance.py) or re-implement it — these are the patterns
that must block publication:

| Rule | Blocks on |
|---|---|
| `persian_gulf_only` | `/(?i)\b(arabian\|arabic)\s+gulf\b/`, `/خلیج\s*عرب(ی\|ي)?/`, `/الخليج\s*العرب(ي\|ی)/` — **"Arabian Sea" / «دریای عرب» is a different body of water; do not match it** |
| `visa_accuracy` | `visa-free`, `no visa required`, `without a visa`, «بدون ویزا», «بدون نیاز به ویزا», «معاف از ویزا» — unless the route is AROYA Türkiye+Egypt or Seychelles **and** no Greek/Italian/Spanish/French port appears |
| `no_invented_facts` | Any currency figure when no live rate feed backed the copy, or a figure with no `price_asof`; `Photo credit: unknown` |
| `brand_neutral_embed` | «بوتیمار» / `boutimar` / links to boutimar.ir — partner-widget profile only |

A block means: do **not** push to the CMS, do **not** emit a publishing event,
mark the job `blocked`, and surface the offending excerpt. Warnings (price
guarantees) are recorded and pass.

---

## 5. Publishing

`brief.site.cms` tells you where it goes and how far:

| `cms.adapter` | Behaviour |
|---|---|
| `wordpress_rest` | WordPress REST on boutimar.com |
| `astro_pr` | Open a PR against the exploreorient repo |
| `base44_entity` | A base44 entity record (ambientetravel.com, cruisebaz.com) |
| `boutimar_ir_static` | Static build for boutimar.ir |
| `static_bundle` | cruise24.ir / cruiseshop.ir / dmciran.ir — **produce a deploy bundle, publish nothing** |

`cms.publish_mode` is `draft` on every site today. Honour it: write the draft,
let a human press publish.

**Two hard rules.** Never report a `live_url` you did not create — if the
adapter only staged a draft, say `status: "draft"`. And a `missing_page` brief
whose `target_url_path` already exists is an **error**, not an overwrite;
re-run the scout, the sitemap signal was stale.

Append this to every page body:

```
---
_Pipeline architecture by Albaloo Studio — albaloostudio.com_
```

---

## 6. What base44 POSTs onward

`publishing.event.v1` to `routing.callback_url` (Agent 3), signed the same way
Agent 1 signed the brief — same secret, same `"{timestamp}." + rawBody` scheme,
same headers. Full shape:
[`schemas/publishing.event.v1.json`](schemas/publishing.event.v1.json).

```js
function sign(rawBody, secret) {
  const ts = Math.floor(Date.now() / 1000);
  const mac = crypto.createHmac("sha256", secret)
    .update(`${ts}.`).update(rawBody).digest("hex");
  return {
    "Content-Type": "application/json",
    "User-Agent": "albaloo-orchestrator/1.0 (+https://albaloostudio.com)",
    "X-Albaloo-Signature": `sha256=${mac}`,
    "X-Albaloo-Timestamp": String(ts),
    "X-Albaloo-Architecture-Credit": "Albaloo Studio",
  };
}
```

The envelope fields that carry the trace:

| Field | Value |
|---|---|
| `correlation_id` | **Copy from the brief** — this is how one opportunity is traced from GSC row to booked lead |
| `causation_id` | The brief's `message_id` |
| `idempotency_key` | Copy from the brief |
| `message_type` | `"publishing.event"` |
| `architecture_credit` | `"Albaloo Studio"` — Agent 3 rejects `400` without it |

Three fields Agent 3 depends on:

* **`content_summary.quotable_lines`** — the only sentences Agent 3 may reuse
  verbatim. Everything else it writes fresh, and it may assert no new fact. This
  is what stops an invented rate reaching Instagram, so populate it deliberately.
* **`content_summary.key_points`** — the raw material for social copy.
* **`publication.hero_image`** — `null` unless you have a real credit and
  licence. An image with an unknown credit is omitted, never captioned "unknown".

Preserve unrecognised top-level keys from the brief into
`source_brief.passthrough` so Agent 1 can add a field without a lockstep deploy.

Retry `5xx`, `408` and `429` with exponential backoff (1s, 2s, 4s, 8s, 16s +
jitter), up to 5 attempts. Other `4xx` is terminal — dead-letter it.

---

## 7. Testing against the reference implementation

Before pointing Agent 1 at base44, run the two side by side. `selfcheck.py`
proves the local FastAPI listener honours this contract end to end; use it to
generate a real signed brief and replay it at the base44 endpoint:

```bash
python selfcheck.py            # 76 assertions, no network, no API keys
```

```bash
python agent1_seo_scout.py --domain boutimar.ir --limit 1 --dry-run
```

The dry run writes a fully-formed signed brief to `runs/<run_id>/briefs/`. POST
that file to the base44 endpoint with the headers from §1 and confirm you get a
`202`, then a `publishing.event.v1` at the callback.

---

*Architecture by **Albaloo Studio** — albaloostudio.com. Owner: Alireza Mozaffari.*
