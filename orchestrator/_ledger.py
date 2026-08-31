# -*- coding: utf-8 -*-
"""What Agent 1 has already asked for, so it stops asking again.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHY THIS EXISTS
───────────────
On 31 Aug 2026 the run history showed 53 briefs collapsing to 10 distinct
keywords. «لانزاروته» had been briefed in ten separate runs, «joybar boutique
hotel» in five. The pipeline was not finding new gaps every week — it was
re-proposing the same handful, because the only thing it checked was whether a
matching URL was already in the sitemap. A brief that has been written, PR'd
and merged but not yet crawled is invisible to that check, so the gap looks
open and the same brief goes out again.

The ledger closes that loop. Every keyword a brief has been emitted for is
recorded with the date. Before the next run sends candidates to the model, any
keyword briefed within the cooldown window is dropped, and the run moves on to
the next gaps down the list.

WHY A COOLDOWN AND NOT A PERMANENT BAN
──────────────────────────────────────
A first attempt can fail — the article underperforms, or never shipped. After
the cooldown a keyword becomes eligible again, so a genuine miss gets a second
try rather than being abandoned forever. 45 days is long enough for write →
merge → deploy → crawl → rank to play out, and short enough that a failed
attempt is not stuck for a quarter.

PERSISTENCE
───────────
The ledger is a committed file, not an artifact, because it has to survive
across scheduled CI runs where each run starts from a clean checkout. Agent 1
reads it from the checkout at the start of a run and the workflow commits the
updated copy at the end. Seeded once from run history so it is populated on the
first read rather than starting empty and re-emitting everything one last time.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_PATH = Path(__file__).resolve().parent / "written" / "briefed-ledger.json"
DEFAULT_COOLDOWN_DAYS = 45


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def load(path: Path = LEDGER_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"cooldown_days": DEFAULT_COOLDOWN_DAYS, "updated_at": None,
                "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _key(domain: str, query: str) -> str:
    return f"{domain}|{query}"


def recently_briefed(doc: dict[str, Any], domain: str, now: datetime | None = None
                     ) -> set[str]:
    """Keywords for this domain still inside the cooldown — the skip set.

    A keyword with no parseable date is treated as recent, not stale: an
    undated entry is evidence it was briefed, and re-briefing on a parse failure
    is the exact loop this exists to stop.
    """
    now = now or datetime.now(timezone.utc)
    cooldown = int(doc.get("cooldown_days", DEFAULT_COOLDOWN_DAYS))
    skip: set[str] = set()
    for e in doc.get("entries", []):
        if e.get("domain") != domain:
            continue
        last = _parse(e.get("last_briefed"))
        if last is None or (now - last).days < cooldown:
            skip.add(e["query"])
    return skip


def filter_candidates(candidates: list[dict[str, Any]], doc: dict[str, Any],
                      domain: str, now: datetime | None = None
                      ) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (kept, skipped_queries). Order preserved."""
    skip = recently_briefed(doc, domain, now)
    kept, skipped = [], []
    for c in candidates:
        if c.get("query") in skip:
            skipped.append(c["query"])
        else:
            kept.append(c)
    return kept, skipped


def record(doc: dict[str, Any], domain: str, query: str,
           target_url_path: str | None = None,
           now: datetime | None = None) -> dict[str, Any]:
    """Append or update one (domain, keyword) entry. Mutates and returns doc."""
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    entries = doc.setdefault("entries", [])
    for e in entries:
        if e.get("domain") == domain and e.get("query") == query:
            e["last_briefed"] = stamp
            e["times_briefed"] = int(e.get("times_briefed", 0)) + 1
            if target_url_path:
                e["target_url_path"] = target_url_path
            doc["updated_at"] = stamp
            return doc
    entries.append({"domain": domain, "query": query, "first_briefed": stamp,
                    "last_briefed": stamp, "times_briefed": 1,
                    "target_url_path": target_url_path})
    doc["updated_at"] = stamp
    return doc


def save(doc: dict[str, Any], path: Path = LEDGER_PATH) -> None:
    doc["entries"] = sorted(doc.get("entries", []), key=lambda e: e.get("query", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
