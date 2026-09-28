#!/usr/bin/env python3
"""
Build the cruise24.me deploy bundle, after a pre-launch check.

    python3 build_bundle.py            # refuses while any blocker is open
    python3 build_bundle.py --draft    # builds anyway, named DRAFT-…, for a staging upload

Output (dist/, gitignored):
    cruise24-me-<date>-<sha>.zip     paths relative to the docroot: extract INTO
                                     public_html, never with a public_html/ prefix
                                     (orchestrator/DEPLOY-BUNDLES.md)
    cruise24-me-<date>-<sha>.sha256  one line per file, for diffing against the live server

Run build_journeys.py first if the inventory changed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import subprocess
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

HERE = Path(__file__).resolve().parent

# Never shipped. Mirrors "Do not deploy" in HANDOFF.md, plus the form's server-side state.
EXCLUDE_DIRS = {"data/sources", "sync", "media-originals", "social", "dist", "__pycache__"}
EXCLUDE_FILES = {"data/data-checks.json", "data/sailings.json", "_v1-illustrated.html",
                 "api/config.php", "api/config.sample.php", "media/.gitkeep"}
EXCLUDE_SUFFIX = {".py", ".md", ".pyc"}
STORED = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".woff2"}  # already compressed


def deployable() -> list[Path]:
    out = []
    for p in sorted(HERE.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(HERE).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in EXCLUDE_DIRS):
            continue
        if rel in EXCLUDE_FILES or p.suffix in EXCLUDE_SUFFIX:
            continue
        if rel.startswith("api/data/") and p.name != ".htaccess":
            continue  # stored requests stay on the server that received them
        out.append(p)
    return out


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.base, self.refs = None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "base" and a.get("href"):
            self.base = a["href"]
        for k in ("href", "src", "poster", "action"):
            if a.get(k):
                self.refs.append(a[k])


def check(files: list[Path]) -> tuple[list[str], list[str]]:
    blockers, warnings = [], []
    rels = {p.relative_to(HERE).as_posix() for p in files}
    html = [p for p in files if p.suffix == ".html"]

    todo, brackets, arabian, bare_gulf, broken = {}, {}, [], [], []
    for p in html:
        rel = p.relative_to(HERE).as_posix()
        s = p.read_text(encoding="utf-8")
        if (n := s.count('class="todo"')):
            todo[rel] = n
        if (m := re.findall(r"\[(?:PHONE|EMAIL|ADDRESS|[A-Z][A-Z ]{3,})\]", s)):
            brackets[rel] = sorted(set(m))
        if "Arabian Gulf" in s:
            arabian.append(rel)
        if re.search(r"(?:\bthe|/)\s*Gulf\b(?!\s+of)", re.sub(r"<[^>]+>", " ", s)):
            bare_gulf.append(rel)
        lk = Links()
        lk.feed(s)
        page_url = "https://cruise24.me/" + rel
        base = urljoin(page_url, lk.base) if lk.base else page_url
        for ref in lk.refs:
            if ref.startswith(("mailto:", "tel:", "data:", "#", "javascript:")):
                continue
            u = urlparse(urljoin(base, ref))
            if u.netloc != "cruise24.me":
                continue
            target = unquote(u.path.lstrip("/")) or "index.html"
            if target.endswith("/"):
                target += "index.html"
            if target not in rels:
                broken.append(f"{rel} → {ref}")

    if todo:
        blockers.append(f"{sum(todo.values())} highlighted gaps (class=\"todo\"): "
                        + ", ".join(f"{k} {v}" for k, v in todo.items()) + " (see HANDOFF-legal.md)")
    if brackets:
        blockers.append("bracket placeholders: " + "; ".join(f"{k} {v}" for k, v in brackets.items()))
    if arabian:
        blockers.append("'Arabian Gulf' on: " + ", ".join(arabian))
    if broken:
        blockers.append(f"{len(broken)} broken internal links, first: " + "; ".join(broken[:5]))
    if bare_gulf:
        warnings.append("a bare 'the Gulf' / '/ Gulf' (house rule: Persian Gulf) on: " + ", ".join(bare_gulf[:10]))

    sm = (HERE / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>https://cruise24\.me/([^<]*)</loc>", sm)
    missing = [l for l in locs if (l or "index.html") not in rels]
    if missing:
        blockers.append(f"sitemap lists {len(missing)} pages not in the bundle, first: {missing[:5]}")
    for must in ("api/enquiry.php", "api/leads.php", "api/data/.htaccess", "robots.txt",
                 "sitemap.xml", "data/journeys-index.json", "media/index.json"):
        if must not in rels:
            blockers.append(f"missing from bundle: {must}")

    warnings += [
        "manual: Explora 'used with permission' line, and rights for CruiseHost and line photos (HANDOFF.md §3)",
        "manual: 'Explora I in Port Hercule for the 2027 Grand Prix' and 'twelve years' (HANDOFF.md §4)",
        "server: create api/config.php from config.sample.php (signing_secret, ip_salt, notify_to)",
    ]
    return blockers, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true", help="build even with blockers open")
    args = ap.parse_args()

    files = deployable()
    blockers, warnings = check(files)
    print(f"{len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.1f} MB")
    for b in blockers:
        print("BLOCKER  " + b)
    for w in warnings:
        print("check    " + w)
    if blockers and not args.draft:
        print(f"\nNot built: {len(blockers)} blocker(s). Fix them, or use --draft for a staging upload.")
        return 1

    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE,
                         capture_output=True, text=True).stdout.strip() or "nogit"
    name = f"{'DRAFT-' if blockers else ''}cruise24-me-{dt.date.today():%Y%m%d}-{sha}"
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    zpath, mpath = dist / f"{name}.zip", dist / f"{name}.sha256"
    with zipfile.ZipFile(zpath, "w") as z, mpath.open("w") as m:
        for p in files:
            rel = p.relative_to(HERE).as_posix()
            assert not rel.startswith("public_html/")
            z.write(p, rel, zipfile.ZIP_STORED if p.suffix.lower() in STORED else zipfile.ZIP_DEFLATED)
            m.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}\n")
    print(f"\n{zpath.relative_to(HERE)}  {zpath.stat().st_size / 1e6:.1f} MB")
    print(f"{mpath.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
