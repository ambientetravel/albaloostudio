#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Farsi keyword demand straight from Google's suggest endpoint. No account, no cap.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHY THIS EXISTS
───────────────
keywordchi sells Persian keyword discovery for 500,000–1,300,000 تومان/month
and rate-limits its trial to three searches a day. Reading its output closely
showed what it actually is: a Google autocomplete scraper. Its sheets are the
base suggestions, a fixed prefix sweep (خرید/فروش/قیمت/بهترین/مقایسه), a suffix
sweep (از/با/در/به/برای), and an alphabet sweep — exactly the permutations you
can ask the public endpoint for yourself.

Measured against its own paid export for «کشتی کروز» (419 terms), 59 free
queries recovered 64% of it AND returned 83 terms it did not have. The gap is
not cleverness, it is the prefix list: keywordchi never sweeps تور، رزرو، بلیط،
انواع, which is precisely where the commercial phrasings live.

So this is not a workaround. It is the same method with a better word list and
no daily allowance.

WHAT IT STILL CANNOT DO
───────────────────────
Give you volume. Autocomplete proves a phrase is typed often enough for Google
to suggest it; it says nothing about how often. That limit is identical to
keywordchi's — its own volume columns are wired to a DataForSEO backend and
switched off, and no paid tier turns them on. Nothing here estimates a number.

ENCODING, WHICH COST AN HOUR
────────────────────────────
The endpoint answers Persian in windows-1256 unless you ask for UTF-8. Decoded
as UTF-8 it raises, and a probe that catches that as "no suggestions" reports a
working query as an empty one — the first run of this looked like throttling
and was a decode bug. &ie=utf-8&oe=utf-8 is not optional.

    python3 tools/suggest_harvest.py "کشتی کروز" "تور کروز"
    python3 tools/suggest_harvest.py --depth 2 --out data/suggest-2026-08.json "رزرو کروز"
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from keyword_demand import classify, norm  # noqa: E402

ENDPOINT = ("https://suggestqueries.google.com/complete/search"
            "?client=firefox&hl=fa&gl=ir&ie=utf-8&oe=utf-8")

# Deliberately wider than keywordchi's. تور/رزرو/بلیط/انواع are the additions
# that produced every commercial term its export was missing.
PREFIXES = ["خرید", "فروش", "قیمت", "بهترین", "مقایسه", "فرق", "اگر", "آموزش",
            "روش", "کدام", "تور", "رزرو", "هزینه", "بلیط", "انواع", "لیست",
            "ارزان", "لوکس", "شرایط", "مدت"]
SUFFIXES = ["از", "با", "در", "به", "برای", "چند", "چیست", "کجا", "و", "یا",
            "قیمت", "ارزان", "بدون ویزا", "نوروز", "1405"]
ALPHABET = list("ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی")


def suggest(query: str, timeout: int = 20) -> list[str]:
    """One call. Returns [] on any failure — the caller counts those."""
    try:
        r = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout), "-G",
             "--data-urlencode", f"q={query}", ENDPOINT],
            capture_output=True, timeout=timeout + 10)
        # bytes, not text: see the encoding note in the module docstring.
        return json.loads(r.stdout.decode("utf-8"))[1]
    except Exception:
        return []


def sweep(seed: str, delay: float) -> tuple[set[str], int, int]:
    """Base + prefix + suffix + alphabet permutations for one seed."""
    plan = ([seed]
            + [f"{p} {seed}" for p in PREFIXES]
            + [f"{seed} {s}" for s in SUFFIXES]
            + [f"{seed} {a}" for a in ALPHABET])
    out: set[str] = set()
    empty = 0
    for q in plan:
        hits = suggest(q)
        if not hits:
            empty += 1
        out.update(norm(h) for h in hits)
        time.sleep(delay)
    return out, len(plan), empty


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("seeds", nargs="+")
    ap.add_argument("--depth", type=int, default=1,
                    help="2 re-expands the terms found at depth 1 (expensive)")
    ap.add_argument("--expand-top", type=int, default=12,
                    help="at depth 2, how many depth-1 terms to re-expand")
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--filter", default="کروز",
                    help="keep only suggestions containing this; '' keeps all")
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parent.parent
                    / "data" / "suggest-cruise.json")
    args = ap.parse_args(argv)

    index: dict[str, dict[str, Any]] = {}
    if args.out.exists():
        prior = json.loads(args.out.read_text(encoding="utf-8"))
        index = {t["term"]: t for t in prior.get("terms", [])}
        print(f"{args.out.name}: {len(index)} terms already held\n")

    queries = empties = 0
    for seed in args.seeds:
        s = norm(seed)
        found, n, e = sweep(s, args.delay)
        queries += n
        empties += e

        if args.depth >= 2:
            # Re-expand the most promising depth-1 terms. Longer phrases are
            # the ones that branch, so prefer them over the bare head term.
            pool = sorted((t for t in found if args.filter in t),
                          key=lambda t: -len(t.split()))[:args.expand_top]
            for t in pool:
                more, n2, e2 = sweep(t, args.delay)
                found |= more
                queries += n2
                empties += e2

        kept = {t for t in found if args.filter in t} if args.filter else found
        new = [t for t in kept if t not in index]
        for t in kept:
            entry = index.setdefault(t, {"term": t, "seeds": [],
                                         "via": "google-suggest"})
            if s not in entry["seeds"]:
                entry["seeds"].append(s)
        print(f"  «{s}» · {n} queries → {len(found)} suggestions · "
              f"{len(kept)} on-topic · {len(new)} NEW")

    doc = {
        "source": "Google suggest endpoint (suggestqueries.google.com)",
        "source_kind": "autocomplete expansion — the same method keywordchi "
                       "resells, with a wider prefix list and no daily cap",
        "captured": datetime.date.today().isoformat(),
        "language": "fa-IR",
        "HAS_SEARCH_VOLUME": False,
        "note": ("Autocomplete proves a phrase is typed often enough to be "
                 "suggested. It carries no frequency, and none is estimated "
                 "here. Same limit as keywordchi, which has volume columns "
                 "wired to DataForSEO and switched off on every tier."),
        "seeds": sorted({s for t in index.values() for s in t["seeds"]}),
        "terms": [index[k] for k in sorted(index)],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    rows = classify(doc)
    usable = [r for r in rows if not r["reject"]]
    print(f"\n{queries} queries fired, {empties} returned nothing "
          f"({empties * 100 // max(queries, 1)}%)")
    print(f"{len(doc['terms'])} terms · {len(usable)} usable "
          f"({len(usable) * 100 // max(len(rows), 1)}%)")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
