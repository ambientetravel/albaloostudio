# Search Console access — the one thing only you can do

Architecture credit: **Albaloo Studio** — [albaloostudio.com](https://albaloostudio.com)
Owner: Alireza Mozaffari

Everything else in this pipeline runs without you. This does not: the Search
Console properties sit under several Google accounts, and no API merges them.
Agent 1 reads only the properties that have been granted.

**Time: ~5 minutes per owning account.** A second browser profile makes this far
less annoying than signing in and out repeatedly.

---

## Why it has to be done once per owning account

**Verified 6 Aug 2026: the properties are spread across more than two accounts.**
`alimozzarella@` and `contactmozaffari@` between them own only three of the
eight. The rest sit under brand-specific accounts — `ambienteturizm@gmail.com`,
`cruisebazonline@gmail.com` and others visible in the Google account chooser.

Nothing about the approach changes. It is still one service account granted
separately on each property; there are simply more sign-ins than two.

A service account is a robot user. It inherits nothing from you. There is no
"link my Google accounts" call, no delegation shortcut (that is Workspace only,
and these are all consumer Gmail), and no way to export one account's history
into another.

What *does* work: one robot, added as a user on every property, by whichever
human owns that property. Then one JSON key reads all of them.

```
alimozzarella@       ─┐
contactmozaffari@     │
ambienteturizm@       ├─→ each adds the SAME service account as a Restricted user
cruisebazonline@      │                    │
…                    ─┘                    ▼
                        one JSON key  →  GH secret  →  reads every granted property
```

---

## Step 1 — Create the robot (5 min, either account)

1. [console.cloud.google.com](https://console.cloud.google.com) → **new project**,
   name it `albaloo-orchestrator`.
2. **APIs & Services → Library** → search **Google Search Console API** →
   **Enable**. (It is the one called *Google Search Console API*, not "Search
   Console API v1" or the Indexing API.)
3. **IAM & Admin → Service Accounts → Create service account**.
   Name `albaloo-orchestrator`. Skip both optional steps — it needs **no**
   project role at all; its access comes from Search Console, not from GCP IAM.
4. Open it → **Keys → Add key → Create new key → JSON**. A file downloads.
5. Copy the `client_email` out of that file. It looks like:
   `albaloo-orchestrator@albaloo-orchestrator.iam.gserviceaccount.com`

Keep the JSON file. It is the only Google credential the pipeline ever holds,
and Google will not show you the key again.

---

## Step 2 — Grant it, account by account

Work through the account chooser. As of 6 Aug 2026:

| Property | Owning account |
|---|---|
| `boutimar.com`, `boutimar.ir` | `alimozzarella@gmail.com` ✓ granted |
| `exploreorient.com` | `contactmozaffari@gmail.com` ✓ granted |
| `ambientetravel.com` | likely `ambienteturizm@gmail.com` — unverified |
| `cruisebaz.com` | likely `cruisebazonline@gmail.com` — unverified |
| `cruise24.ir`, `cruiseshop.ir`, `dmciran.ir` | unknown — check the chooser |

Sign in to [search.google.com/search-console](https://search.google.com/search-console)
as each account in turn.

For **each** property that account owns:

1. **Settings** (left sidebar, near the bottom) → **Users and permissions**
2. **Add user**
3. Paste the `client_email` from step 1
4. Permission: **Restricted** ← not Full
5. **Add**

**Restricted, deliberately.** Agent 1 only reads: it calls `sites.list` and
`searchanalytics.query` and nothing else. Full permission would additionally let
it submit sitemaps and request URL removals. A daily cron job has no business
holding the ability to deindex your pages.

Repeat for every account that owns a property. This is the step that gets
half-done — if Agent 1 later reports three properties instead of eight, this is
why, and `--list-properties` names exactly which are missing.

---

## Step 4 — Verify (1 min)

Point the loader at the file — no need to paste the key anywhere:

```bash
cd orchestrator && GOOGLE_APPLICATION_CREDENTIALS=~/Downloads/albaloo-orchestrator-*.json \
  python agent1_seo_scout.py --list-properties
```

Every row should read `siteRestrictedUser`, with no "NOT readable" list at the
bottom. Anything missing is named explicitly — go back to step 2 for exactly
those.

**Status 6 Aug 2026: 3 of 8 granted** — boutimar.com, boutimar.ir,
exploreorient.com. The other five await the accounts that own them.

The CI workflow runs this same command as a separate step before the scout, so a
half-granted service account fails the run loudly instead of silently scouting
six sites.

---

## Step 5 — Load the secrets

GitHub → the repo → **Settings → Secrets and variables → Actions → New
repository secret**:

| Secret | Value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | the entire JSON file contents, on one line |
| `OPENAI_API_KEY` | for Agent 1's gap analysis |
| `WEBHOOK_SIGNING_SECRET` | any 32+ random chars — the same value goes in all four agents |
| `AGENT2_WEBHOOK_URL` | the base44 endpoint ([contract](BASE44-AGENT2.md)) |
| `AGENT3_WEBHOOK_URL` | Agent 3's `/webhooks/publishing` |

Generate the signing secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

If the JSON gives GitHub trouble as a single line, base64 it — the loader
accepts either form:

```bash
base64 -i ~/Downloads/albaloo-orchestrator-*.json | tr -d '\n' | pbcopy
```

---

## Things that will waste your afternoon

**A domain property, not a URL-prefix property.** `sc-domain:boutimar.ir` rolls
up www, apex, http and https into one row. A URL-prefix property splits your
data across four. `sites.yml` assumes domain properties; if one of the eight was
only ever verified as a URL prefix, fix the `property_uri` there to match
exactly what Search Console shows.

**An OAuth client is not a service account.** If you download "OAuth client
credentials" instead, the loader rejects it by name — the key's `type` field
says `authorized_user` rather than `service_account`.

**Search Console lags about two days**, and drops low-volume queries entirely.
Agent 1 queries back from `today-3d` and never expects today's numbers.

**Nothing has been spent yet.** The Search Console API is free. The only cost in
a run is the OpenAI call — one per domain, batched over that domain's gap
candidates, not one per keyword.

---

*Architecture by **Albaloo Studio** — albaloostudio.com. Owner: Alireza Mozaffari.*
