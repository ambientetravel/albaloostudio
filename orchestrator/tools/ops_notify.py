#!/usr/bin/env python3
"""
ops-sync: notifications for the Albaloo Ops app, routed by field.

Architecture credit: Albaloo Studio — albaloostudio.com. Routing: ops_team.yml.

Events become `Notification` rows in the app. Each row carries a `field`
(persian_content, english_content, sales, social, technical, owner); the app
shows each team member the rows for the fields they cover (TeamMember entity,
set up in the app) and handles any e-mail. This module never sends a message
and never holds an address.

One row per event, keyed so the hourly sync cannot repeat it. A first sync
(seed) announces nothing: the backlog is not news.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import yaml

import notion_review_sync as nrs
import ops_sync

ROOT = Path(__file__).resolve().parents[1]
ENTITY = "Notification"


def load_routing() -> dict:
    return yaml.safe_load((ROOT / "ops_team.yml").read_text(encoding="utf-8"))


def field_for(kind: str, site: str, routing: dict) -> str:
    route = (routing.get("routes") or {}).get(kind, "owner")
    if route != "by_property":
        return route
    for name, f in (routing.get("fields") or {}).items():
        if site in (f.get("properties") or []):
            return name
    return "owner"            # a property nobody owns goes to the owner, never nowhere


def _key(kind: str, *parts: str) -> str:
    return kind + ":" + hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def draft_events(created: list[dict], routing: dict, now: str) -> list[dict]:
    out = []
    for r in created:
        if r.get("status") != "To review":
            continue
        score, why = ops_sync.priority(r, datetime.fromisoformat(now))
        out.append({"key": _key("new_draft", r["pid"]), "kind": "new_draft",
                    "field": field_for("new_draft", r.get("site", ""), routing),
                    "level": "info", "property": r.get("site", ""),
                    "title": f"New draft to review: {r.get('title', '')[:90]}",
                    "body": f"Priority {score} — {why}", "link": ops_sync.pr_link(r["pid"])[2] or r.get("read", ""),
                    "created_at": now})
    return out


def lead_events(new_rows: list[dict], routing: dict, now: str, cap: int = 20) -> list[dict]:
    """A hot or escalated lead just reached the Leads tab. One event per lead, keyed by the
    lead's own row key, so a lead handed out twice is announced once. No contact details
    here: the notification says a lead is waiting, the Leads tab holds who."""
    out = []
    for r in new_rows:
        if r.get("qualification") != "hot" and r.get("escalated") != "yes":
            continue
        facts = (r.get("summary", "").split("\n") + ["", ""])[1]
        why = r.get("escalation_reason") or ""
        out.append({"key": _key("hot_lead", r["source"]), "kind": "hot_lead",
                    "field": field_for("hot_lead", r.get("property", ""), routing),
                    "level": "action", "property": r.get("property", ""),
                    "title": f"{'Hot' if r.get('qualification') == 'hot' else 'Escalated'} lead · {r.get('property', '')}: {facts[:80]}",
                    "body": (f"Escalated: {why[:200]}. " if why else "") + "Open the Leads tab to reply.",
                    "link": "https://albaloo-ops-core.base44.app", "created_at": now})
    return out[:cap]


def social_events(created: list[dict], routing: dict, now: str, cap: int = 10) -> list[dict]:
    """Posts Agent 3 composed and held at the autopost gate, newly on the Social tab. Nothing is
    published from here; this only says a human decision is waiting."""
    out = []
    for r in created:
        if r.get("status") != "held":
            continue
        out.append({"key": _key("social_held", str(r.get("channel")), str(r.get("copy"))), "kind": "social_held",
                    "field": field_for("social_held", r.get("property", ""), routing),
                    "level": "action", "property": r.get("property", ""),
                    "title": f"Post held for approval: {r.get('channel', '')} · {r.get('property', '')}",
                    "body": str(r.get("copy", ""))[:300], "link": "https://albaloo-ops-core.base44.app",
                    "created_at": now})
    return out[:cap]


def health_events(report: dict, routing: dict, now: str) -> list[dict]:
    out = []
    for level, kind, lvl in (("critical", "health_critical", "critical"),
                             ("needs_you", "health_needs_you", "action")):
        for line in report.get(level) or []:
            text = ops_sync_plain(str(line))
            out.append({"key": _key(kind, text), "kind": kind, "field": field_for(kind, "", routing),
                        "level": lvl, "property": "", "title": text[:120], "body": text[:600],
                        "link": "", "created_at": now})
    return out


def ops_sync_plain(md: str) -> str:
    import re
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    return t.replace("**", "").replace("`", "")


def stale_events(report: dict, routing: dict, now: str, hours: int = 26) -> list[dict]:
    try:
        gen = datetime.fromisoformat(str(report.get("generated")).replace("Z", "+00:00"))
        if gen.tzinfo is None:
            gen = gen.replace(tzinfo=timezone.utc)
        age = (datetime.fromisoformat(now) - gen).total_seconds() / 3600
    except ValueError:
        return []
    if age <= hours:
        return []
    day = gen.date().isoformat()
    return [{"key": _key("data_stale", day), "kind": "data_stale", "field": field_for("data_stale", "", routing),
             "level": "warn", "property": "", "title": f"Health report is {int(age)} h old",
             "body": f"The Today tab is showing a report generated {gen:%d %b %H:%M} UTC. health.yml is late or failed.",
             "link": "", "created_at": now}]


def publish(events: list[dict], apply: bool) -> list[str]:
    """Write the events the app has not seen. Never raises: a notification problem must not break a sync."""
    if not events:
        return []
    try:
        code, d = nrs.b44("GET", f"/{ops_sync.OPS_APP}/entities/{ENTITY}/v2/list?limit=2000")
        if code != 200:
            return [f"notifications: {len(events)} event(s) but the app has no Notification entity yet "
                    f"(HTTP {code}) — paste OPS-APP-NOTIFY-PROMPT.md into base44"]
        seen = {x.get("key") for x in nrs._b44_items(d)}
        fresh = [e for e in events if e["key"] not in seen]
        log = [f"notifications: {len(fresh)} new of {len(events)} event(s)"
               + ("" if apply else "  (dry run — nothing written)")]
        for e in fresh:
            log.append(f"  notify  [{e['field']}] {e['title'][:70]}")
            if apply:
                c, r = nrs.b44("POST", f"/{ops_sync.OPS_APP}/entities/{ENTITY}", e)
                if c not in (200, 201):
                    log.append(f"  ! base44 {c}: {str(r)[:120]}")
        return log
    except Exception as exc:  # noqa: BLE001
        return [f"  ! notifications skipped: {exc}"]
