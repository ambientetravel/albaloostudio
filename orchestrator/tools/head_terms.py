#!/usr/bin/env python3
"""Head-term slice of Search Console for one domain: queries x pages, top pages, country split.

    python3 tools/head_terms.py --domain boutimar.com --days 90
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import agent1_seo_scout as a1  # noqa: E402

TERMS = ["iran tour", "tour iran", "tours to iran", "travel to iran", "iran travel",
         "visit iran", "trip to iran", "luxury iran", "private iran", "tailor",
         "iran holiday", "iran vacation", "persia tour"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--terms", default="")
    a = ap.parse_args()
    terms = [t.strip().lower() for t in a.terms.split(",") if t.strip()] or TERMS
    site = next(s for s in config.load_sites(include_hold=True) if s.domain == a.domain)
    svc = a1.build_gsc_client()
    end = (a1.utc_now() - timedelta(days=site.data_lag_days)).date()
    start = end - timedelta(days=a.days)
    S, E = str(start), str(end)
    print(f"property {site.property_uri}  window {S}..{E}")

    def rows(dims):
        return a1._search_analytics(svc, site.property_uri, S, E, dims)

    hit = lambda q: any(t in q.lower() for t in terms)
    qp = [r for r in rows(["query", "page"]) if hit(r["keys"][0])]
    qp.sort(key=lambda r: -r["impressions"])
    print(f"\n## query x page, head terms: {len(qp)} rows, "
          f"{sum(r['impressions'] for r in qp)} impressions, {sum(r['clicks'] for r in qp)} clicks")
    for r in qp[:80]:
        print(f"{r['keys'][0]} | {r['keys'][1]} | imp {r['impressions']} | clk {r['clicks']} | pos {r['position']:.1f}")

    pg = sorted(rows(["page"]), key=lambda r: -r["impressions"])
    print(f"\n## top 30 pages by impressions (of {len(pg)})")
    for r in pg[:30]:
        print(f"{r['keys'][0]} | imp {r['impressions']} | clk {r['clicks']} | ctr {r['ctr']*100:.2f}% | pos {r['position']:.1f}")

    agg: dict[str, list[float]] = {}
    for r in rows(["query", "country"]):
        if hit(r["keys"][0]):
            x = agg.setdefault(r["keys"][1], [0, 0, 0.0])
            x[0] += r["impressions"]; x[1] += r["clicks"]; x[2] += r["position"] * r["impressions"]
    print("\n## country split, head terms")
    for c, (i, k, pw) in sorted(agg.items(), key=lambda x: -x[1][0])[:20]:
        print(f"{c} | imp {i} | clk {k} | pos {pw / i:.1f}")


if __name__ == "__main__":
    main()
