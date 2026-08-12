#!/usr/bin/env python3
"""
Agent 3 — The Marketing Broadcaster.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Receives `publishing.event.v1` from Agent 2, writes platform-specific copy with
Claude — LinkedIn for B2B, Instagram and Telegram for D2C — queues it through
the configured scheduler, and emits `campaign.log.v1` to Agent 4.

    uvicorn agent3_broadcaster:app --host 0.0.0.0 --port 8081

The load-bearing constraint: **Agent 3 asserts no new facts.** It may only
recombine `content_summary.key_points`, `quotable_lines` and `offer`; anything
else is a link to the article. That is the mechanism that stops an invented
rate reaching Instagram (ARCHITECTURE.md §5).
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from datetime import timedelta
from typing import Any, Literal
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import compliance
import config
import llm
from config import build_envelope, rfc3339, utc_now
from scheduler import Scheduler, autopost_allowed, media_ok

log = logging.getLogger("agent3.broadcaster")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

AGENT_ID = "agent3.broadcaster"
TARGET_ID = "agent4.closer"

CHANNELS = ("linkedin", "instagram", "telegram", "x", "facebook", "email")
B2B_CHANNELS = {"linkedin", "email"}

app = FastAPI(
    title="Albaloo Orchestrator — Agent 3 (Broadcaster)",
    version="1.0.0",
    description=(
        "Publishing-event listener and channel copywriter. "
        f"Architecture credit: {config.ARCHITECTURE_CREDIT} — {config.ARCHITECTURE_URL}"
    ),
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Inbound payload — publishing.event.v1 (ARCHITECTURE.md §4.2)
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


class SourceBrief(_Loose):
    message_id: str
    correlation_id: str
    primary_keyword: str
    gap_type: str | None = None
    passthrough: dict[str, Any] = Field(default_factory=dict)


class Publication(_Loose):
    status: Literal["published", "scheduled", "draft", "failed"]
    # Nullable: an adapter that staged a draft has no live URL, and the schema
    # used to force one, which is how phantom URLs entered the pipeline.
    live_url: str | None = None
    intended_url: str | None = None
    canonical_url: str | None = None
    cms: dict[str, Any] = Field(default_factory=dict)
    published_at: str | None = None
    scheduled_for: str | None = None
    language: str = "en"
    word_count: int = 0
    reading_time_min: int = 0
    hero_image: dict[str, Any] | None = None
    indexation: dict[str, Any] = Field(default_factory=dict)


class Offer(_Loose):
    has_offer: bool = False
    product_ref: str | None = None
    price_from: dict[str, Any] | None = None
    price_source: str | None = None
    price_asof: str | None = None
    departure_window: dict[str, Any] | None = None
    visa_regime: str | None = None


class ContentSummary(_Loose):
    title: str
    meta_description: str = ""
    key_points: list[str] = Field(default_factory=list)
    primary_keyword: str = ""
    audience: Literal["d2c", "b2b", "both"] = "d2c"
    offer: Offer = Field(default_factory=Offer)
    quotable_lines: list[str] = Field(default_factory=list)


class DistributionHints(_Loose):
    channels: list[str] = Field(default_factory=list)
    b2b_angle: str | None = None
    d2c_angle: str | None = None
    cta_url: str | None = None
    utm: dict[str, Any] = Field(default_factory=dict)
    hashtags_allowed: bool = True
    embargo_until: str | None = None
    assets: list[dict[str, Any]] = Field(default_factory=list)


class PublishingEvent(_Loose):
    schema_version: str
    envelope: Envelope
    source_brief: SourceBrief
    publication: Publication
    content_summary: ContentSummary
    distribution_hints: DistributionHints = Field(default_factory=DistributionHints)
    compliance: dict[str, Any] = Field(default_factory=dict)
    generation: dict[str, Any] = Field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Idempotency
# ══════════════════════════════════════════════════════════════════════════════


class CampaignRegistry:
    """Process-local. Multi-worker deployments need Redis — see Agent 2's note."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._campaigns: dict[str, dict[str, Any]] = {}

    def claim(self, idem_key: str, campaign_id: str) -> tuple[bool, dict[str, Any]]:
        with self._lock:
            existing = self._campaigns.get(idem_key)
            if existing:
                return False, existing
            entry = {
                "campaign_id": campaign_id,
                "status": "accepted",
                "created_at": rfc3339(),
                "posts": [],
                "error": None,
            }
            self._campaigns[idem_key] = entry
            return True, entry

    def update(self, idem_key: str, **fields: Any) -> None:
        with self._lock:
            entry = self._campaigns.get(idem_key)
            if entry:
                entry.update(fields)

    def get(self, campaign_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (c for c in self._campaigns.values() if c["campaign_id"] == campaign_id),
                None,
            )

    def release(self, idem_key: str) -> None:
        with self._lock:
            self._campaigns.pop(idem_key, None)


CAMPAIGNS = CampaignRegistry()
SCHEDULER = Scheduler()


# ══════════════════════════════════════════════════════════════════════════════
# 3. Routes
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "agent": AGENT_ID,
        "schema_version": config.SCHEMA_VERSION,
        "model": config.ANTHROPIC_MODEL,
        "scheduler_backend": SCHEDULER.backend,
        "autopost_enabled": config.ALLOW_AUTOPOST,
        "architecture_credit": config.ARCHITECTURE_CREDIT,
        "time": rfc3339(),
    }


@app.get("/campaigns/{campaign_id}")
def campaign_status(campaign_id: str) -> dict[str, Any]:
    entry = CAMPAIGNS.get(campaign_id)
    if not entry:
        raise HTTPException(status_code=404, detail="unknown campaign_id")
    return entry


@app.post("/webhooks/publishing", status_code=202)
async def receive_publishing_event(
    request: Request,
    background: BackgroundTasks,
    x_albaloo_signature: str | None = Header(default=None),
    x_albaloo_timestamp: str | None = Header(default=None),
) -> JSONResponse:
    raw = await request.body()

    secret = config.require_env("WEBHOOK_SIGNING_SECRET")
    ok, reason = config.verify_signature(secret, x_albaloo_signature, x_albaloo_timestamp, raw)
    if not ok:
        log.warning("rejected delivery: %s", reason)
        raise HTTPException(status_code=401, detail=f"signature rejected: {reason}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

    try:
        event = PublishingEvent.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc

    if event.envelope.message_type != "publishing.event":
        raise HTTPException(
            status_code=400,
            detail=f"expected publishing.event, got {event.envelope.message_type}",
        )
    if event.envelope.architecture_credit != config.ARCHITECTURE_CREDIT:
        raise HTTPException(
            status_code=400,
            detail=f"envelope.architecture_credit must be {config.ARCHITECTURE_CREDIT!r}",
        )
    if event.publication.status == "failed":
        raise HTTPException(status_code=400, detail="refusing to broadcast a failed publication")

    campaign_id = _campaign_id(event)
    is_new, entry = CAMPAIGNS.claim(event.envelope.idempotency_key, campaign_id)
    if not is_new:
        return JSONResponse(
            status_code=200,
            content={"accepted": True, "duplicate": True, **_ack(event, entry)},
        )

    background.add_task(run_broadcast_job, event, payload)
    log.info(
        "accepted %s — %s → campaign %s",
        event.envelope.message_id, event.publication.live_url, campaign_id,
    )
    return JSONResponse(status_code=202, content={"accepted": True, **_ack(event, entry)})


def _ack(event: PublishingEvent, entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "message_id": event.envelope.message_id,
        "correlation_id": event.envelope.correlation_id,
        "campaign_id": entry["campaign_id"],
        "status": entry["status"],
        "architecture_credit": config.ARCHITECTURE_CREDIT,
    }


def _campaign_id(event: PublishingEvent) -> str:
    hinted = (event.distribution_hints.utm or {}).get("campaign")
    if hinted and hinted != "{channel}":
        return str(hinted)
    path = urlparse(event.publication.live_url).path.strip("/").replace("/", "-")
    return path or event.source_brief.correlation_id


# ══════════════════════════════════════════════════════════════════════════════
# 4. Claude — one call, all channels
# ══════════════════════════════════════════════════════════════════════════════

CHANNEL_BRIEFS = {
    "linkedin": (
        "B2B. Travel-trade professionals: agency owners, product managers, "
        "corporate buyers. Lead with the commercial fact — routing, allotment, "
        "commission, seasonality. 120–200 words, no emoji, no hashtag spam "
        "(2 at most). A first line that works as a standalone hook."
    ),
    "instagram": (
        "D2C. Caption for a single image. Open with an image that is a sentence, "
        "not a slogan. 60–120 words. Sensory and specific. Emoji sparingly (0–2). "
        "Hashtags at the end, 5–10, mixed reach."
    ),
    "telegram": (
        "D2C, Iran. Short broadcast message, 50–100 words. Direct and practical: "
        "what it is, who it suits, what to do next. Farsi if the article is Farsi. "
        "No hashtags. Telegram renders no markdown tables — plain lines only."
    ),
    "x": "D2C. Under 260 characters including the link. One idea. No thread.",
    "facebook": "D2C. 80–150 words, conversational, one clear call to action.",
    "email": (
        "B2B teaser for the agent newsletter. Subject line as the first line, then "
        "80–120 words of body. No greeting, no signature — the template supplies both."
    ),
}

CHANNEL_COPY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["posts"],
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["channel", "audience", "language", "body", "hashtags", "angle"],
                "properties": {
                    "channel": {"type": "string", "enum": list(CHANNELS)},
                    "audience": {"type": "string", "enum": ["d2c", "b2b"]},
                    "language": {"type": "string"},
                    "body": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                    "angle": {
                        "type": "string",
                        "description": "One line on why this framing was chosen for this channel.",
                    },
                },
            },
        }
    },
}


def _system_prompt(event: PublishingEvent, profile: str) -> str:
    return "\n".join(
        [
            "You write channel-specific promotional copy for a luxury travel group.",
            "",
            "THE ONE RULE THAT OVERRIDES EVERYTHING ELSE: you may not assert a "
            "single fact that is not in the supplied material. You recombine "
            "key_points, quotable_lines and offer, and you link to the article "
            "for anything else. No invented price, date, duration, port, "
            "inclusion, discount, availability claim or superlative-as-fact. If a "
            "channel brief asks for detail the material does not contain, write "
            "around it — do not fill the gap.",
            "",
            "quotable_lines may be reused verbatim. Everything else you write "
            "fresh, in that channel's register.",
            "",
            f"Article language: {event.publication.language}. Match it unless the "
            "channel brief says otherwise.",
            "",
            "VOICE: poetic, experience-led luxury — a senior guide who has sailed "
            "the route, not a brochure. Evocative AND specific. Never stack three "
            "adjectives where one exact noun works.",
            "",
            compliance.prompt_constraints(profile),
            "",
            "Do not put the CTA URL in the body — it is appended per channel with "
            "its own UTM parameters.",
        ]
    )


def _user_prompt(event: PublishingEvent, channels: list[str]) -> str:
    cs = event.content_summary
    return json.dumps(
        {
            "article": {
                "title": cs.title,
                "summary": cs.meta_description,
                "language": event.publication.language,
                "url": event.publication.live_url,
                "primary_keyword": cs.primary_keyword,
                "reading_time_min": event.publication.reading_time_min,
            },
            "material_you_may_use": {
                "key_points": cs.key_points,
                "quotable_lines": cs.quotable_lines,
                "offer": cs.offer.model_dump(),
            },
            "angles": {
                "b2b": event.distribution_hints.b2b_angle,
                "d2c": event.distribution_hints.d2c_angle,
            },
            "hashtags_allowed": event.distribution_hints.hashtags_allowed,
            "channels": [
                {
                    "channel": ch,
                    "audience": "b2b" if ch in B2B_CHANNELS else "d2c",
                    "brief": CHANNEL_BRIEFS.get(ch, "Short promotional post."),
                }
                for ch in channels
            ],
            "instruction": "Write exactly one post per channel listed.",
        },
        ensure_ascii=False,
        indent=2,
    )


def _call_claude(event: PublishingEvent, channels: list[str], profile: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    One batched call covering every channel.

    Request-shape notes for this model family: no temperature/top_p/top_k (they
    are a 400), no assistant prefill (also a 400), thinking is on by default and
    `budget_tokens` is a 400 — depth is `output_config.effort`. Structured output
    replaces the prefill trick entirely.
    """
    system = _system_prompt(event, profile)
    prompt = _user_prompt(event, channels)
    # Gemini's JSON mode fixes validity, not shape, so the envelope goes in the
    # prompt. Agent 1 got a bare array where it expected an object by leaving
    # this to the provider.
    if config.PROSE_PROVIDER == "gemini":
        system += ('\n\nReturn a single JSON object of exactly this shape:\n'
                   '{"posts": [ <post>, ... ]}\n'
                   "The top level is an OBJECT with the key \"posts\", never a bare "
                   "array. Each post matches this JSON Schema:\n"
                   + json.dumps(CHANNEL_COPY_SCHEMA["properties"]["posts"]["items"],
                                ensure_ascii=False))

    started = time.time()
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            data, meta = llm.complete_json(
                system, prompt, CHANNEL_COPY_SCHEMA,
                max_tokens=16000, purpose="channel copy",
            )
            posts = data.get("posts", []) if isinstance(data, dict) else data
            if not posts:
                raise ValueError("model returned no posts")
            meta = {**meta, "attempts": attempt,
                    "duration_ms": int((time.time() - started) * 1000)}
            return posts, meta
        except llm.ProviderUnavailable:
            # Unfunded, rate-limited or refused: no retry inside this run helps,
            # and the caller already treats it as a hold rather than a failure.
            raise
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
            log.warning("copy attempt %d returned unusable output: %s", attempt, exc)
        except Exception as exc:
            last_error = exc
            log.warning("copy attempt %d failed: %s", attempt, exc)
        time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.4))

    raise RuntimeError(f"channel copy failed after 3 attempts: {last_error}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Assembly
# ══════════════════════════════════════════════════════════════════════════════


def _resolve_channels(event: PublishingEvent) -> list[dict[str, Any]]:
    """
    Channels come from sites.yml, not from the payload — that is where autopost
    lives, and a payload must never be able to grant itself posting rights.
    """
    domain = urlparse(event.publication.live_url).netloc.lower().removeprefix("www.")
    try:
        sites = config.load_sites(only=[domain])
        configured = sites[0].channels
    except config.ConfigError:
        log.warning("%s is not in sites.yml — falling back to the payload hints", domain)
        configured = [
            {"name": c, "audience": "b2b" if c in B2B_CHANNELS else "d2c", "autopost": False}
            for c in event.distribution_hints.channels
        ]

    out = [c for c in configured if c.get("name") in CHANNELS]
    if event.distribution_hints.channels:
        wanted = set(event.distribution_hints.channels)
        narrowed = [c for c in out if c["name"] in wanted]
        if narrowed:
            out = narrowed
    return out


def _with_utm(url: str, channel: str, campaign_id: str, utm: dict[str, Any]) -> str:
    parts = urlparse(url)
    params = {
        "utm_source": channel,
        "utm_medium": str(utm.get("medium") or "social"),
        "utm_campaign": campaign_id,
    }
    query = f"{parts.query}&{urlencode(params)}" if parts.query else urlencode(params)
    return urlunparse(parts._replace(query=query))


def _schedule_times(count: int, priority_now: bool) -> list[str]:
    """Stagger channels so one article does not carpet every feed at once."""
    base = utc_now() + (timedelta(minutes=15) if priority_now else timedelta(hours=3))
    return [rfc3339(base + timedelta(hours=2 * i)) for i in range(count)]


def build_campaign_log(
    event: PublishingEvent,
    campaign_id: str,
    posts: list[dict[str, Any]],
    violations: list[compliance.Violation],
    profile: str,
) -> dict[str, Any]:
    """campaign.log.v1 — ARCHITECTURE.md §4.3."""
    cs = event.content_summary
    audience = "b2b" if all(p["audience"] == "b2b" for p in posts) else (
        "d2c" if all(p["audience"] == "d2c" for p in posts) else "both"
    )
    brand = urlparse(event.publication.live_url).netloc.removeprefix("www.")

    return {
        "schema_version": config.SCHEMA_VERSION,
        "envelope": build_envelope(
            message_type="campaign.log",
            emitted_by=AGENT_ID,
            target=TARGET_ID,
            correlation_id=event.envelope.correlation_id,
            idem_key=event.envelope.idempotency_key,
            causation_id=event.envelope.message_id,
        ),
        "source_publication": {
            "message_id": event.envelope.message_id,
            "correlation_id": event.envelope.correlation_id,
            "live_url": event.publication.live_url,
            "brand": brand,
            "language": event.publication.language,
        },
        "campaign": {
            "campaign_id": campaign_id,
            "objective": "lead" if cs.offer.has_offer else "traffic",
            "audience": audience,
            "window": {
                "start": posts[0]["scheduled_for"] if posts else rfc3339(),
                "end": rfc3339(utc_now() + timedelta(days=14)),
            },
        },
        "posts": posts,
        "tracking": {
            "utm_campaign": campaign_id,
            "short_links": [],
            "landing_paths": [urlparse(event.publication.live_url).path],
        },
        "lead_routing": {
            "inboxes": ["site_chat", "whatsapp", "instagram_dm"],
            "qualification_profile": "cruise_d2c_v1",
            "price_source": cs.offer.price_source,
            "quote_policy": "live_feed_only",
            "high_value_threshold": {"amount": 15000, "currency": "EUR"},
            "escalate_to": "alireza",
            "auto_escalate_signals": [
                "group", "MICE", "charter", "corporate", "incentive",
                "شرکتی", "گروهی", "دربست",
            ],
        },
        "compliance": {
            "profile": profile,
            **compliance.summarise(violations, profile),
            "reviewed_by": AGENT_ID,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. The job
# ══════════════════════════════════════════════════════════════════════════════


def run_broadcast_job(event: PublishingEvent, raw_payload: dict[str, Any]) -> None:
    idem = event.envelope.idempotency_key
    campaign_id = _campaign_id(event)
    profile = str(event.compliance.get("profile") or "boutimar_v1")
    if profile not in compliance.PROFILES:
        profile = "boutimar_v1"

    CAMPAIGNS.update(idem, status="composing")
    try:
        channel_cfgs = _resolve_channels(event)
        if not channel_cfgs:
            CAMPAIGNS.update(idem, status="skipped", error="no channels configured")
            log.info("%s — no channels configured; nothing to broadcast", campaign_id)
            return

        names = [c["name"] for c in channel_cfgs]
        drafts, gen_meta = _call_claude(event, names, profile)

        # The compliance gate on the OUTPUT. Copy that carries an invented rate
        # or "Arabian Gulf" never reaches a scheduler, let alone a feed.
        priced = event.content_summary.offer.has_offer
        ctx = {
            "priced_facts": priced,
            "price_asof": event.content_summary.offer.price_asof if priced else None,
            "itinerary_ports": event.content_summary.key_points,
        }
        warnings: list[compliance.Violation] = []
        for draft in drafts:
            surface = draft["body"] + " " + " ".join(draft.get("hashtags", []))
            warnings.extend(compliance.enforce(surface, profile, context=ctx))

        CAMPAIGNS.update(idem, status="scheduling")
        times = _schedule_times(len(drafts), priority_now=False)
        by_name = {c["name"]: c for c in channel_cfgs}
        posts: list[dict[str, Any]] = []

        for draft, when in zip(drafts, times):
            channel = draft["channel"]
            cfg = by_name.get(channel, {"name": channel, "autopost": False})
            cta = _with_utm(
                event.distribution_hints.cta_url or event.publication.live_url,
                channel, campaign_id, event.distribution_hints.utm,
            )
            post = {
                "channel": channel,
                "audience": draft["audience"],
                "account_ref": cfg.get("account_ref"),
                "status": "scheduled",
                "scheduled_for": when,
                "published_at": None,
                "external_id": None,
                "permalink": None,
                "copy": {
                    "body": draft["body"],
                    "hashtags": draft.get("hashtags", []),
                    "cta_url": cta,
                    "language": draft.get("language", event.publication.language),
                    # Dedupe guard: identical copy is never posted twice to one
                    # channel, however many times the event is redelivered.
                    "hash": "sha256:" + hashlib.sha256(
                        f"{channel}|{draft['body']}".encode("utf-8")
                    ).hexdigest(),
                },
                "assets": event.distribution_hints.assets,
                "angle": draft.get("angle"),
                "error": None,
            }

            result = SCHEDULER.schedule(
                post=post,
                channel_cfg=cfg,
                campaign_id=campaign_id,
                correlation_id=event.envelope.correlation_id,
            )
            post.update(
                status=result.status,
                external_id=result.external_id,
                permalink=result.permalink,
                error=result.error,
            )
            # Why this post is not live, most specific reason first. A missing
            # image is a harder stop than a closed autopost gate: no amount of
            # flag-flipping publishes an Instagram post with nothing attached.
            has_media, media_reason = media_ok(post)
            allowed, gate_reason = autopost_allowed(cfg)
            if not has_media:
                post["hold_reason"] = media_reason
            elif not allowed:
                post["hold_reason"] = gate_reason
            posts.append(post)

        CAMPAIGNS.update(idem, status="scheduled", posts=posts)
        blocked = sum(1 for p in posts if p["status"] == "blocked")
        held = sum(1 for p in posts if p.get("hold_reason")) - blocked
        log.info(
            "%s — %d post(s) composed: %d live, %d held for approval, %d blocked on media",
            campaign_id, len(posts), len(posts) - held - blocked, held, blocked,
        )

        campaign_log = build_campaign_log(event, campaign_id, posts, warnings, profile)
        callback = config.optional_env("AGENT4_WEBHOOK_URL")
        if not callback:
            log.warning("AGENT4_WEBHOOK_URL not set — campaign.log not forwarded")
            return
        ok, reason = _deliver(callback, campaign_log, config.require_env("WEBHOOK_SIGNING_SECRET"))
        if not ok:
            CAMPAIGNS.update(idem, error=f"forward failed: {reason}")
            log.error("forward to agent4 failed: %s", reason)

    except compliance.ComplianceError as exc:
        blocked = [v.as_dict() for v in exc.violations if v.severity == compliance.BLOCK]
        CAMPAIGNS.update(idem, status="blocked", error=str(exc))
        log.error(
            "%s — copy BLOCKED by the compliance gate: %s",
            campaign_id, json.dumps(blocked, ensure_ascii=False)[:500],
        )
        CAMPAIGNS.release(idem)
    except Exception as exc:
        CAMPAIGNS.update(idem, status="failed", error=str(exc))
        log.exception("%s — broadcast job failed: %s", campaign_id, exc)
        CAMPAIGNS.release(idem)


def _deliver(url: str, payload: dict[str, Any], secret: str) -> tuple[bool, str]:
    message_id = payload["envelope"]["message_id"]
    reason = "not attempted"
    for attempt in range(1, config.WEBHOOK_MAX_ATTEMPTS + 1):
        payload["envelope"]["attempt"] = attempt
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            resp = requests.post(
                url,
                data=body,
                headers=config.signed_headers(secret, body, message_id),
                timeout=config.WEBHOOK_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            reason = f"transport error: {exc}"
        else:
            if 200 <= resp.status_code < 300:
                return True, str(resp.status_code)
            reason = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in (408, 429) and resp.status_code < 500:
                return False, reason
        if attempt == config.WEBHOOK_MAX_ATTEMPTS:
            return False, reason
        time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.5))
    return False, "exhausted"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent3_broadcaster:app",
        host=config.optional_env("AGENT3_HOST", "0.0.0.0"),
        port=int(config.optional_env("AGENT3_PORT", "8081")),
        reload=False,
        workers=1,
    )
