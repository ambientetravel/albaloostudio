#!/usr/bin/env python3
"""
ops-sync phase 3: the Today tab of the Albaloo Ops app, from the health report.

Architecture credit: Albaloo Studio — albaloostudio.com. Spec: OPS-APP.md.

reports/health-latest.json is what tools/health_report.py already writes from
the agents' own artifacts (health.yml, committed back to main). This mirrors it:

  AgentRun    one row per agent: last result, age in days, run link   (upsert by agent)
  HealthItem  every critical / needs_you / warn / fine line            (replaced each sync)
  Metric      the report's numbers; `previous` is the value the app    (upsert by name)
              held before this sync, or the report's own prev_* figure

Read-only towards GitHub. Nothing here is a team input, so nothing comes back.

    python3 tools/ops_today.py            # dry run
    python3 tools/ops_today.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion_review_sync as nrs  # noqa: E402
import ops_sync  # noqa: E402

REPORT = ROOT / "reports" / "health-latest.json"
LEVELS = ("critical", "needs_you", "warn", "fine")
# report key → (label shown in the app, report key holding the previous figure)
METRICS = {
    "open_prs": ("Article PRs waiting", None),
    "articles": ("Articles drafted (last cycle)", "prev_articles"),
    "briefs": ("Briefs (last cycle)", None),
    "cost_usd": ("Model spend, USD (last cycle)", "prev_cost_usd"),
    "posts": ("Social posts composed", None),
    "posts_held": ("Social posts held", None),
    "dlq": ("Dead-lettered", None),
    "sites_scanned": ("Sites scanned", None),
}


def _ent(name: str, path: str = "") -> str:
    return f"/{ops_sync.OPS_APP}/entities/{name}{path}"


def plain(md: str, cap: int = 600) -> str:
    """Health lines are markdown; the app shows plain text."""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    t = t.replace("**", "").replace("`", "")
    return (t[: cap - 1] + "…") if len(t) > cap else t


def rows_from(report: dict, now: str) -> tuple[list[dict], list[dict], list[dict]]:
    runs = [{"agent": a["agent"], "result": a.get("result") or "skipped",
             "age_days": float(a.get("age_days") or 0), "run_url": a.get("url") or "", "synced_at": now}
            for a in report.get("agents") or []]
    items = [{"level": lvl, "text": plain(str(t)), "property": "", "synced_at": now}
             for lvl in LEVELS for t in report.get(lvl) or []]
    nums = report.get("numbers") or {}
    metrics = []
    for key, (label, prev_key) in METRICS.items():
        v = nums.get(key)
        if isinstance(v, (int, float)):
            m = {"name": label, "value": round(float(v), 3), "synced_at": now}
            if prev_key and isinstance(nums.get(prev_key), (int, float)):
                m["previous"] = round(float(nums[prev_key]), 3)
            metrics.append(m)
    return runs, items, metrics


def _list(name: str) -> list[dict]:
    code, d = nrs.b44("GET", _ent(name, "/v2/list?limit=1000"))
    if code != 200:
        raise RuntimeError(f"base44 {code} listing {name}: {str(d)[:200]}")
    return nrs._b44_items(d)


def plan(runs, items, metrics, have_runs, have_items, have_metrics) -> list[tuple]:
    """Ordered (method, entity, id-or-None, body) calls."""
    calls = []
    by_agent = {r.get("agent"): r for r in have_runs}
    for r in runs:
        h = by_agent.get(r["agent"])
        calls.append(("PUT", "AgentRun", h["id"], r) if h else ("POST", "AgentRun", None, r))
    for h in have_items:                     # health lines are replaced wholesale
        calls.append(("DELETE", "HealthItem", h["id"], None))
    for it in items:
        calls.append(("POST", "HealthItem", None, it))
    by_name = {m.get("name"): m for m in have_metrics}
    for m in metrics:
        h = by_name.get(m["name"])
        if h and "previous" not in m and h.get("value") is not None and h.get("value") != m["value"]:
            m = {**m, "previous": h["value"]}
        calls.append(("PUT", "Metric", h["id"], m) if h else ("POST", "Metric", None, m))
    return calls


def run(apply: bool, report_path: Path = REPORT) -> list[str]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    runs, items, metrics = rows_from(report, now)
    calls = plan(runs, items, metrics, _list("AgentRun"), _list("HealthItem"), _list("Metric"))
    log = [f"report generated {report.get('generated')}: {len(runs)} agents, {len(items)} health lines, "
           f"{len(metrics)} metrics"]
    errors = 0
    for method, ent, rid, body in calls:
        if not apply:
            continue
        code, d = nrs.b44(method, _ent(ent, f"/{rid}" if rid else ""), body)
        if code not in (200, 201, 204):
            errors += 1
            log.append(f"  ! base44 {code} {method} {ent}: {str(d)[:160]}")
    tally = {}
    for method, ent, _, _ in calls:
        tally[f"{method} {ent}"] = tally.get(f"{method} {ent}", 0) + 1
    log.append("calls: " + ", ".join(f"{k} ×{v}" for k, v in sorted(tally.items())))
    log.append(f"summary: {len(calls)} call(s), {errors} error(s)" + ("" if apply else "  (dry run — nothing written)"))
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if not os.environ.get("BASE44_ACCESS_TOKEN"):
        print("not configured: BASE44_ACCESS_TOKEN — nothing synced")
        return 0
    if not REPORT.exists():
        print(f"no {REPORT.name} — nothing to sync")
        return 0
    print("\n".join(run(a.apply)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
