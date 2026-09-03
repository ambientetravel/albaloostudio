#!/usr/bin/env python3
"""Assemble the Gemini site-inventory seed from crawled sitemaps + live coverage."""
import os, re, json, subprocess, urllib.parse, collections, sys

OUT = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Macintosh) Chrome/128 Safari/537.36"

PLATFORM = {
    "boutimar.com": "Astro static, JSON-driven. Rich crawlable HTML.",
    "boutimar.ir": "Static Farsi site, flat .html pages. api/cruises.php feed.",
    "cruise24.ir": "Static B2C storefront, flat .html pages (partner API proxy).",
    "cruise24.me": "Turkish storefront. Thin sitemap; check live.",
    "cruisebaz.com": "base44 SPA — content client-rendered; sitemap is the reliable inventory.",
    "exploreorient.com": "Astro 5, content collections (tour/destination/venues). European brand — NO Iran corporate link.",
    "ambientetravel.com": "base44 SPA — content client-rendered; sitemap thin.",
    "albaloostudio.com": "Single-page studio site.",
}
# landmark pages to coverage-fetch per domain (section landings + key pages)
LANDMARKS = {
    "boutimar.com": ["/", "/experience/", "/mice/", "/hotels/", "/discover-iran/",
                     "/destinations/", "/journal/", "/travel-agents/"],
    "boutimar.ir": ["/", "/aroya.html", "/booking-guide.html", "/agencies.html"],
    "cruise24.ir": ["/", "/cruise-persian-gulf.html", "/cruise-prices.html",
                    "/cruise-lines.html", "/aroya.html", "/cruise-dubai.html"],
    "cruise24.me": ["/"],
    "cruisebaz.com": ["/"],
    "exploreorient.com": ["/", "/tour/", "/destination/", "/venues/", "/mice/", "/carbon/"],
    "ambientetravel.com": ["/"],
    "albaloostudio.com": ["/"],
}

def fetch(url):
    try:
        r = subprocess.run(["curl", "-sSL", "--max-time", "25", "-A", UA, url],
                           capture_output=True, text=True, timeout=30)
        return r.stdout or ""
    except Exception:
        return ""

def strip(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

def coverage(url):
    h = fetch(url)
    if not h:
        return {"url": url, "status": "empty/unreachable"}
    title = strip((re.search(r"<title[^>]*>(.*?)</title>", h, re.I | re.S) or [None, ""])[1])[:140]
    md = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', h, re.I | re.S) \
         or re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', h, re.I | re.S)
    meta = strip(md.group(1))[:220] if md else ""
    if "device-width" in meta or "initial-scale" in meta:
        meta = ""  # SPA caught the viewport tag, not a real description
    h1 = strip((re.search(r"<h1[^>]*>(.*?)</h1>", h, re.I | re.S) or [None, ""])[1])[:120]
    types = sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', h)))
    return {"url": url, "title": title, "meta": meta, "h1": h1,
            "schema_types": types, "bytes": len(h)}

def sections(domain):
    path = os.path.join(OUT, domain, "_urls.txt")
    if not os.path.exists(path): return {}, []
    urls = [l.strip() for l in open(path) if l.strip()]
    grp = collections.OrderedDict()
    for u in urls:
        seg = urllib.parse.urlparse(u).path.strip("/").split("/")[0] or "(home)"
        grp.setdefault(seg, []).append(u)
    counts = {seg: len(v) for seg, v in sorted(grp.items(), key=lambda kv: -len(kv[1]))}
    return counts, urls

seed = {"_seed": "albaloo-site-inventory", "generated": "2026-09-03",
        "purpose": ("Live inventory of what each property ALREADY has. Before proposing a "
                    "content_brief or schema task, check here: if the page/section exists and "
                    "covers the topic, propose ENRICHMENT of the extractable gap, not a new page. "
                    "Do not propose building a page that is listed here."),
        "properties": {}}

for d in LANDMARKS:
    counts, urls = sections(d)
    print(f"[{d}] {len(urls)} urls, {len(counts)} sections, {len(LANDMARKS[d])} coverage fetches", file=sys.stderr)
    cov = [coverage(f"https://{d}{p}") for p in LANDMARKS[d]]
    seed["properties"][d] = {
        "platform": PLATFORM.get(d, ""),
        "total_indexed_urls": len(urls),
        "section_counts": counts,          # shape: {section: n pages}
        "key_pages_coverage": cov,         # title/meta/h1/schema for landmark pages
        "all_pages": sorted(urllib.parse.urlparse(u).path or "/" for u in urls),  # complete dedupe list
    }

json.dump(seed, open(os.path.join(OUT, "gemini-inventory-seed.json"), "w"),
          ensure_ascii=False, indent=1)
print("WROTE gemini-inventory-seed.json", file=sys.stderr)
