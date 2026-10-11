#!/usr/bin/env python3
"""Turn an Agent 2 manifest into a ledger release list.

Agent 2 runs read-only on this repo, so it cannot un-record a keyword it blocked
or failed to draft — the keyword then sits in briefed-ledger.json under a 45-day
cooldown and never re-briefs, even after the pipeline bug that blocked it is
fixed. This reads the manifest Agent 2 already emits and writes the (domain,
keyword) pairs Agent 1 should release on its next run, into written/releases.json.

Released statuses: `blocked` (compliance), `failed` (draft error) and `deferred`
(budget ceiling or a provider outage) — a brief that consumed a slot and produced
nothing. `deferred` was once left out as "intentional — it runs next time", but
the writer only ever reads the NEWEST scout run, so a deferred brief never ran
again: 11 Oct, three briefs past the $1 run ceiling sat frozen for 45 days.
NOT `blocked_config` (a permanent site-config condition — re-briefing can't
help), NOT `drafted`.

Several manifests may be given (every writer run since the last scout — a
one-site re-run must not hide the main run's outcomes). A keyword drafted in ANY
of them is never released. `skipped` only in one case: a DEGRADED brief (built without the
scout's LLM step), which the writer skips while promising a re-scout — a promise
the ledger broke by holding the keyword for 45 days (boutimar.ir: 7 briefs, 0
drafts). The scout no longer records those; this frees any already recorded.

Pure transform, no network: the workflow downloads the manifest artifact, this
turns it into the release list. Missing or unreadable input writes an empty list
rather than failing — a self-heal that errors must never break the scout run.

    python3 tools/collect_releases.py <manifest.json>... [--out <releases.json>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RELEASE_STATUSES = {"blocked", "failed", "deferred"}
# Agent 2's skip text for a degraded brief (agent2_writer_batch.py). Matched as
# text because this tool must stay import-free — it runs as a tolerant CI step.
DEGRADED_SKIP_MARK = "without its LLM step"


def _released(o: dict) -> str | None:
    status = o.get("status")
    if status in RELEASE_STATUSES:
        return status
    if status == "skipped" and DEGRADED_SKIP_MARK in str(o.get("error") or ""):
        return "skipped_degraded"
    return None


def collect(manifest: dict) -> list[dict[str, str]]:
    out, seen = [], set()
    for o in manifest.get("outcomes", []) or []:
        reason = _released(o) if isinstance(o, dict) else None
        if not reason:
            continue
        domain = str(o.get("domain") or "").strip()
        query = str(o.get("keyword") or "").strip()
        if domain and query and (domain, query) not in seen:
            seen.add((domain, query))
            out.append({"domain": domain, "query": query, "reason": reason})
    return out


def collect_many(manifests: list[dict]) -> list[dict[str, str]]:
    drafted = {(str(o.get("domain") or "").strip(), str(o.get("keyword") or "").strip())
               for m in manifests for o in (m.get("outcomes") or []) if isinstance(o, dict)
               and o.get("status") == "drafted"}
    out, seen = [], set()
    for m in manifests:
        for r in collect(m):
            k = (r["domain"], r["query"])
            if k not in drafted and k not in seen:
                seen.add(k)
                out.append(r)
    return out


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    dst = Path("written/releases.json")
    if "--out" in args:
        i = args.index("--out")
        dst = Path(args[i + 1])
        del args[i:i + 2]
    elif len(args) == 2 and args[1].endswith("releases.json"):
        dst = Path(args.pop())            # the old two-positional form
    srcs = [Path(a) for a in args] or [Path("written/manifest.json")]
    manifests = []
    for src in srcs:
        try:
            manifests.append(json.loads(src.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            print(f"collect_releases: skipping unusable manifest {src} ({exc})", file=sys.stderr)
    releases = collect_many(manifests)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(releases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"collect_releases: {len(releases)} keyword(s) to release → {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
