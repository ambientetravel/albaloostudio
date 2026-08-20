#!/usr/bin/env python3
"""
Turn a merged pull request into a live URL — or say why it is not one yet.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

THE GAP THIS CLOSES
Agent 2 opens a pull request and returns `live_url: None`, correctly: a PR is
not a published page. Agent 3 (broadcast) and Agent 4 (sales) both take
`publishing.event.v1` and both dereference `live_url` — agent3_broadcaster.py
calls urlparse() on it in six places. So until something fills that field in,
two finished agents are wired to a socket with no current in it. Nothing has
ever been broadcast, because nothing has ever been marked live.

MERGED IS NOT DEPLOYED, AND THAT IS THE WHOLE POINT
The obvious version of this tool marks an article live when its PR merges. That
would be wrong here, and 18 Aug proved it: the دریانامه migration merged into
boutimarfarsi and the pages only became reachable after a human uploaded them
through DirectAdmin. On a static host behind a manual deploy, merge and deploy
are days apart — and boutimar.ir's own history is four consecutive deploy
bundles that silently omitted an edited sitemap.xml.

So a URL is promoted only when the SERVER SERVES IT:

    1. the pull request is merged            (GitHub says so)
    2. the URL returns 200                   (the host says so)
    3. the page contains the article         (the bytes say so)

Step 3 exists because journey.html and article.html always returned 200 for
any slug — a template serving many records answers happily for a record that
is not there. A soft 404 passes steps 1 and 2 and would broadcast a page that
says "این نوشته پیدا نشد".

Anything that clears 1 but fails 2 or 3 is reported as MERGED, NOT DEPLOYED,
which is a finding rather than an error — it is the queue of work waiting for
an upload.

    python3 tools/merge_watch.py --written written/
    python3 tools/merge_watch.py --written written/ --emit promoted/
    python3 tools/merge_watch.py --written written/ --format json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

log = logging.getLogger("tools.merge_watch")

ARCHITECTURE_CREDIT = config.ARCHITECTURE_CREDIT
API = "https://api.github.com"

# Words that mean "this template found no record". A page carrying one of these
# is a soft 404 however cheerful its status line.
_NOT_FOUND_MARKERS = (
    "این نوشته پیدا نشد",      # article.html, unknown slug
    "نوشته مشخص نیست",         # article.html, no slug at all
    "در حال بارگذاری",          # the shell rendered but never resolved
    "404",
)

# How much of the article's own title has to appear in the served page before
# it counts as that article. A title is the one string guaranteed to be both in
# the event and on the page.
_TITLE_MATCH_WORDS = 3


def _pr_number(pr_url: str) -> int | None:
    m = re.search(r"/pull/(\d+)", pr_url or "")
    return int(m.group(1)) if m else None


def _repo(pr_url: str) -> str | None:
    m = re.search(r"github\.com/([^/]+/[^/]+)/pull/", pr_url or "")
    return m.group(1) if m else None


def pr_state(repo: str, number: int, token: str) -> dict[str, Any]:
    """merged / open / closed-unmerged, or an error that is not a merge."""
    hdr = {"Authorization": f"Bearer {token}",
           "Accept": "application/vnd.github+json",
           "User-Agent": config.USER_AGENT}
    try:
        r = requests.get(f"{API}/repos/{repo}/pulls/{number}", headers=hdr,
                         timeout=config.WEBHOOK_TIMEOUT_S)
        r.raise_for_status()
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return {"state": "unknown",
                "detail": f"HTTP {status}: {config.redact(str(exc))[:120]}"}
    j = r.json()
    if j.get("merged_at"):
        return {"state": "merged", "merged_at": j["merged_at"],
                "merged_by": (j.get("merged_by") or {}).get("login")}
    if j.get("state") == "open":
        return {"state": "open", "detail": "still awaiting review"}
    return {"state": "closed", "detail": "closed without merging"}


def page_is_live(url: str, title: str, session: requests.Session) -> dict[str, Any]:
    """
    Does the server actually serve THIS article at this URL?

    Three ways to fail and they are kept apart, because they need different
    people: a non-200 is a deploy that has not happened, a soft 404 is a
    template answering for a record it does not have, and a page whose title is
    absent is the wrong page at the right address.
    """
    try:
        r = session.get(url, timeout=25,
                        headers={"User-Agent": config.USER_AGENT,
                                 "Cache-Control": "no-cache"})
    except requests.RequestException as exc:
        return {"live": False, "reason": f"request failed: {str(exc)[:100]}"}
    if r.status_code != 200:
        return {"live": False, "reason": f"HTTP {r.status_code} — not deployed yet"}

    text = r.text
    for marker in _NOT_FOUND_MARKERS:
        if marker in text:
            return {"live": False,
                    "reason": f"soft 404 — served 200 but the page says {marker!r}"}

    # The title, reduced to its first few words, so punctuation and a
    # " — دریانامه | بوتیمار" suffix do not decide the match.
    words = [w for w in re.split(r"\s+", (title or "").strip()) if w][:_TITLE_MATCH_WORDS]
    if words and not all(w in text for w in words):
        return {"live": False,
                "reason": "200, but the page does not contain this article's title"}
    return {"live": True, "reason": None, "bytes": len(r.content)}


def load_articles(written: Path) -> list[dict[str, Any]]:
    """
    Pair each publishing event with the CMS result that carries its PR URL.

    Agent 2 writes events/<name>.json and drafts/<name>.json under the same
    stem; the event has the content, the draft has `cms` — including pr_url and
    intended_url. Neither alone is enough.
    """
    out = []
    for ev_path in sorted((written / "events").glob("*.json")):
        try:
            event = json.loads(ev_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("unreadable event %s: %s", ev_path.name, exc)
            continue
        cms: dict[str, Any] = {}
        dr_path = written / "drafts" / ev_path.name
        if dr_path.exists():
            try:
                cms = (json.loads(dr_path.read_text(encoding="utf-8")) or {}).get("cms") or {}
            except (OSError, json.JSONDecodeError):
                cms = {}
        out.append({"name": ev_path.stem, "path": ev_path, "event": event, "cms": cms})
    return out


def promote(event: dict[str, Any], live_url: str, merged_at: str) -> dict[str, Any]:
    """
    The same event, now asserting a live page.

    A COPY is returned and the original file is never rewritten. Agent 2's
    output is the record of what Agent 2 did, and editing it in place would
    destroy the evidence that the article was a draft when it was written.
    """
    ev = json.loads(json.dumps(event))          # deep copy, no shared dicts
    pub = ev.setdefault("publication", {})
    pub["status"] = "published"
    pub["live_url"] = live_url
    pub["canonical_url"] = live_url
    pub["published_at"] = merged_at
    idx = pub.setdefault("indexation", {})
    # Stated because it is checked, not assumed: the page was fetched and it
    # served this article. Sitemap and GSC submission remain other people's
    # jobs and are left exactly as Agent 2 set them.
    idx["verified_live_at"] = config.rfc3339()
    ev.setdefault("source_brief", {}).setdefault("passthrough", {})
    return ev


def watch(written: Path, token: str | None, *, emit: Path | None = None
          ) -> list[dict[str, Any]]:
    session = requests.Session()
    rows: list[dict[str, Any]] = []

    for item in load_articles(written):
        ev, cms = item["event"], item["cms"]
        pub = ev.get("publication") or {}
        title = (ev.get("content_summary") or {}).get("title") or ""
        domain = ((ev.get("site") or {}).get("domain")
                  or (ev.get("source_brief") or {}).get("domain") or "")
        row: dict[str, Any] = {
            "name": item["name"], "domain": domain, "title": title,
            "pr_url": cms.get("pr_url") or "",
            "intended_url": cms.get("intended_url") or pub.get("live_url") or "",
        }

        if pub.get("live_url"):
            row.update(state="already live", live_url=pub["live_url"])
            rows.append(row)
            continue

        number, repo = _pr_number(row["pr_url"]), _repo(row["pr_url"])
        if not (number and repo):
            row.update(state="no pull request",
                       detail=cms.get("note") or "adapter opened no PR — nothing to watch")
            rows.append(row)
            continue
        if not token:
            row.update(state="unknown", detail="no GitHub token — PR state unreadable")
            rows.append(row)
            continue

        pr = pr_state(repo, number, token)
        row["pr_state"] = pr["state"]
        if pr["state"] != "merged":
            row.update(state=f"PR {pr['state']}", detail=pr.get("detail", ""))
            rows.append(row)
            continue

        row["merged_at"] = pr["merged_at"]
        if not row["intended_url"]:
            row.update(state="merged, no URL to check",
                       detail="the adapter recorded no intended_url")
            rows.append(row)
            continue

        check = page_is_live(row["intended_url"], title, session)
        if not check["live"]:
            # The queue of work waiting for a human upload. A finding, not a
            # failure — and the one this pipeline's history says to expect.
            row.update(state="MERGED, NOT DEPLOYED", detail=check["reason"])
            rows.append(row)
            continue

        row.update(state="live", live_url=row["intended_url"], bytes=check.get("bytes"))
        if emit:
            emit.mkdir(parents=True, exist_ok=True)
            (emit / f"{item['name']}.json").write_text(
                json.dumps(promote(ev, row["intended_url"], pr["merged_at"]),
                           ensure_ascii=False, indent=2), encoding="utf-8")
            row["emitted"] = str(emit / f"{item['name']}.json")
        rows.append(row)
    return rows


_ORDER = {"live": 0, "MERGED, NOT DEPLOYED": 1, "already live": 2}


def render_markdown(rows: list[dict[str, Any]]) -> str:
    live = [r for r in rows if r["state"] == "live"]
    stuck = [r for r in rows if r["state"] == "MERGED, NOT DEPLOYED"]
    L = ["# Merge watch — which drafts are actually live", "",
         f"Architecture credit: **{ARCHITECTURE_CREDIT}**", "",
         "A URL is promoted only when the pull request is merged **and** the "
         "server returns 200 **and** the page contains the article. Merged is "
         "not deployed: on a static host behind a manual upload those are days "
         "apart, and a template answering 200 for a slug it does not have is a "
         "soft 404, not a page.", ""]
    if live:
        L.append(f"## {len(live)} newly live")
        L.append("These now carry a `live_url`, so Agent 3 can broadcast them.")
        L.append("")
        for r in live:
            L.append(f"- **{r['title'] or r['name']}** — {r['live_url']}")
        L.append("")
    if stuck:
        L.append(f"## {len(stuck)} merged but NOT deployed")
        L.append("The pull request is in. The page is not on the server. Nothing "
                 "downstream can run on these until someone deploys.")
        L.append("")
        for r in stuck:
            L.append(f"- **{r['title'] or r['name']}** — `{r['intended_url']}`  \n"
                     f"  {r.get('detail','')}  \n"
                     f"  merged {r.get('merged_at','?')} · {r['pr_url']}")
        L.append("")
    rest = [r for r in rows if r["state"] not in ("live", "MERGED, NOT DEPLOYED")]
    if rest:
        L.append("## Everything else")
        L.append("")
        L.append("| Article | State | Detail |")
        L.append("|---|---|---|")
        for r in sorted(rest, key=lambda x: x["state"]):
            L.append(f"| {r['title'] or r['name']} | {r['state']} | "
                     f"{r.get('detail','')} |")
        L.append("")
    if not rows:
        L.append("No Agent 2 output found to watch.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--written", type=Path, default=Path("written"),
                    help="Agent 2 output directory (contains events/ and drafts/)")
    ap.add_argument("--emit", type=Path,
                    help="write promoted publishing.event.v1 files here for Agent 3")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")

    if not (args.written / "events").is_dir():
        log.error("%s has no events/ directory — nothing to watch", args.written)
        return 2

    token = (config.optional_env("ASTRO_GITHUB_TOKEN")
             or config.optional_env("GITHUB_TOKEN"))
    if not token:
        log.warning("no ASTRO_GITHUB_TOKEN or GITHUB_TOKEN — pull request state "
                    "cannot be read, so nothing can be promoted")

    rows = watch(args.written, token, emit=args.emit)
    for r in rows:
        log.info("%s — %s", r["name"], r["state"])

    text = (render_markdown(rows) if args.format == "md"
            else json.dumps(rows, ensure_ascii=False, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        log.info("wrote %s", args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
