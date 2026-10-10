#!/usr/bin/env python3
"""
Needs edits → a revised draft on the same pull request → back to "To review".

Until 8 Oct 2026 a reviewer's Feedback on the Content Review board was only
relayed to the PR as a comment, and the draft sat there until a person rewrote
it. Now, for every row whose Status is "Needs edits" and whose Feedback this tool
has not acted on yet:

  1. the draft is read from its PR branch (Markdown article, boutimar.ir
     articles.json item, or cruise24.ir bundle);
  2. the model applies the Feedback and nothing else, under the site's house
     rules (compliance.prompt_constraints);
  3. the result is checked by the same compliance gate as a new draft — a BLOCK
     that survives is NOT committed; the PR gets the findings instead;
  4. a revision that shrank the text by more than a third is refused (a model
     that truncates is not a model that edited);
  5. the file is committed to the same branch, the PR gets a comment saying what
     changed, the Notion page's text is rebuilt, and the row returns to
     "To review" with the Feedback marked as done.

Each Feedback text is acted on once (a hash marker on the PR). A PR labelled
`do-not-revise` is left to people — boutimarfarsi#1 is held by its site session.

base44 drafts (cruisebaz.com, since 10 Oct) have no PR: the Article record's
title, meta description, body and FAQ are revised together (slug untouched), the
same gate and shrink guard apply, the record is backed up to runs/ before the
write and restored if the read-back differs, and only a record still in "draft"
is touched — a published article is never rewritten live. A blocked revision is
recorded in the row's Feedback ("[Revision blocked …]") so it is not retried
until the reviewer writes new Feedback.

    python3 tools/revise_drafts.py            # dry run: what it would revise
    python3 tools/revise_drafts.py --apply
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import compliance  # noqa: E402
import notion_review_sync as nrs  # noqa: E402
import pr_review  # noqa: E402

HOLD_LABEL = "do-not-revise"
MIN_KEEP = 0.66          # a revision may not drop below two thirds of the original length


def marker(feedback: str) -> str:
    return f"<!-- revised:{hashlib.sha1(feedback.encode('utf-8')).hexdigest()[:12]} -->"


def _file(repo: str, path: str, ref: str) -> tuple[str, str]:
    code, d = nrs.gh("GET", f"/repos/{repo}/contents/{path}?ref={ref}")
    if code != 200 or not isinstance(d, dict):
        raise RuntimeError(f"cannot read {path}@{ref} ({code})")
    return base64.b64decode(d["content"]).decode("utf-8"), d["sha"]


def _put(repo: str, path: str, branch: str, text: str, sha: str, msg: str) -> None:
    code, d = nrs.gh("PUT", f"/repos/{repo}/contents/{path}", {
        "message": msg[:72], "branch": branch, "sha": sha,
        "content": base64.b64encode(text.encode("utf-8")).decode()})
    if code not in (200, 201):
        raise RuntimeError(f"commit refused ({code}): {str(d)[:160]}")


def _split_fm(md: str) -> tuple[str, str]:
    m = re.match(r"^---\n.*?\n---\n", md, re.S)
    return (md[:m.end()], md[m.end():]) if m else ("", md)


def revise_text(kind: str, current: str, feedback: str, profile: str, language: str) -> dict:
    """Ask the model for the revision. kind 'markdown' → {text, summary};
    kind 'json' → {item, summary} with the same keys and slug."""
    import llm
    system = ("You revise a travel article draft before publication. Apply the reviewer's feedback "
              "exactly and change NOTHING else: keep the language, voice, headings, links, image and "
              "photo-credit lines, and every sentence the feedback does not touch. Never add a price, "
              "date, inclusion, statistic or credit that is not already in the text.\n\n"
              + compliance.prompt_constraints(profile))
    if kind == "json":
        prompt = (f"Reviewer feedback:\n{feedback}\n\nThe article as a JSON object (language {language}):\n"
                  f"{current}\n\nReturn JSON {{\"item\": <the same object with the feedback applied — same keys, "
                  f"same slug, same structure>, \"summary\": \"one line: what you changed\"}}.")
        schema = {"type": "object", "additionalProperties": False,
                  "properties": {"item": {"type": "object"}, "summary": {"type": "string"}},
                  "required": ["item", "summary"]}
    else:
        prompt = (f"Reviewer feedback:\n{feedback}\n\nThe article body in Markdown (language {language}):\n"
                  f"{current}\n\nReturn JSON {{\"text\": \"<the full Markdown body with the feedback applied>\", "
                  f"\"summary\": \"one line: what you changed\"}}.")
        schema = {"type": "object", "additionalProperties": False,
                  "properties": {"text": {"type": "string"}, "summary": {"type": "string"}},
                  "required": ["text", "summary"]}
    out, _ = llm.complete_json_resilient(system, prompt, schema, max_tokens=16000,
                                         purpose="draft revision", waits=(0,))
    return out


def plan_target(repo: str, num: int, head: dict, base_ref: str) -> dict | None:
    """Which file in the PR holds the article, and in what shape."""
    code, files = nrs.gh("GET", f"/repos/{repo}/pulls/{num}/files?per_page=100")
    names = [f.get("filename", "") for f in files] if isinstance(files, list) else []
    for n in names:
        if n.endswith("articles.json"):
            return {"kind": "json", "path": n}
    for n in names:
        if n.endswith((".md", ".mdx")) and ("content/" in n) and not pr_review.is_internal(n):
            return {"kind": "markdown", "path": n}
    return None


def revise_pr(row: dict, pid: str, apply: bool, log: list[str]) -> None:
    repo, p = nrs.pr_state(pid)
    if not p or p.get("state") != "open":
        return
    num, branch = p["number"], p["head"]["ref"]
    if any(lb.get("name") == HOLD_LABEL for lb in p.get("labels") or []):
        log.append(f"hold        {pid}  labelled {HOLD_LABEL} — left to people")
        return
    fb = row["feedback"].strip()
    mk = marker(fb)
    code, comments = nrs.gh("GET", f"/repos/{repo}/issues/{num}/comments?per_page=100")
    if code == 200 and any(mk in (c.get("body") or "") for c in comments):
        return                                            # this feedback was already acted on
    target = plan_target(repo, num, p["head"], p["base"]["ref"])
    if not target:
        log.append(f"skip        {pid}  no article file found in the PR")
        return
    profile = pr_review.REPOS.get(repo, "boutimar_v1")
    text, fsha = _file(repo, target["path"], branch)

    if target["kind"] == "json":
        main_text, _ = _file(repo, target["path"], p["base"]["ref"])
        lst = lambda d: d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])  # noqa: E731
        doc, have = json.loads(text), {a.get("slug") for a in lst(json.loads(main_text))}
        items = [a for a in lst(doc) if a.get("slug") not in have]
        if len(items) != 1:
            log.append(f"skip        {pid}  expected one new article in {target['path']}, found {len(items)}")
            return
        item = items[0]
        before = json.dumps(item, ensure_ascii=False)
        out = revise_text("json", before, fb, profile, "fa")
        new_item = out.get("item") or {}
        if new_item.get("slug") != item.get("slug") or set(new_item) != set(item):
            log.append(f"refused     {pid}  the revision changed the article's slug or fields")
            return
        after = json.dumps(new_item, ensure_ascii=False)
        surface = compliance.assertive_surface(new_item)
        new_text = None
        if apply:
            item.clear(); item.update(new_item)
            new_text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    else:
        fm, body = _split_fm(text)
        before = body
        lang = "fa" if re.search(r"[؀-ۿ]", body) else "en"
        out = revise_text("markdown", body, fb, profile, lang)
        after = str(out.get("text") or "")
        surface = after
        new_text = fm + after.rstrip() + "\n"

    if len(after) < MIN_KEEP * len(before):
        log.append(f"refused     {pid}  revision is {len(after)} chars vs {len(before)} — looks truncated")
        return
    findings = compliance.check(surface, profile)
    blocks = [v for v in findings if v.severity == compliance.BLOCK]
    summary = str(out.get("summary") or "").strip()[:300]
    if blocks:
        log.append(f"blocked     {pid}  revision still breaks the house rules: "
                   + "; ".join(f"{v.rule}: {v.excerpt[:60]}" for v in blocks[:3]))
        if apply:
            nrs.gh("POST", f"/repos/{repo}/issues/{num}/comments", {"body": (
                "**Automatic revision not committed** — the revised text still breaks the house rules:\n\n"
                + "\n".join(f"- `{v.rule}`: «{v.excerpt[:200]}» → {v.message}" for v in blocks)
                + f"\n\nFeedback was:\n> {fb}\n\n{mk}")})
        return
    log.append(f"revise      {pid}  {summary[:100]}")
    if not apply:
        return

    _put(repo, target["path"], branch, new_text, fsha, f"Revise per review: {fb[:50]}")
    nrs.gh("POST", f"/repos/{repo}/issues/{num}/comments", {"body": (
        f"**Revised automatically** from the Content Review feedback:\n> {fb}\n\n"
        f"What changed: {summary or '(no summary)'}\n\n"
        f"House rules on the revised text: {'PASS' if not findings else f'{len(findings)} warning(s)'}.\n\n{mk}")})
    # Back to the reviewer: fresh text in the Notion page, Status "To review".
    _, p2 = nrs.pr_state(pid)
    try:
        review = pr_review.review_pr(repo, num, profile)
    except Exception:  # noqa: BLE001
        review = {}
    nrs.write_text(row["page_id"], {"pid": pid, "repo": repo, "num": num,
                                    "sha": (p2.get("head") or {}).get("sha", ""), "review": review})
    stamp = datetime.now(timezone.utc).strftime("%-d %b")
    nrs.notion("PATCH", f"/pages/{row['page_id']}", {"properties": {
        "Status": {"select": {"name": "To review"}},
        "Feedback": {"rich_text": [{"type": "text", "text": {
            "content": f"[Done {stamp} — {summary[:160]}] {fb}"[:1900]}}]},
        **({"House rules": {"select": {"name": review.get("verdict")}}} if review.get("verdict") else {})}})


B44_FIELDS = ("title", "meta_description", "body_markdown", "faq")
BLOCKED_TAG = "[Revision blocked"


def _b44_text(item: dict) -> str:
    return "\n".join([str(item.get("title") or ""), str(item.get("meta_description") or ""),
                      str(item.get("body_markdown") or "")]
                     + [f"{x.get('q', '')} {x.get('a', '')}" for x in item.get("faq") or [] if isinstance(x, dict)])


def _feedback(page_id: str, text: str) -> None:
    nrs.notion("PATCH", f"/pages/{page_id}", {"properties": {
        "Feedback": {"rich_text": [{"type": "text", "text": {"content": text[:1900]}}]}}})


def revise_base44(row: dict, pid: str, apply: bool, log: list[str]) -> None:
    domain = next(d for d in nrs.BASE44_SITES if pid.startswith(d + "/"))
    profile = nrs.BASE44_SITES[domain][1]
    found = nrs.base44_record(pid)
    if not found:
        log.append(f"skip        {pid}  no base44 record with this slug")
        return
    app, rec = found
    if str(rec.get("status", "")).lower() != "draft":
        log.append(f"skip        {pid}  record is '{rec.get('status')}' — only drafts are revised")
        return
    fb = row["feedback"].strip()
    item = {k: rec.get(k) for k in B44_FIELDS if k in rec}
    if "body_markdown" not in item:
        log.append(f"skip        {pid}  record has no body_markdown")
        return
    lang = "fa" if re.search(r"[؀-ۿ]", str(item.get("body_markdown") or "")) else "en"
    out = revise_text("json", json.dumps(item, ensure_ascii=False), fb, profile, lang)
    new = out.get("item") or {}
    if set(new) != set(item) or not isinstance(new.get("body_markdown"), str) \
            or ("faq" in new and not isinstance(new["faq"], list)):
        log.append(f"refused     {pid}  the revision changed the article's fields")
        return
    before, after = _b44_text(item), _b44_text(new)
    if len(after) < MIN_KEEP * len(before):
        log.append(f"refused     {pid}  revision is {len(after)} chars vs {len(before)} — looks truncated")
        return
    findings = compliance.check(after, profile)
    blocks = [v for v in findings if v.severity == compliance.BLOCK]
    summary = str(out.get("summary") or "").strip()[:300]
    stamp = datetime.now(timezone.utc).strftime("%-d %b")
    if blocks:
        why = "; ".join(f"{v.rule}: {v.excerpt[:60]}" for v in blocks[:3])
        log.append(f"blocked     {pid}  revision still breaks the house rules: {why}")
        if apply:
            _feedback(row["page_id"], f"{BLOCKED_TAG} {stamp} — {why[:300]}] {fb}")
        return
    changed = {k: new[k] for k in item if new[k] != item[k]}
    if not changed:
        log.append(f"skip        {pid}  the model changed nothing")
        return
    log.append(f"revise      {pid}  {summary[:100]}  (fields: {', '.join(changed)})")
    if not apply:
        for k, v in changed.items():
            a, b = json.dumps(item[k], ensure_ascii=False), json.dumps(v, ensure_ascii=False)
            log.append(f"            {k}: {len(a)} → {len(b)} chars")
        return

    bdir = ROOT / "runs" / f"base44-revise-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    code, d = nrs.b44("PUT", f"/{app}/entities/Article/{rec['id']}", changed)
    if code != 200:
        raise RuntimeError(f"base44 write refused ({code}): {str(d)[:160]}")
    found2 = nrs.base44_record(pid)
    now = found2[1] if found2 else {}
    keep = ("slug", "status", "image_url", "image_credit", "image_source")
    drift = [k for k in keep if rec.get(k) != now.get(k)]
    if any(now.get(k) != v for k, v in changed.items()) or drift:
        nrs.b44("PUT", f"/{app}/entities/Article/{rec['id']}",
                {k: rec.get(k) for k in tuple(changed) + keep if k in rec})
        raise RuntimeError(f"unexpected read-back (changed {drift or 'the revised fields'}) — restored from backup")

    verdict, review = nrs.base44_gate(now, profile)
    nrs.write_text(row["page_id"], {"kind": "base44", "pid": pid, "title": now.get("title", ""),
                                    "summary": now.get("meta_description", ""),
                                    "md": str(now.get("body_markdown") or ""), "faq": now.get("faq") or [],
                                    "review": review})
    nrs.notion("PATCH", f"/pages/{row['page_id']}", {"properties": {
        "Status": {"select": {"name": "To review"}},
        "House rules": {"select": {"name": verdict}},
        "Feedback": {"rich_text": [{"type": "text", "text": {
            "content": f"[Done {stamp} — {summary[:160]}] {fb}"[:1900]}}]}}})


def run(apply: bool) -> list[str]:
    log: list[str] = []
    board = nrs.rows(os.environ.get("NOTION_REVIEW_DB") or nrs.DEFAULT_DB)
    for pid, row in board.items():
        if row["status"] != "Needs edits" or not row["feedback"].strip():
            continue
        if row["feedback"].lstrip().startswith(("[Done ", BLOCKED_TAG)):
            continue                      # already acted on; waiting for the reviewer
        b44 = any(pid.startswith(d + "/") for d in nrs.BASE44_SITES)
        if not b44 and "#" not in pid:
            continue
        if b44 and not os.environ.get("BASE44_ACCESS_TOKEN"):
            log.append(f"skip        {pid}  BASE44_ACCESS_TOKEN not set")
            continue
        try:
            (revise_base44 if b44 else revise_pr)(row, pid, apply, log)
        except Exception as exc:  # noqa: BLE001 — one draft never stops the others
            log.append(f"  ! {pid}: {type(exc).__name__}: {str(exc)[:200]}")
    return log or ["nothing marked Needs edits with new feedback"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rehearse", metavar="PID", help="dry-run one draft with --feedback, whatever its Status "
                    "(a bare domain = its first base44 draft); never writes")
    ap.add_argument("--feedback", default="")
    a = ap.parse_args(argv)
    missing = [k for k in ("NOTION_TOKEN", "GITHUB_TOKEN") if not os.environ.get(k)]
    if missing:
        print(f"not configured: {', '.join(missing)} — nothing revised")
        return 0
    if a.rehearse:
        pid = a.rehearse
        if pid in nrs.BASE44_SITES:
            pid = next((r["pid"] for r in nrs.base44_drafts() if r["site"] == pid), pid)
        log: list[str] = []
        row = {"page_id": "", "status": "Needs edits", "feedback": a.feedback}
        (revise_base44 if any(pid.startswith(d + "/") for d in nrs.BASE44_SITES) else revise_pr)(row, pid, False, log)
        print(f"rehearsal (nothing written) — {pid}\n" + "\n".join(log or ["(no output)"]))
        return 0
    print("\n".join(run(a.apply)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
