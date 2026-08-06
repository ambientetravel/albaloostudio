# What to connect where

Architecture credit: **Albaloo Studio** — [albaloostudio.com](https://albaloostudio.com)
Owner: Alireza Mozaffari

`mozzafiatojourney` is a personal hobby page. It is **not** wired to any brand in
`sites.yml` and it should stay that way — auto-generated Boutimar cruise copy
landing on a private account is the kind of mistake that is embarrassing rather
than recoverable. `selfcheck.py` now asserts no brand channel carries that
account ID, so a future edit can't quietly reintroduce it.

Every `account_ref` in `sites.yml` is `null` today. Agent 3 composes copy for
every channel regardless and holds it in the file queue; it simply cannot reach
a platform it has no account for.

---

## Start with one Telegram channel

If you do exactly one thing, do this: create **@boutimar** on Telegram, connect
it, paste the ID into `sites.yml`. That single step takes the pipeline from
"composes into a folder" to "delivers", because Telegram is the only channel
with no blockers at all:

| | Telegram | Instagram | LinkedIn |
|---|---|---|---|
| Accepts text-only posts | ✅ | ❌ **needs an image** | ✅ |
| Needs a Business-account conversion | ✅ no | ❌ Business + FB Page | ❌ Company Page |
| Meta / US-sanctions exposure | ✅ none | ❌ real (below) | ❌ real |
| Where Iranian travel buying happens | ✅ **yes** | partly | no |

Instagram is blocked on the imagery problem regardless of which account you
connect — Agent 2 emits `hero_image: null` whenever it has no credited, licensed
image, and Instagram rejects text-only posts. That is one problem, not two, and
connecting an account does not solve it.

---

## The map

| Domain | Brand | Channels | Notes |
|---|---|---|---|
| `boutimar.ir` | Boutimar fa | **Telegram**, Instagram | Telegram first — the Iran D2C workhorse |
| `boutimar.com` | Boutimar EN | Instagram, LinkedIn | Separate EN Instagram, or reuse with English copy |
| `cruisebaz.com` | CruiseBaz | **Telegram**, Instagram | Same shape as boutimar.ir |
| `ambientetravel.com` | Ambiente Travel | LinkedIn | B2B DACH — LinkedIn is the whole channel |
| `exploreorient.com` | Explore Orient | LinkedIn | Instagram later, once imagery is solved (Venue Atlas is visual) |
| `dmciran.ir` | DMC Iran | LinkedIn | Inbound B2B |
| `cruise24.ir`, `cruiseshop.ir` | — | none | Parked. The scout still gathers demand data for them. |

That is **3 Telegram channels, 3 LinkedIn Company Pages, and 2–3 Instagram
business accounts** at full build-out. None of it has to happen at once.

---

## Two things worth deciding before you register anything

### 1. Which legal entity owns the Meta and LinkedIn assets

This is the one with real downside. Meta and LinkedIn both restrict business
accounts tied to Iranian entities, and enforcement is account termination without
warning — you lose the page, the follower base, and the ad history together.

The existing guardrail in this repo already points the way: payment rails are EU
only, and the CruiseHost contract sits with **Ambiente Tours GmbH** rather than
Boutimar. Register the Meta Business Manager and the LinkedIn Company Pages under
the **German entity**, and treat the `.ir` domains as content the EU entity
markets, not as the registrant.

Telegram has no such exposure, which is a second reason it is the right first
move for the Iran brands.

### 2. Instagram needs a Business account, not a personal one

A personal Instagram account cannot be published to by any API — Meta only
exposes publishing on **Business or Creator** accounts linked to a Facebook Page.
So each brand Instagram needs: convert to Business → create/link a Facebook Page
→ connect. Three steps per account, and the Page is the part people forget.

---

## Connecting an account

Each connection is an OAuth redirect:

```bash
curl -X GET "https://zernio.com/api/v1/connect/telegram?redirect_url=https://albaloostudio.com/ok" \
  -H "Authorization: Bearer $SCHEDULER_API_KEY"
```

Open the `authUrl` it returns, authorise, then list what you have:

```bash
curl -s https://zernio.com/api/v1/accounts -H "Authorization: Bearer $SCHEDULER_API_KEY"
```

Paste each ID into the matching `channels[].account_ref` in `sites.yml`. Nothing
posts yet — `autopost` is still `false` and `ALLOW_AUTOPOST` is still unset, so
Agent 3 pushes drafts into the dashboard for you to release.

Supported platforms, for reference: `twitter` `instagram` `facebook` `linkedin`
`tiktok` `youtube` `pinterest` `reddit` `bluesky` `threads` `googlebusiness`
`telegram` `snapchat`.

---

## A bonus worth knowing about for Agent 4

The same scheduler exposes a **conversations API** covering Instagram, Facebook,
Telegram, X, Bluesky and Reddit DMs — and on Meta accounts it replays up to 500
conversations of history from before the account was connected.

Agent 4 currently expects a bridge to POST leads at `/leads/inbound`. This is
that bridge, already built: poll conversations, forward new messages, and
Instagram and Telegram DMs are covered without writing a WhatsApp integration.
WhatsApp is not on the list, so that one still needs its own path.

---

*Architecture by **Albaloo Studio** — albaloostudio.com. Owner: Alireza Mozaffari.*
