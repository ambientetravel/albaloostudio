#!/usr/bin/env python3
"""
What the cruise competitors target, and where our properties stand on it.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHAT THIS CAN AND CANNOT KNOW — read before quoting any number from it
─────────────────────────────────────────────────────────────────────
There is NO SEARCH VOLUME here, and none is invented. Google Ads does not
operate in Iran, so Keyword Planner cannot report on this market at all, and no
third-party keyword tool is wired into this pipeline. Anyone who hands you a
Farsi cruise volume figure without naming its source is guessing.

What IS knowable, and what this uses:

  * WHAT RIVALS TARGET. A page's title, h1 and meta description are a
    deliberate statement of the term it wants. Reading those across a
    competitor's cruise pages recovers their keyword map from their own words.
  * HOW MANY RIVALS TARGET IT. A phrase three competitors independently build
    pages around is a stronger signal than one appearing forty times on a
    single site, which is usually a template repeating itself.
  * WHERE WE STAND. Search Console gives our real position for anything we
    surface for at all, and — more usefully — silence for everything we do not.

So the ranking below is COMPETITOR CONSENSUS, not demand. It answers "what is
this market built around and are we present", which is the question that has an
honest answer, rather than "what gets searched most", which does not.

    python3 tools/keyword_gap.py --rivals nilfamtravel.com,gotosafar.com \\
                                 --mine boutimar.ir,cruise24.ir,cruisebaz.com
    python3 tools/keyword_gap.py --top 50 --format json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import agent1_seo_scout as a1  # noqa: E402

_SM_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_TAG = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>|<[^>]+>")

# Persian normalisation. Arabic yeh and kaf are visually identical to the
# Persian letters and constantly mixed in real pages — «كشتي» and «کشتی» are the
# same word to a reader and different strings to a computer. Without this the
# whole study fragments into near-duplicate rows.
_NORM = {
    "ي": "ی",   # Arabic yeh    -> Persian yeh
    "ى": "ی",   # alef maksura  -> Persian yeh
    "ك": "ک",   # Arabic kaf    -> Persian keheh
    "‌": " ",        # ZWNJ          -> space, so compounds tokenise
    "‏": "", "‎": "",
    "ـ": "",         # tatweel
}
_DIACRITICS = re.compile(r"[ً-ْٰ]")

# The segment being studied. A phrase must contain one of these to count — the
# point is cruise keywords, not every phrase on a travel site.
SEEDS = ("کروز", "کشتی", "دریایی", "کروزی")

# Words that carry no intent on their own and make a phrase useless as a target.
_STOP = {"در", "به", "از", "با", "را", "که", "این", "برای", "های", "ها", "است",
         "می", "و", "یا", "تا", "بر", "هم", "شما", "ما", "بیشتر", "ادامه",
         "بخوانید", "مطلب", "صفحه", "اصلی", "تماس", "درباره"}


def norm(text: str) -> str:
    text = _DIACRITICS.sub("", text or "")
    for a, b in _NORM.items():
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def phrases(text: str, lo: int = 2, hi: int = 4) -> list[str]:
    """Every 2–4 word phrase containing a cruise seed, normalised."""
    words = [w for w in re.split(r"[^\w؀-ۿ]+", norm(text)) if w]
    out = []
    for n in range(lo, hi + 1):
        for i in range(len(words) - n + 1):
            gram = words[i:i + n]
            if gram[0] in _STOP or gram[-1] in _STOP:
                continue
            if not any(s in w for w in gram for s in SEEDS):
                continue
            if all(len(w) < 3 for w in gram):
                continue
            out.append(" ".join(gram))
    return out


def _robots(session: requests.Session, base: str) -> RobotFileParser | None:
    rp = RobotFileParser()
    try:
        r = session.get(f"{base}/robots.txt", timeout=20,
                        headers={"User-Agent": config.USER_AGENT})
        if r.status_code >= 400:
            return None
        rp.parse(r.text.splitlines())
        return rp
    except requests.RequestException:
        return None


def sitemap_urls(session: requests.Session, base: str, cap: int = 400) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def pull(url: str, depth: int = 0) -> None:
        if len(out) >= cap or depth > 2 or url in seen:
            return
        seen.add(url)
        try:
            r = session.get(url, timeout=25,
                            headers={"User-Agent": config.USER_AGENT})
            if r.status_code >= 400:
                return
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError):
            return
        if root.tag.split("}")[-1] == "sitemapindex":
            for loc in root.findall(".//sm:sitemap/sm:loc", _SM_NS):
                if loc.text:
                    pull(loc.text.strip(), depth + 1)
        else:
            for loc in root.findall(".//sm:url/sm:loc", _SM_NS):
                if loc.text and len(out) < cap:
                    out.append(loc.text.strip())

    for name in ("sitemap.xml", "sitemap_index.xml", "sitemap-index.xml"):
        pull(f"{base}/{name}")
        if out:
            break
    return out


def page_terms(session: requests.Session, url: str) -> list[str]:
    """Title, h1/h2 and meta description — where a page states its target."""
    try:
        r = session.get(url, timeout=25, headers={"User-Agent": config.USER_AGENT})
        if r.status_code >= 400 or "html" not in (r.headers.get("Content-Type") or ""):
            return []
        html = r.text
    except requests.RequestException:
        return []
    parts: list[str] = []
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if m:
        parts.append(_TAG.sub(" ", m.group(1)))
    m = re.search(r'(?is)<meta\s+name="description"\s+content="([^"]*)"', html)
    if m:
        parts.append(m.group(1))
    for h in re.findall(r"(?is)<h[12][^>]*>(.*?)</h[12]>", html)[:8]:
        parts.append(_TAG.sub(" ", h))
    grams: list[str] = []
    for p in parts:
        grams += phrases(p)
    return grams


def study_rival(session: requests.Session, domain: str, sample: int) -> dict[str, Any]:
    base = f"https://{domain}"
    rp = _robots(session, base)
    urls = sitemap_urls(session, base)
    # Cruise-looking URLs first, then anything, so a small sample still lands on
    # the pages that matter rather than the blog's back catalogue.
    ranked = sorted(urls, key=lambda u: 0 if re.search(r"cruise|کروز|kroz|keshti", u, re.I) else 1)
    picked, grams = [], Counter()
    for u in ranked:
        if len(picked) >= sample:
            break
        if rp is not None and not rp.can_fetch(config.USER_AGENT, u):
            continue
        g = page_terms(session, u)
        if g:
            picked.append(u)
            grams.update(g)
    return {"domain": domain, "sitemap_urls": len(urls),
            "pages_read": len(picked), "grams": grams}


def my_positions(service, domains: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for d in domains:
        try:
            site = config.load_sites(only=[d], include_hold=True)[0]
        except Exception:
            continue
        end = (a1.utc_now() - timedelta(days=site.data_lag_days)).date()
        start = end - timedelta(days=site.lookback_days)
        try:
            rows = a1._search_analytics(service, site.property_uri,
                                        start.isoformat(), end.isoformat(), ["query"])
        except Exception:
            rows = []
        out[d] = [{"q": norm((r.get("keys") or [""])[0]),
                   "pos": round(float(r.get("position", 0) or 0), 1),
                   "imp": int(r.get("impressions", 0) or 0)} for r in rows]
    return out


def stand(term: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Our best position for anything containing this term, or absence."""
    hits = [r for r in rows if term in r["q"]]
    if not hits:
        return {"present": False}
    best = min(hits, key=lambda x: x["pos"])
    return {"present": True, "pos": best["pos"],
            "imp": sum(h["imp"] for h in hits), "queries": len(hits)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rivals", default="",
                    help="comma-separated competitor domains (omit with --render)")
    ap.add_argument("--render", type=Path,
                    help="re-render a saved JSON study as markdown, crawling nothing")
    ap.add_argument("--mine", default="boutimar.ir,cruise24.ir,cruisebaz.com")
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    # Re-render mode: the crawl already happened, the answer is on disk, and
    # fetching four sites again to print the same table differently is waste
    # paid for by someone else's bandwidth.
    if args.render:
        saved = json.loads(args.render.read_text(encoding="utf-8"))
        _report(saved["rivals"], saved["terms"],
                [d.strip() for d in args.mine.split(",") if d.strip()])
        return 0

    if not args.rivals:
        print("--rivals is required unless --render is given", file=sys.stderr)
        return 2

    session = requests.Session()
    rivals = [d.strip() for d in args.rivals.split(",") if d.strip()]
    mine = [d.strip() for d in args.mine.split(",") if d.strip()]

    studies = [study_rival(session, d, args.sample) for d in rivals]
    # Score by HOW MANY rivals use a phrase first, total uses second. One site
    # repeating a phrase in a template is not evidence; three sites choosing it
    # independently is.
    breadth: Counter = Counter()
    depth: Counter = Counter()
    for s in studies:
        for g in set(s["grams"]):
            breadth[g] += 1
        depth.update(s["grams"])
    ranked = sorted(breadth, key=lambda g: (-breadth[g], -depth[g], len(g)))

    service = a1.build_gsc_client()
    pos = my_positions(service, mine)

    rows = []
    for term in ranked[:args.top]:
        rows.append({"term": term, "rivals": breadth[term], "uses": depth[term],
                     "mine": {d: stand(term, pos.get(d, [])) for d in mine}})

    studies_public = [{k: v for k, v in s.items() if k != "grams"} for s in studies]
    if args.format == "json":
        print(json.dumps({"rivals": studies_public, "terms": rows},
                         ensure_ascii=False, indent=2))
        return 0

    _report(studies_public, rows, mine)
    return 0


def _report(studies_public: list[dict[str, Any]], rows: list[dict[str, Any]],
            mine: list[str]) -> None:
    print("# Cruise keyword map — competitor consensus, and where we stand\n")
    print("**No search volume appears here and none is estimated.** Google Ads "
          "does not operate in Iran and no keyword tool is wired in, so the "
          "ranking is by how many rivals independently build pages around a "
          "phrase — a statement of what the market is built on, not of what "
          "gets searched most.\n")
    print("| Rival | Sitemap URLs | Pages read |")
    print("|---|---:|---:|")
    for s in studies_public:
        print(f"| {s['domain']} | {s['sitemap_urls']:,} | {s['pages_read']} |")
    print()
    head = " | ".join(mine)
    print(f"| # | Term | Rivals | Uses | {head} |")
    print("|---:|---|---:|---:|" + "---|" * len(mine))
    for i, r in enumerate(rows, 1):
        cells = []
        for d in mine:
            st = r["mine"][d]
            cells.append(f"**{st['pos']}**" if st.get("present") else "—")
        print(f"| {i} | {r['term']} | {r['rivals']} | {r['uses']} | "
              + " | ".join(cells) + " |")
    print()
    print("`—` means Search Console has never shown that property for any query "
          "containing the term: there is no position to improve and no listing "
          "to optimise. A number is our best position across every query "
          "containing it.\n")


if __name__ == "__main__":
    sys.exit(main())
