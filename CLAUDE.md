# Project Guidelines

## Autonomy — read this first

**Finish the task. Do not stop to ask for permission, approval, or a go-ahead.**

Alireza has said this repeatedly and it is the standing rule for this repo. The
earlier version of this file said "get section-by-section approval — no code
until design is approved", which is a large part of why it kept happening. That
rule is deleted, not softened.

Concretely:

- **Never end a turn with "want me to…?", "shall I…?", "should I go ahead?"**
  If the next step is obvious, it is already part of the task — do it.
- **Take the task to the end**, including the tedious parts: build it, verify it
  live, package it, and report what was actually observed.
- **Make routine judgment calls yourself.** When two options are reasonable, pick
  the better one, do it, and say in one line what was picked and why. Do not
  present a menu.
- **State assumptions instead of asking.** "I assumed X because Y" is a finished
  task; "Do you want X or Y?" is an unfinished one.
- If something is genuinely blocked (a credential, a file only he can produce, a
  third-party outage), do **everything else first**, then say plainly what is
  blocked and what is needed.

**The only things to stop for**, because they are hard to undo or they reach
people outside the company:

- Sending real email to customers, agents or third parties. Test sends to his own
  address are pre-authorised — he has confirmed this more than once.
- Deleting or overwriting data with no backup
- Spending money, or anything touching payments
- Publishing something public under the company name that cannot be quietly pulled

Everything else — writing code, rebuilding pages, restructuring data, running
audits, packaging deploy bundles, running live read-only checks — just do.

Deployment is a hand-off, not a question: build the bundle **and** write the
DirectAdmin prompt in the same turn.

## How he wants work reported

- Lead with what changed and what broke. Not with process.
- Give numbers he can check — file sizes, row counts, status codes, before/after.
- If something is still wrong, say it first and plainly. Never bury it.
- Corrections are one sentence. No re-litigating, no apologising twice.

## Session routing — per-property handoff

Each property has ONE session that owns it. Work on that property is **handed
off** to its session rather than done wherever it was asked for, so one session
keeps the whole history of one site.

The registry is `.claude/session-routing.json`. Before handing off:

- **Match by title, not by id.** Ids are stable for a session's life, but a new
  session for the same property gets a new id and a hardcoded one goes stale
  silently. Use `mcp__ccd_session_mgmt__list_sessions`, find the title, use the
  id it reports, and update the registry when it has moved.
- **The target does not need to be running.** `send_message` delivers into a
  stopped session's transcript as a user turn, waiting for its next open.
- **`ListAgents` will not show a stopped session** — it lists live peers only.
  Do not conclude from an empty `ListAgents` that a session does not exist;
  check `list_sessions` before saying so.
- A route marked `confirmed_by_user: false` was inferred from a title. Ask
  before the first handoff to it.
- Properties in `unrouted` have no owner. Ask, do not guess.

Hand off the finished work — commit sha, what changed, what is deliberately not
done — not a request for the other session to go and do the task.

## Hard rules that override everything

- **«خلیج فارس» / Persian Gulf. Never "Arabian Gulf".** Every page, card, email,
  document, and any relabelled source data. ("Arabian Sea" is a different body of
  water — leave that alone.)
- **Visa accuracy.** Only AROYA's Türkiye+Egypt routes and Seychelles are truly
  visa-free. Persian Gulf and Dubai are *easy visa*, not no-visa. Any Greek,
  Italian, Spanish or French port makes it Schengen — even sailing from Istanbul.
- **Never invent a rate, a departure date, an inclusion, or a photo credit.** If
  the data is not there, say it is not there.
- The **embed widget stays brand-neutral** — no «بوتیمار», no links to
  boutimar.ir. It runs inside partner agency sites.
- The CruiseHost contract belongs to **Ambiente Tours**, not Boutimar. No company
  name in outbound API headers.

## Verification

Verify before reporting done — live, not locally assumed.

**Test every branch a change touches**, not just the convenient one: a `?e=` bug
shipped in August because only the `?id=` path was re-tested after a shared edit
broke both.

**Never infer "shipped" from "edited".** Diff the file against the live server.
`sitemap.xml` was edited and then missed out of four consecutive deploy bundles —
every deploy verified the files that WERE in the zip and nobody checked whether an
edited file had made it in.

## Available workflow skills

TDD, systematic debugging, code review and git worktrees are available and worth
using when they fit. They are tools, not gates — none of them require approval
before starting. Reference: https://github.com/obra/superpowers/tree/main/skills/
