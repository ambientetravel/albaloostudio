# Plugging the ends in

Architecture credit: **Albaloo Studio** — [albaloostudio.com](https://albaloostudio.com)
Owner: Alireza Mozaffari

The seven agents run. What is left is three connections at the edges, and each
one is now a single secret away — the code behind all three is written, tested
and merged.

| | What it unblocks | You provide | Time |
|---|---|---|---|
| **1. Telegram via Make** | Agent 3 posts instead of queueing | a Make webhook URL | ~15 min |
| **2. A lead source** | Agent 4 stops being idle | an endpoint or a file | ~20 min |
| **3. WordPress** | Agent 2's articles reach **dmciran.ir** | an Application Password | ~5 min |

Do **3 first**. It is the shortest, and it is the one where five articles a
night are already being written and thrown away.

---

## 3. WordPress — five minutes, for dmciran.ir

**Corrected 11 Aug 2026.** This section originally named boutimar.com, which
has not been WordPress for some time — it is a static Astro build now, driven
by JSON in `src/data/`, and `/wp-admin` returns 404. The adapter was built
against a site that no longer exists in that form.

The site it genuinely belongs to is **dmciran.ir**, where `/wp-admin`,
`/wp-json/wp/v2` and `/wp-login.php` all answer 200. That is also the site
scoring 75/100 with 48 audit findings and zero impressions in 480 days, so it
is the one with the most to gain from new content.

boutimar.com now uses `astro_pr`, like exploreorient: Agent 2 writes a content
file and opens a pull request. Nothing reaches the live site without a human
merging it — the right shape for a site with no CMS to hold a draft.

**Create an Application Password**, not your account password:

1. `dmciran.ir/wp-admin` → **Users → Profile**
2. Scroll to **Application Passwords**
3. Name it `albaloo-agent2` → **Add New Application Password**
4. Copy the value it shows once. **Keep the spaces** — WordPress generates it
   in `xxxx xxxx xxxx xxxx` form and stripping them is the most common reason
   for a 401.

**Then two repository secrets:**

| Secret | Value |
|---|---|
| `WORDPRESS_USER` | your wp-admin username |
| `WORDPRESS_APP_PASSWORD` | the value from step 4, spaces and all |

That is the whole setup. The adapter is wired to `wordpress_rest` in
`sites.yml` for dmciran.ir.

**It always writes `status: draft`.** Even if `publish_mode` says `publish`.
Five unattended articles a night reaching a live commercial site is not a
setting anyone should be able to flip by accident — changing it is a deliberate
code edit, and the reason is in the docstring.

If it fails it stages the draft and records why, rather than reporting a URL it
did not create. A 401 is almost always the stripped spaces, or an account
without author rights.

---

## 1. Telegram via Make — fifteen minutes

Agent 3 writes channel copy every night and holds it, because no account
exists to send from. Telegram is the right first channel: text-only posts are
allowed, there is no Business-account conversion, no app review, and it is
where Iranian travel buying actually happens.

**In Telegram**

1. Talk to `@BotFather` → `/newbot` → name it → it gives you a bot token.
2. Create your channel, add the bot as an **administrator** with permission to
   post.

**In Make**

3. New scenario → trigger **Webhook → Custom webhook** → copy the URL.
4. Add module **Telegram Bot → Send a Text Message**, connect it with the bot
   token, set Chat ID to your channel (`@yourchannel`).
5. Map the message text to `post.copy.body` from the webhook payload, and
   append `post.copy.cta_url`.
6. Turn the scenario on.

**Then, in GitHub:**

| Secret / variable | Value |
|---|---|
| `SCHEDULER_BASE_URL` *(secret)* | the Make webhook URL |
| `SCHEDULER_BACKEND` *(variable)* | `webhook` |

**What Agent 3 will POST**, HMAC-signed with `WEBHOOK_SIGNING_SECRET`:

```json
{
  "architecture_credit": "Albaloo Studio",
  "campaign_id": "aroya",
  "correlation_id": "run_…",
  "post": {
    "channel": "telegram",
    "copy": { "body": "…", "hashtags": [], "cta_url": "…", "language": "fa-IR" },
    "scheduled_for": "2026-08-12T09:00:00Z"
  }
}
```

**It still will not post.** Two more locks remain, both deliberate:

- `ALLOW_AUTOPOST=1` in the workflow environment — currently commented out
- `autopost: true` on the telegram channel in `sites.yml` — currently `false`

Leave both closed for the first few nights. Read what Agent 3 writes in the
artifact. Open them when the copy is good enough that you would have sent it
yourself.

---

## 2. A lead source — twenty minutes

Agent 4 is complete and idle. It needs leads to arrive somewhere it can read.
Two ways, and the first is better.

### Either: an endpoint

`res.boutimar.ir` already receives leads through `ingest.php`. Add a read
endpoint that returns unprocessed leads as JSON:

```json
[{"channel":"whatsapp","from_ref":"wa-88","message":"…","locale":"fa-IR","utm_campaign":"aroya"}]
```

`{"leads": [...]}` works too. Then:

```bash
python3 agent4_sales_closer_batch.py --leads-url https://res.boutimar.ir/leads.php
```

The request is **HMAC-signed** with the same `WEBHOOK_SIGNING_SECRET` every
other hop uses, so the endpoint can verify it is the pipeline asking. Verify
it. An endpoint that hands out customer messages to anyone who finds the URL is
a data leak wearing an integration costume.

### Or: a Make scenario

Gmail/IMAP trigger → JSON aggregator → HTTP POST to a Gist or a repo file, then
`--leads path/to/file.jsonl`. Slower and clumsier, but it needs no PHP.

### Then add the schedule

Agent 4's workflow is **dispatch-only on purpose** — a nightly run with no
leads would report green every morning, which is how a green tick stops meaning
anything. Once leads genuinely arrive, add to `.github/workflows/agent4-sales-closer.yml`:

```yaml
on:
  schedule:
    - cron: "0 */4 * * *"     # every four hours
```

**Agent 4 cannot send.** There is no SMTP and no customer webhook anywhere in
the file, and `selfcheck` asserts that absence. Replies land in the artifact
for you to read, edit and send. That is not a limitation to be fixed later — a
wrong price or a wrong visa claim cannot be recalled from a real customer.

One thing to decide before you point it at real traffic: `_local-leads.jsonl`
holds real customer messages. It was tested against synthetic leads only,
because pushing real correspondence through a model is your call.

---

## What each one costs if you do nothing

- **No WordPress** — dmciran.ir stays at zero impressions with nothing new to index.
- **No Telegram** — channel copy written nightly, never seen.
- **No lead source** — Agent 4 idle, and every enquiry handled by hand.

Nothing breaks. The pipeline degrades cleanly at every edge — that is the whole
design. But the value is at the edges.

---

*Architecture by **Albaloo Studio** — albaloostudio.com. Owner: Alireza Mozaffari.*
