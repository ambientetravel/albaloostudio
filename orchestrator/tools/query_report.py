#!/usr/bin/env python3
"""
What a site actually ranks for, and where — query by query.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Agent 1 reports GAPS, agent 7 reports GEOGRAPHY, and the coverage tool reports
which pages were never surfaced. None of them answers the question an owner
actually asks: "we are not on page one for our own keywords — why?"

That question has two very different answers and they are easy to confuse:

  * The query does not appear AT ALL. Google has never shown this site for it.
    There is no position to improve; there is nothing there. More on-page work
    on an existing page will not create a listing.
  * The query appears at position 40. There IS a listing, on page four, and the
    work is different — it is competition, not existence.

So this prints both: the queries the site DOES surface for with their positions,
and a WATCHLIST of terms the owner believes matter, marked plainly as absent
when Search Console has never recorded them.

Absent is the more useful finding of the two, and the one a ranking table
hides by only showing what exists.

    python3 tools/query_report.py --domain boutimar.ir
    python3 tools/query_report.py --domain boutimar.ir --watch "تور کشتی کروز,کروز"
    python3 tools/query_report.py --domain boutimar.com --top 40 --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import agent1_seo_scout as a1  # noqa: E402

# Position bands, borrowed from agent 7 so two tools never disagree about what
# "page one" means.
def band(pos: float) -> str:
    if pos < 3:   return "top 3"
    if pos < 11:  return "page 1"
    if pos < 21:  return "page 2"
    if pos < 31:  return "page 3"
    if pos < 41:  return "page 4"
    return "beyond page 4"


def collect(service, site: config.Site) -> list[dict[str, Any]]:
    end = (a1.utc_now() - timedelta(days=site.data_lag_days)).date()
    start = end - timedelta(days=site.lookback_days)
    rows = a1._search_analytics(service, site.property_uri,
                                start.isoformat(), end.isoformat(), ["query"])
    out = []
    for r in rows:
        keys = r.get("keys") or []
        if not keys:
            continue
        imp = int(r.get("impressions", 0) or 0)
        pos = float(r.get("position", 0) or 0)
        out.append({"query": keys[0], "impressions": imp,
                    "clicks": int(r.get("clicks", 0) or 0),
                    "position": round(pos, 1), "band": band(pos)})
    out.sort(key=lambda x: -x["impressions"])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--watch", default="",
                    help="comma-separated terms to check for presence")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    site = config.load_sites(only=[args.domain], include_hold=True)[0]
    service = a1.build_gsc_client()
    rows = collect(service, site)

    watch = [w.strip() for w in args.watch.split(",") if w.strip()]
    found = {}
    for w in watch:
        # Substring, not equality: "تور کشتی کروز" should match the long-tail
        # queries that contain it, which is where a new site actually surfaces.
        hits = [r for r in rows if w in r["query"]]
        found[w] = hits

    if args.format == "json":
        print(json.dumps({"domain": site.domain, "queries": rows,
                          "watch": {k: v for k, v in found.items()}},
                         ensure_ascii=False, indent=2))
        return 0

    total = sum(r["impressions"] for r in rows)
    print(f"# {site.domain} — what it actually ranks for\n")
    print(f"{len(rows)} distinct queries, {total:,} impressions, "
          f"{sum(r['clicks'] for r in rows)} clicks "
          f"({site.lookback_days}-day window)\n")

    if rows:
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["band"]] = counts.get(r["band"], 0) + 1
        print("| Band | Queries |")
        print("|---|---:|")
        for b in ("top 3", "page 1", "page 2", "page 3", "page 4", "beyond page 4"):
            if counts.get(b):
                print(f"| {b} | {counts[b]} |")
        print()

    print(f"## Top {min(args.top, len(rows))} by impressions\n")
    print("| Query | Impressions | Clicks | Position | Band |")
    print("|---|---:|---:|---:|---|")
    for r in rows[:args.top]:
        print(f"| {r['query']} | {r['impressions']:,} | {r['clicks']} | "
              f"{r['position']} | {r['band']} |")
    print()

    if watch:
        print("## Terms you asked about\n")
        print("**Absent means Google has never shown this site for it in the "
              "window — there is no position to improve, and no amount of "
              "on-page work on an existing page creates a listing.**\n")
        print("| Term | Status | Best position | Impressions |")
        print("|---|---|---:|---:|")
        for w in watch:
            hits = found[w]
            if not hits:
                print(f"| {w} | **ABSENT** | — | 0 |")
                continue
            best = min(hits, key=lambda x: x["position"])
            print(f"| {w} | {len(hits)} quer{'y' if len(hits)==1 else 'ies'} | "
                  f"{best['position']} ({best['band']}) | "
                  f"{sum(h['impressions'] for h in hits):,} |")
        print()
        for w in watch:
            if found[w]:
                print(f"**Queries containing “{w}”**\n")
                print("| Query | Impressions | Position |")
                print("|---|---:|---:|")
                for h in sorted(found[w], key=lambda x: -x["impressions"])[:10]:
                    print(f"| {h['query']} | {h['impressions']:,} | {h['position']} |")
                print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
