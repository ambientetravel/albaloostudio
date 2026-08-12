#!/usr/bin/env python3
"""
Agent 5 — Site Auditor (technical SEO, GEO / AI presence, local signals).

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Crawls every property in sites.yml and reports what is wrong with the settings —
the layer between "we have demand data" (Agent 1) and "we wrote a page"
(Agent 2). Needs no credentials: it reads public URLs.

Three areas, because they fail differently:

  technical  Can Google crawl, index and understand this site at all?
  geo        Would an AI answer engine cite it? (Generative Engine Optimization)
             Plus local/geographic signals, which a DMC actually needs.
  content    Is the page itself doing its job — title, headings, internal links?

    python agent5_site_auditor.py                      # all 8 properties
    python agent5_site_auditor.py --domain boutimar.ir --verbose
    python agent5_site_auditor.py --format markdown > audit.md

Every finding carries a fix, not just a complaint. A finding you cannot act on
is noise, and this file is meant to be read by someone with 20 minutes.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

import config
from config import Site, rfc3339

log = logging.getLogger("agent5.auditor")

AGENT_ID = "agent5.auditor"

CRITICAL, HIGH, MEDIUM, LOW, INFO = "critical", "high", "medium", "low", "info"
SEVERITY_ORDER = {CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4}

TIMEOUT = 20
# Fallback only. The real value is `audit_sample_pages` in sites.yml, which
# the cron uses unmodified so every scheduled run measures identically.
SAMPLE_PAGES = 10


# ══════════════════════════════════════════════════════════════════════════════
# 1. Findings
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class Finding:
    id: str
    area: str            # technical | geo | content
    severity: str
    title: str
    evidence: str
    fix: str
    url: str | None = None
    scope: str = "page"  # page | site — decides how it is scored, see score()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SiteAudit:
    domain: str
    brand: str
    locale: str
    checked_at: str
    reachable: bool = True
    findings: list[Finding] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def add(self, **kw: Any) -> None:
        self.findings.append(Finding(**kw))

    def score(self) -> int:
        """
        0–100, and deliberately **independent of how many pages were sampled**.

        The naive version — 100 minus a weighted count of findings — saturates:
        one missing meta description across 10 sampled pages costs ten times what
        it costs across one, so a bigger sample invents a worse site. Three of
        these domains hit 0 that way, which tells you nothing about which is worst.

        So: a site-scope finding (robots, sitemap, host) counts once, and a
        page-scope finding counts as the *fraction of sampled pages it affects*.
        A template defect on every page costs one full weight whether the sample
        was 3 pages or 30 — which is what makes week-over-week comparison mean
        something, and what makes the pinned sample size a statement about
        coverage rather than a thumb on the scale.
        """
        weights = {CRITICAL: 25, HIGH: 10, MEDIUM: 4, LOW: 1, INFO: 0}
        pages = max(1, int(self.stats.get("pages_checked", 1)))

        lost = 0.0
        per_page: dict[str, list[Finding]] = {}
        for f in self.findings:
            if f.scope == "site":
                lost += weights[f.severity]
            else:
                per_page.setdefault(f.id, []).append(f)

        for group in per_page.values():
            affected = min(1.0, len(group) / pages)
            lost += weights[group[0].severity] * affected

        return max(0, round(100 - lost))

    def as_dict(self) -> dict[str, Any]:
        ordered = sorted(self.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.area))
        return {
            "domain": self.domain,
            "brand": self.brand,
            "locale": self.locale,
            "checked_at": self.checked_at,
            "reachable": self.reachable,
            "score": self.score(),
            "counts": {
                sev: sum(1 for f in self.findings if f.severity == sev)
                for sev in (CRITICAL, HIGH, MEDIUM, LOW, INFO)
            },
            "stats": self.stats,
            "findings": [f.as_dict() for f in ordered],
        }


# ══════════════════════════════════════════════════════════════════════════════
# 2. A small HTML reader
# ══════════════════════════════════════════════════════════════════════════════


class PageParser(HTMLParser):
    """
    Deliberately dependency-free. We need head metadata, heading structure,
    JSON-LD and a rough sense of how much text survives without JavaScript —
    not a DOM.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.og: dict[str, str] = {}
        self.lang = ""
        self.canonical = ""
        self.hreflang: list[tuple[str, str]] = []
        self.headings: list[tuple[int, str]] = []
        self.jsonld: list[dict[str, Any]] = []
        self.images: list[dict[str, str]] = []
        self.links: list[str] = []
        self.text_len = 0
        self.script_bytes = 0
        self._in: list[str] = []
        self._buf: list[str] = []
        self._ld_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        self._in.append(tag)
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"]
        elif tag == "meta":
            name = (a.get("name") or a.get("http-equiv") or "").lower()
            prop = (a.get("property") or "").lower()
            if name:
                self.meta[name] = a.get("content", "")
            if prop.startswith("og:"):
                self.og[prop] = a.get("content", "")
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if "canonical" in rel:
                self.canonical = a.get("href", "")
            if "alternate" in rel and a.get("hreflang"):
                self.hreflang.append((a["hreflang"], a.get("href", "")))
        elif tag in {"h1", "h2", "h3"}:
            self._buf = []
        elif tag == "img":
            self.images.append({"src": a.get("src", ""), "alt": a.get("alt", "")})
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script" and "ld+json" in (a.get("type") or "").lower():
            self._ld_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3"}:
            text = " ".join("".join(self._buf).split())
            if text:
                self.headings.append((int(tag[1]), text))
            self._buf = []
        elif tag == "script" and self._ld_buf:
            blob = "".join(self._ld_buf).strip()
            self._ld_buf = []
            try:
                parsed = json.loads(blob)
            except json.JSONDecodeError:
                return
            self.jsonld.extend(parsed if isinstance(parsed, list) else [parsed])
        if self._in and self._in[-1] == tag:
            self._in.pop()

    def handle_data(self, data: str) -> None:
        cur = self._in[-1] if self._in else ""
        if cur == "title":
            self.title += data.strip()
        elif cur == "script":
            self.script_bytes += len(data)
            if self._ld_buf is not None:
                self._ld_buf.append(data)
        elif cur in {"h1", "h2", "h3"}:
            self._buf.append(data)
        elif cur not in {"style", "noscript"}:
            self.text_len += len(data.strip())

    def schema_types(self) -> set[str]:
        out: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                t = node.get("@type")
                if isinstance(t, str):
                    out.add(t)
                elif isinstance(t, list):
                    out.update(x for x in t if isinstance(x, str))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(self.jsonld)
        return out


# ══════════════════════════════════════════════════════════════════════════════
# 3. Fetching
# ══════════════════════════════════════════════════════════════════════════════


_COMING_SOON = re.compile(
    r"(?i)coming\s+soon|under\s+construction|launching\s+soon"
    r"|به\s*زودی|در\s*دست\s*(ساخت|احداث)|راه\s*اندازی\s*می\s*شود"
)


def _is_placeholder(resp: requests.Response) -> bool:
    """Tiny page, no links, or explicit coming-soon wording."""
    if len(resp.content) > 4000:
        return False
    text = re.sub(r"<script.*?</script>|<[^>]+>", " ", resp.text, flags=re.S | re.I)
    words = len(text.split())
    if _COMING_SOON.search(text):
        return True
    return words < 60 and resp.text.lower().count("<a ") < 3


def fetch(session: requests.Session, url: str, **kw: Any) -> requests.Response | None:
    try:
        return session.get(
            url, timeout=TIMEOUT, headers={"User-Agent": config.USER_AGENT}, **kw
        )
    except requests.RequestException as exc:
        log.debug("fetch failed %s: %s", url, exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 4. Technical checks
# ══════════════════════════════════════════════════════════════════════════════

# The lesson that cost boutimar.ir its indexing: a robots.txt that blocks the
# JS/CSS a page needs to render leaves Google with a blank page. It is not a
# crawl-budget optimisation, it is a way to make your content invisible.
_BLOCKS_ASSETS = re.compile(r"(?im)^disallow:\s*/?(\*?\.?(js|css)|assets|static|_next|dist)\b")


def audit_robots(site: Site, session: requests.Session, audit: SiteAudit) -> None:
    url = urljoin(site.base_url + "/", "robots.txt")
    resp = fetch(session, url)
    if resp is None or resp.status_code >= 400:
        audit.add(
            id="robots.missing", scope="site", area="technical", severity=MEDIUM, url=url,
            title="No robots.txt",
            evidence=f"{url} returned {resp.status_code if resp else 'no response'}",
            fix="Serve a robots.txt that allows crawling and points at the sitemap. "
                "Its absence is not fatal, but it is where the sitemap gets discovered.",
        )
        return

    body = resp.text
    audit.stats["robots_bytes"] = len(body)

    if re.search(r"(?im)^disallow:\s*/\s*$", body):
        audit.add(
            id="robots.blocks_everything", scope="site", area="technical", severity=CRITICAL, url=url,
            title="robots.txt blocks the entire site",
            evidence="A bare `Disallow: /` is present.",
            fix="Remove it. Nothing on this domain can be indexed while it stands.",
        )

    if _BLOCKS_ASSETS.search(body):
        audit.add(
            id="robots.blocks_assets", scope="site", area="technical", severity=HIGH, url=url,
            title="robots.txt blocks JS or CSS",
            evidence=_BLOCKS_ASSETS.search(body).group(0),  # type: ignore[union-attr]
            fix="Allow JS and CSS. Googlebot renders the page; blocking the assets it "
                "needs leaves it looking at a blank document. This is exactly what "
                "starved boutimar.ir's JS-rendered pages.",
        )

    if "sitemap:" not in body.lower():
        audit.add(
            id="robots.no_sitemap", scope="site", area="technical", severity=LOW, url=url,
            title="robots.txt does not reference a sitemap",
            evidence="No `Sitemap:` line.",
            fix=f"Add `Sitemap: {site.sitemap}`.",
        )


_TEMPLATE_KEY = re.compile(r"[^/?&=]+(?=\.html|$)")


def _server_words(html: str) -> int:
    """Words a crawler sees WITHOUT running JavaScript."""
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    return len(re.findall(r"[^\W\d_]+", re.sub(r"<[^>]+>", " ", body), re.UNICODE))


def _template_of(url: str) -> str:
    """Group URLs that share a template — /article.html?a=x and ?a=y are one."""
    base = url.split("?", 1)
    path = base[0].rstrip("/")
    return path + ("?" + re.sub(r"=[^&]*", "=", base[1]) if len(base) > 1 else "")


def audit_client_rendered(site: Site, probe: list[tuple[str, int]],
                          audit: SiteAudit) -> list[str]:
    """
    Pages whose body arrives client-side, and so is invisible to a crawler that
    does not run JavaScript.

    The tell is exact: two DIFFERENT urls sharing a template returning the SAME
    server-rendered word count means the count is the template, not the content.
    boutimar.ir's article.html?a=<slug> returned exactly 336 words for three
    different articles on 12 Aug 2026, while its static pages ranged 428–2,985.

    Google renders JS, imperfectly. The crawlers behind AI answers largely do
    not — so this hits the GEO work hardest, which is the work these sites are
    being written for.
    """
    groups: dict[str, list[tuple[str, int]]] = {}
    for url, words in probe:
        groups.setdefault(_template_of(url), []).append((url, words))

    flagged: list[str] = []
    for tmpl, rows in groups.items():
        if len(rows) < 2:
            continue
        counts = {w for _, w in rows}
        if len(counts) == 1 and rows[0][1] > 0:
            flagged.append(tmpl)
            audit.add(
                id="content.client_rendered", scope="site", area="technical",
                severity=HIGH, url=rows[0][0],
                title="Page body is rendered client-side",
                evidence=(f"{len(rows)} different URLs on {tmpl} each return exactly "
                          f"{rows[0][1]} words of server HTML — that is the template, "
                          f"not the article."),
                fix="Server-render the body, or pre-build these as static pages. "
                    "AI crawlers largely do not execute JavaScript, so these "
                    "pages are close to invisible to the answers this content "
                    "is written to appear in.",
            )
    return flagged


def audit_sitemap(site: Site, session: requests.Session, audit: SiteAudit) -> set[str]:
    resp = fetch(session, site.sitemap)
    if resp is None or resp.status_code >= 400:
        audit.add(
            id="sitemap.missing", scope="site", area="technical", severity=HIGH, url=site.sitemap,
            title="Sitemap unreachable",
            evidence=f"{site.sitemap} returned {resp.status_code if resp else 'no response'}",
            fix="Publish a sitemap. Without one, Agent 1 cannot tell a missing page "
                "from an unlisted one, and every ranking query looks like a gap.",
        )
        return set()

    urls: set[str] = set()
    lastmods = 0
    try:
        root = ET.fromstring(resp.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        if root.tag.split("}")[-1] == "sitemapindex":
            for loc in root.findall(".//sm:sitemap/sm:loc", ns)[:10]:
                child = fetch(session, (loc.text or "").strip())
                if child is None:
                    continue
                try:
                    croot = ET.fromstring(child.content)
                except ET.ParseError:
                    continue
                for u in croot.findall(".//sm:url/sm:loc", ns):
                    if u.text:
                        urls.add(u.text.strip())
                lastmods += len(croot.findall(".//sm:url/sm:lastmod", ns))
        else:
            for u in root.findall(".//sm:url/sm:loc", ns):
                if u.text:
                    urls.add(u.text.strip())
            lastmods = len(root.findall(".//sm:url/sm:lastmod", ns))
    except ET.ParseError as exc:
        audit.add(
            id="sitemap.malformed", scope="site", area="technical", severity=HIGH, url=site.sitemap,
            title="Sitemap does not parse as XML",
            evidence=str(exc), fix="Regenerate it. A malformed sitemap is ignored wholesale.",
        )
        return set()

    audit.stats["sitemap_urls"] = len(urls)
    if not urls:
        audit.add(
            id="sitemap.empty", scope="site", area="technical", severity=HIGH, url=site.sitemap,
            title="Sitemap lists no URLs", evidence="0 <loc> entries.",
            fix="Populate it, and re-check that the build step actually writes it — "
                "an edited sitemap that never made it into a deploy is a known "
                "failure mode on these sites.",
        )
    elif lastmods == 0:
        audit.add(
            id="sitemap.no_lastmod", scope="site", area="technical", severity=LOW, url=site.sitemap,
            title="No <lastmod> dates in the sitemap",
            evidence=f"{len(urls)} URLs, 0 lastmod entries.",
            fix="Emit <lastmod>. It is the main signal for recrawl priority.",
        )

    audit_placeholder_content(site, urls, audit)
    return urls


# Every one of these is a CMS default that ships with the install and is meant
# to be deleted. Finding them live means nobody ever did. They were found on
# dmciran.ir and cruiseshop.ir on 12 Aug 2026 — dmciran's entire indexed
# inventory was 73 WordPress theme demo posts from 2017–2018, including the
# literal "Hello World" and an article about the video game No Man's Sky, on a
# site selling inbound travel to Iran. Both properties had reported zero
# impressions for 480 days, and this is why: there is nothing real to index.
_PLACEHOLDER_MARKERS = (
    "hello-world", "helloworld", "sample-page", "برگه-نمونه",
    "uncategorized", "دسته‌بندی-نشده",
    "/author/admin", "lorem-ipsum", "my-first-post",
)


def audit_nonascii_slugs(site: Site, probe: list[tuple[str, int]],
                         audit: SiteAudit, statuses: dict[str, int]) -> list[str]:
    """
    URLs whose slug is non-ASCII and which do not resolve.

    Found on cruiseshop.ir, 13 Aug 2026: every ASCII URL returned 200 and every
    percent-encoded Farsi URL returned 404 — a page and a category archive that
    WordPress itself still lists in wp-sitemap.xml, and a category the REST API
    reports as holding a post. Two 404s look like leftover junk; two 404s that
    are *both* the only non-ASCII slugs on the site are a permalink layer that
    cannot resolve Persian.

    Measured on cruiseshop.ir and dmciran.ir, 13 Aug 2026, and it is narrower
    than it first looks — narrow enough that two earlier readings of it here
    were both wrong:

        Farsi PAGE slug      /%d8%ae%d8%a7%d9%86%d9%87/        200
        ASCII CATEGORY       /archives/category/hiking/        200   (7 of 7)
        Farsi CATEGORY       /archives/category/%d8%af%d8%...  404   (both sites)

    So it is not "Persian URLs do not work" — Persian pages resolve. And it is
    not bad stored data: WordPress stores non-ASCII slugs percent-encoded BY
    DESIGN, and that stored form is what resolves. It is taxonomy archives
    specifically: the category rewrite fails to match a percent-encoded term,
    while the page lookup handles it.

    Practical scope: a Farsi CATEGORY or TAG archive 404s; the pages and posts
    inside it are reachable. Renaming the term's slug to ASCII fixes it, and on
    these two sites the only affected term is WordPress's own default
    «دسته‌بندی نشده», which is junk and duplicates an ASCII `uncategorized`.
    """
    from urllib.parse import unquote

    def _nonascii(u: str) -> bool:
        # The URL arrives percent-encoded, and %d8%a8 is pure ASCII — testing
        # the raw string finds nothing. Decode first, then look at the
        # characters a reader would actually see.
        return any(ord(ch) > 127 for ch in unquote(u))

    bad = sorted(u for u, code in statuses.items() if code == 404 and _nonascii(u))
    good_ascii = [u for u, code in statuses.items() if code < 400 and not _nonascii(u)]
    if not bad:
        return []
    systemic = len(bad) >= 2 and not any(
        code < 400 for u, code in statuses.items() if _nonascii(u)
    )
    audit.add(
        id="url.nonascii_slug_404", scope="site", area="technical",
        severity=CRITICAL if systemic else HIGH, url=bad[0],
        title=("No non-ASCII URL on this site resolves" if systemic
               else f"{len(bad)} non-ASCII URL(s) return 404"),
        evidence=(f"{len(bad)} non-ASCII URL(s) 404 while {len(good_ascii)} ASCII "
                  f"URL(s) return 200: " + "; ".join(u[:70] for u in bad[:3])),
        fix="Check WHERE it fails before assuming what it is. Test an ASCII "
            "term archive, a non-ASCII term archive and a non-ASCII page on the "
            "same site: on cruiseshop.ir and dmciran.ir the pages and the ASCII "
            "terms returned 200 and only the non-ASCII TERM archives 404d, which "
            "makes it the taxonomy rewrite and not the URL layer, the encoding, "
            "or the stored slug. Renaming that term's slug to ASCII resolves it.",
    )
    return bad


def audit_placeholder_content(site: Site, urls: set[str] | list[str],
                              audit: SiteAudit) -> list[str]:
    """
    CMS demo content that was never deleted, still in the sitemap.

    A site whose public inventory is theme filler tells Google it is abandoned,
    and it costs far more than the pages themselves: Agent 1 scouts these
    properties every week for "content gaps", and cannot tell a site with a gap
    from a site with nothing on it at all.
    """
    from urllib.parse import unquote

    hits = sorted({
        u for u in urls
        if any(m in unquote(u).lower() for m in _PLACEHOLDER_MARKERS)
    })
    if not hits:
        return []
    audit.add(
        id="content.placeholder_indexed", scope="site", area="technical",
        severity=CRITICAL if len(hits) >= 5 else HIGH, url=site.sitemap,
        title=f"{len(hits)} CMS placeholder page(s) in the sitemap",
        evidence="; ".join(h[:90] for h in hits[:5]),
        fix="Delete the demo posts, the Sample Page, the Uncategorized category "
            "and the author archive, then regenerate the sitemap. Until then "
            "this site's public inventory is the theme's, not yours.",
    )
    return hits


def audit_canonical_host(site: Site, session: requests.Session, audit: SiteAudit) -> None:
    """www and apex must resolve to one host, in one hop."""
    parsed = urlparse(site.base_url)
    host = parsed.netloc
    other = host[4:] if host.startswith("www.") else f"www.{host}"
    url = f"{parsed.scheme}://{other}/"

    resp = fetch(session, url, allow_redirects=False)
    if resp is None:
        audit.add(
            id="host.alt_unreachable", scope="site", area="technical", severity=LOW, url=url,
            title=f"{other} does not resolve",
            evidence="No response.",
            fix="Not fatal, but a visitor typing the other form gets nothing. "
                "Point it at the canonical host with a 301.",
        )
        return

    if resp.status_code in (301, 308):
        target = resp.headers.get("Location", "")
        if urlparse(urljoin(url, target)).netloc != host:
            audit.add(
                id="host.redirect_wrong_target", scope="site", area="technical", severity=MEDIUM, url=url,
                title=f"{other} redirects somewhere other than {host}",
                evidence=f"{resp.status_code} → {target}",
                fix=f"Send it to {site.base_url}.",
            )
    elif resp.status_code == 200:
        audit.add(
            id="host.duplicate", scope="site", area="technical", severity=HIGH, url=url,
            title=f"Both {host} and {other} serve content",
            evidence=f"{other} returned 200 with no redirect.",
            fix="301 one to the other. Two hosts serving the same pages splits every "
                "ranking signal you have between them.",
        )
    elif resp.status_code in (302, 307):
        audit.add(
            id="host.temp_redirect", scope="site", area="technical", severity=MEDIUM, url=url,
            title=f"{other} uses a temporary redirect",
            evidence=f"HTTP {resp.status_code}",
            fix="Use 301/308. A temporary redirect does not consolidate signals.",
        )


def audit_404(site: Site, session: requests.Session, audit: SiteAudit) -> None:
    url = urljoin(site.base_url + "/", "albaloo-audit-should-not-exist-9f2c")
    resp = fetch(session, url)
    if resp is not None and resp.status_code == 200:
        audit.add(
            id="http.soft_404", scope="site", area="technical", severity=MEDIUM, url=url,
            title="Missing pages return HTTP 200",
            evidence=f"A nonsense URL returned {resp.status_code}.",
            fix="Return a real 404. Soft 404s get indexed as thin duplicates and "
                "dilute the crawl budget across URLs that do not exist.",
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. Page-level: content and GEO
# ══════════════════════════════════════════════════════════════════════════════

# Types an answer engine can actually use to describe a travel business.
USEFUL_SCHEMA = {
    "Organization", "TravelAgency", "LocalBusiness", "WebSite", "BreadcrumbList",
    "FAQPage", "Article", "BlogPosting", "Product", "Offer", "TouristTrip",
    "TouristAttraction", "Trip", "Event",
}
LOCAL_SCHEMA = {"LocalBusiness", "TravelAgency", "PostalAddress", "GeoCoordinates"}


def audit_page(
    site: Site, url: str, resp: requests.Response, audit: SiteAudit, *,
    is_home: bool, from_sitemap: bool = False
) -> PageParser | None:
    parser = PageParser()
    try:
        parser.feed(resp.text)
    except Exception as exc:  # a malformed page must not abort the whole audit
        log.debug("parse failed %s: %s", url, exc)
        return None

    where = "Homepage" if is_home else "Page"

    # ── content ──────────────────────────────────────────────────────────────
    if not parser.title:
        audit.add(id="content.no_title", area="content", severity=HIGH, url=url,
                  title=f"{where} has no <title>", evidence="Empty or absent.",
                  fix="Every page needs one. It is the single strongest on-page signal "
                      "and it is what shows in the result.")
    elif len(parser.title) > 65:
        audit.add(id="content.title_long", area="content", severity=LOW, url=url,
                  title=f"{where} title is {len(parser.title)} characters",
                  evidence=parser.title[:90],
                  fix="Keep it under ~60 so it is not truncated in the result.")

    desc = parser.meta.get("description", "")
    if not desc:
        audit.add(id="content.no_description", area="content", severity=MEDIUM, url=url,
                  title=f"{where} has no meta description", evidence="Absent.",
                  fix="Write one. Google may rewrite it, but an absent one guarantees "
                      "a machine-picked snippet.")

    h1s = [t for lvl, t in parser.headings if lvl == 1]
    if not h1s:
        audit.add(id="content.no_h1", area="content", severity=MEDIUM, url=url,
                  title=f"{where} has no H1", evidence="No <h1> found.",
                  fix="Add one H1 that states what the page is about.")
    elif len(h1s) > 1:
        audit.add(id="content.multiple_h1", area="content", severity=LOW, url=url,
                  title=f"{where} has {len(h1s)} H1s", evidence="; ".join(h1s[:3]),
                  fix="Keep one. Use H2 for the rest.")

    if not parser.lang:
        audit.add(id="content.no_lang", area="technical", severity=MEDIUM, url=url,
                  title=f"{where} has no lang attribute", evidence="<html> without lang.",
                  fix=f'Set lang="{site.locale}". On a Farsi site this also drives '
                      "text direction and hyphenation for assistive tech.")
    elif site.locale.startswith("fa") and not parser.lang.startswith("fa"):
        audit.add(id="content.lang_mismatch", area="technical", severity=MEDIUM, url=url,
                  title=f'{where} declares lang="{parser.lang}" on a Farsi site',
                  evidence=f'lang="{parser.lang}", expected fa',
                  fix='Set lang="fa-IR".')

    if not parser.canonical:
        audit.add(id="content.no_canonical", area="technical", severity=LOW, url=url,
                  title=f"{where} has no canonical link", evidence="No rel=canonical.",
                  fix="Add a self-referencing canonical. It is the cheapest defence "
                      "against parameter and duplicate URLs.")

    robots_meta = parser.meta.get("robots", "").lower()
    if "noindex" in robots_meta:
        if from_sitemap:
            # The contradiction is the finding, not the noindex. A test page, an
            # embed widget or a login screen *should* be noindexed — but listing
            # it in the sitemap tells Google "crawl this" and "ignore this" at
            # once. Framing this as "remove the noindex" sends you to fix the
            # wrong end, and on boutimar.com that would have published an
            # internal partner-widget test page.
            audit.add(id="sitemap.noindex_conflict", area="technical", severity=HIGH,
                      url=url, title="Noindexed page is advertised in the sitemap",
                      evidence=f'{url} is listed in {site.sitemap} but serves '
                               f'robots: "{robots_meta}"',
                      fix="Decide which one is wrong. If the page is meant to be "
                          "hidden — a test page, an embed, a login — keep the noindex "
                          "and exclude it from the sitemap. Only remove the noindex if "
                          "the page was supposed to rank all along. Either way the two "
                          "signals must agree.")
        else:
            audit.add(id="content.noindex", area="technical", severity=LOW, url=url,
                      title=f"{where} is set to noindex", evidence=f'robots: "{robots_meta}"',
                      fix="Confirm this is deliberate. It is not advertised in the "
                          "sitemap, so this is likely intentional — but a noindex left "
                          "over from a staging build is the most common way a page "
                          "silently never ranks.")

    if not parser.meta.get("viewport"):
        audit.add(id="content.no_viewport", area="technical", severity=MEDIUM, url=url,
                  title=f"{where} has no viewport meta", evidence="Absent.",
                  fix="Add it. Iranian traffic to these sites is ~78% mobile.")

    no_alt = [i for i in parser.images if not i["alt"].strip()]
    if parser.images and len(no_alt) / len(parser.images) > 0.5:
        audit.add(id="content.images_no_alt", area="content", severity=LOW, url=url,
                  title=f"{len(no_alt)} of {len(parser.images)} images have no alt text",
                  evidence=", ".join(i["src"][:60] for i in no_alt[:3]),
                  fix="Describe them. Alt text is both accessibility and the only thing "
                      "an answer engine can read out of an image.")

    # ── GEO / AI presence ────────────────────────────────────────────────────
    types = parser.schema_types()
    if not parser.jsonld:
        # Phrased as "not detected in server HTML", not "absent". This auditor
        # fetches without executing JavaScript, and Yoast, RankMath and most SPA
        # frameworks inject JSON-LD client-side. Claiming absence without a
        # rendered check is exactly the kind of fabricated finding the rest of
        # this pipeline refuses to make. Confirm with a rendering fetch before
        # acting — see Out-of-Scope Notes in the Analyst report.
        audit.add(id="geo.no_structured_data", area="geo", severity=HIGH, url=url,
                  title=f"{where}: no JSON-LD in the server-rendered HTML",
                  evidence=f"No ld+json in {len(resp.content)} bytes of raw HTML "
                           f"({parser.script_bytes} chars of script — could be injected "
                           "client-side; unverified without a rendering fetch).",
                  fix="Add schema.org JSON-LD server-side if it is genuinely missing. "
                      "This is the single highest-leverage GEO change: answer engines "
                      "lift entities, prices and FAQs out of structured data far more "
                      "reliably than out of prose — and out of server HTML far more "
                      "reliably than out of a client-side injection.")
    else:
        audit.stats.setdefault("schema_types", sorted(types))
        if is_home and not (types & {"Organization", "TravelAgency", "LocalBusiness"}):
            audit.add(id="geo.no_org_schema", area="geo", severity=MEDIUM, url=url,
                      title="Homepage declares no Organization entity",
                      evidence=f"Types found: {sorted(types) or 'none'}",
                      fix="Add Organization (or TravelAgency) with name, url, logo and "
                          "sameAs links to your social profiles. This is how an answer "
                          "engine knows the brand is one entity across all your domains.")
        if not (types & USEFUL_SCHEMA):
            audit.add(id="geo.schema_not_useful", area="geo", severity=LOW, url=url,
                      title="Structured data present but none of it describes the business",
                      evidence=f"Types: {sorted(types)}",
                      fix="Add at least one of Organization, TravelAgency, FAQPage, "
                          "Article or TouristTrip.")

    if is_home and not (types & LOCAL_SCHEMA):
        audit.add(id="geo.no_local_signals", area="geo", severity=MEDIUM, url=url,
                  title="No local/geographic entity data",
                  evidence="No LocalBusiness, PostalAddress or GeoCoordinates.",
                  fix="Add PostalAddress and, for the DMC brands, LocalBusiness with "
                      "areaServed. 'DMC in Iran' and 'travel agency Tehran' are "
                      "geographic queries and this is what answers them.")

    questions = [t for lvl, t in parser.headings if lvl in (2, 3) and _looks_like_question(t)]
    if not questions and "FAQPage" not in types:
        audit.add(id="geo.no_question_structure", area="geo", severity=MEDIUM, url=url,
                  title=f"{where} has no question-shaped headings or FAQ schema",
                  evidence=f"{len(parser.headings)} headings, none phrased as a question.",
                  fix="Add a short FAQ with question headings and FAQPage schema. "
                      "Answer engines quote passages that already look like an answer "
                      "to a question — this is the cheapest way to become quotable.")

    # Content that only exists after JavaScript runs is content an answer engine
    # mostly does not see. Crawlers render; most AI fetchers do not.
    if parser.text_len < 500 and parser.script_bytes > parser.text_len * 3:
        audit.add(id="geo.js_dependent", area="geo", severity=HIGH, url=url,
                  title=f"{where} serves almost no text without JavaScript",
                  evidence=f"{parser.text_len} chars of text vs {parser.script_bytes} chars of script.",
                  fix="Server-render the main content. Googlebot will eventually render "
                      "it; most AI answer-engine fetchers will not, so a JS-only page is "
                      "invisible to exactly the surface you are trying to win.")

    if is_home and not parser.og.get("og:title"):
        audit.add(id="geo.no_opengraph", area="geo", severity=LOW, url=url,
                  title="No Open Graph tags", evidence="og:title absent.",
                  fix="Add og:title, og:description and og:image. They control how the "
                      "link renders when anyone shares it, including in chat apps.")

    return parser


_QUESTION = re.compile(
    r"(?i)^(what|why|how|when|where|which|who|is|are|do|does|can|should)\b|\?\s*$"
    r"|^(چه|چرا|چگونه|چطور|کدام|آیا|کی|کجا)\b|؟\s*$"
)


def _looks_like_question(text: str) -> bool:
    return bool(_QUESTION.search(text.strip()))


def audit_llms_txt(site: Site, session: requests.Session, audit: SiteAudit) -> None:
    url = urljoin(site.base_url + "/", "llms.txt")
    resp = fetch(session, url)
    if resp is None or resp.status_code >= 400 or "<html" in resp.text[:200].lower():
        audit.add(
            id="geo.no_llms_txt", scope="site", area="geo", severity=LOW, url=url,
            title="No llms.txt",
            evidence=f"{url} returned {resp.status_code if resp else 'no response'}",
            fix="Publish an llms.txt: a short markdown map of what the site covers and "
                "which pages matter. It is an emerging convention rather than a "
                "standard, and cheap — a few hours for a plausible edge in AI answers.",
        )


# ══════════════════════════════════════════════════════════════════════════════
# 6. Run one site
# ══════════════════════════════════════════════════════════════════════════════


def audit_site(site: Site, session: requests.Session, *, sample: int | None = None) -> SiteAudit:
    """
    `sample` defaults to the site's pinned `audit_sample_pages`. Pass it only
    for ad-hoc work — the score counts findings, so changing the sample size
    changes the score without anything on the site changing.
    """
    sample = site.audit_sample_pages if sample is None else sample
    return _audit_site(site, session, sample)


def _audit_site(site: Site, session: requests.Session, sample: int) -> SiteAudit:
    audit = SiteAudit(
        domain=site.domain, brand=site.brand, locale=site.locale, checked_at=rfc3339()
    )
    started = time.time()

    home = fetch(session, site.base_url + "/")
    if home is None:
        audit.reachable = False
        audit.add(id="http.unreachable", scope="site", area="technical", severity=CRITICAL,
                  url=site.base_url, title="Site did not respond",
                  evidence="No response within the timeout.",
                  fix="Check DNS, the certificate and the origin before reading anything "
                      "else in this report.")
        return audit

    audit.stats["home_status"] = home.status_code
    audit.stats["home_bytes"] = len(home.content)

    if home.status_code >= 400:
        audit.reachable = False
        audit.add(id="http.home_error", scope="site", area="technical", severity=CRITICAL,
                  url=site.base_url, title=f"Homepage returns HTTP {home.status_code}",
                  evidence=f"{home.status_code} {home.reason}",
                  fix="Nothing else matters until this serves a 200.")
        return audit

    # A parking or coming-soon page is not a site with SEO problems; it is the
    # absence of a site. Listing 10 findings against it buries the one thing
    # that matters and drags the portfolio mean down for no reason.
    if _is_placeholder(home):
        audit.add(id="site.placeholder", scope="site", area="technical", severity=INFO, url=home.url,
                  title="This is a placeholder, not a site",
                  evidence=f"{len(home.content)} bytes of HTML, no navigation, "
                           "no sitemap — a coming-soon page.",
                  fix="Nothing to audit until there is a site. Meanwhile the domain "
                      "still accrues Search Console impressions, so Agent 1 keeps "
                      "gathering demand data for it — that is the useful signal here.")
        audit.stats["placeholder"] = True
        audit.stats["duration_ms"] = int((time.time() - started) * 1000)
        return audit

    if home.url.startswith("http://"):
        audit.add(id="http.no_https", scope="site", area="technical", severity=CRITICAL, url=home.url,
                  title="Site is served over plain HTTP", evidence=home.url,
                  fix="Install a certificate and 301 all HTTP to HTTPS.")

    audit_robots(site, session, audit)
    sitemap_urls = audit_sitemap(site, session, audit)
    audit_canonical_host(site, session, audit)
    audit_404(site, session, audit)
    audit_llms_txt(site, session, audit)
    audit_page(site, home.url, home, audit, is_home=True)

    # A sample of interior pages — enough to tell a template problem from a
    # one-page problem, without crawling the whole site.
    checked = 0
    _shell_probe: list[tuple[str, int]] = []
    _statuses: dict[str, int] = {}
    for url in sorted(sitemap_urls)[:sample]:
        if url.rstrip("/") == site.base_url.rstrip("/"):
            continue
        resp = fetch(session, url)
        _statuses[url] = resp.status_code if resp is not None else 0
        if resp is None or resp.status_code >= 400:
            audit.add(id="http.sitemap_url_broken", area="technical", severity=HIGH, url=url,
                      title="Sitemap lists a URL that does not load",
                      evidence=f"HTTP {resp.status_code if resp else 'no response'}",
                      fix="Remove it or fix it. Broken sitemap entries waste crawl budget "
                          "and signal a stale build.")
            continue
        audit_page(site, url, resp, audit, is_home=False, from_sitemap=True)
        _shell_probe.append((url, _server_words(resp.text)))
        checked += 1
        time.sleep(0.2)

    audit_client_rendered(site, _shell_probe, audit)
    audit_nonascii_slugs(site, _shell_probe, audit, _statuses)
    audit.stats["sample_pages"] = sample
    audit.stats["pages_checked"] = checked + 1
    audit.stats["duration_ms"] = int((time.time() - started) * 1000)
    return audit


# ══════════════════════════════════════════════════════════════════════════════
# 7. Reporting
# ══════════════════════════════════════════════════════════════════════════════

_SEV_LABEL = {CRITICAL: "CRITICAL", HIGH: "HIGH", MEDIUM: "MEDIUM", LOW: "LOW", INFO: "INFO"}


def to_markdown(audits: list[SiteAudit]) -> str:
    lines = [
        "# Site audit — technical, GEO and content",
        "",
        f"Generated {rfc3339()} · Architecture credit: {config.ARCHITECTURE_CREDIT}",
        "",
        "| Site | Score | Critical | High | Medium | Low |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for a in sorted(audits, key=lambda x: x.score()):
        c = a.as_dict()["counts"]
        lines.append(
            f"| `{a.domain}` | **{a.score()}** | {c[CRITICAL]} | {c[HIGH]} | "
            f"{c[MEDIUM]} | {c[LOW]} |"
        )

    for a in sorted(audits, key=lambda x: x.score()):
        d = a.as_dict()
        lines += ["", f"## {a.domain} — {a.score()}/100", ""]
        if not a.findings:
            lines.append("Nothing found. Either it is clean or it was unreachable.")
            continue
        for f in d["findings"]:
            if f["severity"] == INFO:
                continue
            lines += [
                f"### [{_SEV_LABEL[f['severity']]}] {f['title']}",
                "",
                f"- **Where:** {f['url'] or a.domain}",
                f"- **Evidence:** {f['evidence']}",
                f"- **Fix:** {f['fix']}",
                "",
            ]
    return "\n".join(lines)


def build_payload(
    audits: list[SiteAudit], run_id: str, *, sample_override: int | None = None
) -> dict[str, Any]:
    """site.audit.v1 — same envelope as every other message in the pipeline."""
    pinned = sorted({a.stats.get("sample_pages") for a in audits} - {None})
    return {
        "sampling": {
            "sample_pages": pinned[0] if len(pinned) == 1 else pinned,
            "pinned": sample_override is None,
            # The score counts findings, so it scales with how many pages were
            # sampled. Only runs at the same sample size belong on one trend line.
            "comparable_with_scheduled_runs": sample_override is None,
            "note": (
                "Scheduled runs take audit_sample_pages from sites.yml. This run "
                + ("used the pinned value." if sample_override is None
                   else f"OVERRODE it with --sample {sample_override}; its scores are "
                        "not comparable with the trend line.")
            ),
        },
        "schema_version": config.SCHEMA_VERSION,
        "envelope": config.build_envelope(
            message_type="site.audit",
            emitted_by=AGENT_ID,
            target="agent6.analyst",
            correlation_id=run_id,
            idem_key=config.idempotency_key(run_id, "site.audit", ""),
        ),
        "generated_at": rfc3339(),
        "totals": {
            "sites": len(audits),
            "findings": sum(len(a.findings) for a in audits),
            "critical": sum(
                1 for a in audits for f in a.findings if f.severity == CRITICAL
            ),
            "mean_score": round(sum(a.score() for a in audits) / max(len(audits), 1), 1),
        },
        "sites": [a.as_dict() for a in audits],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 8. CLI
# ══════════════════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent 5 — Site Auditor. Architecture credit: Albaloo Studio."
    )
    parser.add_argument("--domain", action="append", help="restrict to a domain (repeatable)")
    parser.add_argument("--sample", type=int, default=None,
                        help="OVERRIDE the pinned audit_sample_pages from sites.yml. "
                             "Ad-hoc only: scores from a different sample size are not "
                             "comparable with the scheduled trend line.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--out", help="write to this file instead of stdout")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    try:
        sites = config.load_sites(only=args.domain)
    except config.ConfigError as exc:
        log.error("%s", exc)
        return 2

    run_id = config.new_run_id()
    if args.sample is not None:
        log.warning(
            "--sample %d overrides the pinned value; these scores are NOT comparable "
            "with scheduled runs. Omit --sample for a trend-line run.", args.sample
        )
    session = requests.Session()
    audits: list[SiteAudit] = []
    for site in sites:
        log.info("auditing %s …", site.domain)
        audit = audit_site(site, session, sample=args.sample)
        audits.append(audit)
        log.info(
            "%s — score %d, %d finding(s)", site.domain, audit.score(), len(audit.findings)
        )

    out = (
        to_markdown(audits)
        if args.format == "markdown"
        else json.dumps(build_payload(audits, run_id, sample_override=args.sample),
                        ensure_ascii=False, indent=2)
    )
    if args.out:
        from pathlib import Path

        Path(args.out).write_text(out, encoding="utf-8")
        log.info("written to %s", args.out)
    else:
        print(out)

    run_dir = config.RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "site-audit.json").write_text(
        json.dumps(build_payload(audits, run_id, sample_override=args.sample),
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    criticals = sum(1 for a in audits for f in a.findings if f.severity == CRITICAL)
    log.info("run %s — %d site(s), %d critical finding(s)", run_id, len(audits), criticals)
    return 1 if criticals else 0


if __name__ == "__main__":
    sys.exit(main())
