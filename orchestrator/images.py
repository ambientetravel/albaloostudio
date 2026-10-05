"""
A real, freely licensed photo for every article — with its real credit.

Until 5 Oct 2026 the writer sourced no imagery: boutimar.com and cruise24.ir
articles showed only the site's default share image, boutimar.ir's `image` was
left "" for a reviewer to fill, and Explore Orient fell back to a stock hero.

Source: Wikimedia Commons. No key, and every file carries machine-readable
licence metadata (LicenseShortName, Artist), so the credit printed under the
photo is COPIED from the file's own record — never composed. CLAUDE.md: "Never
invent … a photo credit. If the data is not there, say it is not there." A
file without an artist (unless public domain) or under a licence that forbids
commercial use or modification is skipped, and an article with no acceptable
match simply has no photo.

The file is downloaded and committed into the site's own repo (self-hosted):
upload.wikimedia.org is not reliably reachable from Iran, and a hotlink can
change or vanish under the page.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import requests

import config

log = logging.getLogger("images")

COMMONS = "https://commons.wikimedia.org/w/api.php"
# Licences that allow commercial reuse AND modification (resizing). NC/ND excluded.
_OK_LICENCE = re.compile(r"^(cc0|public domain|pd[\s-]|pd$|cc[ -]by(-sa)?[ -]\d(\.\d)?)", re.I)
_BAD_TITLE = re.compile(r"\b(map|logo|flag|coat of arms|diagram|chart|icon|seal|emblem|plan)\b", re.I)
MAX_BYTES = 4_000_000
# Words that say WHAT kind of scene, not WHERE — a photo must match a place word,
# not just these. (5 Oct dry run: "Staying with Nomads" for a Kyrgyzstan piece
# returned a Tibet camp; "Iran Oil Show" returned Safavid oil paintings.)
_GENERIC = set("""ski resort resorts cruise cruises port terminal island islands mount mountain castle
travel tour tours guide trip route routes camp camps camping city town village old new great
temple temples fire festival show fair exhibition market bazaar hotel boutique ship ships
desert lake river valley coast beach sea gulf trail road the and with from view night day""".split())


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return " ".join(s.replace("&amp;", "&").replace("&#039;", "'").split())


# Credit text comes from Commons metadata, which ANYONE can edit. It ends up in
# Markdown (raw HTML allowed), JSON data files and JSON-LD on our sites, so a
# credit like '</script><script>…' would be an outside-reachable injection
# (raised by the cruise24.ir session, 6 Oct). Keep letters, digits, spaces and
# plain punctuation only — no angle brackets, quotes-as-markup, Markdown syntax.
_SAFE = re.compile(r"[^\w\s.,'’()\-/:&+@]", re.UNICODE)


def clean(text: str, limit: int = 200) -> str:
    return " ".join(_SAFE.sub(" ", str(text or "")).split())[:limit]


def licence_ok(name: str) -> bool:
    n = (name or "").strip()
    return bool(n) and bool(_OK_LICENCE.search(n)) and not re.search(r"\b(nc|nd)\b", n, re.I)


def place_words(query: str) -> set[str]:
    """The specific words in a query (Dizin, Damavand, Galataport) a photo must name."""
    return {w for w in re.findall(r"[A-Za-zÀ-ÿ'-]{4,}", (query or "").lower()) if w not in _GENERIC}


def _relevant(title: str, meta: dict, words: set[str]) -> bool:
    if not words:
        return True
    hay = " ".join([title] + [_strip_html((meta.get(k) or {}).get("value", ""))
                              for k in ("ImageDescription", "ObjectName", "Categories")]).lower()
    return any(w in hay for w in words)


def _avoided(hay: str, avoid) -> bool:
    """Whole-word match, so 'Viking' rejects a Viking ship but 'AIDA' never rejects 'Aidan'."""
    return any(re.search(rf"(?<!\w){re.escape(a.lower())}(?!\w)", hay) for a in avoid if a)


def pick(pages: list[dict[str, Any]], min_width: int = 1200, query: str = "",
         avoid: list[str] | tuple = ()) -> dict[str, Any] | None:
    """First search result that is a real photo, big enough, freely licensed, credited,
    and that actually names the place the query is about."""
    words = place_words(query)
    for p in sorted(pages, key=lambda x: x.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        title = str(p.get("title", ""))
        if ii.get("mime") not in ("image/jpeg", "image/png") or _BAD_TITLE.search(title):
            continue
        if int(ii.get("width") or 0) < min_width:
            continue
        if not _relevant(title, meta, words):
            continue
        # Never another company's branded ship on a site that doesn't sell it
        # (cruise24.ir PR #8: Royal Caribbean, Cunard, Holland America; boutimar.ir: Viking).
        hay = " ".join([title] + [_strip_html((meta.get(k) or {}).get("value", ""))
                                  for k in ("ImageDescription", "ObjectName", "Categories")]).lower()
        if _avoided(hay, avoid):
            continue
        # A travel page wants a current scene: skip archive photos (NARA 1970s
        # terminals, 6 Oct) when the file states when it was taken.
        taken = re.search(r"\b(1[89]\d\d|20\d\d)\b", _strip_html((meta.get("DateTimeOriginal") or {}).get("value", "")))
        if taken and int(taken.group(1)) < 2000:
            continue
        lic = _strip_html((meta.get("LicenseShortName") or {}).get("value", ""))
        if not licence_ok(lic):
            continue
        artist = _strip_html((meta.get("Artist") or {}).get("value", ""))
        public_domain = lic.lower().startswith(("public domain", "pd", "cc0"))
        if not artist and not public_domain:
            continue                        # no named creator → no honest credit
        url = ii.get("thumburl") or ii.get("url")
        if not url:
            continue
        return {
            "download_url": url,
            "source_page": ii.get("descriptionurl", ""),
            "title": clean(re.sub(r"^File:|\.\w+$", "", title), 120),
            "creator": clean(artist, 120) or "unknown (public domain)",
            "licence": clean(lic, 40),
            "licence_url": _strip_html((meta.get("LicenseUrl") or {}).get("value", "")),
            "ext": ".png" if ii.get("mime") == "image/png" else ".jpg",
            # What the FILE says it shows — the only honest source for alt text.
            "description": clean(_strip_html((meta.get("ImageDescription") or {}).get("value", "")), 400),
        }
    return None


def find_image(query: str, *, width: int = 1600, avoid: list[str] | tuple = ()) -> dict[str, Any] | None:
    """Search Commons for `query`; if nothing acceptable, retry with the first 3, then
    2 words ('Galataport Istanbul cruise terminal' → 'Galataport Istanbul'). The place
    check always uses the FULL query's place words, so a shorter search can't drift."""
    q = " ".join((query or "").split())
    if len(q) < 3:
        return None
    words = q.split()
    tries = [q] + [" ".join(words[:n]) for n in (3, 2) if len(words) > n]
    for attempt in tries:
        got = _search(attempt, q, width, avoid)
        if got:
            return got
    return None


def _search(q_search: str, q_place: str, width: int, avoid=()) -> dict[str, Any] | None:
    q = q_search
    try:
        r = requests.get(COMMONS, timeout=20, headers={"User-Agent": config.USER_AGENT}, params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f"{q} filetype:bitmap", "gsrlimit": 15, "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "iiurlwidth": width, "iiextmetadatalanguage": "en"})
        r.raise_for_status()
        pages = list(((r.json().get("query") or {}).get("pages") or {}).values())
    except (requests.RequestException, ValueError) as exc:
        log.warning("image search failed for %r: %s", q, exc)
        return None
    return pick(pages, query=q_place, avoid=avoid)


def fetch(img: dict[str, Any]) -> bytes | None:
    try:
        r = requests.get(img["download_url"], timeout=30, headers={"User-Agent": config.USER_AGENT})
        r.raise_for_status()
        data = r.content
    except requests.RequestException as exc:
        log.warning("image download failed: %s", exc)
        return None
    if not data or len(data) > MAX_BYTES:
        return None
    return data


def credit_line(img: dict[str, Any], language: str) -> str:
    """The caption, built only from the file's own metadata."""
    if str(language).lower().startswith("fa"):
        return f"عکس: {img['creator']} — {img['licence']}، از ویکی‌مدیا کامنز ({img['source_page']})"
    return f"Photo: {img['creator']}, {img['licence']}, via [Wikimedia Commons]({img['source_page']})"


def describe(img: dict[str, Any], language: str) -> str:
    """Alt text built ONLY from what the chosen file says it shows (its Commons
    title and description), in the article's language. Written from the article
    instead, it described the photo the article wanted — 'a balcony cabin with a
    sea view' for a hull seen across Hamburg harbour (cruise24.ir PR #8)."""
    facts = f"{img.get('title', '')}. {img.get('description', '')}".strip(" .")
    if not str(language).lower().startswith("fa"):
        return clean(img.get("title", ""), 160)
    try:
        import llm
        out, _ = llm.complete_json(
            "You translate image captions faithfully. Never add anything not stated.",
            f"Image file title and description (from Wikimedia Commons): {facts}\n\nWrite ONE short Farsi "
            f"sentence saying only what this states the photo shows. Do not add people, actions, rooms or "
            f"places that are not stated. Return JSON {{\"alt\": \"...\"}}.",
            {"type": "object", "additionalProperties": False,
             "properties": {"alt": {"type": "string"}}, "required": ["alt"]},
            max_tokens=150, purpose="image alt")
        return clean(out.get("alt", ""), 160)
    except Exception:  # noqa: BLE001 — fall back to the file's own title
        return clean(img.get("title", ""), 160)


def attach(draft: dict[str, Any], *, language: str = "en", avoid: list[str] | tuple = ()) -> dict[str, Any] | None:
    """Find and download a photo for this draft. Fail-soft: None means no photo."""
    img = find_image(str(draft.get("image_query") or ""), avoid=avoid)
    if not img:
        return None
    data = fetch(img)
    if not data:
        return None
    img["bytes"] = data
    img["alt"] = describe(img, language)
    return img
