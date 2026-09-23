#!/usr/bin/env python3
"""
Orchestration health — what broke, what needs a human, and the numbers.

Every agent already writes a step summary and an artifact. Nobody reads step
summaries. On 6 Sep the writer failed, the broadcaster was skipped, a brief hit
a 1.7M-token prompt, the Gemini fallback turned out to be on the free tier, and
three article PRs sat unmerged — and none of it reached Alireza for six days
because every one of those facts lived inside a green-or-red run he had to open.

This reads the same artifacts the agents produce and turns them into one report
that LEADS with the failures, then the things only he can do, then the numbers.
It exits non-zero on anything critical so the `health` workflow goes red — which
is the one signal GitHub emails him about without any new infrastructure.

    python3 tools/health_report.py            # prints markdown, writes reports/
    python3 tools/health_report.py --json     # machine form too

Reads the GitHub API with GITHUB_TOKEN (same-repo runs + artifacts) and, when
BRIDGE_GH_TOKEN is present, the open PRs on the property repos.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = "ambientetravel/albaloostudio"
API = "https://api.github.com"
# Repos whose open PRs are the pipeline's *output waiting on a human*.
PR_REPOS = ["ambientetravel/boutimar", "ambientetravel/exploreorient",
            "ambientetravel/boutimarfarsi", "ambientetravel/cruise24-ir"]
# Workflow display names → the short label used in the report.
AGENTS = {
    "Agent 1 — SEO Scout": "Scout",
    "Agent 2 — Writer": "Writer",
    "Agent 3 — Broadcaster": "Broadcaster",
    "Agent 4 — Sales Closer": "Closer",
    "Agent 5+6 — Site audit & strategy": "Auditor+Analyst",
    "Agent 7 — Keyword & Geo Scout": "Cartographer",
    "Agent 8 — Competitor Scout": "Watcher",
    "Agent 9 — AI Visibility": "Oracle",
    "Merge watch — which drafts went live": "Merge-watch",
    "PR gate — compliance review across the bridge": "PR gate",
    "Portfolio dashboard": "Dashboard",
}
# The ones whose failure means the week produced nothing.
CORE = {"Agent 1 — SEO Scout", "Agent 2 — Writer", "Agent 3 — Broadcaster"}
STALE_DAYS = 9          # a weekly agent older than this has missed a cycle
PR_NUDGE_DAYS = 3       # an article PR older than this is waiting on him


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_days(iso: str) -> float:
    # GitHub created_at is reliably ISO, but a missing or malformed value must not
    # crash the health report — it is the alert, and a dead alert is worse than a
    # wrong age. Unparseable reads as age 0 (not stale, no false nudge), matching
    # _ledger._parse's guard on the same construct.
    if not iso:
        return 0.0
    try:
        return (_now() - datetime.fromisoformat(str(iso).replace("Z", "+00:00"))).total_seconds() / 86400
    except (ValueError, TypeError):
        return 0.0


def _curl(url: str, token: str, *, binary: bool = False) -> tuple[int, bytes]:
    args = ["curl", "-sSL", "--max-time", "60",
            "-H", "Accept: application/vnd.github+json",
            "-H", f"Authorization: Bearer {token}",
            "-H", "User-Agent: albaloo-health",
            "-w", "\n%{http_code}", url]
    r = subprocess.run(args, capture_output=True, timeout=90)
    out = r.stdout
    nl = out.rfind(b"\n")
    body, code = out[:nl], out[nl + 1:].strip() or b"0"
    return int(code), body


def _json(url: str, token: str):
    code, body = _curl(url, token)
    if code >= 400:
        raise RuntimeError(f"GitHub {code} for {url.replace(API, '')}: {body[:100]!r}")
    return json.loads(body.decode("utf-8"))


def latest_runs(token: str) -> dict[str, dict]:
    """Newest run per workflow display name."""
    d = _json(f"{API}/repos/{REPO}/actions/runs?per_page=100", token)
    out: dict[str, dict] = {}
    for r in d.get("workflow_runs", []):
        out.setdefault(r["name"], r)  # list is newest-first
    return out


def latest_artifact(token: str, name: str, index: int = 0) -> dict | None:
    d = _json(f"{API}/repos/{REPO}/actions/artifacts?name={name}&per_page=10", token)
    arts = [a for a in d.get("artifacts", []) if not a.get("expired")]
    return arts[index] if len(arts) > index else None


def artifact_file(token: str, art: dict, suffix: str) -> dict | None:
    """The first file in the artifact zip whose path ends with `suffix`, parsed."""
    code, body = _curl(art["archive_download_url"], token, binary=True)
    if code >= 400:
        return None
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile:
        return None
    for n in z.namelist():
        if n.endswith(suffix):
            try:
                return json.loads(z.read(n).decode("utf-8"))
            except ValueError:
                return None
    return None


def open_prs(token: str) -> tuple[list[dict], list[str]]:
    prs, unreadable = [], []
    for repo in PR_REPOS:
        try:
            for p in _json(f"{API}/repos/{repo}/pulls?state=open&per_page=30", token):
                prs.append({"repo": repo, "number": p["number"], "title": p["title"],
                            "age": _age_days(p["created_at"]), "url": p["html_url"]})
        except RuntimeError as exc:
            unreadable.append(f"{repo} ({str(exc)[:40]})")
    return prs, unreadable


def build(token: str, bridge_token: str) -> dict:
    critical, needs_you, warn, fine = [], [], [], []
    numbers: dict[str, object] = {}

    # ── 1. runs: what each agent last did ─────────────────────────────
    runs = latest_runs(token)
    agents = []
    for wf, label in AGENTS.items():
        r = runs.get(wf)
        if not r:
            agents.append({"agent": label, "result": "never ran", "age_days": None, "url": ""})
            continue
        age = _age_days(r["created_at"])
        row = {"agent": label, "result": r["conclusion"] or r["status"],
               "age_days": round(age, 1), "url": r["html_url"], "run": r["run_number"]}
        agents.append(row)
        if wf in CORE:
            if r["conclusion"] == "failure":
                critical.append(f"**{label}** last run **failed** (#{r['run_number']}, "
                                f"{age:.1f}d ago) — {r['html_url']}")
            elif r["conclusion"] == "skipped":
                critical.append(f"**{label}** was **skipped** last cycle (#{r['run_number']}) "
                                f"— its upstream failed, so nothing downstream ran")
            elif age > STALE_DAYS:
                warn.append(f"{label} has not run for {age:.0f} days (weekly cadence expected)")

    # ── 2. scout: briefs, dead letters, degraded ──────────────────────
    scout = None
    art = latest_artifact(token, "seo-scout-run")
    if art:
        scout = artifact_file(token, art, "manifest.json")
    if scout:
        doms = scout.get("domains", [])
        briefs = sum(d.get("briefs_emitted") or 0 for d in doms)
        cands = sum(d.get("candidates") or 0 for d in doms)
        dlq = sum(d.get("dlq") or 0 for d in doms)
        degraded = sum(d.get("degraded_briefs") or 0 for d in doms)
        skipped = sum(d.get("skipped_recent") or 0 for d in doms)
        numbers.update(briefs=briefs, candidates=cands, dlq=dlq, degraded=degraded,
                       ledger_skipped=skipped, sites_scanned=len(doms),
                       scout_run=scout.get("run_id"))
        if dlq:
            warn.append(f"{dlq} brief(s) dead-lettered by the compliance gate (gate working; "
                        f"review the DLQ for anything worth a human rewrite)")
        if degraded:
            bad = [d["domain"] for d in doms if d.get("degraded_briefs")]
            reason = next((d.get("degraded_reason") for d in doms if d.get("degraded_reason")), "")
            warn.append(f"{degraded} brief(s) built **without the model** on {', '.join(bad)} "
                        f"— not worth publishing; the writer skips them. Cause: {reason[:90]}")
        if briefs == 0 and cands:
            critical.append(f"Scout found {cands} candidates but emitted **0 briefs**")

    # ── 3. writer: articles, PRs, failures, cost ───────────────────────
    writer = prev_writer = None
    art = latest_artifact(token, "agent2-written")
    if art:
        writer = artifact_file(token, art, "manifest.json")
    art2 = latest_artifact(token, "agent2-written", 1)
    if art2:
        prev_writer = artifact_file(token, art2, "manifest.json")
    if writer:
        drafted, failed = writer.get("drafted", 0), writer.get("failed", 0)
        cost = (writer.get("usage") or {}).get("estimated_cost_usd")
        prev_cost = ((prev_writer or {}).get("usage") or {}).get("estimated_cost_usd")
        numbers.update(articles=drafted, writer_failed=failed,
                       deferred=writer.get("deferred_by_limit", 0),
                       briefs_seen=writer.get("briefs_seen", 0),
                       cost_usd=cost, prev_cost_usd=prev_cost,
                       prev_articles=(prev_writer or {}).get("drafted"))
        if drafted == 0 and writer.get("briefs_seen"):
            critical.append(f"Writer saw {writer['briefs_seen']} briefs and drafted **0 articles**")
        for o in writer.get("outcomes", []):
            err = str(o.get("error") or "")
            if o.get("status") == "failed":
                what = f"**{o.get('domain')}** '{o.get('keyword')}'"
                if "prompt is too long" in err:
                    critical.append(f"{what} failed: the writer built a prompt too large for "
                                    f"the model ({err[err.find('too long'):][:60]}…) — a feed "
                                    f"was injected unbounded")
                else:
                    warn.append(f"{what} failed: {err[:120]}")
            if "free_tier" in err or "FreeTier" in err:
                needs_you.append("**Gemini is on the FREE tier** — the fallback hit "
                                 "`free_tier_input_token_count` 429. Billing is not active on "
                                 "the key the pipeline uses, so the 'funded fallback' is not funded.")
            if "credit balance" in err.lower():
                needs_you.append("**Anthropic balance exhausted** — top up or lower the cap.")
        if writer.get("deferred_by_limit"):
            warn.append(f"{writer['deferred_by_limit']} brief(s) deferred by the per-run cap "
                        f"— these are lost to the 45-day ledger cooldown, not queued")

    # ── 4. broadcaster ────────────────────────────────────────────────
    art = latest_artifact(token, "agent3-broadcast")
    bc = artifact_file(token, art, "manifest.json") if art else None
    if bc:
        numbers.update(posts=bc.get("posts_total"), posts_held=bc.get("posts_held"),
                       posts_no_media=bc.get("posts_blocked_media"),
                       campaigns=bc.get("composed"))
        if bc.get("posts_blocked_media"):
            needs_you.append(f"{bc['posts_blocked_media']} social post(s) blocked for **missing "
                             f"media** — no image source is wired, so these can never ship")
        if bc.get("posts_held"):
            fine.append(f"{bc['posts_held']} social post(s) composed and held at the autopost "
                        f"gate (switched off, as designed)")

    # ── 5. output waiting on a human: open PRs ────────────────────────
    prs, unreadable = open_prs(bridge_token or token)
    stale = [p for p in prs if p["age"] >= PR_NUDGE_DAYS]
    numbers.update(open_prs=len(prs))
    if stale:
        needs_you.append(f"**{len(stale)} article PR(s) waiting on your merge** "
                         f"(oldest {max(p['age'] for p in stale):.0f} days): " +
                         "; ".join(f"[{p['repo'].split('/')[1]}#{p['number']}]({p['url']}) "
                                   f"{p['title'][:48]}" for p in sorted(stale, key=lambda p: -p["age"])))
    if unreadable:
        warn.append("Open PRs unreadable on: " + ", ".join(unreadable) +
                    " — BRIDGE_GH_TOKEN lacks these repos")

    # ── 6. the gate's own honesty ─────────────────────────────────────
    g = runs.get("PR gate — compliance review across the bridge")
    if g and g["conclusion"] == "failure":
        critical.append("**PR gate could not read any repo** — no PR was reviewed. "
                        "Fix BRIDGE_GH_TOKEN's repository access.")

    # ── 7. AI recall (monthly) ────────────────────────────────────────
    art = latest_artifact(token, "ai-visibility")
    aiv = artifact_file(token, art, ".json") if art else None
    if isinstance(aiv, dict) and aiv.get("properties"):
        named = sum(1 for p in aiv["properties"].values() if p.get("mentioned_any"))
        numbers.update(ai_recall=f"{named}/{len(aiv['properties'])} properties named")

    return {"generated": _now().isoformat(timespec="minutes"), "critical": critical,
            "needs_you": needs_you, "warn": warn, "fine": fine, "numbers": numbers,
            "agents": agents}


def render(rep: dict) -> str:
    n = rep["numbers"]
    L = [f"# Orchestration health — {rep['generated'][:16]} UTC", ""]
    L.append(f"**{len(rep['critical'])} broke · {len(rep['needs_you'])} need you · "
             f"{len(rep['warn'])} to watch.**")
    L.append("")
    if rep["critical"]:
        L += ["## 🔴 Broke", ""] + [f"- {x}" for x in rep["critical"]] + [""]
    else:
        L += ["## 🔴 Broke", "", "- Nothing. Every core agent's last run succeeded.", ""]
    if rep["needs_you"]:
        L += ["## 🟡 Needs you — only you can do these", ""] + [f"- {x}" for x in rep["needs_you"]] + [""]
    if rep["warn"]:
        L += ["## 👀 To watch", ""] + [f"- {x}" for x in rep["warn"]] + [""]

    def d(key, fmt="{}"):
        v = n.get(key)
        return "—" if v is None else fmt.format(v)
    L += ["## Numbers — last cycle", "",
          "| Metric | This cycle | Previous |", "|---|---:|---:|",
          f"| Sites scanned | {d('sites_scanned')} | |",
          f"| Gap candidates → briefs | {d('candidates')} → **{d('briefs')}** | |",
          f"| Skipped by ledger (already briefed) | {d('ledger_skipped')} | |",
          f"| Dead-lettered / degraded | {d('dlq')} / {d('degraded')} | |",
          f"| Articles drafted (as PRs) | **{d('articles')}** | {d('prev_articles')} |",
          f"| Briefs deferred by cap | {d('deferred')} | |",
          f"| Model spend | {d('cost_usd', '${:.3f}')} | {d('prev_cost_usd', '${:.3f}')} |",
          f"| Social: campaigns / posts held / no-media | {d('campaigns')} / {d('posts_held')} / {d('posts_no_media')} | |",
          f"| Article PRs open | {d('open_prs')} | |",
          f"| AI recall (Oracle, monthly) | {d('ai_recall')} | |", ""]
    L += ["## Agents", "", "| Agent | Last result | Age | |", "|---|---|---:|---|"]
    for a in rep["agents"]:
        mark = {"success": "✓", "failure": "✗", "skipped": "⏭"}.get(a["result"], "·")
        age = "—" if a["age_days"] is None else f"{a['age_days']}d"
        link = f"[run]({a['url']})" if a.get("url") else ""
        L.append(f"| {a['agent']} | {mark} {a['result']} | {age} | {link} |")
    L.append("")
    if rep["fine"]:
        L += ["## ✓ Fine", ""] + [f"- {x}" for x in rep["fine"]] + [""]
    L.append("_Generated by `tools/health_report.py` from the agents' own artifacts. "
             "Architecture credit: Albaloo Studio._")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default="reports")
    a = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    bridge = os.environ.get("BRIDGE_GH_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 4
    rep = build(token, bridge)
    md = render(rep)
    print(md)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "health-latest.md").write_text(md, encoding="utf-8")
    (out / f"health-{rep['generated'][:10]}.md").write_text(md, encoding="utf-8")
    if a.json:
        (out / "health-latest.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    # 2 = something broke (the workflow goes red → GitHub emails). 1 = needs a
    # human but nothing is broken (yellow, no alarm). 0 = clean.
    if rep["critical"]:
        return 2
    return 1 if rep["needs_you"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
