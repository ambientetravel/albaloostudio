# -*- coding: utf-8 -*-
"""Visa truth for an Iranian passport, applied per sailing from its real ports.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

This is the rule that outranks everything else on these properties, and it is
the one a generated page is most likely to get wrong at scale — a template that
says «بدون ویزا» across two hundred pages is two hundred false statements.

THE RULE, verbatim from the house standard:

  * Only AROYA's Türkiye+Egypt routes and Seychelles are TRULY visa-free.
  * Persian Gulf and Dubai are EASY VISA — not no-visa. Saying otherwise is
    the specific error competitors make and the reason to be trusted instead.
  * ANY Greek, Italian, Spanish or French port makes the sailing Schengen,
    even one departing Istanbul. One port is enough.

Port matching is by explicit list, never substring. «رم» sits inside
«مارماریس» and «کن» inside «اسکندریه» — substring matching on Persian port
names has produced wrong visa labels before and is banned here.
"""

# Schengen ports as the feed spells them. Extend by adding, never by loosening
# the match. A port absent from this list is treated as NOT Schengen, so a
# missing entry understates rather than inventing a requirement — but it also
# means new ports must be added deliberately.
SCHENGEN_PORTS = {
    # Italy
    "چیویتاوکیا (رم)", "چیویتاوکیا", "ناپل", "جنوا", "لیورنو", "پالرمو",
    "مسینا", "باری", "ونیز", "تریسته", "لا اسپتزیا", "کالیاری", "سالرنو",
    "کاتانیا", "آنکونا", "ساوونا",
    # Spain
    "بارسلون", "بارسلونا", "والنسیا", "پالما د مایورکا", "ایبیتزا",
    "تاراگونا", "مالاگا", "کادیز", "آلیکانته", "لاس پالماس", "تنریفه",
    "سانتا کروز د تنریفه", "بیلبائو", "ویگو", "لا کرونیا",
    # France
    "مارسی", "کن", "نیس", "تولون", "اجاکسیو", "بستیا", "لو هاور", "شربور",
    # Greece
    "پیره‌آس (آتن)", "پیره‌آس", "آتن", "سانتورینی", "میکونوس", "کورفو",
    "رودس", "هراکلیون", "کاتاکولون", "کفالونیا", "زاکینتوس", "پاتموس",
    "سیراکوز", "ولوس", "تسالونیکی",
    # Portugal / Malta / other Schengen
    "لیسبون", "پورتو", "فونشال", "والتا", "دوبروونیک", "کوپر", "لیوبلیانا",
    "روتردام", "آمستردام", "هامبورگ", "کیل", "وارنمونده", "کپنهاگ",
    "استکهلم", "هلسینکی", "تالین", "ریگا", "اسلو", "برگن", "گایرانگر",
    "استاوانگر", "تروسو", "هونینگسواگ", "فلام",
}

# Truly visa-free for an Iranian passport, per the house rule.
VISA_FREE_PORTS = {
    # Türkiye
    "استانبول", "ازمیر", "کوش‌آداسی", "کوش اداسی", "مارماریس", "آنتالیا",
    "بدروم", "چشمه", "دیکیلی", "سینوپ", "ترابزون",
    # Egypt (AROYA routes)
    "اسکندریه", "پورت سعید", "سفاگا", "شرم الشیخ", "العین السخنه",
    # Seychelles
    "ماهه", "ویکتوریا (سیشل)", "پرالین",
}

# Easy visa — obtainable, but a visa. NEVER labelled visa-free.
EASY_VISA_PORTS = {
    "دبی", "ابوظبی", "شارجه", "راس الخیمه", "دوحه", "مسقط", "صلاله",
    "بحرین", "منامه", "جده", "ینبع", "الدمام", "کویت",
}

SEA_DAY_MARKERS = ("روز دریا", "در دریا", "روز در دریا")


def classify(ports: list[str]) -> dict:
    """Return the visa requirement for one sailing, from its real port list."""
    real = [p for p in (ports or [])
            if p and not any(m in p for m in SEA_DAY_MARKERS)]
    schengen = sorted({p for p in real if p in SCHENGEN_PORTS})
    easy = sorted({p for p in real if p in EASY_VISA_PORTS})
    free = sorted({p for p in real if p in VISA_FREE_PORTS})
    unknown = [p for p in real if p not in SCHENGEN_PORTS
               and p not in EASY_VISA_PORTS and p not in VISA_FREE_PORTS]

    if schengen:
        return {"level": "schengen",
                "label": "ویزای شنگن لازم است",
                "why": ("این مسیر دستِ‌کم به یک بندرِ حوزهٔ شنگن پهلو می‌گیرد"
                        f" ({'، '.join(schengen[:3])})"
                        "؛ حتی اگر سفر از استانبول آغاز شود، ویزای شنگن لازم است."),
                "ports": schengen, "unknown": unknown}
    if easy:
        return {"level": "easy",
                "label": "ویزای آسان — بدونِ ویزا نیست",
                "why": ("ویزای این مسیر برای پاسپورتِ ایرانی به‌سادگی صادر"
                        f" می‌شود ({'، '.join(easy[:3])})، اما ویزا لازم است."
                        " هر تبلیغی که این مسیر را «بدونِ ویزا» بخواند، درست"
                        " نیست."),
                "ports": easy, "unknown": unknown}
    if free and not unknown:
        return {"level": "free",
                "label": "بدونِ ویزا",
                "why": ("همهٔ بندرهای این مسیر برای پاسپورتِ ایرانی بدونِ ویزا"
                        f" هستند ({'، '.join(free[:3])})."),
                "ports": free, "unknown": unknown}
    return {"level": "check",
            "label": "نیازمندِ بررسیِ ویزا",
            "why": ("بندرهای این مسیر در فهرستِ تأییدشدهٔ ما نیستند و بدونِ"
                    " بررسی چیزی دربارهٔ ویزای آن نمی‌گوییم."),
            "ports": [], "unknown": unknown}
