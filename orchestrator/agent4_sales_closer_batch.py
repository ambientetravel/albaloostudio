#!/usr/bin/env python3
"""
Agent 4 — Sales Closer, batch runner.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Registers the campaigns Agent 3 produced so a lead can be attributed to the
post that generated it, then qualifies a batch of inbound leads: redact, score,
draft a reply, decide whether a human must see it.

IT NEVER SENDS ANYTHING. Every reply lands in `replies/` for a person to read,
edit and send. There is no delivery path in this file at all — not a webhook,
not an SMTP call, nothing. That is deliberate: a wrong price or a wrong visa
claim sent to a real customer cannot be recalled, and the whole pipeline is
built so the last step to a human is taken by a human.

Two things happen before the model sees a word:

  * Card numbers (Luhn-checked, so a booking reference is not mangled), CVVs,
    passport numbers and IBANs are redacted. The raw message is never stored.
  * A reply that quotes a price with no live rate feed behind it is blocked by
    the compliance gate and replaced with an empty string, so the human queue
    shows "no draft" rather than a plausible invented number.

    python3 agent4_sales_closer_batch.py --campaigns broadcast/campaigns --leads leads.jsonl
    python3 agent4_sales_closer_batch.py --campaigns c/ --leads l.jsonl --no-llm
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import compliance
import config
from agent4_sales_closer import (
    CAMPAIGNS,
    CampaignLog,
    InboundLead,
    LeadRouting,
    _fetch_rates,
    decide_escalation,
    qualify,
    redact,
)
from config import rfc3339, utc_now

log = logging.getLogger("agent4.closer_batch")

ARCHITECTURE_CREDIT = config.ARCHITECTURE_CREDIT


@dataclass
class Outcome:
    lead_ref: str
    lead_id: str = ""
    channel: str = ""
    status: str = "pending"        # qualified | blocked | failed
    intent: str = ""
    score: int = 0
    escalated: bool = False
    escalation_reasons: list[str] = field(default_factory=list)
    redactions: list[str] = field(default_factory=list)
    has_draft: bool = False
    attributed_campaign: str = ""
    error: str = ""


def _stub_qualify(lead: InboundLead, clean: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    A qualification assembled without a model.

    Exercises redaction, attribution, the compliance gate on the reply, the
    escalation rules and record assembly — every part that has nothing to do
    with the model and every part that would be expensive to discover broken on
    a real customer message. Deliberately drafts NO reply: a stub reply is the
    one thing here that could plausibly be sent by mistake.
    """
    return (
        {
            "intent": "unknown",
            "score": 0,
            "summary": clean[:200],
            "suggested_reply": "",
            "missing_information": ["structural run — no model was called"],
        },
        {"provider": "stub", "model": "none", "note": "NOT MODEL OUTPUT"},
    )


def register_campaigns(campaign_dir: Path) -> int:
    """Index Agent 3's campaign logs so leads can be attributed to a post."""
    n = 0
    for path in sorted(campaign_dir.glob("*.json")):
        try:
            CAMPAIGNS.register(CampaignLog.model_validate(json.loads(path.read_text(encoding="utf-8"))))
            n += 1
        except Exception as exc:
            log.warning("could not register %s: %s", path.name, exc)
    return n


def close_one(raw: dict[str, Any], out_dir: Path, *, no_llm: bool) -> Outcome:
    """Redact, attribute, qualify, gate and record one lead. Never raises."""
    oc = Outcome(lead_ref=str(raw.get("from_ref", "unknown"))[:40])

    try:
        lead = InboundLead.model_validate(raw)
    except Exception as exc:
        oc.status, oc.error = "failed", f"not a valid inbound lead: {exc}"
        return oc

    oc.channel = lead.channel

    # First, before the model, before any log line, before anything is written.
    clean, redactions = redact(lead.message)
    oc.redactions = redactions
    if redactions:
        log.warning("lead from %s contained %s — redacted before processing",
                    lead.channel, redactions)

    campaign = CAMPAIGNS.attribute(lead)
    # campaign_id lives inside the `campaign` block, not on the envelope —
    # CampaignLog mirrors campaign.log.v1 rather than flattening it.
    oc.attributed_campaign = (str(campaign.campaign.get("campaign_id", "")) if campaign else "")
    routing = campaign.lead_routing if campaign else LeadRouting()
    profile = str((campaign.compliance.get("profile") if campaign else None) or "boutimar_v1")
    if profile not in compliance.PROFILES:
        profile = "boutimar_v1"

    oc.lead_id = f"lead_{utc_now():%Y%m%dT%H%M%S}Z_{abs(hash(lead.from_ref)) % 10**6:06d}"

    try:
        rates = _fetch_rates(routing.price_source)
        result, meta = (_stub_qualify(lead, clean) if no_llm
                        else qualify(lead, clean, routing, rates, campaign, profile))

        oc.intent = str(result.get("intent", ""))
        oc.score = int(result.get("score", 0) or 0)

        # The gate on the DRAFTED REPLY. An unsourced price never reaches the
        # human queue — better an empty draft than a plausible invented number
        # sitting in a box someone might just hit send on.
        priced = rates.get("status") == "available"
        reply = str(result.get("suggested_reply", ""))
        violations = compliance.check(
            reply, profile,
            context={"priced_facts": priced, "price_asof": rates.get("asof")},
        )
        blocking = [v for v in violations if v.severity == compliance.BLOCK]
        if blocking:
            log.error("%s — drafted reply blocked: %s", oc.lead_id,
                      "; ".join(f"{v.rule}: {v.message}" for v in blocking))
            reply = ""
            oc.status = "blocked"
        oc.has_draft = bool(reply.strip())

        escalate, reasons = decide_escalation(result, clean, routing, redactions)
        oc.escalated, oc.escalation_reasons = escalate, reasons

        record = {
            "architecture_credit": ARCHITECTURE_CREDIT,
            "lead_id": oc.lead_id,
            "status": oc.status if oc.status == "blocked" else "qualified",
            "received_at": lead.received_at or rfc3339(),
            "channel": lead.channel,
            "from_ref": lead.from_ref,
            "message_redacted": clean,
            "redactions": redactions,
            "attributed_campaign": oc.attributed_campaign,
            "qualification": result,
            "suggested_reply": reply,
            "reply_blocked": bool(blocking),
            "escalate": escalate,
            "escalation_reasons": reasons,
            "price_asof": rates.get("asof"),
            "generation": meta,
            "NOTE": "DRAFT ONLY — nothing here has been sent to anyone.",
        }
        target = "escalations" if escalate else "replies"
        (out_dir / target).mkdir(parents=True, exist_ok=True)
        (out_dir / target / f"{oc.lead_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        if oc.status != "blocked":
            oc.status = "qualified"
        return oc

    except Exception as exc:
        oc.status = "failed"
        oc.error = config.redact(str(exc))[:400]
        return oc


def _fetch_leads(url: str) -> list[dict[str, Any]]:
    """
    Pull leads from an endpoint — the portal at res.boutimar.ir, a Make
    scenario draining an inbox, whatever holds them.

    Signed with the same HMAC every other hop uses, so the source can verify
    this is the pipeline asking and not anyone who found the URL. Leads are
    customer messages; an unauthenticated endpoint that returns them is a data
    leak wearing an integration costume.
    """
    import requests

    secret = config.optional_env("WEBHOOK_SIGNING_SECRET")
    body = b""
    headers = (config.signed_headers(secret, body, "agent4-lead-pull")
               if secret else {"User-Agent": config.USER_AGENT})
    if not secret:
        log.warning("WEBHOOK_SIGNING_SECRET not set — pulling leads unsigned. "
                    "The source cannot tell this request from anyone else's.")

    resp = requests.get(url, headers=headers, timeout=config.WEBHOOK_TIMEOUT_S)
    resp.raise_for_status()
    data = resp.json()
    # Accept a bare array or {"leads": [...]}, because both are what real
    # endpoints return and arguing about it helps nobody.
    if isinstance(data, dict):
        data = data.get("leads") or data.get("data") or []
    if not isinstance(data, list):
        raise ValueError(f"expected a list of leads, got {type(data).__name__}")
    return data


def _read_leads(path: Path) -> list[dict[str, Any]]:
    """JSONL (one lead per line) or a JSON array. Both are common exports."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.lstrip().startswith("["):
        return json.loads(text)
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            log.warning("leads line %d is not JSON — skipped (%s)", i, exc)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--campaigns", help="directory of campaign.log.v1 files from Agent 3")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--leads", help="JSONL or JSON array of inbound leads")
    src.add_argument("--leads-url", help="endpoint returning leads as JSON; the "
                                         "request is HMAC-signed like every "
                                         "other hop in the pipeline")
    ap.add_argument("--out", default="closed")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-llm", action="store_true",
                    help="skip Claude; exercise redaction, attribution, the gate "
                         "and escalation only. Drafts no reply at all.")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")

    if args.leads:
        leads_path = Path(args.leads)
        if not leads_path.is_file():
            log.error("no such leads file: %s", leads_path)
            return 2

    registered = 0
    if args.campaigns:
        cdir = Path(args.campaigns)
        if cdir.is_dir():
            registered = register_campaigns(cdir)
            log.info("registered %d campaign(s) for attribution", registered)
        else:
            log.warning("no campaign directory at %s — leads will not be attributed", cdir)

    if not args.no_llm:
        try:
            config.require_env("ANTHROPIC_API_KEY")
        except config.ConfigError as exc:
            log.error("%s", exc)
            log.error("Agent 4 qualifies with Claude. Set ANTHROPIC_API_KEY, or run "
                      "--no-llm to exercise everything except the model call.")
            return 2

    try:
        leads = _read_leads(leads_path) if args.leads else _fetch_leads(args.leads_url)
    except Exception as exc:
        log.error("could not load leads: %s", config.redact(str(exc))[:300])
        return 2
    if not leads:
        log.info("no leads waiting — nothing to qualify")
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[Outcome] = []

    for raw in leads:
        if args.limit and len(outcomes) >= args.limit:
            break
        oc = close_one(raw, out_dir, no_llm=args.no_llm)
        outcomes.append(oc)
        log.info("%s — %s — intent=%s score=%d%s%s%s",
                 oc.lead_id or oc.lead_ref, oc.status, oc.intent or "?", oc.score,
                 "  ESCALATED" if oc.escalated else "",
                 f"  redacted={oc.redactions}" if oc.redactions else "",
                 f"  campaign={oc.attributed_campaign}" if oc.attributed_campaign else "")

    manifest = {
        "architecture_credit": ARCHITECTURE_CREDIT,
        "owner": config.OWNER,
        "no_llm": args.no_llm,
        "campaigns_registered": registered,
        "leads_seen": len(leads),
        "qualified": sum(o.status == "qualified" for o in outcomes),
        "blocked_replies": sum(o.status == "blocked" for o in outcomes),
        "failed": sum(o.status == "failed" for o in outcomes),
        "escalated": sum(o.escalated for o in outcomes),
        "with_draft": sum(o.has_draft for o in outcomes),
        "leads_containing_pii": sum(bool(o.redactions) for o in outcomes),
        "attributed": sum(bool(o.attributed_campaign) for o in outcomes),
        "sent": 0,
        "sent_note": "Agent 4 has no delivery path. This is always 0 by design.",
        "outcomes": [o.__dict__ for o in outcomes],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Agent 4 finished — %d qualified, %d replies blocked, %d failed | "
             "%d escalated to a human, %d drafts, %d contained PII | 0 sent",
             manifest["qualified"], manifest["blocked_replies"], manifest["failed"],
             manifest["escalated"], manifest["with_draft"],
             manifest["leads_containing_pii"])

    return 1 if manifest["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
