# Parked — pick up after the consulting

Written 27 Aug 2026 by session `claude-websitebuilder-49`.
Everything below is finished, verified, or waiting on one named decision.

> **Re-verified live 25 Oct 2026** (orchestration session) — corrections inline, marked ✎ 25 Oct.
> The full table with evidence is in `orchestrator/OPS-APP.md` → Fact-check.

## Done and live today

- **cruise24.ir: 15 generated pages deployed and verified.** All six spot-checked
  URLs return 200. Sitemap went from **4 declared URLs to 50**. 29 orphan ship
  pages now have inbound links (msc 24, celestyal 2, explora 3). `msc.html`
  went 242 → 1,053 words. Visa rule holds on the live page: «ویزای آسان» ×19,
  «بدون ویزا» 0, «خلیج عربی» 0.
- **All six pages confirmed INDEXED by Google** — "URL is on Google / Page is
  indexed", before any manual request. Sitemap status Success, 50 discovered.
- Generator: `cruise24-ir/_build.py`, `_visa.py`, `_chrome.py`. `--check`
  fetches the live page and fails on chrome drift or feed drift.

## Waiting on one decision each

| Item | Blocked on |
|---|---|
| **Bing verification** for cruise24.ir | Listed but NOT verified. Download `BingSiteAuth.xml` from Bing, then a DirectAdmin upload. Bing feeds Yahoo and DuckDuckGo. |
| **cruisebaz.com** | Handed to its session. Two decisions: does it keep its five Farsi page-1 rankings, and is there a supplier for Royal Caribbean / Carnival / Princess (feed has ZERO). |
| **Search Console connector** on base44 | Cancelled deliberately. `sites.yml` records properties split across `alimozzarella@gmail.com` (5) and `contactmozaffari@gmail.com` (4), with cruisebaz.com UNCONFIRMED. One OAuth grant spanning both clusters is a decision, not a setup step. |
| **Dashboard auto-fetch** | Works as a manual-paste viewer. Auto-fetch needs a read-only GitHub token stored in base44. |
| **Agent 4 — Sales Closer** | ✎ 25 Oct: wired to cruise24.me, every 4 h — 75 runs since 31 Aug, but **0 real leads ever**: 69 runs found none waiting, 5 ran before the pull was set up. Blocked on lead flow, not code. |

## Known defects, unfixed

- ✎ 25 Oct **FIXED** — `/journal/hotels-…` answers 200; the writer records the real path. Original note: **Astro route bug.** Merge-watch found it: brief records
  `/hotels/yazd-joybar-boutique-hotel-review/`, Astro publishes
  `/journal/hotels-yazd-...`. Anything using the recorded URL points at a 404.
- ✎ 25 Oct **FIXED** — `_push_base44_entity` exists and has created 6 cruisebaz drafts. Original note: **`base44_entity` has no adapter.** Declared in `sites.yml` for
  ambientetravel.com and cruisebaz.com; Agent 2 implements only `astro_pr`,
  `boutimar_ir_static`, `static_bundle`, `wordpress_rest`. Those two sites have
  no writer at all. It is also the one place a base44 Superagent is the natural
  owner rather than a duplicate.
- ✎ 25 Oct **still there** (repo secrets list it); no code reads it — Alireza deletes it in Settings → Secrets. **`WEBHOOK_SINGING_SECRET`** — the typo'd repo secret is still there. Harmless
  now (nothing internal uses the webhook path) but Agent 3 references the
  correct spelling and would fail silently if that path ever ran.
- ✎ 25 Oct **RESOLVED — quote this one figure:** today's feed, Nowruz 1406 (15 Mar–10 Apr 2027): **468 departures, 192 (41%) need a national visa** (US/UK/Canada etc.), classified by `c24data.visa_for`. The pairs below were Nowruz 1405 on an older feed. **Nowruz visa counts disagree.** 255 sailings / 53 hard-visa here against
  245 / 58 from session 45, same window. Both say ~a fifth is unsellable to a
  client who cannot get a US/UK/Canada visa. Quote one figure, not two. That
  session has exited; reconciliation never finished.

## The finding that outranks the rest

✎ 25 Oct, refreshed: **206 of 769** usable demand terms name the Persian Gulf/Dubai/Gulf ports against **48 departures (0.77% of 6,238)**; the Mediterranean has **34** terms against **4,137** departures. (The 199 below was the destination-generic cluster size.)

**Demand and inventory are inverted.** Persian Gulf + Dubai = 199 keyword terms
against **18 sailings** (0.5% of a 3,485-sailing catalogue, and they are the
same 18). Mediterranean = **2,445 sailings** against 6 terms. Iranians search
the Gulf; the company sells the Western Med. That is a sourcing question and no
amount of page-building fixes it.

Also: celestyal and explora have **zero** Farsi demand terms. Not a data gap —
nobody searches those brand names in Persian.

## Visibility baseline, for measuring later

Before the deploy: **17 of 769 keywords** surfaced on any property.
cruisebaz held all five page-1 positions (قیمت کروز 3.0, تور کشتی کروز 7.0,
کشتی کروز 7.0, aroya 8.3, عربستان 8.7). boutimar.ir had 15 listings, 13 past
page four. cruise24.ir had 1.

Re-run `keyword-demand.yml` in ~2 weeks to measure movement. Indexed is not
visible — Google now has the pages; whether they rank is the open question.
