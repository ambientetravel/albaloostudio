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


# Spellings of one name that must compare equal. AROYA alone is written five
# ways across the three Farsi sites' queries; without this «کشتی aroya» on
# boutimar.ir and «کروز آروآ» on cruisebaz never register as the same topic.
_ALIASES = {"آرویا": "aroya", "آروآ": "aroya", "آروآیا": "aroya", "آروا": "aroya",
            "اروا": "aroya", "آرویا،": "aroya", "keruz": "cruise", "kroz": "cruise",
            "کروز": "cruise", "کشتی": "cruise", "ship": "cruise", "cruises": "cruise"}
_STOP = {"the", "a", "of", "for", "to", "in", "and", "و", "در", "از", "به", "برای", "با"}


def topic_key(query: str) -> frozenset[str]:
    """A spelling-insensitive identity for a query: its token SET after
    normalising Arabic/Persian letter forms, ZWNJ and known aliases. Word order
    and filler words do not make a different topic."""
    import unicodedata
    q = unicodedata.normalize("NFKC", str(query)).lower()
    q = q.replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
    toks = [t.strip(".,:;!?؟،()«»\"'") for t in q.split()]
    return frozenset(_ALIASES.get(t, t) for t in toks if t and t not in _STOP)


def sibling_topics(doc: dict[str, Any], siblings: list[str] | tuple[str, ...],
                   now: datetime | None = None) -> list[dict[str, str]]:
    """What the sibling sites of an audience group briefed inside the cooldown —
    the topics this site must not duplicate."""
    now = now or datetime.now(timezone.utc)
    cooldown = int(doc.get("cooldown_days", DEFAULT_COOLDOWN_DAYS))
    out = []
    for e in doc.get("entries", []):
        if e.get("domain") not in siblings:
            continue
        last = _parse(e.get("last_briefed"))
        if last is None or (now - last).days < cooldown:
            out.append({"domain": e["domain"], "query": e["query"],
                        "target_url_path": e.get("target_url_path") or ""})
    return out


def filter_candidates(candidates: list[dict[str, Any]], doc: dict[str, Any],
                      domain: str, now: datetime | None = None,
                      siblings: list[str] | tuple[str, ...] = ()
                      ) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (kept, skipped_queries). Order preserved.

    `siblings` are the other sites of this one's audience group: a query one of
    them briefed inside the cooldown is skipped here too — first site to brief a
    topic owns it — matched by topic_key so spelling variants count."""
    skip = recently_briefed(doc, domain, now)
    sib_keys = {topic_key(t["query"]) for t in sibling_topics(doc, siblings, now)}
    kept, skipped = [], []
    for c in candidates:
        q = c.get("query")
        if q in skip:
            skipped.append(q)
        elif sib_keys and topic_key(q) in sib_keys:
            skipped.append(f"{q} (owned by a sibling site)")
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


def release(doc: dict[str, Any], domain: str, query: str) -> bool:
    """Un-freeze one (domain, keyword): drop its entry so the next run may brief it
    again. For a brief that consumed a ledger slot but produced no article — blocked
    or failed at Agent 2 — so a pipeline fix isn't stranded behind a 45-day cooldown.
    Returns True if an entry was removed."""
    entries = doc.get("entries", [])
    kept = [e for e in entries if not (e.get("domain") == domain and e.get("query") == query)]
    if len(kept) == len(entries):
        return False
    doc["entries"] = kept
    doc["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return True


def apply_releases(doc: dict[str, Any], pairs: list[tuple[str, str]]) -> list[str]:
    """Release every (domain, query) that actually had an entry; return what was
    freed, for the run log. Idempotent — a pair with no entry is a no-op."""
    freed = []
    for domain, query in pairs:
        if domain and query and release(doc, domain, query):
            freed.append(f"{domain} · {query}")
    return freed


def save(doc: dict[str, Any], path: Path = LEDGER_PATH) -> None:
    doc["entries"] = sorted(doc.get("entries", []), key=lambda e: e.get("query", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
