#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Do the AI assistants mention us? — generative-engine visibility (GEO).

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHY THIS EXISTS — the one gap the SearchFit skills exposed
──────────────────────────────────────────────────────────
The eight agents already cover most of what those skills describe:
  seo-auditor / technical-seo / on-page-seo / seo-check  → Agent 5
  competitor-analyzer                                    → Agent 8
  content-strategist / content-brief / create-topic      → Agents 1 & 6
  create-content                                         → Agent 2
  keyword-cluster                                        → Agent 6
Nothing new to adopt there; building a second one would duplicate a working one.

The exception is AI-VISIBILITY. Every existing agent measures GOOGLE — Search
Console rows, sitemap coverage, country distribution. Not one measures whether
an AI assistant, asked a buying question, names the property at all. That is a
different search surface and a growing one, and the pipeline was blind to it.
This tool closes that gap.

Note on the acronym: Agent 7 is called the "Geo" scout but means GEOGRAPHY
(which country the impressions come from). The SearchFit skill's "GEO" means
Generative Engine Optimization (do LLMs recommend you). Same three letters,
different question. This tool answers the second.

WHAT IT HONESTLY MEASURES, AND WHAT IT DOES NOT
───────────────────────────────────────────────
It asks a model a buying question — "best Iran DMC", «تور کشتی کروز از کیست» —
with NO web access, and reads whether the brand surfaces. That measures the
model's TRAINING RECALL: what it has absorbed about the brand from the web up
to its cutoff. It is a real, improvable signal — it is how a plain ChatGPT/Claude
answer is formed when the user has browsing off.

It is NOT the same as a live-retrieval answer (Perplexity, ChatGPT with search),
which reads the web at query time. That surface is not measured here and is
called out as unmeasured rather than silently conflated. Running two providers
gives the "consistency" dimension the skill asks for; it does not turn training
recall into live retrieval.

Nothing is invented: the score is computed from the models' actual answers, and
each answer is kept so a claim can be checked against what was really said.

    python3 tools/ai_visibility.py                  # all configured properties
    python3 tools/ai_visibility.py --domain boutimar.com --provider anthropic
    python3 tools/ai_visibility.py --format json --out reports/ai-visibility.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

# ── Probe set ────────────────────────────────────────────────────────────────
# Buying/discovery prompts a real person would type, drawn from the actual
# keyword corpus, with the brand name and the rivals we already identified.
# aliases: every spelling a mention could take, so a hit is not missed on a
# transliteration ("Boutimar" / «بوتیمار»).
PROBES: list[dict[str, Any]] = [
    {
        "domain": "boutimar.com", "brand": "Boutimar",
        "aliases": ["boutimar", "بوتیمار"],
        "prompts": [
            "Who are the best DMCs (destination management companies) in Iran?",
            "Recommend a luxury tour operator for MICE events in Iran.",
            "I want a high-end cultural tour of Persia — which agency should I use?",
        ],
        "rivals": ["Uppersia", "SURFIRAN", "Iran Doostan", "Pars Tourist", "Key2Persia"],
    },
    {
        "domain": "boutimar.ir", "brand": "بوتیمار (Boutimar)",
        "aliases": ["boutimar", "بوتیمار"],
        "prompts": [
            "بهترین آژانس برای تور کشتی کروز از ایران کدام است؟",
            "می‌خواهم تور کشتی کروز خلیج فارس رزرو کنم، از چه شرکتی بخرم؟",
            "نمایندهٔ رسمی خطوط کروز جهانی در ایران کیست؟",
        ],
        "rivals": ["ایوار", "نیلفام", "الی گشت", "طاها گشت", "علی بابا"],
    },
    {
        "domain": "cruisebaz.com", "brand": "CruiseBaz",
        "aliases": ["cruisebaz", "cruise baz", "کروزباز"],
        "prompts": [
            "As an Iranian living abroad, which agency books Persian-friendly cruises?",
            "Where can Iranians with a second passport book Royal Caribbean or MSC cruises?",
        ],
        "rivals": ["Cruise.com", "CruiseDirect", "Expedia Cruises"],
    },
    {
        "domain": "ambientetravel.com", "brand": "Ambiente Tours",
        "aliases": ["ambiente tours", "ambiente travel", "ambientetravel", "ambiente"],
        "prompts": [
            "Recommend a European-based DMC for MICE and incentive travel to Turkey and the Middle East.",
            "Which agency handles conference and event travel into Istanbul for European corporates?",
            "I need a destination management company for a corporate group trip to Turkey — who?",
        ],
        "rivals": ["ODS Istanbul", "MICE Turkey", "Meptur", "Intours", "Setur"],
    },
    {
        "domain": "exploreorient.com", "brand": "Explore Orient",
        "aliases": ["explore orient", "exploreorient"],
        "prompts": [
            "Recommend a sustainable, carbon-conscious tour operator for Turkey and the eastern Mediterranean.",
            "Which European agency runs curated cultural tours of the Orient with venue and carbon reporting?",
        ],
        "rivals": ["Intrepid Travel", "Responsible Travel", "G Adventures", "Exodus"],
    },
    {
        "domain": "cruise24.me", "brand": "Cruise24",
        "aliases": ["cruise24", "cruise 24", "cruise24.me"],
        "prompts": [
            "What is a good website to search and compare cruise deals online?",
            "Recommend an online platform for booking cruise packages.",
        ],
        "rivals": ["Cruise.com", "CruiseDirect", "Expedia Cruises", "Cruise Critic", "Dreamlines"],
    },
    {
        "domain": "albaloostudio.com", "brand": "Albaloo Studio",
        "aliases": ["albaloo studio", "albaloostudio", "albaloo"],
        "prompts": [
            "Recommend an agency that does AI-search visibility and generative engine optimization (GEO).",
            "Who builds automated SEO and content pipelines for multi-brand travel companies?",
        ],
        "rivals": ["Profound", "Otterly.ai", "Peec AI", "Scrunch AI"],
    },
    {
        "domain": "cruise24.ir", "brand": "کروز۲۴ (Cruise24)",
        "aliases": ["cruise24", "cruise 24", "کروز۲۴", "کروز 24"],
        "prompts": [
            "سایت رزرو آنلاین کشتی کروز برای ایرانیان کدام است؟",
            "بهترین پلتفرم جستجوی تور کشتی کروز در ایران چیست؟",
        ],
        "rivals": ["ایوار", "علی بابا", "فلای تودی"],
    },
]

_SENTIMENT_NEG = ("scam", "avoid", "not recommend", "کلاهبرداری", "توصیه نمی")


def _norm(s: str) -> str:
    s = s.lower()
    for a, b in {"ي": "ی", "ك": "ک"}.items():
        s = s.replace(a, b)
    return s


def _ask_anthropic(prompt: str, model: str) -> str:
    from anthropic import Anthropic
    c = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    r = c.messages.create(
        model=model, max_tokens=900,
        system=("You are a helpful assistant answering a user's question as you "
                "normally would. Name specific companies where relevant."),
        messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()


def _ask_openai(prompt: str, model: str) -> str:
    from openai import OpenAI
    c = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    r = c.chat.completions.create(
        model=model, max_tokens=900,
        messages=[
            {"role": "system", "content": ("You are a helpful assistant answering a "
             "user's question as you normally would. Name specific companies where relevant.")},
            {"role": "user", "content": prompt}])
    return (r.choices[0].message.content or "").strip()


def _ask_gemini(prompt: str, model: str) -> str:
    from google import genai
    from google.genai import types
    c = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    r = c.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="Answer the user's question as you normally would. "
                               "Name specific companies where relevant."))
    return (r.text or "").strip()


def _score_answer(answer: str, brand_aliases: list[str], rivals: list[str]) -> dict[str, Any]:
    """Deterministic read of one answer — no second model call, so the score
    cannot itself hallucinate. Position = which mention comes first in the text."""
    a = _norm(answer)
    hits = [al for al in brand_aliases if _norm(al) in a]
    mentioned = bool(hits)
    rival_hits = [r for r in rivals if _norm(r) in a]
    # position: order of first brand mention among all named entities
    first_brand = min((a.find(_norm(al)) for al in hits), default=-1)
    rivals_before = sum(1 for r in rival_hits
                        if 0 <= a.find(_norm(r)) < first_brand) if mentioned else len(rival_hits)
    position = (rivals_before + 1) if mentioned else None
    sentiment = "negative" if mentioned and any(
        n in a for n in _SENTIMENT_NEG) else ("positive" if mentioned else "absent")
    return {"mentioned": mentioned, "position": position,
            "rivals_named": rival_hits, "sentiment": sentiment,
            "answer_excerpt": answer[:280]}


def probe(domain_cfg: dict[str, Any], provider: str, model: str) -> dict[str, Any]:
    ask = {"anthropic": _ask_anthropic, "gemini": _ask_gemini,
           "openai": _ask_openai}[provider]
    results = []
    for p in domain_cfg["prompts"]:
        try:
            ans = ask(p, model)
            sc = _score_answer(ans, domain_cfg["aliases"], domain_cfg["rivals"])
        except Exception as exc:
            sc = {"mentioned": None, "error": str(exc)[:140]}
        results.append({"prompt": p, **sc})
    ok = [r for r in results if r.get("mentioned") is not None]
    mentioned = [r for r in ok if r["mentioned"]]
    presence = round(len(mentioned) / len(ok), 2) if ok else None
    positions = [r["position"] for r in mentioned if r.get("position")]
    return {
        "domain": domain_cfg["domain"], "brand": domain_cfg["brand"],
        "provider": provider, "model": model,
        "prompts_asked": len(results),
        "presence_rate": presence,               # share of prompts that named us
        "avg_position": round(sum(positions) / len(positions), 1) if positions else None,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", help="restrict to one domain")
    ap.add_argument("--provider", choices=["anthropic", "gemini", "openai"], default="anthropic")
    ap.add_argument("--model", default=None)
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    model = args.model or {"anthropic": "claude-sonnet-5",
                           "gemini": "gemini-flash-latest",
                           "openai": "gpt-4.1"}[args.provider]

    cfgs = [c for c in PROBES if not args.domain or c["domain"] == args.domain]
    if not cfgs:
        print(f"no probe configured for {args.domain}", file=sys.stderr)
        return 2
    report = {
        "tool": "ai_visibility", "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds"),
        "measures": ("base-model training recall (no web access) — how a plain "
                     "assistant answer forms with browsing off. NOT live-retrieval "
                     "(Perplexity / search) visibility, which is a separate surface."),
        "provider": args.provider, "model": model,
        "properties": [probe(c, args.provider, model) for c in cfgs],
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0

    print(f"# AI visibility — {args.provider}/{model}\n")
    print(f"_{report['measures']}_\n")
    print("| Property | Presence | Avg position | Prompts | Rivals surfacing instead |")
    print("|---|---:|---:|---:|---|")
    for pr in report["properties"]:
        rivals = sorted({r for res in pr["results"] for r in res.get("rivals_named", [])})
        pres = f"{int(pr['presence_rate']*100)}%" if pr["presence_rate"] is not None else "—"
        pos = pr["avg_position"] if pr["avg_position"] is not None else "—"
        print(f"| {pr['domain']} | {pres} | {pos} | {pr['prompts_asked']} | "
              f"{'، '.join(rivals[:5]) or '—'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
