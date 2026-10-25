#!/usr/bin/env python3
"""
ops-sync phase 1: the Review queue in the Albaloo Ops base44 app.

Architecture credit: Albaloo Studio — albaloostudio.com. Spec: OPS-APP.md.

GitHub stays the source of truth; Notion "Content Review" stays the decision
path (tools/notion_review_sync.py acts on it: Approved → merge, Needs edits →
revision, Rejected → close). The app is a second window on the same board:

  push   every open draft on the board → one ArticleReview row in the app
         (title, site, language, house-rules verdict + notes, the article text,
         age, PR link); status kept in step with the Notion row
  pull   a decision pressed in the app (publish / needs_edits / reject) →
         written onto the Notion row as Status (+ Feedback). The hourly review
         sync then does what it already does. Nothing here merges or closes.
  ping   a draft that appears for the first time → one Notion @mention of
         Alireza (the same push the Monday summary uses). The first sync, which
         finds the whole backlog at once, seeds silently.

Safety: a decision is applied only while the Notion row still reads "To review"
(so a decision made in Notion first wins); "publish" on a BLOCK verdict is
refused; the app's decision field is cleared once applied, so it never fires
twice. Base44 never calls GitHub.

    python3 tools/ops_sync.py --probe            # read-only GET of ArticleReview
    python3 tools/ops_sync.py                    # dry run: what it would do
    python3 tools/ops_sync.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion_review_sync as nrs  # noqa: E402

OPS_APP = os.environ.get("OPS_APP_ID") or "6ade14ab5b5e6721cc424fbe"
ENTITY = "ArticleReview"
OWNER = "1e746a95-158f-4f48-91e6-728fa01dacd7"       # Alireza (Notion user)
PING_TITLE = "🔔 New drafts"
BODY_CAP = 60000
# ArticleReview.image_url exists only once the app has that field; until then it is never sent.
IMAGES_ON = bool(os.environ.get("OPS_ARTICLE_IMAGES"))

STATUS_TO_APP = {"To review": "to_review", "Approved": "approved", "Needs edits": "needs_edits",
                 "Rejected": "rejected", "Published": "published"}
DECISION_TO_NOTION = {"publish": "Approved", "needs_edits": "Needs edits", "reject": "Rejected"}
SITE_REPO = {"boutimar": "boutimar.com", "boutimarfarsi": "boutimar.ir", "cruise24-ir": "cruise24.ir",
             "exploreorient": "exploreorient.com"}


# ── base44 ───────────────────────────────────────────────────────────────────
def _ent(path: str = "") -> str:
    return f"/{OPS_APP}/entities/{ENTITY}{path}"


def probe() -> tuple[int, Any]:
    """Read-only: list ArticleReview. Returns (HTTP status, body)."""
    return nrs.b44("GET", _ent("/v2/list?limit=5"))


def app_rows() -> list[dict]:
    code, d = nrs.b44("GET", _ent("/v2/list?limit=1000"))
    if code != 200:
        raise RuntimeError(f"base44 {code} listing {ENTITY}: {str(d)[:200]}")
    return nrs._b44_items(d)


# ── Notion board ─────────────────────────────────────────────────────────────
def _prop(pr: dict, name: str) -> str:
    p = pr.get(name) or {}
    t = p.get("type")
    if t == "select":
        return ((p.get("select") or {}).get("name")) or ""
    if t == "url":
        return p.get("url") or ""
    if t == "date":
        return ((p.get("date") or {}).get("start")) or ""
    if t == "number":
        return "" if p.get("number") is None else str(p.get("number"))
    return nrs._txt(p)


def board(db: str) -> list[dict]:
    out, cursor = [], None
    while True:
        code, d = nrs.notion("POST", f"/databases/{db}/query",
                             {"page_size": 100, **({"start_cursor": cursor} if cursor else {})})
        if code != 200:
            raise RuntimeError(f"Notion query {code}: {str(d)[:160]}")
        for p in d.get("results", []):
            pr = p["properties"]
            pid = _prop(pr, "Pipeline ID")
            if not pid:
                continue                         # container rows (summaries, pings)
            out.append({"page_id": p["id"], "title": _prop(pr, "Article"), "site": _prop(pr, "Site"),
                        "status": _prop(pr, "Status"), "pid": pid, "gate": _prop(pr, "House rules"),
                        "language": _prop(pr, "Language"), "written": _prop(pr, "Written"),
                        "read": _prop(pr, "Read it"), "live": _prop(pr, "Live page"),
                        "words": _prop(pr, "Words"), "feedback": _prop(pr, "Feedback")})
        if not d.get("has_more"):
            return out
        cursor = d.get("next_cursor")


def pr_link(pid: str) -> tuple[str, int, str]:
    """('ambientetravel/repo', num, url) for 'repo#num'; ('', 0, '') for a base44 draft."""
    if "#" not in pid:
        return "", 0, ""
    repo, num = pid.split("#", 1)
    full = f"ambientetravel/{repo}"
    return full, int(num), f"https://github.com/{full}/pull/{num}"


def age_days(written: str, now: datetime) -> int:
    try:
        d = datetime.fromisoformat(written[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    return max(0, (now - d).days)


# ── article text + verdict notes (only for rows the app does not have yet) ───
IMG_KEYS = ("image_source_url", "image", "hero_image", "hero", "cover", "og_image", "thumbnail")


def find_image(*sources) -> str:
    """The article's own photo as a public http(s) URL, or "" — never a guess.
    Sources: front-matter text, a JSON/base44 record (dict), or the body markdown."""
    for s in sources:
        if isinstance(s, dict):
            for k in IMG_KEYS:
                v = s.get(k)
                v = v.get("url") or v.get("public_url") if isinstance(v, dict) else v
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    return v
        elif isinstance(s, str) and s:
            m = re.search(r"^\s*(?:%s)\s*:\s*[\"']?(https?://[^\s\"']+)" % "|".join(IMG_KEYS), s, re.M) \
                or re.search(r"!\[[^\]]*\]\((https?://[^)\s]+)", s)
            if m:
                return m.group(1)
    return ""


IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")


def _public(url: str) -> bool:
    """True when anyone's browser can load the URL (no token): the app shows it as-is."""
    import subprocess
    out = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-I", "-L", "--max-time", "20",
                          "-w", "%{http_code}", url], capture_output=True, text=True).stdout
    return out.strip() == "200"


def pr_photo(pid: str) -> str:
    """The draft's OWN photo file, from its PR, as a raw URL pinned to the head commit
    (so it keeps working after the branch is deleted). "" when the PR has no image file
    or its repo is not publicly readable."""
    repo, num, _ = pr_link(pid)
    if not repo:
        return ""
    _, p = nrs.pr_state(pid)
    sha = (p.get("head") or {}).get("sha")
    code, files = nrs.gh("GET", f"/repos/{repo}/pulls/{num}/files?per_page=100")
    if not sha or code != 200 or not isinstance(files, list):
        return ""
    for f in files:
        name = str(f.get("filename") or "")
        if name.lower().endswith(IMG_EXT) and f.get("status") != "removed":
            url = f"https://raw.githubusercontent.com/{repo}/{sha}/{name}"
            return url if _public(url) else ""
    return ""


def commons_photo(title: str, site: str) -> tuple[str, str]:
    """Fallback for a draft with no photo of its own: a freely licensed Wikimedia Commons
    photo matching the title, with its real creator and licence. (url, note) or ("", "")."""
    try:
        import images
        subject = re.split(r"\s*[:|–—]\s*", str(title or ""), maxsplit=1)[0]   # the place, not the angle
        got = images.find_image(subject, width=1200, context=str(title or ""))
    except Exception:  # noqa: BLE001 — a failed search only means no suggestion
        got = None
    if not got:
        return "", ""
    note = (f"PHOTO IN THE APP IS A SUGGESTION — the draft has no photo of its own. "
            f"Wikimedia Commons: {got['title']} · {got['creator']} · {got['licence']} · {got['source_page']}")
    return got["download_url"], note


def resolve_photo(row: dict, found: str = "") -> tuple[str, str]:
    """(image_url, note). Order: a public URL the draft names → the draft's own photo
    file → a credited Commons suggestion. Never an unlicensed or uncredited image."""
    if found:
        return found, ""
    own = pr_photo(row["pid"]) if "#" in row["pid"] else ""
    if own:
        return own, ""
    return commons_photo(row.get("title") or "", row.get("site") or "")


def article_text(row: dict) -> tuple[str, str, str]:
    """(body_markdown, verdict_notes, image_url). Never raises — a missing body is shown as such."""
    try:
        if "#" in row["pid"]:
            import pr_review
            import revise_drafts as rd
            repo, num, _ = pr_link(row["pid"])
            _, p = nrs.pr_state(row["pid"])
            target = rd.plan_target(repo, num, p["head"], p["base"]["ref"])
            body, image = "", ""
            if target:
                text, _ = rd._file(repo, target["path"], p["head"]["ref"])
                if target["kind"] == "json":
                    main_text, _ = rd._file(repo, target["path"], p["base"]["ref"])
                    lst = lambda d: d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])  # noqa: E731
                    have = {a.get("slug") for a in lst(json.loads(main_text))}
                    new = [a for a in lst(json.loads(text)) if a.get("slug") not in have]
                    item = new[0] if new else {}
                    body = "\n\n".join(str(item.get(k) or "") for k in ("title", "summary", "body", "content")
                                       if item.get(k)) or json.dumps(item, ensure_ascii=False, indent=1)
                    image = find_image(item, body)
                else:
                    fm, body = rd._split_fm(text)
                    image = find_image(fm, body)
            review = pr_review.review_pr(repo, num, pr_review.REPOS.get(repo, "boutimar_v1"))
        else:
            found = nrs.base44_record(row["pid"])
            rec = found[1] if found else {}
            body = str(rec.get("body_markdown") or "")
            image = find_image(rec, body)
            domain = next(d for d in nrs.BASE44_SITES if row["pid"].startswith(d + "/"))
            _, review = nrs.base44_gate(rec, nrs.BASE44_SITES[domain][1])
        notes = [f"BLOCK {b.get('rule')}: «{str(b.get('excerpt'))[:160]}» → {b.get('fix') or b.get('message') or ''}"
                 for b in review.get("blocks") or []] + \
                [f"WARN {w.get('rule')}: «{str(w.get('excerpt'))[:160]}» → {w.get('fix') or w.get('message') or ''}"
                 for w in review.get("warns") or []]
        return body[:BODY_CAP], "\n".join(notes)[:8000], image
    except Exception as exc:  # noqa: BLE001
        return f"(article text could not be loaded: {type(exc).__name__})", "", ""


def to_app(row: dict, now: datetime, *, with_body: bool) -> dict:
    repo, num, url = pr_link(row["pid"])
    rec = {
        "property": row["site"] or SITE_REPO.get(repo.split("/")[-1], ""),
        # A base44 draft has no PR: its full pipeline id ("cruisebaz.com/<slug>")
        # goes in `repo`, which keeps it unique and inside the app's schema.
        "repo": repo or row["pid"],
        "pr_number": num,
        "pr_url": url or row["read"],
        "title": row["title"],
        "language": "fa" if row["language"] == "Farsi" else "en",
        "house_rules_verdict": row["gate"] or "WARN",
        "created_at": row["written"],
        "age_days": age_days(row["written"], now),
        "status": STATUS_TO_APP.get(row["status"], "to_review"),
        "live_url": row["live"],
        "synced_at": now.isoformat(timespec="seconds"),
    }
    if row["words"]:
        rec["word_count"] = int(float(row["words"]))
    if with_body:
        rec["body_markdown"], rec["verdict_notes"], img = article_text(row)
        if IMAGES_ON:
            img, note = resolve_photo(row, img)
            if img:
                rec["image_url"] = img
            if note:
                rec["verdict_notes"] = (note + "\n" + rec["verdict_notes"]).strip()
        if not rec.get("word_count"):
            rec["word_count"] = len(rec["body_markdown"].split())
    return rec


def _key(rec: dict) -> str:
    """One app row per draft, matching the Notion Pipeline ID: 'repo#pr' for a PR,
    the full 'domain/slug' (stored in `repo`) for a base44 draft."""
    if rec.get("pr_number"):
        return f"{str(rec.get('repo', '')).split('/')[-1]}#{int(rec['pr_number'])}"
    return str(rec.get("repo") or "")


# ── the three moves ──────────────────────────────────────────────────────────
OPEN = {"To review", "Needs edits", "Approved"}


def plan(board_rows: list[dict], app: list[dict], now: datetime) -> dict:
    """Pure: what to create, update and apply. No I/O."""
    by_key = {_key(a): a for a in app}
    rows = {r["pid"]: r for r in board_rows}
    create, update, decide, refused = [], [], [], []
    for pid, r in rows.items():
        have = by_key.get(pid)
        if have is None:
            if r["status"] in OPEN:
                create.append(r)
            continue
        want = STATUS_TO_APP.get(r["status"], "to_review")
        dec = str(have.get("decision") or "").strip()
        if dec and r["status"] == "To review" and dec in DECISION_TO_NOTION:
            if dec == "publish" and (r["gate"] == "BLOCK" or have.get("house_rules_verdict") == "BLOCK"):
                refused.append((pid, "publish refused: house rules say BLOCK"))
            elif dec in ("needs_edits", "reject") and not str(have.get("feedback") or "").strip():
                refused.append((pid, f"{dec} needs feedback text"))
            else:
                decide.append((r, have, dec))
                continue
        fields = {"status": want, "age_days": age_days(r["written"], now), "live_url": r["live"],
                  "house_rules_verdict": r["gate"] or have.get("house_rules_verdict") or "WARN",
                  "title": r["title"]}
        if any(have.get(k) != v for k, v in fields.items()):
            update.append((have, fields))
    seed = not app
    return {"create": create, "update": update, "decide": decide, "refused": refused, "seed": seed}


def apply_decision(r: dict, have: dict, dec: str, apply: bool, log: list[str]) -> None:
    status = DECISION_TO_NOTION[dec]
    fb = str(have.get("feedback") or "").strip()
    who = str(have.get("decided_by") or "the app")
    log.append(f"decide      {r['pid']}  {dec} → Notion '{status}'  (by {who})")
    if not apply:
        return
    props: dict[str, Any] = {"Status": {"select": {"name": status}}}
    if dec in ("needs_edits", "reject"):
        props["Feedback"] = {"rich_text": [{"type": "text", "text": {"content": fb[:1900]}}]}
    code, d = nrs.notion("PATCH", f"/pages/{r['page_id']}", {"properties": props})
    if code != 200:
        raise RuntimeError(f"Notion {code} writing the decision: {str(d)[:160]}")
    code, d = nrs.b44("PUT", _ent(f"/{have['id']}"), {
        "decision": None, "status": STATUS_TO_APP[status],
        "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    if code != 200:
        raise RuntimeError(f"base44 {code} clearing the applied decision: {str(d)[:160]}")


def _ping_container(db: str) -> str:
    code, d = nrs.notion("POST", f"/databases/{db}/query", {"page_size": 5, "filter": {
        "property": "Article", "title": {"equals": PING_TITLE}}})
    if code == 200 and d.get("results"):
        return d["results"][0]["id"]
    code, d = nrs.notion("POST", "/pages", {"parent": {"database_id": db}, "icon": {"emoji": "🔔"},
                                            "properties": {"Article": {"title": [{"type": "text", "text": {
                                                "content": PING_TITLE}}]}}})
    if code != 200:
        raise RuntimeError(f"Notion {code} creating the ping row: {str(d)[:200]}")
    return d["id"]


def ping_blocks(new: list[dict], app_url: str) -> list[dict]:
    n = len(new)
    head = [{"type": "mention", "mention": {"type": "user", "user": {"id": OWNER}}},
            {"type": "text", "text": {"content": f" — {n} new draft{'s' if n != 1 else ''} to review. "}},
            {"type": "text", "text": {"content": "Open the Review tab", "link": {"url": app_url}}}]
    blocks = [{"object": "block", "type": "callout", "callout": {"icon": {"emoji": "🔔"}, "rich_text": head}}]
    for r in new[:20]:
        flag = f" ⚠ {r['gate']}" if r["gate"] in ("WARN", "BLOCK") else ""
        blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [
            {"type": "text", "text": {"content": f"{r['site']} — "}},
            {"type": "text", "text": {"content": r["title"][:180],
                                      "link": {"url": f"https://www.notion.so/{r['page_id'].replace('-', '')}"}}},
            {"type": "text", "text": {"content": flag}}]}})
    return blocks


def run(apply: bool, db: str) -> list[str]:
    now = datetime.now(timezone.utc)
    log: list[str] = []
    rows = board(db)
    app = app_rows()
    p = plan(rows, app, now)
    log.append(f"board: {sum(r['status'] in OPEN for r in rows)} open of {len(rows)} rows · app: {len(app)} rows"
               + (" · first sync (seed — no ping)" if p["seed"] else ""))
    for r in p["create"]:
        log.append(f"create      {r['pid']}  {r['site']} · {r['title'][:60]}")
        if apply:
            code, d = nrs.b44("POST", _ent(), to_app(r, now, with_body=True))
            if code not in (200, 201):
                log.append(f"  ! base44 {code}: {str(d)[:160]}")
    for have, fields in p["update"]:
        log.append(f"update      {_key(have)}  status → {fields['status']}")
        if apply:
            code, d = nrs.b44("PUT", _ent(f"/{have['id']}"), {**fields, "synced_at": now.isoformat(timespec='seconds')})
            if code != 200:
                log.append(f"  ! base44 {code}: {str(d)[:160]}")
    for r, have, dec in p["decide"]:
        try:
            apply_decision(r, have, dec, apply, log)
        except Exception as exc:  # noqa: BLE001
            log.append(f"  ! {r['pid']}: {exc}")
    for pid, why in p["refused"]:
        log.append(f"refused     {pid}  {why}")
    new = [r for r in p["create"] if r["status"] == "To review"]
    if new and not p["seed"]:
        log.append(f"ping        {len(new)} new draft(s) → Notion @mention")
        if apply:
            parent = _ping_container(db)
            code, d = nrs.notion("PATCH", f"/blocks/{parent}/children",
                                 {"children": ping_blocks(new, "https://albaloo-ops-core.base44.app")})
            if code != 200:
                log.append(f"  ! Notion {code} ping: {str(d)[:160]}")
    log.append(f"summary: {len(p['create'])} created, {len(p['update'])} updated, "
               f"{len(p['decide'])} decision(s) applied, {len(p['refused'])} refused, "
               f"{len(new) if not p['seed'] else 0} pinged"
               + ("" if apply else "  (dry run — nothing written)"))
    return log


def backfill_images(apply: bool, db: str) -> list[str]:
    """One-off: give rows already in the app the photo their draft carries."""
    rows = {r["pid"]: r for r in board(db)}
    log, found = [], 0
    for have in app_rows():
        if have.get("image_url") or have.get("status") not in ("to_review", "needs_edits", "approved"):
            continue
        r = rows.get(_key(have))
        if not r:
            continue
        img, note = resolve_photo(r, article_text(r)[2])
        kind = "none  " if not img else ("commons" if note else "own   ")
        log.append(f"{kind}     {_key(have)}  {img[:90]}")
        if img:
            found += 1
            if apply:
                body = {"image_url": img}
                if note:
                    body["verdict_notes"] = (note + "\n" + str(have.get("verdict_notes") or "")).strip()[:8000]
                code, d = nrs.b44("PUT", _ent(f"/{have['id']}"), body)
                if code != 200:
                    log.append(f"  ! base44 {code}: {str(d)[:160]}")
    log.append(f"summary: {found} photo(s) found" + ("" if apply else "  (dry run — nothing written)"))
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--probe", action="store_true", help="read-only GET of the ArticleReview entity")
    ap.add_argument("--backfill-images", action="store_true", help="one-off: photos for rows already in the app")
    a = ap.parse_args(argv)
    if not os.environ.get("BASE44_ACCESS_TOKEN"):
        print("not configured: BASE44_ACCESS_TOKEN — nothing synced")
        return 2 if a.probe else 0
    code, d = probe()
    items = nrs._b44_items(d) if code == 200 else []
    print(f"probe: GET {nrs.B44}{_ent('/v2/list')} → HTTP {code}"
          + (f", {len(items)} row(s) returned (limit 5)" if code == 200 else f" — {str(d)[:300]}"))
    if a.probe:
        for it in items:
            print(f"  {_key(it)} · {it.get('status')} · {it.get('house_rules_verdict')} · "
                  f"body {len(str(it.get('body_markdown') or ''))} chars · notes "
                  f"{len(str(it.get('verdict_notes') or ''))} chars · {str(it.get('title') or '')[:50]}")
        return 0 if code == 200 else 1
    if code != 200:
        return 1
    if not os.environ.get("NOTION_TOKEN") or not os.environ.get("GITHUB_TOKEN"):
        print("not configured: NOTION_TOKEN / GITHUB_TOKEN — nothing synced")
        return 0
    db = os.environ.get("NOTION_REVIEW_DB") or nrs.DEFAULT_DB
    if a.backfill_images:
        print("\n".join(backfill_images(a.apply, db)))
        return 0
    print("\n".join(run(a.apply, db)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
