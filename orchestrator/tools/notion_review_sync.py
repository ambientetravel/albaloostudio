#!/usr/bin/env python3
"""
Content Review ⇄ GitHub. Keeps the Notion "Content Review" board and the
pipeline's article pull requests in step, in both directions.

  GitHub → Notion   every open agent2/* PR on a site repo gets a row
                    (To review, with its house-rules verdict and word count);
                    a PR merged or closed elsewhere flips its row to
                    Published / Rejected.
  Notion → GitHub   Approved     → the PR is squash-merged (never a BLOCK;
                                   never one GitHub says cannot merge)
                    Needs edits  → the Feedback text is posted on the PR once
                    Rejected     → the PR is closed with the Feedback as reason

The board is the review surface for Alireza and his team; nobody needs GitHub.
Merging is not deploying: each site's own deploy path publishes afterwards.

    python3 tools/notion_review_sync.py            # dry run: prints what it would do
    python3 tools/notion_review_sync.py --apply

Env: NOTION_TOKEN (internal integration, the database shared with it),
     NOTION_REVIEW_DB (database id), GITHUB_TOKEN (PR read/write on the site repos).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_review  # noqa: E402

NOTION = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
DEFAULT_DB = "5d903cb86e184d1883cd1b858b90d2fc"
SITES = {
    "ambientetravel/boutimar": "boutimar.com",
    "ambientetravel/boutimarfarsi": "boutimar.ir",
    "ambientetravel/cruise24-ir": "cruise24.ir",
    "ambientetravel/exploreorient": "exploreorient.com",
}
_FA = re.compile(r"[؀-ۿ]")


# ── transport ────────────────────────────────────────────────────────────────
def _curl(method: str, url: str, headers: list[str], body: dict | None = None) -> tuple[int, object]:
    cmd = ["curl", "-sS", "--max-time", "60", "-X", method, "-w", "\n%{http_code}", url]
    for h in headers:
        cmd[1:1] = ["-H", h]
    if body is not None:
        cmd[1:1] = ["-H", "Content-Type: application/json", "-d", json.dumps(body, ensure_ascii=False)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    raw, _, code = out.rpartition("\n")
    try:
        return int(code or 0), (json.loads(raw) if raw.strip() else {})
    except ValueError:
        return int(code or 0), raw


def gh(method: str, path: str, body: dict | None = None):
    return _curl(method, "https://api.github.com" + path,
                 [f"Authorization: Bearer {os.environ.get('GITHUB_TOKEN', '')}",
                  "Accept: application/vnd.github+json"], body)


def notion(method: str, path: str, body: dict | None = None):
    return _curl(method, NOTION + path,
                 [f"Authorization: Bearer {os.environ.get('NOTION_TOKEN', '')}",
                  f"Notion-Version: {NOTION_VERSION}"], body)


# ── Notion rows ──────────────────────────────────────────────────────────────
def _txt(prop: dict) -> str:
    items = prop.get("rich_text") or prop.get("title") or []
    return "".join(i.get("plain_text", "") for i in items)


def rows(db: str) -> dict[str, dict]:
    """Pipeline ID → {page_id, status, feedback}. Paginates."""
    out, cursor = {}, None
    while True:
        body = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
        code, d = notion("POST", f"/databases/{db}/query", body)
        if code != 200:
            raise RuntimeError(f"Notion query {code}: {str(d)[:200]}")
        for p in d.get("results", []):
            pr = p["properties"]
            pid = _txt(pr.get("Pipeline ID", {}))
            if pid:
                out[pid] = {"page_id": p["id"],
                            "status": ((pr.get("Status") or {}).get("select") or {}).get("name", ""),
                            "gate": ((pr.get("House rules") or {}).get("select") or {}).get("name", ""),
                            "feedback": _txt(pr.get("Feedback", {})),
                            "live": ((pr.get("Live page") or {}).get("url")) or ""}
        if not d.get("has_more"):
            return out
        cursor = d.get("next_cursor")


def row_properties(r: dict) -> dict:
    p = {
        "Article": {"title": [{"text": {"content": r["title"][:200]}}]},
        "Site": {"select": {"name": r["site"]}},
        "Status": {"select": {"name": "To review"}},
        "House rules": {"select": {"name": r["gate"]}},
        "Language": {"select": {"name": "Farsi" if _FA.search(r["title"]) else "English"}},
        "Pipeline ID": {"rich_text": [{"text": {"content": r["pid"]}}]},
        "Written": {"date": {"start": r["written"]}},
    }
    if r.get("kind") == "base44":
        p["Live page"] = {"url": r["url"]}      # the text is in the page; the URL goes live on Approve
    else:
        p["Read it"] = {"url": r["url"]}
    if r.get("live"):
        p["Live page"] = {"url": r["live"]}
    if r.get("words"):
        p["Words"] = {"number": r["words"]}
    return p


def feedback_marker(status: str, feedback: str) -> str:
    """Stable across runs (hash() is salted per process, so the same feedback
    would be re-posted every hour)."""
    return f"<!-- review:{status}:{hashlib.sha1(feedback.encode('utf-8')).hexdigest()[:12]} -->"


def set_status(page_id: str, status: str) -> None:
    notion("PATCH", f"/pages/{page_id}", {"properties": {"Status": {"select": {"name": status}}}})


# ── GitHub side ──────────────────────────────────────────────────────────────
def open_article_prs() -> list[dict]:
    out = []
    for repo, site in SITES.items():
        code, prs = gh("GET", f"/repos/{repo}/pulls?state=open&per_page=50")
        if code != 200:
            print(f"  ! {repo}: GitHub {code} — skipped")
            continue
        for p in prs:
            if not p["head"]["ref"].startswith("agent2/"):
                continue
            try:
                review = pr_review.review_pr(repo, p["number"], pr_review.REPOS.get(repo, "boutimar_v1"))
                verdict = review["verdict"]
            except Exception:  # noqa: BLE001 — an unreadable diff is a WARN for a human, not a crash
                review, verdict = {}, "WARN"
            out.append({"pid": f"{repo.split('/')[1]}#{p['number']}", "repo": repo, "num": p["number"],
                        "site": site, "url": p["html_url"], "gate": verdict, "review": review,
                        "sha": p["head"]["sha"],
                        "title": re.sub(r"^(Agent 2 draft|دریانامه draft):\s*", "", p["title"]).strip(),
                        "written": p["created_at"][:10], "live": "", "words": None})
    return out


# ── base44 sites: drafts live as Article records, not pull requests ─────────
# cruisebaz.com and ambientetravel.com publish through base44: the writer stores a
# draft Article record; flipping status to "published" is the go-live (no app
# Publish). Until 5 Oct those drafts never reached this board — Alireza published
# them by hand in base44's Data tab. Pipeline ID = "<domain><slug>".
BASE44_SITES = {"cruisebaz.com": ("69a20a26965079a660bdda58", "boutimar_v1"),
                "ambientetravel.com": ("69a62d9872bf72a85738b6f8", "orient_v1")}
B44 = "https://app.base44.com/api/apps"


def b44(method: str, path: str, body: dict | None = None):
    return _curl(method, B44 + path,
                 [f"Authorization: Bearer {os.environ.get('BASE44_ACCESS_TOKEN', '')}"], body)


def _b44_items(d) -> list[dict]:
    return d if isinstance(d, list) else (d.get("items") or d.get("records") or []) if isinstance(d, dict) else []


def base44_gate(a: dict, profile: str) -> tuple[str, dict]:
    """House-rules verdict for a base44 Article record: title, summary, body and FAQ."""
    import compliance  # noqa: PLC0415 — orchestrator/ is on sys.path via pr_review
    text = "\n".join([a.get("title", ""), a.get("meta_description", ""), str(a.get("body_markdown") or "")] +
                     [f"{x.get('q', '')} {x.get('a', '')}" for x in a.get("faq") or []])
    blocks, warns = [], []
    for v in compliance.check(text, profile):
        row = {"rule": v.rule, "excerpt": v.excerpt, "fix": v.message}
        (blocks if v.severity == compliance.BLOCK else warns).append(row)
    return ("BLOCK" if blocks else ("WARN" if warns else "PASS")), {"blocks": blocks, "warns": warns}


def base44_drafts() -> list[dict]:
    if not os.environ.get("BASE44_ACCESS_TOKEN"):
        return []
    out = []
    for domain, (app, profile) in BASE44_SITES.items():
        code, d = b44("GET", f"/{app}/entities/Article/v2/list?q=" +
                      __import__("urllib.parse").parse.quote(json.dumps({"status": "draft"})))
        if code != 200:
            if code != 404:  # 404 = this app has no Article entity yet
                print(f"  ! base44 {domain}: {code}")
            continue
        for a in _b44_items(d):
            body = str(a.get("body_markdown") or "")
            verdict, review = base44_gate(a, profile)
            slug = a.get("slug", "")
            out.append({"pid": f"{domain}{slug}", "kind": "base44", "app": app, "record": a.get("id"),
                        "site": domain, "url": f"https://{domain}{slug}", "gate": verdict,
                        "review": review,
                        "title": a.get("title", slug), "md": body, "faq": a.get("faq") or [],
                        "summary": a.get("meta_description", ""),
                        "written": str(a.get("generated_at") or a.get("created_date") or "")[:10] or
                        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "live": "", "words": len(body.split())})
    return out


def base44_record(pid: str) -> tuple[str, dict] | None:
    """(app, record) for a base44 Pipeline ID, or None if it is not one / not found."""
    for domain, (app, _p) in BASE44_SITES.items():
        if pid.startswith(domain + "/"):
            slug = pid[len(domain):]
            code, d = b44("GET", f"/{app}/entities/Article/v2/list?q=" +
                          __import__("urllib.parse").parse.quote(json.dumps({"slug": slug})) + "&limit=1")
            items = _b44_items(d) if code == 200 else []
            return (app, items[0]) if items else None
    return None


# Where a merged article lives, by the file the PR ADDED. Repo PR rows never got
# a Live page (only base44 rows did), so the Monday summary could not confirm them
# live — Iranian Food read "merged, not checked" while it answered 200 (10 Oct).
# Patterns checked against live pages on 10 Oct. A PR that adds no article
# (photo sets) gets no link — there is no single page to point at.
LIVE_PATTERNS = {
    "ambientetravel/boutimar": (r"^src/content/journal/([^/]+)\.mdx?$", "https://boutimar.com/journal/{}/"),
    "ambientetravel/exploreorient": (r"^src/content/blog/([^/]+)\.mdx?$", "https://exploreorient.com/journal/{}/"),
    # cruise24.ir serves content/blog/<dir>/ at /blog/<dir minus a leading "blog-">/
    "ambientetravel/cruise24-ir": (r"^content/blog/([^/]+)/index\.md$", "https://cruise24.ir/blog/{}/"),
}


def live_url_for(repo: str, p: dict) -> str:
    """The live address of the article a PR adds, or "" if it adds none."""
    num = p.get("number")
    code, files = gh("GET", f"/repos/{repo}/pulls/{num}/files?per_page=100")
    if code != 200 or not isinstance(files, list):
        return ""
    added = [f.get("filename", "") for f in files if f.get("status") == "added"]
    if repo in LIVE_PATTERNS:
        pat, url = LIVE_PATTERNS[repo]
        for name in added:
            m = re.match(pat, name)
            if m:
                slug = m.group(1)
                if repo.endswith("cruise24-ir") and slug.startswith("blog-"):
                    slug = slug[len("blog-"):]
                return url.format(slug)
        return ""
    if repo == "ambientetravel/boutimarfarsi":
        # The article is a NEW item in data/articles.json (base vs head of the PR).
        if not any(f.get("filename") == "data/articles.json" for f in files):
            return ""
        def items(ref: str) -> list:
            c, d = _curl("GET", f"https://api.github.com/repos/{repo}/contents/data/articles.json?ref={ref}",
                         [f"Authorization: Bearer {os.environ.get('GITHUB_TOKEN', '')}",
                          "Accept: application/vnd.github.raw"])
            d = d if isinstance(d, (dict, list)) else {}
            return d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])
        before = {a.get("slug") for a in items((p.get("base") or {}).get("sha", "main"))}
        new = [a.get("slug") for a in items((p.get("head") or {}).get("sha", "")) if a.get("slug") not in before]
        return f"https://boutimar.ir/daryanameh/{new[0]}.html" if len(new) == 1 else ""
    return ""


def _days_since(iso: str) -> float:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 86400


def set_live(page_id: str, url: str) -> None:
    if url:
        notion("PATCH", f"/pages/{page_id}", {"properties": {"Live page": {"url": url}}})


def pr_state(pid: str) -> tuple[str, dict]:
    name, num = pid.split("#")
    repo = f"ambientetravel/{name}"
    code, p = gh("GET", f"/repos/{repo}/pulls/{num}")
    return (repo if code == 200 else ""), (p if code == 200 else {})


# ── the article itself, inside the Notion page ───────────────────────────────
# The row's "Read it" link opens a GitHub diff — unreadable for a reviewer, and for
# boutimar.ir a JSON file. So the draft's own text is written into the page body,
# with the house-rules findings on top. (Added 5 Oct 2026 after "I see no link to
# the actual writing".)
TEXT_MARK = "Draft text"
# Bump to rebuild every page's text. v2 (8 Oct): photos via Commons' direct
# thumbnail URL — Notion does not follow the Special:FilePath redirect, so v1
# pages showed empty image boxes — and in-text images rendered as images.
TEXT_VERSION = "v2"


_IMG_EXT = r"\.(?:jpe?g|png|webp|tiff?|gif)"
# A Commons file named in a credit link. Non-greedy up to the image extension, so
# a name with brackets — "Tatev_Monastery_(28206606321).jpg" — is not cut at ")".
_COMMONS_FILE = re.compile(r"commons\.wikimedia\.org/wiki/(File:[^\s\]\"'<>]+?" + _IMG_EXT + r")", re.I)
_THUMBS: dict[str, str] = {}


def commons_thumb(fname: str, width: int = 900) -> str:
    """Direct upload.wikimedia.org thumbnail URL for a Commons file ('' if unknown).
    Notion embeds a direct image URL; it shows an empty box for a redirect."""
    key = f"{fname}|{width}"
    if key not in _THUMBS:
        import urllib.parse
        q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "imageinfo",
                                    "iiprop": "url", "iiurlwidth": width,
                                    "titles": "File:" + urllib.parse.unquote(fname).replace("_", " ")})
        code, d = _curl("GET", f"https://commons.wikimedia.org/w/api.php?{q}", ["User-Agent: albaloo-review-sync"])
        url = ""
        if code == 200 and isinstance(d, dict):
            for pg in ((d.get("query") or {}).get("pages") or {}).values():
                ii = (pg.get("imageinfo") or [{}])[0]
                url = ii.get("thumburl") or ii.get("url") or ""
        _THUMBS[key] = url
    return _THUMBS[key]


def _image(url: str, caption: str = "") -> dict:
    return {"object": "block", "type": "image",
            "image": {"type": "external", "external": {"url": url}, "caption": _rt(caption)}}


_MDLINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _rt(text: str) -> list[dict]:
    """Rich text, with [label](url) turned into real links and every run kept
    under Notion's 2,000-character limit."""
    text = str(text or "")
    out, pos = [], 0
    for m in list(_MDLINK.finditer(text)) + [None]:
        plain = text[pos:m.start()] if m else text[pos:]
        out += [{"type": "text", "text": {"content": plain[i:i + 1900]}} for i in range(0, len(plain), 1900)]
        if m:
            out.append({"type": "text", "text": {"content": m.group(1)[:1900], "link": {"url": m.group(2)}}})
            pos = m.end()
    return out


def _blk(kind: str, text: str) -> dict:
    return {"object": "block", "type": kind, kind: {"rich_text": _rt(text)}}


def _para_blocks(text: str) -> list[dict]:
    """A paragraph that carries '<br>- item' lists becomes a paragraph plus bullets."""
    parts = [x.strip() for x in re.split(r"<br\s*/?>", str(text)) if x.strip()]
    out = []
    for x in parts:
        if re.match(r"^[-•*]\s+", x):
            out.append(_blk("bulleted_list_item", re.sub(r"^[-•*]\s+", "", x)))
        else:
            out.append(_blk("paragraph", x))
    return out


def md_blocks(md: str) -> list[dict]:
    """Markdown (boutimar.com journal, cruise24.ir blog) → Notion blocks."""
    out: list[dict] = []
    body = md
    fm = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if fm:
        body = md[fm.end():]
        meta = dict(re.findall(r'^(\w+):\s*"?(.*?)"?\s*$', fm.group(1), re.M))
        if meta.get("title"):
            out.append(_blk("heading_1", meta["title"]))
        if meta.get("summary"):
            out.append(_blk("quote", meta["summary"]))
    para: list[str] = []

    def flush():
        if para:
            out.append(_blk("paragraph", " ".join(para)))
            para.clear()
    for line in body.splitlines():
        t = line.strip()
        if not t:
            flush(); continue
        im = re.match(r"^!\[([^\]]*)\]\(([^)\s]+)\)\s*(.*)$", t)
        if im:
            # A site-relative path (/img/journal/x.jpg) is not reachable from
            # Notion; the photo gallery at the top of the page already shows it.
            flush()
            if im.group(2).startswith("http"):
                out.append(_image(im.group(2), im.group(1)))
            if im.group(3).strip():
                para.append(im.group(3).strip())
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", t)
        if m:
            flush()
            out.append(_blk("heading_2" if len(m.group(1)) <= 2 else "heading_3", m.group(2)))
        elif re.match(r"^[-*]\s+", t):
            flush(); out.append(_blk("bulleted_list_item", re.sub(r"^[-*]\s+", "", t)))
        else:
            para.append(t)
    flush()
    return out


def json_blocks(item: dict) -> list[dict]:
    """boutimar.ir articles.json item ({title, dek, body:[{h|p: …}]}) → Notion blocks."""
    out = [_blk("heading_1", item.get("title", ""))]
    if item.get("dek"):
        out.append(_blk("quote", item["dek"]))
    for part in item.get("body") or []:
        for k, v in (part.items() if isinstance(part, dict) else [("p", part)]):
            if isinstance(v, list):
                out += [_blk("bulleted_list_item", str(x)) for x in v]
            elif k.startswith("h"):
                head, _, rest = str(v).partition("\n")
                out.append(_blk("heading_2", head))
                if rest.strip():
                    out += _para_blocks(rest.strip())
            else:
                out += _para_blocks(str(v))
    return out


def review_blocks(review: dict) -> list[dict]:
    """House-rules findings as a callout, so WARN/BLOCK is explained, not just coloured."""
    items = [("BLOCK", f) for f in review.get("blocks") or []] + [("WARN", f) for f in review.get("warns") or []]
    if not items:
        return [{"object": "block", "type": "callout", "callout": {
            "rich_text": _rt("House rules: PASS — no findings."), "icon": {"emoji": "✅"}}}]
    out = [{"object": "block", "type": "callout", "callout": {
        "rich_text": _rt(f"House rules: {len(items)} finding(s) — check these lines before approving."),
        "icon": {"emoji": "⚠️"}}}]
    for lvl, f in items[:20]:
        out.append(_blk("bulleted_list_item",
                        f"{lvl} · {f.get('rule', '')}: «{(f.get('excerpt') or '')[:300]}» → {f.get('fix', '')}"))
    return out


def article_blocks(repo: str, num: int, sha: str) -> list[dict]:
    code, files = gh("GET", f"/repos/{repo}/pulls/{num}/files?per_page=100")
    if code != 200 or not isinstance(files, list):
        return []

    def raw(path: str, ref: str) -> str:
        c, d = _curl("GET", f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}",
                     [f"Authorization: Bearer {os.environ.get('GITHUB_TOKEN', '')}",
                      "Accept: application/vnd.github.raw"])
        return d if isinstance(d, str) else (json.dumps(d, ensure_ascii=False) if c == 200 else "")
    out: list[dict] = []
    # Photos added by this PR: show them in the page so the reviewer judges the
    # picture, not a file name. Commons' Special:FilePath serves the file
    # directly (the repo copies are private and Notion cannot fetch them).
    shown: set[str] = set()
    for f in files:
        for m in _COMMONS_FILE.finditer(f.get("patch") or ""):
            fname = m.group(1)
            if fname in shown:
                continue
            shown.add(fname)
            url = commons_thumb(fname[5:])
            if url:
                out.append(_image(url, f"{name_of(f)} — {fname[5:]}"))
    for f in files:
        name = f.get("filename", "")
        if name.endswith("articles.json"):
            try:
                branch, main = json.loads(raw(name, sha)), json.loads(raw(name, "main"))
            except ValueError:
                continue
            lst = lambda d: d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])  # noqa: E731
            have = {a.get("slug") for a in lst(main)}
            for item in lst(branch):
                if item.get("slug") not in have:
                    out += json_blocks(item)
        elif name.endswith(".md") and "content/" in name:
            out += md_blocks(raw(name, sha))
    return out


def name_of(f: dict) -> str:
    return f.get("filename", "").rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _heading_text(b: dict) -> str:
    return "".join(t.get("plain_text", "") for t in (b.get(b.get("type"), {}) or {}).get("rich_text", []))


def page_has_text(page_id: str) -> bool:
    """True only when the page carries the CURRENT text version."""
    code, d = notion("GET", f"/blocks/{page_id}/children?page_size=10")
    return code == 200 and any(
        TEXT_MARK in _heading_text(b) and f"· {TEXT_VERSION}" in _heading_text(b)
        for b in d.get("results", []))


_BOT_ID: list[str] = []


def clear_generated(page_id: str) -> int:
    """Remove the blocks THIS integration wrote (an older text version), never a
    block a person typed — those carry the person's user id in created_by."""
    if not _BOT_ID:
        code, me = notion("GET", "/users/me")
        _BOT_ID.append(me.get("id", "") if code == 200 and isinstance(me, dict) else "")
    if not _BOT_ID[0]:
        return 0
    removed, cursor = 0, None
    while True:
        code, d = notion("GET", f"/blocks/{page_id}/children?page_size=100"
                                + (f"&start_cursor={cursor}" if cursor else ""))
        if code != 200:
            break
        for b in d.get("results", []):
            if (b.get("created_by") or {}).get("id") == _BOT_ID[0]:
                if notion("DELETE", f"/blocks/{b['id']}")[0] == 200:
                    removed += 1
        if not d.get("has_more"):
            break
        cursor = d.get("next_cursor")
    return removed


def write_text(page_id: str, r: dict) -> int:
    if r.get("kind") == "base44":
        body = [_blk("heading_1", r.get("title", ""))] + ([_blk("quote", r["summary"])] if r.get("summary") else []) \
            + md_blocks(r.get("md", "")) + ([_blk("heading_2", "FAQ")] if r.get("faq") else []) \
            + [b for x in r.get("faq") or [] for b in (_blk("heading_3", x.get("q", "")), _blk("paragraph", x.get("a", "")))]
    else:
        body = article_blocks(r["repo"], r["num"], r["sha"])
    clear_generated(page_id)
    blocks = review_blocks(r.get("review") or {}) + \
        [_blk("heading_3", f"{TEXT_MARK} — {r['pid']} · {TEXT_VERSION}")] + body
    for i in range(0, len(blocks), 90):
        code, d = notion("PATCH", f"/blocks/{page_id}/children", {"children": blocks[i:i + 90]})
        if code != 200:
            raise RuntimeError(f"Notion append {code}: {str(d)[:160]}")
    return len(blocks)


# ── the sync ─────────────────────────────────────────────────────────────────
def sync(apply: bool, db: str) -> list[str]:
    log: list[str] = []
    board = rows(db)
    live_prs = {r["pid"]: r for r in open_article_prs() + base44_drafts()}

    # 1. new PRs → new rows, each with the draft's text inside
    for pid, r in live_prs.items():
        if pid not in board:
            log.append(f"add row     {pid}  {r['gate']}  {r['title'][:60]}")
            if apply:
                code, d = notion("POST", "/pages", {"parent": {"database_id": db},
                                                    "properties": row_properties(r)})
                if code != 200:
                    log.append(f"  ! Notion {code}: {str(d)[:160]}")
                elif r.get("sha") or r.get("kind") == "base44":
                    try:
                        log.append(f"  text      {write_text(d['id'], r)} block(s)")
                    except RuntimeError as exc:
                        log.append(f"  ! {exc}")
        elif r.get("gate") and board[pid].get("gate") and r["gate"] != board[pid]["gate"]:
            log.append(f"house rules {pid}  {board[pid]['gate']} → {r['gate']}")
            if apply:
                notion("PATCH", f"/pages/{board[pid]['page_id']}",
                       {"properties": {"House rules": {"select": {"name": r["gate"]}}}})
        if pid in board and (r.get("sha") or r.get("kind") == "base44") and not page_has_text(board[pid]["page_id"]):
            log.append(f"add text    {pid}  (row had no article text)")
            if apply:
                try:
                    log.append(f"  text      {write_text(board[pid]['page_id'], r)} block(s)")
                except RuntimeError as exc:
                    log.append(f"  ! {exc}")

    # 2. decisions on the board → GitHub (PRs) or base44 (Article status)
    for pid, row in board.items():
        if any(pid.startswith(d + "/") for d in BASE44_SITES):
            if not os.environ.get("BASE44_ACCESS_TOKEN"):
                continue
            found = base44_record(pid)
            if not found:
                continue
            app, rec = found
            live_status = str(rec.get("status", "")).lower()
            if live_status == "published" and row["status"] != "Published":
                log.append(f"published   {pid}  (published in base44)")
                if apply:
                    set_status(row["page_id"], "Published")
                continue
            if row["status"] == "Approved" and live_status == "draft":
                gate = live_prs.get(pid, {}).get("gate", "WARN")
                if gate == "BLOCK":
                    log.append(f"HOLD        {pid}  approved but house rules say BLOCK — not published")
                    if apply:
                        set_status(row["page_id"], "Needs edits")
                    continue
                log.append(f"publish     {pid}  (base44 status → published)")
                if apply:
                    code, d = b44("PUT", f"/{app}/entities/Article/{rec['id']}", {"status": "published"})
                    if code == 200:
                        set_status(row["page_id"], "Published")
                    else:
                        log.append(f"  ! base44 {code}: {str(d)[:140]}")
            continue
        repo, p = pr_state(pid)
        if not p:
            continue
        num = p["number"]
        if p.get("merged_at") and row["status"] != "Published":
            live = row.get("live") or live_url_for(repo, p)
            log.append(f"published   {pid}  (merged on GitHub){'  → ' + live if live and not row.get('live') else ''}")
            if apply:
                set_status(row["page_id"], "Published")
                if not row.get("live"):
                    set_live(row["page_id"], live)
            continue
        if p.get("merged_at") and not row.get("live") and _days_since(p["merged_at"]) <= 30:
            # Published before Live page was filled in: backfill it once.
            live = live_url_for(repo, p)
            if live:
                log.append(f"live link   {pid}  → {live}")
                if apply:
                    set_live(row["page_id"], live)
            continue
        if p.get("state") == "closed" and not p.get("merged_at") and row["status"] not in ("Rejected",):
            log.append(f"rejected    {pid}  (closed on GitHub)")
            if apply:
                set_status(row["page_id"], "Rejected")
            continue
        if p.get("state") != "open":
            continue
        st = row["status"]
        if st == "Approved":
            gate = live_prs.get(pid, {}).get("gate", "WARN")
            if gate == "BLOCK":
                log.append(f"HOLD        {pid}  approved but house rules say BLOCK — not merged")
                if apply:
                    gh("POST", f"/repos/{repo}/issues/{num}/comments",
                       {"body": "Approved on the Content Review board, but the house-rules gate says **BLOCK**. "
                                "Not merged — fix the flagged lines (or override by merging here)."})
                    set_status(row["page_id"], "Needs edits")
                continue
            log.append(f"merge       {pid}")
            if apply:
                code, d = gh("PUT", f"/repos/{repo}/pulls/{num}/merge",
                             {"merge_method": "squash", "commit_title": f"{p['title']} (#{num})"})
                if code == 200:
                    set_status(row["page_id"], "Published")
                    if not row.get("live"):
                        set_live(row["page_id"], live_url_for(repo, p))
                else:
                    log.append(f"  ! merge refused ({code}): {str(d)[:140]}")
        elif st in ("Needs edits", "Rejected") and row["feedback"]:
            marker = feedback_marker(st, row["feedback"])
            code, comments = gh("GET", f"/repos/{repo}/issues/{num}/comments?per_page=100")
            if code == 200 and any(marker in (c.get("body") or "") for c in comments):
                continue  # already relayed this exact feedback
            log.append(f"{st.lower():11} {pid}  → feedback posted")
            if apply:
                gh("POST", f"/repos/{repo}/issues/{num}/comments",
                   {"body": f"**{st}** (Content Review board):\n\n{row['feedback']}\n\n{marker}"})
                if st == "Rejected":
                    gh("PATCH", f"/repos/{repo}/pulls/{num}", {"state": "closed"})
        elif st == "Rejected":
            log.append(f"reject      {pid}  → PR closed")
            if apply:
                gh("PATCH", f"/repos/{repo}/pulls/{num}", {"state": "closed"})
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    missing = [k for k in ("NOTION_TOKEN", "GITHUB_TOKEN") if not os.environ.get(k)]
    if missing:
        print(f"not configured: {', '.join(missing)} — nothing synced")
        return 0          # a missing secret is a setup gap, not a failed run
    db = os.environ.get("NOTION_REVIEW_DB") or DEFAULT_DB
    log = sync(a.apply, db)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Content Review sync — {stamp} — {'APPLIED' if a.apply else 'dry run'}")
    print("\n".join(log) if log else "  in step — nothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
