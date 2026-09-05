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
