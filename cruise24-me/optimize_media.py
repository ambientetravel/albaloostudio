#!/usr/bin/env python3
"""
optimize_media.py — make the downloaded media web-sized, in place.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Why
---
Explora's CDN serves print-sized masters: a 51 MB JPEG, 4K destination loops
at 26 MB for eleven seconds, a 377 MB three-minute film behind a hover card.
A page cannot ship that, and the claude.ai preview refuses any file over 15 MB.

What it does
------------
* Moves each original once into media-originals/ (gitignored, never
  published) and writes the web version back to media/ under the SAME name,
  so media/index.json and the pages need no change. Re-running starts again
  from the originals, so settings can be tuned and re-applied.
* Photos: longest edge capped (see IMAGE_MAX), EXIF orientation applied, JPEG
  q80 progressive, WebP q80. Format and extension are kept.
* Videos: H.264, yuv420p, faststart, NO audio (every <video> on the site is
  muted). Width, length and quality depend on the role the clip plays, read
  from which attribute and which page element uses it (see VIDEO_ROLES).

Needs Pillow and an ffmpeg binary:  pip install pillow imageio-ffmpeg

Usage
-----
    python3 optimize_media.py            # everything not yet optimised
    python3 optimize_media.py --force    # redo all from media-originals/
    python3 optimize_media.py --report   # sizes only, change nothing
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEDIA, ORIG = HERE / "media", HERE / "media-originals"
IMAGE_MAX = 2000              # px, longest edge; full-bleed at 1440 css px x ~1.4
LIMIT = 15 * 1024 * 1024      # claude.ai artifact per-file cap

# role -> (max width, max seconds or None, crf)
VIDEO_ROLES = {
    "hero":   (1920, None, 26),   # full-screen, always playing: keep the whole loop
    "panel":  (1920, 14,   28),   # full-screen sticky panels, stacked film
    "hover":  (1280, 12,   28),   # destination cards, plays on hover at ~600 css px
    "mobile": (1080, None, 28),   # data-media-mobile hero
}


def role_of(filename: str, pages: list[str]) -> str:
    """Classify a video by how the pages use its URL."""
    index = json.loads((MEDIA / "index.json").read_text(encoding="utf-8"))
    url = next((u for u, p in index.items() if p.endswith(filename)), "")
    html = "\n".join(pages)
    if f'data-media-mobile="{url}"' in html:
        return "mobile"
    if 'class="hero-video"' in html and f'data-media="{url}"' in html.split('class="hero-video"', 1)[1][:600]:
        return "hero"
    i = html.find(f'data-media="{url}"')
    before = html[max(0, i - 400):i]
    if 'class="dest"' in before or 'class="region-media"' in before or "<video data-media" in html[i - 7:i + 1]:
        return "hover"
    return "panel"


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        exe = shutil.which("ffmpeg")
        if not exe:
            sys.exit("needs ffmpeg: pip install imageio-ffmpeg")
        return exe


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return str(n)


def do_image(src: Path, dst: Path) -> None:
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src))
    im.thumbnail((IMAGE_MAX, IMAGE_MAX), Image.LANCZOS)
    if dst.suffix.lower() == ".webp":
        im.save(dst, "WEBP", quality=80, method=6)
    elif dst.suffix.lower() == ".png":
        im.save(dst, "PNG", optimize=True)
    else:
        im.convert("RGB").save(dst, "JPEG", quality=80, optimize=True, progressive=True)


def do_video(src: Path, dst: Path, role: str, ff: str) -> None:
    width, secs, crf = VIDEO_ROLES[role]
    for attempt in range(4):  # raise crf until it fits under the artifact cap
        cmd = [ff, "-y", "-v", "error", "-i", str(src)]
        if secs:
            cmd += ["-t", str(secs)]
        cmd += ["-an", "-vf", f"scale='min({width},iw)':-2", "-c:v", "libx264", "-preset", "slow",
                "-crf", str(crf + 2 * attempt), "-pix_fmt", "yuv420p", "-profile:v", "high",
                "-movflags", "+faststart", str(dst)]
        subprocess.run(cmd, check=True)
        if dst.stat().st_size <= LIMIT * 0.9:
            return
    raise RuntimeError(f"{dst.name} still {human(dst.stat().st_size)} after raising crf")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    ORIG.mkdir(exist_ok=True)
    pages = [p.read_text(encoding="utf-8") for p in HERE.glob("*.html") if not p.name.startswith("_")]
    files = sorted(p for p in MEDIA.iterdir() if p.is_file() and p.suffix.lower() in
                   (".jpg", ".jpeg", ".png", ".webp", ".mp4"))
    ff = None if args.report else ffmpeg()
    before = after = 0
    for f in files:
        orig = ORIG / f.name
        if args.report:
            o = orig.stat().st_size if orig.exists() else f.stat().st_size
            print(f"{human(o):>9} -> {human(f.stat().st_size):>9}  {f.name}")
            before += o; after += f.stat().st_size
            continue
        if not orig.exists():
            shutil.move(str(f), orig)          # first run: keep the master
        elif not args.force and f.exists() and f.stat().st_mtime >= orig.stat().st_mtime and f.stat().st_size < orig.stat().st_size:
            before += orig.stat().st_size; after += f.stat().st_size
            continue                           # already optimised
        tmp = f.with_name(f.stem + ".tmp" + f.suffix)
        if f.suffix.lower() == ".mp4":
            role = role_of(f.name, pages)
            do_video(orig, tmp, role, ff)
            label = role
        else:
            do_image(orig, tmp)
            label = "image"
        if tmp.stat().st_size >= orig.stat().st_size and f.suffix.lower() != ".mp4":
            shutil.copy2(orig, tmp)            # already small: keep the master
        tmp.replace(f)
        before += orig.stat().st_size; after += f.stat().st_size
        print(f"{label:>6}  {human(orig.stat().st_size):>9} -> {human(f.stat().st_size):>9}  {f.name}")
    over = [f.name for f in files if (MEDIA / f.name).stat().st_size > LIMIT]
    print(f"\n{len(files)} files: {human(before)} -> {human(after)}"
          + (f"\nOVER 15 MB: {over}" if over else "\nevery file is under the 15 MB artifact cap"))
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
