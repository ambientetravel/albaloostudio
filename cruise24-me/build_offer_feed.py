#!/usr/bin/env python3
"""
Build offer.json (offer.v1) for cruise24.me: what the site sells, for the pipeline's writer.

Contract: orchestrator/bridge/OFFER-FEED-CONTRACT.md. One offering per durable product page,
never per sailing; no price of any kind; no digits in a summary (a count that is true today
is wrong next week, and a writer prints it as a fact); visa wording is never typed here.

Sources, all already on the site:
  - data/journeys-index.json  which lines and regions have live sailings
  - lines.html                each line's description (first sentence without a digit)
  - journeys.html             the region labels of the area filter

Every url is a page that exists: a filtered sailing list (journeys.html#<area>.<month>.<line>,
the format the page reads) or lines.html for lines booked on request.

    python3 build_offer_feed.py        # writes offer.json next to this script
"""

from __future__ import annotations

import collections
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "https://cruise24.me"
MAX_OFFERINGS = 60

# Order that matters to the business: the lines the site focuses on first (lines.html).
PRIORITY = ["explora-journeys", "silversea", "variety-cruises", "scenic",
            "seabourn", "regent-seven-seas", "ponant", "seadream", "sea-cloud", "star-clippers"]
ON_REQUEST = ["Celestyal", "AROYA Cruises", "MSC Cruises", "A-ROSA", "nicko cruises", "Amadeus River Cruises"]


def text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def summary_from(paragraph: str) -> str:
    """The first sentences without a digit, up to about 220 characters."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", text(paragraph)):
        # no counts, and no visa wording: the contract says visa text is derived, never typed
        if not sentence or re.search(r"\d", sentence.replace("Cruise24", "")) or re.search(r"(?i)visa|schengen", sentence):
            continue
        if sum(len(x) + 1 for x in out) + len(sentence) > 220 and out:
            break
        out.append(sentence)
    return " ".join(out)


def line_descriptions() -> dict[str, str]:
    page = (HERE / "lines.html").read_text(encoding="utf-8")
    found = {}
    for m in re.finditer(r'<article class="post">.*?<h3>(.*?)</h3>\s*<p>(.*?)</p>', page, re.S):
        name = text(m.group(1))
        # drop the "Current X sailings" link sentence; it is navigation, not description
        para = re.sub(r"<a [^>]*>.*?</a>[^<]*", "", m.group(2), flags=re.S)
        found[name] = summary_from(para)
    return found


def area_labels() -> dict[str, str]:
    page = (HERE / "journeys.html").read_text(encoding="utf-8")
    return {v: text(t) for v, t in re.findall(r'<option value="([a-z-]+)"[^>]*>([^<]+)', page)}


def main() -> int:
    sailings = json.loads((HERE / "data/journeys-index.json").read_text(encoding="utf-8"))
    desc, labels = line_descriptions(), area_labels()

    by_line: dict[str, dict] = {}
    for s in sailings:
        e = by_line.setdefault(s["k"], {"name": s["l"], "areas": collections.Counter(), "countries": collections.Counter()})
        e["areas"].update(s.get("a", []))
        e["countries"].update(c.lower() for c in s.get("f", []))

    offerings = []
    for k in PRIORITY + sorted(set(by_line) - set(PRIORITY)):
        if k not in by_line:
            continue
        e = by_line[k]
        summary = desc.get(e["name"]) or f"{e['name']} sailings booked through Cruise24, with the fare confirmed with the line before you commit."
        offerings.append({
            "slug": k, "title": e["name"], "type": "cruise", "summary": summary,
            "url": f"{BASE}/journeys.html#all.any.{k}",
            "regions": [a for a, _ in e["areas"].most_common()],
            "countries": [c for c, _ in e["countries"].most_common(8)],
        })
    for name in ON_REQUEST:
        if name in desc:
            offerings.append({
                "slug": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), "title": name, "type": "cruise",
                "summary": desc[name], "url": f"{BASE}/lines.html",
            })
    areas = collections.Counter(a for s in sailings for a in s.get("a", []))
    for a, _ in areas.most_common():
        label = labels.get(a, a)
        offerings.append({
            "slug": a, "title": label, "type": "destination",
            "summary": f"Cruises {'on' if a == 'rivers' else 'in'} {label}, from the lines Cruise24 books, with the fare confirmed with the line before you commit.",
            "url": f"{BASE}/journeys.html#{a}.any",
            "regions": [a],
        })

    # The contract's hard rules, asserted rather than hoped for.
    problems = []
    for o in offerings:
        if re.search(r"\d", o["summary"].replace("Cruise24", "")):   # the brand name is not a count
            problems.append(f"digit in summary: {o['slug']}")
        if re.search(r"(?i)visa[- ]free|no visa|without a visa|arabian gulf|boutimar|€|\bEUR\b|\$", o["summary"] + o["title"]):
            problems.append(f"forbidden wording: {o['slug']}")
        if not o["summary"]:
            problems.append(f"empty summary: {o['slug']}")
    if problems:
        print("offer.json NOT written:\n  " + "\n  ".join(problems))
        return 1

    feed = {
        "schema_version": "offer.v1",
        "site": "cruise24.me",
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "offerings": offerings[:MAX_OFFERINGS],
    }
    (HERE / "offer.json").write_text(json.dumps(feed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    kinds = collections.Counter(o["type"] for o in feed["offerings"])
    print(f"offer.json: {len(feed['offerings'])} offerings ({dict(kinds)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
