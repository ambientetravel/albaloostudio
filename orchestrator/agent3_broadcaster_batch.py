#!/usr/bin/env python3
"""
Agent 3 — Broadcaster, batch runner.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Reads the publishing.event.v1 files Agent 2 produced, writes channel-specific
copy with Claude, runs the compliance gate on that copy, hands each post to the
scheduler backend, and emits campaign.log.v1.

Same reasoning as agent2_writer_batch: Agent 3's FastAPI listener expects to be
woken by a signed webhook from an external Agent 2. Both now run in GitHub
Actions, so the events are read directly off the upstream artifact — no
webhook, no signature, no AGENT3_WEBHOOK_URL. The listener stays as the
reference implementation and the thing selfcheck exercises over HTTP.

What this does NOT do is post anything. Live posting still needs two
independent yeses — ALLOW_AUTOPOST=1 in the environment AND autopost: true on
that channel in sites.yml — and every account_ref in the registry is null
today, so the scheduler holds the copy rather than delivering it. That is the
designed state, not a gap: the copy is worth composing and reviewing before any
account exists to send it from.

    python3 agent3_broadcaster_batch.py --events inbox/written/events
    python3 agent3_broadcaster_batch.py --events e/ --no-llm
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import compliance
import config
from agent3_broadcaster import (
    SCHEDULER,
    PublishingEvent,
    _call_claude,
    _campaign_id,
    _resolve_channels,
    _schedule_times,
    _with_utm,
    autopost_allowed,
    build_campaign_log,
    media_ok,
)

log = logging.getLogger("agent3.broadcaster_batch")

ARCHITECTURE_CREDIT = config.ARCHITECTURE_CREDIT


@dataclass
class Outcome:
    event_file: str
    campaign_id: str = ""
    domain: str = ""
    title: str = ""
    status: str = "pending"        # composed | blocked | failed | skipped
    posts: int = 0
    held: int = 0
    blocked_media: int = 0
    error: str = ""
    violations: list[dict[str, Any]] = field(default_factory=list)


def _stub_copy(event: PublishingEvent, channels: list[str]) -> tuple[list[dict], dict]:
    """
    Channel copy assembled from the publication itself, no model involved.

    Exists for the same reason as Agent 2's stub: channel resolution, the
    compliance gate, the scheduler backends, the media pre-flight and
    campaign.log assembly have all broken before for reasons unrelated to the
    model, and each cost an API round-trip to find. Never publishable.
    """
    cs = event.content_summary
    body = f"{cs.title}\n\n{cs.meta_description}".strip()
    return (
        [
            {
                "channel": ch,
                "audience": "b2b" if ch == "linkedin" else "d2c",
                "body": body,
                "hashtags": [],
                "language": event.publication.language,
                "angle": "stub",
            }
            for ch in channels
        ],
        {"provider": "stub", "model": "none", "note": "NOT MODEL OUTPUT — structural test only"},
    )


def broadcast_one(payload: dict[str, Any], out_dir: Path, *, no_llm: bool) -> Outcome:
    """Compose, gate, schedule and record one publishing event. Never raises."""
    name = payload.get("envelope", {}).get("message_id", "unknown")
    oc = Outcome(event_file=name)

    try:
        event = PublishingEvent.model_validate(payload)
    except Exception as exc:
        oc.status, oc.error = "failed", f"payload does not match publishing.event.v1: {exc}"
        return oc

    oc.campaign_id = _campaign_id(event)
    # title lives on content_summary, not publication — publication carries
    # where and how it was published, content_summary carries what it says.
    oc.title = event.content_summary.title
    oc.domain = event.publication.live_url

    profile = str(event.compliance.get("profile") or "boutimar_v1")
    if profile not in compliance.PROFILES:
        profile = "boutimar_v1"

    try:
        # You cannot broadcast a page that does not exist. When Agent 2 staged a
        # draft rather than publishing — no adapter configured, a PR awaiting
        # review, a failed push — live_url is null, and posting a link to it
        # would send readers to a 404 and burn the one impression you get.
        if not event.publication.live_url:
            oc.status = "skipped"
            oc.error = ("nothing was published — Agent 2 staged a draft "
                        f"(intended: {getattr(event.publication, 'intended_url', None) or 'unknown'}). "
                        "Broadcast when the page is live.")
            return oc

        channel_cfgs = _resolve_channels(event)
        if not channel_cfgs:
            oc.status = "skipped"
            oc.error = "no channels configured for this site in sites.yml"
            return oc

        names = [c["name"] for c in channel_cfgs]
        drafts, gen_meta = (_stub_copy(event, names) if no_llm
                            else _call_claude(event, names, profile)[:2])

        priced = event.content_summary.offer.has_offer
        ctx = {
            "priced_facts": priced,
            "price_asof": event.content_summary.offer.price_asof if priced else None,
            "itinerary_ports": event.content_summary.key_points,
        }
        warnings: list[compliance.Violation] = []
        for d in drafts:
            surface = compliance.assertive_surface([d["body"], d.get("hashtags", [])])
            warnings.extend(compliance.enforce(surface, profile, context=ctx))

        times = _schedule_times(len(drafts), priority_now=False)
        by_name = {c["name"]: c for c in channel_cfgs}
        posts: list[dict[str, Any]] = []

        for d, when in zip(drafts, times):
            cfg = by_name.get(d["channel"], {"name": d["channel"], "autopost": False})
            post = {
                "channel": d["channel"],
                "audience": d["audience"],
                "account_ref": cfg.get("account_ref"),
                "status": "scheduled",
                "scheduled_for": when,
                "published_at": None,
                "external_id": None,
                "permalink": None,
                "copy": {
                    "body": d["body"],
                    "hashtags": d.get("hashtags", []),
                    "cta_url": _with_utm(
                        event.distribution_hints.cta_url or event.publication.live_url,
                        d["channel"], oc.campaign_id, event.distribution_hints.utm),
                    "language": d.get("language", event.publication.language),
                    # Dedupe guard, required by campaign.log.v1. Identical copy
                    # is never posted twice to one channel however many times an
                    # event is redelivered. Omitting it was caught by schema
                    # validation, not by reading the code — which is the whole
                    # reason the schema is validated rather than trusted.
                    "hash": "sha256:" + hashlib.sha256(
                        f"{d['channel']}|{d['body']}".encode("utf-8")).hexdigest(),
                },
                "assets": event.distribution_hints.assets,
                "angle": d.get("angle"),
                "error": None,
            }
            result = SCHEDULER.schedule(
                post=post, channel_cfg=cfg, campaign_id=oc.campaign_id,
                correlation_id=event.envelope.correlation_id,
            )
            post.update(status=result.status, external_id=result.external_id,
                        permalink=result.permalink, error=result.error)

            # Most specific reason first: a missing image is a harder stop than
            # a closed autopost gate. No flag flips an Instagram post live with
            # nothing attached to it.
            has_media, media_reason = media_ok(post)
            allowed, gate_reason = autopost_allowed(cfg)
            if not has_media:
                post["hold_reason"] = media_reason
                oc.blocked_media += 1
            elif not allowed:
                post["hold_reason"] = gate_reason
                oc.held += 1
            posts.append(post)

        oc.posts = len(posts)
        campaign_log = build_campaign_log(event, oc.campaign_id, posts, warnings, profile)

        (out_dir / "campaigns").mkdir(parents=True, exist_ok=True)
        (out_dir / "campaigns" / f"{oc.campaign_id}.json").write_text(
            json.dumps(campaign_log, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "posts").mkdir(parents=True, exist_ok=True)
        (out_dir / "posts" / f"{oc.campaign_id}.json").write_text(
            json.dumps({"campaign_id": oc.campaign_id, "posts": posts},
                       ensure_ascii=False, indent=2), encoding="utf-8")

        oc.status = "composed"
        return oc

    except compliance.ComplianceError as exc:
        oc.status = "blocked"
        oc.error = str(exc)[:400]
        oc.violations = [v.as_dict() for v in exc.violations if v.severity == compliance.BLOCK]
        (out_dir / "blocked").mkdir(parents=True, exist_ok=True)
        (out_dir / "blocked" / f"{name}.json").write_text(
            json.dumps({"event": payload, "violations": oc.violations},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        return oc
    except Exception as exc:
        oc.status = "failed"
        oc.error = config.redact(str(exc))[:400]
        return oc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True, help="directory of publishing.event.v1 JSON files")
    ap.add_argument("--out", default="broadcast")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-llm", action="store_true",
                    help="assemble copy from the publication instead of calling Claude")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")

    ev_dir = Path(args.events)
    if not ev_dir.is_dir():
        log.error("no such directory: %s", ev_dir)
        return 2

    files = sorted(ev_dir.glob("*.json"))
    if not files:
        log.warning("no publishing events in %s — nothing to broadcast", ev_dir)
        return 0

    if not args.no_llm:
        try:
            config.require_env("ANTHROPIC_API_KEY")
        except config.ConfigError as exc:
            log.error("%s", exc)
            log.error("Agent 3 writes channel copy with Claude. Set ANTHROPIC_API_KEY, "
                      "or run --no-llm to exercise everything except the model call.")
            return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[Outcome] = []

    for path in files:
        if args.limit and len(outcomes) >= args.limit:
            break
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            outcomes.append(Outcome(event_file=path.name, status="failed",
                                    error=f"unreadable: {exc}"))
            continue
        oc = broadcast_one(payload, out_dir, no_llm=args.no_llm)
        outcomes.append(oc)
        log.info("%s — %s — %d post(s), %d held, %d blocked on media — %s",
                 oc.campaign_id or "?", oc.status, oc.posts, oc.held,
                 oc.blocked_media, oc.title[:60])
        if oc.status == "blocked":
            for v in oc.violations[:3]:
                log.error("    BLOCKED %s: %s", v.get("rule"), str(v.get("excerpt"))[:100])
        elif oc.status in ("failed", "skipped"):
            log.warning("    %s", oc.error)

    manifest = {
        "architecture_credit": ARCHITECTURE_CREDIT,
        "owner": config.OWNER,
        "no_llm": args.no_llm,
        "scheduler_backend": config.SCHEDULER_BACKEND,
        "autopost_env_allowed": config.ALLOW_AUTOPOST,
        "events_seen": len(files),
        "composed": sum(o.status == "composed" for o in outcomes),
        "blocked": sum(o.status == "blocked" for o in outcomes),
        "skipped": sum(o.status == "skipped" for o in outcomes),
        "failed": sum(o.status == "failed" for o in outcomes),
        "posts_total": sum(o.posts for o in outcomes),
        "posts_held": sum(o.held for o in outcomes),
        "posts_blocked_media": sum(o.blocked_media for o in outcomes),
        "outcomes": [o.__dict__ for o in outcomes],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Agent 3 finished — %d composed, %d blocked, %d skipped, %d failed | "
             "%d post(s): %d held, %d blocked on media",
             manifest["composed"], manifest["blocked"], manifest["skipped"],
             manifest["failed"], manifest["posts_total"],
             manifest["posts_held"], manifest["posts_blocked_media"])

    # A held post is the design working. Only a real error is a failure.
    return 1 if manifest["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
