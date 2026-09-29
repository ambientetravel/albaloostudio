#!/usr/bin/env python3
"""
IndexNow — tell Bing, Yandex, Seznam and Naver about a new page the minute it
is live, instead of waiting days for a crawl. (Google does not use IndexNow;
it has its own queue — Search Console covers that side.)

Called by merge-watch after it verifies articles are LIVE: only pages the
server actually serves are submitted, never a draft or a merged-not-deployed
URL. Per site the key lives in sites.yml `indexnow_key`, and the protocol
needs the same key served at https://<domain>/<key>.txt. That file is checked
by CONTENT, not status: base44 sites answer 200 for any path (their app shell),
so a 200 alone proves nothing.

    python3 tools/indexnow_ping.py --promoted promoted --previous promoted_prev
    python3 tools/indexnow_ping.py --url https://exploreorient.com/journal/x/   # one-off
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

ENDPOINT = "https://api.indexnow.org/indexnow"


def _curl(args: list[str]) -> tuple[int, str]:
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "30", "-w", "\n%{http_code}", *args],
                       capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    return int(code or 0), body


def key_hosted(domain: str, key: str) -> bool:
    code, body = _curl([f"https://{domain}/{key}.txt"])
    return code == 200 and body.strip() == key


def submit(domain: str, key: str, urls: list[str]) -> tuple[int, str]:
    payload = {"host": domain, "key": key, "keyLocation": f"https://{domain}/{key}.txt", "urlList": urls}
    return _curl(["-X", "POST", "-H", "Content-Type: application/json; charset=utf-8",
                  "-d", json.dumps(payload), ENDPOINT])


def new_live_urls(promoted: Path, previous: Path | None) -> list[str]:
    seen = {p.name for p in previous.glob("*.json")} if previous and previous.is_dir() else set()
    out = []
    for p in sorted(promoted.glob("*.json")) if promoted.is_dir() else []:
        if p.name in seen:
            continue
        try:
            live = ((json.loads(p.read_text(encoding="utf-8")).get("publication") or {}).get("live_url"))
        except ValueError:
            continue
        if live:
            out.append(live)
    return out


def ping(urls: list[str], sites: dict) -> list[str]:
    log, by_host = [], {}
    for u in urls:
        by_host.setdefault(urlparse(u).netloc.removeprefix("www."), []).append(u)
    for host, us in by_host.items():
        site = sites.get(host)
        key = (getattr(site, "indexnow_key", "") or "") if site else ""
        if not key:
            log.append(f"skip  {host}: no indexnow_key in sites.yml ({len(us)} URL)")
            continue
        if not key_hosted(host, key):
            log.append(f"skip  {host}: https://{host}/{key}.txt is not served with the key — host it first")
            continue
        code, body = submit(host, key, us)
        # 200 = accepted, 202 = accepted, key validation pending
        log.append(f"{'sent ' if code in (200, 202) else 'FAIL '} {host}: {len(us)} URL → HTTP {code}"
                   + ("" if code in (200, 202) else f" {body[:120]}"))
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--promoted", type=Path)
    ap.add_argument("--previous", type=Path)
    ap.add_argument("--url", action="append", default=[])
    a = ap.parse_args(argv)
    urls = list(a.url) + (new_live_urls(a.promoted, a.previous) if a.promoted else [])
    if not urls:
        print("IndexNow: no newly live URLs this run")
        return 0
    sites = {s.domain: s for s in config.load_sites(include_hold=True)}
    print("\n".join(["IndexNow:"] + ping(urls, sites)))
    return 0          # a ping that fails is a note; it never fails merge-watch


if __name__ == "__main__":
    raise SystemExit(main())
