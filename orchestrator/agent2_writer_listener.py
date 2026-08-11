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
            model=config.GEMINI_MODEL,
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
        model_name=config.GEMINI_MODEL,
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
        time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.4))

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

    if adapter == "static_bundle":
        # cruise24.ir / cruiseshop.ir / dmciran.ir are hand-built static sites:
        # there is no API to push to, so the deliverable is a deploy bundle a
        # human uploads. Status stays `draft` — nothing is live until it is.
        return _write_static_bundle(site, brief, draft, url)

    # A missing_page brief whose path already exists is a hard error, never an
    # overwrite (ARCHITECTURE.md §5, Agent 2).
    if brief.opportunity.gap_type == "missing_page" and _url_exists(url):
        raise RuntimeError(
            f"{url} already exists but the brief says missing_page — refusing to "
            "overwrite. Re-run the scout; the sitemap signal was stale."
        )

    log.info("adapter %s → %s (%s)", adapter, url, site.cms.publish_mode)
    return {
        "status": "draft" if site.cms.publish_mode == "draft" else site.cms.publish_mode,
        "live_url": url,
        "record_id": brief.brief.target_url_path.strip("/").replace("/", "-"),
        "published_at": rfc3339() if site.cms.publish_mode == "publish" else None,
        "scheduled_for": None,
    }


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
