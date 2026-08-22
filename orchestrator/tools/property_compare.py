#!/usr/bin/env python3
"""
Why two Search Console properties for one site disagree.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

ambientetravel.com has both a domain property and a URL-prefix property on
https://www.ambientetravel.com/. www 301s to the apex and the page canonicals
to the apex, so the www property should be close to empty — and it is not. It
reports MORE impressions and clicks than the domain property.

A domain property does not backfill. It starts collecting the day it is
verified, so a recently-added one can show a fraction of a long-standing
URL-prefix property's numbers while being the more correct instrument. Whether
that is the explanation here is a question about dates, not about opinion, so
this asks:

  * daily impressions and clicks per property, so a start date is visible as
    the day the numbers begin rather than inferred
  * the first and last day each property has ANY data
  * the top pages in each, because a www property still carrying pre-migration
    URLs says something different from one carrying today's

Neither property is assumed to be the truth. They are printed side by side and
the dates are left to say which is which.

    python3 tools/property_compare.py --a sc-domain:ambientetravel.com \\
                                      --b https://www.ambientetravel.com/
    python3 tools/property_compare.py --days 180 --format json
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


def series(service, prop: str, start: str, end: str) -> list[dict[str, Any]]:
    """Daily rows. The date dimension is what makes a start date visible."""
    try:
        return a1._search_analytics(service, prop, start, end, ["date"])
    except Exception as exc:                      # PermissionError and HttpError alike
        return [{"error": config.redact(str(exc))[:160]}]


def top_pages(service, prop: str, start: str, end: str, n: int = 5) -> list[dict[str, Any]]:
    try:
        rows = a1._search_analytics(service, prop, start, end, ["page"])
    except Exception:
        return []
    rows.sort(key=lambda r: -(r.get("impressions") or 0))
    return [{"page": (r.get("keys") or ["?"])[0],
             "impressions": int(r.get("impressions", 0) or 0),
             "clicks": int(r.get("clicks", 0) or 0)} for r in rows[:n]]


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if rows and rows[0].get("error"):
        return {"error": rows[0]["error"]}
    days = [(r["keys"][0], int(r.get("impressions", 0) or 0), int(r.get("clicks", 0) or 0))
            for r in rows if r.get("keys")]
    days.sort()
    live = [d for d in days if d[1] > 0]
    return {
        "impressions": sum(d[1] for d in days),
        "clicks": sum(d[2] for d in days),
        "days_with_data": len(live),
        "first_day_with_data": live[0][0] if live else None,
        "last_day_with_data": live[-1][0] if live else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--a", default="sc-domain:ambientetravel.com")
    ap.add_argument("--b", default="https://www.ambientetravel.com/")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    service = a1.build_gsc_client()
    end = (a1.utc_now() - timedelta(days=3)).date()
    start = end - timedelta(days=args.days)
    s, e = start.isoformat(), end.isoformat()

    out = {}
    for label, prop in (("A", args.a), ("B", args.b)):
        rows = series(service, prop, s, e)
        out[label] = {"property": prop, **summarise(rows),
                      "top_pages": top_pages(service, prop, s, e)}

    if args.format == "json":
        print(json.dumps({"window": {"start": s, "end": e}, **out}, indent=2))
        return 0

    print(f"# Two properties, one site — {s} to {e}\n")
    print("| | Property | Impressions | Clicks | Days with data | First day | Last day |")
    print("|---|---|---:|---:|---:|---|---|")
    for label in ("A", "B"):
        d = out[label]
        if d.get("error"):
            print(f"| {label} | `{d['property']}` | — | — | — | — | {d['error']} |")
            continue
        print(f"| {label} | `{d['property']}` | {d['impressions']:,} | {d['clicks']:,} | "
              f"{d['days_with_data']} | {d['first_day_with_data']} | {d['last_day_with_data']} |")
    print()
    for label in ("A", "B"):
        d = out[label]
        if d.get("error") or not d.get("top_pages"):
            continue
        print(f"**{label} — {d['property']}**\n")
        print("| Page | Impressions | Clicks |")
        print("|---|---:|---:|")
        for p in d["top_pages"]:
            print(f"| {p['page']} | {p['impressions']:,} | {p['clicks']:,} |")
        print()
    print("*A domain property does not backfill: it collects from the day it was "
          "verified. If one of these starts later than the other, that is the "
          "answer, and it does not make the later one wrong.*")
    return 0


if __name__ == "__main__":
    sys.exit(main())
