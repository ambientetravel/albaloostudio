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

CHINESE MODELS (30 Sep 2026)
────────────────────────────
Iran and Silk-Road tours sell to Chinese agencies and travellers, and they ask
DeepSeek, Qwen, ERNIE, Doubao and Kimi — not ChatGPT. All five speak the OpenAI
chat protocol, so each is one row in PROVIDERS: base URL, key variable, model.
A provider whose key is not set is reported "not configured" and skipped; one
that errors is reported with the error — neither fails the run. Only the public
probe prompts below are sent; no customer or company data leaves the pipeline.
Model names move fast (Moonshot retired every moonshot-v1 model on 31 Aug
2026), so each model is overridable by env (DEEPSEEK_MODEL, QWEN_MODEL, …).

    python3 tools/ai_visibility.py                  # all providers with a key
    python3 tools/ai_visibility.py --provider deepseek,qwen --domain boutimar.com
    python3 tools/ai_visibility.py --provider cn    # the five Chinese models
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
            "伊朗有哪些靠谱的地接社（DMC）推荐？",
            "我们旅行社想做伊朗团，伊朗当地的地接社找哪家比较好？",
            "去伊朗办会议或奖励旅游，推荐哪家当地公司？",
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
        "aliases": ["explore orient", "exploreorient", "探索东方"],
        "prompts": [
            "Recommend a sustainable, carbon-conscious tour operator for Turkey and the eastern Mediterranean.",
            "Which European agency runs curated cultural tours of the Orient with venue and carbon reporting?",
            "推荐一家做伊朗和土耳其高端定制游的旅行社。",
            "丝绸之路（伊朗、土耳其）深度文化游，哪家旅行社比较专业？",
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


# OpenAI-protocol providers. key: env var holding the API key; model: default,
# overridable by <NAME>_MODEL; base: overridable by <NAME>_BASE_URL.
PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {"label": "DeepSeek", "base": "https://api.deepseek.com",
                 "key": "DEEPSEEK_API_KEY", "model": "deepseek-flash"},
    "qwen":     {"label": "Qwen (Alibaba)", "base": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                 "key": "DASHSCOPE_API_KEY", "model": "qwen-plus"},
    "ernie":    {"label": "ERNIE (Baidu)", "base": "https://qianfan.baidubce.com/v2",
                 "key": "QIANFAN_API_KEY", "model": "ernie-5.1"},
    "doubao":   {"label": "Doubao/Seed (ByteDance)", "base": "https://ark.ap-southeast.bytepluses.com/api/v3",
                 "key": "ARK_API_KEY", "model": "seed-2-0-lite-260228"},
    "kimi":     {"label": "Kimi (Moonshot)", "base": "https://api.moonshot.ai/v1",
                 "key": "MOONSHOT_API_KEY", "model": "kimi-k3"},
}
NATIVE = {"anthropic": ("ANTHROPIC_API_KEY", "claude-sonnet-5"),
          "gemini": ("GEMINI_API_KEY", "gemini-flash-latest"),
          "openai": ("OPENAI_API_KEY", "gpt-4.1")}
CN = ["deepseek", "qwen", "ernie", "doubao", "kimi"]
ALL = list(NATIVE) + CN


def provider_setup(name: str) -> tuple[str | None, str, str | None]:
    """(key or None, model, base_url or None) — env first, registry second."""
    if name in NATIVE:
        env, model = NATIVE[name]
        return os.environ.get(env) or None, model, None
    p = PROVIDERS[name]
    up = name.upper()
    return (os.environ.get(p["key"]) or None,
            os.environ.get(f"{up}_MODEL") or p["model"],
            os.environ.get(f"{up}_BASE_URL") or p["base"])


def _ask_compat(prompt: str, model: str, *, base: str, key: str) -> str:
    from openai import OpenAI
    c = OpenAI(api_key=key, base_url=base, timeout=90, max_retries=1)
    # No temperature: several of these are reasoning models that reject it, and
    # a generous max_tokens so thinking does not eat the whole answer.
    r = c.chat.completions.create(
        model=model, max_tokens=1500,
        messages=[
            {"role": "system", "content": ("You are a helpful assistant answering a "
             "user's question as you normally would. Name specific companies where relevant.")},
            {"role": "user", "content": prompt}])
    return (r.choices[0].message.content or "").strip()


def resolve_providers(spec: str) -> list[str]:
    out: list[str] = []
    for part in (x.strip().lower() for x in spec.split(",") if x.strip()):
        names = ALL if part == "all" else CN if part == "cn" else [part]
        for n in names:
            if n not in ALL:
                raise SystemExit(f"unknown provider {n!r}; choose from {', '.join(ALL)}, all, cn")
            if n not in out:
                out.append(n)
    return out


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


def probe(domain_cfg: dict[str, Any], provider: str, model: str,
          ask=None) -> dict[str, Any]:
    ask = ask or {"anthropic": _ask_anthropic, "gemini": _ask_gemini,
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


def run_provider(name: str, cfgs: list[dict[str, Any]], model_override: str | None) -> dict[str, Any]:
    key, model, base = provider_setup(name)
    model = model_override or model
    label = PROVIDERS.get(name, {}).get("label", name)
    if not key:
        env = NATIVE[name][0] if name in NATIVE else PROVIDERS[name]["key"]
        return {"provider": name, "label": label, "model": model, "status": "not configured",
                "note": f"{env} is not set", "properties": []}
    ask = None
    if name in PROVIDERS:
        ask = lambda p, m: _ask_compat(p, m, base=base, key=key)  # noqa: E731
    props = [probe(c, name, model, ask) for c in cfgs]
    answered = [r for pr in props for r in pr["results"] if r.get("mentioned") is not None]
    errors = [r["error"] for pr in props for r in pr["results"] if r.get("error")]
    status = "ok" if answered else "error"
    return {"provider": name, "label": label, "model": model, "status": status,
            "note": (errors[0] if status == "error" and errors else
                     f"{len(errors)} prompt(s) failed" if errors else ""),
            "properties": props}


def rollup(runs: list[dict[str, Any]], cfgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in cfgs:
        by: dict[str, Any] = {}
        for run in runs:
            for pr in run["properties"]:
                if pr["domain"] == c["domain"]:
                    by[run["provider"]] = pr["presence_rate"]
        out.append({"domain": c["domain"], "brand": c["brand"],
                    "mentioned_any": any((v or 0) > 0 for v in by.values()),
                    "presence_by_provider": by})
    return out


def to_md(report: dict[str, Any]) -> str:
    runs = [r for r in report["runs"] if r["status"] == "ok"]
    L = ["# AI visibility — do the assistants name us?", "",
         f"_{report['measures']}_", "",
         "| Property | " + " | ".join(r["label"] for r in runs) + " |",
         "|---|" + "---:|" * len(runs)]
    for p in report["properties"]:
        cells = []
        for r in runs:
            v = p["presence_by_provider"].get(r["provider"])
            cells.append("—" if v is None else f"{int(v * 100)}%")
        L.append(f"| {p['domain']} | " + " | ".join(cells) + " |")
    rivals = {}
    for r in runs:
        for pr in r["properties"]:
            for res in pr["results"]:
                for rv in res.get("rivals_named", []):
                    rivals.setdefault(pr["domain"], set()).add(rv)
    if rivals:
        L += ["", "**Named instead of us:**"]
        L += [f"- {d}: {', '.join(sorted(v)[:6])}" for d, v in rivals.items()]
    off = [r for r in report["runs"] if r["status"] != "ok"]
    if off:
        L += ["", "**Not measured this run:**"]
        L += [f"- {r['label']} ({r['model']}): {r['status']} — {r['note']}" for r in off]
    L += ["", "_Presence = share of that property's probe prompts whose answer named the brand._"]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", help="restrict to one domain")
    ap.add_argument("--provider", default="all",
                    help=f"comma list of {', '.join(ALL)}; or all / cn (default: all with a key)")
    ap.add_argument("--model", default=None, help="override the model (single provider only)")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    names = resolve_providers(args.provider)
    if args.model and len(names) != 1:
        raise SystemExit("--model needs exactly one --provider")

    cfgs = [c for c in PROBES if not args.domain or c["domain"] == args.domain]
    if not cfgs:
        print(f"no probe configured for {args.domain}", file=sys.stderr)
        return 2
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(names)) as ex:   # providers in parallel
        runs = list(ex.map(lambda n: run_provider(n, cfgs, args.model), names))
    report = {
        "tool": "ai_visibility", "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds"),
        "measures": ("base-model training recall (no web access) — how a plain "
                     "assistant answer forms with browsing off. NOT live-retrieval "
                     "(Perplexity / search) visibility, which is a separate surface."),
        "runs": runs,
        "properties": rollup(runs, cfgs),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1) if args.format == "json" else to_md(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
