#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریانامه — static generator for the Farsi cruise hub + PWA.

Owner: Alireza Mozaffari · Ambiente Turizm, Kuşadası
Architecture credit: Albaloo Studio — albaloostudio.com

    python3 build.py            # content/ + templates/ + static/  ->  public/
    python3 build.py --check    # house rules: «خلیج فارس», no "visa-free" on easy-visa ports

HOW CONTENT GETS IN
───────────────────
Every collection is one JSON file in content/ (ports.json, ships.json, ...). Add an
object to the list, rebuild, deploy. collections.json names the collection, its
Farsi title and which `facts` keys appear in the fact table. Articles are Markdown
files in content/articles/ with a small front-matter block. Offers merge two
sources: content/offers.json `manual` (hand-entered, must carry `verified_on`) and
the live sailing feed from site.json `feed.url` (fetched at build if reachable and
again in the browser by static/js/offers.js).

NOTHING IS INVENTED
───────────────────
No rate, date or inclusion appears unless it is in content/ or in the feed.
Visa levels come from cruise24-ir/_visa.py, the one classifier all properties share.
"""
from __future__ import annotations
import argparse, datetime, html, json, re, shutil, subprocess, sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = Path(__file__).resolve().parent
CONTENT, TEMPLATES, STATIC, PUBLIC = HERE/"content", HERE/"templates", HERE/"static", HERE/"public"
sys.path.insert(0, str(HERE.parent/"cruise24-ir"))
import _visa  # noqa: E402  (shared visa classifier — the single source of truth)

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
FACT_LABELS = {
    "country": "کشور", "terminal": "ترمینال", "walkable": "پیاده تا شهر", "visa": "ویزا برای گذرنامهٔ ایرانی",
    "distance_city": "فاصله تا شهر", "unesco_nearby": "میراث جهانی نزدیک", "line": "خط کروز", "year": "سال ساخت",
    "gt": "تناژ ناخالص", "length_m": "طول (متر)", "guests": "مسافر", "cabins": "کابین", "class": "کلاس",
    "river": "رودخانه", "hq": "دفتر مرکزی", "founded": "تأسیس", "fleet_size": "ناوگان", "style": "سبک",
    "iranian_passport": "گذرنامهٔ ایرانی", "length_km": "طول (کیلومتر)", "countries": "کشورها", "season": "فصل",
    "classic_route": "مسیر کلاسیک", "dock": "اسکله", "port": "بندر", "duration": "مدت", "type": "نوع",
    "distance": "فاصله", "inscribed": "سال ثبت", "nearest_port": "نزدیک‌ترین بندر", "chain": "زنجیره",
    "city": "شهر", "near_port": "تا بندر", "opened": "افتتاح", "era": "دوره", "status": "وضعیت",
}
VISA_LABEL = {"schengen": "شینگن", "hard": "ویزای دشوار (آمریکا/بریتانیا/کانادا)", "easy": "ویزای آسان",
              "free": "بدون ویزا", "unknown": "نیازمند بررسی"}

def fa(n) -> str:
    return str(n).translate(FA_DIGITS)

def load(name):
    return json.loads((CONTENT/f"{name}.json").read_text(encoding="utf-8"))

def md_to_html(md: str) -> str:
    """Tiny Markdown: headings, paragraphs, bullet lists, bold, links. Enough for editorial."""
    out, para, ul = [], [], False
    def flush():
        nonlocal para
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>"); para = []
    def inline(t):
        t = html.escape(t, quote=False)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', t)
        return t
    for line in md.splitlines():
        s = line.rstrip()
        if s.startswith("## "):
            flush(); out.append(f"<h2>{inline(s[3:])}</h2>")
        elif s.startswith("### "):
            flush(); out.append(f"<h3>{inline(s[4:])}</h3>")
        elif s.startswith("- "):
            flush()
            if not ul: out.append("<ul>"); ul = True
            out.append(f"<li>{inline(s[2:])}</li>")
        elif not s:
            flush()
            if ul: out.append("</ul>"); ul = False
        else:
            para.append(s)
    flush()
    if ul: out.append("</ul>")
    return "\n".join(out)

def load_articles():
    arts = []
    for p in sorted((CONTENT/"articles").glob("*.md")):
        txt = p.read_text(encoding="utf-8")
        meta, body = {}, txt
        if txt.startswith("---"):
            _, fm, body = txt.split("---", 2)
            for ln in fm.strip().splitlines():
                k, _, v = ln.partition(":"); meta[k.strip()] = v.strip()
        meta.setdefault("title", p.stem); meta.setdefault("date", ""); meta.setdefault("summary", "")
        meta["slug"] = p.stem; meta["html"] = md_to_html(body.strip())
        arts.append(meta)
    arts.sort(key=lambda a: a["date"], reverse=True)
    return arts

def fetch_feed(url: str):
    try:
        out = subprocess.run(["curl", "-sS", "--max-time", "25", url], capture_output=True, timeout=40)
        rows = json.loads(out.stdout.decode("utf-8"))
        return rows if isinstance(rows, list) else [], "live"
    except Exception as e:  # noqa: BLE001
        return [], f"unavailable at build ({type(e).__name__})"

def normalise_offer(s: dict, book_url: str) -> dict:
    ports = [p for p in (s.get("ports") or []) if p]
    v = _visa.classify(ports)
    dates = s.get("dates") or []
    return {
        "title": s.get("title") or f"{s.get('ship','')} · {s.get('region','')}".strip(" ·"),
        "line": s.get("line", ""), "ship": s.get("ship", ""), "region": s.get("region", ""),
        "nights": s.get("nights"), "ports": ports, "dates": dates[:3], "date_count": len(dates),
        "price_from": s.get("priceFrom"), "currency": s.get("currency", "EUR"),
        "visa": VISA_LABEL.get(v.get("level", "unknown"), "نیازمند بررسی"), "visa_level": v.get("level", "unknown"),
        "book_url": s.get("book_url") or book_url, "source": s.get("source", "feed"),
    }

def build(check_only=False):
    site, collections = load("site"), load("collections")
    data = {c["slug"]: load(c["slug"]) for c in collections}
    didyouknow, glossary, offers_cfg = load("didyouknow"), load("glossary"), load("offers")
    articles = load_articles()
    index = {(c["slug"], it["slug"]): it for c in collections for it in data[c["slug"]]}
    coll_by_slug = {c["slug"]: c for c in collections}

    def resolve(rel):
        it = index.get((rel["collection"], rel["slug"]))
        return {"href": f"/{rel['collection']}/{rel['slug']}/", "title": it["title"] if it else rel["slug"],
                "kicker": coll_by_slug[rel["collection"]]["singular"]} if it else None

    manual = [dict(normalise_offer({**m, "priceFrom": m.get("price_from"), "source": "manual"}, site["feed"]["book_url"]))
              for m in offers_cfg.get("manual", []) if m.get("verified_on")]
    feed_rows, feed_status = fetch_feed(site["feed"]["url"])
    feed_offers = [normalise_offer(s, site["feed"]["book_url"]) for s in feed_rows if s.get("priceFrom")]
    feed_offers.sort(key=lambda o: (o["price_from"] or 9e9))
    offers = manual + feed_offers[: site["feed"]["max_offers"]]

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    env.filters["fa"] = fa
    built = datetime.date.today().isoformat()
    base = dict(site=site, nav=site["nav"], collections=collections, labels=FACT_LABELS, built=built,
                year_fa=fa(datetime.date.today().year), resolve=resolve)

    if PUBLIC.exists(): shutil.rmtree(PUBLIC)
    shutil.copytree(STATIC, PUBLIC)
    (PUBLIC/"data").mkdir(exist_ok=True)
    (PUBLIC/"data"/"visa.json").write_text(json.dumps({
        "schengen": sorted(_visa.SCHENGEN_PORTS), "free": sorted(_visa.VISA_FREE_PORTS),
        "hard": sorted(_visa.HARD_VISA_PORTS), "easy": sorted(_visa.EASY_VISA_PORTS),
        "labels": VISA_LABEL}, ensure_ascii=False), encoding="utf-8")
    (PUBLIC/"data"/"offers.json").write_text(json.dumps({"status": feed_status, "built": built, "offers": offers},
                                                        ensure_ascii=False), encoding="utf-8")
    (PUBLIC/"data"/"didyouknow.json").write_text(json.dumps(didyouknow, ensure_ascii=False), encoding="utf-8")

    search = [{"u": f"/{c['slug']}/{it['slug']}/", "t": it["title"], "l": it.get("latin", ""), "k": it.get("kicker", ""),
               "c": c["singular"]} for c in collections for it in data[c["slug"]]]
    search += [{"u": f"/journal/{a['slug']}/", "t": a["title"], "l": "", "k": a.get("kicker", ""), "c": "مجله"} for a in articles]
    search += [{"u": "/visa/", "t": "ویزانامه", "l": "visa", "k": "ویزا", "c": "راهنما"}, {"u": "/glossary/", "t": "واژه‌نامهٔ کروز", "l": "glossary", "k": "", "c": "راهنما"}]
    (PUBLIC/"data"/"search.json").write_text(json.dumps(search, ensure_ascii=False), encoding="utf-8")

    urls = []
    def write(path: str, tpl: str, **ctx):
        out = PUBLIC/path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(env.get_template(tpl).render(**base, **ctx, path=path), encoding="utf-8")
        urls.append("/" + path.replace("index.html", ""))

    featured = {c["slug"]: data[c["slug"]][:4] for c in collections}
    write("index.html", "home.html", featured=featured, didyouknow=didyouknow, offers=offers[:4],
          feed_status=feed_status, articles=articles[:3], gatherings=data["gatherings"][:3])
    for c in collections:
        write(f"{c['slug']}/index.html", "listing.html", coll=c, items=data[c["slug"]])
        for it in data[c["slug"]]:
            rel = [r for r in (resolve(x) for x in it.get("related", [])) if r]
            write(f"{c['slug']}/{it['slug']}/index.html", "detail.html", coll=c, item=it, related=rel)
    write("offers/index.html", "offers.html", offers=offers, feed_status=feed_status)
    write("visa/index.html", "visa.html", schengen=sorted(_visa.SCHENGEN_PORTS), free=sorted(_visa.VISA_FREE_PORTS),
          easy=sorted(_visa.EASY_VISA_PORTS), hard=sorted(_visa.HARD_VISA_PORTS))
    write("glossary/index.html", "glossary.html", glossary=glossary)
    write("journal/index.html", "journal.html", articles=articles)
    for a in articles:
        write(f"journal/{a['slug']}/index.html", "article.html", article=a)
    write("policy/index.html", "policy.html")
    write("offline/index.html", "offline.html")

    sm = ["<?xml version='1.0' encoding='UTF-8'?>", "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    for u in urls:
        if u.startswith("/offline"): continue
        sm.append(f"  <url><loc>{site['brand']['domain']}{u}</loc><lastmod>{built}</lastmod></url>")
    sm.append("</urlset>")
    (PUBLIC/"sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    (PUBLIC/"robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site['brand']['domain']}/sitemap.xml\n")
    # Precache manifest for the service worker: shell + every port page (offline port guides).
    shell = ["/", "/offline/", "/css/hub.css", "/js/hub.js", "/js/offers.js", "/js/pwa.js", "/manifest.webmanifest",
             "/data/visa.json", "/data/offers.json"] + [f"/img/{p.name}" for p in (STATIC/"img").glob("*.svg")] + [f"/img/{p.name}" for p in (STATIC/"img").glob("*.png")]
    (PUBLIC/"precache.json").write_text(json.dumps({"version": built + "-" + str(len(urls)), "shell": shell,
                                                    "pages": urls}, ensure_ascii=False), encoding="utf-8")
    print(f"built {len(urls)} pages · offers: {len(offers)} ({feed_status}) · {sum(len(v) for v in data.values())} items")
    return urls

def check():
    bad = 0
    for p in PUBLIC.rglob("*.html"):
        t = p.read_text(encoding="utf-8")
        if "خلیج عربی" in t: print("HOUSE RULE: «خلیج عربی» in", p); bad += 1
        if "Arabian Gulf" in t: print("HOUSE RULE: 'Arabian Gulf' in", p); bad += 1
    for it in load("ports"):
        v = it["facts"].get("visa", "")
        port_name = it["title"].split(" ·")[0].split(" (")[0]
        if "بدون ویزا" in v and any(port_name.startswith(e) for e in _visa.EASY_VISA_PORTS):
            print("VISA RULE: easy-visa port labelled visa-free:", it["slug"]); bad += 1
    print("check:", "OK" if not bad else f"{bad} problem(s)")
    return bad

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check: sys.exit(1 if check() else 0)
    build(); sys.exit(1 if check() else 0)
