# Provider matrix — which model does which job, and whose credits pay

The pipeline treats the model as a **setting, not a call site**. Each job reads a
provider knob; swap the knob and the same code runs on a different brain. This is
the map: what's wired today, what a job costs, and where your Gemini / OpenAI
credits actually come into use.

**One rule underneath all of it:** Claude (this orchestration session) is always
the reviewer. Gemini and GPT *propose* — draft, analyse, suggest strategy. Nothing
they produce ships without passing the compliance gate and your merge. Adding a
brain adds proposals, never autonomy.

## The matrix

| Job | Knob | Default today | GPT usable? | Whose credits | Fallback |
|-----|------|---------------|-------------|---------------|----------|
| **Agent 1 · Scout** — gap analysis | `GAP_ANALYSIS_PROVIDER` + `GAP_ANALYSIS_FALLBACK` | `gemini → gemini` | ✅ **today** — set `=openai` | Gemini / Anthropic / **OpenAI** | deterministic builder (no model) |
| **Agent 2 · Writer** — drafting | `PROSE_PROVIDER` (via `llm.py`) | `gemini → anthropic` | ⚠️ needs `_openai` in `llm.py` | Gemini / Anthropic | skip the brief |
| **Agent 3 · Broadcaster** — social copy | `PROSE_PROVIDER` (via `llm.py`) | `gemini → anthropic` | ⚠️ same one addition | Gemini / Anthropic | hold the post |
| **Agent 9 · Oracle** — AI-visibility probe | `--provider` | `anthropic` | ⚠️ add `_ask_openai` — and GPT is a probe *target* you want anyway | Anthropic / Gemini | — |
| **Bridge** — strategy proposals | manifest `source` | `gemini-strategy` live | ✅ **today** — `source:"openai-strategy"` already validates | your ChatGPT (external) | Claude review |
| **PR lane** — code/content on a repo | external agent | Claude / Gemini | ✅ **today** — Codex opens PRs | your ChatGPT (external) | Claude review + your merge |
| **Review / routing / gate** | — | **always Claude** | — | Anthropic | — |

Model defaults: `OPENAI_MODEL=gpt-4.1` · `GEMINI_MODEL=gemini-2.5-flash` ·
`ANTHROPIC_MODEL=claude-opus-5` (Scout) · `PROSE_MODEL=claude-sonnet-5` (Writer).
Order-of-magnitude cost: a full drafting cycle ran **$0.05** on Claude Sonnet;
gap analysis and social copy are in the same cents range. This is a
pennies-per-cycle system — the credit question is which balance you'd rather spend
from, not whether you can afford it.

## Three ways your GPT / Gemini credits come into use

**A. As pipeline providers (inside the machine).** Add the key as a repo secret and
flip a knob:
- `GAP_ANALYSIS_PROVIDER=openai` → GPT finds the gaps. **Works today.**
- `PROSE_PROVIDER=gemini` → Gemini drafts (funded fallback already live).
- Keep review on Claude. So: *GPT scouts, Gemini writes, Claude judges* — three
  balances, one pipeline.

**B. As a bridge strategist (outside the machine, no code).** Paste the inventory
seed + the OpenAI manifest template into ChatGPT; it returns a `bridge.v1` manifest;
Claude reviews and routes it. This is the cheapest way to use ChatGPT credits —
it's just you and ChatGPT, and the review gate catches anything wrong. **Works today.**

**C. As a PR author (Codex on a repo).** Connect Codex to `ambientetravel/boutimar`
or `exploreorient`; GPT opens content/schema PRs; Claude reviews; the owning session
merges. **Works today** for the three git-backed properties (see the bridgeability
table). base44 sites (cruisebaz, ambientetravel) can't take this lane.

## To make GPT a first-class *worker* (not just a scout)

One self-contained change: add an `_openai(...)` function to `llm.py` and register
it in `_PROVIDERS` (mirroring the OpenAI structured-output call Agent 1 already
carries in `_analyse_with_openai`). That single addition turns on GPT for **Agent 2
drafting and Agent 3 broadcasting** via `PROSE_PROVIDER=openai`. Optionally add
`_ask_openai` to `tools/ai_visibility.py` so Agent 9 also *probes* ChatGPT — worth
it because ChatGPT is one of the engines you're trying to get cited in.

Neither runs without `OPENAI_API_KEY`; both fall back gracefully when the key is
absent, so the code is safe to land before the key exists.

## Recommended assignment (for your credits)

| Balance | Best lane | Why |
|---------|-----------|-----|
| **ChatGPT credits** | Bridge strategist (B) + Codex PRs (C) | External, zero pipeline cost, reviewed by Claude — lowest risk, uses credits you already have |
| **Gemini credits** | Pipeline drafting (`PROSE_PROVIDER=gemini`) | Already wired and funded; cheapest per-word drafting |
| **Anthropic credits** | Review + gap analysis + fallback | Claude is the gate; keep the judgment on the funded, trusted brain |

Do not give any external agent merge, push-to-`main`, deploy, or outbound-email
rights. Propose-only, through the gate. That boundary is the whole safety model.
