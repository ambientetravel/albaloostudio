#!/usr/bin/env python3
"""Write an owner idea into orchestrator/ideas/ (see ideas/README.md).

    python3 tools/add_idea.py --title "Cruise and walking holidays in Europe" \
        --note "Crociere Europe offers cruises combined with guided walks" \
        --source-kind email --source-from "Crociere Europe" \
        --site cruise24.me="walking cruises europe" --site cruisebaz.com="سفر دریایی و پیاده‌روی در اروپا"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import agent1_seo_scout as a1  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--note", action="append", default=[], help="a fact from the source; repeatable")
    ap.add_argument("--source-kind", default="owner", help="email | voice | photo | link | owner")
    ap.add_argument("--source-from", default="")
    ap.add_argument("--site", action="append", default=[],
                    help='domain="search phrase" (optionally domain="phrase|angle"); repeatable')
    ap.add_argument("--image", action="append", default=[])
    a = ap.parse_args()
    known = {s.domain for s in config.load_sites(include_hold=True)}
    domains: dict[str, dict[str, str]] = {}
    for spec in a.site:
        dom, _, rest = spec.partition("=")
        if dom not in known:
            sys.exit(f"unknown domain {dom!r}; known: {', '.join(sorted(known))}")
        phrase, _, angle = rest.strip().strip('"').partition("|")
        if not phrase.strip():
            sys.exit(f"{dom}: empty search phrase")
        domains[dom] = {"query": phrase.strip(), **({"angle": angle.strip()} if angle.strip() else {})}
    if not domains:
        sys.exit("give at least one --site domain=\"search phrase\"")
    today = a1.utc_now().date().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", a.title.lower()).strip("-")[:50] or "idea"
    idea = {"id": f"{today}-{slug}", "status": "new", "created": today, "title": a.title,
            "notes": a.note, "source": {"kind": a.source_kind, "from": a.source_from, "date": today},
            "domains": domains, **({"images": a.image} if a.image else {})}
    out = a1.IDEAS_DIR / f"{idea['id']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(idea, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
