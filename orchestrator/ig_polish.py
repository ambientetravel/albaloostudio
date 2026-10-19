"""
Instagram caption polish for Agent 3: the instagram-agent skill's rules, applied in CI.

Architecture credit: Albaloo Studio. Rules and tools from Jake Schincariol's
MIT-licensed instagram-agent-skill (vendor/instagram_agent/), the same skill
Alireza runs on his Mac as /instagram-agent and /ig-*.

What it does to one Instagram draft:
  1. humanize the body: slop words, em dashes, invisible characters. English and
     other Latin-script captions ONLY; Persian keeps its U+200C, which the
     humanizer would delete.
  2. cap hashtags at five (Instagram's limit since Dec 2025), dropping the
     generic ones (#viral, #explorepage…) first
  3. lint the caption exactly as it would post: the ~125-character window before
     "… more", first line, tags below the fold, no dead links, one ask
  4. score how human it reads (Latin script only)

It never rewrites meaning and never blocks on its own. The receipt travels with
the post, so the reviewer sees FIX / REVIEW / READY before anything is
scheduled. Autopost stays off; nothing here posts.
"""
from __future__ import annotations

import importlib.util
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

VENDOR = Path(__file__).resolve().parent / "vendor" / "instagram_agent"
ARABIC_SCRIPT = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
HASHTAG_LIMIT = 5


@lru_cache(maxsize=None)
def _tool(name: str):
    spec = importlib.util.spec_from_file_location(f"_ig_{name}", VENDOR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, Any]:
    return _tool("humanize").load_lexicon(str(VENDOR / "slop.json"))


def is_persian(text: str) -> bool:
    return bool(ARABIC_SCRIPT.search(text or ""))


def cap_hashtags(tags: list[str]) -> tuple[list[str], list[str]]:
    """At most five, generic ones dropped first; returns (kept, dropped)."""
    filler = _tool("caption").FILLER_TAGS
    norm = [t if t.startswith("#") else f"#{t}" for t in (str(x).strip() for x in tags) if t.strip("#")]
    seen, uniq = set(), []
    for t in norm:
        if t.lower() not in seen:
            seen.add(t.lower())
            uniq.append(t)
    specific = [t for t in uniq if t.lower() not in filler]
    kept = specific[:HASHTAG_LIMIT]
    return kept, [t for t in uniq if t not in kept]


def polish(body: str, hashtags: list[str], keywords: list[str] | None = None) -> dict[str, Any]:
    """Polished body and tags plus the receipt. Pure: no I/O, no network."""
    persian = is_persian(body)
    changes: dict[str, Any] = {}
    if persian:
        clean = body.strip()
        changes["humanize"] = "skipped: Persian script (the humanizer deletes U+200C)"
    else:
        clean, report = _tool("humanize").humanize(body, _lexicon())
        clean = clean.strip()
        changes["humanize"] = {k: v for k, v in report.items() if v}
    kept, dropped = cap_hashtags(hashtags)
    if dropped:
        changes["hashtags_dropped"] = dropped

    caption = clean + ("\n\n" + " ".join(kept) if kept else "")
    lint = _tool("caption").analyse(caption, keywords=[k for k in (keywords or []) if k])
    receipt: dict[str, Any] = {
        "verdict": lint["verdict"],
        "visible": lint["visible"],
        "fails": [f"{c['check']}: {c['detail']}" for c in lint["checks"] if c["status"] == "FAIL"],
        "warns": [f"{c['check']}: {c['detail']}" for c in lint["checks"] if c["status"] == "WARN"],
        "changes": changes,
        "source": "instagram-agent-skill (MIT) via orchestrator/ig_polish.py",
    }
    if persian:
        receipt["human_score"] = None
        receipt["human_note"] = "not computed: the detector is tuned for English"
    else:
        _, overall, verdict = _tool("detect").run(clean, _lexicon())
        receipt["human_score"] = round(overall)
        receipt["human_verdict"] = verdict
    return {"body": clean, "hashtags": kept, "receipt": receipt}


def polish_drafts(drafts: list[dict[str, Any]], keywords: list[str] | None = None) -> None:
    """In place: every Instagram draft gets the polished body/tags and an
    `ig_lint` receipt. Other channels are untouched."""
    for d in drafts:
        if d.get("channel") != "instagram":
            continue
        out = polish(str(d.get("body") or ""), list(d.get("hashtags") or []), keywords)
        d["body"], d["hashtags"], d["ig_lint"] = out["body"], out["hashtags"], out["receipt"]
