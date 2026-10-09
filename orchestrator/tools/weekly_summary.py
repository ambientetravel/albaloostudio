#!/usr/bin/env python3
"""
The Monday summary — one Notion page a week, built for reading on a phone.

Alireza reviews from his phone (Remote Control, Notion app). The pipeline's own
state is spread over a GitHub health report, a Notion board, four site repos and
two run artifacts; nobody opens five places on a phone. Every Monday this writes
ONE page under the "websites" page:

  @Alireza — mention first, so the Notion app pushes a notification
  Waiting for you   every board row needing a decision, tap-to-open
  Went live         articles merged in the last 7 days, with the live link
  Sunday's run      what the writer produced per site; blocked / failed named
  Health            what broke (or "nothing"), what needs him
  Spend             model cost of the last real cycle

Read-only towards everything except the one new Notion page.

    python3 tools/weekly_summary.py            # print the summary, write nothing
    python3 tools/weekly_summary.py --apply    # create the Notion page

Env: NOTION_TOKEN, GITHUB_TOKEN (site repos), GH_ALBALOO_TOKEN (this repo's
artifacts), NOTION_REVIEW_DB, NOTION_SUMMARY_PARENT, NOTION_OWNER_ID.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import health_report as hr  # noqa: E402
import notion_review_sync as nrs  # noqa: E402

WEBSITES_PAGE = "37b5b5e3660b802da9f2c97d003c9463"       # Notion "websites", parent of Content Review
OWNER = "1e746a95-158f-4f48-91e6-728fa01dacd7"            # Alireza Mozaffari (Notion user)
WAITING = ("To review", "Needs edits", "Approved")         # Approved = merges at the next sync


def _prop_text(pr: dict, name: str) -> str:
    p = pr.get(name) or {}
    if p.get("type") == "select":
        return ((p.get("select") or {}).get("name")) or ""
    if p.get("type") == "url":
        return p.get("url") or ""
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
            out.append({"url": p.get("url", ""), "title": _prop_text(pr, "Article"),
                        "site": _prop_text(pr, "Site"), "status": _prop_text(pr, "Status"),
                        "pid": _prop_text(pr, "Pipeline ID"), "live": _prop_text(pr, "Live page"),
                        "gate": _prop_text(pr, "House rules"), "feedback": _prop_text(pr, "Feedback")})
        if not d.get("has_more"):
            return out
        cursor = d.get("next_cursor")


def went_live(rows: list[dict], since: datetime) -> list[dict]:
    """Published rows whose PR merged in the window (base44 rows have no PR; skipped)."""
    out = []
    for r in rows:
        if r["status"] != "Published" or "#" not in r["pid"]:
            continue
        _, p = nrs.pr_state(r["pid"])
        merged = (p or {}).get("merged_at") or ""
        if merged and datetime.fromisoformat(merged.replace("Z", "+00:00")) >= since:
            out.append({**r, "merged": merged[:10], "http": live_status(r["live"])})
    return out


def live_status(url: str) -> int:
    """HTTP status of the live page. "Merged" is not "live": on 10 Oct boutimar.ir's
    deploy was a green no-op and boutimar.com's skipped img/ — both looked done."""
    if not url:
        return 0
    code, _ = nrs._curl("GET", url, ["User-Agent: albaloo-weekly-summary"])
    return code


def last_cycle(token: str) -> dict:
    """The newest REAL (not dry-run) writer and scout manifests."""
    def newest(name: str) -> dict:
        for i in range(10):
            art = hr.latest_artifact(token, name, i)
            if not art:
                return {}
            m = hr.artifact_file(token, art, "manifest.json")
            if m and not m.get("dry_run"):
                return m
        return {}
    return {"writer": newest("agent2-written"), "scout": newest("seo-scout-run")}


def build(rows: list[dict], live: list[dict], cycle: dict, health: dict, now: datetime) -> dict:
    waiting = [r for r in rows if r["status"] in WAITING]
    w = cycle.get("writer") or {}
    per_site: dict[str, dict] = {}
    for o in w.get("outcomes") or []:
        s = per_site.setdefault(o.get("domain") or "?", {"drafted": [], "blocked": [], "failed": []})
        if o.get("status") in s:
            s[o["status"]].append(o.get("keyword") or o.get("target_url") or "")
    cost = sum(float(((cycle.get(k) or {}).get("usage") or {}).get("estimated_cost_usd") or 0)
               for k in ("writer", "scout"))
    return {"date": now.strftime("%-d %b %Y"), "waiting": waiting,
            # No live link (photo PRs, rows the sync never filled) cannot be tested,
            # so it is listed as live-unchecked — a false "NOT live" alarm trains the
            # reader to ignore the section that matters.
            "live": [r for r in live if r.get("http") == 200 or not r.get("live")],
            "not_live": [r for r in live if r.get("live") and r.get("http") != 200], "per_site": per_site,
            "critical": [_short(c) for c in health.get("critical") or []],
            # "N article PR(s) waiting on your merge" repeats the Waiting list above.
            "needs_you": [_short(n) for n in health.get("needs_you") or [] if "waiting on your merge" not in n],
            "cost": round(cost, 2), "drafted": w.get("drafted", 0)}


def as_text(s: dict) -> str:
    """The same summary as plain text (dry run, and the run's step summary)."""
    L = [f"# Monday summary — {s['date']}", "", f"## Waiting for you ({len(s['waiting'])})"]
    L += [f"- [{r['status']}] {r['site']} — {r['title']} {'⚠ ' + r['gate'] if r['gate'] in ('WARN', 'BLOCK') else ''}"
          for r in s["waiting"]] or ["- nothing"]
    L += ["", f"## Went live this week ({len(s['live'])})"]
    L += [f"- {r['site']} — {r['title']} → {r['live'] or '(no link yet)'}" for r in s["live"]] or ["- nothing"]
    if s["not_live"]:
        L += ["", f"## ⚠ Merged but NOT live ({len(s['not_live'])})"]
        L += [f"- {r['site']} — {r['title']} → {r['live'] or '(no link)'} answers {r['http']}"
              for r in s["not_live"]]
    L += ["", f"## Sunday's run — {s['drafted']} draft(s)"]
    for site, v in sorted(s["per_site"].items()):
        L.append(f"- {site}: {len(v['drafted'])} drafted"
                 + (f", {len(v['blocked'])} blocked" if v["blocked"] else "")
                 + (f", {len(v['failed'])} failed" if v["failed"] else ""))
    L += ["", "## Health"] + ([f"- 🔴 {c}" for c in s["critical"]] or ["- Nothing broke."])
    L += [f"- 🟡 {n}" for n in s["needs_you"]]
    L += ["", f"## Spend — ${s['cost']:.2f} for the last cycle", "",
          "Next writing cycle: Sunday 07:15 Istanbul."]
    return "\n".join(L)


def _p(text: str, link: str = "") -> dict:
    t = {"type": "text", "text": {"content": text[:1900], **({"link": {"url": link}} if link else {})}}
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [t]}}


def _li(parts: list[tuple[str, str]]) -> dict:
    rt = [{"type": "text", "text": {"content": t[:1900], **({"link": {"url": u}} if u else {})}} for t, u in parts]
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt}}


def _h(text: str) -> dict:
    return nrs._blk("heading_2", text)


def as_blocks(s: dict, owner: str) -> list[dict]:
    head = {"object": "block", "type": "callout", "callout": {"icon": {"emoji": "📬"}, "rich_text": [
        {"type": "mention", "mention": {"type": "user", "user": {"id": owner}}},
        {"type": "text", "text": {"content": f" — {len(s['waiting'])} waiting for you, "
                                              f"{len(s['live'])} went live, "
                                              + (f"{len(s['not_live'])} merged but NOT live, "
                                                 if s["not_live"] else "")
                                              +
                                              f"{'nothing broke' if not s['critical'] else str(len(s['critical'])) + ' broke'}."}}]}}
    B = [head, _h(f"Waiting for you ({len(s['waiting'])})")]
    if s["waiting"]:
        for r in s["waiting"]:
            flag = " ⚠ " + r["gate"] if r["gate"] in ("WARN", "BLOCK") else ""
            note = " — merges at the next sync" if r["status"] == "Approved" else ""
            B.append(_li([(f"[{r['status']}] {r['site']} — ", ""), (r["title"], r["url"]), (flag + note, "")]))
    else:
        B.append(_p("Nothing — the board is clear."))
    B.append(_h(f"Went live this week ({len(s['live'])})"))
    B += [_li([(f"{r['site']} — ", ""), (r["title"], r["live"] or r["url"])]) for r in s["live"]] \
        or [_p("Nothing merged in the last 7 days.")]
    if s["not_live"]:
        B.append(_h(f"⚠ Merged but NOT live ({len(s['not_live'])})"))
        B += [_li([(f"{r['site']} — ", ""), (r["title"], r["url"]),
                   (f" — {r['live'] or 'no live link'} answers {r['http']}", "")]) for r in s["not_live"]]
    B.append(_h(f"Sunday's run — {s['drafted']} draft(s)"))
    for site, v in sorted(s["per_site"].items()):
        txt = f"{site}: {len(v['drafted'])} drafted"
        if v["blocked"]:
            txt += f", {len(v['blocked'])} blocked by the house rules"
        if v["failed"]:
            txt += f", {len(v['failed'])} failed"
        B.append(_li([(txt, "")]))
    if not s["per_site"]:
        B.append(_p("No writer run found for the last cycle."))
    B.append(_h("Health"))
    B += [_li([("🔴 " + c, "")]) for c in s["critical"]] or [_p("✅ Nothing broke.")]
    B += [_li([("🟡 " + n, "")]) for n in s["needs_you"]]
    B.append(_h("Spend"))
    B.append(_p(f"${s['cost']:.2f} in model calls for the last cycle (scout + writer)."))
    B.append(_p("Next writing cycle: Sunday 07:15 Istanbul. Approve on the Content Review board; "
                "Needs edits + Feedback is rewritten automatically within the hour."))
    return B


def _short(text: str, n: int = 160) -> str:
    """One phone-width line: Markdown link syntax dropped, cut at a word."""
    import re
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", str(text)).replace("**", "")
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …"


CONTAINER_TITLE = "📬 Monday summaries"


def _container(db: str) -> str:
    """The integration only sees the Content Review database, not the "websites"
    page above it (10 Oct: 404). So the summaries live under one container row on
    that board — no Pipeline ID, no Status, ignored by the sync — found or made once."""
    code, d = nrs.notion("POST", f"/databases/{db}/query", {"page_size": 5, "filter": {
        "property": "Article", "title": {"equals": CONTAINER_TITLE}}})
    if code == 200 and d.get("results"):
        return d["results"][0]["id"]
    code, d = nrs.notion("POST", "/pages", {"parent": {"database_id": db}, "icon": {"emoji": "📬"},
                                            "properties": {"Article": {"title": [{"type": "text", "text": {
                                                "content": CONTAINER_TITLE}}]}}})
    if code != 200:
        raise RuntimeError(f"Notion {code} creating the summaries row: {str(d)[:200]}")
    return d["id"]


def publish(s: dict, parent: str, owner: str, db: str) -> str:
    page = {"icon": {"emoji": "📬"},
            "properties": {"title": {"title": [{"type": "text", "text": {"content": f"Monday summary — {s['date']}"}}]}},
            "children": as_blocks(s, owner)}
    code, d = nrs.notion("POST", "/pages", {"parent": {"page_id": parent}, **page})
    if code == 404:                       # "websites" not shared with the integration
        parent = _container(db)
        code, d = nrs.notion("POST", "/pages", {"parent": {"page_id": parent}, **page})
    if code == 400 and "Could not find user" in str(d):
        # The integration lacks the "Read user information" capability, so it may
        # not @mention anyone (10 Oct). The page still goes up — without the push.
        page["children"][0]["callout"]["rich_text"][0] = {"type": "text", "text": {"content": "Alireza"}}
        code, d = nrs.notion("POST", "/pages", {"parent": {"page_id": parent}, **page})
        if code == 200:
            print("note: no @mention (integration cannot read users) — enable 'Read user information' "
                  "on the Notion integration to get the phone notification")
    if code != 200:
        raise RuntimeError(f"Notion {code}: {str(d)[:200]}")
    return d.get("url", "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if not os.environ.get("NOTION_TOKEN"):
        print("not configured: NOTION_TOKEN — nothing to summarise")
        return 0
    now = datetime.now(timezone.utc)
    rows = board(os.environ.get("NOTION_REVIEW_DB") or nrs.DEFAULT_DB)
    live = went_live(rows, now - timedelta(days=7))
    cycle = last_cycle(os.environ.get("GH_ALBALOO_TOKEN") or os.environ.get("GITHUB_TOKEN", ""))
    hp = ROOT / "reports" / "health-latest.json"
    health = json.loads(hp.read_text(encoding="utf-8")) if hp.exists() else {}
    s = build(rows, live, cycle, health, now)
    print(as_text(s))
    if a.apply:
        url = publish(s, os.environ.get("NOTION_SUMMARY_PARENT") or WEBSITES_PAGE,
                      os.environ.get("NOTION_OWNER_ID") or OWNER,
                      os.environ.get("NOTION_REVIEW_DB") or nrs.DEFAULT_DB)
        print(f"\nNotion page: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
