#!/usr/bin/env python3
"""
Agent 1 — SEO Scout.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Crawls the eight Search Console properties of the travel portfolio with ONE
service account (ARCHITECTURE.md §3.1), diffs demand (GSC) against supply
(sitemap), asks an LLM to classify and rank the gaps, and POSTs a signed
`content.brief.v1` payload to Agent 2 for each opportunity worth writing.

Runs on a GitHub Actions cron. Reads only — it never mutates a site.

    python agent1_seo_scout.py --list-properties
    python agent1_seo_scout.py --dry-run
    python agent1_seo_scout.py --domain boutimar.ir --limit 2
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import timedelta
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import compliance
import config
from config import (
    ARCHITECTURE_CREDIT,
    ConfigError,
    Site,
    build_envelope,
    idempotency_key,
    rfc3339,
    utc_now,
)

log = logging.getLogger("agent1.seo_scout")

AGENT_ID = "agent1.seo_scout"
TARGET_ID = "agent2.writer"

GSC_ROW_LIMIT = 25_000          # the API maximum per request
GSC_PAGE_SLEEP_S = 0.25         # 200 queries/min/site — stay well under it
MAX_CANDIDATES_TO_LLM = 40      # one batched LLM call per domain, not per keyword

# Rough organic CTR by position. Used only to spot a page that ranks well and
# still under-earns its clicks — i.e. a title/intent problem, not a volume one.
EXPECTED_CTR = {
    1: 0.28, 2: 0.15, 3: 0.11, 4: 0.08, 5: 0.06,
    6: 0.05, 7: 0.04, 8: 0.033, 9: 0.028, 10: 0.025,
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. Search Console — one service account, eight properties
# ══════════════════════════════════════════════════════════════════════════════


def build_gsc_client():
    """
    Authenticate with the single service-account key.

    The two historical Google accounts (alimozzarella@ and contactmozaffari@)
    are NOT merged by this credential and cannot be — there is no API for that.
    Each has separately granted this service account **Restricted** access to
    the properties it owns, which is what makes one key read all eight.
    See ARCHITECTURE.md §3.1.
    """
    info = config.load_service_account_info()
    try:
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=config.GSC_SCOPES
        )
    except (ValueError, GoogleAuthError) as exc:
        raise ConfigError(f"Service account key rejected by google-auth: {exc}") from exc

    log.info("GSC service account: %s", info["client_email"])
    # cache_discovery=False: the file cache is unusable on a read-only CI runner.
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def list_properties(service) -> list[dict[str, str]]:
    entries = service.sites().list().execute().get("siteEntry", [])
    return [
        {"siteUrl": e.get("siteUrl", ""), "permissionLevel": e.get("permissionLevel", "")}
        for e in entries
    ]


def audit_access(service, sites: list[Site]) -> list[str]:
    """
    Name the properties this key CANNOT see. The usual cause is that step 3 or 4
    of the setup was completed under only one of the two Google accounts.
    """
    visible = {p["siteUrl"] for p in list_properties(service)}
    missing = [s.property_uri for s in sites if s.property_uri not in visible]
    if missing:
        log.warning(
            "Service account cannot see %d propert%s: %s — add it as a Restricted "
            "user in Search Console under whichever Google account owns them "
            "(ARCHITECTURE.md §3.1).",
            len(missing),
            "y" if len(missing) == 1 else "ies",
            ", ".join(missing),
        )
    return missing


def _has_verification_txt(domain: str) -> bool | None:
    """
    Does this domain publish a google-site-verification TXT record?

    Resolved over DNS-over-HTTPS so it needs no resolver library and works from
    a CI runner. Returns None when the lookup itself fails — an unknown answer
    must not be reported as a confident "no".
    """
    try:
        r = requests.get(
            "https://dns.google/resolve",
            params={"name": domain, "type": "TXT"},
            timeout=8,
        )
        r.raise_for_status()
        answers = r.json().get("Answer") or []
        return any("google-site-verification=" in a.get("data", "") for a in answers)
    except Exception:  # network, DNS, malformed JSON — all mean "do not guess"
        return None


def diagnose_403(property_uri: str) -> str:
    """
    Turn a bare 403 into the instruction that will actually fix it.

    Search Console returns 403 both for "you are not a user on this property"
    and for "no such property", and the two need opposite responses. Telling
    someone to click *Add user* on a property that was never created sends them
    hunting through Settings for a screen that is not there — which is exactly
    what this pipeline told its owner for three days.

    A `sc-domain:` property cannot exist without a google-site-verification TXT
    record on the domain, so the DNS answer separates the two cases cleanly.
    """
    tail = property_uri.split(":", 1)[1] if property_uri.startswith("sc-domain:") else None
    if not tail:
        return (f"403 on {property_uri}: the service account is not a user on this "
                "property. Add it in Search Console → Settings → Users and "
                "permissions → Restricted.")

    verified = _has_verification_txt(tail)
    if verified is False:
        return (
            f"403 on {property_uri}: {tail} publishes NO google-site-verification "
            "TXT record, so this domain property does not exist yet. Granting "
            "access is not the fix and there is no Users-and-permissions screen "
            "to visit. Create the property first — Search Console → Add property "
            f"→ Domain → {tail} → copy the TXT record into the domain's DNS — "
            "then add the service account as a Restricted user. See SETUP-GSC.md."
        )
    if verified is None:
        return (
            f"403 on {property_uri}: could not resolve DNS to tell whether this "
            "property exists. Either it was never created, or it exists and the "
            "service account is not a user on it. See SETUP-GSC.md."
        )
    return (
        f"403 on {property_uri}: {tail} IS verified, so the property exists and "
        "the service account simply has no access to it. Search Console → "
        "Settings → Users and permissions → Add user → Restricted."
    )


def _search_analytics(
    service,
    property_uri: str,
    start: str,
    end: str,
    dimensions: list[str],
) -> list[dict[str, Any]]:
    """Paginated searchanalytics.query. Returns raw rows with `keys` intact."""
    rows: list[dict[str, Any]] = []
    start_row = 0
    while True:
        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": dimensions,
            "rowLimit": GSC_ROW_LIMIT,
            "startRow": start_row,
            "dataState": "final",
            "type": "web",
        }
        try:
            resp = (
                service.searchanalytics()
                .query(siteUrl=property_uri, body=body)
                .execute()
            )
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status == 403:
                raise PermissionError(diagnose_403(property_uri)) from exc
            if status == 429:
                log.warning("429 on %s — backing off 30s", property_uri)
                time.sleep(30)
                continue
            raise

        batch = resp.get("rows", [])
        rows.extend(batch)
        if len(batch) < GSC_ROW_LIMIT:
            break
        start_row += GSC_ROW_LIMIT
        time.sleep(GSC_PAGE_SLEEP_S)
    return rows


def collect_gsc(service, site: Site) -> dict[str, Any]:
    """Four passes per property: long window, short window, page map, country map."""
    end = (utc_now() - timedelta(days=site.data_lag_days)).date()
    long_start = end - timedelta(days=site.lookback_days)
    short_start = end - timedelta(days=site.trend_window_days)
    e, ls, ss = end.isoformat(), long_start.isoformat(), short_start.isoformat()

    long_rows = _search_analytics(service, site.property_uri, ls, e, ["query", "device"])
    short_rows = _search_analytics(service, site.property_uri, ss, e, ["query"])
    page_rows = _search_analytics(service, site.property_uri, ls, e, ["query", "page"])
    country_rows = _search_analytics(service, site.property_uri, ls, e, ["query", "country"])

    log.info(
        "%s — GSC rows: long=%d short=%d page=%d country=%d (%s → %s)",
        site.domain, len(long_rows), len(short_rows), len(page_rows), len(country_rows), ls, e,
    )
    return {
        "date_range": {"start": ls, "end": e},
        "short_range": {"start": ss, "end": e},
        "long_rows": long_rows,
        "short_rows": short_rows,
        "page_rows": page_rows,
        "country_rows": country_rows,
        "row_count": len(long_rows) + len(short_rows) + len(page_rows) + len(country_rows),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. Supply — what actually exists on the site
# ══════════════════════════════════════════════════════════════════════════════

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch_sitemap_urls(site: Site, session: requests.Session, depth: int = 0) -> set[str]:
    """
    Read sitemap.xml, following one level of <sitemapindex>. A failure here is
    non-fatal: with no supply signal every ranking query looks like a gap, so we
    degrade to 'unknown supply' and let the LLM step be the judge.

    ElementTree does not resolve external entities and raises on entity
    declarations, so an untrusted sitemap cannot pull an XXE here.
    """
    urls: set[str] = set()
    try:
        resp = session.get(site.sitemap, timeout=20, headers={"User-Agent": config.USER_AGENT})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except (requests.RequestException, ET.ParseError) as exc:
        log.warning("%s — sitemap unavailable (%s): %s", site.domain, site.sitemap, exc)
        return urls

    tag = root.tag.split("}")[-1]
    if tag == "sitemapindex" and depth == 0:
        for loc in root.findall(".//sm:sitemap/sm:loc", _SITEMAP_NS):
            child = (loc.text or "").strip()
            if not child:
                continue
            urls |= _fetch_child_sitemap(child, session)
    else:
        for loc in root.findall(".//sm:url/sm:loc", _SITEMAP_NS):
            if loc.text:
                urls.add(loc.text.strip())

    log.info("%s — sitemap lists %d URLs", site.domain, len(urls))
    return urls


def _fetch_child_sitemap(url: str, session: requests.Session) -> set[str]:
    out: set[str] = set()
    try:
        resp = session.get(url, timeout=20, headers={"User-Agent": config.USER_AGENT})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except (requests.RequestException, ET.ParseError) as exc:
        log.warning("child sitemap failed (%s): %s", url, exc)
        return out
    for loc in root.findall(".//sm:url/sm:loc", _SITEMAP_NS):
        if loc.text:
            out.add(loc.text.strip())
    return out


_SLUG_SPLIT = re.compile(r"[^0-9a-z؀-ۿ]+")


def _slug_tokens(url: str) -> set[str]:
    path = urlparse(url).path.lower()
    return {t for t in _SLUG_SPLIT.split(path) if len(t) > 2}


# ══════════════════════════════════════════════════════════════════════════════
# 3. The diff — demand minus supply
# ══════════════════════════════════════════════════════════════════════════════


def _agg(rows: Iterable[dict[str, Any]], key_index: int = 0) -> dict[str, dict[str, float]]:
    """Aggregate GSC rows on one dimension. Position is impression-weighted."""
    acc: dict[str, dict[str, float]] = defaultdict(
        lambda: {"clicks": 0.0, "impressions": 0.0, "pos_weight": 0.0}
    )
    for row in rows:
        keys = row.get("keys") or []
        if len(keys) <= key_index:
            continue
        a = acc[keys[key_index]]
        imps = float(row.get("impressions", 0))
        a["clicks"] += float(row.get("clicks", 0))
        a["impressions"] += imps
        a["pos_weight"] += float(row.get("position", 0)) * imps
    out: dict[str, dict[str, float]] = {}
    for key, a in acc.items():
        imps = a["impressions"]
        out[key] = {
            "clicks": a["clicks"],
            "impressions": imps,
            "ctr": (a["clicks"] / imps) if imps else 0.0,
            "position": (a["pos_weight"] / imps) if imps else 0.0,
        }
    return out


def _device_split(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, float]]:
    per_query: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        per_query[keys[0]][keys[1].lower()] += float(row.get("impressions", 0))
    out: dict[str, dict[str, float]] = {}
    for query, devices in per_query.items():
        total = sum(devices.values()) or 1.0
        out[query] = {d: round(v / total, 3) for d, v in devices.items()}
    return out


def _top_by_second_key(rows: Iterable[dict[str, Any]]) -> dict[str, list[tuple[str, float, float]]]:
    """query -> [(second_key, impressions, position)] sorted by impressions desc."""
    per_query: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    for row in rows:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        per_query[keys[0]].append(
            (keys[1], float(row.get("impressions", 0)), float(row.get("position", 0)))
        )
    for query in per_query:
        per_query[query].sort(key=lambda t: t[1], reverse=True)
    return per_query


def _trend(long_ctx: dict[str, float], short_ctx: dict[str, float] | None,
           long_days: int, short_days: int) -> str:
    if not short_ctx or not long_ctx["impressions"]:
        return "flat"
    long_rate = long_ctx["impressions"] / max(long_days, 1)
    short_rate = short_ctx["impressions"] / max(short_days, 1)
    if long_rate <= 0:
        return "flat"
    ratio = short_rate / long_rate
    return "rising" if ratio > 1.15 else "falling" if ratio < 0.85 else "flat"


def find_gaps(site: Site, gsc: dict[str, Any], sitemap_urls: set[str]) -> list[dict[str, Any]]:
    """Turn raw GSC rows into scored, typed gap candidates. No LLM involved yet."""
    long_agg = _agg(gsc["long_rows"])
    short_agg = _agg(gsc["short_rows"])
    devices = _device_split(gsc["long_rows"])
    pages_by_query = _top_by_second_key(gsc["page_rows"])
    countries_by_query = _top_by_second_key(gsc["country_rows"])
    sitemap_tokens = {url: _slug_tokens(url) for url in sitemap_urls}

    candidates: list[dict[str, Any]] = []
    for query, m in long_agg.items():
        if m["impressions"] < site.min_impressions or m["position"] > site.max_position:
            continue

        ranked = pages_by_query.get(query, [])
        top_url = ranked[0][0] if ranked else None
        # Cannibalisation: a second URL carrying at least 40% of the leader's
        # impressions means two pages are splitting one intent.
        cannibal = (
            len(ranked) > 1
            and ranked[0][1] > 0
            and (ranked[1][1] / ranked[0][1]) >= 0.40
        )

        query_tokens = {t for t in _SLUG_SPLIT.split(query.lower()) if len(t) > 2}
        covered = any(
            query_tokens and len(query_tokens & tokens) >= max(1, len(query_tokens) // 2)
            for tokens in sitemap_tokens.values()
        )

        expected = EXPECTED_CTR.get(int(round(m["position"])), 0.02)
        underperforming = bool(top_url) and m["position"] <= 10 and m["ctr"] < expected * 0.6

        # Already won. A query sitting in the top 3 and earning at least the
        # expected CTR has nothing left to gain — and must never be typed
        # missing_page just because the page dimension came back empty, which is
        # what GSC does for brand-navigational terms.
        if m["position"] <= 3.0 and m["ctr"] >= expected:
            continue

        if not top_url and not covered:
            gap_type = "missing_page"
        elif cannibal:
            gap_type = "cannibalisation"
        elif underperforming:
            gap_type = "serp_feature_loss"
        elif top_url and m["position"] > 10:
            gap_type = "thin_content"
        else:
            continue  # ranking, earning its clicks — leave it alone

        # Local score: volume × how close the win is. The LLM refines this; it
        # does not get to invent it from nothing.
        proximity = max(0.0, min(1.0, (site.max_position - m["position"]) / site.max_position))
        local_score = m["impressions"] * (0.35 + 0.65 * proximity)

        countries = countries_by_query.get(query, [])
        candidates.append(
            {
                "query": query,
                "gap_type": gap_type,
                "impressions": int(m["impressions"]),
                "clicks": int(m["clicks"]),
                "ctr": round(m["ctr"], 4),
                "position": round(m["position"], 1),
                "best_position": round(min((p for _, _, p in ranked), default=m["position"]), 1),
                "trend": _trend(m, short_agg.get(query), site.lookback_days, site.trend_window_days),
                "current_url": top_url,
                "competing_urls": [u for u, _, _ in ranked[1:4]],
                "top_country": countries[0][0] if countries else None,
                "device_split": devices.get(query, {}),
                "covered_by_sitemap": covered,
                "local_score": round(local_score, 1),
            }
        )

    candidates.sort(key=lambda c: c["local_score"], reverse=True)
    log.info("%s — %d gap candidates above threshold", site.domain, len(candidates))
    return candidates[:MAX_CANDIDATES_TO_LLM]


# ══════════════════════════════════════════════════════════════════════════════
# 4. OpenAI — classify, prioritise, outline (one batched call per domain)
# ══════════════════════════════════════════════════════════════════════════════

GAP_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["briefs"],
    "properties": {
        "briefs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "primary_keyword", "gap_type", "search_intent", "priority_score",
                    "priority_inputs", "rationale", "working_title", "content_type",
                    "target_url_path", "word_count_min", "word_count_max", "outline",
                    "secondary_keywords", "must_include", "must_avoid",
                    "meta_title", "meta_description", "schema_org",
                ],
                "properties": {
                    "primary_keyword": {"type": "string"},
                    "gap_type": {
                        "type": "string",
                        "enum": [
                            "missing_page", "thin_content", "cannibalisation",
                            "stale_content", "serp_feature_loss",
                            "competitor_outranking", "untranslated",
                        ],
                    },
                    "search_intent": {
                        "type": "string",
                        "enum": ["informational", "commercial", "transactional", "navigational"],
                    },
                    # No minimum/maximum here: neither OpenAI strict mode nor
                    # Anthropic structured outputs support numeric constraints.
                    # Clamped in code instead — see _clamp_analysis.
                    "priority_score": {"type": "integer"},
                    "priority_inputs": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["volume", "position_proximity", "commercial_value", "effort"],
                        "properties": {
                            "volume": {"type": "number"},
                            "position_proximity": {"type": "number"},
                            "commercial_value": {"type": "number"},
                            "effort": {"type": "number"},
                        },
                    },
                    "rationale": {"type": "string"},
                    "working_title": {"type": "string"},
                    "content_type": {
                        "type": "string",
                        "enum": ["guide", "landing", "itinerary", "comparison", "faq",
                                 "news", "translation"],
                    },
                    "target_url_path": {"type": "string"},
                    "word_count_min": {"type": "integer"},
                    "word_count_max": {"type": "integer"},
                    "secondary_keywords": {"type": "array", "items": {"type": "string"}},
                    "outline": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["h", "heading", "must_cover"],
                            "properties": {
                                "h": {"type": "integer"},
                                "heading": {"type": "string"},
                                "must_cover": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "must_include": {"type": "array", "items": {"type": "string"}},
                    "must_avoid": {"type": "array", "items": {"type": "string"}},
                    "meta_title": {"type": "string"},
                    "meta_description": {"type": "string"},
                    "schema_org": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def _analysis_system_prompt(site: Site) -> str:
    """Shared by both providers — the instruction is about the task, not the vendor."""
    return "\n".join([
        "You are the SEO analyst of a luxury travel group. You convert Search "
        "Console gap data into content briefs. You are analytical, not "
        "promotional: you do not write the article, you specify it.",
        "",
        f"Brand: {site.brand}. Domain: {site.domain}. Locale: {site.locale}.",
        f"Write every brief field in the site's language ({site.locale}); keep "
        "keywords exactly as they appear in the Search Console data.",
        "",
        "target_url_path must be a lowercase ASCII slug beginning with '/' even "
        "for Farsi pages — the sites do not use percent-encoded URLs. Transliterate "
        "rather than leaving a placeholder.",
        "Never propose a path that already exists in the supplied sitemap sample.",
        "",
        compliance.prompt_constraints(site.compliance_profile),
        "",
        "Put the Persian Gulf and visa rules into every brief's must_avoid list "
        "so the writing agent inherits them.",
        "",
        # From heytony.ca's 100-AI-Overview study (Aug 2026): pages whose figures
        # AGREED with the consensus number in the answer were ~12 points more
        # likely to be cited, and the effect was stronger among citations that
        # persisted across checks. "You're not being judged on quality. You're
        # being matched on agreement." Agreement is the entry ticket; the real
        # number is the differentiation.
        "EVERY brief's must_include list MUST contain two entries, in this order:",
        "  1. A statement of the CONSENSUS figure for the topic — the number, "
        "duration or band a reader would meet everywhere else — stated plainly "
        "and early, in the first section. A consensus figure is something you "
        "OBSERVED, not something you estimated: it must come from the supplied "
        "data, the site's own live feed, or a named public source, and the brief "
        "must say which. Write the instruction so the writer states the figure "
        "WITH its source attached.",
        "  NEVER instruct the writer to state a PRICE as consensus unless the "
        "number is in the live feed with a price_asof timestamp. Prices are the "
        "one figure the writer may not reconstruct, and a plausible-looking "
        "nightly band is the exact failure this rule keeps producing: run #9 was "
        "blocked for '$50 to $150 USD per room', a number nobody measured. If "
        "there is no sourced price, make the consensus a NON-PRICE figure — "
        "duration, distance, season length, room count, sailing frequency — or "
        "write 'no sourced consensus figure available; state the range only if "
        "the draft can cite one'.",
        "  2. At least one fact that is TRUE OF THIS BUSINESS AND NOBODY ELSE — "
        "a real fare from the live feed, a real port fee, a real sailing date, a "
        "real cabin category. Frame it as our own experience, placed after the "
        "consensus.",
        "If no proprietary fact is available for a topic, say so in must_include "
        "rather than inventing one. A brief with no distinctive fact is a brief "
        "for a page a larger competitor can copy in an afternoon.",
        "",
        # Same study, Finding 6: question-format titles matching the query
        # structure showed NO positive correlation with citation.
        "Do NOT require question-shaped headings. Testing found no citation "
        "benefit from question-format titles. Use them where they genuinely read "
        "better for a person, never as an optimisation.",
    ])


def _analysis_user_prompt(site: Site, candidates: list[dict[str, Any]], limit: int) -> str:
    return json.dumps(
        {
            "site": {
                "domain": site.domain, "brand": site.brand, "locale": site.locale,
                "market": site.market, "base_url": site.base_url,
            },
            "instruction": (
                f"Select AT MOST {limit} opportunities from the candidates and "
                "produce one brief for each. Fewer is correct when the candidates "
                "do not justify more. Score priority 0-100 using volume, position "
                "proximity, commercial value and effort. Reject candidates that are "
                "brand-navigational, and MERGE any that share an intent — two "
                "spellings of one query are one page, not two."
            ),
            "candidates": candidates,
        },
        ensure_ascii=False,
    )


def _clamp_analysis(a: dict[str, Any]) -> dict[str, Any]:
    """
    Bounds that used to live in the JSON schema. Neither OpenAI strict mode nor
    Anthropic structured outputs accept numeric constraints, so they are applied
    here rather than silently trusted.
    """
    a["priority_score"] = max(0, min(100, int(a.get("priority_score", 50))))
    for section in a.get("outline", []):
        section["h"] = max(2, min(3, int(section.get("h", 2))))
    lo = max(100, int(a.get("word_count_min", 1200)))
    hi = max(lo, int(a.get("word_count_max", 1800)))
    a["word_count_min"], a["word_count_max"] = lo, hi
    return a


def analyse_gaps(
    site: Site, candidates: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """
    One call per domain, batched over its candidates. Returns at most `limit`
    briefs. On any provider failure we fall back to the deterministic builder —
    a degraded run beats a dead one.

    Provider is config.GAP_ANALYSIS_PROVIDER: `gemini` (default), `anthropic`,
    or `openai`. The step is analytical — classify, deduplicate, rank, outline —
    and all three do it well. Gemini is the default because this is the
    pipeline's highest-volume model call (once per property, every night) and
    the free tier has no balance to exhaust; Anthropic held the default until
    its $5 ran out on 12 Aug 2026 and took the head of the chain with it.
    """
    if not candidates:
        return []

    if _PROVIDER_DOWN.get("reason"):
        # Already established, on an earlier site, that this account cannot call
        # the model at all. Asking again produces the same 400 and a second
        # identical line in the summary.
        return [_fallback_brief(site, c, _PROVIDER_DOWN["reason"])
                for c in candidates[:limit]]

    if config.GAP_ANALYSIS_PROVIDER == "gemini":
        return _analyse_with_gemini(site, candidates, limit)

    if config.GAP_ANALYSIS_PROVIDER == "anthropic":
        return _analyse_with_anthropic(site, candidates, limit)

    # Import and client construction sit inside the guarded path on purpose. A
    # missing `openai` package or an unset key is precisely the "provider
    # unavailable" case the fallback exists for — letting either crash the run
    # would lose every other domain's work too.
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.require_env("OPENAI_API_KEY"))
    except (ImportError, ConfigError) as exc:
        log.error(
            "%s — OpenAI unavailable (%s); using the deterministic fallback. "
            "Candidates will not be deduplicated or ranked.",
            site.domain, exc,
        )
        return [_fallback_brief(site, c, f"OpenAI unavailable: {exc}")
                for c in candidates[:limit]]

    try:
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": _analysis_system_prompt(site)},
                {"role": "user", "content": _analysis_user_prompt(site, candidates, limit)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "gap_analysis",
                    "strict": True,
                    "schema": GAP_ANALYSIS_SCHEMA,
                },
            },
        )
        content = resp.choices[0].message.content or "{}"
        briefs = json.loads(content).get("briefs", [])
        usage = getattr(resp, "usage", None)
        if usage:
            log.info(
                "%s — OpenAI %s: %s in / %s out",
                site.domain, config.OPENAI_MODEL,
                getattr(usage, "prompt_tokens", "?"), getattr(usage, "completion_tokens", "?"),
            )
        return [_clamp_analysis(b) for b in briefs[:limit]]
    except Exception as exc:  # provider outage, quota, schema refusal
        log.error("%s — OpenAI step failed (%s); using deterministic fallback", site.domain, exc)
        reason = f"OpenAI call failed: {exc}"
        if config.terminal_provider_error(str(exc)):
            _PROVIDER_DOWN["reason"] = reason
            log.error("This is an account-level failure — skipping the model for "
                      "every remaining site rather than repeating the same call.")
        return [_fallback_brief(site, c, reason) for c in candidates[:limit]]


# Analysis, not prose. Agent 2 drafts at temperature 0.85 for voice; this step
# classifies, deduplicates, ranks and outlines, where a wandering sampler just
# produces a different ranking each night for the same data.
_GEMINI_ANALYSIS_CONFIG = {
    "temperature": 0.2,
    "top_p": 0.95,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}


def _analyse_with_gemini(
    site: Site, candidates: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """
    Same contract as the other two paths, same schema, same fallback on failure.

    Reuses Agent 2's model resolution rather than pinning a name. That machinery
    exists because pinning failed twice in one evening: gemini-2.5-pro answers
    429 "limit: 0" (absent from the free tier, which reads as rate-limiting and
    is not), and gemini-2.5-flash answers 404 "no longer available" for keys
    issued after its withdrawal. Asking the account what it can call beats
    asserting it. The import is deferred so a missing FastAPI or pydantic never
    breaks the scout at module load — this agent does not otherwise need them.
    """
    try:
        from agent2_writer_listener import mark_model_unusable, resolve_model
        model_name = resolve_model()
    except Exception as exc:
        log.error(
            "%s — Gemini unavailable (%s); using the deterministic fallback. "
            "Candidates will not be deduplicated or ranked.", site.domain, exc,
        )
        return [_fallback_brief(site, c, f"Gemini unavailable: {exc}")
                for c in candidates[:limit]]

    system = _analysis_system_prompt(site)
    prompt = _analysis_user_prompt(site, candidates, limit)

    # One retry, and only for the one failure that a retry can fix: the model
    # being withdrawn for this key, where resolve_model() hands back a different
    # name. Retrying anything else here just doubles the latency.
    for attempt in (1, 2):
        try:
            text, usage = _gemini_generate(system, prompt, model_name)
            briefs = json.loads(text).get("briefs", [])
            if usage:
                log.info("%s — Gemini %s: %s in / %s out", site.domain, model_name,
                         getattr(usage, "prompt_token_count", "?"),
                         getattr(usage, "candidates_token_count", "?"))
            if not briefs:
                raise ValueError("model returned no briefs")
            return [_clamp_analysis(b) for b in briefs[:limit]]
        except Exception as exc:
            msg = str(exc)
            if attempt == 1 and "NOT_FOUND" in msg and "no longer available" in msg:
                mark_model_unusable(model_name)
                nxt = resolve_model()
                if nxt != model_name:
                    log.warning("%s is withdrawn for this key — retrying with %s",
                                model_name, nxt)
                    model_name = nxt
                    continue
            log.error("%s — Gemini step failed (%s); using deterministic fallback",
                      site.domain, exc)
            reason = f"Gemini call failed: {exc}"
            if config.terminal_provider_error(msg):
                _PROVIDER_DOWN["reason"] = reason
                log.error("This is an account-level failure — skipping the model for "
                          "every remaining site rather than repeating the same call.")
            return [_fallback_brief(site, c, reason) for c in candidates[:limit]]

    # Unreachable: every path in the loop returns. Present so a future edit that
    # adds a `continue` cannot fall out of the function returning None.
    return [_fallback_brief(site, c, "Gemini retries exhausted")
            for c in candidates[:limit]]


def _gemini_generate(system: str, prompt: str, model_name: str) -> tuple[str, Any]:
    """
    One Gemini generation. Returns (text, usage_metadata).

    Two SDKs because Google shipped a replacement: `google-genai` is the current
    unified client and is preferred when installed; `google-generativeai` is the
    legacy package and the fallback. Same shape as Agent 2's caller — the
    generation config differs, the transport does not.
    """
    try:
        from google import genai as new_genai
        from google.genai import types as genai_types

        client = new_genai.Client(api_key=config.require_env("GEMINI_API_KEY"))
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system, **_GEMINI_ANALYSIS_CONFIG
            ),
        )
        return (resp.text or "").strip(), getattr(resp, "usage_metadata", None)
    except ImportError:
        pass

    import google.generativeai as genai   # legacy SDK — deprecated by Google

    genai.configure(api_key=config.require_env("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system,
        generation_config=_GEMINI_ANALYSIS_CONFIG,
    )
    resp = model.generate_content(prompt)
    return (resp.text or "").strip(), getattr(resp, "usage_metadata", None)


def _analyse_with_anthropic(
    site: Site, candidates: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """
    Same contract as the OpenAI path, same schema, same fallback on failure.

    Request-shape notes for this model family: no temperature/top_p/top_k (a
    400), thinking is on by default and `budget_tokens` is a 400 — depth is
    `output_config.effort`. Structured output replaces the assistant prefill
    that older code would have used to force JSON.
    """
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=config.require_env("ANTHROPIC_API_KEY"))
    except (ImportError, ConfigError) as exc:
        log.error(
            "%s — Anthropic unavailable (%s); using the deterministic fallback. "
            "Candidates will not be deduplicated or ranked.", site.domain, exc,
        )
        return [_fallback_brief(site, c, f"Anthropic unavailable: {exc}")
                for c in candidates[:limit]]

    kwargs: dict[str, Any] = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": 16000,
        "system": _analysis_system_prompt(site),
        "messages": [{"role": "user", "content": _analysis_user_prompt(site, candidates, limit)}],
        "output_config": {
            "effort": config.ANTHROPIC_EFFORT,
            "format": {"type": "json_schema", "schema": GAP_ANALYSIS_SCHEMA},
        },
    }
    if config.ANTHROPIC_FALLBACKS.lower() not in {"", "off", "false", "0"}:
        kwargs["betas"] = [config.ANTHROPIC_FALLBACK_BETA]
        kwargs["fallbacks"] = config.ANTHROPIC_FALLBACKS
        create = client.beta.messages.create
    else:
        create = client.messages.create

    try:
        resp = create(**kwargs)
        # Check stop_reason before touching content — a refusal leaves it empty.
        if getattr(resp, "stop_reason", None) == "refusal":
            detail = getattr(resp, "stop_details", None)
            raise RuntimeError(
                f"declined by safety classifiers (category="
                f"{getattr(detail, 'category', None)!r})"
            )
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        ).strip()
        briefs = json.loads(text).get("briefs", [])
        usage = getattr(resp, "usage", None)
        if usage:
            log.info(
                "%s — Claude %s: %s in / %s out", site.domain,
                getattr(resp, "model", config.ANTHROPIC_MODEL),
                getattr(usage, "input_tokens", "?"), getattr(usage, "output_tokens", "?"),
            )
        if not briefs:
            raise ValueError("model returned no briefs")
        return [_clamp_analysis(b) for b in briefs[:limit]]
    except Exception as exc:
        log.error("%s — Claude step failed (%s); using deterministic fallback",
                  site.domain, exc)
        reason = f"Claude call failed: {exc}"
        if config.terminal_provider_error(str(exc)):
            _PROVIDER_DOWN["reason"] = reason
            log.error("This is an account-level failure — skipping the model for "
                      "every remaining site rather than repeating the same call.")
        return [_fallback_brief(site, c, reason) for c in candidates[:limit]]


# Set the first time a provider says something that will be equally true for
# every remaining site — an exhausted credit balance, a revoked key, a model the
# plan does not include. Run #12 made the same failing Claude call once per
# domain and printed the same "credit balance is too low" four times; the second
# call was never going to succeed, and on a ten-property portfolio that is ten
# round-trips to learn one fact.
# A dict rather than a module-level string so the two analysis functions can set
# it without a `global` declaration in each.
_PROVIDER_DOWN: dict[str, str] = {}

def _fallback_brief(site: Site, c: dict[str, Any], reason: str = "") -> dict[str, Any]:
    """
    No-LLM brief. Coarser, but every field the schema needs is present.

    "Every field the schema needs" is a lower bar than "a brief worth writing",
    and run #10 showed the gap. The LLM step failed for every site, this builder
    produced all 14 briefs, and Agent 1 reported Success — because a degraded
    run is designed to beat a dead one. What nobody saw was that the briefs
    carried `must_include: []`, so the consensus figure and the proprietary
    fact — the only two things measured to affect AI citation — were silently
    absent from every one of them, and the target paths were raw slugs
    (`/iranoilshow`, and `/opportunity` for a Farsi keyword that strips to
    nothing in ASCII). Four of them then spent a Gemini call each.

    So the marker below is not decoration. `_degraded` is counted into the run
    manifest, annotated on the workflow, and read by Agent 2, which will not
    spend a model call on a brief that cannot satisfy the pipeline's own rules.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", c["query"].lower()).strip("-") or "opportunity"
    return {
        "_degraded": True,
        # Why the model did not answer, carried to the manifest and the run
        # summary. Without it the only way to learn that a green run produced
        # nothing usable is to expand a collapsed log step by hand.
        "_degraded_reason": config.redact(reason)[:300],
        "primary_keyword": c["query"],
        "gap_type": c["gap_type"],
        "search_intent": "commercial",
        "priority_score": min(100, int(c["local_score"] / max(c["impressions"], 1) * 100) + 40),
        "priority_inputs": {
            "volume": min(1.0, c["impressions"] / 5000),
            "position_proximity": max(0.0, (site.max_position - c["position"]) / site.max_position),
            "commercial_value": 0.5,
            "effort": 0.5,
        },
        "rationale": (
            f"{c['impressions']} impressions at position {c['position']} "
            f"({c['gap_type']}); generated without the LLM step."
        ),
        "working_title": c["query"],
        "content_type": "guide",
        "target_url_path": f"/{slug}"[:120],
        "word_count_min": 1200,
        "word_count_max": 1800,
        "secondary_keywords": [],
        "outline": [{"h": 2, "heading": c["query"], "must_cover": []}],
        "must_include": [],
        "must_avoid": ["Arabian Gulf", "خلیج عربی", "بدون ویزا", "visa-free"],
        "meta_title": c["query"][:60],
        "meta_description": "",
        "schema_org": ["Article", "BreadcrumbList"],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. Payload assembly — content.brief.v1 (ARCHITECTURE.md §4.1)
# ══════════════════════════════════════════════════════════════════════════════

_HARD_AVOID = ["Arabian Gulf", "خلیج عربی", "بدون ویزا", "visa-free", "no visa required"]


def build_brief_payload(
    site: Site,
    analysis: dict[str, Any],
    candidate: dict[str, Any],
    gsc_meta: dict[str, Any],
    run_id: str,
    callback_url: str,
    dry_run: bool,
) -> dict[str, Any]:
    path = analysis["target_url_path"]
    if not path.startswith("/"):
        path = "/" + path

    must_avoid = list(dict.fromkeys(list(analysis.get("must_avoid", [])) + _HARD_AVOID))

    return {
        "schema_version": config.SCHEMA_VERSION,
        "envelope": build_envelope(
            message_type="content.brief",
            emitted_by=AGENT_ID,
            target=TARGET_ID,
            correlation_id=run_id,
            idem_key=idempotency_key(site.domain, analysis["primary_keyword"], path),
        ),
        "site": {
            "domain": site.domain,
            "property_uri": site.property_uri,
            "brand": site.brand,
            "locale": site.locale,
            "market": site.market,
            "base_url": site.base_url,
            "cms": {
                "type": site.cms.get("type", "unknown"),
                "adapter": site.cms.get("adapter"),
                "content_root": site.cms.get("content_root", "/"),
                "publish_mode": site.cms.get("publish_mode", "draft"),
            },
        },
        "opportunity": {
            "gap_type": analysis["gap_type"],
            "primary_keyword": analysis["primary_keyword"],
            "keyword_locale": site.locale,
            "secondary_keywords": analysis.get("secondary_keywords", []),
            "search_intent": analysis["search_intent"],
            "gsc": {
                "date_range": gsc_meta["date_range"],
                "impressions": candidate["impressions"],
                "clicks": candidate["clicks"],
                "ctr": candidate["ctr"],
                "avg_position": candidate["position"],
                "best_position": candidate["best_position"],
                "trend_28d": candidate["trend"],
                "top_country": candidate["top_country"],
                "current_url": candidate["current_url"],
                "device_split": candidate["device_split"],
            },
            "serp": {
                "checked_at": rfc3339(),
                "competitors": [{"rank": i + 1, "url": u} for i, u in
                                enumerate(candidate.get("competing_urls", []))],
                "features": [],
                "source": "gsc_inference",   # open decision O-4
            },
            "priority_score": analysis["priority_score"],
            "priority_inputs": analysis["priority_inputs"],
            "rationale": analysis["rationale"],
        },
        "brief": {
            "working_title": analysis["working_title"],
            "content_type": analysis["content_type"],
            "target_url_path": path,
            "language": site.locale,
            "word_count_target": {
                "min": analysis["word_count_min"],
                "max": analysis["word_count_max"],
            },
            "reading_level": "general",
            "tone": "poetic-luxury",
            "outline": analysis["outline"],
            "must_include": analysis.get("must_include", []),
            "must_avoid": must_avoid,
            "internal_links": [],
            "external_sources": [],
            "schema_org": analysis.get("schema_org", ["Article"]),
            "meta": {
                "title": analysis["meta_title"],
                "description": analysis["meta_description"],
                "og_image_hint": None,
            },
            "media": {
                "hero_required": True,
                "allowed_sources": ["licensed_library", "supplier_press_kit"],
                "credit_required": True,
            },
            "data_dependencies": site.data_dependencies,
            # Carried onto the wire so a downstream agent can tell a ranked,
            # outlined brief from a slug and an impression count. Agent 2 reads
            # this; without it the two are indistinguishable in the payload.
            "degraded_no_llm": bool(analysis.get("_degraded")),
        },
        "compliance": {
            "profile": site.compliance_profile,
            # .get, not [] — an unknown profile in sites.yml must not take the
            # run down; it falls back to the strictest defaults.
            **compliance.PROFILES.get(site.compliance_profile, compliance.PROFILES["boutimar_v1"]),
            "blocking": True,
        },
        "routing": {
            "callback_url": callback_url,
            "priority": "high" if analysis["priority_score"] >= 80 else "normal",
            "deadline": rfc3339(utc_now() + timedelta(days=3)),
            "dry_run": dry_run,
        },
    }


def self_check_brief(payload: dict[str, Any]) -> list[compliance.Violation]:
    """
    Run the compliance gate on the brief we are about to emit. A brief that
    itself says "Arabian Gulf" would poison every downstream prompt.
    """
    brief = payload["brief"]
    # One clause per line, and `must_avoid` excluded — see compliance.assertive_surface.
    surface = compliance.assertive_surface(
        [
            payload["opportunity"]["primary_keyword"],
            payload["opportunity"]["rationale"],
            brief["working_title"],
            brief["meta"]["title"],
            brief["meta"]["description"],
            [section.get("heading", "") for section in brief["outline"]],
            [s.get("must_cover", []) for s in brief["outline"]],
            brief["must_include"],
        ]
    )
    profile = payload["compliance"]["profile"]
    if profile not in compliance.PROFILES:
        log.warning("unknown compliance profile %r — falling back to boutimar_v1", profile)
        profile = "boutimar_v1"
    return compliance.check(
        surface,
        profile,
        context={
            "priced_facts": bool(brief["data_dependencies"]),
            "price_asof": rfc3339() if brief["data_dependencies"] else None,
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# 6. Delivery — signed POST with bounded retries
# ══════════════════════════════════════════════════════════════════════════════


def deliver(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    secret: str,
) -> tuple[bool, str]:
    """At-least-once. 5xx/429/timeouts retry; other 4xx are terminal."""
    message_id = payload["envelope"]["message_id"]
    reason = "not attempted"

    for attempt in range(1, config.WEBHOOK_MAX_ATTEMPTS + 1):
        # Re-serialise per attempt: envelope.attempt is part of the signed body,
        # so bumping the counter after signing would ship a stale count.
        payload["envelope"]["attempt"] = attempt
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = config.signed_headers(secret, body, message_id)
        try:
            resp = session.post(
                url, data=body, headers=headers, timeout=config.WEBHOOK_TIMEOUT_S
            )
        except requests.RequestException as exc:
            reason = f"transport error: {exc}"
        else:
            if 200 <= resp.status_code < 300:
                return True, f"{resp.status_code}"
            reason = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in (408, 429) and resp.status_code < 500:
                log.error("delivery %s — terminal %s", message_id, reason)
                return False, reason

        if attempt == config.WEBHOOK_MAX_ATTEMPTS:
            log.error("delivery %s — giving up after %d attempts: %s",
                      message_id, attempt, reason)
            return False, reason

        backoff = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
        log.warning("delivery %s — attempt %d failed (%s); retrying in %.1fs",
                    message_id, attempt, reason, backoff)
        time.sleep(backoff)

    return False, "exhausted"   # unreachable; keeps the type checker honest


def write_dead_letter(run_dir, payload: dict[str, Any], reason: str) -> None:
    dlq = run_dir / "dlq"
    dlq.mkdir(parents=True, exist_ok=True)
    envelope = payload["envelope"]
    (dlq / f"{envelope['message_id']}.json").write_text(
        json.dumps(
            {
                "schema_version": config.SCHEMA_VERSION,
                "envelope": {**envelope, "message_type": "pipeline.error"},
                "error": {
                    "stage": AGENT_ID,
                    "kind": "transport",
                    "message": reason,
                    "retryable": True,
                    "attempts": envelope.get("attempt", 0),
                    "original_message_id": envelope["message_id"],
                },
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 7. Run
# ══════════════════════════════════════════════════════════════════════════════


def process_site(
    service,
    site: Site,
    session: requests.Session,
    run_id: str,
    run_dir,
    *,
    limit: int,
    dry_run: bool,
    use_llm: bool,
    webhook_url: str,
    callback_url: str,
    secret: str,
) -> dict[str, Any]:
    started = time.time()
    stat: dict[str, Any] = {
        "domain": site.domain, "status": "ok", "gsc_rows": 0, "candidates": 0,
        "briefs_emitted": 0, "delivered": 0, "dlq": 0, "blocked": 0,
        # Briefs this site produced without the LLM step. Green-but-degraded is
        # the run state that hides best, so it gets its own counter rather than
        # living only in a log line nobody scrolls to.
        "degraded_briefs": 0, "degraded_reason": "", "error": None,
    }
    try:
        gsc = collect_gsc(service, site)
        stat["gsc_rows"] = gsc["row_count"]

        sitemap_urls = fetch_sitemap_urls(site, session)
        candidates = find_gaps(site, gsc, sitemap_urls)
        stat["candidates"] = len(candidates)

        # A held site is not live. Keep gathering its demand — knowing what
        # people already search for is exactly what you want on launch day —
        # but write nothing for a site that cannot publish it.
        if site.on_hold:
            stat["status"] = "hold"
            stat["note"] = (
                f"{len(candidates)} gap candidate(s) recorded; no briefs emitted "
                "because the site is on hold"
            )
            (run_dir / "demand").mkdir(parents=True, exist_ok=True)
            (run_dir / "demand" / f"{site.domain}.json").write_text(
                json.dumps(
                    {"domain": site.domain, "status": "hold",
                     "date_range": gsc["date_range"], "candidates": candidates},
                    ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("%s — on hold; demand banked, no briefs", site.domain)
            return stat

        if not candidates:
            return stat

        by_query = {c["query"]: c for c in candidates}
        analyses = (
            analyse_gaps(site, candidates, limit)
            if use_llm
            else [_fallback_brief(site, c, "--no-llm requested")
                  for c in candidates[:limit]]
        )

        for analysis in analyses:
            candidate = by_query.get(analysis["primary_keyword"]) or candidates[0]
            payload = build_brief_payload(
                site, analysis, candidate, gsc, run_id, callback_url, dry_run
            )

            violations = self_check_brief(payload)
            blocking = [v for v in violations if v.severity == compliance.BLOCK]
            if blocking:
                stat["blocked"] += 1
                log.error(
                    "%s — brief for %r blocked: %s",
                    site.domain, analysis["primary_keyword"],
                    "; ".join(f"{v.rule}: {v.message}" for v in blocking),
                )
                write_dead_letter(run_dir, payload, f"compliance: {blocking[0].rule}")
                stat["dlq"] += 1
                continue
            payload["compliance"]["preflight"] = compliance.summarise(
                violations, payload["compliance"]["profile"]
            )
            stat["briefs_emitted"] += 1
            if analysis.get("_degraded"):
                stat["degraded_briefs"] += 1
                stat["degraded_reason"] = (stat.get("degraded_reason")
                                           or analysis.get("_degraded_reason", ""))

            briefs_dir = run_dir / "briefs"
            briefs_dir.mkdir(parents=True, exist_ok=True)
            (briefs_dir / f"{payload['envelope']['message_id']}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if dry_run:
                log.info(
                    "[dry-run] %s ← %r (score %s) → %s",
                    site.domain, analysis["primary_keyword"],
                    analysis["priority_score"], payload["brief"]["target_url_path"],
                )
                continue

            ok, reason = deliver(session, webhook_url, payload, secret)
            if ok:
                stat["delivered"] += 1
            else:
                stat["dlq"] += 1
                write_dead_letter(run_dir, payload, reason)

    except PermissionError as exc:
        # A property nobody has granted yet is a configuration gap, not a run
        # failure. It is already named at startup and it persists for as long as
        # it takes a human to click Add user in another Google account — days,
        # sometimes weeks. Failing the run on it makes the daily cron
        # permanently red, and a cron that is always red is a cron nobody reads.
        # It stays loud (ERROR, named in the manifest) without burying the day
        # something genuinely breaks.
        stat["status"] = "not_granted"
        stat["error"] = config.redact(str(exc))
        log.error("%s — skipped: %s", site.domain, stat["error"])
    except (HttpError, ConfigError) as exc:
        stat["status"] = "failed"
        stat["error"] = config.redact(str(exc))
        log.error("%s — aborted: %s", site.domain, stat["error"])

    stat["duration_ms"] = int((time.time() - started) * 1000)
    return stat


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent 1 — SEO Scout. Architecture credit: Albaloo Studio."
    )
    parser.add_argument("--domain", action="append", help="restrict to a domain (repeatable)")
    parser.add_argument("--limit", type=int, default=None, help="max briefs per domain")
    parser.add_argument("--dry-run", action="store_true", help="build briefs, deliver nothing")
    parser.add_argument("--no-llm", "--no-openai", dest="no_llm", action="store_true",
                        help="skip the LLM step and use the deterministic fallback")
    parser.add_argument("--list-properties", action="store_true",
                        help="print every property this service account can read, then exit")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        # include_hold: held sites still contribute demand data (see process_site)
        sites = config.load_sites(only=args.domain, include_hold=True)
        service = build_gsc_client()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    if args.list_properties:
        props = list_properties(service)
        print(f"Service account can read {len(props)} propert{'y' if len(props)==1 else 'ies'}:")
        for p in sorted(props, key=lambda x: x["siteUrl"]):
            print(f"  {p['permissionLevel']:<24} {p['siteUrl']}")
        missing = audit_access(service, sites)
        if missing:
            print("\nDeclared in sites.yml but NOT readable:")
            for m in missing:
                print(f"  ✗ {m}")
        # Exit 1 only when NOTHING is readable — that means the credential or the
        # grant process is broken and scouting would be pointless. Some properties
        # pending is the normal state while grants are worked through account by
        # account, and it must not block work on the ones that ARE granted.
        if not props:
            print("\nNo readable properties at all — check the key and the grants.")
            return 1
        if missing:
            print(f"\n{len(props)} of {len(props) + len(missing)} granted — "
                  "proceeding with those. See SETUP-GSC.md for the rest.")
        return 0

    audit_access(service, sites)

    run_id = config.new_run_id()
    run_dir = config.RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log.info("run %s — %d site(s) — credit: %s", run_id, len(sites), ARCHITECTURE_CREDIT)

    # A delivering run needs somewhere to deliver and something to sign with.
    # Missing either is an environment problem, not a run failure — exit 2, with
    # the name of the thing to set. It used to escape as a raw traceback and
    # exit 1, which reads as "a brief was dead-lettered" and sends the wrong
    # person looking in the wrong place.
    try:
        webhook_url = "" if args.dry_run else config.require_env("AGENT2_WEBHOOK_URL")
        secret = "" if args.dry_run else config.require_env("WEBHOOK_SIGNING_SECRET")
    except ConfigError as exc:
        log.error("%s", exc)
        log.error(
            "A live run delivers to Agent 2. Until that endpoint exists, run with "
            "--dry-run: the briefs are still built and archived under runs/."
        )
        return 2
    callback_url = config.optional_env("AGENT3_WEBHOOK_URL")

    session = requests.Session()
    stats: list[dict[str, Any]] = []
    started = utc_now()
    for site in sites:
        stats.append(
            process_site(
                service, site, session, run_id, run_dir,
                limit=args.limit or site.max_briefs_per_run,
                dry_run=args.dry_run,
                use_llm=not args.no_llm,
                webhook_url=webhook_url,
                callback_url=callback_url,
                secret=secret,
            )
        )

    manifest = {
        "run_id": run_id,
        "started_at": rfc3339(started),
        "finished_at": rfc3339(),
        "architecture_credit": ARCHITECTURE_CREDIT,
        "owner": config.OWNER,
        "environment": config.ENVIRONMENT,
        "dry_run": args.dry_run,
        "analysis_provider": None if args.no_llm else config.GAP_ANALYSIS_PROVIDER,
        "domains": stats,
        "totals": {
            key: sum(s.get(key, 0) for s in stats)
            for key in ("gsc_rows", "candidates", "briefs_emitted", "delivered",
                        "dlq", "blocked", "degraded_briefs")
        },
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    t = manifest["totals"]
    ungranted = [s["domain"] for s in stats if s["status"] == "not_granted"]
    manifest["not_granted"] = ungranted
    manifest["degraded_domains"] = [s["domain"] for s in stats
                                    if s.get("degraded_briefs")]
    manifest["degraded_reasons"] = sorted({s["degraded_reason"] for s in stats
                                           if s.get("degraded_reason")})
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log.info(
        "run %s finished — %d briefs, %d delivered, %d dead-lettered, %d blocked%s",
        run_id, t["briefs_emitted"], t["delivered"], t["dlq"], t["blocked"],
        f", {len(ungranted)} not granted ({', '.join(ungranted)})" if ungranted else "",
    )
    # Loud, because this is the state that looks fine. Run #10 produced 14
    # briefs with no consensus figure, no proprietary fact and raw-slug URLs,
    # and reported Success in 47 seconds — a sixth of run #9's time, which was
    # the only visible sign anything had gone wrong.
    if t["degraded_briefs"]:
        doms = ", ".join(manifest["degraded_domains"])
        log.error(
            "DEGRADED: %d of %d briefs were built WITHOUT the LLM step (%s). They "
            "carry no consensus figure, no proprietary fact and an unranked slug "
            "for a URL. The run is green because a degraded run beats a dead one, "
            "but these briefs are not worth publishing.",
            t["degraded_briefs"], t["briefs_emitted"], doms,
        )
        for r in manifest["degraded_reasons"]:
            log.error("DEGRADED because: %s", r)
    if any(s["status"] == "failed" for s in stats):
        return 1
    return 1 if t["dlq"] else 0


if __name__ == "__main__":
    sys.exit(main())
