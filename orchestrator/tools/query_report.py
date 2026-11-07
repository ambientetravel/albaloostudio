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


def collect_pages(service, site: config.Site) -> dict[str, list[dict[str, Any]]]:
    """Which PAGE Google shows for each query. Position 77 on a head term reads
    very differently when it is the home page (a linking/canonical problem: the
    dedicated page exists and is not the one chosen) than when it is the
    dedicated page itself (authority — backlinks and time). cruise24.ir asked
    exactly this on 1 Nov and the query-only table could not say."""
    end = (a1.utc_now() - timedelta(days=site.data_lag_days)).date()
    start = end - timedelta(days=site.lookback_days)
    rows = a1._search_analytics(service, site.property_uri,
                                start.isoformat(), end.isoformat(), ["query", "page"])
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        keys = r.get("keys") or []
        if len(keys) < 2:
            continue
        pos = float(r.get("position", 0) or 0)
        out.setdefault(keys[0], []).append({
            "page": keys[1].replace(f"https://{site.domain}", "") or "/",
            "impressions": int(r.get("impressions", 0) or 0),
            "clicks": int(r.get("clicks", 0) or 0), "position": round(pos, 1)})
    for v in out.values():
        v.sort(key=lambda x: -x["impressions"])
    return out


def trend(service, site: config.Site, days: int = 480) -> list[dict[str, Any]]:
    """Clicks, impressions and position per ISO week (Monday), as far back as Search
    Console keeps data (16 months). "Performance dropped" is a claim about a curve;
    this is the curve."""
    from datetime import date as _date
    end = (a1.utc_now() - timedelta(days=site.data_lag_days)).date()
    start = end - timedelta(days=days)
    rows = a1._search_analytics(service, site.property_uri, start.isoformat(), end.isoformat(), ["date"])
    weeks: dict[str, dict[str, float]] = {}
    for r in rows:
        d = _date.fromisoformat(r["keys"][0])
        wk = (d - timedelta(days=d.weekday())).isoformat()
        w = weeks.setdefault(wk, {"clicks": 0, "impressions": 0, "pos_x_impr": 0.0, "days": 0})
        imp = int(r.get("impressions", 0) or 0)
        w["clicks"] += int(r.get("clicks", 0) or 0)
        w["impressions"] += imp
        w["pos_x_impr"] += float(r.get("position", 0) or 0) * imp
        w["days"] += 1
    return [{"week": k, "clicks": int(v["clicks"]), "impressions": int(v["impressions"]), "days": int(v["days"]),
             "position": round(v["pos_x_impr"] / v["impressions"], 1) if v["impressions"] else None}
            for k, v in sorted(weeks.items())]


def page_windows(service, site: config.Site, pivot: str, days: int) -> list[dict[str, Any]]:
    """Impressions and clicks per page in the `days` before `pivot` and the `days` after it
    (or up to the data lag), to see which pages a drop came from."""
    from datetime import date as _date
    p = _date.fromisoformat(pivot)
    end = min(p + timedelta(days=days), (a1.utc_now() - timedelta(days=site.data_lag_days)).date())
    span = (end - p).days
    before = a1._search_analytics(service, site.property_uri, (p - timedelta(days=span)).isoformat(),
                                  (p - timedelta(days=1)).isoformat(), ["page"])
    after = a1._search_analytics(service, site.property_uri, p.isoformat(), end.isoformat(), ["page"])
    out: dict[str, dict[str, Any]] = {}
    for tag, rows in (("before", before), ("after", after)):
        for r in rows:
            o = out.setdefault(r["keys"][0], {"page": r["keys"][0], "before_impr": 0, "before_clicks": 0,
                                              "after_impr": 0, "after_clicks": 0})
            o[f"{tag}_impr"] += int(r.get("impressions", 0) or 0)
            o[f"{tag}_clicks"] += int(r.get("clicks", 0) or 0)
    rows = sorted(out.values(), key=lambda o: -(o["before_impr"] + o["after_impr"]))
    for o in rows:
        o["span_days"] = span
    return rows


def sitemap_status(service, site: config.Site) -> list[dict[str, Any]]:
    """What Search Console itself holds for the property's sitemaps: when it last read
    them, errors, and how many URLs it took from each. Restricted users can read this."""
    try:
        resp = service.sitemaps().list(siteUrl=site.property_uri).execute()
    except Exception as e:  # noqa: BLE001 — a permission answer is a finding, not a crash
        return [{"error": str(e)[:200]}]
    return resp.get("sitemap", [])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--watch", default="",
                    help="comma-separated terms to check for presence")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--trend", action="store_true",
                    help="weekly clicks, impressions and position over 16 months, plus sitemap status")
    ap.add_argument("--compare", default="",
                    help="YYYY-MM-DD: per-page impressions in equal windows before and after this date")
    ap.add_argument("--pages", action="store_true",
                    help="also show WHICH page ranks for each top/watched query")
    args = ap.parse_args(argv)

    site = config.load_sites(only=[args.domain], include_hold=True)[0]
    service = a1.build_gsc_client()
    if args.trend or args.compare:
        return report_trend(service, site, args)
    rows = collect(service, site)

    watch = [w.strip() for w in args.watch.split(",") if w.strip()] or list(site.watch_terms)
    found = {}
    for w in watch:
        # Substring, not equality: "تور کشتی کروز" should match the long-tail
        # queries that contain it, which is where a new site actually surfaces.
        hits = [r for r in rows if w in r["query"]]
        found[w] = hits

    pages = collect_pages(service, site) if args.pages else {}

    if args.format == "json":
        print(json.dumps({"domain": site.domain, "queries": rows,
                          "watch": {k: v for k, v in found.items()}, "pages": pages},
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
    if args.pages:
        shown = [w for w in watch if found.get(w)] or []
        qs = []
        for w in shown:
            qs += [h["query"] for h in sorted(found[w], key=lambda x: -x["impressions"])[:5]]
        if not qs:
            qs = [r["query"] for r in rows[:args.top]]
        seen = set()
        print("\n## Which page Google shows for each query\n")
        print("The home page at position 70+ for a head term means the dedicated page "
              "is not being chosen (canonical / internal links); the dedicated page at 70+ means authority.\n")
        print("| Query | Page | Impressions | Clicks | Position |")
        print("|---|---|---:|---:|---:|")
        for q in qs:
            if q in seen:
                continue
            seen.add(q)
            for pg in (pages.get(q) or [])[:3]:
                print(f"| {q} | `{pg['page']}` | {pg['impressions']:,} | {pg['clicks']} | {pg['position']} |")
        print()
    return 0


def report_trend(service, site: config.Site, args) -> int:
    if args.trend:
        weeks = trend(service, site)
        print(f"# {site.domain} — clicks and impressions per week ({site.property_uri})\n")
        print("| Week of | Clicks | Impressions | Avg position | Days with data |")
        print("|---|---:|---:|---:|---:|")
        for w in weeks:
            print(f"| {w['week']} | {w['clicks']} | {w['impressions']:,} | {w['position'] if w['position'] is not None else '—'} | {w['days']} |")
        print(f"\n{len(weeks)} weeks, {sum(w['clicks'] for w in weeks)} clicks, "
              f"{sum(w['impressions'] for w in weeks):,} impressions in total.\n")
        print("## Sitemaps as Search Console holds them\n")
        sm = sitemap_status(service, site)
        if not sm:
            print("No sitemap submitted to Search Console for this property.\n")
        for m in sm:
            if "error" in m:
                print(f"Could not read sitemaps: {m['error']}\n")
                continue
            parts = ", ".join(f"{c.get('type')}: {c.get('submitted')} submitted" + (f", {c['indexed']} indexed" if c.get("indexed") else "")
                              for c in m.get("contents", []))
            print(f"- `{m.get('path')}`: last submitted {str(m.get('lastSubmitted', '—'))[:10]}, last read by Google "
                  f"{str(m.get('lastDownloaded', '—'))[:10]}, pending {m.get('isPending')}, errors {m.get('errors', 0)}, "
                  f"warnings {m.get('warnings', 0)}; {parts or 'no contents reported'}")
        print()
    if args.compare:
        rows = page_windows(service, site, args.compare, 60)
        span = rows[0]["span_days"] if rows else 0
        print(f"## Pages, {span} days before vs {span} days after {args.compare}\n")
        print(f"Before: {sum(r['before_impr'] for r in rows):,} impressions, {sum(r['before_clicks'] for r in rows)} clicks. "
              f"After: {sum(r['after_impr'] for r in rows):,} impressions, {sum(r['after_clicks'] for r in rows)} clicks.\n")
        print("| Page | Impr. before | Clicks before | Impr. after | Clicks after |")
        print("|---|---:|---:|---:|---:|")
        for r in rows[:args.top]:
            print(f"| {r['page']} | {r['before_impr']:,} | {r['before_clicks']} | {r['after_impr']:,} | {r['after_clicks']} |")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
