#!/usr/bin/env python3
"""
How much of each site Google actually shows.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Agent 1 answers half of this already: `find_unlisted_pages()` reports pages
Google ranks that the sitemap never mentions. This is the other half, and the
bigger one — pages the site DECLARES that Google has never once surfaced.

WHAT THE THREE SETS MEAN, because conflating them is the whole trap
───────────────────────────────────────────────────────────────────
    S  every URL in the sitemap, following <sitemapindex> one level down
    G  every URL Search Console recorded at least one impression for
    R  every URL in S that the site's own robots.txt disallows

    S ∩ G   declared and surfaced — working
    S − G   declared, never surfaced  ← the number this tool is FOR
    G − S   surfaced, never declared  ← agent 1 already reports this

`S − G` IS NOT "NOT INDEXED". This is the single most important line in the
file. Search Analytics reports IMPRESSIONS, not index membership. A page can be
indexed, healthy and simply never have ranked well enough to be shown to anyone
in the window — that page is invisible in G and is not an indexing fault. The
honest label is "never surfaced", and every heading here says that instead.

The only API that answers "is this indexed?" is URL Inspection, and it has a
condition this pipeline does not currently meet:

    URL Inspection requires the caller to be an OWNER or FULL user of the
    property. This service account is a RESTRICTED user on all ten — that is
    what ARCHITECTURE.md §3.1 describes and it is deliberate. Restricted is
    enough for Search Analytics and NOT enough for inspection.

So `--inspect` is built, defaults to off, and reports the 403 as the permission
fact it is rather than as a broken run. Upgrade the service account to Full in
Search Console → Settings → Users and permissions, per property, and it starts
answering. Quota when it does: 2000 URLs/day/property, 600/minute.

    python3 tools/index_coverage.py                      # every active site
    python3 tools/index_coverage.py --domain boutimar.com
    python3 tools/index_coverage.py --include-hold       # + cruiseshop, dmciran
    python3 tools/index_coverage.py --inspect 25         # real index status
    python3 tools/index_coverage.py --format json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import agent1_seo_scout as a1  # noqa: E402

log = logging.getLogger("tools.index_coverage")

ARCHITECTURE_CREDIT = config.ARCHITECTURE_CREDIT

# Sample size when --inspect is given without a number. Deliberately small:
# the quota is per property per day and this is a diagnostic, not a crawl.
DEFAULT_INSPECT_SAMPLE = 25


def fetch_declared(site: config.Site, session: requests.Session
                   ) -> tuple[set[str], str | None]:
    """
    The sitemap, and WHY it is empty when it is empty.

    agent1.fetch_sitemap_urls() swallows every failure into an empty set, which
    is right for its purpose — it degrades to "unknown supply" and lets the LLM
    judge. It is wrong for this one. Run #2 reported exploreorient.com as
    `declared 0, coverage —` when the site declares 70 URLs; the sitemap had
    come back as an HTML error page and "could not read" was rendered as "has
    nothing". That understated the portfolio by 70 pages and would have sent
    someone to write content for a site that already has it.

    So this returns the reason alongside, and reports the shape of what actually
    arrived. `mismatched tag: line 93, column 2` is what ElementTree says when
    it is handed a web page; it is not a diagnosis anyone can act on.
    """
    try:
        resp = session.get(site.sitemap, timeout=20,
                           headers={"User-Agent": config.USER_AGENT})
    except requests.RequestException as exc:
        return set(), f"request failed: {str(exc)[:120]}"
    if resp.status_code >= 400:
        return set(), f"HTTP {resp.status_code}"

    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
    head = resp.content[:200].lstrip()[:80].decode("utf-8", "replace")
    if not head.startswith("<?xml") and "<urlset" not in head and "<sitemapindex" not in head:
        return set(), (f"served {ctype or 'unknown type'}, not XML — begins "
                       f"{head[:60]!r}")

    urls = a1.fetch_sitemap_urls(site, session)
    if not urls:
        return set(), f"parsed as {ctype or 'XML'} but listed no URLs"
    return urls, None


def surfaced_urls(service, site: config.Site) -> tuple[set[str], int]:
    """
    Every URL Search Console showed at least once, over the long window.

    Dimension is ["page"] alone, not agent 1's ["query","page"]. The query pair
    is capped per request and a page that ranks for many low-volume queries can
    fall off the end of it; ["page"] is one row per page and cannot.
    """
    from datetime import timedelta
    end = (a1.utc_now() - timedelta(days=site.data_lag_days)).date()
    start = end - timedelta(days=site.lookback_days)
    rows = a1._search_analytics(service, site.property_uri,
                                start.isoformat(), end.isoformat(), ["page"])
    urls, impressions = set(), 0
    for r in rows:
        keys = r.get("keys") or []
        if not keys:
            continue
        urls.add(a1._canon_url(keys[0]))
        impressions += int(r.get("impressions", 0) or 0)
    return urls, impressions


def robots_blocked(site: config.Site, sitemap_urls: set[str],
                   session: requests.Session) -> dict[str, Any]:
    """
    Declared URLs the site's own robots.txt forbids.

    Worth its own column because it is the one cause of "declared but never
    surfaced" that is both extremely common and entirely self-inflicted —
    boutimar.ir spent weeks with a robots.txt that starved its own JS-rendered
    pages. A page in this set will never surface no matter how much is written.
    """
    root = f"{urlparse(site.base_url).scheme}://{urlparse(site.base_url).netloc}"
    rp = RobotFileParser()
    try:
        resp = session.get(f"{root}/robots.txt", timeout=20,
                           headers={"User-Agent": config.USER_AGENT})
        if resp.status_code >= 400:
            return {"available": False, "reason": f"HTTP {resp.status_code}", "blocked": []}
        rp.parse(resp.text.splitlines())
    except requests.RequestException as exc:
        return {"available": False, "reason": str(exc)[:120], "blocked": []}

    blocked = [u for u in sorted(sitemap_urls) if not rp.can_fetch("Googlebot", u)]
    return {"available": True, "reason": None, "blocked": blocked}


def inspect_urls(service, site: config.Site, urls: list[str]) -> dict[str, Any]:
    """
    Real index status, for as many URLs as the caller asked for.

    Returns a `permitted: False` result rather than raising when the service
    account is Restricted — that is a fact about the grant, not a failure of
    the run, and every other column on this report is still valid without it.
    """
    out: list[dict[str, Any]] = []
    for url in urls:
        try:
            resp = service.urlInspection().index().inspect(body={
                "inspectionUrl": url,
                "siteUrl": site.property_uri,
            }).execute()
        except Exception as exc:  # googleapiclient raises HttpError, but not only
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status in (403, 401):
                return {
                    "permitted": False,
                    "reason": (
                        "URL Inspection needs an OWNER or FULL user; this service "
                        "account is Restricted on this property. Search Console → "
                        "Settings → Users and permissions → set it to Full."),
                    "results": out,
                }
            log.warning("%s — inspect failed for %s: %s", site.domain, url,
                        config.redact(str(exc))[:160])
            continue
        idx = (resp.get("inspectionResult") or {}).get("indexStatusResult") or {}
        out.append({
            "url": url,
            "verdict": idx.get("verdict"),
            "coverage_state": idx.get("coverageState"),
            "indexing_state": idx.get("indexingState"),
            "last_crawl": idx.get("lastCrawlTime"),
            "robots_state": idx.get("robotsTxtState"),
        })
    return {"permitted": True, "reason": None, "results": out}


def assess(service, site: config.Site, session: requests.Session,
           *, inspect: int = 0) -> dict[str, Any]:
    declared_raw, sitemap_error = fetch_declared(site, session)
    declared = {a1._canon_url(u) for u in declared_raw}
    try:
        surfaced, impressions = surfaced_urls(service, site)
    except PermissionError as exc:
        return {"domain": site.domain, "error": config.redact(str(exc))[:200]}

    never = sorted(declared - surfaced)
    undeclared = sorted(surfaced - declared)
    robots = robots_blocked(site, declared_raw, session)
    blocked_canon = {a1._canon_url(u) for u in robots["blocked"]}

    row: dict[str, Any] = {
        "domain": site.domain,
        "market": site.market,
        "on_hold": bool(getattr(site, "on_hold", False)),
        # None when the sitemap could not be READ, 0 only when it genuinely
        # declares nothing. Every count derived from it is None too — a site
        # whose supply is unknown has an unknown gap, not a gap of zero, and
        # summing it into a portfolio total silently understates the total.
        "sitemap_error": sitemap_error,
        "declared": None if sitemap_error else len(declared),
        "surfaced": len(surfaced),
        "declared_and_surfaced": None if sitemap_error else len(declared & surfaced),
        "declared_never_surfaced": None if sitemap_error else len(never),
        # This one stays a real number either way: every surfaced URL genuinely
        # is undeclared when nothing could be read from the sitemap. It is the
        # only column an unreadable sitemap does not poison.
        "surfaced_never_declared": len(undeclared),
        "robots_blocked": None if sitemap_error else len(blocked_canon),
        "robots_available": robots["available"],
        "impressions": impressions,
        # Share of what the site DECLARES that Google has shown at least once.
        # None, not 0.0, when nothing is declared — a site with no sitemap has
        # no coverage ratio, and printing 0% would read as a failing site
        # rather than an unmeasurable one.
        "coverage": (None if sitemap_error or not declared
                     else round(len(declared & surfaced) / len(declared), 3)),
        "sample_never_surfaced": never[:15],
        "sample_undeclared": undeclared[:15],
    }
    if inspect and never:
        row["inspection"] = inspect_urls(service, site, never[:inspect])
    return row


def render_markdown(rows: list[dict[str, Any]]) -> str:
    L = ["# How much of each site Google actually shows", "",
         f"Architecture credit: **{ARCHITECTURE_CREDIT}**", "",
         "**`Never surfaced` is not the same as `not indexed`.** Search Analytics "
         "reports impressions, not index membership: a page can be indexed, "
         "healthy, and simply never have ranked well enough to be shown to anyone "
         "in the window. Only URL Inspection answers indexing, and it needs a "
         "permission level this service account does not have — see the foot of "
         "this report.", "",
         "| Site | Declared | Surfaced | Never surfaced | Undeclared but ranking | Robots-blocked | Coverage |",
         "|---|---:|---:|---:|---:|---:|---:|"]
    num = lambda v: "?" if v is None else f"{v:,}"
    for r in sorted(rows, key=lambda x: -(x.get("declared") or 0)):
        if r.get("error"):
            L.append(f"| {r['domain']} | — | — | — | — | — | not readable |")
            continue
        cov = "—" if r["coverage"] is None else f"{r['coverage']:.0%}"
        if r.get("sitemap_error"):
            cov = "sitemap unreadable"
        hold = " *(on hold)*" if r["on_hold"] else ""
        L.append(f"| {r['domain']}{hold} | {num(r['declared'])} | {num(r['surfaced'])} | "
                 f"{num(r['declared_never_surfaced'])} | {num(r['surfaced_never_declared'])} | "
                 f"{num(r['robots_blocked'])} | {cov} |")
    L.append("")

    # Totals over the sites that could actually be measured, and an explicit
    # count of the ones that could not. A total that quietly drops the
    # unreadable sites reads as a complete portfolio figure and is not one.
    unreadable = [r for r in rows if r.get("sitemap_error")]
    measured = [r for r in rows if not r.get("sitemap_error") and not r.get("error")]
    totals_declared = sum(r["declared"] for r in measured)
    totals_never = sum(r["declared_never_surfaced"] for r in measured)
    totals_undeclared = sum(r.get("surfaced_never_declared") or 0 for r in rows)
    scope = (f" across the {len(measured)} propert(ies) whose sitemap could be read"
             if unreadable else "")
    L.append(f"**{totals_never:,} of {totals_declared:,} declared pages have never been "
             f"surfaced**{scope}, and **{totals_undeclared:,} pages rank without being "
             f"declared.**")
    L.append("")
    if unreadable:
        L.append(f"### {len(unreadable)} sitemap(s) could not be read")
        L.append("These sites are counted in NEITHER total above. `?` is not zero — "
                 "their declared pages are unknown, so their gap is unknown too.")
        L.append("")
        for r in unreadable:
            L.append(f"- **{r['domain']}** — {r['sitemap_error']}")
        L.append("")

    for r in sorted(rows, key=lambda x: -(x.get("declared_never_surfaced") or 0)):
        if r.get("error") or r.get("sitemap_error") or not r.get("declared_never_surfaced"):
            continue
        L.append(f"## {r['domain']} — {r['declared_never_surfaced']:,} declared, never surfaced")
        if r["robots_blocked"]:
            L.append(f"{r['robots_blocked']:,} of them are disallowed by the site's own "
                     f"robots.txt and cannot surface however much is written.")
        elif not r["robots_available"]:
            L.append("robots.txt could not be read, so the blocked count is unknown "
                     "rather than zero.")
        L.append("")
        for u in r["sample_never_surfaced"]:
            L.append(f"- `{u}`")
        if r["declared_never_surfaced"] > len(r["sample_never_surfaced"]):
            L.append(f"- …and {r['declared_never_surfaced'] - len(r['sample_never_surfaced']):,} more")
        L.append("")
        insp = r.get("inspection")
        if insp and not insp["permitted"]:
            L.append(f"> Index status not read: {insp['reason']}")
            L.append("")
        elif insp and insp["results"]:
            L.append("| URL | Verdict | Coverage state | Last crawl |")
            L.append("|---|---|---|---|")
            for i in insp["results"]:
                L.append(f"| `{i['url']}` | {i['verdict'] or '—'} | "
                         f"{i['coverage_state'] or '—'} | {i['last_crawl'] or 'never'} |")
            L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", action="append")
    ap.add_argument("--include-hold", action="store_true")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--inspect", nargs="?", type=int, const=DEFAULT_INSPECT_SAMPLE,
                    default=0, help="also read real index status for N URLs per site")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")
    try:
        sites = config.load_sites(only=args.domain, include_hold=args.include_hold)
        service = a1.build_gsc_client()
    except config.ConfigError as exc:
        log.error("%s", exc)
        return 2

    session = requests.Session()
    rows = []
    for site in sites:
        try:
            rows.append(assess(service, site, session, inspect=args.inspect))
        except PermissionError as exc:
            log.error("%s — skipped: %s", site.domain, config.redact(str(exc))[:160])
        else:
            r = rows[-1]
            if not r.get("error"):
                if r.get("sitemap_error"):
                    log.warning("%s — sitemap UNREADABLE (%s); declared count is "
                                "unknown, not zero", r["domain"], r["sitemap_error"])
                else:
                    log.info("%s — declared %d, surfaced %d, never surfaced %d",
                             r["domain"], r["declared"], r["surfaced"],
                             r["declared_never_surfaced"])
    if not rows:
        log.error("no readable properties")
        return 1

    text = (render_markdown(rows) if args.format == "md"
            else json.dumps(rows, ensure_ascii=False, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        log.info("wrote %s (%d bytes)", args.out, len(text))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
