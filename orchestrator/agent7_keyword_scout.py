#!/usr/bin/env python3
"""
Agent 7 — Keyword & Geo Scout.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Answers two questions Agent 1 does not:

  1. WHERE IN THE WORLD does each site actually surface, and at what position?
  2. WHAT SHOULD WE TARGET that we do not rank for at all yet?

Question 1 needs no new credential. Agent 1 already queries Search Console with
the ["query","country"] dimension pair and then keeps only `countries[0][0]` —
the single top country — discarding the rest. boutimar.com returns 768
query×country rows across 74 countries on every run. This agent reads that same
data properly.

Question 2 is where Keyword Planner comes in, and where the honesty has to be
loudest, so read `KEYWORD_PLANNER_REALITY` below before wiring anything to it.

    python3 agent7_keyword_scout.py                     # every active site
    python3 agent7_keyword_scout.py --domain boutimar.com
    python3 agent7_keyword_scout.py --format md         # human report
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from typing import Any

import config

log = logging.getLogger("agent7.keyword_scout")

ARCHITECTURE_CREDIT = config.ARCHITECTURE_CREDIT

# ── The Keyword Planner problem, stated once, plainly ───────────────────────
#
# "Google Keyword Planner" has no API of its own. The data lives behind the
# Google Ads API (KeywordPlanIdeaService.GenerateKeywordIdeas), and getting to
# it costs more than it first appears:
#
#   * A Google Ads account, plus a DEVELOPER TOKEN. Basic access is an
#     application with a review, not a checkbox.
#   * OAuth2 with a refresh token. The Search Console service-account key
#     already in this pipeline will NOT work — Google Ads does not accept
#     service accounts outside Workspace domain-wide delegation, and these are
#     consumer Gmail accounts.
#   * Volumes come back as RANGES ("1K–10K") rather than numbers unless the
#     account has meaningful active spend. An unfunded account produces buckets
#     too coarse to rank candidates with.
#
# And the constraint that decides the architecture:
#
#   * GOOGLE ADS DOES NOT OPERATE IN IRAN. US sanctions mean no Iranian Ads
#     account, no ad serving into Iran, and embargoed territories are absent
#     from the geo-target list. So for boutimar.ir, cruise24.ir, cruiseshop.ir,
#     dmciran.ir and cruisebaz.com — the sites named as most important —
#     Keyword Planner is the wrong instrument and may return nothing at all.
#     VERIFY THIS AGAINST A REAL ADS ACCOUNT BEFORE BUILDING ON IT. It could
#     not be verified from this machine: Google's published geo-target list is
#     rendered client-side, so scraping it proves nothing either way.
#
# The good news is that the substitute is better than the thing it replaces.
# Search Console reports Iran directly, and it reports MEASURED behaviour by
# real Iranian searchers rather than an advertiser-funnel estimate. boutimar.ir
# already shows 88 impressions from `irn`. For the Iran-market sites, GSC geo
# data is not a fallback — it is the superior signal.
#
# What Keyword Planner genuinely adds, and nothing here replaces, is discovery
# of terms with ZERO current impressions. Search Console can only ever show
# queries a site already surfaces for. That gap is real, and it applies to the
# world-market sites where Ads does operate.
KEYWORD_PLANNER_REALITY = "see the module docstring and the comment block above"

# Sites whose market Google Ads cannot report on. Keyword Planner is skipped for
# these and the geo plane carries the work.
ADS_UNAVAILABLE_MARKETS = frozenset({"IR"})

# ISO-3166 alpha-3 as Search Console returns it, to something readable.
COUNTRY_NAMES = {
    "irn": "Iran", "usa": "United States", "deu": "Germany", "gbr": "United Kingdom",
    "nld": "Netherlands", "fra": "France", "can": "Canada", "ind": "India",
    "are": "UAE", "tur": "Türkiye", "grc": "Greece", "afg": "Afghanistan",
    "bra": "Brazil", "vnm": "Vietnam", "bgd": "Bangladesh", "aut": "Austria",
    "che": "Switzerland", "ita": "Italy", "esp": "Spain", "swe": "Sweden",
    "aus": "Australia", "rus": "Russia", "pak": "Pakistan", "irq": "Iraq",
    "qat": "Qatar", "sau": "Saudi Arabia", "kwt": "Kuwait", "omn": "Oman",
    "bhr": "Bahrain", "aze": "Azerbaijan", "arm": "Armenia", "geo": "Georgia",
}

# Position bands. The boundaries are where behaviour actually changes, not
# round numbers: page one ends around 10, and past ~50 a listing is not being
# seen by anyone at all, so "improve it" is the wrong advice — the right advice
# is usually "this page does not deserve to rank yet".
BANDS = (
    (0.0, 3.0, "winning", "Defend. Small losses here cost more than big gains elsewhere."),
    (3.0, 10.0, "page one", "Real traffic is reachable. Best return on effort."),
    (10.0, 20.0, "striking distance", "One good page or a few links away from page one."),
    (20.0, 50.0, "weak", "Visible to crawlers, invisible to people."),
    (50.0, 1e9, "absent", "Not competing. Do not 'optimise' — decide whether to compete at all."),
)


def band_for(position: float) -> tuple[str, str]:
    for lo, hi, name, advice in BANDS:
        if lo <= position < hi:
            return name, advice
    return "absent", BANDS[-1][3]


@dataclass
class CountryVisibility:
    country: str
    country_name: str
    impressions: int
    clicks: int
    ctr: float
    avg_position: float
    best_position: float
    queries: int
    band: str
    advice: str
    top_queries: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def geo_visibility(country_rows: list[dict[str, Any]], *, top_n_queries: int = 3
                   ) -> list[CountryVisibility]:
    """
    Collapse ["query","country"] rows into one record per country.

    Position is impression-WEIGHTED, not a plain mean. A country where one
    obscure query sits at position 1 and forty real ones sit at 40 is not a
    country you rank well in, and a plain average says it is.
    """
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"impressions": 0, "clicks": 0, "pos_weighted": 0.0,
                 "best": 1e9, "queries": []}
    )
    for r in country_rows:
        keys = r.get("keys") or []
        if len(keys) < 2:
            continue
        query, country = keys[0], keys[1]
        imp = int(r.get("impressions", 0) or 0)
        if imp <= 0:
            continue
        pos = float(r.get("position", 0) or 0)
        a = agg[country]
        a["impressions"] += imp
        a["clicks"] += int(r.get("clicks", 0) or 0)
        a["pos_weighted"] += pos * imp
        a["best"] = min(a["best"], pos)
        a["queries"].append({"query": query, "impressions": imp,
                             "clicks": int(r.get("clicks", 0) or 0),
                             "position": round(pos, 1)})

    out: list[CountryVisibility] = []
    for country, a in agg.items():
        imp = a["impressions"]
        avg = a["pos_weighted"] / imp if imp else 0.0
        band, advice = band_for(avg)
        a["queries"].sort(key=lambda q: -q["impressions"])
        out.append(CountryVisibility(
            country=country,
            country_name=COUNTRY_NAMES.get(country, country.upper()),
            impressions=imp,
            clicks=a["clicks"],
            ctr=round(a["clicks"] / imp, 4) if imp else 0.0,
            avg_position=round(avg, 1),
            best_position=round(a["best"], 1) if a["best"] < 1e9 else 0.0,
            queries=len(a["queries"]),
            band=band,
            advice=advice,
            top_queries=a["queries"][:top_n_queries],
        ))
    out.sort(key=lambda c: -c.impressions)
    return out


def market_alignment(site: config.Site, geo: list[CountryVisibility]) -> dict[str, Any]:
    """
    Does the site surface where its market actually is?

    This is the check that catches a site quietly serving the wrong audience —
    an INT-market brand whose only real visibility is domestic, or an IR brand
    that nobody in Iran can find.
    """
    if not geo:
        return {"verdict": "no data", "detail": "no country rows returned"}

    total = sum(c.impressions for c in geo)
    home = {"IR": "irn", "DACH": "deu", "INT": None}.get(site.market)
    top = geo[0]

    if site.market == "IR":
        share = next((c.impressions for c in geo if c.country == "irn"), 0) / total
        aligned = share >= 0.5
        return {
            "verdict": "aligned" if aligned else "MISALIGNED",
            "home_share": round(share, 3),
            "detail": (f"{share:.0%} of impressions come from Iran"
                       if aligned else
                       f"only {share:.0%} of impressions come from Iran, "
                       "the market this site is written for"),
        }

    if site.market == "DACH":
        share = sum(c.impressions for c in geo if c.country in ("deu", "aut", "che")) / total
        return {
            "verdict": "aligned" if share >= 0.4 else "MISALIGNED",
            "home_share": round(share, 3),
            "detail": f"{share:.0%} of impressions come from DACH",
        }

    # INT: no single home market, but a world-market site whose visibility is
    # overwhelmingly one country is not yet a world-market site.
    share = top.impressions / total
    return {
        "verdict": "concentrated" if share >= 0.4 else "distributed",
        "top_country": top.country_name,
        "home_share": round(share, 3),
        "detail": (f"{share:.0%} of all impressions come from {top.country_name} alone — "
                   "this is a domestic site wearing an international domain"
                   if share >= 0.4 else
                   f"spread across {len(geo)} countries, top is {top.country_name} at {share:.0%}"),
    }


def opportunities(geo: list[CountryVisibility], *, min_impressions: int = 20
                  ) -> list[dict[str, Any]]:
    """
    Countries worth working on: enough demand to matter, close enough to move.

    Deliberately excludes the `absent` band. A country at position 60 does not
    need optimisation, it needs a decision about whether to compete there, and
    dressing that up as an SEO task wastes a quarter.
    """
    out = []
    for c in geo:
        if c.impressions < min_impressions or c.band in ("winning", "absent"):
            continue
        # Closer to page one and more impressions = more recoverable traffic.
        proximity = max(0.0, (50.0 - c.avg_position) / 50.0)
        out.append({
            "country": c.country,
            "country_name": c.country_name,
            "impressions": c.impressions,
            "avg_position": c.avg_position,
            "band": c.band,
            "score": round(c.impressions * proximity, 1),
            "why": (f"{c.impressions} impressions at position {c.avg_position} "
                    f"and zero clicks" if c.clicks == 0 else
                    f"{c.impressions} impressions at position {c.avg_position}"),
        })
    out.sort(key=lambda o: -o["score"])
    return out


# ── Keyword Planner adapter ─────────────────────────────────────────────────

def keyword_planner_status(site: config.Site) -> dict[str, Any]:
    """
    Whether Keyword Planner can serve this site, and why not when it cannot.

    Returns rather than raises: an unconfigured integration is a known state of
    the world, not a run failure. Agent 1 learned that lesson the hard way when
    a missing webhook killed the nightly cron.
    """
    if site.market in ADS_UNAVAILABLE_MARKETS:
        return {
            "available": False,
            "reason": "market_not_served",
            "detail": (
                "Google Ads does not operate in Iran, so Keyword Planner cannot "
                "report on this market. Search Console geo data is used instead "
                "— and it is the better signal here, because it measures what "
                "Iranian searchers actually did rather than estimating what "
                "advertisers might bid on."
            ),
        }

    missing = [k for k in ("GOOGLE_ADS_DEVELOPER_TOKEN",
                           "GOOGLE_ADS_CLIENT_ID",
                           "GOOGLE_ADS_CLIENT_SECRET",
                           "GOOGLE_ADS_REFRESH_TOKEN",
                           "GOOGLE_ADS_CUSTOMER_ID")
               if not config.optional_env(k)]
    if missing:
        return {
            "available": False,
            "reason": "not_configured",
            "missing": missing,
            "detail": ("Keyword Planner needs a Google Ads developer token and an "
                       "OAuth2 refresh token. The Search Console service account "
                       "cannot be reused — Google Ads rejects service accounts "
                       "outside Workspace domain-wide delegation. See "
                       "SETUP-KEYWORD-PLANNER.md."),
        }

    return {"available": True, "reason": "configured",
            "detail": "Credentials present. Volumes may still be returned as "
                      "ranges rather than exact numbers unless the Ads account "
                      "has active spend."}


def scout_site(site: config.Site, gsc: dict[str, Any]) -> dict[str, Any]:
    geo = geo_visibility(gsc.get("country_rows") or [])
    return {
        "domain": site.domain,
        "market": site.market,
        "locale": site.locale,
        "date_range": gsc.get("date_range"),
        "countries_seen": len(geo),
        "total_impressions": sum(c.impressions for c in geo),
        "market_alignment": market_alignment(site, geo),
        "geo": [c.as_dict() for c in geo],
        "opportunities": opportunities(geo),
        "keyword_planner": keyword_planner_status(site),
        "architecture_credit": ARCHITECTURE_CREDIT,
    }


def render_markdown(reports: list[dict[str, Any]]) -> str:
    L: list[str] = ["# Agent 7 — where each site is actually found", "",
                    f"Architecture credit: **{ARCHITECTURE_CREDIT}**", ""]
    for r in reports:
        L.append(f"## {r['domain']}  ·  market {r['market']}")
        ma = r["market_alignment"]
        L.append(f"**{ma['verdict']}** — {ma['detail']}")
        L.append("")
        L.append(f"{r['total_impressions']} impressions across {r['countries_seen']} countries.")
        L.append("")
        L.append("| Country | Impressions | Clicks | Avg pos | Band |")
        L.append("|---|---:|---:|---:|---|")
        for c in r["geo"][:10]:
            L.append(f"| {c['country_name']} | {c['impressions']} | {c['clicks']} "
                     f"| {c['avg_position']} | {c['band']} |")
        L.append("")
        if r["opportunities"]:
            L.append("**Worth working on**")
            for o in r["opportunities"][:5]:
                L.append(f"- **{o['country_name']}** ({o['band']}) — {o['why']}")
            L.append("")
        kp = r["keyword_planner"]
        L.append(f"*Keyword Planner: {'available' if kp['available'] else kp['reason']}* — {kp['detail']}")
        L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", action="append")
    ap.add_argument("--format", choices=["json", "md"], default="md")
    ap.add_argument("--min-impressions", type=int, default=20)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")

    import agent1_seo_scout as a1  # reuse the GSC client and collector

    try:
        sites = config.load_sites(only=args.domain)
        service = a1.build_gsc_client()
    except config.ConfigError as exc:
        log.error("%s", exc)
        return 2

    reports = []
    for site in sites:
        try:
            gsc = a1.collect_gsc(service, site)
        except PermissionError as exc:
            log.error("%s — skipped: %s", site.domain, config.redact(str(exc)))
            continue
        r = scout_site(site, gsc)
        reports.append(r)
        ma = r["market_alignment"]
        log.info("%s — %d countries, %d impressions, %s",
                 site.domain, r["countries_seen"], r["total_impressions"], ma["verdict"])

    if not reports:
        log.error("no readable properties")
        return 1

    print(render_markdown(reports) if args.format == "md"
          else json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
