"""
Firecrawl: read a page the way a browser renders it.

Architecture credit: Albaloo Studio — albaloostudio.com

Two places in the pipeline see only an empty JavaScript shell where a reader
sees a full page: the base44 sites (cruisebaz.com, ambientetravel.com) and
competitors built the same way. merge-watch could not find a cruisebaz article's
title on its live page, so the Broadcaster never got the text a human approved;
Agent 8 counted those competitors' pages as near-empty. Firecrawl renders them.

Off unless FIRECRAWL_API_KEY is set (keyless use is refused from datacenter and
VPN addresses — measured 1 Nov 2026). Never raises: a failed render is "no
better text", never a failed run. FIRECRAWL_MAX_PAGES (default 30) caps credits
per process, because every page costs one.
"""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)
API = "https://api.firecrawl.dev/v2/scrape"
_used = 0


def enabled() -> bool:
    return bool(os.environ.get("FIRECRAWL_API_KEY", "").strip())


def pages_used() -> int:
    return _used


def rendered_html(url: str, *, main_only: bool = True, timeout: int = 90) -> str | None:
    """The page's HTML after JavaScript ran, or None (off, over budget, or failed)."""
    global _used
    if not enabled():
        return None
    cap = int(os.environ.get("FIRECRAWL_MAX_PAGES", "30") or 30)
    if _used >= cap:
        log.info("firecrawl: page cap %d reached — %s read without rendering", cap, url)
        return None
    _used += 1
    try:
        r = requests.post(API, timeout=timeout, json={
            "url": url, "formats": ["html"], "onlyMainContent": main_only},
            headers={"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY'].strip()}"})
        d = r.json() if r.content else {}
    except (requests.RequestException, ValueError) as exc:
        log.warning("firecrawl: %s failed: %s", url, str(exc)[:120])
        return None
    if r.status_code != 200 or not d.get("success"):
        log.warning("firecrawl: %s → HTTP %s %s", url, r.status_code, str(d.get("error") or "")[:160])
        return None
    html = ((d.get("data") or {}).get("html") or "").strip()
    return html or None


if __name__ == "__main__":
    # Key check: `python3 firecrawl_client.py URL` renders one page (one credit)
    # and prints only the outcome and the size, never the page or the key.
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not enabled():
        print("FIRECRAWL_API_KEY is not set — nothing to test")
        sys.exit(2)
    out = rendered_html(sys.argv[1], main_only=False)
    print(f"rendered {len(out)} chars" if out else "render FAILED — see the warning above")
    sys.exit(0 if out else 1)
