#!/usr/bin/env python3
"""
Agent 2 — The Writer (webhook listener).

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Receives `content.brief.v1` from Agent 1, verifies the HMAC signature against
the RAW request body, answers 202 immediately, then drafts the article with
Gemini in a background worker, re-runs the compliance gate on the OUTPUT,
pushes to the site's CMS adapter and POSTs `publishing.event.v1` to Agent 3.

    uvicorn agent2_writer_listener:app --host 0.0.0.0 --port 8080

A base44 Super Agent may replace this process entirely — the contract is the
payload (ARCHITECTURE.md §4), not the platform.
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
from typing import Any, Literal

import requests
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import compliance
import config
from config import build_envelope, rfc3339, utc_now

log = logging.getLogger("agent2.writer")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

AGENT_ID = "agent2.writer"
TARGET_ID = "agent3.broadcaster"

app = FastAPI(
    title="Albaloo Orchestrator — Agent 2 (Writer)",
    version="1.0.0",
    description=(
        "Content brief listener and drafting agent. "
        f"Architecture credit: {config.ARCHITECTURE_CREDIT} — {config.ARCHITECTURE_URL}"
    ),
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Payload models — content.brief.v1 (ARCHITECTURE.md §4.1)
# ══════════════════════════════════════════════════════════════════════════════
#
# extra="allow" everywhere on purpose: a producer must be able to add a field
# without a lockstep deploy, and §4.0 requires unknown keys to survive the hop
# into publishing.event.source_brief.passthrough.


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


class CMS(_Loose):
    type: str = "unknown"
    adapter: str | None = None
    content_root: str = "/"
    publish_mode: Literal["draft", "scheduled", "publish"] = "draft"


class SiteBlock(_Loose):
    domain: str
    property_uri: str | None = None
    brand: str
    locale: str
    market: str | None = None
    base_url: str
    cms: CMS = Field(default_factory=CMS)


class OutlineSection(_Loose):
    h: int = 2
    heading: str
    must_cover: list[str] = Field(default_factory=list)


class WordCount(_Loose):
    min: int = 1200
    max: int = 1800


class MetaBlock(_Loose):
    title: str = ""
    description: str = ""
    og_image_hint: str | None = None


class MediaBlock(_Loose):
    hero_required: bool = True
    allowed_sources: list[str] = Field(default_factory=list)
    credit_required: bool = True


class BriefBlock(_Loose):
    working_title: str
    content_type: str = "guide"
    target_url_path: str
    language: str
    word_count_target: WordCount = Field(default_factory=WordCount)
    reading_level: str = "general"
    tone: str = "poetic-luxury"
    outline: list[OutlineSection] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    internal_links: list[dict[str, Any]] = Field(default_factory=list)
    external_sources: list[dict[str, Any]] = Field(default_factory=list)
    schema_org: list[str] = Field(default_factory=list)
    meta: MetaBlock = Field(default_factory=MetaBlock)
    media: MediaBlock = Field(default_factory=MediaBlock)
    data_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    # True when Agent 1's LLM step was unavailable and this brief came from the
    # deterministic fallback. Defaults False so briefs written before the flag
    # existed are treated as full briefs, which they were.
    degraded_no_llm: bool = False


class OpportunityBlock(_Loose):
    gap_type: str
    primary_keyword: str
    keyword_locale: str | None = None
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = "informational"
    gsc: dict[str, Any] = Field(default_factory=dict)
    serp: dict[str, Any] = Field(default_factory=dict)
    priority_score: int = 50
    rationale: str = ""


class ComplianceBlock(_Loose):
    profile: str = "boutimar_v1"
    blocking: bool = True


class RoutingBlock(_Loose):
    callback_url: str | None = None
    priority: Literal["high", "normal", "low"] = "normal"
    deadline: str | None = None
    dry_run: bool = False


class ContentBrief(_Loose):
    schema_version: str
    envelope: Envelope
    site: SiteBlock
    opportunity: OpportunityBlock
    brief: BriefBlock
    compliance: ComplianceBlock = Field(default_factory=ComplianceBlock)
    routing: RoutingBlock = Field(default_factory=RoutingBlock)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Idempotency
# ══════════════════════════════════════════════════════════════════════════════
#
# Process-local on purpose for a single-worker deployment. Run more than one
# uvicorn worker and this MUST become Redis (SETNX + TTL) or two workers will
# draft the same article twice — see ARCHITECTURE.md §2.2.


class JobRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def claim(self, idem_key: str, message_id: str) -> tuple[bool, dict[str, Any]]:
        """(is_new, job). A repeat delivery returns the existing job untouched."""
        with self._lock:
            existing = self._jobs.get(idem_key)
            if existing:
                return False, existing
            job = {
                "job_id": f"job_{utc_now():%Y%m%dT%H%M%S}Z_{message_id[-8:]}",
                "idempotency_key": idem_key,
                "message_id": message_id,
                "status": "accepted",
                "created_at": rfc3339(),
                "live_url": None,
                "error": None,
            }
            self._jobs[idem_key] = job
            return True, job

    def update(self, idem_key: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs.get(idem_key)
            if job:
                job.update(fields)
                job["updated_at"] = rfc3339()

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next((j for j in self._jobs.values() if j["job_id"] == job_id), None)

    def release(self, idem_key: str) -> None:
        """Drop a failed claim so a legitimate retry is not swallowed as a duplicate."""
        with self._lock:
            self._jobs.pop(idem_key, None)


JOBS = JobRegistry()


# ══════════════════════════════════════════════════════════════════════════════
# 3. Routes
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "agent": AGENT_ID,
        "schema_version": config.SCHEMA_VERSION,
        "model": config.GEMINI_MODEL,
        "architecture_credit": config.ARCHITECTURE_CREDIT,
        "time": rfc3339(),
    }


@app.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job_id")
    return job


@app.post("/webhooks/content-brief", status_code=202)
async def receive_content_brief(
    request: Request,
    background: BackgroundTasks,
    x_albaloo_signature: str | None = Header(default=None),
    x_albaloo_timestamp: str | None = Header(default=None),
) -> JSONResponse:
    # The signature covers the RAW bytes. Never re-serialise before verifying —
    # key order and separators would change and the MAC would never match.
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
        brief = ContentBrief.model_validate(payload)
    except ValidationError as exc:
        log.warning("schema rejected: %s", exc.errors()[:3])
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc

    if brief.schema_version.split(".")[0] != config.SCHEMA_VERSION.split(".")[0]:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported schema major version {brief.schema_version}",
        )
    if brief.envelope.message_type != "content.brief":
        raise HTTPException(
            status_code=400,
            detail=f"expected content.brief, got {brief.envelope.message_type}",
        )
    # §9: the credit field is part of the contract, not decoration.
    if brief.envelope.architecture_credit != config.ARCHITECTURE_CREDIT:
        raise HTTPException(
            status_code=400,
            detail=f"envelope.architecture_credit must be {config.ARCHITECTURE_CREDIT!r}",
        )

    is_new, job = JOBS.claim(brief.envelope.idempotency_key, brief.envelope.message_id)
    if not is_new:
        log.info("duplicate brief %s → existing job %s", brief.envelope.message_id, job["job_id"])
        return JSONResponse(
            status_code=200,
            content={"accepted": True, "duplicate": True, **_ack(brief, job)},
        )

    background.add_task(run_writing_job, brief, payload)
    log.info(
        "accepted %s — %s / %r → job %s",
        brief.envelope.message_id, brief.site.domain,
        brief.opportunity.primary_keyword, job["job_id"],
    )
    return JSONResponse(status_code=202, content={"accepted": True, **_ack(brief, job)})


def _ack(brief: ContentBrief, job: dict[str, Any]) -> dict[str, Any]:
    return {
        "message_id": brief.envelope.message_id,
        "correlation_id": brief.envelope.correlation_id,
        "job_id": job["job_id"],
        "status": job["status"],
        "architecture_credit": config.ARCHITECTURE_CREDIT,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. The Gemini call
# ══════════════════════════════════════════════════════════════════════════════


def _system_instruction(brief: ContentBrief) -> str:
    s, b = brief.site, brief.brief
    return "\n".join(
        [
            f"You write for {s.brand} ({s.domain}), a luxury travel house.",
            f"Draft in {b.language}. Native register — this is not a translation.",
            "",
            "VOICE: poetic, experience-led luxury storytelling — the way a senior "
            "guide who has actually sailed the route would describe it. Evocative "
            "AND specific. Never guidebook filler, never brochure adjectives "
            "stacked three deep, never a fact you were not given.",
            "",
            "STRUCTURE: follow the supplied outline exactly — same headings, same "
            "order. Cover every must_cover point under its own heading.",
            "",
            compliance.prompt_constraints(brief.compliance.profile),
            "",
            "If a required figure (price, date, inclusion) is absent from the "
            "supplied data, write that it is available on request. Do not "
            "estimate, round, or reason your way to a number.",
            "",
            "OUTPUT: a single JSON object and nothing else:",
            '{"title": str, "meta_description": str, "body_markdown": str, '
            '"key_points": [str], "quotable_lines": [str], "faq": '
            '[{"q": str, "a": str}], "internal_link_suggestions": '
            '[{"path": str, "anchor": str}]}',
            "body_markdown uses ## and ### only — no H1, the CMS renders that from "
            "the title.",
        ]
    )


def _user_prompt(brief: ContentBrief, data: dict[str, Any]) -> str:
    b, o = brief.brief, brief.opportunity
    return json.dumps(
        {
            "assignment": {
                "working_title": b.working_title,
                "content_type": b.content_type,
                "target_url_path": b.target_url_path,
                "language": b.language,
                "word_count": {"min": b.word_count_target.min, "max": b.word_count_target.max},
                "outline": [s.model_dump() for s in b.outline],
                "must_include": b.must_include,
                "must_avoid": b.must_avoid,
                "meta_hint": b.meta.model_dump(),
                "schema_org": b.schema_org,
                "internal_links": b.internal_links,
            },
            "why_this_page_exists": {
                "gap_type": o.gap_type,
                "primary_keyword": o.primary_keyword,
                "secondary_keywords": o.secondary_keywords,
                "search_intent": o.search_intent,
                "search_console": o.gsc,
                "rationale": o.rationale,
            },
            "available_data": data,
        },
        ensure_ascii=False,
        indent=2,
    )


def _resolve_data_dependencies(brief: ContentBrief) -> dict[str, Any]:
    """
    Fetch the live feeds the brief points at. Anything that fails to load is
    reported as explicitly unavailable — never silently omitted, because a
    missing key is exactly what tempts a model to invent the number.
    """
    resolved: dict[str, Any] = {"fetched_at": rfc3339(), "fields": {}}
    for dep in brief.brief.data_dependencies:
        field_name, source = dep.get("field"), dep.get("source")
        if not field_name or not source:
            continue
        try:
            resp = requests.get(
                source, timeout=15, headers={"User-Agent": config.USER_AGENT}
            )
            resp.raise_for_status()
            resolved["fields"][field_name] = {
                "status": "available",
                "source": source,
                "asof": rfc3339(),
                "value": resp.json(),
            }
        except (requests.RequestException, ValueError) as exc:
            log.warning("data dependency %s failed: %s", source, exc)
            resolved["fields"][field_name] = {
                "status": "unavailable",
                "source": source,
                "note": "State that this figure is available on request. Do not estimate it.",
            }
    resolved["has_priced_facts"] = any(
        f["status"] == "available" for f in resolved["fields"].values()
    )
    return resolved


GENERATION_CONFIG = {
    "temperature": 0.85,          # long-form voice, not analysis
    "top_p": 0.95,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}


_RESOLVED_MODEL: str | None = None

# Models ListModels advertises but the API then refuses with 404 "no longer
# available to new users". Presence in the listing is NOT proof of access, so
# the only reliable signal is a rejected call. Remembering them lets the retry
# loop move on instead of asking for the same withdrawn model three times.
_UNUSABLE_MODELS: set[str] = set()


def mark_model_unusable(name: str) -> None:
    """Retire a model for this process and force the next call to re-resolve."""
    global _RESOLVED_MODEL
    _UNUSABLE_MODELS.add(name)
    _RESOLVED_MODEL = None

# Preference order when the configured model is not usable. Newest generation
# first, and flash tiers ahead of pro within a generation because pro is the one
# routinely gated behind billing. Any name absent from the account's own list is
# skipped, so entries that do not exist cost nothing.
_MODEL_PREFERENCE = (
    "gemini-flash-latest",
    "gemini-pro-latest",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
)


class TransientUpstreamError(RuntimeError):
    """
    The model provider was temporarily unable to answer.

    Distinct from every other failure because the correct response is
    different: nothing here is wrong, nothing needs fixing, and the brief will
    draft on the next run untouched. A 503 capacity spike at Google is not a
    defect in this pipeline, and turning the nightly cron red for one is how a
    cron stops being read — the same reasoning that made an ungranted Search
    Console property a configuration gap in Agent 1 rather than a failure.
    """


# Seconds to wait after an overload response, per attempt. Google's own advice
# on 503 is that spikes are usually temporary; the generic 1s/2s backoff does
# not outlast one. Run #9 spent all three attempts inside 31 seconds.
_OVERLOAD_BACKOFF = (15, 45)


def is_overloaded(msg: str) -> bool:
    """True when the provider said 'busy, come back later' rather than 'no'."""
    m = msg.upper()
    return ("UNAVAILABLE" in m or "503" in m
            or "OVERLOADED" in m or "HIGH DEMAND" in m.upper())


def resolve_model() -> str:
    """
    The model this API key can actually call, asked rather than assumed.

    Hardcoding a model name has now failed twice in one evening for two
    different reasons: gemini-2.5-pro answers 429 "limit: 0" because it is not
    on the free tier, and gemini-2.5-flash answers 404 "no longer available to
    new users" because a key minted today cannot reach that generation at all.
    Both are invisible until a live call, and both look like ordinary errors.

    Model names churn faster than this pipeline will be edited, so it asks the
    account what it has: ListModels, filtered to those supporting
    generateContent. The configured name wins when it is present. Otherwise the
    first preference the account actually offers is used, loudly.

    Cached per process — the answer cannot change mid-run, and a batch of ten
    briefs should not make ten identical calls.
    """
    global _RESOLVED_MODEL
    if _RESOLVED_MODEL:
        return _RESOLVED_MODEL

    configured = config.GEMINI_MODEL
    try:
        from google import genai as new_genai

        client = new_genai.Client(api_key=config.require_env("GEMINI_API_KEY"))
        listed = list(client.models.list())
        # supported_actions is populated on Vertex and usually EMPTY on the
        # Gemini Developer API. Filtering on it excluded every model, discovery
        # returned nothing, and the configured name was honoured straight into
        # the 404 it was meant to prevent. So exclude only what we positively
        # know cannot generate — an unknown capability is included, not dropped.
        available = [
            m.name.removeprefix("models/")
            for m in listed
            if (acts := getattr(m, "supported_actions", None)) is None
            or not acts
            or "generateContent" in acts
        ]
        # Embedding and similar models advertise nothing useful here and would
        # otherwise win the alphabetical fallback.
        available = [n for n in available
                     if not any(x in n for x in ("embedding", "aqa", "imagen", "veo", "tts"))]
        available = [n for n in available if n not in _UNUSABLE_MODELS]
        log.info("Gemini lists %d model(s), %d usable for generation",
                 len(listed), len(available))
    except config.ConfigError:
        raise
    except Exception as exc:
        # If the listing itself fails, honour the configured name rather than
        # second-guessing it — the caller's error will be the real one.
        log.warning("could not list Gemini models (%s); using %s as configured", exc, configured)
        _RESOLVED_MODEL = configured
        return configured

    if not available:
        log.warning("Gemini returned no generateContent models; using %s as configured", configured)
        _RESOLVED_MODEL = configured
        return configured

    if configured in available and configured not in _UNUSABLE_MODELS:
        _RESOLVED_MODEL = configured
        return configured

    for candidate in _MODEL_PREFERENCE:
        if candidate in available and candidate not in _UNUSABLE_MODELS:
            log.warning(
                "GEMINI_MODEL=%s is not available to this API key. Using %s instead. "
                "This key offers: %s",
                configured, candidate, ", ".join(sorted(available)[:12]),
            )
            _RESOLVED_MODEL = candidate
            return candidate

    fallback = sorted(available)[0]
    log.warning(
        "neither GEMINI_MODEL=%s nor any preferred model is available. Falling back to %s. "
        "This key offers: %s",
        configured, fallback, ", ".join(sorted(available)[:12]),
    )
    _RESOLVED_MODEL = fallback
    return fallback


def _gemini_once(system: str, prompt: str) -> tuple[str, Any]:
    """
    One Gemini generation. Returns (text, usage_metadata).

    Two SDKs, because Google shipped a replacement: `google-genai` is the
    current unified client and is preferred when installed; `google-generativeai`
    is the legacy package named in the original spec and is the fallback. It
    emits an end-of-support FutureWarning on import — keep it only until the
    hosts are migrated.
    """
    try:
        from google import genai as new_genai
        from google.genai import types as genai_types

        client = new_genai.Client(api_key=config.require_env("GEMINI_API_KEY"))
        resp = client.models.generate_content(
            model=resolve_model(),
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system, **GENERATION_CONFIG
            ),
        )
        return (resp.text or "").strip(), getattr(resp, "usage_metadata", None)
    except ImportError:
        pass

    import google.generativeai as genai   # legacy SDK — deprecated by Google

    genai.configure(api_key=config.require_env("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name=resolve_model(),
        system_instruction=system,
        generation_config=GENERATION_CONFIG,
    )
    resp = model.generate_content(prompt)
    return (resp.text or "").strip(), getattr(resp, "usage_metadata", None)


def _call_gemini(
    brief: ContentBrief, data: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns (draft, generation_meta). Raises on an unusable response."""
    started = time.time()
    system = _system_instruction(brief)
    prompt = _user_prompt(brief, data)
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            text, usage = _gemini_once(system, prompt)
            draft = json.loads(text)
            if not draft.get("body_markdown"):
                raise ValueError("model returned no body_markdown")

            meta = {
                "provider": "gemini",
                "model": config.GEMINI_MODEL,
                "input_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None),
                "attempts": attempt,
                "duration_ms": int((time.time() - started) * 1000),
            }
            return draft, meta
        except config.ConfigError:
            # A missing or malformed credential will be just as missing on the
            # third try. Retrying it wastes ~7s per brief and buries the real
            # cause under three identical warnings.
            raise
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            log.warning("gemini attempt %d returned unusable output: %s", attempt, exc)
        except Exception as exc:  # transport / quota / safety block
            # "limit: 0" is not rate-limiting, it is the model being absent from
            # the plan — most often Pro on a free-tier key. Zero permitted
            # requests will still be zero on the third attempt, so retrying only
            # buries the cause under three identical 429s.
            msg = str(exc)
            if "NOT_FOUND" in msg and "no longer available" in msg:
                dead = resolve_model()
                mark_model_unusable(dead)
                nxt = resolve_model()
                if nxt == dead:
                    raise RuntimeError(
                        f"{dead} is withdrawn for this API key and no alternative "
                        "remains. Set GEMINI_MODEL to a model the key can call."
                    ) from exc
                log.warning("%s is withdrawn for this key — retrying with %s", dead, nxt)
                last_error = exc
                continue
            if "RESOURCE_EXHAUSTED" in msg and "limit: 0" in msg:
                raise RuntimeError(
                    f"{config.GEMINI_MODEL} is not available on this API key's plan "
                    "(quota limit: 0, not a temporary rate limit). Either set "
                    "GEMINI_MODEL to a model your plan includes — gemini-2.5-flash "
                    "is on the free tier — or enable billing on the Google Cloud "
                    "project behind the key."
                ) from exc
            last_error = exc
            log.warning("gemini attempt %d failed: %s", attempt, exc)
            if is_overloaded(msg) or config.rate_limited(msg):
                # Google says a 503 spike is "usually temporary". The general
                # backoff answers that with 1s and 2s, which is not a wait —
                # run #9 burned all three attempts inside 31 seconds and lost
                # the brief to a capacity blip. Wait long enough for the spike
                # to actually pass.
                time.sleep(_OVERLOAD_BACKOFF[min(attempt - 1, len(_OVERLOAD_BACKOFF) - 1)]
                           + random.uniform(0, 3))
                continue
        time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.4))

    if last_error is not None and (is_overloaded(str(last_error))
                                   or config.rate_limited(str(last_error))):
        # Overloaded or rate-limited: both mean "not now", neither means the
        # brief is bad. Deferring keeps the run green and re-drafts next time.
        raise TransientUpstreamError(
            f"Gemini was unavailable on all 3 attempts: {last_error}"
        ) from last_error
    raise RuntimeError(f"Gemini failed after 3 attempts: {last_error}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. CMS adapters
# ══════════════════════════════════════════════════════════════════════════════


def push_to_cms(brief: ContentBrief, draft: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatch on site.cms.adapter. Each adapter returns
    {status, live_url, record_id, published_at, scheduled_for}.

    The real WordPress/Astro/base44 implementations live behind their own
    credentials; unimplemented adapters stage the draft and return `draft`
    rather than pretending to publish — an adapter must never report a URL it
    did not create.
    """
    site = brief.site
    adapter = site.cms.adapter or "unimplemented"
    url = f"{site.base_url}{brief.brief.target_url_path}"

    footer = (
        f"\n\n---\n_Pipeline architecture by {config.ARCHITECTURE_CREDIT} — "
        f"{config.ARCHITECTURE_URL}_\n"
    )
    draft["body_markdown"] = draft.get("body_markdown", "") + footer

    if site.cms.type == "unknown" or adapter == "unimplemented":
        log.warning(
            "%s has no CMS adapter — staging the draft, not publishing", site.domain
        )
        return {
            "status": "draft",
            "live_url": url,
            "record_id": None,
            "published_at": None,
            "scheduled_for": None,
            "note": f"no adapter for cms.type={site.cms.type!r}",
        }

    if adapter == "wordpress_rest":
        return _push_wordpress(brief, draft, url)

    if adapter == "static_bundle":
        # cruise24.ir / cruiseshop.ir / dmciran.ir are hand-built static sites:
        # there is no API to push to, so the deliverable is a deploy bundle a
        # human uploads. Status stays `draft` — nothing is live until it is.
        return _write_static_bundle(site, brief, draft, url)

    if adapter == "astro_pr":
        return _push_astro_pr(brief, draft, url)

    # A missing_page brief whose path already exists is a hard error, never an
    # overwrite (ARCHITECTURE.md §5, Agent 2).
    if brief.opportunity.gap_type == "missing_page" and _url_exists(url):
        raise RuntimeError(
            f"{url} already exists but the brief says missing_page — refusing to "
            "overwrite. Re-run the scout; the sitemap signal was stale."
        )

    # Anything still here has no implementation. It used to return `url` as
    # live_url and stamp published_at when publish_mode said publish — a URL for
    # a page nothing had created, and a publication timestamp for a publication
    # that never happened. Five of ten sites were routed through it.
    #
    # The rule at the top of this function is not decorative: an adapter must
    # never report a URL it did not create. So it reports the INTENDED path and
    # says plainly that nothing was written.
    log.warning("%s — adapter %r is not implemented; staging only, nothing written",
                site.domain, adapter)
    return {
        "status": "draft",
        "live_url": None,
        "intended_url": url,
        "record_id": None,
        "published_at": None,
        "scheduled_for": None,
        "note": f"adapter {adapter!r} is not implemented — draft staged, not published",
    }


def _push_wordpress(
    brief: ContentBrief, draft: dict[str, Any], url: str
) -> dict[str, Any]:
    """
    Create a WordPress post via the REST API, always as a DRAFT.

    publish_mode is honoured only as far as `draft`. Even when sites.yml says
    `publish`, this writes status=draft — the pipeline generates five articles a
    night unattended and a bad one going straight to a live commercial site
    cannot be recalled. Flipping that is a deliberate edit, not a config value.

    Auth is a WordPress Application Password (Users -> Profile -> Application
    Passwords), never the account password. It is revocable on its own, scoped
    to the REST API, and does not unlock wp-admin.

    Returns status `draft` with the real post ID and edit link when it works.
    On any failure it returns `draft` with the intended URL and a note — an
    adapter must never report a URL it did not create.
    """
    base = brief.site.base_url.rstrip("/")
    user = config.optional_env("WORDPRESS_USER")
    app_pw = config.optional_env("WORDPRESS_APP_PASSWORD")

    if not user or not app_pw:
        log.warning(
            "%s — WORDPRESS_USER/WORDPRESS_APP_PASSWORD not set; staging the draft",
            brief.site.domain,
        )
        return {
            "status": "draft", "live_url": None, "intended_url": url, "record_id": None,
            "published_at": None, "scheduled_for": None,
            "note": "wordpress_rest not configured — set WORDPRESS_USER and "
                    "WORDPRESS_APP_PASSWORD (an Application Password, not the "
                    "account password)",
        }

    slug = brief.brief.target_url_path.strip("/").split("/")[-1] or "post"
    body = {
        "title": draft.get("title") or brief.brief.working_title,
        "slug": slug,
        "content": draft.get("body_markdown", ""),
        "excerpt": draft.get("meta_description", ""),
        # Never anything else. See the docstring.
        "status": "draft",
    }

    try:
        resp = requests.post(
            f"{base}/wp-json/wp/v2/posts",
            json=body,
            auth=(user, app_pw),
            timeout=config.WEBHOOK_TIMEOUT_S,
            headers={"User-Agent": config.USER_AGENT},
        )
    except requests.RequestException as exc:
        log.error("%s — WordPress unreachable: %s", brief.site.domain, exc)
        return {
            "status": "draft", "live_url": None, "intended_url": url, "record_id": None,
            "published_at": None, "scheduled_for": None,
            "note": f"wordpress transport error: {exc}",
        }

    if resp.status_code not in (200, 201):
        # 401 is the common one and it is almost always the Application
        # Password being pasted with its spaces stripped, or the account
        # lacking author rights.
        log.error("%s — WordPress returned %s: %s",
                  brief.site.domain, resp.status_code, resp.text[:300])
        return {
            "status": "draft", "live_url": None, "intended_url": url, "record_id": None,
            "published_at": None, "scheduled_for": None,
            "note": f"wordpress HTTP {resp.status_code}: {resp.text[:200]}",
        }

    data = resp.json()
    post_id = data.get("id")
    log.info("%s — WordPress draft %s created: %s",
             brief.site.domain, post_id, data.get("link") or url)
    return {
        "status": "draft",
        # The link WordPress reports for a draft is the eventual permalink, not
        # a live page. Report it, but it is not published and says so.
        "live_url": data.get("link") or url,
        "record_id": str(post_id) if post_id else None,
        "published_at": None,
        "scheduled_for": None,
        "edit_url": f"{base}/wp-admin/post.php?post={post_id}&action=edit" if post_id else None,
        "note": "created as a WordPress draft — review and publish by hand",
    }


def _push_astro_pr(
    brief: ContentBrief, draft: dict[str, Any], url: str
) -> dict[str, Any]:
    """
    Write the article into an Astro content collection and open a pull request.

    Used by boutimar.com and exploreorient.com — both static Astro builds with
    no CMS able to hold a draft. A pull request IS the draft: it is reviewable,
    diffable, revertible, and nothing reaches the live site until a human
    merges it. For a site generated from files, that is a better review surface
    than a CMS admin.

    Needs a token with `contents: write` and `pull_requests: write` on the
    TARGET repository — the default GITHUB_TOKEN is scoped to the repo the
    workflow runs in, which is not the one being written to. Without it the
    file is staged to disk and the adapter says so rather than pretending.
    """
    from pathlib import Path as _Path

    site = brief.site
    repo = config.optional_env(f"ASTRO_REPO_{site.domain.replace('.', '_').upper()}") \
        or config.optional_env("ASTRO_REPO")
    token = config.optional_env("ASTRO_GITHUB_TOKEN")

    # The collection is declared per site, NOT derived from content_type. Astro
    # only has the collections defined in src/content/config.ts, so a brief of
    # type "guide" would write to src/content/guide/ — a directory Astro does
    # not know, which fails the build.
    cms = site.cms.model_dump() if hasattr(site.cms, "model_dump") else dict(site.cms or {})
    collection = str(cms.get("collection") or brief.brief.content_type or "journal").strip("/")
    # Astro derives the URL from collection + filename, so a target path of
    # /journal/persian-gardens must become journal/persian-gardens.md — not
    # journal/journal-persian-gardens.md, which would publish at
    # /journal/journal-persian-gardens/. Drop the leading segment when it is
    # already the collection name.
    segments = [x for x in brief.brief.target_url_path.strip("/").split("/") if x]
    if segments and segments[0] == collection:
        segments = segments[1:]
    slug = "-".join(segments) or "post"
    rel_path = f"{site.cms.content_root.strip('/')}/{collection}/{slug}.md"

    # Astro validates every entry against the collection's zod schema and
    # refuses to build on a mismatch, so the frontmatter shape belongs to the
    # site, not to this adapter. boutimar.com's `journal` requires title, date,
    # category and author; the generic title/description/pubDate this used to
    # emit would have failed the build on the first PR.
    fields = {
        "title": draft.get("title") or brief.brief.working_title,
        "date": utc_now().strftime("%Y-%m-%d"),
        "category": (brief.opportunity.primary_keyword or "Travel").strip()[:60],
        "summary": (draft.get("meta_description") or "").strip(),
        "language": brief.brief.language,
    }
    template = cms.get("frontmatter") or {}
    if template:
        front = {}
        for key, val in template.items():
            rendered = str(val)
            for token, repl in fields.items():
                rendered = rendered.replace("{" + token + "}", str(repl))
            front[key] = rendered
        missing = [k for k, v in front.items() if not v]
        if missing:
            # Never open a PR that cannot build. A red build on the target repo
            # is worse than no PR: it blocks every other merge into that site.
            raise ValueError(
                f"{site.domain}: frontmatter field(s) {missing} came out empty for "
                f"collection '{collection}'. Astro will reject the entry — fix the "
                f"mapping in sites.yml rather than pushing an unbuildable file."
            )
    else:
        front = {
            "title": fields["title"],
            "description": fields["summary"],
            "draft": True,      # Astro content collections honour this
            "pubDate": rfc3339(),
            "lang": brief.brief.language,
        }
    fm = "\n".join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in front.items())
    file_body = f"---\n{fm}\n---\n\n{draft.get('body_markdown', '')}"

    if not repo or not token:
        out = _Path(config.optional_env("BUNDLE_DIR", str(config.BASE_DIR / "bundles")))
        out = out / site.domain / slug
        out.mkdir(parents=True, exist_ok=True)
        (out / _Path(rel_path).name).write_text(file_body, encoding="utf-8")
        log.warning("%s — ASTRO_REPO/ASTRO_GITHUB_TOKEN not set; wrote %s instead of a PR",
                    site.domain, out)
        return {
            "status": "draft", "live_url": None, "intended_url": url,
            "record_id": slug, "published_at": None, "scheduled_for": None,
            "staged_path": str(out / _Path(rel_path).name),
            "note": "astro_pr not configured — set ASTRO_REPO and ASTRO_GITHUB_TOKEN "
                    "to open a pull request. File written to bundles/ meanwhile.",
        }

    api = "https://api.github.com"
    hdr = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
           "User-Agent": config.USER_AGENT}
    branch = f"agent2/{slug}"

    try:
        r = requests.get(f"{api}/repos/{repo}", headers=hdr, timeout=config.WEBHOOK_TIMEOUT_S)
        r.raise_for_status()
        base = r.json()["default_branch"]

        r = requests.get(f"{api}/repos/{repo}/git/ref/heads/{base}", headers=hdr,
                         timeout=config.WEBHOOK_TIMEOUT_S)
        r.raise_for_status()
        sha = r.json()["object"]["sha"]

        # 422 here means the branch already exists — a redelivery of the same
        # brief. That is idempotency working, not an error.
        rb = requests.post(f"{api}/repos/{repo}/git/refs", headers=hdr,
                           json={"ref": f"refs/heads/{branch}", "sha": sha},
                           timeout=config.WEBHOOK_TIMEOUT_S)
        if rb.status_code not in (201, 422):
            rb.raise_for_status()

        import base64 as _b64
        r = requests.put(
            f"{api}/repos/{repo}/contents/{rel_path}", headers=hdr,
            json={"message": f"Agent 2: draft \u2014 {front['title']}"[:72],
                  "content": _b64.b64encode(file_body.encode("utf-8")).decode("ascii"),
                  "branch": branch},
            timeout=config.WEBHOOK_TIMEOUT_S)
        r.raise_for_status()

        rp = requests.post(
            f"{api}/repos/{repo}/pulls", headers=hdr,
            json={"title": f"Agent 2 draft: {front['title']}"[:72],
                  "head": branch, "base": base,
                  "body": (f"Drafted by Agent 2 from the Search Console gap "
                           f"`{brief.opportunity.primary_keyword}`.\n\n"
                           f"Intended path: `{brief.brief.target_url_path}`\n\n"
                           f"`draft: true` in the front matter — merging does not "
                           f"publish it, it only puts the file in the repo.\n\n"
                           f"_Pipeline architecture by {config.ARCHITECTURE_CREDIT}_")},
            timeout=config.WEBHOOK_TIMEOUT_S)
        if rp.status_code == 422:      # a PR for this branch already exists
            log.info("%s — PR already open for %s", site.domain, branch)
            return {"status": "draft", "live_url": None, "intended_url": url,
                    "record_id": slug, "published_at": None, "scheduled_for": None,
                    "note": f"pull request already open for {branch}"}
        rp.raise_for_status()
        pr = rp.json()
        log.info("%s — opened PR #%s: %s", site.domain, pr.get("number"), pr.get("html_url"))
        return {
            "status": "draft", "live_url": None, "intended_url": url,
            "record_id": slug, "published_at": None, "scheduled_for": None,
            "pr_url": pr.get("html_url"), "pr_number": pr.get("number"),
            "note": "pull request opened — review and merge to add the file",
        }
    except requests.RequestException as exc:
        # 401 and 403 look alike and mean opposite things, and guessing wrong
        # sends you to the wrong settings page. GitHub is strict about it:
        #   401 — the credential itself was rejected. The token is malformed,
        #         truncated, expired or revoked. Permissions are irrelevant;
        #         GitHub never got far enough to check them.
        #   403 — the token is valid and lacks a permission, or the resource
        #         owner did not grant it access to this repository.
        #   404 — valid token, but it cannot see this repo at all: usually the
        #         wrong repo name in ASTRO_REPO_*, or the repo was not selected.
        status = getattr(getattr(exc, "response", None), "status_code", None)
        # Shape of the credential, never the credential. A 401 that survives a
        # careful re-paste needs to distinguish "truncated" from "wrong kind of
        # token" from "right token, revoked", and those are indistinguishable
        # from the outside. Length and the PUBLIC prefix settle it and leak
        # nothing: github_pat_ is documented, and a length is not a secret.
        kind = next((p for p in ("github_pat_", "ghp_", "gho_", "ghu_", "ghs_", "ghr_")
                     if token.startswith(p)), "unrecognised-prefix")
        shape = (f"[token shape: {len(token)} chars, {kind}; a complete "
                 f"fine-grained token is ~93 chars and starts github_pat_]")
        hint = {
            401: (f"the token in ASTRO_GITHUB_TOKEN was REJECTED — it is malformed, "
                  f"truncated, expired or revoked. This is not a permissions problem; "
                  f"re-create the token and paste the whole value. {shape}"),
            403: (f"the token is valid but lacks a permission on {repo}. It needs "
                  f"Contents: Read and write, and Pull requests: Read and write."),
            404: (f"the token cannot see {repo} at all — check the repository name in "
                  f"ASTRO_REPO_{site.domain.replace('.', '_').upper()} and that the "
                  f"token selected this repository."),
        }.get(status, "")
        detail = config.redact(str(exc))[:200]
        log.error("%s — astro_pr failed: %s%s", site.domain, detail,
                  f" — {hint}" if hint else "")
        return {"status": "draft", "live_url": None, "intended_url": url,
                "record_id": None, "published_at": None, "scheduled_for": None,
                "note": f"astro_pr error: {detail}" + (f" — {hint}" if hint else "")}


def _write_static_bundle(
    site: SiteBlock, brief: ContentBrief, draft: dict[str, Any], url: str
) -> dict[str, Any]:
    """Deploy bundle for a hand-built static site: markdown + a manifest."""
    from pathlib import Path

    record_id = brief.brief.target_url_path.strip("/").replace("/", "-") or "page"
    out = Path(config.optional_env("BUNDLE_DIR", str(config.BASE_DIR / "bundles")))
    out = out / site.domain / record_id
    out.mkdir(parents=True, exist_ok=True)

    (out / "index.md").write_text(draft.get("body_markdown", ""), encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "architecture_credit": config.ARCHITECTURE_CREDIT,
                "domain": site.domain,
                "target_url_path": brief.brief.target_url_path,
                "language": brief.brief.language,
                "title": draft.get("title", brief.brief.working_title),
                "meta_description": draft.get("meta_description", ""),
                "schema_org": brief.brief.schema_org,
                "faq": draft.get("faq", []),
                "generated_at": rfc3339(),
                "deploy_note": (
                    "Upload index.md through the site's own build, then add "
                    f"{brief.brief.target_url_path} to sitemap.xml. Verify the live "
                    "file against this bundle before marking the deploy done."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("%s — static bundle written to %s", site.domain, out)
    return {
        "status": "draft",
        "live_url": url,
        "record_id": record_id,
        "published_at": None,
        "scheduled_for": None,
        "note": f"deploy bundle at {out}",
    }


def _url_exists(url: str) -> bool:
    try:
        resp = requests.head(
            url, timeout=10, allow_redirects=True, headers={"User-Agent": config.USER_AGENT}
        )
        return resp.status_code < 400
    except requests.RequestException:
        return False   # unreachable ≠ existing


# ══════════════════════════════════════════════════════════════════════════════
# 6. The job
# ══════════════════════════════════════════════════════════════════════════════


def run_writing_job(brief: ContentBrief, raw_payload: dict[str, Any]) -> None:
    """
    Runs in FastAPI's background worker thread. Every exit path updates the job
    registry — a job that vanishes silently is worse than one that fails loudly.
    """
    idem = brief.envelope.idempotency_key
    JOBS.update(idem, status="drafting")

    try:
        # Resolved once and reused: the same snapshot must feed the prompt and
        # the compliance context, or the gate would judge against different data
        # than the model saw.
        data = _resolve_data_dependencies(brief)
        draft, gen_meta = _call_gemini(brief, data)

        # The compliance gate on the OUTPUT. The prompt already carried these
        # rules; this is the half that is enforcement rather than instruction.
        surface = "\n".join(
            filter(
                None,
                [
                    draft.get("title", ""),
                    draft.get("meta_description", ""),
                    draft.get("body_markdown", ""),
                    " ".join(draft.get("key_points", [])),
                    " ".join(draft.get("quotable_lines", [])),
                    " ".join(f"{f.get('q','')} {f.get('a','')}" for f in draft.get("faq", [])),
                ],
            )
        )
        ctx = {
            "priced_facts": data["has_priced_facts"],
            "price_asof": data["fetched_at"] if data["has_priced_facts"] else None,
            "itinerary_ports": brief.brief.must_include,
        }
        warnings = compliance.enforce(surface, brief.compliance.profile, context=ctx)
        if warnings:
            log.warning(
                "%s — %d non-blocking compliance flag(s)", brief.site.domain, len(warnings)
            )

        JOBS.update(idem, status="publishing")
        result = push_to_cms(brief, draft)
        JOBS.update(idem, status="published", live_url=result["live_url"])

        event = build_publishing_event(brief, raw_payload, draft, result, gen_meta, warnings, data)

        if brief.routing.dry_run:
            log.info("[dry-run] would POST publishing.event for %s", result["live_url"])
            return

        callback = brief.routing.callback_url or config.optional_env("AGENT3_WEBHOOK_URL")
        if not callback:
            log.warning("no callback_url and no AGENT3_WEBHOOK_URL — event not forwarded")
            return

        ok, reason = _deliver(callback, event, config.require_env("WEBHOOK_SIGNING_SECRET"))
        if ok:
            log.info("forwarded publishing.event → agent3 for %s", result["live_url"])
        else:
            JOBS.update(idem, error=f"forward failed: {reason}")
            log.error("forward to agent3 failed: %s", reason)

    except compliance.ComplianceError as exc:
        blocked = [v.as_dict() for v in exc.violations if v.severity == compliance.BLOCK]
        JOBS.update(idem, status="blocked", error=str(exc))
        log.error(
            "%s — draft BLOCKED by the compliance gate: %s",
            brief.site.domain, json.dumps(blocked, ensure_ascii=False)[:500],
        )
        JOBS.release(idem)   # a corrected brief must be able to come back through
    except Exception as exc:
        JOBS.update(idem, status="failed", error=str(exc))
        log.exception("%s — writing job failed: %s", brief.site.domain, exc)
        JOBS.release(idem)


def build_publishing_event(
    brief: ContentBrief,
    raw_payload: dict[str, Any],
    draft: dict[str, Any],
    result: dict[str, Any],
    gen_meta: dict[str, Any],
    warnings: list[compliance.Violation],
    data: dict[str, Any],
) -> dict[str, Any]:
    """publishing.event.v1 — ARCHITECTURE.md §4.2."""
    known = {"schema_version", "envelope", "site", "opportunity", "brief", "compliance", "routing"}
    passthrough = {k: v for k, v in raw_payload.items() if k not in known}

    body = draft.get("body_markdown", "")
    word_count = len(body.split())
    audience = "b2b" if brief.site.market in {"DACH", "INT"} else "d2c"

    price_field = data["fields"].get("price_from", {})
    has_offer = price_field.get("status") == "available"

    return {
        "schema_version": config.SCHEMA_VERSION,
        "envelope": build_envelope(
            message_type="publishing.event",
            emitted_by=AGENT_ID,
            target=TARGET_ID,
            correlation_id=brief.envelope.correlation_id,
            idem_key=brief.envelope.idempotency_key,
            causation_id=brief.envelope.message_id,
        ),
        "source_brief": {
            "message_id": brief.envelope.message_id,
            "correlation_id": brief.envelope.correlation_id,
            "primary_keyword": brief.opportunity.primary_keyword,
            "gap_type": brief.opportunity.gap_type,
            "passthrough": passthrough,
        },
        "publication": {
            "status": result["status"],
            "live_url": result["live_url"],
            "canonical_url": result["live_url"],
            "cms": {
                "type": brief.site.cms.type,
                "adapter": brief.site.cms.adapter,
                "record_id": result.get("record_id"),
            },
            "published_at": result.get("published_at"),
            "scheduled_for": result.get("scheduled_for"),
            "language": brief.brief.language,
            "word_count": word_count,
            "reading_time_min": max(1, round(word_count / 220)),
            # No hero image is asserted here. Agent 2 does not source imagery, and
            # an image with no known credit is omitted rather than guessed (§7.3).
            "hero_image": None,
            "indexation": {
                "sitemap_updated": False,
                "robots": "index,follow",
                "submitted_to_gsc": False,
            },
        },
        "content_summary": {
            "title": draft.get("title", brief.brief.working_title),
            "meta_description": draft.get("meta_description", ""),
            "key_points": draft.get("key_points", []),
            "primary_keyword": brief.opportunity.primary_keyword,
            "audience": audience,
            "offer": {
                "has_offer": has_offer,
                "price_source": price_field.get("source"),
                "price_asof": price_field.get("asof"),
            },
            "quotable_lines": draft.get("quotable_lines", []),
        },
        "distribution_hints": {
            "channels": [],   # Agent 3 resolves these from sites.yml
            "b2b_angle": None,
            "d2c_angle": None,
            "cta_url": result["live_url"],
            "utm": {
                "source": "{channel}",
                "medium": "social",
                "campaign": brief.brief.target_url_path.strip("/").replace("/", "-"),
            },
            "hashtags_allowed": True,
            "embargo_until": None,
            "assets": [],
        },
        "compliance": {
            "profile": brief.compliance.profile,
            **compliance.summarise(warnings, brief.compliance.profile),
            "reviewed_by": AGENT_ID,
            "human_review_required": result["status"] == "draft",
        },
        "generation": gen_meta,
    }


def _deliver(url: str, payload: dict[str, Any], secret: str) -> tuple[bool, str]:
    """Same retry contract as Agent 1's deliver(); kept local so Agent 2 has no
    dependency on the Google client libraries."""
    message_id = payload["envelope"]["message_id"]
    reason = "not attempted"

    for attempt in range(1, config.WEBHOOK_MAX_ATTEMPTS + 1):
        # Re-serialise per attempt — envelope.attempt is inside the signed body.
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
        "agent2_writer_listener:app",
        host=config.optional_env("AGENT2_HOST", "0.0.0.0"),
        port=int(config.optional_env("AGENT2_PORT", "8080")),
        reload=False,
        workers=1,   # see JobRegistry — >1 worker requires a shared store
    )
