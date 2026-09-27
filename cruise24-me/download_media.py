#!/usr/bin/env python3
"""
download_media.py — pull every photo and video index.html references into media/
and write media/index.json, which the page's resolver uses to swap remote URLs
for local files.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Why
---
index.html carries its imagery as data-media / data-media-mobile / data-poster
attributes pointing at explorajourneys.com. Left like that the live site would
hot-link a cruise line's CDN: slow, fragile (they rename paths), and their
analytics sees every visitor. This script copies each asset once, names it
predictably, and records the URL → local path map the page reads at load.

Nothing is invented: only URLs already present in the HTML are fetched, and a
URL that fails is left OUT of index.json so the page falls back to the original
remote URL rather than to a broken local path.

Usage
-----
    python3 download_media.py                # fetch everything missing
    python3 download_media.py --no-videos    # images only (fast first pass)
    python3 download_media.py --force        # re-fetch even if the file exists
    python3 download_media.py --dry-run      # list what would be fetched
    python3 download_media.py --check        # verify index.json covers the HTML
                                             # and every listed file exists on disk

Exit status: 0 when every URL is local, 1 when any is missing or failed.
Stdlib only — runs on a stock macOS / Linux python3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATTRS = ("data-media", "data-media-mobile", "data-poster")
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
CT_EXT = {  # Content-Type → extension, for URLs with no usable suffix
    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/avif": ".avif", "image/gif": ".gif",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
}


def urls_in(html: str) -> list[str]:
    """Every distinct media URL in the page, in document order."""
    seen: dict[str, None] = {}
    for attr in ATTRS:
        for m in re.finditer(rf'{attr}="([^"]+)"', html):
            u = m.group(1).strip()
            if u.startswith(("http://", "https://")):
                seen.setdefault(u, None)
    return list(seen)


def local_name(url: str, content_type: str | None = None) -> str:
    """Stable, readable filename: <8-char hash>-<basename>.<ext>.

    The hash prefix makes two different URLs with the same basename
    (Explora reuses 'Thumbnail-Vertical.jpg' across destinations) coexist,
    and keeps the name stable across runs so index.json does not churn.
    """
    path = urllib.parse.urlparse(url).path
    base = Path(urllib.parse.unquote(path)).name or "asset"
    stem, ext = Path(base).stem, Path(base).suffix.lower()
    if ext not in VIDEO_EXT and ext not in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"):
        # e.g. dm.explorajourneys.com/is/image/ExploraProd/EXIII_01_Clean has no suffix,
        # and '.../img.jpg.transform/1300x900/img.jpg' resolves to img.jpg (fine).
        stem = base if not ext else stem
        ext = CT_EXT.get((content_type or "").split(";")[0].strip().lower(), ext or ".bin")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")[:60] or "asset"
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f"{h}-{stem}{ext}"


def sniff_ext(head: bytes) -> str:
    """Extension from magic bytes, for servers that send application/octet-stream."""
    if head.startswith(b"\x89PNG"): return ".png"
    if head.startswith(b"\xff\xd8\xff"): return ".jpg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP": return ".webp"
    if head[:3] == b"GIF": return ".gif"
    if head[4:8] == b"ftyp": return ".mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3": return ".webm"
    return ".bin"


def is_video(url: str) -> bool:
    return Path(urllib.parse.urlparse(url).path).suffix.lower() in VIDEO_EXT


def fetch(url: str, dest_dir: Path, timeout: int, retries: int = 3) -> tuple[Path, int]:
    """Stream url to dest_dir. Returns (path, bytes). Raises on final failure."""
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                ct = r.headers.get("Content-Type", "")
                name = local_name(url, ct)
                tmp = dest_dir / (name + ".part")
                n = 0
                with tmp.open("wb") as f:
                    while True:
                        chunk = r.read(1 << 16)
                        if not chunk:
                            break
                        f.write(chunk)
                        n += len(chunk)
                if n == 0:
                    raise IOError("empty body")
                if name.endswith(".bin"):  # no usable suffix or Content-Type: sniff the bytes
                    with tmp.open("rb") as f:
                        head = f.read(16)
                    name = name[:-4] + sniff_ext(head)
                final = dest_dir / name
                tmp.replace(final)
                return final, n
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, IOError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code in (403, 404, 410):
                break  # not going to change on retry
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{type(last).__name__}: {last}")


def existing_for(url: str, dest_dir: Path) -> Path | None:
    """A previously downloaded file for this URL, whatever extension it got."""
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    for p in dest_dir.glob(f"{h}-*"):
        if p.suffix != ".part" and p.stat().st_size > 0:
            return p
    return None


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--html", default=str(HERE / "index.html"))
    ap.add_argument("--out", default=str(HERE / "media"))
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    ap.add_argument("--no-videos", action="store_true", help="skip .mp4/.webm — images only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="verify only; download nothing")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    html_path, out = Path(args.html), Path(args.out)
    html = html_path.read_text(encoding="utf-8")
    urls = urls_in(html)
    if not urls:
        print(f"no {'/'.join(ATTRS)} URLs found in {html_path}", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    index_path = out / "index.json"
    index: dict[str, str] = {}
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    rel = lambda p: str(p.relative_to(html_path.parent)).replace("\\", "/")  # noqa: E731

    if args.check:
        missing = [u for u in urls if u not in index]
        gone = [u for u, p in index.items() if not (html_path.parent / p).is_file()]
        stale = [u for u in index if u not in urls]
        print(f"{len(urls)} URLs in {html_path.name}; {len(index)} entries in {index_path.name}")
        for u in missing: print(f"  NOT LOCAL   {u}")
        for u in gone:    print(f"  FILE GONE   {index[u]}  ({u})")
        for u in stale:   print(f"  stale entry {index[u]}  (URL no longer in page)")
        ok = not missing and not gone
        print("OK — every URL in the page resolves to a local file" if ok else "FAIL")
        return 0 if ok else 1

    todo, skipped = [], 0
    for u in urls:
        if args.no_videos and is_video(u):
            continue
        have = None if args.force else existing_for(u, out)
        if have:
            index[u] = rel(have)
            skipped += 1
        else:
            todo.append(u)

    print(f"{len(urls)} URLs in page · {skipped} already local · {len(todo)} to fetch"
          + (" (videos skipped)" if args.no_videos else ""))
    if args.dry_run:
        for u in todo: print("  would fetch", u)
        return 0

    total, failed = 0, []
    for i, u in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {u}")
        try:
            p, n = fetch(u, out, args.timeout)
            index[u] = rel(p)
            total += n
            print(f"          → {p.name}  {human(n)}")
        except Exception as e:  # keep going; report at the end
            failed.append((u, str(e)))
            print(f"          FAILED  {e}")

    # write only successes; a failed URL stays remote in the page
    index = {u: p for u, p in index.items() if (html_path.parent / p).is_file()}
    index_path.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    on_disk = sum((html_path.parent / p).stat().st_size for p in index.values())
    print(f"\nfetched {human(total)} this run · {len(index)} files, {human(on_disk)} in {out.name}/ · wrote {rel(index_path)}")
    if failed:
        print(f"\n{len(failed)} FAILED (left remote in the page):")
        for u, e in failed: print(f"  {u}\n      {e}")
    not_local = [u for u in urls if u not in index]
    if not_local and not failed:
        print(f"\n{len(not_local)} URL(s) still remote (skipped): run again without --no-videos")
    return 1 if (failed or not_local) else 0


if __name__ == "__main__":
    sys.exit(main())
