#!/usr/bin/env python3
"""
cruisehost_sync.py — cruise24.me inventory straight from CruiseHost CPX.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Same method as boutimar.ir's sync (ambientetravel/boutimarfarsi, data/cruisehost/), rebuilt
for cruise24.me so this site has NO runtime or build dependency on any .ir host:

    GET https://cpx.cruisec.net/api/Search/Results/json
          ?aid=204622&url=<KIND>/<Areas+…>/<Lines+…>/all/<FromMonthYear>/<ToMonthYear>/all&page=N

    aid 204622 is the Ambiente Tours CruiseHost contract. Auth is the aid alone.
    10 results per page, hard-locked. Filters only work in the url= path.
    `cruises` is a JSON array on page 1 and an object keyed by index on page 2+ (rows_of()).

Differences from the boutimar.ir sync, all deliberate:
  * English throughout. CruiseHost already answers in English, so there is no port
    translation table and no untranslated-port backlog.
  * Luxury and small-ship lines only (LINES). No MSC, Royal Caribbean, NCL.
  * Türkiye, Greece and Italy areas are walked first (AREAS order), everything else after.
  * The User-Agent names no company. Repo rule: no company name in outbound API headers.
  * Line codes are verified, not assumed: `--discover` asks CruiseHost how many sailings
    each candidate code returns and records the ones that answer in state.json. Walks use
    verified codes only, so a wrong guess costs one request, never a polluted inventory.
  * Ship photos are downloaded once into media/cruisehost/ so the site never hot-links.

The two safety rules are kept exactly:
  1. MERGE, NEVER REPLACE — a sailing from another source is never touched.
  2. PRUNE, NEVER DELETE  — elapsed departures are dropped; a sailing left with none is
     marked hidden, not removed. Only --full may hide a sailing CruiseHost stopped
     returning; --rolling leaves anything outside its slice alone.

Usage
    python3 sync/cruisehost_sync.py --selftest              # offline, proves mapping and rules
    python3 sync/cruisehost_sync.py --discover              # which line codes CruiseHost knows
    python3 sync/cruisehost_sync.py --check                 # 1 request: how big is the catalogue
    python3 sync/cruisehost_sync.py --full [--limit N]      # walk, report, write nothing
    python3 sync/cruisehost_sync.py --full --write          # ... and update the inventory
    python3 sync/cruisehost_sync.py --rolling 10 --write    # daily: 10 pages from the cursor
    then:  python3 build_journeys.py

Before enabling a schedule: confirm with CruiseHost that systematic retrieval under this
contract is permitted (the boutimar.ir README raises the same point).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

AID = "204622"
BASE = "https://cpx.cruisec.net/api/Search/Results/json"
COUNT = "https://cpx.cruisec.net/api/Search/count/json"
UA = "Mozilla/5.0 (compatible; inventory-sync/1.0; aid=%s)" % AID

# Candidate CruiseHost line codes. Only Explora_Journeys is proven (boutimar.ir walks it daily).
# The rest are the obvious spellings; --discover confirms or rejects each one.
LINES = {
    "Explora_Journeys":   {"name": "Explora Journeys", "kind": "SEA"},
    "Silversea_Cruises":  {"name": "Silversea", "kind": "SEA"},
    "Silversea":          {"name": "Silversea", "kind": "SEA"},
    "Variety_Cruises":    {"name": "Variety Cruises", "kind": "SEA"},
    "Scenic_Luxury_Cruises_Tours": {"name": "Scenic", "kind": "RIVER"},
    "Scenic_Cruises":     {"name": "Scenic", "kind": "RIVER"},
    "Scenic":             {"name": "Scenic", "kind": "RIVER"},
}

# Focus first: Türkiye, Greece and Italy sit in these three. Then everything else.
FOCUS_AREAS = ["Eastern_Mediterranean", "Central_Mediterranean_", "Mediterranean"]
OTHER_AREAS = ["Western_Mediterranean", "Southeurope", "Northeurope", "North_Europe", "Norwegian_Fjords",
               "Baltic_Sea_and_Baltic_States", "Iceland_Svalbard", "Westeurope", "Around_western_Europe",
               "Atlantic_Ocean_Europe", "Canary_Isles", "South_America", "Africa", "South_Africa", "Asia",
               "Far_East", "Indian_Ocean"]
AREAS = FOCUS_AREAS + OTHER_AREAS
RIVER_AREAS = ["all"]

OUT = os.path.join(ROOT, "data", "sources", "cruisehost-sailings.json")
STATE = os.path.join(HERE, "state.json")
REPORT = os.path.join(HERE, "last-report.json")
SHIPS_DIR = os.path.join(ROOT, "media", "cruisehost")
JITTER = (4.0, 10.0)
TIMEOUT = 25
PERSIAN_GULF_SRC = re.compile(r"arab(ian|ic)\s+gulf|persian\s+gulf", re.I)
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def window(today: date, months: int = 18):
    """CruiseHost wants 'July2026'-style bounds. From this month, `months` ahead."""
    y, m = today.year, today.month
    y2, m2 = y + (m - 1 + months) // 12, (m - 1 + months) % 12 + 1
    return f"{MONTHS[m - 1]}{y}", f"{MONTHS[m2 - 1]}{y2}"


def build_url(endpoint, kind, areas, lines, today, page=None):
    w0, w1 = window(today)
    path = "%s/%s/%s/all/%s/%s/all" % (kind, "+".join(areas), "+".join(lines), w0, w1)
    q = {"aid": AID, "url": path}
    if page:
        q["page"] = str(page)
    return endpoint + "?" + urllib.parse.urlencode(q, safe="/+")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def rows_of(payload):
    """Page 1: 'cruises' is a list. Page 2+: an object keyed by absolute index. Normalise."""
    c = (payload or {}).get("cruises")
    if isinstance(c, dict):
        return list(c.values())
    return list(c or [])


def region_en(text):
    t = (text or "").strip().replace("_", " ")
    return "Persian Gulf" if PERSIAN_GULF_SRC.search(t) else t


ROMAN = re.compile(r"(?i)^(i{1,3}|iv|vi{0,3}|ix|x)$")


def ship_name(raw):
    """'EXPLORA II' -> 'Explora II', 'silver vision' -> 'Silver Vision' (not 'Silver VIsion')."""
    return " ".join(w.upper() if ROMAN.match(w) else w.capitalize() for w in (raw or "").strip().split())


def map_row(c, line_names):
    """One CruiseHost result row (one departure) -> one sailing record. Field names as live."""
    route = [p.strip() for p in (c.get("route") or "").split(" - ") if p.strip()]
    dep = (c.get("departure_raw") or "").strip()
    price = int(float(c.get("priceUnformatted") or 0)) or None
    img = (c.get("shipImage") or "").strip()
    if img.startswith("//"):
        img = "https:" + img
    code = (c.get("cruiseLineID") or "").strip()
    return {
        "cruisehostId": (c.get("masterCruiseID") or "").strip(),
        "line": line_names.get(code, code),
        "lineCode": code,
        "ship": ship_name(c.get("ship")),
        "nights": int(c.get("duration") or 0),
        "region": region_en(c.get("cruiseArea")),
        "route": route,
        "departures": [{"date": dep, "priceFrom": price}] if dep else [],
        "priceFrom": price,
        "priceStrike": (c.get("price_strike") or "").strip() or None,
        "currency": (c.get("currency") or "EUR").strip(),
        "shipImageSource": img,
    }


def group(rows):
    """CruiseHost returns one row per departure; keep one sailing per masterCruiseID."""
    out = {}
    for r in rows:
        sid = r["cruisehostId"]
        if not sid:
            continue
        if sid not in out:
            out[sid] = r
            continue
        have = {d["date"] for d in out[sid]["departures"]}
        out[sid]["departures"] += [d for d in r["departures"] if d["date"] not in have]
    for s in out.values():
        s["departures"].sort(key=lambda d: d["date"])
        prices = [d["priceFrom"] for d in s["departures"] if d["priceFrom"]]
        s["priceFrom"] = min(prices) if prices else s["priceFrom"]
    return list(out.values())


def apply(existing, fetched, today, authoritative):
    """Merge fetched into existing. authoritative=True only for a complete walk."""
    fresh = {s["cruisehostId"]: s for s in fetched}
    stats = dict(new=0, updated=0, unchanged=0, expired=0, vanished=0, untouched=0)
    out = []
    for s in existing:
        sid = s["cruisehostId"]
        if sid in fresh:
            n = fresh.pop(sid)
            n["syncedAt"] = today
            stats["updated" if any(s.get(k) != n.get(k) for k in ("priceFrom", "departures", "route")) else "unchanged"] += 1
            s = n
        elif authoritative:
            s["hidden"] = True
            stats["vanished"] += 1
        else:
            stats["untouched"] += 1
        future = [d for d in s.get("departures", []) if d["date"] >= today]
        if len(future) != len(s.get("departures", [])):
            s["departures"] = future
        if not future and not s.get("hidden"):
            s["hidden"] = True
            stats["expired"] += 1
        out.append(s)
    for n in fresh.values():
        n["syncedAt"] = today
        out.append(n)
        stats["new"] += 1
    return out, stats


def fetch_ship_images(sailings, verbose=True):
    """Download each ship photo once into media/cruisehost/, point the record at it."""
    os.makedirs(SHIPS_DIR, exist_ok=True)
    for s in sailings:
        src = s.get("shipImageSource")
        if not src:
            continue
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", src.rsplit("/", 1)[-1]) or "ship.jpg"
        dst = os.path.join(SHIPS_DIR, name)
        if not os.path.exists(dst):
            try:
                req = urllib.request.Request(src, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r, open(dst + ".part", "wb") as f:
                    f.write(r.read())
                os.replace(dst + ".part", dst)
            except Exception as e:
                if verbose:
                    print("  ! ship image %s: %s" % (src, e), file=sys.stderr)
                continue
        s["shipImage"] = "media/cruisehost/" + name


def verified_lines(state):
    v = state.get("verified") or {}
    return {k: LINES[k] for k in v if k in LINES and v[k] > 0}


def discover(today):
    """One count request per candidate code. Records what CruiseHost actually answers."""
    state = load_json(STATE, {})
    found = {}
    for code, meta in LINES.items():
        areas = AREAS if meta["kind"] == "SEA" else RIVER_AREAS
        try:
            n = int(get_json(build_url(COUNT, meta["kind"], areas, [code], today)).get("allentries") or 0)
        except Exception as e:
            print("  %-30s %-6s error: %s" % (code, meta["kind"], e))
            continue
        found[code] = n
        print("  %-30s %-6s %6d sailings" % (code, meta["kind"], n))
        time.sleep(random.uniform(1.5, 3.0))
    state["verified"] = found
    state["discoveredAt"] = today
    json.dump(state, open(STATE, "w"), indent=1)
    print("verified:", {k: v for k, v in found.items() if v})


def walk(today, lines, max_pages=None, pages_wanted=None, verbose=True):
    """Walk each kind (SEA, RIVER) separately. Returns rows, total, and the page count per kind."""
    rows, total, pages_by_kind = [], 0, {}
    for kind in ("SEA", "RIVER"):
        codes = [c for c, m in lines.items() if m["kind"] == kind]
        if not codes:
            continue
        areas = AREAS if kind == "SEA" else RIVER_AREAS
        first = get_json(build_url(BASE, kind, areas, codes, today, 1))
        pages = int(first.get("pages") or 0)
        total += int(first.get("allentries") or 0)
        pages_by_kind[kind] = pages
        want = list(range(1, pages + 1)) if pages_wanted is None else [p for p in pages_wanted.get(kind, []) if p <= pages]
        if max_pages:
            want = want[:max_pages]
        if 1 in want:
            rows += rows_of(first)
        for n, p in enumerate([p for p in want if p != 1]):
            time.sleep(random.uniform(*JITTER))
            try:
                rows += rows_of(get_json(build_url(BASE, kind, areas, codes, today, p)))
            except Exception as e:
                print("  ! %s page %d: %s" % (kind, p, e), file=sys.stderr)
            if verbose and n and n % 10 == 0:
                print("  ... %s %d/%d pages" % (kind, n, len(want)))
    return rows, total, pages_by_kind


def selftest():
    today = "2026-09-27"
    names = {"EXP": "Explora Journeys", "SIL": "Silversea"}
    p1 = {"allentries": 3, "pages": 2, "cruises": [
        {"masterCruiseID": "A1", "cruiseLineID": "EXP", "ship": "EXPLORA II", "duration": "7", "cruiseArea": "Eastern_Mediterranean",
         "route": "Piraeus, Athens - Mykonos - Kusadasi, Ephesos - Piraeus, Athens", "departure_raw": "2026-10-03", "priceUnformatted": "4720.00", "shipImage": "//images.cruisec.net/images/ships/ships/M2.jpg"},
        {"masterCruiseID": "A1", "cruiseLineID": "EXP", "ship": "EXPLORA II", "duration": "7", "cruiseArea": "Eastern_Mediterranean",
         "route": "Piraeus, Athens - Mykonos - Kusadasi, Ephesos - Piraeus, Athens", "departure_raw": "2026-10-10", "priceUnformatted": "4390"}]}
    p2 = {"cruises": {"10": {"masterCruiseID": "B2", "cruiseLineID": "SIL", "ship": "silver nova", "duration": "10", "cruiseArea": "Arabian Gulf",
                             "route": "Dubai - Doha - Dubai", "departure_raw": "2027-01-05", "priceUnformatted": "8900"}}}
    rows = rows_of(p1) + rows_of(p2)
    assert all(isinstance(r, dict) for r in rows), "rows_of must yield records, not index keys"
    got = group([map_row(r, names) for r in rows])
    a = next(s for s in got if s["cruisehostId"] == "A1"); b = next(s for s in got if s["cruisehostId"] == "B2")
    assert [d["date"] for d in a["departures"]] == ["2026-10-03", "2026-10-10"] and a["priceFrom"] == 4390, a
    assert a["ship"] == "Explora II" and a["shipImageSource"].startswith("https://"), a
    assert b["region"] == "Persian Gulf" and b["line"] == "Silversea" and b["ship"] == "Silver Nova", b
    assert ship_name("SILVER VISION") == "Silver Vision" and ship_name("explora iv") == "Explora IV"
    existing = [dict(a, departures=[{"date": "2026-09-01", "priceFrom": 1}]), {"cruisehostId": "C3", "departures": [{"date": "2027-02-01", "priceFrom": 5}]}]
    merged, st = apply([dict(x) for x in existing], [b], today, authoritative=False)
    c3 = next(s for s in merged if s["cruisehostId"] == "C3")
    assert not c3.get("hidden") and st["untouched"] == 2 and st["new"] == 1, (st, c3)
    a_old = next(s for s in merged if s["cruisehostId"] == "A1")
    assert a_old.get("hidden") and a_old["departures"] == [], a_old          # elapsed -> hidden, never deleted
    merged, st = apply([dict(x) for x in existing], [b], today, authoritative=True)
    assert next(s for s in merged if s["cruisehostId"] == "C3").get("hidden") and st["vanished"] == 2, st
    assert len(merged) == 3, "nothing is ever deleted"
    assert not re.search(r"ambiente|boutimar|albaloo|cruise24", UA, re.I), "no company name in outbound headers"
    u = build_url(BASE, "SEA", AREAS[:2], ["Explora_Journeys"], date(2026, 9, 27), 2)
    assert "url=SEA/Eastern_Mediterranean+Central_Mediterranean_/Explora_Journeys/all/September2026/March2028/all" in u and "page=2" in u, u
    print("selftest OK: page shapes, grouping, Persian Gulf, merge/prune, rolling vs full, neutral UA, URL form")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--rolling", type=int, metavar="PAGES")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    today = date.today()

    if args.selftest:
        return selftest()
    if args.discover:
        return discover(today)

    state = load_json(STATE, {})
    lines = verified_lines(state)
    if not lines:
        sys.exit("no verified line codes yet: run --discover first")
    names = {}
    if args.check:
        _, total, pages = walk(today, lines, max_pages=1, verbose=False)
        print("catalogue: %d sailings, pages %s, lines %s" % (total, pages, list(lines)))
        return
    if args.write and args.full and args.limit:
        sys.exit("--write refuses a truncated --full walk")

    if args.rolling:
        cur = state.get("cursor") or {}
        _, _, pages = walk(today, lines, max_pages=1, verbose=False)
        want = {k: [((int(cur.get(k, 1)) - 1 + i) % n) + 1 for i in range(min(args.rolling, n))] for k, n in pages.items() if n}
        rows, total, _ = walk(today, lines, pages_wanted=want)
        state["cursor"] = {k: ((want[k][-1]) % pages[k]) + 1 for k in want}
        authoritative = False
    else:
        rows, total, _ = walk(today, lines, max_pages=args.limit)
        authoritative = args.limit is None

    fetched = group([map_row(r, names) for r in rows])
    for s in fetched:          # CruiseHost's line code -> our display name, from the verified table
        s["line"] = next((m["name"] for c, m in lines.items() if s["lineCode"] and s["lineCode"].lower() in c.lower()), s["line"])
    existing = load_json(OUT, {}).get("sailings", [])
    merged, stats = apply(existing, fetched, today.isoformat(), authoritative)
    report = {"ran": today.isoformat(), "mode": "rolling" if args.rolling else "full", "catalogue": total, "rows": len(rows), "sailings": len(fetched), **stats}
    print(json.dumps(report))
    json.dump(report, open(REPORT, "w"), indent=1)
    if args.write:
        fetch_ship_images(merged)
        tmp = OUT + ".tmp"
        json.dump({"_about": "CruiseHost CPX, aid %s, synced directly by sync/cruisehost_sync.py" % AID,
                   "snapshotDate": today.isoformat(), "sailings": merged}, open(tmp, "w"), ensure_ascii=False, indent=1)
        os.replace(tmp, OUT)
        json.dump(state, open(STATE, "w"), indent=1)
        print("wrote", OUT, "— now run: python3 build_journeys.py")


if __name__ == "__main__":
    main()
