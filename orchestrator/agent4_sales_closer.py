#!/usr/bin/env python3
"""
Agent 4 — The Sales Closer.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Consumes `campaign.log.v1` from Agent 3 to know what is in market, then takes
inbound leads from the site chat, WhatsApp and Instagram DM, attributes them to
a campaign, qualifies them with Claude, and drafts a reply.

    uvicorn agent4_sales_closer:app --host 0.0.0.0 --port 8082

Three boundaries are structural, not stylistic (ARCHITECTURE.md §5):

  1. It **qualifies, it does not contract.** Every reply is a draft. Nothing is
     sent to a customer by this process — a human releases it.
  2. It quotes **only** figures present in the live feed named by the campaign's
     `lead_routing.price_source`, and always states the `price_asof` timestamp.
  3. It never handles payment details, card numbers or passport numbers. Those
     are redacted on arrival, before the model sees them and before anything is
     written to disk.
"""

from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
from typing import Any, Literal

import requests
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import compliance
import config
from config import rfc3339, utc_now

log = logging.getLogger("agent4.closer")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

AGENT_ID = "agent4.closer"

app = FastAPI(
    title="Albaloo Orchestrator — Agent 4 (Sales Closer)",
    version="1.0.0",
    description=(
        "Lead qualification and escalation. Drafts replies; sends nothing. "
        f"Architecture credit: {config.ARCHITECTURE_CREDIT} — {config.ARCHITECTURE_URL}"
    ),
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Redaction — runs before the model and before storage
# ══════════════════════════════════════════════════════════════════════════════

_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_PASSPORT = re.compile(r"(?i)\b(?:passport|پاسپورت|گذرنامه)\D{0,12}([A-Z0-9]{6,9})\b")
_CVV = re.compile(r"(?i)\b(cvv|cvc|شماره\s*امنیتی)\D{0,6}\d{3,4}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")


def _luhn(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact(text: str) -> tuple[str, list[str]]:
    """
    Strip payment and identity numbers. Returns (clean_text, kinds_found).

    A card number is only redacted if it passes Luhn — otherwise a booking
    reference or a phone number would be mangled for nothing.
    """
    found: list[str] = []

    def _card_sub(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            found.append("card_number")
            return "[redacted:card]"
        return m.group(0)

    text = _CARD.sub(_card_sub, text)
    if _CVV.search(text):
        found.append("cvv")
        text = _CVV.sub("[redacted:cvv]", text)
    if _PASSPORT.search(text):
        found.append("passport_number")
        text = _PASSPORT.sub("[redacted:passport]", text)
    if _IBAN.search(text):
        found.append("iban")
        text = _IBAN.sub("[redacted:iban]", text)
    return text, sorted(set(found))


# ══════════════════════════════════════════════════════════════════════════════
# 2. Payloads
# ══════════════════════════════════════════════════════════════════════════════


class _Loose(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Envelope(_Loose):
    message_id: str
    correlation_id: str
    causation_id: str | None = None
    idempotency_key: str
    message_type: str
    emitted_at: str
    emitted_by: str
    target: str
    attempt: int = 1
    environment: str = "production"
    architecture_credit: str
    owner: str | None = None


class LeadRouting(_Loose):
    inboxes: list[str] = Field(default_factory=list)
    qualification_profile: str = "cruise_d2c_v1"
    price_source: str | None = None
    quote_policy: Literal["live_feed_only"] = "live_feed_only"
    high_value_threshold: dict[str, Any] = Field(
        default_factory=lambda: {"amount": 15000, "currency": "EUR"}
    )
    escalate_to: str = "alireza"
    auto_escalate_signals: list[str] = Field(default_factory=list)


class CampaignLog(_Loose):
    schema_version: str
    envelope: Envelope
    source_publication: dict[str, Any]
    campaign: dict[str, Any]
    posts: list[dict[str, Any]] = Field(default_factory=list)
    tracking: dict[str, Any] = Field(default_factory=dict)
    lead_routing: LeadRouting = Field(default_factory=LeadRouting)
    compliance: dict[str, Any] = Field(default_factory=dict)


class InboundLead(BaseModel):
    """What a chat widget, WhatsApp bridge or inbox poller posts to us."""

    model_config = ConfigDict(extra="allow")

    channel: str                      # site_chat | whatsapp | instagram_dm | email | form
    from_ref: str                     # opaque handle — never a raw phone number if avoidable
    message: str
    locale: str | None = None
    utm_campaign: str | None = None
    landing_path: str | None = None
    display_name: str | None = None
    received_at: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# 3. Stores
# ══════════════════════════════════════════════════════════════════════════════


class CampaignIndex:
    """What is in market, keyed for attribution. Process-local; Redis at scale."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_campaign: dict[str, CampaignLog] = {}
        self._by_landing: dict[str, str] = {}

    def register(self, log_entry: CampaignLog) -> str:
        campaign_id = str(log_entry.campaign.get("campaign_id"))
        with self._lock:
            self._by_campaign[campaign_id] = log_entry
            for path in log_entry.tracking.get("landing_paths", []) or []:
                self._by_landing[str(path)] = campaign_id
        return campaign_id

    def attribute(self, lead: InboundLead) -> CampaignLog | None:
        with self._lock:
            if lead.utm_campaign and lead.utm_campaign in self._by_campaign:
                return self._by_campaign[lead.utm_campaign]
            if lead.landing_path:
                cid = self._by_landing.get(lead.landing_path)
                if cid:
                    return self._by_campaign.get(cid)
            return None

    def get(self, campaign_id: str) -> CampaignLog | None:
        with self._lock:
            return self._by_campaign.get(campaign_id)


class LeadStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._leads: dict[str, dict[str, Any]] = {}

    def put(self, lead_id: str, record: dict[str, Any]) -> None:
        with self._lock:
            self._leads[lead_id] = record

    def get(self, lead_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._leads.get(lead_id)

    def escalations(self) -> list[dict[str, Any]]:
        with self._lock:
            return [r for r in self._leads.values() if r.get("escalate")]


CAMPAIGNS = CampaignIndex()
LEADS = LeadStore()


# ══════════════════════════════════════════════════════════════════════════════
# 4. Qualification
# ══════════════════════════════════════════════════════════════════════════════

QUALIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "intent", "qualified", "party_size", "travel_window", "budget_band",
        "estimated_value_eur", "corporate_signal", "missing_information",
        "suggested_reply", "reply_language", "escalate", "escalation_reason",
        "confidence",
    ],
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "booking_enquiry", "price_enquiry", "availability", "general_info",
                "support", "complaint", "spam", "other",
            ],
        },
        "qualified": {"type": "boolean"},
        "party_size": {"type": "integer", "description": "0 when not stated."},
        "travel_window": {"type": "string", "description": "Empty string when not stated."},
        "budget_band": {
            "type": "string",
            "enum": ["unknown", "under_2k", "2k_5k", "5k_15k", "over_15k"],
        },
        "estimated_value_eur": {"type": "number", "description": "0 when not estimable."},
        "corporate_signal": {"type": "boolean"},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "suggested_reply": {"type": "string"},
        "reply_language": {"type": "string"},
        "escalate": {"type": "boolean"},
        "escalation_reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
}


def _fetch_rates(price_source: str | None) -> dict[str, Any]:
    """The only figures Agent 4 may quote. Unreachable feed ⇒ quote nothing."""
    if not price_source:
        return {"status": "unavailable", "note": "No price feed is attached to this campaign."}
    try:
        resp = requests.get(
            price_source, timeout=15, headers={"User-Agent": config.USER_AGENT}
        )
        resp.raise_for_status()
        return {
            "status": "available",
            "source": price_source,
            "asof": rfc3339(),
            "data": resp.json(),
        }
    except (requests.RequestException, ValueError) as exc:
        log.warning("rate feed %s unavailable: %s", price_source, exc)
        return {
            "status": "unavailable",
            "source": price_source,
            "note": "Feed unreachable. State that a current quote will follow; give no figure.",
        }


def _system_prompt(routing: LeadRouting, profile: str) -> str:
    threshold = routing.high_value_threshold
    return "\n".join(
        [
            "You qualify inbound travel enquiries for a luxury travel group and "
            "draft a reply for a human colleague to review and send.",
            "",
            "You are not authorised to contract, confirm, hold or guarantee "
            "anything. Your draft proposes; a person decides.",
            "",
            "PRICING: you may state a figure ONLY if it appears in the supplied "
            "live rate feed, and you must state when that price was read. If the "
            "feed is unavailable or does not cover what was asked, say a current "
            "quote will follow — never estimate, round, or reason your way to a "
            "number. A price without a timestamp is not a price.",
            "",
            f"ESCALATE to {routing.escalate_to} when the enquiry is worth "
            f"{threshold.get('amount')} {threshold.get('currency')} or more, is "
            "corporate/group/MICE/charter, asks for a written proposal, is a "
            "complaint, or concerns a refund or cancellation.",
            "",
            "NEVER ask for, repeat, or acknowledge card numbers, CVV codes, "
            "passport numbers or bank details. Anything already redacted stays "
            "redacted. Payment is arranged by a human, on a secure channel.",
            "",
            "The reply is warm, specific and brief — a knowledgeable colleague, "
            "not a chatbot. Answer what was asked, ask at most two questions "
            "back, and match the language the enquiry came in.",
            "",
            compliance.prompt_constraints(profile),
        ]
    )


def qualify(
    lead: InboundLead, clean_message: str, routing: LeadRouting, rates: dict[str, Any],
    campaign: CampaignLog | None, profile: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One Claude call. Same request-shape rules as Agent 3."""
    from anthropic import Anthropic

    client = Anthropic(api_key=config.require_env("ANTHROPIC_API_KEY"))

    user = json.dumps(
        {
            "enquiry": {
                "channel": lead.channel,
                "message": clean_message,
                "locale": lead.locale,
                "display_name": lead.display_name,
                "received_at": lead.received_at or rfc3339(),
            },
            "attribution": {
                "campaign_id": (campaign.campaign.get("campaign_id") if campaign else None),
                "article_url": (
                    campaign.source_publication.get("live_url") if campaign else None
                ),
                "landing_path": lead.landing_path,
            },
            "live_rate_feed": rates,
            "escalation_policy": {
                "high_value_threshold": routing.high_value_threshold,
                "signals": routing.auto_escalate_signals,
            },
        },
        ensure_ascii=False,
        indent=2,
    )

    kwargs: dict[str, Any] = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": 8000,
        "system": _system_prompt(routing, profile),
        "messages": [{"role": "user", "content": user}],
        "output_config": {
            "effort": config.ANTHROPIC_EFFORT,
            "format": {"type": "json_schema", "schema": QUALIFICATION_SCHEMA},
        },
    }
    use_fallbacks = config.ANTHROPIC_FALLBACKS.lower() not in {"", "off", "false", "0"}
    if use_fallbacks:
        kwargs["betas"] = [config.ANTHROPIC_FALLBACK_BETA]
        kwargs["fallbacks"] = config.ANTHROPIC_FALLBACKS

    started = time.time()
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            create = client.beta.messages.create if use_fallbacks else client.messages.create
            resp = create(**kwargs)

            if getattr(resp, "stop_reason", None) == "refusal":
                detail = getattr(resp, "stop_details", None)
                category = getattr(detail, "category", None) if detail else None
                raise RuntimeError(f"Claude declined the request (category={category!r})")

            text = "".join(
                b.text for b in resp.content if getattr(b, "type", "") == "text"
            ).strip()
            result = json.loads(text)
            usage = getattr(resp, "usage", None)
            meta = {
                "provider": "anthropic",
                "model": getattr(resp, "model", config.ANTHROPIC_MODEL),
                "effort": config.ANTHROPIC_EFFORT,
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "attempts": attempt,
                "duration_ms": int((time.time() - started) * 1000),
            }
            return result, meta
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            log.warning("claude attempt %d returned unusable output: %s", attempt, exc)
        except Exception as exc:
            last_error = exc
            log.warning("claude attempt %d failed: %s", attempt, exc)
        time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.4))

    raise RuntimeError(f"Claude failed after 3 attempts: {last_error}")


_HUMAN_ONLY = re.compile(
    r"(?i)\brefund\b|\bcancel(lation)?\b|\bcomplain|\bchargeback\b"
    r"|استرداد|کنسل|لغو|شکایت|عودت\s*وجه"
)


def decide_escalation(
    result: dict[str, Any], clean_message: str, routing: LeadRouting, redactions: list[str]
) -> tuple[bool, list[str]]:
    """
    Deterministic rules on top of the model's judgement. The model may escalate;
    only these rules may keep something OUT of a human's hands, and they are the
    ones that decide when it must go in.
    """
    reasons: list[str] = []
    haystack = clean_message.lower()

    threshold = float(routing.high_value_threshold.get("amount") or 0)
    if threshold and float(result.get("estimated_value_eur") or 0) >= threshold:
        reasons.append(
            f"estimated value ≥ {threshold:.0f} "
            f"{routing.high_value_threshold.get('currency', 'EUR')}"
        )

    # Signals are whole words or multi-character Persian phrases — never a bare
    # short token, for the same reason «رم» must not be matched inside «مارماریس».
    for signal in routing.auto_escalate_signals:
        token = str(signal).strip().lower()
        if not token:
            continue
        if token.isascii():
            if re.search(rf"\b{re.escape(token)}\b", haystack):
                reasons.append(f"signal term {signal!r}")
        elif len(token) >= 3 and token in haystack:
            reasons.append(f"signal term {signal!r}")

    if result.get("corporate_signal"):
        reasons.append("corporate/group signal")
    if result.get("intent") == "complaint":
        reasons.append("complaint")
    if _HUMAN_ONLY.search(clean_message):
        reasons.append("refund / cancellation / complaint language")
    if redactions:
        reasons.append("payment or identity data was sent — human handling required")
    if result.get("escalate"):
        reasons.append(str(result.get("escalation_reason") or "model escalated"))

    return bool(reasons), reasons


# ══════════════════════════════════════════════════════════════════════════════
# 5. Routes
# ══════════════════════════════════════════════════════════════════════════════


def _verify(request_body: bytes, sig: str | None, ts: str | None) -> None:
    secret = config.require_env("WEBHOOK_SIGNING_SECRET")
    ok, reason = config.verify_signature(secret, sig, ts, request_body)
    if not ok:
        log.warning("rejected delivery: %s", reason)
        raise HTTPException(status_code=401, detail=f"signature rejected: {reason}")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "agent": AGENT_ID,
        "schema_version": config.SCHEMA_VERSION,
        "model": config.ANTHROPIC_MODEL,
        "architecture_credit": config.ARCHITECTURE_CREDIT,
        "time": rfc3339(),
    }


@app.post("/webhooks/campaign-log", status_code=202)
async def receive_campaign_log(
    request: Request,
    x_albaloo_signature: str | None = Header(default=None),
    x_albaloo_timestamp: str | None = Header(default=None),
) -> JSONResponse:
    raw = await request.body()
    _verify(raw, x_albaloo_signature, x_albaloo_timestamp)

    try:
        entry = CampaignLog.model_validate(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc

    if entry.envelope.message_type != "campaign.log":
        raise HTTPException(
            status_code=400,
            detail=f"expected campaign.log, got {entry.envelope.message_type}",
        )
    if entry.envelope.architecture_credit != config.ARCHITECTURE_CREDIT:
        raise HTTPException(
            status_code=400,
            detail=f"envelope.architecture_credit must be {config.ARCHITECTURE_CREDIT!r}",
        )

    campaign_id = CAMPAIGNS.register(entry)
    log.info("registered campaign %s (%d post(s))", campaign_id, len(entry.posts))
    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "campaign_id": campaign_id,
            "architecture_credit": config.ARCHITECTURE_CREDIT,
        },
    )


@app.post("/leads/inbound")
async def inbound_lead(
    request: Request,
    x_albaloo_signature: str | None = Header(default=None),
    x_albaloo_timestamp: str | None = Header(default=None),
) -> dict[str, Any]:
    raw = await request.body()
    _verify(raw, x_albaloo_signature, x_albaloo_timestamp)

    try:
        lead = InboundLead.model_validate(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc

    # Redaction happens first — before the model, before the log line, before
    # anything is stored. The raw message is never retained.
    clean_message, redactions = redact(lead.message)
    if redactions:
        log.warning("lead from %s contained %s — redacted", lead.channel, redactions)

    campaign = CAMPAIGNS.attribute(lead)
    routing = campaign.lead_routing if campaign else LeadRouting()
    profile = str((campaign.compliance.get("profile") if campaign else None) or "boutimar_v1")
    if profile not in compliance.PROFILES:
        profile = "boutimar_v1"

    rates = _fetch_rates(routing.price_source)
    lead_id = f"lead_{utc_now():%Y%m%dT%H%M%S}Z_{abs(hash(lead.from_ref)) % 10**6:06d}"

    try:
        result, meta = qualify(lead, clean_message, routing, rates, campaign, profile)
    except Exception as exc:
        LEADS.put(lead_id, {
            "lead_id": lead_id, "status": "failed", "error": str(exc),
            "channel": lead.channel, "received_at": rfc3339(),
        })
        log.exception("qualification failed for %s", lead_id)
        raise HTTPException(status_code=502, detail="qualification failed") from exc

    # The compliance gate on the drafted reply. A draft that quotes an
    # unsourced price never reaches the human queue, let alone the customer.
    priced = rates.get("status") == "available"
    reply = str(result.get("suggested_reply", ""))
    violations = compliance.check(
        reply,
        profile,
        context={"priced_facts": priced, "price_asof": rates.get("asof")},
    )
    blocking = [v for v in violations if v.severity == compliance.BLOCK]
    if blocking:
        log.error(
            "%s — drafted reply blocked: %s",
            lead_id, "; ".join(f"{v.rule}: {v.message}" for v in blocking),
        )
        reply = ""

    escalate, reasons = decide_escalation(result, clean_message, routing, redactions)

    record = {
        "lead_id": lead_id,
        "status": "qualified",
        "received_at": lead.received_at or rfc3339(),
        "channel": lead.channel,
        "from_ref": lead.from_ref,
        "message_redacted": clean_message,
        "redactions": redactions,
        "campaign_id": (campaign.campaign.get("campaign_id") if campaign else None),
        "attributed": campaign is not None,
        "qualification": {k: v for k, v in result.items() if k != "suggested_reply"},
        "draft_reply": {
            # Draft only. Agent 4 sends nothing — a human releases this.
            "text": reply,
            "language": result.get("reply_language"),
            "blocked": bool(blocking),
            "blocked_reasons": [v.as_dict() for v in blocking],
            "sent": False,
        },
        "price_context": {
            "status": rates.get("status"),
            "source": rates.get("source"),
            "asof": rates.get("asof"),
        },
        "escalate": escalate,
        "escalation_reasons": reasons,
        "escalate_to": routing.escalate_to if escalate else None,
        "compliance": compliance.summarise(violations, profile),
        "generation": meta,
        "architecture_credit": config.ARCHITECTURE_CREDIT,
    }
    LEADS.put(lead_id, record)

    log.info(
        "%s — %s / %s%s",
        lead_id, result.get("intent"),
        "qualified" if result.get("qualified") else "not qualified",
        f" → ESCALATE ({'; '.join(reasons)})" if escalate else "",
    )
    return record


@app.get("/leads/{lead_id}")
def lead_status(lead_id: str) -> dict[str, Any]:
    record = LEADS.get(lead_id)
    if not record:
        raise HTTPException(status_code=404, detail="unknown lead_id")
    return record


@app.get("/escalations")
def escalations() -> dict[str, Any]:
    items = LEADS.escalations()
    return {"count": len(items), "leads": items, "generated_at": rfc3339()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent4_sales_closer:app",
        host=config.optional_env("AGENT4_HOST", "0.0.0.0"),
        port=int(config.optional_env("AGENT4_PORT", "8082")),
        reload=False,
        workers=1,
    )
