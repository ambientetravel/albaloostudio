#!/usr/bin/env python3
"""
Agent 6 — The Analyst.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

The layer that turns data into a decision. Agent 1 finds demand, Agent 5 finds
defects; neither tells you what to do on Monday. This one reads both, ranks the
whole portfolio, and writes the strategy — technical fixes in tier order, a
topical authority map, a prioritised content queue, a 12-week calendar, and the
actual JSON-LD to paste.

    python agent6_analyst.py --audit runs/<run_id>/site-audit.json
    python agent6_analyst.py --audit … --gaps runs/<run_id>/briefs/ --no-llm
    python agent6_analyst.py --audit … --out reports/strategy.md

Four disciplines are borrowed deliberately and enforced in code, not in a prompt:

  **Evidence or it doesn't ship.** Every finding carries Issue / Impact /
  Evidence / Fix / Priority. A claim with no evidence field is dropped before
  the report renders. This is the same rule as the pipeline's "never invent a
  rate", pointed at diagnostics.

  **Five tiers, in order.** Crawlability → Technical → On-page → Content →
  Authority. A title-tag suggestion under a site that blocks crawling is noise.

  **Out-of-Scope Notes.** What this cannot measure is stated, not omitted:
  no JavaScript rendering, no Core Web Vitals field data, no backlinks, no SERP
  positions. Silence about a limit reads as a clean bill of health.

  **A priority matrix, not a wishlist.** Quick wins / Big bets / Fill-ins /
  Avoid, scored from impressions, position proximity and commercial intent.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import compliance
import config
import llm
from config import rfc3339, utc_now

log = logging.getLogger("agent6.analyst")

AGENT_ID = "agent6.analyst"

# Tier order is the report order. A finding in tier 1 outranks anything below it
# regardless of its own severity — an unindexable site has no on-page problems
# worth discussing yet.
TIERS = [
    ("crawlability", "Crawlability & indexation",
     "Can search engines and answer engines reach and index this at all?"),
    ("technical", "Technical foundations",
     "Host canonicalisation, language declaration, response codes, mobile."),
    ("onpage", "On-page optimisation",
     "Titles, descriptions, headings, canonicals, alt text."),
    ("geo", "GEO — generative engine optimisation",
     "Structured data, entity clarity, question structure, AI-fetchable content."),
    ("content", "Content & topical authority",
     "What is missing, what is thin, what cluster it belongs to."),
]

_TIER_OF_FINDING = {
    "robots.missing": "crawlability", "robots.blocks_everything": "crawlability",
    "robots.blocks_assets": "crawlability", "robots.no_sitemap": "crawlability",
    "sitemap.missing": "crawlability", "sitemap.malformed": "crawlability",
    "sitemap.empty": "crawlability", "sitemap.no_lastmod": "crawlability",
    "content.noindex": "crawlability", "http.sitemap_url_broken": "crawlability",
    "sitemap.noindex_conflict": "crawlability",
    "http.unreachable": "crawlability", "http.home_error": "crawlability",
    "http.no_https": "technical", "host.duplicate": "technical",
    "host.temp_redirect": "technical", "host.redirect_wrong_target": "technical",
    "host.alt_unreachable": "technical", "http.soft_404": "technical",
    "content.no_lang": "technical", "content.lang_mismatch": "technical",
    "content.no_viewport": "technical",
    "content.no_title": "onpage", "content.title_long": "onpage",
    "content.no_description": "onpage", "content.no_h1": "onpage",
    "content.multiple_h1": "onpage", "content.no_canonical": "onpage",
    "content.images_no_alt": "onpage",
    "geo.no_structured_data": "geo", "geo.no_org_schema": "geo",
    "geo.schema_not_useful": "geo", "geo.no_local_signals": "geo",
    "geo.no_question_structure": "geo", "geo.js_dependent": "geo",
    "geo.no_llms_txt": "geo", "geo.no_opengraph": "geo",
    "site.placeholder": "crawlability",
}

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Stated, not omitted. Every one of these is a real blind spot in this pipeline.
OUT_OF_SCOPE = [
    ("JavaScript-rendered content", "Agent 5 fetches without executing JS. Schema "
     "injected by Yoast, RankMath or a client-side framework is invisible to it, so "
     "every 'no JSON-LD' finding says *not in the server HTML* — not *absent*.",
     "Re-check with a rendering fetch (Bright Data `bdata scrape -f html`, or any "
     "headless browser) before spending a day adding schema that already exists."),
    ("Core Web Vitals field data", "No CrUX or RUM data. Page weight and script "
     "volume are proxies, and weak ones.",
     "PageSpeed Insights, or the Core Web Vitals report in Search Console."),
    ("Backlinks and authority", "Nothing here measures off-site signals.",
     "Ahrefs or Semrush. Relevant for the 'big bet' keywords, not the quick wins."),
    ("Live SERP positions and cannibalisation", "Positions come from Search Console, "
     "which reports where you ranked — not who outranked you, and not which two of "
     "your own pages are competing for one query.",
     "A SERP API, or `bdata search` once the Bright Data CLI is installed."),
    ("AI answer-engine citations", "Nothing yet measures whether these brands are "
     "actually cited in ChatGPT, Claude, Gemini or Perplexity answers. The GEO "
     "findings are readiness signals, not measured presence.",
     "A tracked prompt set run against each engine on a schedule — the obvious "
     "next agent in this lane."),
]


# ══════════════════════════════════════════════════════════════════════════════
# 1. Findings
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class Recommendation:
    tier: str
    priority: str          # P0 | P1 | P2 | P3
    issue: str
    impact: str
    evidence: str
    fix: str
    sites: list[str] = field(default_factory=list)
    effort: str = "medium"

    def valid(self) -> bool:
        """No evidence, no recommendation. Enforced, not requested."""
        return bool(self.evidence and self.evidence.strip() and self.issue and self.fix)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier, "priority": self.priority, "issue": self.issue,
            "impact": self.impact, "evidence": self.evidence, "fix": self.fix,
            "sites": self.sites, "effort": self.effort,
        }


_PRIORITY_BY_SEVERITY = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P3", "info": "P3"}

# What a class of finding actually costs, in plain terms. Severity says how loud;
# this says why anyone should care.
_IMPACT = {
    "robots.blocks_everything": "Nothing on the domain can be indexed. Every other line in this report is moot until it is removed.",
    "robots.blocks_assets": "Googlebot renders pages; blocked JS/CSS means it renders a blank one. This is what starved boutimar.ir's JS pages.",
    "sitemap.missing": "Discovery falls back to link-crawling, and Agent 1 cannot tell a missing page from an unlisted one — so its gap detection degrades too.",
    "sitemap.empty": "Same as missing, with the added risk that an edited sitemap never made it into a deploy.",
    "host.duplicate": "Every ranking signal is split across two hostnames. One 301 consolidates them.",
    "content.noindex": "The page is excluded from the index. Not advertised in the sitemap, so probably deliberate — worth confirming.",
    "sitemap.noindex_conflict": "The sitemap says crawl it, the page says ignore it. Contradictory signals waste crawl budget, and whichever of the two is wrong is a real defect.",
    "geo.no_structured_data": "Answer engines lift entities, prices and FAQs from structured data far more reliably than from prose. Without it the brand is invisible to the surface you are trying to win.",
    # DOWNGRADED 11 Aug 2026. The original claim — that answer engines quote
    # passages shaped like an answer — did not survive testing. In a 100-query
    # AI Overview study (heytony.ca), question-format titles matching the query
    # showed NO positive correlation with citation, alongside heavy formatting
    # and fact density. What DID correlate was agreeing with the consensus
    # number (+12 points) and matching the answer's geographic scope (+14).
    #
    # Kept as a finding because question headings still help a reader scan, and
    # FAQPage schema is still valid structured data. It is no longer sold as a
    # citation lever, and it no longer ranks above the things that measured.
    "geo.no_question_structure": "Question headings help a reader scan and FAQ schema is valid structured data — but tested AI-citation benefit is nil. Do this for people, not for engines.",
    "geo.js_dependent": "Googlebot renders eventually; most AI fetchers do not. A JS-only page is invisible to exactly the surface this lane targets.",
    "geo.no_local_signals": "'DMC in Iran', 'travel agency Tehran' are geographic queries. Nothing on the page answers the geographic part.",
    "content.lang_mismatch": "The wrong language is declared for the primary market, which affects both ranking and how assistive tech reads the page.",
    "content.no_viewport": "Roughly 78% of the Iranian traffic to these sites is mobile.",
    "http.soft_404": "Non-existent URLs get indexed as thin duplicates and eat crawl budget.",
    "site.placeholder": "There is no site here to optimise. Excluded from the portfolio mean.",
    "sitemap.no_lastmod": "Crawlers have no signal about what changed, so recrawl priority falls back to guesswork and new pages are found late.",
    "content.no_description": "Google writes its own snippet from whatever text it finds. You lose control of the one line that decides the click.",
    "content.no_h1": "The page states no subject in the one element both crawlers and screen readers use to find it.",
    "content.multiple_h1": "Competing subjects on one page. Minor, but it muddies what the page is about.",
    "content.title_long": "The tail gets truncated in the result, and the truncated part is usually the brand.",
    "content.no_canonical": "Parameter and duplicate URLs can be indexed separately, splitting the signal for one page.",
    "content.images_no_alt": "The images are unreadable to screen readers and to every answer engine — for a travel brand that is most of the page.",
    "geo.no_llms_txt": "No map for AI crawlers of what this site covers. An emerging convention, cheap to adopt, plausible upside.",
    "geo.no_opengraph": "Shared links render without a title or image, in chat apps as much as social — and Telegram is a primary channel here.",
    "geo.no_org_schema": "Nothing declares that these domains are one business. Answer engines cannot connect the brand across the portfolio.",
    "geo.schema_not_useful": "Structured data is present but describes none of the things a travel buyer or an answer engine asks about.",
    "host.temp_redirect": "A 302 does not consolidate ranking signals the way a 301 does.",
    "host.alt_unreachable": "A visitor typing the other hostname gets nothing.",
    "robots.no_sitemap": "The sitemap still works if submitted in Search Console, but discovery is one step less reliable.",
    "robots.missing": "Not fatal on its own, but it is where crawlers look for the sitemap.",
    "http.sitemap_url_broken": "Wasted crawl budget, and a signal that the build is emitting stale URLs.",
}
_DEFAULT_IMPACT = "Weakens how clearly search and answer engines can read the page."

_EFFORT = {
    "robots.blocks_assets": "minutes", "robots.no_sitemap": "minutes",
    "host.duplicate": "minutes", "content.noindex": "minutes",
    "content.no_lang": "minutes", "content.lang_mismatch": "minutes",
    "content.no_viewport": "minutes", "geo.no_llms_txt": "hours",
    "geo.no_structured_data": "hours", "geo.no_question_structure": "minutes",
    "geo.js_dependent": "days", "sitemap.missing": "hours",
}


def _portfolio_phrasing(title: str) -> str:
    """
    A per-page finding title reads wrong once it covers six sites. Drop the
    "Homepage"/"Page" subject and let the site list carry the scope — naive
    substitution produced "Pages declares lang=…".
    """
    stripped = re.sub(r"^(Homepage|Page)\b[:\s]*", "", title).strip()
    if not stripped:
        return title
    return stripped[0].upper() + stripped[1:]


def roll_up(audit_payload: dict[str, Any]) -> list[Recommendation]:
    """
    Collapse per-page findings into portfolio recommendations.

    Nine pages missing schema is one decision, not nine tickets — grouping by
    finding id and listing the affected sites is what makes the report
    actionable rather than exhausting.
    """
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"sites": set(), "count": 0, "sample": None, "severity": "low"}
    )
    for site in audit_payload.get("sites", []):
        if site.get("stats", {}).get("placeholder") and site["score"] < 100:
            pass  # still record the placeholder finding itself
        for f in site.get("findings", []):
            g = grouped[f["id"]]
            g["sites"].add(site["domain"])
            g["count"] += 1
            g["title"] = f["title"]
            g["fix"] = f["fix"]
            if g["sample"] is None:
                g["sample"] = f
            if SEVERITY_RANK[f["severity"]] < SEVERITY_RANK[g["severity"]]:
                g["severity"] = f["severity"]

    out: list[Recommendation] = []
    for fid, g in grouped.items():
        sample = g["sample"]
        sites = sorted(g["sites"])
        evidence = (
            f"{g['count']} occurrence(s) across {len(sites)} site(s): "
            f"{', '.join(sites)}. Example — {sample['url'] or sites[0]}: "
            f"{sample['evidence']}"
        )
        rec = Recommendation(
            tier=_TIER_OF_FINDING.get(fid, "onpage"),
            priority=_PRIORITY_BY_SEVERITY[g["severity"]],
            issue=_portfolio_phrasing(g["title"]),
            impact=_IMPACT.get(fid, _DEFAULT_IMPACT),
            evidence=evidence,
            fix=g["fix"],
            sites=sites,
            effort=_EFFORT.get(fid, "medium"),
        )
        if rec.valid():
            out.append(rec)
        else:
            log.warning("dropped a recommendation with no evidence: %s", fid)

    tier_index = {t[0]: i for i, t in enumerate(TIERS)}
    out.sort(key=lambda r: (tier_index[r.tier], r.priority, -len(r.sites)))
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 2. The priority matrix
# ══════════════════════════════════════════════════════════════════════════════

_COMMERCIAL = re.compile(
    r"(?i)price|cost|cheap|deal|book|buy|package|tour|قیمت|ارزان|رزرو|تور|خرید|هزینه"
)
_INFORMATIONAL = re.compile(
    r"(?i)^(what|why|how|when|guide)|چیست|چگونه|راهنما|چطور"
)


@dataclass
class Opportunity:
    keyword: str
    domain: str
    impressions: int
    position: float
    intent: str
    quadrant: str          # quick_win | big_bet | fill_in | avoid
    score: float
    cluster: str
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def classify(keyword: str, impressions: int, position: float, domain: str,
             median_impressions: float) -> Opportunity:
    """
    Quadrant from volume × winnability, not from volume alone.

    Position is the competition proxy available without a SERP API: a query
    sitting at 8–20 is one page away from the first page; the same volume at 60
    is a different project entirely.
    """
    intent = ("transactional" if _COMMERCIAL.search(keyword)
              else "informational" if _INFORMATIONAL.search(keyword)
              else "commercial")

    high_volume = impressions >= median_impressions
    winnable = 5 <= position <= 20

    if winnable and (high_volume or intent == "transactional"):
        quadrant, rationale = "quick_win", (
            f"Position {position:.0f} — one good page from the first screen, and the "
            f"query is {intent}.")
    elif high_volume and position > 20:
        quadrant, rationale = "big_bet", (
            f"{impressions:,} impressions but position {position:.0f}. Real demand, "
            "real work — pillar-length, and it needs internal links behind it.")
    elif not high_volume and winnable:
        quadrant, rationale = "fill_in", (
            "Low volume, close position. Batch these; do not schedule them individually.")
    else:
        quadrant, rationale = "avoid", (
            f"Position {position:.0f} with {impressions:,} impressions. Nothing here "
            "pays for the effort yet.")

    proximity = max(0.0, min(1.0, (40 - position) / 40))
    value = {"transactional": 1.0, "commercial": 0.75, "informational": 0.45}[intent]
    score = round(impressions * (0.3 + 0.7 * proximity) * value, 1)

    return Opportunity(
        keyword=keyword, domain=domain, impressions=impressions,
        position=round(position, 1), intent=intent, quadrant=quadrant,
        score=score, cluster=cluster_of(keyword), rationale=rationale,
    )


# Topic clusters for this portfolio. A keyword that matches nothing lands in
# "unclustered", which is itself a finding — it means the topic map has a hole.
CLUSTERS: dict[str, list[str]] = {
    "Persian Gulf cruising": ["خلیج فارس", "persian gulf", "dubai", "دبی", "قطر", "abu dhabi", "ابوظبی"],
    "Mediterranean & Greek isles": ["mediterranean", "greek", "santorini", "مدیترانه", "یونان", "سانتورینی", "italy", "ایتالیا"],
    "AROYA & Red Sea": ["aroya", "آرویا", "red sea", "دریای سرخ", "jeddah", "جده"],
    "Cruise lines & ships": ["msc", "royal caribbean", "costa", "کشتی", "ship", "cabin", "کابین"],
    "Practical & visa": ["visa", "ویزا", "passport", "پاسپورت", "insurance", "بیمه", "transfer", "ترانسفر"],
    "Pricing & booking": ["price", "قیمت", "cost", "هزینه", "book", "رزرو", "cheap", "ارزان"],
    "DMC & inbound Iran": ["dmc", "inbound", "iran tour", "تور ایران", "mice", "incentive"],
    "Türkiye & Orient": ["turkey", "türkiye", "ترکیه", "istanbul", "استانبول", "orient"],
}


def cluster_of(keyword: str) -> str:
    k = keyword.lower()
    for name, terms in CLUSTERS.items():
        if any(t in k for t in terms):
            return name
    return "unclustered"


def build_matrix(gaps: list[dict[str, Any]]) -> list[Opportunity]:
    if not gaps:
        return []
    impressions = sorted(g.get("impressions", 0) for g in gaps)
    median = impressions[len(impressions) // 2] or 1
    opps = [
        classify(
            g.get("query") or g.get("primary_keyword", ""),
            int(g.get("impressions", 0)),
            float(g.get("position", g.get("avg_position", 50))),
            g.get("domain", "—"),
            median,
        )
        for g in gaps
        if (g.get("query") or g.get("primary_keyword"))
    ]
    opps.sort(key=lambda o: o.score, reverse=True)
    return opps


# heytony.ca's 100-AI-Overview study, Finding 4: when page one is dominated by
# major brands (more than 7 of 10), those brands took 76% of stable citations.
# Where page one was mostly smaller sites, small and mid-size businesses took
# 77%. The query is either open or it is walled off, and writing into a walled
# query is a wasted brief.
#
# Counting brands on page one needs SERP data, and this pipeline has none — it
# infers everything from Search Console, which reports only our own rows. So
# this returns "unknown" unless a SERP source is supplied, and an unknown
# verdict NEVER filters a brief out. Dropping work on a guess is worse than
# doing work that might be crowded.
WALLED_OFF_BRAND_THRESHOLD = 7      # of 10 page-one results


def competition_verdict(page_one_brands: int | None) -> dict[str, Any]:
    """
    Is this query worth entering?

    page_one_brands is the count of major-brand results in the top ten, or None
    when nobody has measured it. None is the honest default here: a verdict
    invented from Search Console data would look like evidence and be a guess.
    """
    if page_one_brands is None:
        return {
            "verdict": "unknown",
            "acts_as_filter": False,
            "detail": (
                "No SERP source is configured, so page-one composition has not "
                "been measured. Briefs are not filtered on an unmeasured signal."
            ),
        }
    if page_one_brands > WALLED_OFF_BRAND_THRESHOLD:
        return {
            "verdict": "walled_off",
            "acts_as_filter": True,
            "page_one_brands": page_one_brands,
            "detail": (
                f"{page_one_brands} of 10 page-one results are major brands. In "
                "testing, brands took 76% of stable AI citations in queries like "
                "this. A new page here is unlikely to be cited or to rank; spend "
                "the brief somewhere open."
            ),
        }
    return {
        "verdict": "open",
        "acts_as_filter": False,
        "page_one_brands": page_one_brands,
        "detail": (
            f"Only {page_one_brands} of 10 page-one results are major brands. "
            "Small and mid-size sites took 77% of stable citations in queries "
            "with this shape — worth entering."
        ),
    }


def topic_map(opps: list[Opportunity]) -> dict[str, dict[str, Any]]:
    """
    Pillar → cluster → supporting, sized by the demand actually behind each.

    A cluster with real volume and no pillar page is the strongest content
    signal this pipeline produces: it means demand exists and nothing anchors it.
    """
    out: dict[str, dict[str, Any]] = {}
    for o in opps:
        c = out.setdefault(o.cluster, {"impressions": 0, "keywords": [], "quadrants": Counter()})
        c["impressions"] += o.impressions
        c["keywords"].append(o)
        c["quadrants"][o.quadrant] += 1
    for c in out.values():
        c["keywords"].sort(key=lambda o: o.score, reverse=True)
        top = c["keywords"][0]
        c["pillar"] = top.keyword
        c["pillar_words"] = "2000–4000"
        c["supporting"] = [o.keyword for o in c["keywords"][1:8]]
        # Keywords as STRINGS, not Opportunity objects. They were the objects,
        # which made this whole payload unserialisable — so `--format json` had
        # never once worked, and nobody noticed because the workflow only ever
        # asked for markdown. The dashboard reads the JSON, which is how it
        # surfaced.
        c["keywords"] = [o.keyword for o in c["keywords"]]
        c["quadrants"] = dict(c["quadrants"])
    return dict(sorted(out.items(), key=lambda kv: kv[1]["impressions"], reverse=True))


def calendar(opps: list[Opportunity], weeks: int = 12) -> list[dict[str, Any]]:
    """
    Quick wins first, then pillars, then the batch.

    Deliberately front-loads winnable pages: the point of week 1–4 is to prove
    the pipeline moves rankings before anyone commits a quarter to it.
    """
    quick = [o for o in opps if o.quadrant == "quick_win"]
    bets = [o for o in opps if o.quadrant == "big_bet"]
    fills = [o for o in opps if o.quadrant == "fill_in"]

    plan: list[dict[str, Any]] = []
    start = utc_now()
    queue: list[tuple[Opportunity, str, str]] = (
        [(o, "cluster", "1000–2000") for o in quick[:6]]
        + [(o, "pillar", "2000–4000") for o in bets[:3]]
        + [(o, "supporting", "500–1500") for o in fills[:12]]
    )
    per_week = max(1, -(-len(queue) // weeks))
    for w in range(weeks):
        batch = queue[w * per_week:(w + 1) * per_week]
        if not batch:
            break
        plan.append({
            "week": w + 1,
            "starting": (start + timedelta(weeks=w)).date().isoformat(),
            "items": [
                {"keyword": o.keyword, "domain": o.domain, "type": kind,
                 "words": words, "cluster": o.cluster, "intent": o.intent}
                for o, kind, words in batch
            ],
        })
    return plan


# ══════════════════════════════════════════════════════════════════════════════
# 3. Schema generation — the fix, not just the finding
# ══════════════════════════════════════════════════════════════════════════════


def schema_for(site: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """
    Concrete JSON-LD for a site that has none, built only from facts already in
    sites.yml. No invented address, no invented phone number, no invented
    rating — the same rule that governs every other generator in this pipeline.
    Placeholders are marked `TODO` so a human fills them rather than the model.
    """
    domain = site["domain"]
    brand = registry.get("brand", domain)
    base = registry.get("base_url", f"https://{domain}")
    locale = registry.get("locale", "en")
    market = registry.get("market", "")

    org_type = "TravelAgency" if "cruise" in domain or "boutimar" in domain else "Organization"
    doc: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": org_type,
        "name": brand,
        "url": base,
        "inLanguage": locale,
        "logo": f"{base}/logo.png",
        "sameAs": ["TODO: your social profile URLs — one per line"],
    }
    if market == "IR":
        doc["address"] = {
            "@type": "PostalAddress",
            "addressCountry": "IR",
            "addressLocality": "TODO: city",
            "streetAddress": "TODO: street",
        }
        doc["areaServed"] = {"@type": "Country", "name": "Iran"}
    return {
        "domain": domain,
        "why": "Highest-leverage GEO fix for this site. Paste into <head>.",
        "jsonld": doc,
        "also_add": [
            "WebSite with potentialAction/SearchAction if the site has search",
            "BreadcrumbList on every interior page",
            "FAQPage wherever you add the question headings recommended above",
        ],
        "validate": "https://search.google.com/test/rich-results",
        "snippet": '<script type="application/ld+json">\n'
                   + json.dumps(doc, ensure_ascii=False, indent=2)
                   + "\n</script>",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. Narrative (optional LLM pass)
# ══════════════════════════════════════════════════════════════════════════════


def write_narrative(payload: dict[str, Any], profile: str) -> str | None:
    """
    A short executive read. Everything factual is computed above and passed in —
    the model orders and explains, it does not discover. Then the compliance
    gate runs on what comes back, because a strategy memo is as capable of
    saying "Arabian Gulf" as a landing page is.
    """
    system = "\n".join([
        "You are the SEO lead for a luxury travel group, writing the opening of a "
        "strategy memo for the owner.",
        "",
        "Every number and finding is supplied. Do not add facts, do not estimate "
        "traffic, do not predict rankings, do not invent a competitor. If the data "
        "does not support a claim, leave the claim out.",
        "",
        "Six to ten sentences. Lead with the single thing that matters most. Say "
        "what to do first and why that order. No preamble, no bullet lists, no "
        "restating the tables — the reader has them.",
        "",
        compliance.prompt_constraints(profile),
    ])

    try:
        text, _meta = llm.complete(
            system,
            json.dumps(payload, ensure_ascii=False)[:60000],
            max_tokens=4000,
            purpose="strategy narrative",
        )
    except llm.ProviderUnavailable as exc:
        # The memo is worth publishing without its opening paragraph. Every
        # number in it was computed here, not by the model — the narrative
        # orders and explains, it does not discover. Failing the weekly run for
        # a missing preamble would throw away the part that has the value.
        log.warning("narrative omitted — %s; the report stands without it", exc)
        return None
    except Exception as exc:
        log.warning("narrative pass failed (%s); the report stands without it", exc)
        return None

    violations = compliance.check(text, profile, context={"priced_facts": False})
    if any(v.severity == compliance.BLOCK for v in violations):
        log.error("narrative blocked by the compliance gate: %s",
                  "; ".join(f"{v.rule}" for v in violations))
        return None
    return text


# ══════════════════════════════════════════════════════════════════════════════
# 5. Report
# ══════════════════════════════════════════════════════════════════════════════

_QUADRANT_LABEL = {
    "quick_win": "Quick wins — do these first",
    "big_bet": "Big bets — worth a pillar page",
    "fill_in": "Fill-ins — batch produce",
    "avoid": "Skip for now",
}


def render(payload: dict[str, Any]) -> str:
    a = payload
    L: list[str] = [
        "# Organic growth strategy",
        "",
        f"Generated {a['generated_at']} · Architecture credit: {config.ARCHITECTURE_CREDIT}",
        "",
    ]

    if a.get("narrative"):
        L += ["## The short version", "", a["narrative"], ""]

    L += ["## Portfolio", "", "| Site | Score | Findings | Note |", "|---|---:|---:|---|"]
    for s in a["portfolio"]:
        note = "placeholder — nothing to audit" if s.get("placeholder") else ""
        L.append(f"| `{s['domain']}` | {s['score']} | {s['findings']} | {note} |")
    L += ["", f"Mean score **{a['mean_score']}/100** across "
          f"{a['sites_audited']} audited "
          f"({a['placeholders']} placeholder(s) excluded)."]
    if a.get("on_hold"):
        L += ["",
              "On hold, not audited: " + ", ".join(f"`{d}`" for d in a["on_hold"])
              + ". Search Console demand is still being banked for these — that is "
                "the launch-day input."]
    L.append("")

    L += ["## What to fix, in order", ""]
    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in a["recommendations"]:
        by_tier[r["tier"]].append(r)
    for key, title, blurb in TIERS:
        recs = by_tier.get(key)
        if not recs:
            continue
        L += [f"### {title}", "", f"*{blurb}*", ""]
        for r in recs:
            L += [
                f"**[{r['priority']}] {r['issue']}**  ·  {', '.join(r['sites'])}  ·  {r['effort']}",
                "",
                f"- **Impact:** {r['impact']}",
                f"- **Evidence:** {r['evidence']}",
                f"- **Fix:** {r['fix']}",
                "",
            ]

    if a.get("topics"):
        L += ["## Topical authority map", "",
              "Clusters ranked by the demand behind them. A cluster with volume and "
              "no pillar page is where the money is.", ""]
        for name, c in a["topics"].items():
            L += [f"### {name} — {c['impressions']:,} impressions", "",
                  f"- **Pillar ({c['pillar_words']} words):** {c['pillar']}"]
            if c["supporting"]:
                L.append("- **Supporting:** " + ", ".join(c["supporting"]))
            L.append("")

    if a.get("opportunities"):
        L += ["## Priority queue", ""]
        by_q: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for o in a["opportunities"]:
            by_q[o["quadrant"]].append(o)
        for q in ("quick_win", "big_bet", "fill_in", "avoid"):
            items = by_q.get(q)
            if not items:
                continue
            L += [f"### {_QUADRANT_LABEL[q]}", "",
                  "| Keyword | Site | Impressions | Position | Intent | Why |",
                  "|---|---|---:|---:|---|---|"]
            for o in items[:12]:
                L.append(
                    f"| {o['keyword']} | `{o['domain']}` | {o['impressions']:,} | "
                    f"{o['position']} | {o['intent']} | {o['rationale']} |"
                )
            L.append("")

    if a.get("calendar"):
        L += ["## 12-week calendar", ""]
        for w in a["calendar"]:
            titles = "; ".join(
                f"{i['keyword']} ({i['type']}, {i['words']}w)" for i in w["items"]
            )
            L.append(f"- **Week {w['week']}** ({w['starting']}): {titles}")
        L.append("")

    if a.get("schema_fixes"):
        L += ["## Structured data — paste-ready", "",
              "Built only from facts already in `sites.yml`. Anything marked `TODO` "
              "is a fact this pipeline does not have and must not invent.", ""]
        for s in a["schema_fixes"]:
            L += [f"### `{s['domain']}`", "", "```html", s["snippet"], "```", "",
                  "Then add: " + "; ".join(s["also_add"]),
                  f"  ·  Validate: {s['validate']}", ""]

    L += ["## Out-of-scope notes", "",
          "What this report does **not** measure. Silence about a limit reads as a "
          "clean bill of health, so:", ""]
    for name, limit, where in a["out_of_scope"]:
        L += [f"- **{name}** — {limit} *Use:* {where}"]
    L.append("")

    L += ["---", "",
          f"*Architecture by {config.ARCHITECTURE_CREDIT} — {config.ARCHITECTURE_URL}.*"]
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Assembly
# ══════════════════════════════════════════════════════════════════════════════


def load_gaps(path: Path | None) -> list[dict[str, Any]]:
    """Accept either Agent 1's brief directory or a flat JSON list of gaps."""
    if path is None:
        return []
    if path.is_dir():
        gaps = []
        for f in sorted(path.glob("*.json")):
            try:
                brief = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            opp, site = brief.get("opportunity", {}), brief.get("site", {})
            gsc = opp.get("gsc", {})
            gaps.append({
                "query": opp.get("primary_keyword"),
                "impressions": gsc.get("impressions", 0),
                "position": gsc.get("avg_position", 50),
                "domain": site.get("domain", "—"),
            })
        return gaps
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("gaps", [])


def analyse(audit: dict[str, Any], gaps: list[dict[str, Any]], *, use_llm: bool,
            profile: str = "boutimar_v1") -> dict[str, Any]:
    sites = audit.get("sites", [])
    real = [s for s in sites if not s.get("stats", {}).get("placeholder")]
    placeholders = len(sites) - len(real)

    recs = roll_up(audit)
    opps = build_matrix(gaps)

    registry = {s.domain: s for s in config.load_sites(include_hold=True)}
    schema_fixes = []
    for s in sites:
        if s.get("stats", {}).get("placeholder"):
            continue
        if any(f["id"] == "geo.no_structured_data" for f in s.get("findings", [])):
            site_cfg = registry.get(s["domain"])
            schema_fixes.append(schema_for(s, {
                "brand": site_cfg.brand if site_cfg else s["domain"],
                "base_url": site_cfg.base_url if site_cfg else f"https://{s['domain']}",
                "locale": site_cfg.locale if site_cfg else "en",
                "market": site_cfg.market if site_cfg else "",
            }))

    payload: dict[str, Any] = {
        "schema_version": config.SCHEMA_VERSION,
        "envelope": config.build_envelope(
            message_type="strategy.report",
            emitted_by=AGENT_ID,
            target="human",
            correlation_id=audit.get("envelope", {}).get("correlation_id", config.new_run_id()),
            idem_key=config.idempotency_key("strategy", audit.get("generated_at", ""), ""),
        ),
        "generated_at": rfc3339(),
        "sites_audited": len(real),
        "placeholders": placeholders,
        "mean_score": round(sum(s["score"] for s in real) / max(len(real), 1), 1),
        "portfolio": [
            {"domain": s["domain"], "score": s["score"],
             "findings": len(s.get("findings", [])),
             "placeholder": bool(s.get("stats", {}).get("placeholder"))}
            for s in sorted(sites, key=lambda x: x["score"])
        ],
        "on_hold": sorted(
            s.domain for s in config.load_sites(include_hold=True) if s.on_hold
        ),
        "recommendations": [r.as_dict() for r in recs],
        "opportunities": [o.as_dict() for o in opps],
        "topics": topic_map(opps),
        "calendar": calendar(opps),
        "schema_fixes": schema_fixes,
        "out_of_scope": OUT_OF_SCOPE,
    }
    payload["narrative"] = write_narrative(payload, profile) if use_llm else None
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent 6 — The Analyst. Architecture credit: Albaloo Studio."
    )
    parser.add_argument("--audit", required=True, help="site-audit.json from Agent 5")
    parser.add_argument("--gaps", help="Agent 1 brief directory, or a gaps JSON file")
    parser.add_argument("--no-llm", action="store_true", help="skip the narrative pass")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--out", help="write here instead of stdout")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S", stream=sys.stderr,
    )

    audit_path = Path(args.audit)
    if not audit_path.exists():
        log.error("no audit at %s — run agent5_site_auditor.py first", audit_path)
        return 2

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    gaps = load_gaps(Path(args.gaps) if args.gaps else None)
    log.info("analysing %d site(s), %d gap candidate(s)",
             len(audit.get("sites", [])), len(gaps))

    payload = analyse(audit, gaps, use_llm=not args.no_llm)
    out = render(payload) if args.format == "markdown" else json.dumps(
        payload, ensure_ascii=False, indent=2)

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        log.info("written to %s", args.out)
    else:
        print(out)

    p0 = sum(1 for r in payload["recommendations"] if r["priority"] == "P0")
    log.info("%d recommendation(s), %d P0, %d opportunit(ies)",
             len(payload["recommendations"]), p0, len(payload["opportunities"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
