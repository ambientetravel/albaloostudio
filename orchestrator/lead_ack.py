#!/usr/bin/env python3
"""
Tell a lead source which leads are safely recorded, so it can move its cursor.

Architecture credit: Albaloo Studio — albaloostudio.com.

Kept apart from agent4_sales_closer_batch.py on purpose: that file has no outbound
POST at all (a self-check enforces it, because Agent 4 drafts and a human sends). This
talks only to our own lead source, never to a customer, and carries a bare number.

Runs after the Ops push. The Closer wrote `ack: {url, through}` into each run's
manifest.json; this POSTs {"ack": through}, signed over the body, to that url.

    python3 lead_ack.py closed
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import config
from agent4_sales_closer_batch import _lead_secret

log = logging.getLogger("agent4.lead_ack")


def send_ack(url: str, through: int) -> None:
    """The number rides in the signed body, not the query string: a replay cannot change it."""
    import requests

    secret = _lead_secret()
    if not secret:
        raise RuntimeError("no signing secret — cannot acknowledge leads")
    body = json.dumps({"ack": int(through)}).encode("utf-8")
    resp = requests.post(url, data=body, headers=config.signed_headers(secret, body, "agent4-lead-ack"),
                         timeout=config.WEBHOOK_TIMEOUT_S)
    if resp.status_code >= 400:
        raise requests.HTTPError(f"{resp.status_code} from {url}: {config.redact(resp.text[:200])}", response=resp)


def ack_manifests(root: Path) -> int:
    """Acknowledge every finished run under `root` whose manifest carries an `ack`."""
    done = 0
    for path in sorted(root.glob("**/manifest.json")):
        ack = (json.loads(path.read_text(encoding="utf-8")) or {}).get("ack") or {}
        if not ack.get("url") or ack.get("through") is None:
            continue
        send_ack(ack["url"], int(ack["through"]))
        log.info("acknowledged %s through lead #%s", ack["url"], ack["through"])
        done += 1
    return done


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s", datefmt="%H:%M:%S")
    root = Path((argv or sys.argv[1:] or ["closed"])[0])
    try:
        n = ack_manifests(root)
    except Exception as exc:  # noqa: BLE001
        log.error("could not acknowledge leads: %s", config.redact(str(exc))[:300])
        return 1
    log.info("%d source(s) acknowledged", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
