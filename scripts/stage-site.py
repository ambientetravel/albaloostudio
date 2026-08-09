#!/usr/bin/env python3
"""
Stage albaloostudio.com into _site/ for deployment.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Why this exists instead of `lftp mirror -R .`
---------------------------------------------
This repository root is BOTH the albaloostudio.com document root AND the
working directory for the whole travel portfolio. Sitting next to index.html
are orchestrator/ (sites.yml, ARCHITECTURE.md, SETUP-GSC.md, the compliance
gate), CLAUDE.md and AGENTS.md (internal working instructions), docs/, and a
dozen untracked sibling project folders — one of which has held a live
PORTAL_SECRET in a PHP file.

A mirror of the repo root would publish every one of those to a public web
server. So deployment is an ALLOWLIST, never a mirror: a file reaches the
server because it is named in PUBLISH below, and for no other reason.

Two guards, because an allowlist fails in both directions:

  * Anything index.html / styles.css / script.js references that is NOT in the
    allowlist fails the run. That is the "I added a photo and forgot to list
    it" case, which would otherwise ship a page with a broken image.
  * Anything in the allowlist that does not exist on disk fails the run.

Run:  python3 scripts/stage-site.py [--out _site] [--check-only]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The complete published surface of albaloostudio.com. Adding a page or an
# asset means adding it here — that is the point, not an inconvenience.
PUBLISH: list[str] = [
    # documents
    "index.html",
    # styling and behaviour
    "styles.css",
    "script.js",
    # SEO / crawler files (added 2026-08-09)
    ".htaccess",
    "sitemap.xml",
    "robots.txt",
    # media the page actually uses. NOT the raw Midjourney exports sitting
    # beside them — "Davan_motion.Full_body_front-facing…mp4" and friends are
    # ~20MB of superseded originals that the site never references.
    "logo.png",
    "hero-video.mp4",
    "davan-portrait.png",
    "davan-motion.mp4",
    "davan-card-motion.mp4",
    "roxana-portrait.png",
    "roxana-motion.mp4",
]

# Never publishable, whatever else happens. Belt and braces against someone
# later adding a directory to PUBLISH and sweeping these in with it.
FORBIDDEN_PARTS = {
    "orchestrator", "docs", "scripts", ".github", ".claude", ".git",
    "boutimar", "boutimar-com", "boutimar-ir", "boutimar-partner",
    "boutimar-group", "boutimar-mice", "boutimar-site", "boutixcruises",
    "cruisebaz-seo", "cruiseshop-cruises", "res-portal",
}
FORBIDDEN_NAMES = {
    "CLAUDE.md", "AGENTS.md", "README.md", ".gitignore", ".DS_Store",
    ".env", "package.json",
}

# Files whose references we validate.
SOURCES = ("index.html", "styles.css", "script.js")

_REF = re.compile(
    r"""src=["']([^"']+)["']|href=["']([^"']+)["']"""
    r"""|poster=["']([^"']+)["']|url\(\s*['"]?([^)'"]+)['"]?\s*\)"""
)


def referenced_assets() -> set[str]:
    """Every local path the site's own source asks the browser to fetch."""
    blob = ""
    for name in SOURCES:
        p = ROOT / name
        if p.exists():
            blob += p.read_text(encoding="utf-8", errors="replace")

    out: set[str] = set()
    for m in _REF.finditer(blob):
        raw = next((g for g in m.groups() if g), "").strip()
        if not raw:
            continue
        # `url(%23noise)` is an SVG filter reference — a percent-encoded "#",
        # not a file. Decode before testing for a fragment, or the check
        # demands you ship a file called "%23noise".
        raw = raw.replace("%23", "#")
        if raw.startswith(("http://", "https://", "//", "#",
                           "mailto:", "tel:", "data:", "javascript:")):
            continue
        out.add(raw.split("?")[0].split("#")[0].lstrip("./"))
    return out


def check() -> list[str]:
    """Return a list of problems. Empty means safe to deploy."""
    problems: list[str] = []
    allow = set(PUBLISH)

    for rel in PUBLISH:
        p = ROOT / rel
        if not p.exists():
            problems.append(f"listed in PUBLISH but missing on disk: {rel}")
        elif p.is_dir():
            problems.append(f"PUBLISH must name files, not directories: {rel}")

        parts = set(Path(rel).parts)
        if parts & FORBIDDEN_PARTS:
            problems.append(f"PUBLISH names a forbidden path: {rel}")
        if Path(rel).name in FORBIDDEN_NAMES:
            problems.append(f"PUBLISH names a never-publish file: {rel}")

    for ref in sorted(referenced_assets()):
        if ref not in allow:
            problems.append(
                f"the site references {ref!r} but it is not in PUBLISH — "
                "add it, or the deployed page will 404 on that asset"
            )
    return problems


def stage(out_dir: Path) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    total = 0
    for rel in PUBLISH:
        src = ROOT / rel
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        total += src.stat().st_size
        print(f"  {src.stat().st_size:>12,}B  {rel}")

    staged = sorted(p.relative_to(out_dir).as_posix()
                    for p in out_dir.rglob("*") if p.is_file())
    if staged != sorted(PUBLISH):
        print("staged tree does not match PUBLISH exactly", file=sys.stderr)
        return 1

    print(f"  {total:>12,}B  TOTAL — {len(PUBLISH)} files staged in {out_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="_site")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    problems = check()
    if problems:
        print("REFUSING TO STAGE:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"{len(PUBLISH)} files pass the publish check.")
    if args.check_only:
        return 0
    return stage(ROOT / args.out)


if __name__ == "__main__":
    sys.exit(main())
