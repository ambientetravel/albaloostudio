# Keyword Planner — what it can and cannot do for this portfolio

Architecture credit: **Albaloo Studio** — [albaloostudio.com](https://albaloostudio.com)
Owner: Alireza Mozaffari

Read this before spending a day on the setup, because for the three sites you
called most important, **two of them cannot use it at all.**

---

## The short version

| Site | Market | Keyword Planner | What it uses instead |
|---|---|---|---|
| `boutimar.com` | INT | ✅ worth it | — |
| `exploreorient.com` | INT | ✅ worth it | — |
| `ambientetravel.com` | DACH | ✅ worth it | — |
| `cruise24.me` | INT | ✅ worth it | — |
| `albaloostudio.com` | INT | ⚠️ low value — tiny surface | — |
| **`boutimar.ir`** | **IR** | ❌ **cannot** | Search Console geo |
| **`cruise24.ir`** | **IR** | ❌ **cannot** | Search Console geo |
| `cruiseshop.ir` | IR | ❌ cannot | Search Console geo |
| `dmciran.ir` | IR | ❌ cannot | Search Console geo |
| `cruisebaz.com` | IR | ❌ cannot | Search Console geo |

---

## Why the Iranian sites cannot use it

Google Ads does not operate in Iran. US sanctions mean no Iranian Ads account,
no ad delivery into Iran, and embargoed territories absent from the geo-target
list. Keyword Planner is an *advertising* tool: it reports what advertisers can
bid on, in markets where ads can run. Iran is not one of those markets.

**This has not been confirmed against a live Ads account, and it should be
before anyone builds on the assumption.** It could not be verified from this
machine — Google's published geo-target list renders client-side, so scraping
it returns nothing for *every* country, Germany included, and proves nothing.
Treat the table above as the working assumption, not as measured fact.

### The substitute is better than the thing it replaces

Search Console reports Iran directly, and it reports **measured behaviour by
real Iranian searchers** rather than an estimate of advertiser demand.
`boutimar.ir` already returns 88 impressions from `irn` across 7 countries; the
data is flowing today and costs nothing.

For the Iran-market sites this is not a fallback. Keyword Planner would tell you
what a hypothetical advertiser might pay for a term. Search Console tells you
what actual people in Tehran typed, which of your pages Google showed them, and
at what position. For an organic programme that is the stronger signal, and it
is the one this pipeline already has.

---

## What Keyword Planner genuinely adds, and nothing here replaces

**Discovery of terms with zero current impressions.**

Search Console can only ever show queries a site *already surfaces for*. If
`boutimar.com` has never once appeared for "luxury Iran tour operator", Search
Console will never mention it — the term is invisible, not absent. Keyword
Planner does not have that blind spot.

That gap is real, and it is the whole reason to do the setup. It applies to the
world-market sites, where Ads does operate.

---

## Setup, for the sites where it applies

**Time: an afternoon, plus a review wait that is out of your hands.**

1. **A Google Ads account.** Not necessarily a spending one, but see the warning
   below about ranges.
2. **A developer token** — Ads account → *Tools → API Center*. Basic access is
   an application with a human review, typically a few days. Test-account tokens
   return test data only, which is useless here.
3. **OAuth2 client** in the same Google Cloud project as the Search Console
   service account → *Credentials → Create OAuth client ID → Desktop app*.
4. **A refresh token**, generated once by running the OAuth flow locally and
   consenting as the Google account that owns the Ads account.
5. **The customer ID** — the 10-digit number top-right in the Ads UI, no dashes.

Then, as GitHub repository secrets:

| Secret | |
|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | from step 2 |
| `GOOGLE_ADS_CLIENT_ID` | from step 3 |
| `GOOGLE_ADS_CLIENT_SECRET` | from step 3 |
| `GOOGLE_ADS_REFRESH_TOKEN` | from step 4 |
| `GOOGLE_ADS_CUSTOMER_ID` | from step 5, digits only |

`agent7_keyword_scout.py` reports `not_configured` and names exactly which of
the five is missing, rather than failing the run.

### The service account will not work

The Search Console key already in this pipeline cannot be reused. Google Ads
rejects service accounts outside Workspace domain-wide delegation, and these are
consumer Gmail accounts. Keyword Planner needs a user-consented OAuth refresh
token — a different credential with a different lifecycle.

### Volumes come back as ranges

Without meaningful active spend, `GenerateKeywordIdeas` returns buckets — "1K –
10K" — not numbers. Buckets that wide cannot rank candidates against each other,
which is the entire job. Budget for a small live campaign, or accept that the
output is directional only.

---

## What runs today, with no setup at all

`agent7_keyword_scout.py` answers the geographic half of the question right now,
for every granted property, using Search Console data Agent 1 already fetches
and discards:

- per-country impressions, clicks, and **impression-weighted** average position
- a position band per country, and what to do about each
- a market-alignment check: does the site surface where its market actually is
- ranked country opportunities, excluding the ones not worth competing in

```bash
python3 agent7_keyword_scout.py                    # every active site
python3 agent7_keyword_scout.py --domain boutimar.com --format json
```

The first run already found something worth acting on: **boutimar.com's single
strongest country is Iran**, at position 10.5 — better than the United States at
35.8, despite being the portfolio's international brand. An INT-market site
whose best market is domestic is a positioning question, not a keyword one.

---

*Architecture by **Albaloo Studio** — albaloostudio.com. Owner: Alireza Mozaffari.*
