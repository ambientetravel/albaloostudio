#!/usr/bin/env python3
"""
ops-sync: the Issues tab of the Albaloo Ops app, from orchestrator/ops_tasks.yml.

Architecture credit: Albaloo Studio — albaloostudio.com. Spec: OPS-APP.md.

GitHub owns what a task IS (title, detail, owner, priority, property, link); the app
owns its STATUS. So:
  * a task new to the app is created with status open
  * a task already in the app gets its title/detail/owner/priority/link refreshed,
    and its status left exactly as the team set it
  * a task removed from the file is set to archived (never deleted)

Row key: `key` (a field on the app's Task entity).

    python3 tools/ops_tasks.py            # dry run
    python3 tools/ops_tasks.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion_review_sync as nrs  # noqa: E402
import ops_sync  # noqa: E402

ENTITY = "Task"
FILE = ROOT / "ops_tasks.yml"
OWNED_BY_GITHUB = ("title", "detail", "owner", "priority", "property", "link")


def _ent(path: str = "") -> str:
    return f"/{ops_sync.OPS_APP}/entities/{ENTITY}{path}"


def load(path: Path = FILE) -> list[dict]:
    import yaml
    return [t for t in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("tasks") or [] if t.get("key")]


def plan(tasks: list[dict], have: list[dict], now: str) -> list[tuple]:
    calls = []
    by_key = {h.get("key"): h for h in have}
    wanted = set()
    for t in tasks:
        wanted.add(t["key"])
        body = {k: str(t.get(k) or "") for k in OWNED_BY_GITHUB}
        h = by_key.get(t["key"])
        if not h:
            calls.append(("POST", None, {"key": t["key"], **body, "status": "open", "synced_at": now}))
        elif any(str(h.get(k) or "") != body[k] for k in OWNED_BY_GITHUB) or h.get("status") == "archived":
            fields = {**body, "synced_at": now}
            if h.get("status") == "archived":       # back in the file → open again
                fields["status"] = "open"
            calls.append(("PUT", h["id"], fields))
    for h in have:
        if h.get("key") not in wanted and h.get("status") != "archived":
            calls.append(("PUT", h["id"], {"status": "archived", "synced_at": now}))
    return calls


def run(apply: bool) -> list[str]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    code, d = nrs.b44("GET", _ent("/v2/list?limit=1000"))
    if code != 200:
        return [f"Task entity not reachable (HTTP {code}) — paste OPS-APP-OVERVIEW-PROMPT.md into base44 first"]
    calls = plan(load(), nrs._b44_items(d), now)
    errors = 0
    for method, rid, body in calls:
        if apply:
            c, resp = nrs.b44(method, _ent(f"/{rid}" if rid else ""), body)
            if c not in (200, 201):
                errors += 1
    tally = {}
    for m, _, b in calls:
        k = "archive" if b.get("status") == "archived" else ("create" if m == "POST" else "update")
        tally[k] = tally.get(k, 0) + 1
    return [f"tasks: {', '.join(f'{k} ×{v}' for k, v in sorted(tally.items())) or 'nothing to change'}, "
            f"{errors} error(s)" + ("" if apply else "  (dry run — nothing written)")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if not os.environ.get("BASE44_ACCESS_TOKEN"):
        print("not configured: BASE44_ACCESS_TOKEN — nothing synced")
        return 0
    print("\n".join(run(a.apply)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
