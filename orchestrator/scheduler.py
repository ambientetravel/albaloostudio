"""
Albaloo Orchestration Pipeline — social scheduler adapters (Agent 3).

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Agent 3 composes copy; this module decides where the copy goes. Three backends,
selected by SCHEDULER_BACKEND:

    file     write the queue to disk and publish nothing        (default)
    zernio   POST to the Zernio / Late scheduler REST API
    webhook  POST the whole queue to a URL you control

The default is `file`. Posting under the company name is an outbound action, so
it needs two independent yeses: ALLOW_AUTOPOST=1 in the environment AND
`autopost: true` on that channel in sites.yml. Either one missing and the post
is a draft — on the `zernio` backend that means `isDraft: true`, which puts it
in the dashboard for a human to review and release rather than on a feed.

The Zernio payload shape here was verified against the live API on 2026-08-06
via its documented request body and the `validate_post` endpoint. Two things
that verification caught and that the code now enforces:

  * **Instagram rejects text-only posts** — media is mandatory. Agent 2 emits
    `hero_image: null` whenever there is no credited image, so an Instagram post
    with nothing attached is held here rather than failing at publish time.
  * The API **resolves the media URL**, so a fabricated image link fails
    validation upstream. Good: it is one more place an invented asset dies.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import requests

import config

log = logging.getLogger("agent3.scheduler")

# Channels that will not accept a text-only post.
MEDIA_REQUIRED = frozenset({"instagram", "tiktok", "pinterest", "youtube"})


@dataclass
class ScheduleResult:
    status: str                  # scheduled | draft | queued | blocked | failed
    external_id: str | None = None
    permalink: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "external_id": self.external_id,
            "permalink": self.permalink,
            "error": self.error,
        }


def autopost_allowed(channel_cfg: dict[str, Any]) -> tuple[bool, str]:
    """Both gates must open. Returns (allowed, reason_when_not)."""
    if not config.ALLOW_AUTOPOST:
        return False, "ALLOW_AUTOPOST is not set — held as a draft"
    if not channel_cfg.get("autopost"):
        return False, f"autopost is false for {channel_cfg.get('name')} in sites.yml"
    return True, ""


def media_ok(post: dict[str, Any]) -> tuple[bool, str]:
    """
    Pre-flight the platform's media requirement before we spend an API call.

    Verified against the live API: an Instagram post with no media comes back
    `{'valid': False, 'errors': [{'platform': 'instagram', 'error': 'Instagram
    posts require media content (images or videos)'}]}`.
    """
    channel = post.get("channel", "")
    if channel not in MEDIA_REQUIRED:
        return True, ""
    if post.get("assets"):
        return True, ""
    return False, (
        f"{channel} requires an image or video and none was supplied — Agent 2 "
        "emits hero_image: null when there is no credited, licensed asset"
    )


class Scheduler:
    """Dispatches on config.SCHEDULER_BACKEND. One instance per Agent 3 process."""

    def __init__(self, backend: str | None = None) -> None:
        self.backend = (backend or config.SCHEDULER_BACKEND).lower()
        self.session = requests.Session()
        if self.backend not in {"file", "zernio", "webhook"}:
            raise config.ConfigError(
                f"Unknown SCHEDULER_BACKEND {self.backend!r} "
                "(expected file | zernio | webhook)"
            )

    # ── public API ───────────────────────────────────────────────────────────

    def schedule(
        self,
        *,
        post: dict[str, Any],
        channel_cfg: dict[str, Any],
        campaign_id: str,
        correlation_id: str,
    ) -> ScheduleResult:
        ok, why = media_ok(post)
        if not ok:
            log.warning("%s — %s", post["channel"], why)
            self._queue_to_file(post, campaign_id, correlation_id, status="blocked")
            return ScheduleResult(status="blocked", error=why)

        live, reason = autopost_allowed(channel_cfg)

        if self.backend == "file":
            return self._queue_to_file(post, campaign_id, correlation_id, status="queued")
        if self.backend == "zernio":
            # Not live ⇒ push as a draft to the dashboard, which is where the
            # human reviews and releases it. Still not a publish.
            return self._zernio(post, channel_cfg, draft=not live)
        return self._webhook(post, campaign_id, correlation_id)

    # ── backends ─────────────────────────────────────────────────────────────

    def _queue_to_file(
        self,
        post: dict[str, Any],
        campaign_id: str,
        correlation_id: str,
        *,
        status: str,
    ) -> ScheduleResult:
        out = config.QUEUE_DIR / correlation_id
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{campaign_id}-{post['channel']}.json"
        path.write_text(
            json.dumps(
                {
                    "architecture_credit": config.ARCHITECTURE_CREDIT,
                    "campaign_id": campaign_id,
                    "correlation_id": correlation_id,
                    "queued_at": config.rfc3339(),
                    "status": status,
                    "post": post,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        log.info("%s %s → %s", status, post["channel"], path)
        return ScheduleResult(status=status)

    @staticmethod
    def build_zernio_body(
        post: dict[str, Any], channel_cfg: dict[str, Any], *, draft: bool
    ) -> dict[str, Any]:
        """
        The POST /v1/posts request body. Split out from the transport so
        selfcheck.py can assert the shape without touching the network.

        `scheduledFor` is sent naive alongside an explicit `timezone` — that is
        the form the API's own quickstart uses, and it avoids the ambiguity of a
        Z-suffixed instant paired with a timezone field.
        """
        copy = post.get("copy", {})
        body: dict[str, Any] = {
            "content": copy.get("body", ""),
            "platforms": [
                {
                    "platform": post["channel"],
                    "accountId": channel_cfg.get("account_ref") or post.get("account_ref"),
                }
            ],
            "timezone": "UTC",
        }
        if copy.get("hashtags"):
            body["hashtags"] = copy["hashtags"]
        if post.get("assets"):
            body["mediaItems"] = [
                {"type": a.get("type", "image"), "url": a["url"]}
                for a in post["assets"]
                if a.get("url")
            ]
        if draft:
            # Explicit, not implied. The API also defaults to draft when no
            # scheduledFor is present, but relying on that is how a post that
            # was supposed to be held ends up live after a field rename.
            body["isDraft"] = True
        elif post.get("scheduled_for"):
            body["scheduledFor"] = str(post["scheduled_for"]).replace("Z", "")
        return body

    def _zernio(
        self, post: dict[str, Any], channel_cfg: dict[str, Any], *, draft: bool
    ) -> ScheduleResult:
        base = config.SCHEDULER_BASE_URL or "https://zernio.com"
        key = config.SCHEDULER_API_KEY
        if not key:
            return ScheduleResult(
                status="failed",
                error="SCHEDULER_API_KEY is required for the zernio backend",
            )

        body = Scheduler.build_zernio_body(post, channel_cfg, draft=draft)
        if not body["platforms"][0]["accountId"]:
            return ScheduleResult(
                status="failed",
                error=(
                    f"no account_ref for {post['channel']} in sites.yml — connect the "
                    "account in the scheduler and record its ID"
                ),
            )

        try:
            resp = self.session.post(
                f"{base}{config.SCHEDULER_PATH}",
                json=body,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "User-Agent": config.USER_AGENT,
                },
                timeout=config.WEBHOOK_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            return ScheduleResult(status="failed", error=f"transport error: {exc}")

        if not (200 <= resp.status_code < 300):
            return ScheduleResult(
                status="failed", error=f"HTTP {resp.status_code}: {resp.text[:300]}"
            )
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        record = (payload.get("data") or payload).get("post", payload) or {}
        return ScheduleResult(
            status="draft" if draft else "scheduled",
            external_id=str(record.get("_id") or record.get("id") or "") or None,
            permalink=record.get("permalink") or record.get("releaseURL"),
        )

    def _webhook(
        self, post: dict[str, Any], campaign_id: str, correlation_id: str
    ) -> ScheduleResult:
        """Signed POST to a URL the owner controls (Make.com, n8n, a PHP endpoint)."""
        base = config.SCHEDULER_BASE_URL
        if not base:
            return ScheduleResult(
                status="failed", error="SCHEDULER_BASE_URL is required for the webhook backend"
            )
        payload = {
            "architecture_credit": config.ARCHITECTURE_CREDIT,
            "campaign_id": campaign_id,
            "correlation_id": correlation_id,
            "post": post,
        }
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        secret = config.optional_env("WEBHOOK_SIGNING_SECRET")
        headers = (
            config.signed_headers(secret, raw, campaign_id)
            if secret
            else {"Content-Type": "application/json", "User-Agent": config.USER_AGENT}
        )
        try:
            resp = self.session.post(
                base, data=raw, headers=headers, timeout=config.WEBHOOK_TIMEOUT_S
            )
        except requests.RequestException as exc:
            return ScheduleResult(status="failed", error=f"transport error: {exc}")
        if not (200 <= resp.status_code < 300):
            return ScheduleResult(
                status="failed", error=f"HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return ScheduleResult(status="scheduled")
