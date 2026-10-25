#!/usr/bin/env python3
"""
ops-sync phase 4: the Social tab of the Albaloo Ops app, from Agent 3's posts.

Architecture credit: Albaloo Studio — albaloostudio.com. Spec: OPS-APP.md.

Agent 3 (Broadcaster) composes posts for each published article and holds them
at the autopost gate (ALLOW_AUTOPOST off, autopost: false per channel). The
held posts live only in its run artifact (agent3-broadcast/posts/*.json). This
puts each one in front of the team as a preview card:

  push     one SocialPost per post: site, channel, the copy with its hashtags,
           the article's photo, the article link; status held (or posted when
           the scheduler has a published_at)
  decide   a team decision in the app sets the row's status: approve → approved,
           reject → rejected. The decision fields stay as the record of who/when.

**Nothing here publishes.** Posting under the company name stays a human act:
an approved post is a post someone may now put up by hand (copy + image are on
the card), or the trigger for switching that one channel's autopost on. The
approve button never reaches a social network from this code.

Row key: channel + copy (the app's SocialPost has no id field of its own;
Agent 3 already guarantees identical copy is never produced twice per channel).

    python3 tools/ops_social.py --posts <agent3-broadcast dir>            # dry run
    python3 tools/ops_social.py --posts <agent3-broadcast dir> --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion_review_sync as nrs  # noqa: E402
import ops_sync  # noqa: E402

ENTITY = "SocialPost"
DECIDED = {"approve": "approved", "reject": "rejected"}


def _ent(path: str = "") -> str:
    return f"/{ops_sync.OPS_APP}/entities/{ENTITY}{path}"


def copy_text(post: dict) -> str:
    c = post.get("copy") or {}
    tags = " ".join(h if str(h).startswith("#") else f"#{h}" for h in c.get("hashtags") or [])
    return (str(c.get("body") or "").strip() + ("\n\n" + tags if tags else "")).strip()


def image_of(post: dict) -> str:
    for a in post.get("assets") or []:
        if isinstance(a, dict) and (a.get("type") in (None, "image")) and a.get("url"):
            return str(a["url"])
    return ""


def to_row(post: dict, now: str) -> dict:
    url = str((post.get("copy") or {}).get("cta_url") or "")
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return {"property": host, "channel": str(post.get("channel") or ""), "copy": copy_text(post),
            "image_url": image_of(post), "article_url": url,
            "status": "posted" if post.get("published_at") else "held", "synced_at": now}


def key(r: dict) -> str:
    return f"{r.get('channel')}|{r.get('copy')}"


def posts_in(folder: Path) -> list[dict]:
    out = []
    for p in sorted(folder.glob("**/posts/*.json")):
        out.extend(json.loads(p.read_text(encoding="utf-8")).get("posts") or [])
    return out


def plan(posts: list[dict], have: list[dict], now: str) -> dict:
    by_key = {key(h): h for h in have}
    create, update = [], []
    seen = set()
    for p in posts:
        r = to_row(p, now)
        k = key(r)
        if k in seen or not r["copy"]:
            continue
        seen.add(k)
        if k not in by_key:
            create.append(r)
        elif r["status"] == "posted" and by_key[k].get("status") != "posted":
            update.append((by_key[k], {"status": "posted", "synced_at": now}))
    for h in have:                                   # team decisions → status
        want = DECIDED.get(str(h.get("decision") or ""))
        if want and h.get("status") not in (want, "posted"):
            update.append((h, {"status": want, "synced_at": now}))
    return {"create": create, "update": update}


def run(folder: Path, apply: bool) -> list[str]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    code, d = nrs.b44("GET", _ent("/v2/list?limit=1000"))
    if code != 200:
        raise RuntimeError(f"base44 {code} listing {ENTITY}: {str(d)[:200]}")
    have = nrs._b44_items(d)
    posts = posts_in(folder)
    p = plan(posts, have, now)
    log = [f"agent 3 posts: {len(posts)} · app: {len(have)} rows"]
    for r in p["create"]:
        log.append(f"create      {r['channel']:<10} {r['property']} · image {'yes' if r['image_url'] else 'NO'}")
        if apply:
            c, resp = nrs.b44("POST", _ent(), r)
            if c not in (200, 201):
                log.append(f"  ! base44 {c}: {str(resp)[:160]}")
    for h, fields in p["update"]:
        log.append(f"update      {h.get('channel')} {h.get('property')} → {fields['status']}")
        if apply:
            c, resp = nrs.b44("PUT", _ent(f"/{h['id']}"), fields)
            if c != 200:
                log.append(f"  ! base44 {c}: {str(resp)[:160]}")
    ready = sum(1 for h in have if h.get("decision") == "approve")
    log.append(f"summary: {len(p['create'])} created, {len(p['update'])} updated, {ready} approved and "
               f"waiting to be posted by hand (nothing is published from here)"
               + ("" if apply else "  (dry run — nothing written)"))
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--posts", required=True, help="folder holding Agent 3's agent3-broadcast artifact")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if not os.environ.get("BASE44_ACCESS_TOKEN"):
        print("not configured: BASE44_ACCESS_TOKEN — nothing synced")
        return 0
    if not Path(a.posts).exists():
        print(f"no Agent 3 artifact at {a.posts} — nothing to sync")
        return 0
    print("\n".join(run(Path(a.posts), a.apply)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
