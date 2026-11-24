# base44 credit queue: Albaloo Ops (app 6ade14ab5b5e6721cc424fbe)

Written 24 Nov 2026. This month's base44 credits expire at the end of the month. Below is
what is **not built yet**, in the order it should be spent. A live probe of the app on
24 Nov (ops-sync `mode=probe`) gave the "built?" column.

| # | Prompt | Built? | Why it's next |
|---|---|---|---|
| 1 | `orchestrator/OPS-APP-PARTNER-PROMPT.md` | **No.** The `Partner` entity returns 404. | The embed is live on cruise24.me (HTTP 200, embedding allowed) and `Lead.partner_id` exists, but agencies have no login to see their leads. |
| 2 | Quote branding (below) | **No.** The task is still open. | The quote PDF says "AMBTC HQ", a name base44 invented. It must be fixed before any quote reaches a customer. |
| – | `OPS-APP-TRIAGE-PROMPT.md` | Yes (`priority_score` and `priority_reason` exist) | skip |
| – | `OPS-APP-NOTIFY-PROMPT.md` | Yes (`Notification` exists) | skip |

## How a Mac session runs this queue

Only a session running **on Alireza's Mac** can do this. It needs Chrome with the Claude
in Chrome extension and his base44 login. A cloud session can't reach any of these. Never
use a game session (Persia at War, PAW1, Karvansara).

For each prompt in order:

1. Open `https://app.base44.com/apps/6ade14ab5b5e6721cc424fbe` and go to the AI chat. Find
   the box by its placeholder ("What do you want to change?"), not by its position on the
   page. Paste the prompt text and send it.
   - For #1, paste everything between the first two `---` lines of the file.
   - For #2, paste the block below.
2. Wait until base44 finishes. If it asks a question, answer it from the prompt's own
   wording. Never let it invent a rate, a price, a date, a company name or a commission.
3. Press **Publish** (the last Publish button in the panel). Open
   https://albaloo-ops-core.base44.app and confirm the new screen is there.
4. Copy base44's summary of what it built. When the queue is done, send all the summaries
   to the "24-hour project strategy" session. It then runs the probe and the live checks
   from GitHub.

---

### #2 Quote branding (paste this block)

Fix the branding on quotes and on the quote PDF. Change nothing else.

1. Remove the text "AMBTC HQ" everywhere it appears: the PDF header, the footer, the
   quote screen and the e-mail templates. That name is not ours.
2. Take the brand shown on a quote from the Site record that matches the quote's lead
   property: show Site.brand and Site.domain. If the property is empty or has no Site
   record, show no brand line at all. Never fall back to a made-up name.
3. Add one owner-only setting, "Legal name on quotes" (text, empty by default). If it's
   set, print it in small type in the PDF footer. If it's empty, print nothing there.
   Don't prefill it.
4. Don't add a logo image unless one is uploaded through that same settings screen.
   There's no default logo.
5. Prices, dates and inclusions on a quote come only from the Quote and Rate records.
   If a value is missing, the PDF shows "to be confirmed". Never show an estimate.
