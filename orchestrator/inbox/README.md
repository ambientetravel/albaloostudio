# inbox/ — where the base44 Superagent drops work

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

## What this is

A one-way drop point. The base44 Superagent commits findings here; this repo's
tooling and whoever is working in it read them. Nothing in this repo calls
base44, and base44 never receives a webhook.

That direction is the entire design. Agent 2 was specified as a base44 service
receiving signed webhooks and it failed in production for three reasons — six
of ten sites needed git or filesystem writes it did not have, the raw-body HMAC
is hostile to a platform that pre-parses JSON, and drafting takes 30–90s which
is not a request handler's work. A missing `AGENT2_WEBHOOK_URL` then killed the
nightly cron on 9 Aug 2026.

Producing INTO git has none of those properties. There is no signature to
verify, no request to time out, and git is the one write base44 genuinely has
via its GitHub connector.

## The contract

One JSON file per job, named `<job>-<YYYY-MM-DD>.json`, plus a `.md` beside it
if the agent wants to write prose. Every file MUST carry:

```json
{
  "job": "competitor-browse",
  "agent": "base44-superagent",
  "generated_at": "2026-08-26T00:00:00Z",
  "sources_read": ["https://…", "https://…"],
  "could_not_read": [{"url": "https://…", "reason": "403 to automated fetch"}],
  "findings": []
}
```

### Quotes and judgements are different things — keep them apart

The first job here proved the split. Its verbatim quotes were accurate and
independently confirmed; its *assessment* of what they meant was wrong. It read
«نرخ بدون ویزا 950 دلار» sitting beside a higher price of $1070 as a competitor
falsely advertising a visa-free trip, when it is a price line meaning "rate
excluding visa" — and the higher tier is the one bundling the UAE visa service,
which supports that reading rather than contradicting it.

That is not a failure. Browsing and quoting is what this agent is for; judging
Persian pricing idiom against a visa rule is not. So the contract separates them:

* **`*_verbatim` fields are findings.** Quote exactly, name the URL each quote
  came from, and never paraphrase a claim into something stronger.
* **`*_assessment` fields are HYPOTHESES and must say so.** Every assessment
  carries `"status": "unverified"` until a human or a second pass confirms it.
  Nothing downstream may act on an unverified assessment, and no assessment may
  be published, quoted publicly, or used to make a claim about a competitor.

An accusation that a named company is misleading customers is the highest-cost
thing that can be written here. It gets confirmed against the live page before
it is called a finding, or it does not get called one.

`sources_read` and `could_not_read` are not optional. A finding whose source
cannot be named is not a finding, and a site the agent failed to reach must be
declared rather than silently missing — the whole portfolio's tooling already
distinguishes "measured zero" from "could not measure", and anything landing
here has to honour that too.

## Rules for anything written here

1. **Never invent a rate, a departure date, an inclusion or a photo credit.**
   If the data is not there, say it is not there.
2. **«خلیج فارس», never «خلیج عربی».**
3. Visa accuracy: only AROYA's Türkiye+Egypt routes and Seychelles are truly
   visa-free; Persian Gulf and Dubai are EASY VISA, never no-visa; any Greek,
   Italian, Spanish or French port makes a sailing Schengen.
4. Quote what a competitor actually published. Do not paraphrase a claim into
   something stronger than the source.

## What does NOT belong here

Keyword harvesting. `tools/suggest_harvest.py` already does it against Google's
suggest endpoint for free, with no account and no daily cap, and it recovered
64% of a paid keywordchi export plus 83 terms that export did not have. Paying
credits for that would be paying for a worse version of something free.
