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

# ── models (overridable; never pinned inside a prompt) ────────────────────────

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

# Claude Opus 5 is the default for Agents 3 and 4. Notes that matter for the
# request shape on this model family:
#   * temperature / top_p / top_k are REMOVED — sending any of them is a 400.
#     Steer tone with the prompt, not sampling.
#   * thinking is ON by default; `budget_tokens` is a 400. Depth is `effort`.
#   * assistant-turn prefills are a 400 — structured output replaces them.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
ANTHROPIC_EFFORT = os.getenv("ANTHROPIC_EFFORT", "medium")
# Safety classifiers can decline a request (HTTP 200 + stop_reason "refusal").
# Server-side fallbacks re-run it on Anthropic's recommended model instead of
# handing us the refusal. Set ANTHROPIC_FALLBACKS=off to disable.
ANTHROPIC_FALLBACKS = os.getenv("ANTHROPIC_FALLBACKS", "default")
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"

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
    status: str = "active"          # active | hold
    audit_sample_pages: int = 10    # pinned in sites.yml — see the note there

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
                status=str(merged.get("status", "active")).lower(),
                audit_sample_pages=int(merged.get("audit_sample_pages", 10)),
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
