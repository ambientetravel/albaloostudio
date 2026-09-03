#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate and route a Gemini strategy manifest. Never executes it.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

The bridge is a reviewed drop, not an API (see bridge/README.md). This tool is
the gate a manifest passes before a human or an agent run acts on it:

  1. shape       — validates against bridge/task-manifest.schema.json
  2. provenance  — a task with no source is a suggestion, not a directive: rejected
  3. compliance  — prescreens every string for banned terms («خلیج عربی», a
                   no-visa claim) so a bad directive is caught before it becomes
                   a page, not after
  4. redundancy  — flags GSC-only tasks the scout already covers, so credits go
                   to what the pipeline cannot see for itself
  5. route       — reports which agent each task belongs to; writes nothing that
                   runs

    python3 tools/bridge_ingest.py bridge/examples/manifest-2026-09-03.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import compliance  # noqa: E402

SCHEMA = Path(__file__).resolve().parent.parent / "bridge" / "task-manifest.schema.json"


def _basic_validate(doc: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Enough JSON-schema checking for this fixed shape without a dependency:
    required keys, enums, additionalProperties. Kept deliberately small."""
    errs: list[str] = []
    if doc.get("schema_version") != "bridge.v1":
        errs.append("schema_version must be 'bridge.v1'")
    tasks = doc.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errs.append("tasks must be a non-empty array")
        return errs
    tschema = schema["properties"]["tasks"]["items"]
    req = tschema["required"]
    enums = {k: v["enum"] for k, v in tschema["properties"].items() if "enum" in v}
    for i, t in enumerate(tasks):
        tag = t.get("task_id", f"#{i}")
        for r in req:
            if r not in t:
                errs.append(f"[{tag}] missing required field '{r}'")
        for k, allowed in enums.items():
            if k in t and t[k] not in allowed:
                errs.append(f"[{tag}] {k}={t[k]!r} not in {allowed}")
        prov = t.get("provenance") or {}
        if not prov.get("sources"):
            errs.append(f"[{tag}] provenance.sources is empty — a directive with "
                        f"no source is a suggestion, rejected")
    return errs


# Which agent each action_type actually belongs to. The schema's enum accepts
# any valid agent name, so a geo task can be addressed to Agent 7 (country
# geography) or a schema WRITE to Agent 5 (which only audits) and still parse.
# Gemini's first manifest did exactly that on all five tasks. This catches it.
EXPECTED_AGENTS = {
    "keyword_gap": {"agent1_scout"},
    "content_brief": {"agent1_scout", "agent2_writer"},
    "schema_injection": {"agent2_writer"},          # a write, not an audit
    "geo_optimization": {"agent9_aivis", "agent2_writer"},  # not agent7 (geography)
    "competitor_watch": {"agent8_competitor"},
    "audit_fix": {"agent5_auditor"},
    "broadcast_copy": {"agent3_broadcaster"},
    "analytics_note": {"agent6_analyst", "agent7_geo"},
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path)
    args = ap.parse_args(argv)

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    doc = json.loads(args.manifest.read_text(encoding="utf-8"))

    errs = _basic_validate(doc, schema)
    if errs:
        print("REJECTED — manifest is not valid:")
        for e in errs:
            print("  ✗", e)
        return 1

    print(f"Manifest OK — {doc['source']} · {len(doc['tasks'])} task(s)\n")
    blocked = redundant = 0
    for t in doc["tasks"]:
        tag = t["task_id"]
        # compliance prescreen over every string in the task
        blob = json.dumps(t, ensure_ascii=False)
        if compliance.mentions_prohibition(blob):
            print(f"  ⛔ {tag} [{t['property_id']}] → {t['assigned_agent']}: "
                  f"names a banned term (Arabian Gulf / no-visa). HOLD for review.")
            blocked += 1
            continue
        prov = t.get("provenance") or {}
        flag = ""
        if prov.get("gsc_backed") and not prov.get("live_retrieval"):
            flag = "  ⚠ GSC-only — Agent 1 likely finds this itself; low bridge value"
            redundant += 1
        exp = EXPECTED_AGENTS.get(t["action_type"], set())
        misroute = (f"  ↳ mis-routed: {t['action_type']} belongs to "
                    f"{' or '.join(sorted(exp))}, not {t['assigned_agent']}"
                    if exp and t["assigned_agent"] not in exp else "")
        star = " ★ live-retrieval (Gemini's unique lane)" if prov.get("live_retrieval") else ""
        print(f"  ✓ {tag} [{t['property_id']}] → {t['assigned_agent']} "
              f"({t['action_type']}, {t.get('priority','P?')}){star}")
        if flag:
            print(flag)
        if misroute:
            print(misroute)

    print(f"\n{len(doc['tasks'])} task(s): "
          f"{blocked} held on compliance, {redundant} flagged redundant, "
          f"{len(doc['tasks'])-blocked} routable.")
    print("Nothing was executed. Route the clean tasks by hand or on the next "
          "agent run after review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
