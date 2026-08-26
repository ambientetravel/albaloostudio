#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Farsi cruise demand: what people actually type, filtered, and whether we exist for it.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHAT CHANGED, AND WHAT DID NOT
──────────────────────────────
keyword_gap.py says, correctly, that no search volume is obtainable for this
market. That is still true and this tool does not weaken it. What arrived on
25 Aug 2026 is a different thing that was also missing: a DEMAND LIST — 500
real query strings Google expands «سفر کروز» and «کشتی کروز» into, exported
from a paid keywordchi account.

The distinction matters and is easy to blur:

  * keyword_gap.py  → COMPETITOR CONSENSUS. What rivals build pages around.
  * this tool       → QUERY EXISTENCE. What searchers actually type.
  * neither         → VOLUME. keywordchi's workbooks contain zero numeric
                      cells. There is no popularity ordering in the source and
                      none is invented here.

So a term appearing below means Google has seen it typed enough to suggest it.
It does NOT mean it is typed more than a term that ranks lower in this file.

WHY THE FILTER IS THE POINT
───────────────────────────
Autocomplete expansion is indiscriminate. «کروز» in Persian is also a car
bumper (سپر کروز), a Land Cruiser, cruise control, and an anti-ship cruise
MISSILE (کروز ضد کشتی رعد/سجیل/نور). «سفر» alone dragged in fifteen queries
about day trips around Tehran. Fourteen more carry a «، استان …» suffix — those
are Google Business Profile local-pack lookups for a venue named "کشتی کروز" in
Yazd, Zanjan, Mashhad and other landlocked cities, not cruise intent at all.

Building pages against an unfiltered export means writing for people shopping
for a bumper. Every reject class below was found by reading the export, not
assumed, and each is named so the judgement can be argued with.

    python3 tools/keyword_demand.py
    python3 tools/keyword_demand.py --gsc            # add live position data
    python3 tools/keyword_demand.py --format json
    python3 tools/keyword_demand.py --show rejects   # audit what was dropped
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from datetime import timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The merged corpus: keywordchi's paid export plus the free suggest harvest.
# Either source alone is readable with --data.
DATA = Path(__file__).resolve().parent.parent / "data" / "cruise-demand-fa.json"

# Properties that could plausibly own a Farsi cruise query. boutimar.com is
# English-language and is included only to prove it is not competing here.
CRUISE_SITES = ["boutimar.ir", "cruisebaz.com", "cruise24.ir", "cruiseshop.ir",
                "boutimar.com"]

# ── Persian normalisation ───────────────────────────────────────────────────
# Load-bearing, and it has bitten this pipeline before. Farsi text arrives with
# Arabic yeh (ي) and kaf (ك) mixed into Persian yeh (ی) and kaf (ک) — visually
# near-identical, different code points. «كشتي كروز» and «کشتی کروز» are the
# same query to a reader and two different strings to Python.
#
# The keywordchi data file is stored already normalised. Search Console is NOT:
# it returns whatever the searcher typed. Comparing one against the other
# without folding both is how a term that ranks gets reported as ABSENT — the
# most damaging way this tool can be wrong, because absent is the finding
# people act on.
_AR2FA = {"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه",
          "أ": "ا", "إ": "ا", "آ": "ا"}
_DIAC = "".join(chr(c) for c in range(0x064B, 0x0653)) + "\u0670\u0640"


def norm(s: str) -> str:
    """Fold Arabic forms, strip diacritics/ZWNJ, Persian digits to ASCII."""
    s = unicodedata.normalize("NFC", str(s))
    s = "".join(_AR2FA.get(c, c) for c in s)
    s = "".join(c for c in s if c not in _DIAC)
    s = s.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    s = re.sub(r"[\u06F0-\u06F9]",
               lambda m: str(ord(m.group()) - 0x06F0), s)
    s = re.sub(r"[\u0660-\u0669]",
               lambda m: str(ord(m.group()) - 0x0660), s)
    return re.sub(r"\s+", " ", s).strip()


# ── Reject classes ──────────────────────────────────────────────────────────
# Wrong entity, wrong product, or seed bleed. Ordered by how badly a page built
# against them would waste effort.
REJECTS: list[tuple[str, str, list[str]]] = [
    ("car-part", "«کروز» as a car part — bumper, Land Cruiser, cruise control",
     ["سپر", "لندکروز", "لند کروز", "پرادو", "تویوتا", "کروز کنترل", "کروزکنترل"]),
    ("missile", "anti-ship cruise MISSILE (رعد/سجیل/نور) — same word, different weapon",
     ["کروز ضد کشتی", "موشک"]),
    ("warship", "naval vessels, not passenger ships",
     ["کشتی کروز جنگی", "کشتی کروز نظامی"]),
    ("day-trip", "seed bleed: matched «سفر» alone — one-day trips around Tehran",
     ["سفر یک روزه"]),
    ("local-pack", "Google Business Profile lookups for a venue named «کشتی کروز» "
                   "in a landlocked city — the «، استان …» suffix is the tell",
     ["استان خراسان", "استان یزد", "استان زنجان", "استان قزوین", "استان البرز",
      "استان گلستان", "استان فارس", "استان اذربایجان", "استان گیلان",
      "استان مازندران", "استان تهران", "منطقه 8", "تهرانپارس"]),
    ("domestic-boat", "lake and Caspian pleasure boats — a different product",
     ["چیتگر", "بابلسر", "رامسر", "نوشهر", "ملیکا", "میزبان", "بام لند", "امیرکبیر"]),
    ("toy-game", "Lego, Minecraft, toys",
     ["لگو", "لگویی", "اسباب بازی", "ماین کرافت", "بازی کشتی", "دیزنی"]),
    ("news-virus", "outbreak and disaster news cycles",
     ["هانتا", "ویروس", "غرق", "حادثه", "طوفان"]),
    ("celebrity", "entity noise — Ronaldo, the Shah era, political framing",
     ["رونالدو", "سفر علی کروز", "شیخ عرب", "کشتی کروز شاه", "زمان شاه",
      "جمهوری اسلامی"]),
    ("school", "a twelfth-grade geography textbook question", ["جغرافیا"]),
    ("arabic", "Arabic, not Persian", ["رحلات", "سفر فی "]),
    ("buy-a-ship", "buying or building an actual vessel — not a passenger",
     ["خرید کشتی کروز", "فروش کشتی", "ساخت کشتی", "کشتی کروز شخصی",
      "کشتی کروز خرید", "قیمت خرید یک کشتی", "برای خرید", "کروز کوچک"]),
    ("typo-frag", "fragments and misspellings with no coherent intent",
     ["کشتی ی کروز", "کروز شپ", "سیاره سفر", "کروز بسفر", "مدل کشتی", "کشتی ها کروز"]),
]

# ── Value clusters, first match wins ────────────────────────────────────────
# Order is deliberate: a query that names two ports is a route query even if it
# also says «قیمت», because the route is what the page has to be about.
CLUSTERS: list[tuple[str, str, list[str]]] = [
    ("route-pair", "names both ends of a sailing — the highest-intent shape there is",
     [r"از .+ به ", r"استانبول به", r"ترکیه به", r"ازمیر به", r"کیش به",
      r"بندرعباس به", r"بندر لنگه به", r"ایران به دبی", r"یونان ایتالیا"]),
    ("price", "asks what it costs",
     [r"قیمت", r"هزینه", r"نرخ", r"ارزان", r"چند تومن", r"چند میلیون", r"پول کشتی"]),
    ("tour-booking", "asks to buy — tour, ticket, booking, last minute",
     [r"^تور", r" تور", r"بلیط", r"رزرو", r"لست سکند", r"لحظه اخری"]),
    ("visa", "asks about visas — the one cluster where the truthful answer is "
             "unwelcome, and therefore ownable",
     [r"ویزا"]),
    ("date-season", "tied to a Persian calendar date — expires, must be maintained",
     [r"140[4-9]", r"نوروز", r"عید", r"بهترین زمان", r"تابستان", r"زمستان"]),
    ("persian-gulf", "Persian Gulf and Iranian islands",
     [r"خلیج فارس", r"خلیج ", r"کیش", r"قشم", r"بندرعباس", r"بندر لنگه", r"جزایر جنوب"]),
    # «یورو بیا» is NOT here, and that was a real error worth naming. It was
    # classified as a rival brand and reported to the owner twice as evidence
    # that "seven Iranian rivals have branded demand and you have none". It is
    # a Persian transliteration of MSC EURIBIA — a ship, not a company. There
    # are 242 Euribia sailings in the feed, 312 departures from €183, and
    # cruise24.ir/msc-euribia.html has been live and in the sitemap since the
    # 26 Aug deploy. The term is demand for our own product, misfiled as a
    # threat. A browsing agent found it by looking the name up; a pattern list
    # never could.
    ("competitor", "names a rival brand or the forum they are discussed on",
     [r"فلای تودی", r"علی بابا", r"نی نی سایت", r"الی گشت", r"طاها ?گشت",
      r"نیلفام", r"ژیوار", r"ایوار", r"eavar"]),
    ("what-country", "a single mass misconception — that «کشتی کروز» is one ship "
                     "belonging to one country",
     [r"برای کدام کشور", r"برای چه کشور", r"برای کجا", r"مال کجا", r"مال کدام",
      r"در کدام کشور", r"کدام کشور", r"کدوم کشور", r"کجاست", r"کجا میره",
      r"کجاها میره", r"ساخت کدام کشور", r"صاحب کشتی", r"کدام کشورها"]),
    ("definition", "what the word means, in Persian/English/German/Turkish",
     [r"چیست", r"یعنی چه", r"به چه معنا", r"به انگلیسی", r"به المانی", r"به ترکی",
      r"معنی"]),
    ("duration", "how long a sailing lasts, incl. the three-year world cruise story",
     [r"چند روز", r"چند ساله", r"سه ساله", r"3 ساله", r"یک ساله", r"یک ماهه",
      r"یک هفته", r"مدت سفر", r"دور دنیا", r"دوردنیا"]),
    ("specs", "capacity, decks, dimensions, food, facilities",
     [r"چند طبقه", r"چند متر", r"چند نفر", r"ظرفیت", r"گنجایش", r"نفری چند",
      r"امکانات", r"چه امکاناتی", r"غذاهای", r"داخل", r"شرایط سفر"]),
    ("superlative", "biggest, best, most expensive, most luxurious",
     [r"بهترین", r"بزرگترین", r"بزرگ ترین", r"گرانترین", r"لوکس", r"لاکچری",
      r"زیباترین", r"غول پیکر", r"مدرن", r"جدید"]),
    ("titanic", "compared against the Titanic — the reference point Iranians have",
     [r"تایتانیک"]),
    ("brand-ship", "names a line or a named ship",
     [r"msc", r"ام اس سی", r"aroya", r"اروی", r"کاستا", r"رویال", r"پرنسس",
      r"ویرجین", r"نروژی", r"فانتاسیا", r"ورتوسا", r"سیمفونی", r"شگفتی دریاها",
      r"نماد دریاها", r"رویای دریا", r"کارینا", r"رافائل", r"سانی",
      # MSC Euribia, as Persian actually writes it. Four spellings in the wild.
      r"یورو ?بیا", r"یوری ?بیا", r"یوریبیا", r"euribia"]),
    ("iran-supply", "asks whether Iran itself has cruise ships — it effectively "
                    "does not, and saying so plainly is the answer",
     [r"کشتی کروز ایران", r"کروز ایرانی", r"کروز در ایران", r"ساخت ایران",
      r"کشتی های کروز ایران", r"کروز شمال", r"کروز خزر", r"دریای خزر"]),
    ("jobs", "working on board — traffic without revenue for a tour operator",
     [r"استخدام", r"کار در", r"حقوق", r"درامد", r"درآمد", r"شغل", r"خدمه", r"ملوان"]),
    ("media", "photos, video, vlogs, travelogues",
     [r"عکس", r"فیلم", r"ویدیو", r"ولاگ", r"یوتیوب", r"پیج", r"سفرنامه"]),
]

# Commercial weight per cluster. Used only to order the report — it is an
# editorial judgement about revenue proximity, not a measurement.
WEIGHT = {"route-pair": 5, "tour-booking": 5, "price": 4, "date-season": 4,
          "visa": 4, "persian-gulf": 4, "brand-ship": 3, "competitor": 3,
          "duration": 2, "superlative": 2, "destination-generic": 2,
          "iran-supply": 2, "specs": 1, "what-country": 1, "definition": 1,
          "titanic": 1, "media": 1, "jobs": 0}

GEO = {"استانبول": "Istanbul", "ترکیه": "Türkiye", "دبی": "Dubai", "اروپا": "Europe",
       "مدیترانه": "Mediterranean", "خلیج فارس": "Persian Gulf", "کیش": "Kish",
       "قشم": "Qeshm", "ایتالیا": "Italy", "یونان": "Greece", "اسپانیا": "Spain",
       "فرانسه": "France", "انگلیس": "UK", "المان": "Germany", "نروژ": "Norway",
       "مصر": "Egypt", "عربستان": "Saudi", "عمان": "Oman", "قطر": "Qatar",
       "تایلند": "Thailand", "پوکت": "Phuket", "سنگاپور": "Singapore",
       "ژاپن": "Japan", "کارائیب": "Caribbean", "کاریبین": "Caribbean",
       "دور دنیا": "World", "مارماریس": "Marmaris", "کوش اداسی": "Kusadasi",
       "ازمیر": "Izmir", "بندرعباس": "Bandar Abbas", "خزر": "Caspian",
       "نیل": "Nile", "ویتنام": "Vietnam", "قبرس": "Cyprus"}


def _latin(s: str) -> bool:
    """Latin script that is not one of the cruise lines we do want to catch."""
    return bool(re.search(r"[A-Za-z]{4,}", s)) and not re.search(
        r"(msc|aroya|costa|royal|norwegian|celebrity|princess|viking|virgin|carnival)",
        s.lower())


def reject_of(term: str) -> str | None:
    if _latin(term):
        return "latin"
    for tag, _why, needles in REJECTS:
        if any(n in term for n in needles):
            return tag
    return None


def cluster_of(term: str) -> str:
    for name, _why, pats in CLUSTERS:
        if any(re.search(p, term) for p in pats):
            return name
    return "destination-generic"


def classify(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for t in doc["terms"]:
        term = t["term"]
        rej = reject_of(term)
        out.append({"term": term, "seeds": t.get("seeds", []),
                    "reject": rej,
                    "cluster": None if rej else cluster_of(term),
                    "geo": sorted({v for n, v in GEO.items() if n in term})})
    return out


# ── Search Console overlay (optional; needs the service account) ─────────────
def gsc_positions(domains: list[str]) -> dict[str, list[dict[str, Any]]]:
    import config
    import agent1_seo_scout as a1
    svc = a1.build_gsc_client()
    out: dict[str, list[dict[str, Any]]] = {}
    for d in domains:
        try:
            site = config.load_sites(only=[d], include_hold=True)[0]
        except Exception:
            continue
        end = (a1.utc_now() - timedelta(days=site.data_lag_days)).date()
        start = end - timedelta(days=site.lookback_days)
        rows = a1._search_analytics(svc, site.property_uri, start.isoformat(),
                                    end.isoformat(), ["query"])
        # norm() here, not at compare time: the data file is already
        # normalised, so folding both sides is what makes the match honest.
        out[d] = [{"q": norm((r.get("keys") or [""])[0]),
                   "raw": (r.get("keys") or [""])[0],
                   "imp": int(r.get("impressions", 0) or 0),
                   "clicks": int(r.get("clicks", 0) or 0),
                   "pos": round(float(r.get("position", 0) or 0), 1)}
                  for r in rows if r.get("keys")]
    return out


def overlay(rows: list[dict[str, Any]],
            gsc: dict[str, list[dict[str, Any]]]) -> None:
    """Attach each property's best position for every usable term, in place.

    MATCHING IS ONE-DIRECTIONAL, and the first version of this was not.

    A site is present for term T if Search Console recorded a query that IS T,
    or a longer query that CONTAINS T — surfacing for «قیمت تور کشتی کروز دبی»
    is fair evidence of presence on «کشتی کروز دبی».

    The reverse is NOT true and was the bug. Matching when the QUERY is a
    substring of the term means a site that surfaces for the bare phrase
    «کشتی کروز» is scored present for all 769 terms containing it. The first
    run reported cruisebaz.com present for 768 of 769 — 537 of those rows
    carrying the identical position 61.5, which is the signature of one short
    query smeared across the whole corpus. Ranking for a head term is not
    ranking for its long tail; that is the entire problem being measured.

    The matched queries are recorded so a bad match stays visible instead of
    hiding inside an aggregate.
    """
    for r in rows:
        if r["reject"]:
            continue
        r["gsc"] = {}
        for d, qs in gsc.items():
            hits = [x for x in qs if r["term"] in x["q"]]
            if not hits:
                r["gsc"][d] = None
                continue
            best = min(hits, key=lambda x: x["pos"])
            r["gsc"][d] = {"pos": best["pos"],
                           "imp": sum(h["imp"] for h in hits),
                           "clicks": sum(h["clicks"] for h in hits),
                           "queries": len(hits),
                           "exact": any(x["q"] == r["term"] for x in hits),
                           "matched": sorted({x["raw"] for x in hits})[:5]}


# ── Report ──────────────────────────────────────────────────────────────────
def report(doc: dict[str, Any], rows: list[dict[str, Any]],
           show: str, has_gsc: bool) -> None:
    rej = [r for r in rows if r["reject"]]
    use = [r for r in rows if not r["reject"]]

    print("# Farsi cruise demand — filtered\n")
    seeds = doc.get("seeds", [])
    print(f"Source: **{doc.get('source', 'unknown')}**"
          + (f" · captured {doc['captured']}" if doc.get("captured") else "")
          + (f" · {len(seeds)} seeds" if seeds else "") + "\n")
    print("**This file carries no search volume and none is estimated here.** "
          + doc.get("note", "") + " A term below exists as a query. Nothing in "
          "the source says how often it is typed, so nothing below is ordered "
          "by popularity.\n")

    print(f"| | Terms |\n|---|---:|")
    print(f"| Unique after normalisation | {len(rows)} |")
    print(f"| Rejected — not cruise-travel intent | {len(rej)} |")
    print(f"| **Usable** | **{len(use)}** |\n")

    print("## What was dropped, and why\n")
    print("| Class | Terms | Reason |\n|---|---:|---|")
    why = {t: w for t, w, _ in REJECTS}
    why["latin"] = "Latin-script rows that are not a cruise line"
    for tag, n in collections.Counter(r["reject"] for r in rej).most_common():
        print(f"| {tag} | {n} | {why.get(tag, '')} |")
    print()

    print("## Usable demand by cluster\n")
    if has_gsc:
        print("`present` counts terms at least one property surfaces for at all.\n")
    counts = collections.Counter(r["cluster"] for r in use)
    hdr = "| Cluster | Terms | Weight |" + (" Present | Absent |" if has_gsc else "")
    print(hdr)
    print("|---|---:|---:|" + ("---:|---:|" if has_gsc else ""))
    for c, n in sorted(counts.items(), key=lambda kv: (-WEIGHT.get(kv[0], 0), -kv[1])):
        line = f"| {c} | {n} | {WEIGHT.get(c, 0)} |"
        if has_gsc:
            here = [r for r in use if r["cluster"] == c]
            present = sum(1 for r in here
                          if any((r.get("gsc") or {}).values()))
            line += f" {present} | {len(here) - present} |"
        print(line)
    print()

    if show in ("rejects", "all"):
        print("## Every rejected term\n")
        for tag, _w, _n in REJECTS + [("latin", "", [])]:
            members = sorted(r["term"] for r in rej if r["reject"] == tag)
            if members:
                print(f"**{tag}** — " + " · ".join(members) + "\n")

    if show in ("terms", "all"):
        print("## Every usable term, by cluster\n")
        for c, _n in sorted(counts.items(),
                            key=lambda kv: (-WEIGHT.get(kv[0], 0), -kv[1])):
            members = sorted((r for r in use if r["cluster"] == c),
                             key=lambda r: r["term"])
            print(f"### {c} ({len(members)})\n")
            if has_gsc:
                print("| Term | " + " | ".join(CRUISE_SITES) + " |")
                print("|---|" + "---|" * len(CRUISE_SITES))
                for r in members:
                    cells = []
                    for d in CRUISE_SITES:
                        g = (r.get("gsc") or {}).get(d)
                        cells.append(f"{g['pos']}" if g else "—")
                    print(f"| {r['term']} | " + " | ".join(cells) + " |")
            else:
                for r in members:
                    print(f"- {r['term']}")
            print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--gsc", action="store_true",
                    help="overlay live Search Console positions (needs the "
                         "service account; in CI that is the GSC secret)")
    ap.add_argument("--show", choices=["summary", "terms", "rejects", "all"],
                    default="summary")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    doc = json.loads(Path(args.data).read_text(encoding="utf-8"))
    if doc.get("HAS_SEARCH_VOLUME"):
        # Guard against a future export that DOES carry volume being read by
        # this tool, which would silently keep printing "no volume here".
        print("This data file claims to carry search volume; keyword_demand.py "
              "is written for volume-free exports and would misreport it.",
              file=sys.stderr)
        return 2

    rows = classify(doc)
    has_gsc = False
    if args.gsc:
        try:
            overlay(rows, gsc_positions(CRUISE_SITES))
            has_gsc = True
        except Exception as exc:
            print(f"Search Console overlay unavailable ({type(exc).__name__}: "
                  f"{str(exc)[:120]}) — demand analysis below is unaffected, "
                  f"but position columns are omitted.", file=sys.stderr)

    if args.format == "json":
        print(json.dumps({"source": doc["source"], "captured": doc["captured"],
                          "has_search_volume": False, "has_gsc": has_gsc,
                          "terms": rows}, ensure_ascii=False, indent=1))
        return 0

    report(doc, rows, args.show, has_gsc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
