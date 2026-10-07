#!/usr/bin/env python3
"""
Page speed for every property — Google's own numbers, real users first.

Two layers, from one PageSpeed Insights call per page (mobile):
  * FIELD — Chrome UX Report data from real visitors over 28 days: LCP, INP,
    CLS, each rated FAST / AVERAGE / SLOW by Google. This is what ranking
    uses. Low-traffic pages have none, and the report says so rather than
    guessing.
  * LAB — a one-off Lighthouse load: the 0–100 performance score and the
    three biggest savings it suggests. Useful for *why*, not for *how fast*.

Pages: each site's home plus its newest pipeline article (from the sitemap).
Key: PAGESPEED_API_KEY if set (higher quota); works without one at low volume.

    python3 tools/pagespeed_check.py                  # md
    python3 tools/pagespeed_check.py --format json --domain boutimar.com
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
_ARTICLE = re.compile(r"/(journal|daryanameh|blog|guides)/[^/]+")
METRICS = {"LARGEST_CONTENTFUL_PAINT_MS": "LCP", "INTERACTION_TO_NEXT_PAINT": "INP",
           "CUMULATIVE_LAYOUT_SHIFT_SCORE": "CLS"}


def _curl(url: str, timeout: int = 90) -> tuple[int, str]:
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", str(timeout), "-w", "\n%{http_code}", url],
                       capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    return int(code or 0), body


def pages_for(site) -> list[str]:
    pages = [site.base_url + "/"]
    code, xml = _curl(site.sitemap, 30)
    locs = re.findall(r"<loc>([^<]+)</loc>", xml) if code == 200 else []
    if locs and all(u.endswith(".xml") for u in locs[:3]):      # sitemap index → first child
        code, xml = _curl(locs[0], 30)
        locs = re.findall(r"<loc>([^<]+)</loc>", xml) if code == 200 else []
    arts = [u for u in locs if _ARTICLE.search(u)]
    if arts:
        pages.append(arts[-1])
    return pages


def check(url: str) -> dict:
    q = {"url": url, "strategy": "mobile", "category": "performance"}
    if os.environ.get("PAGESPEED_API_KEY"):
        q["key"] = os.environ["PAGESPEED_API_KEY"]
    code, body = _curl(f"{API}?{urllib.parse.urlencode(q)}", 120)
    if code != 200:
        return {"url": url, "error": f"HTTP {code}" + (" (quota — set PAGESPEED_API_KEY)" if code == 429 else "")}
    d = json.loads(body)
    field = {}
    for src in ("loadingExperience", "originLoadingExperience"):
        m = (d.get(src) or {}).get("metrics") or {}
        if m:
            for k, short in METRICS.items():
                if k in m:
                    v = m[k].get("percentile")
                    field[short] = {"p75": (v / 100 if short == "CLS" else v), "rating": m[k].get("category")}
            field["_scope"] = "this page" if src == "loadingExperience" else "whole site (page has too few visits)"
            break
    lh = d.get("lighthouseResult") or {}
    score = ((lh.get("categories") or {}).get("performance") or {}).get("score")
    audits = lh.get("audits") or {}
    savings = sorted(((a.get("title"), (a.get("details") or {}).get("overallSavingsMs") or 0)
                      for a in audits.values() if (a.get("details") or {}).get("type") == "opportunity"),
                     key=lambda x: -x[1])
    lab = {k: (audits.get(a) or {}).get("displayValue")
           for k, a in (("FCP", "first-contentful-paint"), ("LCP", "largest-contentful-paint"),
                        ("TBT", "total-blocking-time"), ("CLS", "cumulative-layout-shift"),
                        ("SI", "speed-index"))}
    lcp_items = (((audits.get("largest-contentful-paint-element") or {}).get("details") or {})
                 .get("items") or [])
    lcp_node = None
    for it in lcp_items:   # newer Lighthouse nests the node inside a table
        node = it.get("node") or next((r.get("node") for r in (it.get("items") or []) if r.get("node")), None)
        if node:
            lcp_node = (node.get("snippet") or node.get("nodeLabel") or "")[:140]
            break
    heavy = sorted((((audits.get("total-byte-weight") or {}).get("details") or {}).get("items") or []),
                   key=lambda i: -(i.get("totalBytes") or 0))[:4]
    return {"url": url, "field": field or None,
            "lab_score": round(score * 100) if isinstance(score, (int, float)) else None,
            "lcp_lab_ms": (audits.get("largest-contentful-paint") or {}).get("numericValue"),
            "lab": lab, "lcp_element": lcp_node,
            "heaviest": [{"url": i.get("url", ""), "kb": round((i.get("totalBytes") or 0) / 1024)} for i in heavy],
            "top_savings": [{"fix": t, "ms": round(ms)} for t, ms in savings[:3] if ms >= 200]}


def to_md(report: dict) -> str:
    L = [f"# Page speed (Google PageSpeed / CrUX, mobile) · {report['generated_at'][:10]}", "",
         "FIELD = real visitors, 75th percentile, Google's own rating — what ranking uses. "
         "LAB = one Lighthouse load: the score and what would save the most time.", "",
         "| Page | LCP | INP | CLS | Field scope | Lab score |", "|---|---|---|---|---|---:|"]
    fixes = []
    for s in report["sites"]:
        for p in s["pages"]:
            if p.get("error"):
                L.append(f"| {p['url']} | — | — | — | {p['error']} | — |")
                continue
            f = p.get("field") or {}
            cell = lambda k, unit: (f"{f[k]['p75']}{unit} {f[k]['rating'].lower()}" if k in f else "—")  # noqa: E731
            L.append(f"| {p['url']} | {cell('LCP', 'ms')} | {cell('INP', 'ms')} | {cell('CLS', '')} | "
                     f"{f.get('_scope', 'no field data yet')} | {p.get('lab_score', '—')} |")
            fixes += [f"- **{p['url']}** — {x['fix']} (~{x['ms']} ms)" for x in p.get("top_savings", [])]
    if fixes:
        L += ["", "**Biggest savings Lighthouse found:**", *fixes]
    detail = [p for s in report["sites"] for p in s["pages"] if p.get("lab")]
    if detail:
        L += ["", "**Lab timings (one mobile load) — what holds each score down:**", "",
              "| Page | FCP | LCP | TBT | CLS | LCP element | Heaviest downloads |", "|---|---|---|---|---|---|---|"]
        for p in detail:
            lb = p["lab"]
            el = (p.get("lcp_element") or "—").replace("|", "/")
            hv = ", ".join(f"{h['url'].rsplit('/', 1)[-1][:32]} {h['kb']} KB" for h in p.get("heaviest", []))
            L.append(f"| {p['url']} | {lb.get('FCP') or '—'} | {lb.get('LCP') or '—'} | {lb.get('TBT') or '—'} | "
                     f"{lb.get('CLS') or '—'} | `{el[:80]}` | {hv or '—'} |")
    L += ["", "_Good thresholds (p75): LCP ≤ 2500 ms, INP ≤ 200 ms, CLS ≤ 0.1._"]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--domain", action="append")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    a = ap.parse_args(argv)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sites": []}
    for s in [x for x in config.load_sites(only=a.domain) if not x.on_hold]:
        pages = []
        for u in pages_for(s):
            pages.append(check(u))
            time.sleep(1)
        report["sites"].append({"domain": s.domain, "pages": pages})
    print(json.dumps(report, ensure_ascii=False, indent=1) if a.format == "json" else to_md(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
