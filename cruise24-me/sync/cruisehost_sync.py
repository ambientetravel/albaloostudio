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
    python3 sync/cruisehost_sync.py --rolling 10 --write    # 10 pages per family from the cursor
    python3 sync/cruisehost_sync.py --spread 7 --write      # daily: 1/7 of every family, so the
                                                            # whole catalogue is refreshed once a week
    then:  python3 build_journeys.py

Spread (the scheduled mode, .github/workflows/cruise24-inventory-sync.yml): CruiseHost sees
about 40 requests a day, 3-6 s apart, instead of ~250 in one go. A slice is pages, and pages
drift as departures sail and new ones appear, so a sailing can be missed in one cycle. It is
only hidden once it has not been seen for --stale-after days (default: three cycles), which
is the rolling stand-in for the vanished-sailing rule a --full walk applies.

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
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

AID = "204622"
BASE = "https://cpx.cruisec.net/api/Search/Results/json"
COUNT = "https://cpx.cruisec.net/api/Search/count/json"
UA = "Mozilla/5.0 (compatible; inventory-sync/1.0; aid=%s)" % AID

# Lines, as CruiseHost spells them in the url= path. Codes and names confirmed against the
# catalogue's own line list (Search/count/json -> cruiselines) on 2026-09-27.
#   scope "all"   -> every destination       (the lines this site is built around)
#   scope "focus" -> Mediterranean only      (similar lines, grown into more areas later)
# Variety Cruises is NOT in CruiseHost; its sailings come from its own catalogue.
LINES = {
    "Explora_Journeys":      {"name": "Explora Journeys",  "code": "EXP", "kinds": ["SEA"],          "scope": "all"},
    "Silversea":             {"name": "Silversea",         "code": "SSE", "kinds": ["SEA"],          "scope": "all"},
    "Scenic_Luxury_Cruises": {"name": "Scenic",            "code": "SLC", "kinds": ["SEA", "RIVER"], "scope": "all"},
    "Seabourn_Cruise_Line":  {"name": "Seabourn",          "code": "SBN", "kinds": ["SEA"],          "scope": "focus"},
    "Regent_Seven_Seas":     {"name": "Regent Seven Seas", "code": "REG", "kinds": ["SEA"],          "scope": "focus"},
    "PONANT":                {"name": "Ponant",            "code": "COM", "kinds": ["SEA"],          "scope": "focus"},
    "Seadream":              {"name": "SeaDream",          "code": "SDM", "kinds": ["SEA"],          "scope": "focus"},
    "Sea_Cloud":             {"name": "Sea Cloud",         "code": "SCD", "kinds": ["SEA"],          "scope": "focus"},
    "Star_Clipper":          {"name": "Star Clippers",     "code": "CLP", "kinds": ["SEA"],          "scope": "focus"},
}
CODE_NAME = {m["code"]: m["name"] for m in LINES.values()}

# The Mediterranean, where Türkiye, Greece and Italy sit. "all" means every area.
FOCUS_AREAS = ["Eastern_Mediterranean", "Central_Mediterranean_", "Mediterranean"]
RIVER_AREAS = ["all"]

OUT = os.path.join(ROOT, "data", "sources", "cruisehost-sailings.json")
STATE = os.path.join(HERE, "state.json")
REPORT = os.path.join(HERE, "last-report.json")
SHIPS_DIR = os.path.join(ROOT, "media", "cruisehost")
JITTER = (3.0, 6.0)
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
        "line": CODE_NAME.get(code, line_names.get(code, code)),
        "kind": c.get("_kind", "SEA"),
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


def itinerary_id(r):
    import hashlib
    key = "|".join((r["lineCode"], r["ship"], " - ".join(r["route"]), str(r["nights"]), r.get("kind", "SEA")))
    return "%s-%s" % (r["lineCode"] or "CH", hashlib.sha1(key.encode()).hexdigest()[:8])


def group(rows):
    """CruiseHost returns one row per departure. Keep one record per itinerary
    (same line, ship, route, nights) with every departure and its own CruiseHost id."""
    out = {}
    for r in rows:
        if not r["cruisehostId"] or not r["route"]:
            continue
        iid = itinerary_id(r)
        dep = [dict(d, cruisehostId=r["cruisehostId"]) for d in r["departures"]]
        if iid not in out:
            out[iid] = dict(r, itineraryId=iid, departures=dep)
            continue
        have = {d["date"] for d in out[iid]["departures"]}
        out[iid]["departures"] += [d for d in dep if d["date"] not in have]
    for s in out.values():
        s["departures"].sort(key=lambda d: d["date"])
        prices = [d["priceFrom"] for d in s["departures"] if d["priceFrom"]]
        s["priceFrom"] = min(prices) if prices else None
        s["cruisehostId"] = s["itineraryId"]
    return list(out.values())


def apply(existing, fetched, today, authoritative, stale_before=None):
    """Merge fetched into existing. authoritative=True only for a complete walk.
    stale_before (ISO date, partial walks only): a sailing not refreshed since then is hidden,
    since a sailing CruiseHost dropped is otherwise never noticed by a rolling walk."""
    fresh = {s["cruisehostId"]: s for s in fetched}
    stats = dict(new=0, updated=0, unchanged=0, expired=0, vanished=0, untouched=0, stale=0)
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
            if stale_before and (s.get("syncedAt") or "") < stale_before and not s.get("hidden"):
                s["hidden"] = True
                stats["stale"] += 1
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
    """Only lines, and only kinds, that --discover confirmed."""
    v = state.get("verified") or {}
    return {k: dict(LINES[k], kinds=[kd for kd in LINES[k]["kinds"] if (v.get(k) or {}).get(kd)]) for k in v if k in LINES}


def discover(today):
    """One count request per line and kind. An unknown slug makes CruiseHost silently drop the
    filter and count the WHOLE catalogue (53,262 on 2026-09-27), so a slug only counts as
    verified when the url CruiseHost echoes back still contains it."""
    state = load_json(STATE, {})
    found = {}
    for slug, meta in LINES.items():
        for kind in meta["kinds"]:
            areas = ["all"] if meta["scope"] == "all" else FOCUS_AREAS
            try:
                d = get_json(build_url(COUNT, kind, areas, [slug], today))
            except Exception as e:
                print("  %-24s %-5s error: %s" % (slug, kind, e)); continue
            n, echo = int(d.get("count") or 0), str(d.get("url") or "")
            ok = slug in echo.split("/")[2].split("+") if echo.count("/") >= 2 else False
            print("  %-24s %-5s %6d departures  %s" % (slug, kind, n, "ok" if ok else "REJECTED: CruiseHost ignored this name (echo %s)" % echo))
            if ok:
                found.setdefault(slug, {})[kind] = n
            time.sleep(random.uniform(1.5, 3.0))
    state["verified"] = found
    state["discoveredAt"] = today.isoformat()
    json.dump(state, open(STATE, "w"), indent=1)
    print("verified:", found)


def groups(lines):
    """(kind, areas, [slugs]) per request family: one URL per kind and scope."""
    out = []
    for kind in ("SEA", "RIVER"):
        for scope in ("all", "focus"):
            slugs = [k for k, m in lines.items() if kind in m["kinds"] and m["scope"] == scope]
            if slugs:
                out.append((kind, ["all"] if scope == "all" else FOCUS_AREAS, slugs))
    return out


def walk(today, lines, max_pages=None, pick=None, verbose=True):
    """Walk every request family. Returns rows (each tagged with its kind), total, pages per family.
    pick(family, pages) -> the page numbers to fetch; page 1 is always fetched, because it is
    the request that says how many pages there are."""
    rows, total, pages_by = [], 0, {}
    for kind, areas, slugs in groups(lines):
        fam = kind + ":" + "+".join(slugs)
        first = get_json(build_url(BASE, kind, areas, slugs, today, 1))
        echo = str((first.get("search") or {}).get("url") if isinstance(first.get("search"), dict) else first.get("url") or "")
        pages = int(first.get("pages") or 0)
        total += int(first.get("allentries") or 0)
        pages_by[fam] = pages
        want = list(range(1, pages + 1)) if pick is None else [p for p in pick(fam, pages) if 1 <= p <= pages]
        if max_pages:
            want = want[:max_pages]
        tag = lambda rs: [dict(r, _kind=kind) for r in rs]
        rows += tag(rows_of(first))   # fetched anyway for the page count, so never wasted
        for n, p in enumerate([p for p in want if p != 1]):
            time.sleep(random.uniform(*JITTER))
            try:
                rows += tag(rows_of(get_json(build_url(BASE, kind, areas, slugs, today, p))))
            except Exception as e:
                print("  ! %s page %d: %s" % (fam, p, e), file=sys.stderr)
            if verbose and n and n % 10 == 0:
                print("  ... %s %d/%d pages, %d rows" % (fam, n, len(want), len(rows)), flush=True)
        if verbose:
            print("  %s: %d pages, %d rows so far" % (fam, pages, len(rows)), flush=True)
    return rows, total, pages_by


def slice_size(pages: int, days: int) -> int:
    """Pages per run so that `days` runs cover every page of a family once."""
    return max(1, -(-pages // max(1, days)))


def rolling_pages(start: int, pages: int, size: int) -> list[int]:
    """`size` page numbers from `start`, wrapping round at `pages`."""
    if pages <= 0:
        return []
    start = (start - 1) % pages + 1
    return [((start - 1 + i) % pages) + 1 for i in range(min(size, pages))]


def selftest():
    today = "2026-09-27"
    names = {}
    p1 = {"allentries": 3, "pages": 2, "cruises": [
        {"masterCruiseID": "A1", "cruiseLineID": "EXP", "ship": "EXPLORA II", "duration": "7", "cruiseArea": "Eastern_Mediterranean",
         "route": "Piraeus, Athens - Mykonos - Kusadasi, Ephesos - Piraeus, Athens", "departure_raw": "2026-10-03", "priceUnformatted": "4720.00", "shipImage": "//images.cruisec.net/images/ships/ships/M2.jpg"},
        {"masterCruiseID": "A1", "cruiseLineID": "EXP", "ship": "EXPLORA II", "duration": "7", "cruiseArea": "Eastern_Mediterranean",
         "route": "Piraeus, Athens - Mykonos - Kusadasi, Ephesos - Piraeus, Athens", "departure_raw": "2026-10-10", "priceUnformatted": "4390"}]}
    p2 = {"cruises": {"10": {"masterCruiseID": "B2", "cruiseLineID": "SSE", "ship": "silver nova", "duration": "10", "cruiseArea": "Arabian Gulf",
                             "route": "Dubai - Doha - Dubai", "departure_raw": "2027-01-05", "priceUnformatted": "8900"}}}
    rows = rows_of(p1) + rows_of(p2)
    assert all(isinstance(r, dict) for r in rows), "rows_of must yield records, not index keys"
    got = group([map_row(r, names) for r in rows])
    a = next(s for s in got if s["lineCode"] == "EXP"); b = next(s for s in got if s["lineCode"] == "SSE")
    assert len(got) == 2 and a["cruisehostId"].startswith("EXP-") and [d["cruisehostId"] for d in a["departures"]] == ["A1", "A1"], got
    assert [d["date"] for d in a["departures"]] == ["2026-10-03", "2026-10-10"] and a["priceFrom"] == 4390, a
    assert a["ship"] == "Explora II" and a["shipImageSource"].startswith("https://"), a
    assert b["region"] == "Persian Gulf" and b["line"] == "Silversea" and b["ship"] == "Silver Nova", b
    assert ship_name("SILVER VISION") == "Silver Vision" and ship_name("explora iv") == "Explora IV"
    existing = [dict(a, departures=[{"date": "2026-09-01", "priceFrom": 1}]), {"cruisehostId": "C3", "departures": [{"date": "2027-02-01", "priceFrom": 5}]}]
    aid = a["cruisehostId"]
    merged, st = apply([dict(x) for x in existing], [b], today, authoritative=False)
    c3 = next(s for s in merged if s["cruisehostId"] == "C3")
    assert not c3.get("hidden") and st["untouched"] == 2 and st["new"] == 1, (st, c3)
    a_old = next(s for s in merged if s["cruisehostId"] == aid)
    assert a_old.get("hidden") and a_old["departures"] == [], a_old          # elapsed -> hidden, never deleted
    merged, st = apply([dict(x) for x in existing], [b], today, authoritative=True)
    assert next(s for s in merged if s["cruisehostId"] == "C3").get("hidden") and st["vanished"] == 2, st
    assert len(merged) == 3, "nothing is ever deleted"
    # a partial walk hides only what has gone unseen past the cutoff, and never deletes it
    seen = dict(existing[1], cruisehostId="C4", syncedAt="2026-09-20")
    old = dict(existing[1], cruisehostId="C5", syncedAt="2026-08-01")
    merged, st = apply([seen, old], [], today, authoritative=False, stale_before="2026-09-06")
    assert st["stale"] == 1 and len(merged) == 2, st
    assert not merged[0].get("hidden") and merged[1].get("hidden"), merged
    back = {k: v for k, v in old.items() if k != "hidden"}
    merged, st = apply([dict(old, hidden=True)], [back], today, authoritative=False, stale_before="2026-09-06")
    assert not merged[0].get("hidden") and st["updated"] + st["unchanged"] == 1, "seen again -> shown again"
    # spread: every page of every family exactly once per cycle, about 1/7 a day
    for n in (1, 6, 39, 106, 109):
        cur, cover = 1, []
        for _ in range(7):
            got_p = rolling_pages(cur, n, slice_size(n, 7))
            cover += got_p
            cur = got_p[-1] % n + 1
        assert sorted(set(cover)) == list(range(1, n + 1)), (n, cover)
        assert len(cover) - n < 7, ("a cycle refetches at most a few pages", n, len(cover))
    assert slice_size(106, 7) + slice_size(39, 7) + slice_size(109, 7) == 38
    assert not re.search(r"ambiente|boutimar|albaloo|cruise24", UA, re.I), "no company name in outbound headers"
    u = build_url(BASE, "SEA", FOCUS_AREAS[:2], ["Explora_Journeys"], date(2026, 9, 27), 2)
    assert "url=SEA/Eastern_Mediterranean+Central_Mediterranean_/Explora_Journeys/all/September2026/March2028/all" in u and "page=2" in u, u
    print("selftest OK: page shapes, grouping, Persian Gulf, merge/prune, rolling vs full, stale hiding, weekly spread, neutral UA, URL form")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--rolling", type=int, metavar="PAGES")
    ap.add_argument("--spread", type=int, metavar="DAYS", help="refresh 1/DAYS of every family per run")
    ap.add_argument("--stale-after", type=int, metavar="DAYS", help="partial walks: hide a sailing not seen for DAYS (default 3 x --spread, else off)")
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

    stale_before = None
    if args.rolling or args.spread:
        cur = state.get("cursor") or {}
        chosen = {}

        def pick(fam, n):
            size = args.rolling or slice_size(n, args.spread)
            chosen[fam] = (n, rolling_pages(int(cur.get(fam, 1)), n, size))
            return chosen[fam][1]

        rows, total, pages = walk(today, lines, pick=pick)
        state["cursor"] = {**cur, **{k: (want[-1] % n) + 1 for k, (n, want) in chosen.items() if want}}
        authoritative = False
        days = args.stale_after if args.stale_after is not None else (3 * args.spread if args.spread else 0)
        if days:
            stale_before = (today - timedelta(days=days)).isoformat()
    else:
        rows, total, _ = walk(today, lines, max_pages=args.limit)
        authoritative = args.limit is None

    fetched = group([map_row(r, names) for r in rows])
    existing = load_json(OUT, {}).get("sailings", [])
    merged, stats = apply(existing, fetched, today.isoformat(), authoritative, stale_before)
    mode = "spread/%d" % args.spread if args.spread else "rolling" if args.rolling else "full"
    report = {"ran": today.isoformat(), "mode": mode, "catalogue": total, "rows": len(rows), "sailings": len(fetched), **stats}
    if args.rolling or args.spread:
        report["slice"] = {k: "%d of %d pages, from %d" % (len(w), n, w[0]) for k, (n, w) in chosen.items() if w}
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
