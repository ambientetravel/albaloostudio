#!/usr/bin/env python3
"""
Google Trends for every property — Agent 7's demand-over-time lens.

Search Console says what a site already ranks for; Trends says what people
are about to search for, and when. Per property this reports:

  * seasonality   — the months each topic peaks (12 months, weekly), so a
                    Nowruz or AROYA-season article is briefed BEFORE the rise
  * momentum      — last 8 weeks vs the 8 before (rising / flat / falling)
  * rising queries — related searches Google marks as rising or "Breakout":
                    candidate topics GSC cannot show because nobody ranks yet
  * where         — the regions with the most interest (diaspora signal)

Terms come from sites.yml `trend_terms` (else the first seed keywords); geo
from the site's market (IR → Iran, DACH → Germany, INT → worldwide).

No key and no library: the same public endpoints trends.google.com uses,
fetched with curl, throttled, and degraded to a note on 429 — a Trends outage
must never fail Agent 7.

    python3 tools/trends_scan.py                   # all active sites → md
    python3 tools/trends_scan.py --format json --domain cruise24.ir
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

BASE = "https://trends.google.com/trends/api"
GEO = {"IR": "IR", "DACH": "DE", "INT": ""}
PAUSE = 2.5            # seconds between calls — Trends rate-limits hard
MAX_TERMS = 4
_JAR = Path("/tmp/albaloo-trends.cookies")


def _get(url: str) -> tuple[int, str]:
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "30", "-b", str(_JAR), "-c", str(_JAR),
                        "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36",
                        "-w", "\n%{http_code}", url], capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    return int(code or 0), body


def _json(body: str):
    # Trends prefixes every JSON response with an anti-XSSI line: )]}' or )]}',
    return json.loads(body.split("\n", 1)[1] if body.startswith(")]}'") else body)


def _widget(kind: str, w: dict) -> tuple[int, object]:
    q = urllib.parse.urlencode({"hl": "en-US", "tz": "-180",
                                "req": json.dumps(w["request"], separators=(",", ":")),
                                "token": w["token"]})
    time.sleep(PAUSE)
    code, body = _get(f"{BASE}/widgetdata/{kind}?{q}")
    return code, (_json(body) if code == 200 else None)


def scan_term(term: str, geo: str) -> dict:
    out: dict = {"term": term, "geo": geo or "worldwide"}
    if not _JAR.exists():
        _get("https://trends.google.com/trends/?geo=" + (geo or "US"))  # session cookie
    req = {"comparisonItem": [{"keyword": term, "geo": geo, "time": "today 12-m"}],
           "category": 0, "property": ""}
    time.sleep(PAUSE)
    code, body = _get(f"{BASE}/explore?hl=en-US&tz=-180&req={urllib.parse.quote(json.dumps(req))}")
    if code != 200:
        out["error"] = f"explore HTTP {code}" + (" (rate-limited)" if code == 429 else "")
        return out
    widgets = {w["id"]: w for w in _json(body).get("widgets", [])}

    if "TIMESERIES" in widgets:
        code, d = _widget("multiline", widgets["TIMESERIES"])
        pts = [(p["formattedTime"], (p.get("value") or [0])[0]) for p in (d or {}).get("default", {}).get("timelineData", [])]
        if pts and sum(v for _, v in pts) >= len(pts) * 3:   # below ~3/100 average Trends is noise
            vals = [v for _, v in pts]
            out["peak_weeks"] = [t for t, v in sorted(pts, key=lambda x: -x[1])[:3]]
            recent, prior = vals[-8:], vals[-16:-8]
            r, p = (sum(recent) / len(recent) if recent else 0), (sum(prior) / len(prior) if prior else 0)
            out["momentum"] = ("rising" if r > p * 1.2 else "falling" if r < p * 0.8 else "flat") if p else ("new" if r else "no data")
            out["avg_interest"] = round(sum(vals) / len(vals), 1)
            months = {}
            for t, v in pts:
                m = t.split("–")[0].split(" ")[0][:3]
                months[m] = months.get(m, 0) + v
            out["peak_months"] = [m for m, _ in sorted(months.items(), key=lambda x: -x[1])[:3]]
        elif code == 429:
            out["error"] = "rate-limited on the time series"
        else:
            out["momentum"] = "too little search volume"

    for wid, w in widgets.items():
        if wid.startswith("RELATED_QUERIES"):
            code, d = _widget("relatedsearches", w)
            ranked = (d or {}).get("default", {}).get("rankedList", [])
            if len(ranked) > 1:
                out["rising"] = [{"query": k["query"], "growth": k.get("formattedValue")}
                                 for k in ranked[1].get("rankedKeyword", [])[:8]]
            if ranked:
                out["top_related"] = [k["query"] for k in ranked[0].get("rankedKeyword", [])[:6]]
        if wid == "GEO_MAP" and not geo:
            code, d = _widget("comparedgeo", w)
            geo_rows = (d or {}).get("default", {}).get("geoMapData", [])
            out["top_regions"] = [g["geoName"] for g in sorted(geo_rows, key=lambda g: -(g.get("value") or [0])[0])
                                  if (g.get("value") or [0])[0] > 0][:5]
    return out


def terms_for(site) -> list[str]:
    raw = getattr(site, "trend_terms", None) or []
    return [t for t in (raw or site.seed_keywords)][:MAX_TERMS]


def to_md(report: dict) -> str:
    lines = [f"# Agent 7 — Google Trends · {report['generated_at'][:10]}", "",
             "What people are about to search for, and when. Seasonality tells you when to publish "
             "(brief ~6 weeks before the peak); rising queries are topics nobody ranks for yet.", ""]
    for s in report["sites"]:
        lines += [f"## {s['domain']}  ·  {s['geo'] or 'worldwide'}", ""]
        if not s["terms"]:
            lines += ["_No trend terms or seeds configured._", ""]
            continue
        lines += ["| Term | Momentum | Peak months | Avg interest |", "|---|---|---|---:|"]
        for t in s["terms"]:
            lines.append(f"| {t['term']} | {t.get('momentum', t.get('error', '—'))} | "
                         f"{', '.join(t.get('peak_months', [])) or '—'} | {t.get('avg_interest', '—')} |")
        rising = [(t["term"], r) for t in s["terms"] for r in t.get("rising", [])]
        if rising:
            lines += ["", "**Rising searches (candidate topics):**"]
            lines += [f"- {r['query']} — {r['growth']}  _(from “{term}”)_" for term, r in rising[:12]]
        regions = [(t["term"], t["top_regions"]) for t in s["terms"] if t.get("top_regions")]
        for term, regs in regions[:2]:
            lines.append(f"\nWhere “{term}” is searched most: {', '.join(regs)}")
        lines.append("")
    lines.append("_Source: trends.google.com public endpoints. Relative interest (0–100), not search volume._")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--domain", action="append")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    a = ap.parse_args(argv)
    sites = [s for s in config.load_sites(only=a.domain) if not s.on_hold]
    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sites": []}
    for s in sites:
        geo = GEO.get(s.market or "INT", "")
        terms = [scan_term(t, geo) for t in terms_for(s)]
        report["sites"].append({"domain": s.domain, "geo": geo, "terms": terms})
    print(json.dumps(report, ensure_ascii=False, indent=1) if a.format == "json" else to_md(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
