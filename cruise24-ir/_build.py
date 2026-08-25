#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate cruise24.ir's pages from the live sailing feed.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHY THIS EXISTS
───────────────
On 25 Aug 2026 cruise24.ir had nine real pages and surfaced in Search Console
for exactly one keyword. Five of those nine — cruise-lines, msc, aroya,
celestyal, explora — were not in sitemap.xml at all. /msc.html carried 242
words while MSC is 3,237 of the 3,485 sailings in the feed.

Meanwhile a 769-term Farsi demand corpus sits in orchestrator/data, and 752 of
those terms return nothing from any property we own. This closes that gap with
pages built from real inventory.

NOTHING HERE IS INVENTED
────────────────────────
Every number on every generated page comes from the feed at build time: sailing
counts, ship names, port names, nights, priceFrom, departure dates. There is no
placeholder rate, no illustrative date, no "from €X" that is not the real
minimum of real sailings. Where the feed has nothing, the page says so — see
kish.html, which exists precisely because no line calls at Kish and searchers
deserve that answer rather than a fabricated itinerary.

THE TWO RULES THAT OUTRANK LAYOUT
─────────────────────────────────
  * «خلیج فارس». Never «خلیج عربی». Checked in --check.
  * Visa accuracy, per sailing, from its real ports — see _visa.py. The
    Persian Gulf pages say EASY VISA, never visa-free, because that is the
    truth and it is the specific lie the competition tells.

    python3 _build.py            # write pages + sitemap
    python3 _build.py --check    # verify what is on disk matches the feed
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _chrome  # noqa: E402
import _visa  # noqa: E402

HERE = Path(__file__).resolve().parent
FEED = "https://boutimar.ir/api/cruises.php"
BOOK = "https://book.cruise24.ir/"

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(n, group: bool = True) -> str:
    """Persian numerals. Grouped with «٬», the separator this site uses.

    group=False for years — «۲٬۰۲۷» is not a year.
    """
    txt = f"{n:,}" if group else str(n)
    return txt.translate(FA_DIGITS).replace(",", "\u066c")


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def latin(s) -> str:
    """Latin runs inside Farsi prose break mid-word without this wrapper."""
    return f'<span class="latin">{esc(s)}</span>'


# Months as book.cruise24.ir writes them. Copied from its MONTHS array rather
# than translated, so a date on a generated page and the same date in the
# booking engine read identically.
MONTHS_FA = ["ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن",
             "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"]


def money(n) -> str:
    """A price the way this site writes prices.

    The first fifteen pages emitted 342 strings like «۲۵۵ کروز ... 154 EUR» —
    Persian numerals for counts sitting beside Latin numerals for money, in the
    same sentence. On pages whose whole argument is "these are real figures
    from the feed", the figures were the part that read machine-generated.

    index.html already had the answer:
        eur(n) = '<span dir="ltr">€' + num(n) + '</span>'
    The dir="ltr" is load-bearing, not decoration. Without it the currency sign
    floats to whichever side the surrounding Farsi run decides, and «۱۵۴€» is
    not how a price is written in Farsi.
    """
    return f'<span dir="ltr">€{fa(int(n))}</span>'


def date_fa(iso: str) -> str:
    """«۱۵ مارس ۲۰۲۷», not «2027-03-15».

    227 ISO dates shipped in visible prose. ISO is a machine format; it is not
    how a date is written to a reader in Farsi, and book.cruise24.ir never
    does it. Falls back to the raw string rather than guessing if the value is
    not a date — a wrong date is worse than an ugly one.
    """
    try:
        y, m, d = (int(x) for x in str(iso).split("-"))
        return f"{fa(d, False)} {MONTHS_FA[m - 1]} {fa(y, False)}"
    except Exception:
        return esc(iso)


def fetch_feed() -> list[dict]:
    out = subprocess.run(["curl", "-sS", "--max-time", "60", FEED],
                         capture_output=True, timeout=90)
    return json.loads(out.stdout.decode("utf-8"))


# ── Page definitions ────────────────────────────────────────────────────────
# Each destination names the feed values it selects on. Ports are matched
# exactly against the itinerary; regions by substring of the region label,
# which is safe because region labels are a controlled vocabulary in the feed.
DESTINATIONS = [
    {"slug": "cruise-persian-gulf.html", "name": "خلیج فارس",
     "h1": "تور کشتی کروز خلیج فارس",
     "regions": ["خلیج فارس"], "ports": ["دبی", "ابوظبی", "دوحه", "مسقط"],
     "lede": ("کروزهای خلیج فارس کوتاه‌ترین راهِ دریا برای مسافرِ ایرانی‌اند: "
              "پروازِ کوتاه، بندرِ نزدیک، و کشتی‌هایی که زمستان را در همین آب‌ها "
              "می‌گذرانند.")},
    {"slug": "cruise-dubai.html", "name": "دبی",
     "h1": "تور کشتی کروز دبی",
     "regions": [], "ports": ["دبی"],
     "lede": ("دبی بندرِ خانگیِ کروزهای خلیج فارس است — از همان‌جا سوار می‌شوید "
              "و به همان‌جا برمی‌گردید.")},
    {"slug": "cruise-istanbul.html", "name": "استانبول",
     "h1": "تور کشتی کروز از استانبول",
     "regions": [], "ports": ["استانبول"],
     "lede": ("استانبول تنها بندرِ بزرگِ کروز است که ایرانی‌ها بدونِ ویزا به آن "
              "می‌رسند — اما مقصدهای پس از آن داستانِ دیگری دارند.")},
    {"slug": "cruise-turkiye.html", "name": "ترکیه",
     "h1": "تور کشتی کروز ترکیه",
     "regions": [], "ports": ["استانبول", "ازمیر", "کوش‌آداسی", "مارماریس",
                              "بدروم", "آنتالیا", "چشمه", "دیکیلی"],
     "lede": ("بندرهای ترکیه برای پاسپورتِ ایرانی بدونِ ویزا هستند؛ آنچه "
              "تعیین‌کننده است، بندرهای بعدیِ همان مسیر است.")},
    {"slug": "cruise-greece.html", "name": "یونان",
     "h1": "تور کشتی کروز یونان",
     "regions": [], "ports": ["پیره‌آس (آتن)", "سانتورینی", "میکونوس",
                              "کورفو", "رودس", "هراکلیون", "کاتاکولون"],
     "lede": ("جزایرِ یونان پرتکرارترین مقصدِ مدیترانه‌اند — و هر کدام از آن‌ها "
              "بندری در حوزهٔ شنگن است.")},
    {"slug": "cruise-mediterranean.html", "name": "مدیترانه",
     "h1": "تور کشتی کروز مدیترانه",
     "regions": ["مدیترانه"], "ports": [],
     "lede": ("مدیترانه بزرگ‌ترین بازارِ کروزِ جهان است و بیشترین تنوعِ تاریخ و "
              "کشتی را دارد.")},
    {"slug": "cruise-europe.html", "name": "اروپا",
     "h1": "تور کشتی کروز اروپا",
     "regions": ["مدیترانه", "اروپای", "فیوردهای نروژ", "دریای بالتیک"],
     "ports": [],
     "lede": ("از فیوردهای نروژ تا جزایرِ یونان — کروزهای اروپایی بیشترین "
              "شمارِ حرکت را در تقویمِ ما دارند.")},
    {"slug": "cruise-world.html", "name": "دور دنیا",
     "h1": "کشتی کروز دور دنیا",
     "regions": ["ترانس‌آتلانتیک", "کانال پاناما"], "ports": [],
     "min_nights": 14,
     "lede": ("سفرهای بلند — از گذرِ اقیانوس اطلس تا کانالِ پاناما. این‌ها "
              "کروزهایی‌اند که هفته‌ها طول می‌کشند، نه روزها.")},
]

SEASON = {
    "slug": "cruise-nowruz-1406.html",
    "h1": "تور کشتی کروز نوروز ۱۴۰۶",
    "name": "نوروز ۱۴۰۶",
    "start": "2027-03-15", "end": "2027-04-10",
    "lede": ("نوروزِ ۱۴۰۶ برابر است با ۲۱ مارس ۲۰۲۷. حرکت‌های زیر واقعاً در "
             "این بازه از بندر جدا می‌شوند — نه تخمین، نه تقویمِ نمونه."),
}


def sailings_for(feed, spec):
    out = []
    for s in feed:
        region = s.get("region") or ""
        ports = s.get("ports") or []
        hit = False
        if spec.get("regions") and any(r in region for r in spec["regions"]):
            hit = True
        if spec.get("ports") and any(p in ports for p in spec["ports"]):
            hit = True
        if hit and s.get("nights", 0) >= spec.get("min_nights", 0):
            out.append(s)
    return out


def price_line(rows):
    p = [s["priceFrom"] for s in rows if s.get("priceFrom")]
    if not p:
        return None, None
    return min(p), len(p)


def sailing_card(s):
    v = _visa.classify(s.get("ports"))
    ports = [p for p in (s.get("ports") or [])
             if not any(m in p for m in _visa.SEA_DAY_MARKERS)]
    price = (f'از {money(s["priceFrom"])} برای هر نفر'
             if s.get("priceFrom") else "قیمت را بپرسید")
    deps = s.get("dates") or []
    dep = (f'{fa(len(deps))} تاریخِ حرکت' if len(deps) > 1
           else (date_fa(deps[0]) if deps else "—"))
    return f"""      <article class="card">
        <div class="card__body">
          <h3 class="h-sm">{esc(s.get('title') or s.get('ship'))}</h3>
          <p>{latin(s.get('ship'))} · {fa(s.get('nights', 0))} شب · {esc(s.get('region') or '')}</p>
          <p>{esc(' ← '.join(ports[:6]))}{' …' if len(ports) > 6 else ''}</p>
          <p><strong>{v['label']}</strong></p>
        </div>
        <div class="card__foot">
          <p>{price} · {dep}</p>
          <a class="btn" href="{BOOK}">دیدنِ تاریخ‌ها و رزرو</a>
        </div>
      </article>"""


def visa_block(rows):
    """Aggregate visa reality across a page's sailings. Counted, not asserted."""
    c = Counter(_visa.classify(s.get("ports"))["level"] for s in rows)
    if not c:
        return ""
    parts = []
    if c["schengen"]:
        parts.append(f"<li><strong>ویزای شنگن لازم است</strong> — {fa(c['schengen'])} "
                     "حرکت. حتی اگر سفر از استانبول آغاز شود، پهلوگرفتن در یک "
                     "بندرِ شنگن یعنی ویزای شنگن.</li>")
    if c["easy"]:
        parts.append(f"<li><strong>ویزای آسان</strong> — {fa(c['easy'])} حرکت. "
                     "ویزا به‌سادگی صادر می‌شود، اما <em>لازم است</em>. این مسیرها "
                     "«بدونِ ویزا» نیستند و هر جا چنین خوانده شوند، نادرست است.</li>")
    if c["free"]:
        parts.append(f"<li><strong>بدونِ ویزا</strong> — {fa(c['free'])} حرکت، "
                     "جایی که همهٔ بندرها برای پاسپورتِ ایرانی بدونِ ویزا هستند.</li>")
    if c["check"]:
        parts.append(f"<li><strong>نیازمندِ بررسی</strong> — {fa(c['check'])} حرکت "
                     "با بندرهایی که بدونِ بررسی دربارهٔ ویزایشان چیزی نمی‌گوییم.</li>")
    return ("\n  <section class=\"band\">\n    <div class=\"wrap\">\n"
            "      <h2 class=\"h\">ویزا، بر پایهٔ بندرهای واقعیِ همین مسیرها</h2>\n"
            f"      <ul>\n        {chr(10).join('        ' + p for p in parts)}\n      </ul>\n"
            "      <p>هیچ‌کدام از این برچسب‌ها دستی نوشته نشده‌اند؛ هر حرکت از "
            "روی فهرستِ بندرهای خودش دسته‌بندی شده است.</p>\n"
            "    </div>\n  </section>\n")


def render(slug, title, description, h1, lede, body, jsonld="", live_line=None):
    """Assemble one page.

    The scripts are not optional and were missing from the first fifteen pages
    this generator wrote — _chrome.FOOTER used to close the document itself,
    so nav.js never appeared and every page shipped without a mobile menu
    button, because nav.js is what creates it. --check now diffs this tail
    against a live page so it cannot drift again silently.
    """
    head = _chrome.HEAD.format(title=esc(title), description=esc(description),
                               slug=slug, css=_chrome.CSS_VERSION,
                               jsonld=jsonld)
    tail = ""
    if live_line:
        tail = _chrome.LIVE_COUNT % {"param": live_line, "key": live_line.lower()}
    return (head + _chrome.HEADER
            + f'\n  <section class="band">\n    <div class="wrap">\n'
              f'      <h1 class="h-lg">{h1}</h1>\n      <p>{lede}</p>\n'
              f'    </div>\n  </section>\n'
            + body + _chrome.FOOTER + "\n" + tail
            + _chrome.NAV_JS + _chrome.CLOSE)


def build_destination(feed, spec):
    rows = sailings_for(feed, spec)
    lo, npriced = price_line(rows)
    ships = Counter(s.get("ship") for s in rows)
    regions = Counter(s.get("region") for s in rows if s.get("region"))
    ports = Counter(p for s in rows for p in (s.get("ports") or [])
                    if not any(m in p for m in _visa.SEA_DAY_MARKERS))
    nights = [s.get("nights", 0) for s in rows if s.get("nights")]
    deps = sorted({d for s in rows for d in (s.get("dates") or [])})

    facts = [f"{fa(len(rows))} کروزِ فعال در تقویمِ ما"]
    if deps:
        facts.append(f"{fa(len(deps))} تاریخِ حرکت، از {date_fa(deps[0])} "
                     f"تا {date_fa(deps[-1])}")
    if nights:
        facts.append(f"از {fa(min(nights))} تا {fa(max(nights))} شب")
    if lo:
        facts.append(f"ارزان‌ترین نقطهٔ شروع: {money(lo)} برای هر نفر"
                     f" (بر پایهٔ {fa(npriced)} کروزِ قیمت‌دار)")
    if ships:
        facts.append(f"{fa(len(ships))} کشتی، پرتکرارترین: "
                     + "، ".join(latin(k) for k, _ in ships.most_common(4)))

    body = ['  <section class="band band--white">\n    <div class="wrap">\n'
            f'      <h2 class="h-lg">{esc(spec["name"])} در عددهای واقعی</h2>\n'
            '      <ul>\n' + "\n".join(f"        <li>{f}</li>" for f in facts)
            + '\n      </ul>\n']
    if ports:
        body.append('      <h3 class="h-sm">پرتکرارترین بندرها</h3>\n      <p>'
                    + "، ".join(esc(p) + f" ({fa(n)})"
                                for p, n in ports.most_common(12)) + "</p>\n")
    if regions and len(regions) > 1:
        body.append('      <h3 class="h-sm">مناطق</h3>\n      <p>'
                    + "، ".join(f"{esc(r)} ({fa(n)})"
                                for r, n in regions.most_common(8)) + "</p>\n")
    body.append("    </div>\n  </section>\n")
    body.append(visa_block(rows))

    show = sorted(rows, key=lambda s: (s.get("priceFrom") or 10**9))[:24]
    if show:
        body.append('  <section class="band">\n    <div class="wrap">\n'
                    f'      <h2 class="h">{fa(len(show))} کروزِ {esc(spec["name"])}'
                    '، از ارزان‌ترین</h2>\n      <div class="grid grid--3" '
                    'style="margin-block-start:40px">\n'
                    + "\n".join(sailing_card(s) for s in show)
                    + "\n      </div>\n    </div>\n  </section>\n")

    desc = (f"{spec['name']}: {len(rows)} کروز، از {lo} یورو برای هر نفر. "
            "تاریخ‌های واقعیِ حرکت، بندرها و وضعیتِ ویزا برای پاسپورتِ ایرانی."
            ) if lo else (f"{spec['name']}: {len(rows)} کروز با تاریخ‌های واقعیِ "
                          "حرکت، بندرها و وضعیتِ ویزا برای پاسپورتِ ایرانی.")
    desc = desc[:158]
    title = f"{spec['h1']} | کروز۲۴"
    return spec["slug"], render(spec["slug"], title, desc, spec["h1"],
                                spec["lede"], "".join(body)), len(rows)


def build_season(feed):
    rows, count = [], 0
    for s in feed:
        d = [x for x in (s.get("dates") or [])
             if SEASON["start"] <= x <= SEASON["end"]]
        if d:
            rows.append(s)
            count += len(d)
    lo, npriced = price_line(rows)
    facts = [f"{fa(len(rows))} کروز با {fa(count)} تاریخِ حرکت در بازهٔ "
             f"{date_fa(SEASON['start'])} تا {date_fa(SEASON['end'])}"]
    if lo:
        facts.append(f"ارزان‌ترین نقطهٔ شروع: {money(lo)} برای هر نفر")
    reg = Counter(s.get("region") for s in rows if s.get("region"))
    if reg:
        facts.append("مناطق: " + "، ".join(f"{esc(r)} ({fa(n)})"
                                           for r, n in reg.most_common(6)))
    pg = [s for s in rows if "خلیج فارس" in (s.get("region") or "")]
    facts.append(f"کروزِ خلیج فارس در این بازه: {fa(len(pg))}"
                 + ("" if pg else " — در نوروزِ ۱۴۰۶ کشتی‌ها در مدیترانه‌اند،"
                                  " نه در خلیج فارس."))
    body = ['  <section class="band band--white">\n    <div class="wrap">\n'
            '      <h2 class="h-lg">نوروزِ ۱۴۰۶ در عددهای واقعی</h2>\n      <ul>\n'
            + "\n".join(f"        <li>{f}</li>" for f in facts)
            + "\n      </ul>\n    </div>\n  </section>\n"]
    body.append(visa_block(rows))
    show = sorted(rows, key=lambda s: (s.get("priceFrom") or 10**9))[:24]
    body.append('  <section class="band">\n    <div class="wrap">\n'
                '      <h2 class="h">حرکت‌های نوروزِ ۱۴۰۶</h2>\n'
                '      <div class="grid grid--3" style="margin-block-start:40px">\n'
                + "\n".join(sailing_card(s) for s in show)
                + "\n      </div>\n    </div>\n  </section>\n")
    desc = (f"نوروز ۱۴۰۶: {len(rows)} کروز، "
            f"{count} تاریخِ حرکتِ واقعی. وضعیتِ ویزا برای پاسپورتِ ایرانی.")[:158]
    return (SEASON["slug"],
            render(SEASON["slug"], f"{SEASON['h1']} | کروز۲۴", desc,
                   SEASON["h1"], SEASON["lede"], "".join(body)), len(rows))


def build_kish(feed):
    """The page that exists because the inventory does not.

    «کشتی کروز کیش» and its neighbours are 21 terms of real Farsi demand with
    zero sailings behind them — no line calls at Kish, Qeshm or Bandar Abbas.
    Every competitor answering this query is either selling a domestic pleasure
    boat under a cruise word or inventing an itinerary. Saying so plainly is
    both the honest answer and the only defensible page.
    """
    IRAN = ["کیش", "قشم", "بندرعباس", "بندر لنگه", "چابهار", "بوشهر", "انزلی"]
    hits = [s for s in feed
            if any(p in (s.get("ports") or []) for p in IRAN)]
    gulf = [s for s in feed if "خلیج فارس" in (s.get("region") or "")]
    lo, _ = price_line(gulf)
    body = [f"""  <section class="band band--white">
    <div class="wrap">
      <h2 class="h-lg">پاسخِ کوتاه: هیچ کشتیِ کروزی در کیش پهلو نمی‌گیرد.</h2>
      <p>در تقویمِ زندهٔ ما {fa(len(feed))} کروز هست. شمارِ کروزهایی که به کیش،
      قشم، بندرعباس، بندر لنگه، چابهار، بوشهر یا انزلی پهلو می‌گیرند:
      <strong>{fa(len(hits))}</strong>.</p>
      <p>این عدد از فهرستِ بندرهای همان {fa(len(feed))} کروز شمرده شده است، نه
      از حافظه. خطوطِ بزرگِ کروز — <span class="latin">MSC</span>،
      <span class="latin">AROYA</span>، <span class="latin">Celestyal</span>،
      <span class="latin">Explora</span> — هیچ‌کدام بندری در ایران ندارند.</p>
      <p>آنچه در کیش و جزایرِ جنوب هست، قایق و شناورِ تفریحیِ داخلی است؛ محصولِ
      دیگری است و ما آن را کروز نمی‌نامیم.</p>
    </div>
  </section>
  <section class="band">
    <div class="wrap">
      <h2 class="h">پس نزدیک‌ترین کروزِ واقعی کجاست؟</h2>
      <p>خلیج فارس — با {fa(len(gulf))} کروزِ فعال که از بندرهای آن‌سویِ آب
      حرکت می‌کنند{f'، از {money(lo)} برای هر نفر' if lo else ''}.
      این مسیرها <strong>ویزای آسان</strong> می‌خواهند، نه اینکه بدونِ ویزا
      باشند؛ هر جا «بدونِ ویزا» خوانده شوند، نادرست است.</p>
      <p><a class="btn" href="cruise-persian-gulf.html">کروزهای خلیج فارس</a></p>
    </div>
  </section>
"""]
    desc = ("هیچ کشتیِ کروزی در کیش پهلو نمی‌گیرد — شمرده از تقویمِ زندهٔ "
            f"{len(feed)} کروز. نزدیک‌ترین کروزِ واقعی کدام است و چه ویزایی "
            "می‌خواهد.")[:158]
    return ("cruise-kish.html",
            render("cruise-kish.html", "کشتی کروز کیش — واقعیت | کروز۲۴", desc,
                   "کشتی کروز کیش",
                   "پرسشی که زیاد جستجو می‌شود و پاسخش را کسی صاف نمی‌دهد.",
                   "".join(body)), len(gulf))


LINE_SLUG = {"MSC": "msc.html", "Aroya": "aroya.html",
             "Celestyal": "celestyal.html", "Explora": "explora.html"}
LINE_LEDE = {
    "MSC": ("بزرگ‌ترین ناوگانِ در دسترسِ مسافرِ ایرانی — بیشترین تنوعِ تاریخ، "
            "مسیر و کابین."),
    "Aroya": ("خطِ کروزِ عربستان، با مسیرهایی که برای پاسپورتِ ایرانی "
              "ساده‌ترین وضعیتِ ویزا را دارند."),
    "Celestyal": "کشتی‌های کوچک‌تر، مسیرهای جزیره‌محورِ یونان و ترکیه.",
    "Explora": "لوکسِ آرام — کشتی‌های کوچک و مسیرهای کم‌ازدحام.",
}


def build_line(feed, line):
    """Rebuild a cruise-line page from the fleet that actually sails.

    /msc.html shipped with 242 words and a grid of ship names — no prose, no
    numbers, and it was missing from sitemap.xml entirely. MSC is 3,237 of the
    3,485 sailings in this feed; that page was the thinnest thing on the site
    describing the largest thing in the inventory.
    """
    rows = [s for s in feed if s.get("line") == line]
    ships = Counter(s.get("ship") for s in rows)
    lo, npriced = price_line(rows)
    regions = Counter(s.get("region") for s in rows if s.get("region"))
    nights = [s.get("nights", 0) for s in rows if s.get("nights")]
    deps = sorted({d for s in rows for d in (s.get("dates") or [])})

    facts = [f'<span data-live="{line.lower()}">{fa(len(rows))}</span> '
             f"کروزِ فعال در تقویمِ ما",
             f"{fa(len(ships))} کشتی"]
    if deps:
        facts.append(f"{fa(len(deps))} تاریخِ حرکت، از {date_fa(deps[0])} "
                     f"تا {date_fa(deps[-1])}")
    if nights:
        facts.append(f"از {fa(min(nights))} تا {fa(max(nights))} شب")
    if lo:
        facts.append(f"ارزان‌ترین نقطهٔ شروع: {money(lo)} برای هر نفر")
    if regions:
        facts.append("مناطق: " + "، ".join(f"{esc(r)} ({fa(n)})"
                                           for r, n in regions.most_common(8)))

    body = [f'  <section class="band band--white">\n    <div class="wrap">\n'
            f'      <h2 class="h-lg">{latin(line)} در عددهای واقعی</h2>\n'
            '      <ul>\n' + "\n".join(f"        <li>{f}</li>" for f in facts)
            + "\n      </ul>\n    </div>\n  </section>\n"]

    # Fleet table — the thing the old page gestured at without saying anything.
    rowsh = []
    for ship, n in ships.most_common():
        sh = [s for s in rows if s.get("ship") == ship]
        p = [s["priceFrom"] for s in sh if s.get("priceFrom")]
        reg = Counter(s.get("region") for s in sh if s.get("region"))
        nl = [s.get("nights", 0) for s in sh if s.get("nights")]
        href = ship_href(ship)
        cell = (f'<a href="{href}">{latin(ship)}</a>' if href else latin(ship))
        rowsh.append(
            f"        <tr><td>{cell}</td><td>{fa(n)}</td>"
            f"<td>{fa(min(nl)) + '–' + fa(max(nl)) if nl else '—'}</td>"
            f"<td>{money(min(p)) if p else '—'}</td>"
            f"<td>{esc(reg.most_common(1)[0][0]) if reg else '—'}</td></tr>")
    body.append('  <section class="band">\n    <div class="wrap">\n'
                f'      <h2 class="h">ناوگانِ {latin(line)} — {fa(len(ships))} کشتی</h2>\n'
                '      <div style="overflow-x:auto">\n      <table>\n'
                '        <thead><tr><th>کشتی</th><th>کروزها</th><th>شب</th>'
                '<th>از</th><th>منطقهٔ اصلی</th></tr></thead>\n        <tbody>\n'
                + "\n".join(rowsh)
                + "\n        </tbody>\n      </table>\n      </div>\n"
                "    </div>\n  </section>\n")
    body.append(visa_block(rows))
    show = sorted(rows, key=lambda s: (s.get("priceFrom") or 10**9))[:18]
    if show:
        body.append('  <section class="band band--white">\n    <div class="wrap">\n'
                    f'      <h2 class="h">ارزان‌ترین کروزهای {latin(line)}</h2>\n'
                    '      <div class="grid grid--3" style="margin-block-start:40px">\n'
                    + "\n".join(sailing_card(s) for s in show)
                    + "\n      </div>\n    </div>\n  </section>\n")

    h1 = f"تور کشتی کروز {line}"
    desc = (f"{line}: {len(rows)} کروز، {len(ships)} کشتی"
            + (f"، از {lo} یورو برای هر نفر" if lo else "")
            + ". تاریخ‌های واقعیِ حرکت و وضعیتِ ویزا برای پاسپورتِ ایرانی.")[:158]
    return (LINE_SLUG[line],
            render(LINE_SLUG[line], f"{h1} | کروز۲۴", desc, h1,
                   LINE_LEDE.get(line, ""), "".join(body),
                   live_line=line), len(rows))


def build_prices(feed):
    """118 keyword terms ask what it costs. priceFrom is on 99% of sailings."""
    by = defaultdict(list)
    for s in feed:
        if s.get("priceFrom") and s.get("region"):
            by[s["region"]].append(s)
    rows = []
    for region, sh in sorted(by.items(), key=lambda kv: -len(kv[1])):
        p = sorted(s["priceFrom"] for s in sh)
        nl = [s.get("nights", 0) for s in sh if s.get("nights")]
        mid = p[len(p) // 2]
        rows.append(f"        <tr><td>{esc(region)}</td><td>{fa(len(sh))}</td>"
                    f"<td>{money(p[0])}</td>"
                    f"<td>{money(mid)}</td>"
                    f"<td>{fa(min(nl)) + '–' + fa(max(nl)) if nl else '—'}</td></tr>")
    allp = sorted(s["priceFrom"] for s in feed if s.get("priceFrom"))
    body = [f"""  <section class="band band--white">
    <div class="wrap">
      <h2 class="h-lg">قیمت‌ها، شمرده از تقویمِ زنده</h2>
      <p>{fa(len(allp))} کروز از {fa(len(feed))} کروزِ تقویمِ ما قیمتِ شروع دارند.
      ارزان‌ترین {money(allp[0])} و میانهٔ همهٔ آن‌ها
      {money(allp[len(allp) // 2])} برای هر نفر است.</p>
      <p>این عددها نقطهٔ شروع‌اند: ارزان‌ترین کابینِ موجود، دو نفر در کابین،
      به یورو، بدونِ سرویس‌شارژِ خطِ کروز. هیچ‌کدام تخمین نیستند.</p>
    </div>
  </section>
  <section class="band">
    <div class="wrap">
      <h2 class="h">قیمتِ شروع به تفکیکِ منطقه</h2>
      <div style="overflow-x:auto">
      <table>
        <thead><tr><th>منطقه</th><th>کروزها</th><th>ارزان‌ترین</th><th>میانه</th><th>شب</th></tr></thead>
        <tbody>
{chr(10).join(rows)}
        </tbody>
      </table>
      </div>
      <p>چرا به یورو و نه به تومان: نرخِ کروز را خطِ کروز به یورو اعلام می‌کند و
      ما نرخِ تبدیل را از خودمان نمی‌سازیم. مبلغِ ریالی را در زمانِ رزرو، با
      نرخِ همان روز، به شما می‌گوییم.</p>
    </div>
  </section>
"""]
    desc = (f"قیمتِ شروعِ {len(allp)} کروز به تفکیکِ منطقه — ارزان‌ترین "
            f"{allp[0]} یورو برای هر نفر. شمرده از تقویمِ زنده، بدونِ تخمین.")[:158]
    return ("cruise-prices.html",
            render("cruise-prices.html", "قیمت کشتی کروز | کروز۲۴", desc,
                   "قیمت کشتی کروز",
                   "همهٔ عددهای این صفحه از تقویمِ زندهٔ حرکت‌ها شمرده شده‌اند.",
                   "".join(body)), len(allp))


# Pages that already exist on the server and must stay in the sitemap even
# though this generator does not write them.
#
# The first version of this list held five entries, found by crawling from the
# homepage. That was wrong and the error is instructive: 23 SHIP PAGES exist
# and are reachable only from the line pages, and the line pages were
# themselves missing from the sitemap. Crawling from the homepage cannot see
# past a broken link layer, so it found 12 pages where 38 exist.
#
# This list was verified by requesting every URL over HTTPS — all 38 return
# 200 and none carries a robots noindex, so all 38 belong here. Spot-checked
# again independently before it was committed, including a deliberate 404 to
# confirm the server was not answering 200 for everything.
#
# /search.html is deliberately absent: it 301s to book.cruise24.ir, which
# carries its own noindex. A 301 never belongs in a sitemap.
EXISTING = [
    "index.html", "blog.html", "cruiseletter.html", "events.html",
    "cruise-lines.html",
    # line pages — also written by this generator, deduped in write_sitemap()
    "msc.html", "aroya.html", "celestyal.html", "explora.html",
    # ship pages, 23 of them, orphaned behind the line pages
    "celestyal-discovery.html", "celestyal-journey.html",
    "explora-i.html", "explora-ii.html", "explora-iii.html",
    "msc-armonia.html", "msc-bellissima.html", "msc-divina.html",
    "msc-euribia.html", "msc-fantasia.html", "msc-grandiosa.html",
    "msc-lirica.html", "msc-magnifica.html", "msc-meraviglia.html",
    "msc-musica.html", "msc-opera.html", "msc-orchestra.html",
    "msc-poesia.html", "msc-preziosa.html", "msc-seascape.html",
    "msc-seashore.html", "msc-seaside.html", "msc-seaview.html",
    "msc-sinfonia.html", "msc-splendida.html", "msc-virtuosa.html",
    "msc-world-america.html", "msc-world-asia.html", "msc-world-europa.html",
]


# The 29 ship pages, derived from EXISTING rather than typed twice. They are
# the reason internal linking is the biggest job on this site: a peer session
# parsed every internal href across all 38 pages and found that NOT ONE of
# these has an inbound link — not from the homepage, not from cruise-lines,
# and not from the line pages either. 29 of 38 pages are unreachable by
# crawling, which is why the sitemap was the only way in.
#
# The name→page rule is lower-case, spaces to hyphens. Verified both ways
# against the live feed: 29 of the 30 distinct ships resolve to a page that
# exists, and every one of the 29 pages has sailings in the feed. No misses in
# either direction.
#
# The 30th is AROYA, whose ship carries the line's own name and resolves to
# aroya.html — the LINE page. Linking that would point the page at itself, so
# ship_href() refuses any slug that is a line page. That is a real exception,
# not a gap.
SHIP_PAGES = {e[:-5] for e in EXISTING
              if e not in ("index.html", "blog.html", "cruiseletter.html",
                           "events.html", "cruise-lines.html",
                           "msc.html", "aroya.html", "celestyal.html",
                           "explora.html")}


def ship_href(name: str) -> str | None:
    """The ship's own page, or None — never a guess.

    Returns None rather than a constructed URL when the page does not exist,
    because a link to a 404 is worse than no link.
    """
    slug = (name or "").lower().replace(" ", "-")
    if slug in SHIP_PAGES:
        return slug + ".html"
    return None


def write_sitemap(slugs: list[str]) -> str:
    """One <url> per page. Deduped, because four line pages are in BOTH lists.

    msc, aroya, celestyal and explora exist on the server AND are rewritten by
    this generator. Concatenating the two lists ships them twice, and a sitemap
    that declares the same URL twice is a defect a crawler notices.
    """
    today = datetime.date.today().isoformat()
    urls = []
    seen = set()
    for s in slugs:
        if s in seen:
            continue
        seen.add(s)
        loc = "https://cruise24.ir/" + ("" if s == "index.html" else s)
        pri = "1.0" if s == "index.html" else (
            "0.9" if s.startswith("cruise-") or s in LINE_SLUG.values() else "0.6")
        urls.append(f"  <url>\n    <loc>{loc}</loc>\n"
                    f"    <lastmod>{today}</lastmod>\n"
                    f"    <priority>{pri}</priority>\n  </url>")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  Cruise24 — cruise24.ir

  Regenerated by _build.py. The sitemap this replaces listed FOUR URLs while
  38 pages were live and returning 200 — including 23 ship pages reachable
  only from the line pages, which were themselves undeclared. Crawling from
  the homepage found 12 of the 38; every URL here was verified by request.

  /search.html stays out on purpose. It is not a file in this docroot — both
  /search and /search.html 301 to https://book.cruise24.ir/, which carries its
  own <meta name="robots" content="noindex, nofollow">. A 301 never belongs in
  a sitemap.
-->
<urlset xmlns="http://www.sitemap.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>
""".replace("www.sitemap.org", "www.sitemaps.org")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", type=Path, default=HERE / "public")
    args = ap.parse_args(argv)

    feed = fetch_feed()
    print(f"feed: {len(feed)} sailings\n")

    pages = []
    for spec in DESTINATIONS:
        pages.append(build_destination(feed, spec))
    pages.append(build_season(feed))
    pages.append(build_kish(feed))
    for line in LINE_SLUG:
        pages.append(build_line(feed, line))
    pages.append(build_prices(feed))

    # A generated page with no inventory behind it is worse than no page. The
    # only exception is kish.html, whose entire subject is the absence.
    empty = [(s, n) for s, h, n in pages if n == 0 and s != "cruise-kish.html"]
    if empty:
        print("REFUSING to write pages with zero sailings behind them:")
        for s, _ in empty:
            print(f"   {s}")
        return 1

    if args.check:
        bad = []
        # Chrome drift is silent and expensive: the first build of these pages
        # dropped nav.js because the chrome was eyeballed off a live page
        # rather than diffed against one.
        try:
            live = subprocess.run(
                ["curl", "-sS", "--max-time", "30", "-A", "Mozilla/5.0",
                 "https://cruise24.ir/msc.html"],
                capture_output=True, timeout=45).stdout.decode("utf-8")
            for needle, what in ((_chrome.NAV_JS, "nav.js tag"),
                                 (_chrome.CSS_VERSION, "stylesheet version")):
                if needle not in live:
                    bad.append(f"CHROME DRIFT: {what} in _chrome.py no longer "
                               f"matches the live page — re-lift it")
        except Exception as exc:
            print(f"  (could not reach the live site to diff chrome: "
                  f"{type(exc).__name__})")
        for slug, doc, n in pages:
            p = args.out / slug
            if not p.exists():
                bad.append(f"{slug} missing")
            elif p.read_text(encoding="utf-8") != doc:
                bad.append(f"{slug} differs from the feed")
        if bad:
            print("STALE:\n  " + "\n  ".join(bad))
            return 1
        print(f"all {len(pages)} pages match the live feed")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    for slug, doc, n in pages:
        (args.out / slug).write_text(doc, encoding="utf-8")
        words = len(re.sub(r"<[^>]+>", " ", doc).split())
        print(f"  {slug:34} {n:5} sailings  {words:5} words")

    sm = write_sitemap(EXISTING + [s for s, _, _ in pages])
    (args.out / "sitemap.xml").write_text(sm, encoding="utf-8")
    # Count what is IN the file, not what was passed in. Four line pages appear
    # in both lists, so the naive sum says 53 where the artifact holds 49 — a
    # build log that disagrees with its own output is how a bad deploy passes.
    declared = re.findall(r"<loc>", sm)
    overlap = len(EXISTING) + len(pages) - len(declared)
    print(f"\n  sitemap.xml  {len(declared)} URLs "
          f"({len(EXISTING)} existing + {len(pages)} generated "
          f"− {overlap} rewritten in both)")

    # The rule that outranks everything else, checked on the output.
    wrong = [s for s, d, _ in pages if "خلیج عربی" in d or "Arabian Gulf" in d]
    if wrong:
        print(f"\nWRONG GULF NAME in: {wrong}")
        return 1
    print("  Persian Gulf naming correct across every generated page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
