#!/usr/bin/env python3
"""CTR gap: pages Google shows at a decent position that get fewer clicks than that position normally earns.

    python3 tools/ctr_gap.py [--domain X] [--days 90] [--min-imp 150]
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import agent1_seo_scout as a1  # noqa: E402

# Rough organic CTR by whole position; a yardstick, not a Google number.
EXPECTED = {1: .28, 2: .15, 3: .10, 4: .07, 5: .055, 6: .045, 7: .035, 8: .03, 9: .025, 10: .02,
            11: .012, 12: .010}


def expected(pos: float) -> float:
    return EXPECTED.get(max(1, min(12, round(pos))), 0.01)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--min-imp", type=int, default=150)
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    svc = a1.build_gsc_client()
    sites = [s for s in config.load_sites(include_hold=True) if not a.domain or s.domain == a.domain]
    for site in sites:
        end = (a1.utc_now() - timedelta(days=site.data_lag_days)).date()
        start = end - timedelta(days=a.days)
        try:
            pages = a1._search_analytics(svc, site.property_uri, str(start), str(end), ["page"])
        except Exception as exc:  # one site's grant must not stop the others
            print(f"\n## {site.domain}: skipped ({config.redact(str(exc))[:120]})")
            continue
        tot_i = sum(r["impressions"] for r in pages)
        tot_c = sum(r["clicks"] for r in pages)
        print(f"\n## {site.domain}  {start}..{end}: {len(pages)} pages, {tot_i} impressions, {tot_c} clicks "
              f"({(tot_c / tot_i * 100 if tot_i else 0):.2f}% CTR)")
        cand = []
        for r in pages:
            imp, clk, pos = r["impressions"], r["clicks"], r["position"]
            if imp < a.min_imp or pos > 12:
                continue
            exp_clicks = imp * expected(pos)
            missed = exp_clicks - clk
            if missed >= 3 and clk < 0.6 * exp_clicks:
                cand.append((missed, r))
        cand.sort(key=lambda x: -x[0])
        print(f"gap pages (>= {a.min_imp} imp, pos <= 12, CTR < 60% of yardstick): {len(cand)}; "
              f"missed clicks ~{sum(m for m, _ in cand):.0f}")
        if not cand:
            continue
        qrows = a1._search_analytics(svc, site.property_uri, str(start), str(end), ["page", "query"])
        topq: dict[str, tuple[str, int]] = {}
        for r in qrows:
            p, q = r["keys"]
            if p not in topq or r["impressions"] > topq[p][1]:
                topq[p] = (q, r["impressions"])
        for missed, r in cand[: a.top]:
            p = r["keys"][0]
            q = topq.get(p, ("?", 0))[0]
            print(f"{p} | imp {r['impressions']} clk {r['clicks']} ctr {r['ctr']*100:.2f}% pos {r['position']:.1f} "
                  f"| missed ~{missed:.0f} | top query: {q}")


if __name__ == "__main__":
    main()
