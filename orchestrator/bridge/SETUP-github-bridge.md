# GitHub as the bridge — Claude · GPT · Gemini

The interchange between the models is a **pull request**. Any model that can open
one — Codex/GPT, Jules/Gemini, Claude — contributes the same way, and every PR is
read against the house rules before a human merges it. Claude is the reviewer;
nobody merges but you.

```
   Codex / GPT ─┐
   Jules / Gemini ─┼──►  PR on a property repo  ──►  PR gate (compliance.check)  ──►  YOU merge
   Claude ───────┘         (the bridge)               ✓ PASS  ▲ WARN  ✗ BLOCK
```

## What is already built (this commit)

- **GPT is a full worker.** `llm.py` now has an `_openai` provider, so
  `PROSE_PROVIDER=openai` makes GPT draft (Agent 2) and compose social copy
  (Agent 3), not just analyse gaps. `tools/ai_visibility.py` gained an OpenAI
  probe, so Agent 9 can also ask ChatGPT what it recommends.
- **The PR gate.** `tools/pr_review.py` runs `compliance.check` over any PR's
  added lines — «خلیج فارس» / no-visa / invented-fact / brand-separation — and
  returns PASS / WARN / BLOCK. Verified live: the open article PR passes; an
  "Arabian Gulf" + false "Dubai visa-free" diff is BLOCKed.
      python3 tools/pr_review.py --repo ambientetravel/boutimar --pr 6
      python3 tools/pr_review.py --all        # every open PR, git-backed sites
- **The gate runs itself.** `.github/workflows/pr-gate.yml` reviews every open PR
  across the git-backed repos every 6h and writes the verdict to the run summary.
  Posting the verdict as a PR comment is opt-in (`post=true`), off by default.
- **The OpenAI key flows.** `OPENAI_API_KEY` is now passed by the Agent 1/2/3 and
  ai-visibility workflows; absent, every path falls back cleanly.
- **The manifest lane already takes GPT** — `source:"openai-strategy"` validates,
  with a template and prompt in this folder.

## The game is now on the lane too (5 Sep)

*Persia at War* lives in `ambientetravel/albaloostudio` under `persia-wars-game/`,
so that repo is now in `REPOS` — and because it holds the orchestrator **and** the
game, the profile is chosen **per path**, not per repo.

- `persia-wars-game/**` → **`persia_at_war_v1`**
- everything else in that repo → `boutimar_v1`

That distinction is the point rather than tidiness. The game sells no holiday, so
the visa and sanctions rules would produce only noise; and the rule that actually
matters for it — **it never invents a date, an outcome, a unit or a king** — has
no analogue on the website side. Judged under the travel profile, a PR that
invented a Persian heroine would pass clean, and that is the one failure this
product cannot survive.

`fabricated_history` BLOCKs the claims a general model reliably produces in good
faith: **Pantea Arteshbod** commanding the Immortals, **Apranik** resisting the
Arab conquest, **Youtab** at the Persian Gate, the **Cyrus Cylinder as a charter
of human rights**, **Artemisia called Persian** (she was Carian Greek, a vassal),
and **Rostam Farrokhzad conflated with Rostam son of Zal** — two different men,
and the most common error in this whole subject. Each violation returns the
reason, not just a refusal, because the refusal has to survive being argued with
in six months.

Verified: a clean paragraph about Zarina passes; a paragraph containing all five
fabrications returns six BLOCKs.

## Connecting ASTRA specifically

ASTRA is a worker on this lane like Codex or Jules, and needs nothing new built:

1. Give it **repo/PR access to `ambientetravel/albaloostudio`** — and only that.
   Never admin, never merge, never write-to-default.
2. Point it at `orchestrator/bridge/ASTRA-PROMPT.md` and the seed.
3. It opens a PR. The gate reads it within 6h, or on demand:

       python3 tools/pr_review.py --repo ambientetravel/albaloostudio --pr <n>

4. **You merge, or nobody does.**

The seed still matters even with a live PR lane: a model that can open a PR can
open a redundant one just as easily, and the first run of that seed caught its
own author proposing an arena that was already finished.

## What only you can do (the clicks)

1. **Add secrets** to the `ambientetravel/albaloostudio` repo → Settings → Secrets:
   - `OPENAI_API_KEY` — your OpenAI key. Lights up GPT everywhere above.
   - `BRIDGE_GH_TOKEN` — a fine-grained PAT with **contents:read** on the three
     property repos (`boutimar`, `boutimarfarsi`, `exploreorient`), so the PR gate
     can read PRs in repos other than albaloostudio. Add **issues:write** only if
     you'll run the gate with `post=true`.
2. **Connect the coding agents to the property repos** (so GPT/Gemini can open PRs):
   - **Codex** (GPT): chatgpt.com → Codex → connect GitHub → grant
     `ambientetravel/boutimar` and `ambientetravel/exploreorient`.
   - **Jules** (Gemini): jules.google → connect the same repos.
   Give each **repo/PR access only** — never admin, never "allow merge".
3. **Fix the `boutimarfarsi` push token** so boutimar.ir joins the PR lane (it's
   been blocked on the PAT).

## Correction, 5 Sep — the ChatGPT GitHub PLUGIN is not the lane

Checked on the live account and the instruction above ("connect GitHub in
ChatGPT") is not sufficient. Two different things carry similar names:

| | what it is | can it open a PR? |
|---|---|---|
| **ChatGPT GitHub plugin** | already connected as `contactmozaffari@gmail.com`, permission level **"Allow low-risk actions (DEFAULT)"** — Check repo initialized, Compare commits, Download git tree archive | **No. Read only.** |
| **ChatGPT Codex Connector** | listed under **Authorized** GitHub Apps, NOT under Installed | this is the one that writes |

**Authorized is not installed, and the difference decides everything here.** A
per-repository selector — "Only select repositories" — exists only for a GitHub
App *installation*. An OAuth authorisation is account-scoped by construction, so
there is no repo picker to find and no way to fence it to one repo from GitHub's
side. Any narrowing has to happen in Codex's own repo selection instead.

**Two things not to do:**

- **Do not click Reconnect on the plugin.** GitHub skips the consent screen when
  re-authorising an app that already holds a grant, so it completes silently —
  there is no button left to decline.
- **Do not raise the plugin above "low-risk actions".** That setting is
  account-wide, not per-repository, so it would grant write across every repo on
  the account. That is precisely the exposure the repo split was done to avoid,
  and trading it away at the last step would undo the whole exercise.

`ambientetravel` is a **personal account, not an organisation**, which is why
`persia-at-war` sits directly under it.

### DONE, 5 Sep — Codex is installed and scoped to one repo

`ChatGPT Codex Connector` → **Only select repositories** → `ambientetravel/persia-at-war`,
verified after a full reload.

**The route, for when this is done again:** the workspace is
`chatgpt.com/codex/cloud` — `/codex` is a marketing page with no account state at
all — and the per-repo selector sits behind **"Configure Repositories on GitHub"**
in the repository dropdown. That link opens a real GitHub App **installation**
page, which is exactly why it is the safe route: an installation always shows the
repository selector and the permission list, where Reconnect on an existing OAuth
grant completes silently with nothing to decline.

**Two things GitHub will not let you narrow:**

- **`workflows` write cannot be unticked.** It is bundled with code, issues,
  actions and pull requests on one line. Write to `.github/workflows` is the
  ability to run code in your Actions runners with that repo's secrets, so
  **repository scope is the only lever there is** — the argument for the game
  having its own repo, made concrete.
- **"Only select repositories" still includes public repositories, read-only**,
  per GitHub's own wording on the option.

**The radio defaults to "All repositories" and is pre-selected.** It was installed
on that default and narrowed a few minutes later. Nothing could have used it —
Codex had no environments and no repositories selected, so there was no task to
run — but the lesson is that the radio must be changed BEFORE the green button.

## Still open: which account this lives on

`persia-at-war` sits on the `ambientetravel` account beside the travel properties.
Private, so nothing is publicly associated today. But the game is explicitly **not**
a Boutimar or Ambiente product, and the moment that repo goes public — or the game
ships from it — the owner is visible and the association is made for you.

Moving a repo between accounts keeps its history and takes a few clicks. **Same
deadline as the name: before anything is public.**

## The boundary that keeps it safe

An external agent **opens a PR and nothing more**. No merge, no push to `main`, no
deploy, no outbound email. The gate reads and reports; you merge. More brains
proposing is only safe because one brain reviews and one person ships. Do not grant
any connected agent merge or write-to-default rights — that removes the gate and
the guarantee with it.

## Not bridgeable this way

`cruisebaz.com` and `ambientetravel.com` are base44 (no git), so they cannot take a
PR from any model. Their only bridge is base44's own inbox/API. Everything else in
the portfolio is git-backed and bridgeable.
