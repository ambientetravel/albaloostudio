#!/usr/bin/env python3
"""
Agent 8 — Competitor Scout.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Answers the one question the rest of the pipeline cannot: *who already covers
this, and what do they cover that we do not?*

Agent 1 finds gaps from our own Search Console — demand we do not serve. Agent 6
ranks them. Neither can see a competitor, so a gap that a rival has owned for
three years and a gap nobody has written about look identical, and they are not
remotely the same bet.

    python3 agent8_competitor_scout.py --domain boutimar.ir
    python3 agent8_competitor_scout.py --dry-run

WHY NOT COMMON CRAWL
────────────────────
It was the obvious answer and it was measured before being believed. Coverage in
CC-MAIN-2026-30, counted twice:

    royalcaribbean.com   5000+      flytoday.ir      13–20
    msccruises.com         361      cruisecritic.com     9
    aroya.com                1      alibaba.ir           0
    boutimar.ir              0      cruisebaz.com        0

Two things kill it for this portfolio. The Iranian web is essentially absent —
alibaba.ir is one of Iran's largest travel sites and returns nothing — which
writes off five of ten properties. And Common Crawl obeys robots.txt, so
coverage tracks who blocked CCBot rather than who matters: Cruise Critic, the
largest cruise review site on the web, has nine pages, and AROYA — the line this
portfolio's entire visa ruleset is built around — has one.

Crawling a named list ourselves works in Farsi and English alike, is current
rather than a monthly snapshot, and has no coverage gaps we did not choose.

WHAT THIS IS NOT
────────────────
Not rank tracking. This reports who *publishes* what, never who *ranks* for it —
that needs SERP data the pipeline does not buy. A competitor with a thin page
that outranks a thorough one will look weak here and beat you in the results.

Politeness is not optional when the site is not ours: robots.txt is parsed and
obeyed, one request at a time, spaced. A competitor that disallows us is
reported as such and not crawled.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

import config
from agent5_site_auditor import fetch
from config import ARCHITECTURE_CREDIT, Site, rfc3339, utc_now

log = logging.getLogger("agent8.competitor_scout")

AGENT_ID = "agent8.competitor_scout"

# One request at a time, spaced. Nothing here is urgent and these are not our
# servers — a scout that gets the pipeline's user-agent blocked has cost far
# more than the data was worth.
CRAWL_DELAY_S = 1.5
MAX_SITEMAP_CHILDREN = 12
MAX_PAGES_SAMPLED = 12

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_TAG = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(r"(?is)<(script|style)\b.*?</\1>")


@dataclass
class CompetitorReport:
    domain: str
    base_url: str
    status: str = "ok"           # ok | disallowed | unreachable | skipped
    note: str = ""
    robots_crawl_delay: float | None = None
    urls_listed: int = 0
    pages_sampled: int = 0
    topics: dict[str, int] = field(default_factory=dict)
    schema_types: dict[str, int] = field(default_factory=dict)
    median_words: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    samples: list[dict[str, Any]] = field(default_factory=list)


def _robots_for(session: requests.Session, base_url: str) -> tuple[RobotFileParser | None, float | None]:
    """
    Parse the competitor's robots.txt so we can obey it.

    Agent 5 reads robots.txt to *audit* it — it never obeys it, because it only
    crawls sites we own and a disallow there is a finding, not an instruction.
    Here the site belongs to someone else and the same file is an instruction.

    A robots.txt we cannot fetch is treated as permissive, which matches every
    major crawler: absence is not a disallow. A robots.txt that *parses* and
    disallows us is obeyed to the letter.
    """
    rp = RobotFileParser()
    url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
    resp = fetch(session, url)
    if resp is None or resp.status_code >= 400:
        rp.parse([])                      # no file → nothing is disallowed
        return rp, None
    try:
        rp.parse(resp.text.splitlines())
    except Exception:
        rp.parse([])
        return rp, None
    delay = None
    try:
        d = rp.crawl_delay(config.USER_AGENT)
        delay = float(d) if d is not None else None
    except Exception:
        delay = None
    return rp, delay


def _allowed(rp: RobotFileParser | None, url: str) -> bool:
    if rp is None:
        return True
    try:
        return rp.can_fetch(config.USER_AGENT, url)
    except Exception:
        # A robots.txt we cannot evaluate must not silently become permission.
        return False


def _sitemap_urls(session: requests.Session, base_url: str,
                  rp: RobotFileParser | None) -> list[str]:
    """Every URL the competitor lists about itself. The cheapest, most complete
    statement of what a site thinks it publishes — and one fetch, not a crawl."""
    found: list[str] = []
    seen: set[str] = set()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    candidates = [urljoin(base_url.rstrip("/") + "/", "sitemap.xml")]
    robots = fetch(session, urljoin(base_url.rstrip("/") + "/", "robots.txt"))
    if robots is not None and robots.status_code < 400:
        for line in robots.text.splitlines():
            if line.lower().startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())

    for cand in dict.fromkeys(candidates):
        if not _allowed(rp, cand):
            continue
        resp = fetch(session, cand)
        time.sleep(CRAWL_DELAY_S)
        if resp is None or resp.status_code >= 400:
            continue
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            continue

        if root.tag.split("}")[-1] == "sitemapindex":
            for loc in root.findall(".//sm:sitemap/sm:loc", ns)[:MAX_SITEMAP_CHILDREN]:
                child_url = (loc.text or "").strip()
                if not child_url or not _allowed(rp, child_url):
                    continue
                child = fetch(session, child_url)
                time.sleep(CRAWL_DELAY_S)
                if child is None:
                    continue
                try:
                    croot = ET.fromstring(child.content)
                except ET.ParseError:
                    continue
                for u in croot.findall(".//sm:url/sm:loc", ns):
                    t = (u.text or "").strip()
                    if t and t not in seen:
                        seen.add(t)
                        found.append(t)
        else:
            for u in root.findall(".//sm:url/sm:loc", ns):
                t = (u.text or "").strip()
                if t and t not in seen:
                    seen.add(t)
                    found.append(t)
        if found:
            break
    return found


def topic_of(url: str) -> str:
    """
    The section a URL sits in.

    A path segment is a decent proxy for a content section and needs no parsing
    of the page — /cruises/, /destinations/, /blog/. Deliberately crude: the
    point is to compare two sites' shapes, not to classify perfectly. Farsi and
    percent-encoded paths fall back to the raw segment rather than being dropped,
    because half this portfolio's competitors write in Farsi.
    """
    path = urlparse(url).path.strip("/")
    if not path:
        return "(home)"
    parts = path.split("/")
    if re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", parts[0], re.I) and len(parts) > 1:
        parts = parts[1:]                   # skip a locale prefix like /fa/ or /en-gb/
    if len(parts) == 1:
        # A flat site: every page sits at the root, so the filename is a page
        # name, not a section. boutimar.ir has 130 pages and would otherwise
        # report 130 "sections" of one page each — a diff against that is
        # noise. Five of the ten properties are flat static builds, so this is
        # the common case here, not an edge one.
        return "(root)"
    return parts[0][:60] or "(home)"


def _text_stats(html: str) -> tuple[int, str, list[str], list[str]]:
    """Word count, title, h1/h2 headings, and schema.org @type values."""
    body = _SCRIPT_STYLE.sub(" ", html)
    title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    title = _TAG.sub("", title_m.group(1)).strip()[:200] if title_m else ""
    heads = [
        _TAG.sub("", m.group(1)).strip()[:120]
        for m in re.finditer(r"(?is)<h[12][^>]*>(.*?)</h[12]>", body)
    ]
    types = re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', body)
    words = len(_WORD.findall(_TAG.sub(" ", body)))
    return words, title, [h for h in heads if h][:8], types


def scout_competitor(session: requests.Session, base_url: str,
                     *, sample: int) -> CompetitorReport:
    """Read one competitor. Never raises — a rival's outage is not our failure."""
    host = urlparse(base_url).netloc or base_url
    rep = CompetitorReport(domain=host, base_url=base_url)

    try:
        rp, delay = _robots_for(session, base_url)
        rep.robots_crawl_delay = delay
        pace = max(CRAWL_DELAY_S, delay or 0)

        if not _allowed(rp, base_url):
            rep.status = "disallowed"
            rep.note = ("robots.txt disallows this user-agent. Not crawled — "
                        "reported so the gap is visible rather than silent.")
            return rep

        urls = _sitemap_urls(session, base_url, rp)
        rep.urls_listed = len(urls)
        if not urls:
            rep.status = "unreachable"
            rep.note = ("no readable sitemap. Their content inventory is not "
                        "public, so only the home page could be compared.")
            urls = [base_url]

        for u in urls:
            rep.topics[topic_of(u)] = rep.topics.get(topic_of(u), 0) + 1

        # Sample across sections rather than the first N URLs, which on a
        # sitemap sorted by path would all land in one directory and describe
        # that directory instead of the site.
        by_topic: dict[str, list[str]] = {}
        for u in urls:
            by_topic.setdefault(topic_of(u), []).append(u)
        picks: list[str] = []
        while len(picks) < min(sample, len(urls)):
            before = len(picks)
            for bucket in by_topic.values():
                if bucket and len(picks) < min(sample, len(urls)):
                    picks.append(bucket.pop(0))
            if len(picks) == before:
                break

        words_seen: list[int] = []
        for u in picks:
            if not _allowed(rp, u):
                continue
            resp = fetch(session, u)
            time.sleep(pace)
            if resp is None or resp.status_code >= 400:
                continue
            words, title, heads, types = _text_stats(resp.text)
            words_seen.append(words)
            for t in types:
                rep.schema_types[t] = rep.schema_types.get(t, 0) + 1
            lang = ""
            m = re.search(r'(?is)<html[^>]*\blang=["\']([^"\']+)', resp.text)
            if m:
                lang = m.group(1).strip()[:12]
                rep.languages[lang] = rep.languages.get(lang, 0) + 1
            rep.samples.append({
                "url": u, "title": title, "words": words,
                "headings": heads, "language": lang,
            })

        rep.pages_sampled = len(rep.samples)
        if words_seen:
            words_seen.sort()
            rep.median_words = words_seen[len(words_seen) // 2]
        return rep

    except Exception as exc:
        rep.status = "unreachable"
        rep.note = config.redact(str(exc))[:300]
        return rep


def compare(site: Site, ours: list[str], reports: list[CompetitorReport]) -> dict[str, Any]:
    """
    Where their coverage and ours differ, by section.

    Only sections a competitor covers and we do not are actionable here; the
    reverse is not automatically a win, so it is reported plainly rather than
    framed as one. Nothing in this function knows anything about rankings.
    """
    our_topics = {topic_of(u) for u in ours}
    # A site whose pages all sit at the root has no sections to diff. Saying so
    # is the honest output; printing an empty "sections they cover" list would
    # read as "no gaps found" when it means "this comparison does not apply".
    ours_flat = bool(ours) and our_topics <= {"(root)", "(home)"}
    theirs: dict[str, int] = {}
    for r in reports:
        if r.status != "ok":
            continue
        for t, n in r.topics.items():
            theirs[t] = theirs.get(t, 0) + n

    missing = [] if ours_flat else sorted(
        ((t, n) for t, n in theirs.items() if t not in our_topics),
        key=lambda kv: -kv[1],
    )
    usable = [r for r in reports if r.status == "ok" and r.median_words]
    return {
        "our_site_is_flat": ours_flat,
        "section_comparison_applies": not ours_flat,
        "note": ("Our pages all sit at the root, so there are no sections to "
                 "compare. Read page counts, median length and schema coverage "
                 "instead." if ours_flat else ""),
        "our_sections": sorted(our_topics),
        "sections_they_cover_that_we_do_not": [
            {"section": t, "their_pages": n} for t, n in missing[:25]
        ],
        "their_median_words": (
            sorted(r.median_words for r in usable)[len(usable) // 2] if usable else None
        ),
        "reachable_competitors": len(usable),
        "blocked_by_robots": [r.domain for r in reports if r.status == "disallowed"],
        "unreachable": [r.domain for r in reports if r.status == "unreachable"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", action="append", help="restrict to a domain (repeatable)")
    ap.add_argument("--sample", type=int, default=MAX_PAGES_SAMPLED,
                    help="pages to read per competitor")
    ap.add_argument("--out", default="competitors")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be crawled, fetch nothing")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")

    sites = config.load_sites(only=args.domain)
    configured = [s for s in sites if getattr(s, "competitors", None)]
    if not configured:
        log.warning("No site in sites.yml declares `competitors:`. Nothing to scout — "
                    "this agent reads a named list, it does not discover rivals.")
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    results: list[dict[str, Any]] = []

    for site in configured:
        rivals = list(site.competitors)
        log.info("%s — %d competitor(s): %s", site.domain, len(rivals), ", ".join(rivals))
        if args.dry_run:
            results.append({"domain": site.domain, "competitors": rivals, "dry_run": True})
            continue

        ours = _sitemap_urls(session, site.base_url, None)
        reports = [scout_competitor(session, r, sample=args.sample) for r in rivals]
        for r in reports:
            log.info("  %s — %s — %d listed, %d sampled%s", r.domain, r.status,
                     r.urls_listed, r.pages_sampled,
                     f" — {r.note}" if r.note else "")

        results.append({
            "domain": site.domain,
            "our_urls_listed": len(ours),
            "competitors": [r.__dict__ for r in reports],
            "comparison": compare(site, ours, reports),
        })

    manifest = {
        "architecture_credit": ARCHITECTURE_CREDIT,
        "owner": config.OWNER,
        "agent": AGENT_ID,
        "generated_at": rfc3339(utc_now()),
        "dry_run": args.dry_run,
        "note": ("Content coverage, not rankings. This says who publishes what, "
                 "never who ranks for it."),
        "sites": results,
    }
    (out_dir / "competitors.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Agent 8 finished — %d site(s) compared", len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
