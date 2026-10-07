#!/usr/bin/env python3
"""
deploy_update.py — ship only what changed, and know it shipped by reading it back live.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

The daily inventory sync (.github/workflows/cruise24-inventory-sync.yml) rebuilds the site.
This finds which built files are not yet what https://cruise24.me serves, and either packs
them for a manual upload or uploads them over SSH.

    python3 deploy_update.py            # dist/update-<date>.zip + .txt: files that differ from live
    python3 deploy_update.py --ssh      # ... and upload them, then read them back to confirm

"Live" is checked, not assumed (CLAUDE.md: never infer shipped from edited). deploy/live.sha256
records the hash of every file last seen live; a file whose built hash matches it is skipped,
anything else is fetched from cruise24.me and compared. So after a manual upload the next run
notices by itself, and the very first run reads the whole site once to fill the record.

Scope: what the build generates and the media it uses. Never .htaccess or PHP: Apache does
not serve those as files, so they cannot be read back, and they change by hand, not by a sync.

Sailing pages the build no longer makes (every departure sailed, or the line dropped it)
are MOVED on the server to ~/retired/<date>/, never deleted.

--ssh needs CRUISE24_SSH_KEY_FILE (a private key authorised in cPanel → SSH Access) and
reads CRUISE24_SSH_TARGET (default ekrd2r2976p9@92.205.251.216).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import io
import os
import shlex
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_bundle  # noqa: E402

SITE = os.environ.get("CRUISE24_SITE", "https://cruise24.me/")   # override only to test against a copy
MANIFEST = HERE / "deploy" / "live.sha256"
UA = "Mozilla/5.0 (compatible; deploy-check/1.0)"
DOCROOT = "public_html"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def in_scope(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return not name.startswith(".") and not rel.endswith(".php")


def load_manifest() -> dict[str, str]:
    if not MANIFEST.exists():
        return {}
    out = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        h, _, rel = line.partition("  ")
        if h and rel:
            out[rel] = h
    return out


def save_manifest(m: dict[str, str]) -> None:
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text("".join(f"{m[k]}  {k}\n" for k in sorted(m)), encoding="utf-8")


def live_hash(rel: str) -> str | None:
    """sha256 of the file as cruise24.me serves it; None when it is not there (or unreachable)."""
    url = SITE + urllib.parse.quote(rel)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return sha(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
    return None


def live_hashes(rels: list[str]) -> dict[str, str | None]:
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        return dict(zip(rels, ex.map(live_hash, rels)))


def ssh(target: str, key: str, command: str, stdin: bytes | None = None) -> None:
    subprocess.run(["ssh", "-i", key, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
                    "-o", "ConnectTimeout=20", target, command], input=stdin, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ssh", action="store_true", help="upload the changed files and confirm them live")
    args = ap.parse_args()
    today = dt.date.today().isoformat()

    every = build_bundle.deployable()
    files = [p for p in every if in_scope(p.relative_to(HERE).as_posix())]
    blockers, _ = build_bundle.check(every)
    if blockers:
        print("NOT shipping, the pre-launch check failed:\n  " + "\n  ".join(blockers))
        return 2
    local = {p.relative_to(HERE).as_posix(): sha(p.read_bytes()) for p in files}
    known = load_manifest()

    candidates = sorted(r for r, h in local.items() if known.get(r) != h)
    gone = sorted(r for r in known if r.startswith("journeys/") and r not in local)
    print(f"{len(local)} files in scope; {len(candidates)} differ from the last-known live copy; "
          f"{len(gone)} sailing pages no longer built")

    seen = live_hashes(candidates + gone)
    for r in candidates:
        if seen[r] == local[r]:
            known[r] = local[r]                      # already live (a manual upload, or first run)
    changed = [r for r in candidates if seen[r] != local[r]]
    retire = [r for r in gone if seen[r] is not None]
    for r in gone:
        if seen[r] is None:
            known.pop(r, None)                       # already off the server
    print(f"to ship: {len(changed)} files ({sum((HERE / r).stat().st_size for r in changed) / 1e6:.1f} MB); "
          f"to retire: {len(retire)} pages")

    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    if changed or retire:
        zpath = dist / f"update-{today}.zip"
        with zipfile.ZipFile(zpath, "w") as z:
            for r in changed:
                z.write(HERE / r, r, zipfile.ZIP_STORED if (HERE / r).suffix.lower() in build_bundle.STORED else zipfile.ZIP_DEFLATED)
        (dist / f"update-{today}.txt").write_text(
            f"Extract update-{today}.zip INTO public_html (it replaces {len(changed)} files).\n"
            + (f"\nThen move these {len(retire)} pages out of public_html (sailings that are over):\n"
               + "".join(f"  {r}\n" for r in retire) if retire else ""), encoding="utf-8")
        print(f"wrote {zpath.relative_to(HERE)}")

    if args.ssh and (changed or retire):
        key = os.environ.get("CRUISE24_SSH_KEY_FILE", "")
        target = os.environ.get("CRUISE24_SSH_TARGET", "ekrd2r2976p9@92.205.251.216")
        if not key:
            print("--ssh: CRUISE24_SSH_KEY_FILE is not set"); return 1
        if changed:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as t:
                for r in changed:
                    t.add(HERE / r, arcname=r)
            ssh(target, key, f"cd {DOCROOT} && tar xzf -", buf.getvalue())
        if retire:
            dest = f"retired/{today}"
            ssh(target, key, f"mkdir -p {dest}/journeys && cd {DOCROOT} && mv -f -- "
                + " ".join(shlex.quote(r) for r in retire) + f" ../{dest}/journeys/")
        after = live_hashes(changed + retire)
        ok = [r for r in changed if after[r] == local[r]]
        for r in ok:
            known[r] = local[r]
        for r in retire:
            if after[r] is None:
                known.pop(r, None)
        bad = [r for r in changed if r not in ok] + [r for r in retire if after[r] is not None]
        print(f"uploaded and read back: {len(ok)}/{len(changed)} files live, "
              f"{len(retire) - sum(1 for r in retire if after[r] is not None)}/{len(retire)} pages retired")
        save_manifest(known)
        if bad:
            print("NOT live after upload: " + ", ".join(bad[:10]))
            return 1
        return 0

    save_manifest(known)
    return 0


if __name__ == "__main__":
    sys.exit(main())
