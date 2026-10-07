#!/usr/bin/env python3
"""
Insert one paragraph into a LIVE base44 article, after an exact anchor sentence.

base44 has no pull requests: a record edit is live the moment it saves. So this
is deliberately narrow — one insertion, located by an anchor that must occur
exactly once, nothing else in the record touched — and it is careful the same
way the photo backfill is: the record is saved to disk first (kept as a run
artifact), only body_markdown is written, and the record is read back and
compared. Anything unexpected restores the backup.

First use, 7 Oct 2026: cruisebaz /aroya-cruise-guide shows AROYA at Rhodes, and
its visa section had no Schengen line for Greek calls.

    python3 tools/base44_patch.py --domain cruisebaz.com --slug /aroya-cruise-guide \
        --after "…anchor sentence…" --insert "…new paragraph…"          # dry run
    … --apply                                                            # write
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402


def patched(body: str, anchor: str, insert: str) -> str:
    """The body with `insert` as its own paragraph right after the line holding
    `anchor`. Refuses an anchor that is missing or not unique, and an insert that
    is already there (re-running is a no-op, not a duplicate paragraph)."""
    if insert.strip() in body:
        return body
    n = body.count(anchor)
    if n != 1:
        raise ValueError(f"anchor occurs {n} times; it must occur exactly once")
    i = body.index(anchor) + len(anchor)
    eol = body.find("\n", i)
    eol = len(body) if eol == -1 else eol
    return body[:eol].rstrip() + "\n\n" + insert.strip() + "\n" + body[eol:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--domain", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--after", required=True, help="exact anchor text, must occur once")
    ap.add_argument("--insert", required=True, help="the paragraph to add")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    import agent2_writer_listener as a2
    site = config.load_sites(only=[a.domain], include_hold=True)[0]
    cms = site.cms if isinstance(site.cms, dict) else site.cms.model_dump()
    base = a2.base44_entity_url(str(cms["app_id"]), str(cms.get("entity") or "Article"))
    hdr = {"Authorization": f"Bearer {os.environ.get('BASE44_ACCESS_TOKEN', '')}",
           "Content-Type": "application/json", "User-Agent": config.USER_AGENT}

    r = requests.get(f"{base}/v2/list", headers=hdr, timeout=40,
                     params={"q": json.dumps({"slug": a.slug}), "limit": 2})
    r.raise_for_status()
    d = r.json()
    recs = d if isinstance(d, list) else (d.get("records") or d.get("items") or [])
    if len(recs) != 1:
        print(f"expected exactly one record for {a.slug}, found {len(recs)}")
        return 2
    rec = recs[0]
    rid = rec.get("id") or rec.get("_id")
    body = str(rec.get("body_markdown") or "")
    new = patched(body, a.after, a.insert)
    if new == body:
        print(f"{a.slug}: the paragraph is already there — nothing to do")
        return 0
    print(f"{a.slug} ({rec.get('status')}): body {len(body)} → {len(new)} chars; inserted after the anchor:\n"
          f"  {a.insert.strip()}")
    if not a.apply:
        print("dry run — nothing written")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bdir = ROOT / "runs" / f"base44-patch-backup-{stamp}"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / f"{rid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    requests.put(f"{base}/{rid}", headers=hdr, json={"body_markdown": new}, timeout=40).raise_for_status()
    now = requests.get(f"{base}/{rid}", headers=hdr, timeout=40)
    now.raise_for_status()
    after = now.json()
    keep = ("title", "slug", "status", "meta_description", "image_url", "image_credit")
    drift = [k for k in keep if rec.get(k) != after.get(k)]
    if after.get("body_markdown") != new or drift:
        requests.put(f"{base}/{rid}", headers=hdr, timeout=40,
                     json={k: rec.get(k) for k in keep + ("body_markdown",) if k in rec}).raise_for_status()
        print(f"UNEXPECTED read-back (body mismatch or changed {drift}) — restored from backup")
        return 1
    print(f"written and verified; backup in {bdir.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
