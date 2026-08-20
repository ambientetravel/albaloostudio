"""
Albaloo Orchestration Pipeline — shared configuration.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Every agent imports from here. Model IDs, secrets and the domain registry are
configuration, never literals in a prompt or a call site.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:  # optional: no-op inside GitHub Actions, convenient locally
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"), override=False)
except ImportError:  # pragma: no cover - dotenv is a convenience, not a need
    pass

# ── identity ─────────────────────────────────────────────────────────────────

ARCHITECTURE_CREDIT = "Albaloo Studio"
ARCHITECTURE_URL = "https://albaloostudio.com"
OWNER = "Alireza Mozaffari"
SCHEMA_VERSION = "1.0"
USER_AGENT = f"albaloo-orchestrator/1.0 (+{ARCHITECTURE_URL})"

BASE_DIR = Path(__file__).resolve().parent
SITES_FILE = Path(os.getenv("SITES_FILE", BASE_DIR / "sites.yml"))
RUNS_DIR = Path(os.getenv("RUNS_DIR", BASE_DIR / "runs"))

# Substrings that mean "this account cannot call this model right now", as
# opposed to a timeout or a malformed response, which are worth retrying on the
# next site.
_TERMINAL_PROVIDER_ERRORS = (
    "credit balance is too low",
    "invalid x-api-key",
    "authentication_error",
    "permission_error",
    "insufficient_quota",
    # Gemini's version of "credit balance is too low", and it arrives dressed as
    # a 429 RESOURCE_EXHAUSTED, which is why it slipped past rate_limited() and
    # got retried three times per property on 14 Aug. Depleted credits are not
    # restored by waiting.
    "credits are depleted",
    "prepayment credit",
)

# 429s that are NOT rate limiting. Both are plan/balance problems wearing a
# throttle's status code, and retrying either returns the identical answer.
_FALSE_429S = (
    # The model is absent from the plan entirely, so every retry returns zero.
    "limit: 0",
    # Prepaid balance exhausted — only a purchase changes this, never a wait.
    "credits are depleted",
    "prepayment credit",
)


def rate_limited(msg: str) -> bool:
    """
    A 429 that waiting will fix, as opposed to one that never will.

    Free tiers meter requests per minute and per day. Hitting that ceiling is a
    queue problem, not a plan problem, and the fix is to wait — so it must not
    be reported as a failed run.

    Not every 429 is one. Two are plan-or-balance problems wearing a throttle's
    status code, and retrying either returns the identical answer:

      * `limit: 0` — the model is absent from the plan entirely. Agent 2 learned
        that one the expensive way in August.
      * `prepayment credits are depleted` — Gemini's exhausted-balance error,
        which arrives as `429 RESOURCE_EXHAUSTED` and so matched this function
        exactly. On 14 Aug it was retried three times for one property and would
        have been thirty calls across the full portfolio, every one of them
        certain to fail, before anything said why.

    Keeping both agents on one definition is how the distinction stays learned.
    """
    m = msg.lower()
    if any(s in m for s in _FALSE_429S):
        return False
    u = msg.upper()
    return "429" in u or "RESOURCE_EXHAUSTED" in u or "RATE LIMIT" in u


def transport_error(msg: str) -> bool:
    """
    The connection failed, rather than the provider answering unfavourably.

    "Server disconnected without sending a response" degraded a whole scout run
    on 13 Aug: it is not a 503, not a 429, and not malformed JSON, so it matched
    none of the retry paths and fell straight through to the fallback. A dropped
    connection is the most ordinary transient failure there is and the one most
    obviously worth retrying.
    """
    m = msg.lower()
    return any(s in m for s in (
        "server disconnected", "connection reset", "connection aborted",
        "remote end closed", "broken pipe", "timed out", "timeout",
        "connection error", "temporary failure in name resolution",
    ))


def terminal_provider_error(msg: str) -> str:
    """The reason this will fail for every other site too, or '' if it will not."""
    low = msg.lower()
    for needle in _TERMINAL_PROVIDER_ERRORS:
        if needle in low:
            return needle
    return ""


# ── models (overridable; never pinned inside a prompt) ────────────────────────

# Agent 1's gap analysis: `gemini` (default), `anthropic`, or `openai`.
#
# Anthropic was the default until 12 Aug 2026, on the reasoning that Agents 3, 4
# and 6 already need that key — one vendor, one bill, one thing to rotate. What
# that reasoning left out is that Agent 1 is by far the most expensive caller in
# the pipeline: one Opus 5 call per property per night, up to 16k output tokens
# each, at $25 per million output. Eight properties × five runs emptied the $5
# balance in four days, and when it emptied, the head of the chain went with it.
#
# Gemini already drafts every article in Agent 2 on a key with no balance to
# exhaust, and gap analysis — classify, deduplicate, rank, outline — is the
# easier of the two jobs. Putting the nightly scout on the free tier and keeping
# the paid key for the agents that run occasionally is the right way round.
GAP_ANALYSIS_PROVIDER = os.getenv("GAP_ANALYSIS_PROVIDER", "gemini").lower()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
# Flash, not Pro, and the reason is not preference. Gemini 2.5 Pro is not on
# the free tier at all: the API answers a request for it with 429 and
# "limit: 0", which reads like rate-limiting but means "this model is not in
# your plan". Flash is available without billing, and for drafting from a brief
# that already fixes the outline, headings and must-cover points, the gap
# between the two is small. Override with GEMINI_MODEL once billing is on.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# Seconds between Agent 1's per-property Gemini calls. The free tier's ceiling
# is requests-per-minute, and the scout otherwise fires ten in a row.
#
# This is a FREE-TIER workaround, not a politeness setting. On a billed key the
# ceiling rises by orders of magnitude and 20s per property is pure wall-clock
# for nothing — eight properties spend 2m40s asleep. Drop it to 1 in the same
# change that enables billing, by setting the GEMINI_MIN_INTERVAL_S repository
# variable. It is deliberately left high by default so that turning billing OFF
# again does not silently start tripping 429s.
GEMINI_MIN_INTERVAL_S = float(os.getenv("GEMINI_MIN_INTERVAL_S", "20"))

# ── What a run costs ────────────────────────────────────────────────────────
#
# USD per MILLION tokens, (input, output). These are an ASSUMPTION, not a
# measurement: the pipeline cannot read a vendor's price list, and rates change
# without notice. They are recorded here, with the date they were entered, so
# that a number in a run summary can always be traced to a stated rate rather
# than looking like something the pipeline knows.
#
# Verify against the vendor's current pricing page before trusting a total, and
# override without a code change by setting TOKEN_PRICES_JSON, e.g.
#     TOKEN_PRICES_JSON='{"gemini-2.5-flash": [0.30, 2.50]}'
#
# A model that is not in this table is reported as UNPRICED — tokens counted,
# cost blank. Guessing a rate for an unknown model would produce a total that
# looks authoritative and is fiction.
_DEFAULT_TOKEN_PRICES: dict[str, tuple[float, float]] = {
    # Entered 14 Aug 2026.
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.0-flash": (0.10, 0.40),
    # The `-latest` ALIASES, which is what resolve_model() actually settles on:
    # run #22 reported `gemini-flash-latest` and the cost line read "unpriced"
    # because only the pinned names were listed. Pinned names are the ones this
    # key cannot use — 2.5-flash is withdrawn for keys issued after a certain
    # date, and this key was created 11 Aug 2026 — so the alias is the normal
    # case and the pinned name is the exception.
    #
    # An alias is a moving target: the price here is whatever the alias points
    # at TODAY, and it can change without the model name changing. That is a
    # real limitation and the reason every cost line says it is an assumption.
    "gemini-flash-latest": (0.30, 2.50),
    "gemini-flash-lite-latest": (0.10, 0.40),
    "gemini-pro-latest": (1.25, 10.00),
    # Priced ahead of being usable. Pro is absent from the free tier entirely —
    # it answers 429 "limit: 0" — so it becomes selectable on the same day
    # billing is enabled, which is precisely the day a missing rate would turn
    # every cost line into "unpriced". Note the ratio before switching: Pro is
    # ~4x Flash on both sides, and gap analysis (classify, dedupe, rank,
    # outline against a fixed schema) is not work that needs it.
    "gemini-2.5-pro": (1.25, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
}


def token_prices() -> dict[str, tuple[float, float]]:
    """The price table, with any TOKEN_PRICES_JSON override merged over it."""
    prices = dict(_DEFAULT_TOKEN_PRICES)
    raw = os.getenv("TOKEN_PRICES_JSON", "").strip()
    if not raw:
        return prices
    try:
        for model, pair in json.loads(raw).items():
            prices[str(model)] = (float(pair[0]), float(pair[1]))
    except Exception:
        # A malformed override must not take the run down over a cost estimate.
        pass
    return prices


# The brake, in USD per run. A Google Cloud free trial is a hard cap — credit
# runs out and everything stops, with the card never charged. Upgrading to
# pay-as-you-go removes that cap: spend accrues and the card is billed at a
# threshold. A Cloud budget only emails; it does not stop anything (its
# spend-cap enforcement is preview-only and does not clearly cover the
# Generative Language API). So the only brake that actually exists is this one,
# and it lives here because this code is what does the spending.
#
# An observed run is ~$0.11 for eight properties and ~$0.02 for five articles,
# so $1.00 is roughly 9x headroom — high enough never to fire on a normal run,
# low enough that a loop calling the model a thousand times cannot quietly cost
# real money. Raise it deliberately with MAX_RUN_COST_USD; set 0 to disable.
MAX_RUN_COST_USD = float(os.getenv("MAX_RUN_COST_USD", "1.00"))


def over_budget(spent_usd: float | None) -> str:
    """
    Reason string when a run has spent its ceiling, or "" to continue.

    A None cost means the model is unpriced, and an unpriced model must NOT be
    treated as free — but it must not halt the run either, since a missing rate
    is a bookkeeping gap and not evidence of overspending. Unpriced spend is
    therefore allowed through and reported, which is why every summary names the
    unpriced model rather than burying it.
    """
    if MAX_RUN_COST_USD <= 0 or spent_usd is None:
        return ""
    if spent_usd < MAX_RUN_COST_USD:
        return ""
    return (f"run cost ceiling reached — estimated ${spent_usd:.4f} spent, "
            f"limit ${MAX_RUN_COST_USD:.2f} (MAX_RUN_COST_USD). No further "
            f"model calls this run; nothing is wrong with the remaining work "
            f"and it is retried on the next run.")


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """
    Cost of one call, or None when the model is not priced.

    None is a real answer and callers must render it as "unpriced" rather than
    coercing it to 0.0 — a run that silently reports $0.00 because nobody
    entered a rate is worse than one that says it does not know.
    """
    if not model:
        return None
    prices = token_prices()
    rate = prices.get(model)
    if rate is None:
        # Vendors version model names ("-preview", a date suffix) far faster
        # than a price table gets updated, and those variants price the same as
        # the family. Longest prefix wins so -flash-lite never matches -flash.
        for name in sorted(prices, key=len, reverse=True):
            if model.startswith(name):
                rate = prices[name]
                break
    if rate is None:
        return None
    return (input_tokens or 0) / 1_000_000 * rate[0] + \
           (output_tokens or 0) / 1_000_000 * rate[1]

# Claude Opus 5 is the default for Agents 3 and 4. Notes that matter for the
# request shape on this model family:
#   * temperature / top_p / top_k are REMOVED — sending any of them is a 400.
#     Steer tone with the prompt, not sampling.
#   * thinking is ON by default; `budget_tokens` is a 400. Depth is `effort`.
#   * assistant-turn prefills are a 400 — structured output replaces them.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

# Agent 1's gap analysis when GAP_ANALYSIS_PROVIDER=anthropic — deliberately NOT
# ANTHROPIC_MODEL. The scout ran on Opus 5 until 12 Aug 2026 because it shared
# that one setting with Agents 3, 4 and 6, and it is the wrong tier for the job:
# classify, deduplicate, rank, outline against a fixed JSON schema is not the
# work Opus exists for. It is also the only one of the four that ran every
# night, so it paid the top rate most often.
#
# Sonnet 5 rather than Haiku 4.5 because the brief is not pure classification —
# working_title, meta_title, meta_description and the outline headings are
# Farsi prose that seeds the article, and that copy is worth a mid tier. Haiku
# is the further step down if the bill still matters: set GAP_ANALYSIS_MODEL.
#
# Per run, eight properties, ~64k in / 40k out:
#     Opus 5     $5/$25 per MTok  →  ~$1.32
#     Sonnet 5   $3/$15           →  ~$0.79
#     Haiku 4.5  $1/$5            →  ~$0.26
#     Gemini flash (free tier)    →   $0.00   ← the current default
GAP_ANALYSIS_MODEL = os.getenv("GAP_ANALYSIS_MODEL", "claude-sonnet-5")
ANTHROPIC_EFFORT = os.getenv("ANTHROPIC_EFFORT", "medium")
# Safety classifiers can decline a request (HTTP 200 + stop_reason "refusal").
# Server-side fallbacks re-run it on Anthropic's recommended model instead of
# handing us the refusal. Set ANTHROPIC_FALLBACKS=off to disable.
ANTHROPIC_FALLBACKS = os.getenv("ANTHROPIC_FALLBACKS", "default")
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Which provider writes prose — Agent 3's channel copy, Agent 6's strategy
# narrative (Agent 4 too, once it has a lead source). `gemini` or `anthropic`.
#
# Defaults to gemini for the same reason the scout does: the Anthropic balance
# ran out on 12 Aug 2026, and Agent 6 runs unattended every Monday. An agent on
# a schedule should not depend on a balance nobody is watching. Anthropic is one
# variable away when the key is funded — these are prose tasks and Opus is
# genuinely better at them than Flash.
PROSE_PROVIDER = os.getenv("PROSE_PROVIDER", "gemini").lower()

# ── Agent 3 distribution ─────────────────────────────────────────────────────
# file    — write the queue to disk, publish nothing (default; always safe)
# zernio  — POST to the Zernio / Late scheduler REST API (bearer token)
# webhook — POST the queue to a URL you control (Make.com, n8n, …)
SCHEDULER_BACKEND = os.getenv("SCHEDULER_BACKEND", "file")
SCHEDULER_BASE_URL = os.getenv("SCHEDULER_BASE_URL", "").rstrip("/")
SCHEDULER_API_KEY = os.getenv("SCHEDULER_API_KEY", "")
SCHEDULER_PATH = os.getenv("SCHEDULER_PATH", "/api/v1/posts")
QUEUE_DIR = Path(os.getenv("QUEUE_DIR", Path(__file__).resolve().parent / "queue"))
# Live posting is off unless BOTH this flag and the channel's own autopost are
# true. Publishing under the company name is not something a cron job decides.
ALLOW_AUTOPOST = os.getenv("ALLOW_AUTOPOST", "").lower() in {"1", "true", "yes"}

# ── transport tunables ───────────────────────────────────────────────────────

WEBHOOK_TIMEOUT_S = int(os.getenv("WEBHOOK_TIMEOUT_S", "30"))
WEBHOOK_MAX_ATTEMPTS = int(os.getenv("WEBHOOK_MAX_ATTEMPTS", "5"))
SIGNATURE_TOLERANCE_S = int(os.getenv("SIGNATURE_TOLERANCE_S", "300"))
ENVIRONMENT = os.getenv("PIPELINE_ENVIRONMENT", "production")

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

_SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)")


class ConfigError(RuntimeError):
    """Raised when the environment cannot support a run. Fail loud, fail early."""


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"{name} is not set. See orchestrator/.env.example for the full list."
        )
    return value


def optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# ── the domain registry ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Site:
    domain: str
    property_uri: str
    brand: str
    locale: str
    market: str
    base_url: str
    sitemap: str
    cms: dict[str, Any]
    channels: list[dict[str, Any]] = field(default_factory=list)
    data_dependencies: list[dict[str, Any]] = field(default_factory=list)
    lookback_days: int = 90
    trend_window_days: int = 28
    data_lag_days: int = 3
    min_impressions: int = 150
    max_position: float = 40.0
    max_briefs_per_run: int = 5
    compliance_profile: str = "boutimar_v1"
    # WHERE THE BYTES LIVE, which is not the same question as which CMS holds
    # them. Recorded on 20 Aug after a DirectAdmin upload procedure was written
    # for a GoDaddy-hosted site: the portfolio spans Netafraz/DirectAdmin
    # (nginx), GoDaddy cPanel (Apache), GoDaddy's DPS builder and base44 behind
    # Cloudflare, and the deploy step is different on every one of them.
    #
    # It also decides whether a merged pull request is live. On GoDaddy cPanel
    # the Astro build still has to be uploaded after the merge, so merge and
    # deploy are separate events — which is why merge_watch checks the server
    # rather than trusting GitHub.
    hosting: str = "unknown"
    hosting_note: str = ""
    status: str = "active"          # active | hold
    audit_sample_pages: int = 10    # pinned in sites.yml — see the note there
    # Named rivals for Agent 8. A list, never discovered: who you actually
    # compete with is a judgement about the business, and a crawler guessing at
    # it would confidently study the wrong sites.
    competitors: list[str] = field(default_factory=list)

    @property
    def on_hold(self) -> bool:
        return self.status.lower() == "hold"


def load_sites(
    path: Path | None = None,
    only: list[str] | None = None,
    *,
    include_hold: bool = False,
) -> list[Site]:
    """
    Read sites.yml.

    `only` filters by domain (used by --domain on the CLI). Naming a site
    explicitly **overrides its hold** — if you ask for it by name you get it.

    Held sites are excluded by default so nothing acts on a site that is not
    live. Agent 1 passes include_hold=True on purpose: it still gathers Search
    Console demand for a held domain (that data is exactly what you want on
    launch day) but emits no briefs for it.
    """
    path = path or SITES_FILE
    if not path.exists():
        raise ConfigError(f"Site registry not found at {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = raw.get("defaults") or {}
    entries = raw.get("sites") or []
    if not entries:
        raise ConfigError(f"{path} declares no sites")

    wanted = {d.lower() for d in (only or [])}
    sites: list[Site] = []
    for entry in entries:
        domain = str(entry["domain"]).lower()
        if wanted and domain not in wanted:
            continue
        merged: dict[str, Any] = {**defaults, **entry}
        sites.append(
            Site(
                domain=domain,
                property_uri=merged["property_uri"],
                brand=merged.get("brand", domain),
                locale=merged.get("locale", "en"),
                market=merged.get("market", "INT"),
                base_url=merged.get("base_url", f"https://{domain}").rstrip("/"),
                sitemap=merged.get("sitemap", f"https://{domain}/sitemap.xml"),
                cms=merged.get("cms") or {"type": "unknown", "adapter": None},
                channels=merged.get("channels") or [],
                data_dependencies=merged.get("data_dependencies") or [],
                lookback_days=int(merged.get("lookback_days", 90)),
                trend_window_days=int(merged.get("trend_window_days", 28)),
                data_lag_days=int(merged.get("data_lag_days", 3)),
                min_impressions=int(merged.get("min_impressions", 150)),
                max_position=float(merged.get("max_position", 40)),
                max_briefs_per_run=int(merged.get("max_briefs_per_run", 5)),
                compliance_profile=merged.get("compliance_profile", "boutimar_v1"),
                hosting=str(merged.get("hosting", "unknown")),
                hosting_note=str(merged.get("hosting_note", "") or "").strip(),
                status=str(merged.get("status", "active")).lower(),
                audit_sample_pages=int(merged.get("audit_sample_pages", 10)),
                competitors=[str(u).rstrip("/") for u in (merged.get("competitors") or [])],
            )
        )

    if wanted and not sites:
        raise ConfigError(f"No site in {path} matched {sorted(wanted)}")

    if not include_hold and not wanted:
        held = [s.domain for s in sites if s.on_hold]
        if held:
            sites = [s for s in sites if not s.on_hold]
            _log_hold(held)
    return sites


def _log_hold(domains: list[str]) -> None:
    import logging

    logging.getLogger("config").info(
        "skipping %d site(s) on hold: %s (use include_hold=True, or name one "
        "explicitly with --domain, to include them)",
        len(domains), ", ".join(domains),
    )


# ── google credentials ───────────────────────────────────────────────────────


def load_service_account_info() -> dict[str, Any]:
    """
    Accept the service-account key in any of three shapes, because CI secrets,
    local dev and container mounts each favour a different one:

      1. GOOGLE_SERVICE_ACCOUNT_JSON  = the raw JSON document
      2. GOOGLE_SERVICE_ACCOUNT_JSON  = the same document, base64-encoded
      3. GOOGLE_APPLICATION_CREDENTIALS = a path to the JSON file
    """
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        if not raw.lstrip().startswith("{"):
            try:
                raw = base64.b64decode(raw, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError) as exc:
                raise ConfigError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON is neither JSON nor valid base64"
                ) from exc
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
    else:
        path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        if not path:
            raise ConfigError(
                "Set GOOGLE_SERVICE_ACCOUNT_JSON (raw or base64) or "
                "GOOGLE_APPLICATION_CREDENTIALS (file path)."
            )
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"GOOGLE_APPLICATION_CREDENTIALS points at {p}, which does not exist")
        info = json.loads(p.read_text(encoding="utf-8"))

    if info.get("type") != "service_account":
        raise ConfigError(
            "The supplied Google credential is not a service account key "
            f"(type={info.get('type')!r}). OAuth client secrets will not work here — "
            "see ARCHITECTURE.md §3.1."
        )
    for key in ("client_email", "private_key", "token_uri"):
        if not info.get(key):
            raise ConfigError(f"Service account key is missing {key!r}")
    return info


# ── envelope helpers ─────────────────────────────────────────────────────────


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def rfc3339(dt: datetime | None = None) -> str:
    dt = (dt or utc_now()).astimezone(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_run_id() -> str:
    return f"run_{utc_now():%Y%m%dT%H%M}Z_{secrets.token_hex(2)}"


def new_message_id() -> str:
    return f"msg_{utc_now():%Y%m%dT%H%M%S}Z_{secrets.token_hex(6)}"


def idempotency_key(*parts: str) -> str:
    digest = hashlib.sha256("|".join(p.strip().lower() for p in parts).encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def build_envelope(
    *,
    message_type: str,
    emitted_by: str,
    target: str,
    correlation_id: str,
    idem_key: str,
    causation_id: str | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    """The envelope defined in ARCHITECTURE.md §4.0. Identical for all messages."""
    return {
        "message_id": new_message_id(),
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "idempotency_key": idem_key,
        "message_type": message_type,
        "emitted_at": rfc3339(),
        "emitted_by": emitted_by,
        "target": target,
        "attempt": attempt,
        "environment": ENVIRONMENT,
        "architecture_credit": ARCHITECTURE_CREDIT,
        "owner": OWNER,
    }


# ── webhook signing (both sides live here so they cannot drift apart) ─────────


def sign_payload(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + body,
        hashlib.sha256,
    )
    return f"sha256={mac.hexdigest()}"


def verify_signature(
    secret: str,
    signature_header: str | None,
    timestamp_header: str | None,
    body: bytes,
    tolerance_s: int = SIGNATURE_TOLERANCE_S,
) -> tuple[bool, str]:
    """Returns (ok, reason). Timestamp is checked *before* the MAC comparison."""
    if not signature_header or not timestamp_header:
        return False, "missing signature or timestamp header"
    try:
        ts = int(timestamp_header)
    except ValueError:
        return False, "timestamp header is not an integer"

    drift = abs(int(time.time()) - ts)
    if drift > tolerance_s:
        return False, f"timestamp outside the {tolerance_s}s replay window (drift {drift}s)"

    expected = sign_payload(secret, ts, body)
    if not hmac.compare_digest(expected, signature_header):
        return False, "signature mismatch"
    return True, "ok"


def signed_headers(secret: str, body: bytes, message_id: str) -> dict[str, str]:
    ts = int(time.time())
    return {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-Albaloo-Signature": sign_payload(secret, ts, body),
        "X-Albaloo-Timestamp": str(ts),
        "X-Albaloo-Message-Id": message_id,
        "X-Albaloo-Architecture-Credit": ARCHITECTURE_CREDIT,
    }


def redact(text: str) -> str:
    """Scrub anything that smells like a credential before it reaches a log."""
    return _SECRET_PATTERN.sub("[redacted]", text)
