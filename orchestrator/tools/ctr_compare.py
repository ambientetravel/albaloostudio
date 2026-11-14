#!/usr/bin/env python3
"""28 days before vs 28 days after a title change, one page.

    python3 tools/ctr_compare.py --domain cruisebaz.com --page https://cruisebaz.com/en/aroya/price --applied 2026-11-16
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import agent1_seo_scout as a1  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--applied", required=True)
    ap.add_argument("--window", type=int, default=28)
    a = ap.parse_args()
    site = next(s for s in config.load_sites(include_hold=True) if s.domain == a.domain)
    svc = a1.build_gsc_client()
    d0 = date.fromisoformat(a.applied)
    w = a.window
    # skip the application day itself; Google recrawls later, so the after-window is a lower bound on effect
    spans = {"before": (d0 - timedelta(days=w), d0 - timedelta(days=1)),
             "after": (d0 + timedelta(days=1), d0 + timedelta(days=w))}
    for name, (s, e) in spans.items():
        rows = a1._search_analytics(svc, site.property_uri, str(s), str(e), ["page"])
        r = next((x for x in rows if a1._canon_url(x["keys"][0]) == a1._canon_url(a.page)), None)
        if not r:
            print(f"{name} {s}..{e}: no data")
            continue
        print(f"{name} {s}..{e}: imp {r['impressions']} clk {r['clicks']} ctr {r['ctr']*100:.2f}% pos {r['position']:.1f}")


if __name__ == "__main__":
    main()
