#!/usr/bin/env python3
"""
Rename percent-encoded Persian term slugs to ASCII, so their archives resolve.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHAT THIS FIXES
───────────────
Measured on cruiseshop.ir and dmciran.ir, 13 Aug 2026:

    Farsi PAGE      dmciran.ir/%d8%ae%d8%a7%d9%86%d9%87/     200
    ASCII CATEGORY  dmciran.ir/category/hiking/              200   (7 of 7)
    Farsi CATEGORY  dmciran.ir/category/%d8%af%d8%b3...      404
    Farsi CATEGORY  cruiseshop.ir/archives/category/%d8...   404

    (The two sites use different category bases — /category/ and
    /archives/category/. This script reads each term's own link rather than
    assuming one.)

Persian URLs are not broken and the stored slug is not corrupt — WordPress
percent-encodes non-ASCII slugs by design, and that stored form is what
resolves for pages. It is the TAXONOMY rewrite that fails to match one. So the
fix is not a server change and not a re-import: give the term an ASCII slug and
its archive resolves. The Persian NAME is untouched, so nothing a reader sees
changes.

Deleting the term was the first instinct and does not work on cruiseshop.ir:
it is the site's only category, which makes it the default, and WordPress
refuses to delete the default because posts would have nowhere to go.

RUNNING IT
──────────
Credentials come from your environment and are never printed, logged, or
written to the backup file. Create an Application Password per site in
WordPress (Users → Profile → Application Passwords) — not your login password,
because an application password is revocable on its own and is scoped to the
REST API.

    export WP_CRUISESHOP_USER='alireza'
    export WP_CRUISESHOP_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx'
    export WP_DMCIRAN_USER='alireza'
    export WP_DMCIRAN_APP_PASSWORD='yyyy yyyy yyyy yyyy yyyy yyyy'

    python3 tools/fix_farsi_term_slugs.py                    # dry run — default
    python3 tools/fix_farsi_term_slugs.py --site dmciran.ir  # one site
    python3 tools/fix_farsi_term_slugs.py --apply            # actually write

Nothing is written without --apply. Every run, dry or real, saves the current
state of each term it would touch to backups/ first, so the old slug can always
be put back by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# Only these two properties run WordPress. Adding a third here is a deliberate
# act — this script should never discover a site to write to.
SITES = {
    "cruiseshop.ir": {"env": "CRUISESHOP", "base": "https://cruiseshop.ir"},
    "dmciran.ir": {"env": "DMCIRAN", "base": "https://dmciran.ir"},
}

USER_AGENT = "albaloo-orchestrator/1.0 (+https://albaloostudio.com)"
TIMEOUT = 30


def needs_fix(slug: str) -> bool:
    """
    A slug whose archive cannot resolve: percent-encoded non-ASCII.

    `%d8%af...` is pure ASCII as a string, so testing the raw value for
    non-ASCII characters finds nothing — decode first, then look. Getting that
    backwards is what made the first version of this check silently pass.
    """
    if not slug or "%" not in slug:
        return False
    return any(ord(ch) > 127 for ch in urllib.parse.unquote(slug))


def ascii_slug_for(name: str, existing: set[str]) -> str:
    """
    A readable ASCII slug, not a transliteration.

    Transliterating Persian into Latin gives something no one can read or type
    and that no one would search for. These are internal URL keys; the Persian
    NAME is what readers see and it is left alone.
    """
    base = "uncategorized-fa" if "دسته" in name or "نشده" in name else "term-fa"
    candidate, n = base, 2
    while candidate in existing:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def auth_for(site_key: str) -> tuple[str, str] | None:
    cfg = SITES[site_key]
    user = os.getenv(f"WP_{cfg['env']}_USER") or os.getenv("WP_USER", "")
    pw = os.getenv(f"WP_{cfg['env']}_APP_PASSWORD") or os.getenv("WP_APP_PASSWORD", "")
    return (user.strip(), pw.strip()) if user.strip() and pw.strip() else None


def check(session: requests.Session, url: str) -> int:
    try:
        return session.get(url, timeout=TIMEOUT, allow_redirects=False).status_code
    except requests.RequestException:
        return 0


def run_site(site_key: str, *, apply: bool, backup_dir: Path) -> int:
    cfg = SITES[site_key]
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    print(f"\n── {site_key}")

    try:
        terms: list[dict[str, Any]] = s.get(
            f"{cfg['base']}/wp-json/wp/v2/categories?per_page=100",
            timeout=TIMEOUT).json()
    except Exception as exc:
        print(f"   could not read categories: {exc}")
        return 1
    if not isinstance(terms, list):
        print(f"   categories endpoint returned: {str(terms)[:120]}")
        return 1

    targets = [t for t in terms if needs_fix(t.get("slug", ""))]
    if not targets:
        print("   nothing to fix — every term slug already resolves.")
        return 0

    existing = {t.get("slug", "") for t in terms}
    auth = auth_for(site_key)
    changed = 0

    for t in targets:
        new_slug = ascii_slug_for(t.get("name", ""), existing)
        existing.add(new_slug)
        old_url = t.get("link", "")
        # Derive the post-change URL from the term's OWN link rather than
        # assuming a base. The two sites disagree — cruiseshop.ir uses
        # /archives/category/ and dmciran.ir uses /category/ — so a hardcoded
        # base reported a successful fix as a failure on one of them.
        new_url = (old_url.replace(t["slug"], new_slug) if t["slug"] in old_url
                   else f"{cfg['base']}/category/{new_slug}/")

        # Record the current state BEFORE anything is written, on dry runs too.
        # A backup that only exists when you remembered to ask for it is not a
        # backup. Credentials are never part of this file.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir.mkdir(parents=True, exist_ok=True)
        (backup_dir / f"{site_key}-term-{t['id']}-{stamp}.json").write_text(
            json.dumps({k: v for k, v in t.items() if k != "_links"},
                       ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"   term id={t['id']}  «{t.get('name')}»  posts={t.get('count')}")
        print(f"     slug : {t['slug'][:56]}{'…' if len(t['slug']) > 56 else ''}")
        print(f"       →    {new_slug}")
        print(f"     archive now : {check(s, old_url)}  {urllib.parse.unquote(old_url)[:70]}")

        if not apply:
            print("     DRY RUN — nothing written. Re-run with --apply to make this change.")
            continue
        if auth is None:
            print(f"     SKIPPED — set WP_{cfg['env']}_USER and WP_{cfg['env']}_APP_PASSWORD.")
            continue

        try:
            r = s.post(f"{cfg['base']}/wp-json/wp/v2/categories/{t['id']}",
                       json={"slug": new_slug}, auth=auth, timeout=TIMEOUT)
        except requests.RequestException as exc:
            print(f"     FAILED to write: {exc}")
            continue
        if r.status_code >= 400:
            # Never echo the response wholesale — an auth error can carry the
            # request back to you, credentials included.
            print(f"     FAILED: HTTP {r.status_code} — "
                  f"{str(r.json().get('code', '')) if 'json' in r.headers.get('content-type','') else ''}")
            continue

        after = check(s, new_url)
        print(f"     archive after: {after}  {new_url}")
        if after == 200:
            print("     fixed.")
            changed += 1
        else:
            print("     written, but the archive still does not resolve — the term "
                  "slug is no longer the cause. Flush permalinks "
                  "(Settings → Permalinks → Save) and re-check.")
    return 0 if (changed or not apply) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", action="append", choices=sorted(SITES),
                    help="restrict to one site (repeatable); default is both")
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without it, nothing is changed.")
    ap.add_argument("--backup-dir", default="backups")
    args = ap.parse_args(argv)

    if not args.apply:
        print("DRY RUN — no changes will be written. Add --apply when the plan below "
              "is what you want.")

    rc = 0
    for key in (args.site or sorted(SITES)):
        rc |= run_site(key, apply=args.apply, backup_dir=Path(args.backup_dir))

    print("\nThe Persian display name is unchanged on every term above — only the "
          "URL key changes.")
    if not args.apply:
        print("Nothing was written.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
