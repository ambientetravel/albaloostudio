#!/usr/bin/env python3
"""Turn an Agent 2 manifest into a ledger release list.

Agent 2 runs read-only on this repo, so it cannot un-record a keyword it blocked
or failed to draft — the keyword then sits in briefed-ledger.json under a 45-day
cooldown and never re-briefs, even after the pipeline bug that blocked it is
fixed. This reads the manifest Agent 2 already emits and writes the (domain,
keyword) pairs Agent 1 should release on its next run, into written/releases.json.

Released statuses: `blocked` (compliance) and `failed` (draft error) — a brief
that consumed a slot and produced nothing. NOT `blocked_config` (a permanent
site-config condition — re-briefing can't help), NOT `deferred` (intentional),
NOT `skipped`/`drafted`.

Pure transform, no network: the workflow downloads the manifest artifact, this
turns it into the release list. Missing or unreadable input writes an empty list
rather than failing — a self-heal that errors must never break the scout run.

    python3 tools/collect_releases.py <manifest.json> [<out releases.json>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RELEASE_STATUSES = {"blocked", "failed"}


def collect(manifest: dict) -> list[dict[str, str]]:
    out, seen = [], set()
    for o in manifest.get("outcomes", []) or []:
        if not isinstance(o, dict) or o.get("status") not in RELEASE_STATUSES:
            continue
        domain = str(o.get("domain") or "").strip()
        query = str(o.get("keyword") or "").strip()
        if domain and query and (domain, query) not in seen:
            seen.add((domain, query))
            out.append({"domain": domain, "query": query, "reason": o["status"]})
    return out


def main(argv: list[str]) -> int:
    src = Path(argv[1]) if len(argv) > 1 else Path("written/manifest.json")
    dst = Path(argv[2]) if len(argv) > 2 else Path("written/releases.json")
    try:
        manifest = json.loads(src.read_text(encoding="utf-8"))
        releases = collect(manifest)
    except (OSError, ValueError) as exc:
        print(f"collect_releases: no usable manifest ({exc}); writing empty list",
              file=sys.stderr)
        releases = []
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(releases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"collect_releases: {len(releases)} keyword(s) to release → {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
