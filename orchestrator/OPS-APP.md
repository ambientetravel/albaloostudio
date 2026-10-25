# Albaloo Ops: one base44 app for the whole portfolio

Architecture credit: **Albaloo Studio** — albaloostudio.com
Owner: Alireza Mozaffari. Spec written 25 Oct 2026 by session "24-hour project strategy".

## The app

- Published URL: **https://albaloo-ops-core.base44.app** (built 25 Oct 2026 from OPS-APP-PROMPT.md: Review, Today, Leads, Social, Team tabs; six entities).
- App ID: **6ade14ab5b5e6721cc424fbe** (given by Alireza 25 Oct 2026). Entity API base: see `base44_entity_url()` in agent2_writer_listener.py.

## The rule

**GitHub stays the source of truth. base44 is the window and the team's input form.**

- Every agent keeps running in GitHub Actions, unchanged. ARCHITECTURE.md §2.1
  records why base44 can't run an agent: no git or file writes, no raw-body HMAC,
  and no 30–90 s background work.
- One new Action, `ops-sync`, **pushes** snapshots of the pipeline's own
  artifacts into base44 entities. It authenticates with the existing
  `BASE44_ACCESS_TOKEN`, through the same entity REST path as `base44_entity_url()`
  in `agent2_writer_listener.py:2033`.
- The same Action **pulls** the team's inputs back (lead status, approvals,
  verified rates) and commits them to the repo as JSON, so agents read them
  exactly as they read every other input.
- Nothing in base44 calls GitHub, and base44 never receives a webhook. That
  keeps the one direction that has worked (see `inbox/README.md`).

```
GitHub Actions (agents 1–8, health, inventory, merge-watch …)
      │  artifacts / reports/*.json / written/*.json
      ▼
  ops-sync.yml  ── every 30 min ──►  base44 "Albaloo Ops" entities  ◄── team logs in
      ▲                                     │
      └──────── pulls team inputs ──────────┘  (Lead.status, Approval, Rate.verified)
```

## One app, access by role and property

Each `User` gets two custom fields: `role`, and `properties` (a list of domains).
Every entity row carries `property`. Use base44 entity security rules so a user
reads and writes only rows whose `property` is in `user.properties`. The owner
and managers see everything.

| Role | Sees | Can change |
|---|---|---|
| `owner` (Alireza) | everything | everything, user admin |
| `manager` | every property | approvals, assignment, rates |
| `sales` | Leads, Quotes and Rates for their properties | lead status, notes, quotes, **Send** (human release) |
| `content` | article PR queue, social queue, SEO for their properties | approve or hold posts, review notes |
| `partner` (agency) | only Leads carrying their `partner_id`, plus their embed code | lead status on their own leads |
| `viewer` | dashboards only | nothing |

## Entities

| Entity | Filled by | Source in repo |
|---|---|---|
| `Property` | ops-sync | `sites.yml` (domain, platform, language, owning session) |
| `AgentRun` | ops-sync | `reports/health-latest.json` → `agents[]` (agent, result, age, run URL) |
| `HealthItem` | ops-sync | `health-latest.json` → `critical / needs_you / warn / fine` |
| `Metric` | ops-sync | `health-latest.json` → `numbers` (briefs, articles, cost_usd, open PRs, AI recall …) |
| `ArticlePR` | ops-sync | merge-watch / PR gate output (repo, PR number, title, age, gate verdict) |
| `SocialPost` | ops-sync ⇄ team | Agent 3 `campaign.log.v1` (held at the autopost gate) → team approves → pulled back |
| `Lead` | ops-sync ⇄ team | Agent 4 output (already redacted, qualified, draft reply) → team sets status and releases |
| `Quote` | team ⇄ Agent 4 | Agent 4 opens a draft when a lead asks for a written proposal |
| `Rate` | team / rate reader | supplier sheets; `verified=false` until a manager approves; only verified rows reach Agent 4 |
| `Sailing` | ops-sync | cruise24.me inventory sync (daily) — summary per line and region, not every row |
| `Keyword` | ops-sync | `written/*-demand-*.json`, Agent 7 country visibility |
| `Partner` | owner | agency, embed code, `partner_id` |

PII: `Lead` holds only what Agent 4 has already redacted. Passports, card data and
payment details never enter base44 (ARCHITECTURE.md §5, Agent 4).

## Screens

1. **Pipeline**: one card per agent (green, amber or red, last run, link to run), plus "Needs you" at the top.
2. **Leads**: inbox by property, the draft reply, and a Send button that only a human presses.
3. **Quotes and Rates**: quote builder, PDF export, rate approval queue.
4. **Content**: open article PRs by age, and the social approval queue.
5. **SEO and Demand**: keyword demand against inventory per region (the Persian Gulf inversion lives here).
6. **Inventory**: sailings by line and region, plus price-drop list.
7. **Admin**: users, roles, properties, partners.

## Build order

1. Read-only first: `Property`, `AgentRun`, `HealthItem`, `Metric`, `ArticlePR` and the Pipeline screen. No team input, no risk.
2. `Lead`, then the pull-back path (status → repo JSON → Agent 4).
3. `SocialPost` approvals. These replace flipping `ALLOW_AUTOPOST` by hand.
4. `Rate` and `Quote`. These need real supplier rate sheets. **Never seed invented rates.**
5. `Partner` portal.

## Phase 1 is the Review queue (changed 25 Oct 2026)

Alireza misses article drafts because nothing reaches his phone. Notion "Content
Review" (`tools/notion_review_sync.py`, hourly, working: run 40198837793) is
already the decision path: Approved → squash-merge, Needs edits → feedback on the
PR and a revision, Rejected → PR closed.

The app's Review screen must use **that same path**, not a second one.
`ops-sync` copies open article PRs into `ArticleReview`. When a row's
`decision` is set in base44, `ops-sync` writes that decision onto the Notion row,
and the existing review-sync acts on it. One brain: GitHub decides, Notion and
base44 are two windows on it. `ops-sync` also sends a ping (Telegram or email to
Alireza) the moment a new draft lands.

The paste-ready prompt is `OPS-APP-PROMPT.md`.

## Fact-check of open issues (25 Oct 2026, against code on main)

| Claim (PARKED.md, 27 Aug) | Status now | Evidence |
|---|---|---|
| `base44_entity` adapter missing | **Fixed** | `agent2_writer_listener.py:1378` `_push_base44_entity` |
| Astro route bug `/hotels/…` vs `/journal/hotels-…` | **Fixed in Writer** | `agent2_writer_listener.py:1549-1564`; merge_watch documents the trap |
| `WEBHOOK_SINGING_SECRET` typo | Code uses the correct name and warns about the typo'd secret | `agent2_writer_listener.py:2400-2405`. **To check:** delete the typo'd repo secret |
| Agent 4 has no lead source | **Wired** for cruise24.me (`sites.yml:651`, signed GET, `LEADS_SIGNING_SECRET`), every 4 h | Closer last run OK, 0.3 days old. **To check:** how many leads it has processed so far |
| Nowruz visa counts disagree (255/53 vs 245/58) | **Unresolved**. Reconcile on today's feed and quote one figure | — |
| 22 article PRs unmerged (oldest 27 days) | **Open**, waiting on Alireza | `reports/health-latest.md` |
| 11 social posts without image | Open; pre-7-Oct articles only | health report |
| AI recall 0/8 properties | **Open**. No model names any property | health report, Oracle 22.9 days old |
| Persian Gulf demand vs inventory (199 terms vs 18 sailings) | Sourcing problem, not software | PARKED.md. Refresh on today's inventory |

The orchestration session should re-verify each row live (Actions runs, repo
secrets, live URLs) and correct this table rather than trust it.
