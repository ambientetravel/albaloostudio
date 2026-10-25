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

**Built 25 Oct 2026** (orchestration session): `tools/ops_sync.py` + `.github/workflows/ops-sync.yml`,
hourly at :40. Read-only probe of `ArticleReview` → HTTP 200 with the existing `BASE44_ACCESS_TOKEN`
(no new token needed). Seeded 34 rows (run 40207408284) after a dry run; a second dry run plans
nothing. The board's Pipeline ID is the row key (`repo#pr`, or `domain/slug` stored in `repo` for a
base44 draft). The ping is a Notion @mention on a "🔔 New drafts" row (the Monday summary's proven
path): Actions has no Telegram bot and no working mail sender. Tests: 5 in selfcheck.py.

## Phase 2: the Leads tab (built 25 Oct 2026, session "24-hour project strategy")

`tools/ops_leads.py` runs as the last step of `agent4-sales-closer.yml`, on the
records that run just wrote. leads.php hands each lead out only once, so this is
the only moment to push it. One `Lead` row per record:
- `summary` starts "Reply to: <address>", then intent · party · window ·
  budget, what is missing, the campaign, and the redacted message
- `qualification` band: **hot** = a qualified booking/price/availability
  enquiry that is escalated or worth ≥ €5,000; **warm** = any other qualified
  lead; **cold** = spam or unqualified
- `draft_reply`, empty when the compliance gate blocked it
- `escalated` + `escalation_reason`

Rows are keyed `source = channel:lead_id`, so re-runs never duplicate. Staff
fields (status, assigned_to, notes, reply_released) are set once (new / "" /
"" / no) and then belong to the app. **Lead state is not pulled back into
git**: a CRM status next to a customer's email does not belong in a
repository. This replaces build-order item 2's "status → repo JSON".

New leads ping Alireza on the same Notion 🔔 row.
`.github/workflows/ops-leads-backfill.yml` pushes a past run's kept artifact
(7 days).

First push: run 40238408454 sent Agent 4 run 40224394726's three TEST leads
(cruise24.me, all cold). Tests: 3 in selfcheck.py, plus the 5 from phase 1,
all passing when run in isolation. The full selfcheck stops at line 2696 on
main because it needs `../boutimar-ir`, which isn't in this repo.

**Gap:** the `Lead` entity has no contact or name field, so the reply address
lives in `summary`. Add `contact` and `display_name` fields in base44, and
ops_leads.py should fill them.

## Fact-check of open issues — re-verified LIVE 25 Oct 2026 (orchestration session)

Checked against Actions runs, repo secrets, live URLs and today's feed, not the code alone.
Supersedes the first draft of this table, which had three rows wrong (marked ✎).

| Claim (PARKED.md, 27 Aug) | Status 25 Oct | Live evidence |
|---|---|---|
| `base44_entity` adapter missing | **Fixed** | Code `agent2_writer_listener.py:1378` → `_push_base44_entity` (:2038); live: the writer has created 6 cruisebaz drafts in base44 (11 + 18 Oct), all on the Content Review board |
| Astro route bug `/hotels/…` vs `/journal/hotels-…` | **Fixed** | `boutimar.com/journal/hotels-yazd-joybar-boutique-hotel-review/` → 200; the brief's old `/hotels/…-review/` → 404 (nothing links there); writer note at `agent2_writer_listener.py:1564` |
| `WEBHOOK_SINGING_SECRET` typo | **Still there** — no code reads it | Repo secrets (25 Oct, 11 names) still list `WEBHOOK_SINGING_SECRET`; code reads only `WEBHOOK_SIGNING_SECRET` and warns about the typo. **Alireza:** delete it in GitHub → albaloostudio → Settings → Secrets (irreversible, so not done for you) |
| ✎ Agent 4 has no lead source | **Wired, but has never had a lead** | cruise24.me signed pull, every 4 h. 75 runs since 31 Aug: 69 "no leads waiting", 5 before the pull was set up, 1 on 31 Aug qualified 4 (before cruise24.me was wired). Not one `agent4-closed` artifact exists, i.e. **0 real leads processed**. One red run (11 Oct, cruise24.me timeout) fixed by retry in f36c62a |
| ✎ Nowruz visa counts disagree (255/53 vs 245/58) | **Resolved — quote one figure** | Today's feed (6,238 departures), Nowruz 1406 window 15 Mar–10 Apr 2027 (the window in cruise24.ir's builder), classified by `c24data.visa_for` (mirror of `api/v1/cruises.php`): **468 departures, 192 need a national visa** (US/UK/Canada etc.: 86 alone + 106 with Schengen) = 41%; Schengen-only 266; visa-free 3; unresolved 7. The old pairs were Nowruz 1405 on an older, smaller feed |
| 22 article PRs unmerged | **Worse: 34 drafts waiting** | 28 open PRs (boutimar 5, boutimarfarsi 8, cruise24-ir 6, exploreorient 9; oldest 28 days) + 6 cruisebaz base44 drafts. All 34 are now in the ops app's Review queue |
| ✎ 11 social posts without image | **3, not 11** | The 11 came from a no-model TEST broadcast (19 Oct) counted as a cycle — health fixed in 8d181ad. Real run 25 Oct: 3 of 3 Instagram posts have no image (they promote pages published before articles carried photos). Fix = take the live page's photo |
| AI recall 0/8 properties | **Open — not stale** | Oracle (`ai-visibility.yml`) runs monthly on the 1st; last 1 Oct, next 1 Nov |
| Persian Gulf demand vs inventory (199 terms vs 18 sailings) | **Sharper than stated** | Inventory today: Gulf = 8 itineraries / **48 departures (0.77%)**; Mediterranean = **4,137 departures**. Demand (keywordchi export, Aug 2026 — static until a new export): **206 of 769** usable terms name the Persian Gulf, Dubai or a Gulf port; **34** name the Mediterranean. The old "199" was the size of the destination-generic cluster, not a Gulf count |

## Phase 3: the Today tab (built 25 Oct 2026, session "24-hour project strategy")

`tools/ops_today.py`, an hourly step of `ops-sync.yml`, mirrors
`reports/health-latest.json` into the app:
- `AgentRun`: upsert by agent
- `HealthItem`: replaced each sync, markdown stripped
- `Metric`: upsert by name; `previous` is the value it replaced, or the
  report's `prev_*` figure

First write: run 40240969278 sent 11 agents, 3 health lines and 8 metrics,
22 calls with 0 errors. Tests: 3 in selfcheck.py.

Phase 2 follow-up (commit 1947abe): `Lead.contact` and `Lead.display_name` are
filled. Agent 4's record now keeps the name the customer typed. Verified live
by run 40240621198: form TEST enquiry → Agent 4 (spam, so cold) → Lead row
created, 0 errors.

## Phase 4: the Social tab (built 25 Oct 2026, session "24-hour project strategy")

`tools/ops_social.py`, an hourly step of `ops-sync.yml`, reads the latest
successful `agent3-broadcast` artifact. It shows every held post as a card:
site, channel, copy with hashtags, the article photo, and the link. A team
Approve or Reject sets the card's status.

**Nothing is published from here.** An approved post is put up by hand, or it
is the trigger to switch that one channel's autopost on. A selfcheck asserts
that the module contains no posting call.

First write: run 40242067295 created 6 boutimar.com posts (3 LinkedIn and 3
Instagram), with 0 errors. None has a photo: they are pre-7-Oct articles, as
the health report already said.

Article photos: `ops_sync.find_image()` plus the `images_dry_run` and
`images_apply` modes. Run 40241842373 found **0 of 34** open drafts with a
public photo URL: drafts hold repo-relative paths. The fix is for Agent 2 to
write `image_source_url`; this was asked of the orchestration session.
`OPS_ARTICLE_IMAGES` stays off until the app has `image_url` (see
`OPS-APP-VISUAL-PROMPT.md`).
