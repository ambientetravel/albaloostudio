#!/usr/bin/env python3
"""
variety_sync.py — Variety Cruises sailings from varietycruises.com itself.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Variety is not in CruiseHost. Its own cruise pages carry, for every departure, the line's
booking data (the "Events" list in the page's Next.js data): date, departure code, yacht,
and each cabin category with its EUR fare per person. This reads those pages and writes
data/sources/variety-sailings.json, which build_journeys.py prefers over the older
boutimar.ir catalogue copy.

What it takes, and only this:
  * route (in order)       from the page's schema.org TouristTrip itinerary
  * day titles             from the "Day N | Weekday" blocks
  * included / not included, as the line lists them
  * departures             date, code, yacht, lowest category fare in EUR (RateData.Price,
                           per person, port charges excluded) among categories with
                           cabins left; a departure with none left is marked soldOut
Photos are NOT fetched: the image CDN is a separate host (d2koisdtuu1wg4.cloudfront.net).

Usage:  python3 sync/variety_sync.py [--limit N]      then  python3 build_journeys.py
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import sys
import time
import urllib.request
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "sources", "variety-sailings.json")
SITE = "https://www.varietycruises.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"

# Variety's own destination grouping, by cruise slug keyword. Used for the region label only.
REGION = [
    (r"cape-verde", "Cape Verde"), (r"west-africa", "West Africa"), (r"seychelles", "Seychelles"),
    (r"tahiti", "Tahiti & French Polynesia"), (r"croatia|adriatic", "Croatia & Adriatic"),
    (r"dolce-vita|italy|malta", "Italy & Malta"), (r"turkey", "Greek Islands & Türkiye"),
    (r"ionian", "Ionian Islands"), (r"canal-crossing|byzantium", "Greece: Corinth Canal"), (r".", "Greek Islands"),
]


ROMAN = re.compile(r"(?i)^(i{1,3}|iv|vi{0,3}|ix|x)$")


def ship_name(raw) -> str:
    """'PANORAMA II' -> 'Panorama II' (not 'Panorama Ii')."""
    return " ".join(w.upper() if ROMAN.match(w) else w.capitalize() for w in (raw or "").strip().split())


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", errors="ignore")


def slugs() -> list[str]:
    return sorted(set(re.findall(r'href="/cruises/([a-z0-9-]+)"', get(SITE + "/cruises"))))


def flight_blob(page: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', page, re.S)
    return json.loads('"' + "".join(chunks).replace("\n", "\\n") + '"') if chunks else ""


def json_array_after(blob: str, key: str):
    """Parse the JSON array that follows `"key":` using bracket matching."""
    i = blob.find(f'"{key}":[')
    if i < 0:
        return []
    start = blob.index("[", i)
    depth, j, in_str, esc = 0, start, False, False
    while j < len(blob):
        ch = blob[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return json.loads(blob[start:j + 1])
        j += 1
    return []


def text_lines(page: str) -> list[str]:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    return [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n") if l.strip()]


def listed(lines, head, stop):
    try:
        i = lines.index(head)
    except ValueError:
        return []
    out = []
    for l in lines[i + 1:]:
        if l in stop:
            break
        out.append(l)
    return out


def parse(slug: str, page: str, today: str) -> dict | None:
    ld = None
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        d = json.loads(m.group(1))
        for node in (d if isinstance(d, list) else d.get("@graph", [d])):
            if isinstance(node, dict) and node.get("@type") == "TouristTrip":
                ld = node
    if not ld:
        return None
    route = [e["item"]["name"] for e in ld.get("itinerary", {}).get("itemListElement", [])
             if not re.match(r"Day \d+\s*\|", e["item"]["name"])]
    lines = text_lines(page)
    days = []
    for i, l in enumerate(lines):
        if not re.match(r"Day (\d+) \|", l) or not i:
            continue
        # The port heading is the capitalised line next to "Day N | Weekday": before it on most
        # pages, after it on some (croatia-island-hopping-montenegro). Anything else is prose.
        cands = [lines[i - 1]] + ([lines[i + 1]] if i + 1 < len(lines) else [])
        title = next((c for c in cands if c.isupper() and len(c) < 80), None)
        if title:
            days.append([title.title(), ""])
    if len(route) < 2:   # no usable schema.org route: take the ports from the day headings
        route = [p.strip() for d in days for p in re.split(r"\s+[–-]\s+", d[0]) if p.strip()]
    included = listed(lines, "Included", {"Not included"})
    excluded = listed(lines, "Not included", {"From"})
    deps = {}
    for ev in json_array_after(flight_blob(page), "Events"):
        e = ev.get("EventData") or {}
        beg = e.get("PackageBegDate") or e.get("BegDate")
        if not beg or beg < today:
            continue
        cats = (e.get("CategoryList") or {}).get("Category") or []
        cats = cats if isinstance(cats, list) else [cats]
        # The line's own "from" is the cheapest category that still has cabins (checked 27 Sep:
        # 9 Oct 2026 shows $4,390 = Category B; Category C, cheaper, has AvailUnits 0).
        eur = [c for c in cats if (c.get("RateData") or {}).get("PriceCurrency") == "EUR" and float(c["RateData"].get("Price") or 0) > 0]
        open_ = [c for c in eur if int(float(c.get("AvailUnits") or 0)) > 0]
        prices = [float(c["RateData"]["Price"]) for c in open_]
        deps[beg] = {"date": beg, "code": e.get("Code") or e.get("Flex01"), "ship": ship_name(e.get("FacilityName")),
                     "nights": int(float(e.get("Duration") or 0)), "priceFrom": int(min(prices)) if prices else None,
                     "soldOut": bool(eur) and not open_}
    if not deps:
        # Some pages carry no booking data, only the visible "Dates & Rates" list, priced in
        # US dollars. Take the dates and yacht from it; the EUR fare stays "on request"
        # rather than a converted figure the line never quoted.
        for i, l in enumerate(lines):
            if i + 3 < len(lines) and lines[i + 1] == "DATE" and lines[i + 3] == "SHIP":
                try:
                    d = datetime.strptime(l, "%d %b %Y").date().isoformat()
                except ValueError:
                    continue
                if d >= today:
                    deps.setdefault(d, {"date": d, "code": None, "ship": ship_name(lines[i + 2]), "nights": 0,
                                        "priceFrom": None, "soldOut": False})
        if not deps:
            return None
        nights_guess = max(len(route) - 1, 1)
        for d in deps.values():
            d["nights"] = nights_guess
    ships = list(dict.fromkeys(d["ship"] for d in deps.values() if d["ship"]))
    nights = max(set(d["nights"] for d in deps.values()), key=lambda n: sum(1 for d in deps.values() if d["nights"] == n))
    region = next(r for p, r in REGION if re.search(p, slug))
    return {"id": "VAR-" + slug, "slug": slug, "url": f"{SITE}/cruises/{slug}", "title": re.sub(r"\s+Cruise$", "", ld["name"]),
            "summary": ld.get("description", ""), "region": region, "ships": ships, "nights": nights, "route": route,
            "itinerary": days if len(days) >= 2 else [[p, ""] for p in route], "included": included, "notIncluded": excluded,
            "departures": sorted(deps.values(), key=lambda d: d["date"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    today = date.today().isoformat()
    todo = slugs()[: args.limit] if args.limit else slugs()
    out, skipped = [], []
    for n, s in enumerate(todo):
        if n:
            time.sleep(random.uniform(2.0, 4.0))
        try:
            rec = parse(s, get(f"{SITE}/cruises/{s}"), today)
        except Exception as e:
            skipped.append((s, str(e))); continue
        if rec:
            out.append(rec)
            fares = [d['priceFrom'] for d in rec['departures'] if d['priceFrom']]
            print(f"  {s:48} {len(rec['departures']):>3} departures  {', '.join(rec['ships'])}  " + (f"from €{min(fares):,}" if fares else "fare on request"), flush=True)
        else:
            skipped.append((s, "no future departures or no trip data"))
    json.dump({"_about": "Variety Cruises sailings read from varietycruises.com cruise pages (the line's own booking data). "
                         "priceFrom = cheapest cabin category with cabins left, EUR per person, port charges excluded; soldOut when none are left.",
               "source": "Variety Cruises", "synced": today, "sailings": out}, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"\n{len(out)} Variety itineraries, {sum(len(r['departures']) for r in out)} departures -> {OUT}")
    for s, why in skipped:
        print("  skipped", s, "-", why)


if __name__ == "__main__":
    main()
