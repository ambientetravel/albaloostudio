#!/usr/bin/env python3
"""
ops-sync phase 2: Agent 4's qualified leads → the Leads tab of the Albaloo Ops app.

Architecture credit: Albaloo Studio — albaloostudio.com. Spec: OPS-APP.md.

Runs as the last step of agent4-sales-closer.yml, on the records that run just
wrote (closed/<host>/{replies,escalations}/<lead_id>.json). leads.php hands each
lead out once, so this is the only moment the record exists; it is pushed then.

  push   one Lead row per record: site, channel, summary (who to reply to, intent,
         party, window, budget, what is missing, the redacted message), a hot /
         warm / cold band, the drafted reply, escalation and its reason
  ping   new leads → one Notion @mention of Alireza on the "🔔 New drafts" row,
         the same push the article queue uses

Staff fields (status, assigned_to, notes, reply_released) are set once on
create (new / "" / "" / no) and never written again: from then on the app owns
them. Lead state is deliberately NOT pulled back into git: a CRM status next to
a customer's email address does not belong in a repository.

The row key is `source` = "<channel>:<lead_id>" (the app's Lead entity has no
id field of its own), so a re-run never duplicates a lead.

Nothing here contacts a customer. The draft is a draft; a person copies it.

    python3 tools/ops_leads.py --closed closed            # dry run
    python3 tools/ops_leads.py --closed closed --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion_review_sync as nrs  # noqa: E402
import ops_sync  # noqa: E402

ENTITY = "Lead"
APP_URL = "https://albaloo-ops-core.base44.app"
BUYING = {"booking_enquiry", "price_enquiry", "availability"}


def _ent(path: str = "") -> str:
    return f"/{ops_sync.OPS_APP}/entities/{ENTITY}{path}"


def band(q: dict, escalate: bool) -> str:
    """hot: a qualified buying enquiry that is escalated or worth ≥ €5,000;
    warm: any other qualified lead; cold: everything else (spam, support, unqualified)."""
    if not q.get("qualified") or q.get("intent") == "spam":
        return "cold"
    if q.get("intent") in BUYING and (escalate or float(q.get("estimated_value_eur") or 0) >= 5000):
        return "hot"
    return "warm"


def summary(rec: dict) -> str:
    q = rec.get("qualification") or {}
    bits = [f"Reply to: {rec.get('from_ref') or '(no address)'}"]
    facts = [str(q.get("intent") or "").replace("_", " ")]
    if q.get("party_size"):
        facts.append(f"{q['party_size']} travellers")
    if q.get("travel_window"):
        facts.append(str(q["travel_window"]))
    if q.get("budget_band") and q["budget_band"] != "unknown":
        facts.append(f"budget {q['budget_band'].replace('_', '–')}")
    bits.append(" · ".join(f for f in facts if f))
    if q.get("missing_information"):
        bits.append("Missing: " + ", ".join(q["missing_information"]))
    if rec.get("attributed_campaign"):
        bits.append(f"Campaign: {rec['attributed_campaign']}")
    msg = str(rec.get("message_redacted") or "").strip()
    return "\n".join(bits) + ("\n\n" + msg[:3000] if msg else "")


def to_row(rec: dict, host: str, locale: str, now: datetime) -> dict:
    q = rec.get("qualification") or {}
    esc = bool(rec.get("escalate"))
    return {
        "property": host,
        "partner_id": "",
        "source": f"{rec.get('channel') or 'unknown'}:{rec['lead_id']}",
        "language": str(q.get("reply_language") or locale or "en")[:5],
        "summary": summary(rec),
        "qualification": band(q, esc),
        "draft_reply": "" if rec.get("reply_blocked") else str(rec.get("suggested_reply") or ""),
        "escalated": "yes" if esc else "no",
        "escalation_reason": "; ".join(rec.get("escalation_reasons") or []) or str(q.get("escalation_reason") or ""),
        "created_at": rec.get("received_at") or now.isoformat(timespec="seconds"),
        "synced_at": now.isoformat(timespec="seconds"),
        # staff fields: set once, owned by the app afterwards
        "status": "new",
        "assigned_to": "",
        "notes": "",
        "reply_released": "no",
    }


def records(closed: Path) -> list[tuple[str, dict]]:
    """(host, record) for every lead record under closed/. A file directly under
    closed/ (a leads-file run) has no host; it takes 'unknown'."""
    out = []
    for p in sorted(closed.glob("**/*.json")):
        if p.parent.name not in ("replies", "escalations"):
            continue
        rel = p.relative_to(closed).parts
        host = rel[0] if len(rel) == 3 else "unknown"
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("lead_id"):
            out.append((host, rec))
    return out


def ping_blocks(new: list[dict]) -> list[dict]:
    n = len(new)
    head = [{"type": "mention", "mention": {"type": "user", "user": {"id": ops_sync.OWNER}}},
            {"type": "text", "text": {"content": f" — {n} new lead{'s' if n != 1 else ''}. "}},
            {"type": "text", "text": {"content": "Open the Leads tab", "link": {"url": APP_URL}}}]
    blocks = [{"object": "block", "type": "callout", "callout": {"icon": {"emoji": "📥"}, "rich_text": head}}]
    for r in new[:20]:
        first = r["summary"].split("\n")[1] if "\n" in r["summary"] else ""
        blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [
            {"type": "text", "text": {"content": f"{r['qualification'].upper()} · {r['property']} — {first[:160]}"
                                      + (" · ESCALATED" if r["escalated"] == "yes" else "")}}]}})
    return blocks


def run(closed: Path, apply: bool, locales: dict[str, str]) -> list[str]:
    now = datetime.now(timezone.utc)
    log: list[str] = []
    recs = records(closed)
    if not recs:
        return ["no lead records in this run — nothing to push"]
    code, d = nrs.b44("GET", _ent("/v2/list?limit=1000"))
    if code != 200:
        raise RuntimeError(f"base44 {code} listing {ENTITY}: {str(d)[:200]}")
    have = {str(r.get("source") or "") for r in nrs._b44_items(d)}
    new = []
    for host, rec in recs:
        row = to_row(rec, host, locales.get(host, "en"), now)
        if row["source"] in have:
            log.append(f"exists      {row['source']}")
            continue
        log.append(f"create      {row['source']}  {host} · {row['qualification']}"
                   + (" · escalated" if row["escalated"] == "yes" else ""))
        if apply:
            c, resp = nrs.b44("POST", _ent(), row)
            if c not in (200, 201):
                log.append(f"  ! base44 {c}: {str(resp)[:160]}")
                continue
        new.append(row)
        have.add(row["source"])
    if new and os.environ.get("NOTION_TOKEN"):
        log.append(f"ping        {len(new)} new lead(s) → Notion @mention")
        if apply:
            db = os.environ.get("NOTION_REVIEW_DB") or nrs.DEFAULT_DB
            c, resp = nrs.notion("PATCH", f"/blocks/{ops_sync._ping_container(db)}/children",
                                 {"children": ping_blocks(new)})
            if c != 200:
                log.append(f"  ! Notion {c} ping: {str(resp)[:160]}")
    log.append(f"summary: {len(recs)} record(s), {len(new)} created"
               + ("" if apply else "  (dry run — nothing written)"))
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--closed", default="closed", help="Agent 4's --out folder")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if not os.environ.get("BASE44_ACCESS_TOKEN"):
        print("not configured: BASE44_ACCESS_TOKEN — nothing pushed")
        return 0
    try:
        import config  # noqa: PLC0415
        locales = {s.domain: s.locale for s in config.load_sites()}
    except Exception:  # noqa: BLE001 — a missing locale only defaults to "en"
        locales = {}
    print("\n".join(run(Path(a.closed), a.apply, locales)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
