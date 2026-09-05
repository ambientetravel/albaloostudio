#!/usr/bin/env python3
"""
PR compliance gate — Claude's house rules over a pull request's diff.

This is what makes GitHub the bridge between the models. Codex/GPT, Jules/Gemini
and Claude all contribute the same way — by opening a pull request — and every
one of those PRs is read here against the exact rules the manifest bridge and the
writer already enforce (compliance.check): «خلیج فارس» never "Arabian Gulf", easy
visa ≠ no visa, no invented rate/date, no photo-credit guess, brand separation.

It never merges and never pushes. It reads a PR and returns a verdict — PASS,
WARN or BLOCK — so a human (or Claude) can decide. Posting the verdict as a PR
comment is opt-in (--post); by default it only prints.

    python3 tools/pr_review.py --repo ambientetravel/boutimar --pr 6
    python3 tools/pr_review.py --all            # every open PR on the git-backed sites

Auth: GITHUB_TOKEN (a classic token with repo read; contents:read is enough to
read, and issues:write only if you pass --post).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compliance  # noqa: E402

# The git-backed properties and the compliance profile each PR is judged under.
# exploreorient uses the brand-neutral profile so a boutimar brand/link leak —
# the Explore Orient brand-separation breach — is caught automatically.
GAME_REPO = "ambientetravel/persia-at-war"

REPOS = {
    "ambientetravel/boutimar": "boutimar_v1",
    "ambientetravel/boutimarfarsi": "boutimar_v1",
    "ambientetravel/exploreorient": "partner_widget_v1",
    "ambientetravel/albaloostudio": "boutimar_v1",
    # Persia at War — a standalone game, deliberately NOT a travel property.
    # Its own repo so an outside agent can be given PR access to the game
    # without being handed read of the whole travel operation. Change the name
    # here and in PATH_PROFILES below if the repo is created under another owner.
    GAME_REPO: "persia_at_war_v1",
}

# Paths judged under a different profile than their repo's default.
#
# One entry, and it is a TRANSITIONAL one: the game still sits inside
# albaloostudio under persia-wars-game/ until the standalone repo above is
# created and pushed. Once it is, this rule stops matching anything and can go.
# It is kept meanwhile because judging the game under the travel profile passes
# a PR that invents a Persian heroine, and that is the one failure a product
# built to teach honestly cannot survive.
PATH_PROFILES = (
    ("persia-wars-game/", "persia_at_war_v1"),
)


def profile_for(filename: str, default: str) -> str:
    """The compliance profile a single changed file is judged under."""
    for prefix, profile in PATH_PROFILES:
        if filename.startswith(prefix):
            return profile
    return default
API = "https://api.github.com"
# Only lines a person would read as content; skip lockfiles and generated noise.
TEXT_EXT = (".md", ".mdx", ".astro", ".html", ".htm", ".json", ".js", ".ts",
            ".jsx", ".tsx", ".txt", ".yml", ".yaml", ".vue", ".svelte")


def _curl(args: list[str]) -> tuple[int, str]:
    """GitHub over curl — this project's hosts have no Python CA bundle, and curl
    works both here and in CI. Returns (http_status, body)."""
    tok = os.environ.get("GITHUB_TOKEN", "")
    base = ["curl", "-sS", "--max-time", "30",
            "-H", "Accept: application/vnd.github+json",
            "-H", f"Authorization: Bearer {tok}",
            "-H", "User-Agent: albaloo-pr-gate",
            "-w", "\n%{http_code}"]
    r = subprocess.run(base + args, capture_output=True, text=True, timeout=40)
    out = r.stdout.rsplit("\n", 1)
    body, code = (out[0], out[1]) if len(out) == 2 else (r.stdout, "000")
    return int(code or 0), body


def _gh(path: str) -> object:
    code, body = _curl([API + path])
    if code >= 400:
        raise RuntimeError(f"GitHub {code} for {path}: {body[:120]}")
    return json.loads(body)


def _added_text(patch: str) -> str:
    """The lines this PR ADDS — a '+' that is not the '+++' file header."""
    out = []
    for line in (patch or "").splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return "\n".join(out)


def review_pr(repo: str, num: int, profile: str) -> dict:
    files = _gh(f"/repos/{repo}/pulls/{num}/files?per_page=100")
    blocks, warns, scanned = [], [], 0
    for f in files if isinstance(files, list) else []:
        name = f.get("filename", "")
        patch = f.get("patch")  # None for binary/renamed-only
        if not patch or not name.lower().endswith(TEXT_EXT):
            continue
        scanned += 1
        text = _added_text(patch)
        for v in compliance.check(text, profile_for(name, profile)):
            row = {"file": name, "rule": v.rule, "excerpt": v.excerpt, "fix": v.message,
                   "profile": profile_for(name, profile)}
            (blocks if v.severity == compliance.BLOCK else warns).append(row)
    verdict = "BLOCK" if blocks else ("WARN" if warns else "PASS")
    return {"repo": repo, "pr": num, "profile": profile, "files_scanned": scanned,
            "verdict": verdict, "blocks": blocks, "warns": warns}


def _print(r: dict) -> None:
    mark = {"PASS": "✓", "WARN": "▲", "BLOCK": "✗"}[r["verdict"]]
    print(f"\n{mark} {r['repo']}#{r['pr']} — {r['verdict']} "
          f"({r['files_scanned']} content file(s), profile {r['profile']})")
    for tag, rows in (("BLOCK", r["blocks"]), ("WARN", r["warns"])):
        for x in rows:
            print(f"    {tag} [{x['rule']}] {x['file']}")
            print(f"          …{x['excerpt']}…")
            print(f"          → {x['fix']}")


def _comment_body(r: dict) -> str:
    head = {"PASS": "✓ **Compliance gate: PASS**", "WARN": "▲ **Compliance gate: WARN**",
            "BLOCK": "✗ **Compliance gate: BLOCK — do not merge as-is**"}[r["verdict"]]
    lines = [head, "", f"House rules over the diff ({r['files_scanned']} content file(s), "
             f"profile `{r['profile']}`). Reviewed by the Albaloo bridge, not merged.", ""]
    for tag, rows in (("BLOCK", r["blocks"]), ("WARN", r["warns"])):
        for x in rows:
            lines.append(f"- **{tag}** `{x['rule']}` in `{x['file']}` — {x['fix']}")
            lines.append(f"  > …{x['excerpt']}…")
    if r["verdict"] == "PASS":
        lines.append("_No house-rule violations found. A human still owns the merge._")
    return "\n".join(lines)


def _post(repo: str, num: int, body: str) -> None:
    payload = json.dumps({"body": body})
    code, resp = _curl(["-X", "POST", "-H", "Content-Type: application/json",
                        "-d", payload, f"{API}/repos/{repo}/issues/{num}/comments"])
    if code >= 400:
        print(f"    ! could not post to {repo}#{num} ({code}): {resp[:120]}")
    else:
        print(f"    …posted verdict comment to {repo}#{num}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Compliance gate for a PR diff.")
    ap.add_argument("--repo", help="owner/name")
    ap.add_argument("--pr", type=int)
    ap.add_argument("--all", action="store_true", help="every open PR on the git-backed sites")
    ap.add_argument("--profile", help="override the per-repo default")
    ap.add_argument("--post", action="store_true", help="post the verdict as a PR comment (write)")
    a = ap.parse_args()

    jobs: list[tuple[str, int, str]] = []
    if a.all:
        for repo, prof in REPOS.items():
            for pr in _gh(f"/repos/{repo}/pulls?state=open&per_page=50"):
                jobs.append((repo, pr["number"], a.profile or prof))
    elif a.repo and a.pr:
        jobs.append((a.repo, a.pr, a.profile or REPOS.get(a.repo, "boutimar_v1")))
    else:
        ap.error("give --all, or --repo owner/name --pr N")

    worst = 0
    rank = {"PASS": 0, "WARN": 1, "BLOCK": 2}
    for repo, num, prof in jobs:
        try:
            r = review_pr(repo, num, prof)
        except (RuntimeError, ValueError) as exc:
            print(f"\n! {repo}#{num} — could not read ({exc})")
            continue
        _print(r)
        if a.post:
            _post(repo, num, _comment_body(r))
        worst = max(worst, rank[r["verdict"]])
    print(f"\n{len(jobs)} PR(s) reviewed. Nothing merged; the merge is a human's.")
    return worst  # non-zero exit on WARN/BLOCK, so CI can gate on it


if __name__ == "__main__":
    raise SystemExit(main())
