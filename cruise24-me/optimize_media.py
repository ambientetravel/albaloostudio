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
IMAGE_MAX = 1600              # px, longest edge (30 Sep: 2000 made pages crawl on shared hosting)
QUALITY = 76                  # JPEG/WebP quality; 76 is not visibly different from 80 at these sizes
LIMIT = 15 * 1024 * 1024      # claude.ai artifact per-file cap

# role -> (max width, max seconds or None, crf)
VIDEO_ROLES = {
    "hero":   (1600, None, 28),   # full-screen, always playing: keep the whole loop
    "panel":  (1280, 12,   30),   # sticky panels, stacked film: loaded only when scrolled to
    "hover":  (960,  8,    30),   # destination cards, plays on hover at ~600 css px
    "mobile": (720,  None, 30),   # data-media-mobile hero
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
        im.save(dst, "WEBP", quality=QUALITY, method=6)
    elif dst.suffix.lower() == ".png":
        im.save(dst, "PNG", optimize=True)
    else:
        im.convert("RGB").save(dst, "JPEG", quality=QUALITY, optimize=True, progressive=True)


def do_video(src: Path, dst: Path, role: str, ff: str) -> None:
    width, secs, crf = VIDEO_ROLES[role]
    for attempt in range(4):  # raise crf until it fits under the artifact cap
        cmd = [ff, "-y", "-v", "error", "-i", str(src)]
        if secs:
            cmd += ["-t", str(secs)]
        cmd += ["-an", "-vf", f"fps=30,scale='min({width},iw)':-2", "-c:v", "libx264", "-preset", "slow",
                "-crf", str(crf + 2 * attempt), "-pix_fmt", "yuv420p", "-profile:v", "high",
                "-movflags", "+faststart", str(dst)]
        subprocess.run(cmd, check=True)
        if dst.stat().st_size <= LIMIT * 0.9:
            return
    raise RuntimeError(f"{dst.name} still {human(dst.stat().st_size)} after raising crf")


# The home hero opens on the balcony shot, which starts 6.34 s into Explora's film (cut found
# with ffmpeg scene detection, 29 Sep). Rebuilt from the masters so it is never re-encoded twice.
HERO_CUT = 6.36
HEROES = {"hero-balcony-1920.mp4": ("2752c37b-Hero-video.mp4", 1600, 28),
          "hero-balcony-1080sq.mp4": ("1d6fe463-Cover-video.mp4", 720, 30)}


def make_hero(ff: str) -> None:
    for out, (master, width, crf) in HEROES.items():
        src = ORIG / master
        if not src.exists():
            print(f"  hero master missing: {src}")
            continue
        dst = MEDIA / out
        subprocess.run([ff, "-v", "error", "-y", "-ss", str(HERO_CUT), "-i", str(src), "-an",
                        "-vf", f"fps=30,scale='min({width},iw)':-2", "-c:v", "libx264", "-preset", "slow",
                        "-crf", str(crf), "-pix_fmt", "yuv420p", "-profile:v", "high",
                        "-movflags", "+faststart", str(dst)], check=True)
        print(f"  hero  {human(dst.stat().st_size):>9}  {out}")
    poster = MEDIA / "hero-balcony-poster.jpg"
    subprocess.run([ff, "-v", "error", "-y", "-ss", "0.3", "-i", str(MEDIA / "hero-balcony-1920.mp4"),
                    "-frames:v", "1", "-q:v", "4", str(poster)], check=True)
    print(f"  hero  {human(poster.stat().st_size):>9}  {poster.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    ORIG.mkdir(exist_ok=True)
    pages = [p.read_text(encoding="utf-8") for p in HERE.glob("*.html") if not p.name.startswith("_")]
    files = sorted(p for p in MEDIA.rglob("*") if p.is_file() and p.suffix.lower() in
                   (".jpg", ".jpeg", ".png", ".webp", ".mp4") and not p.name.startswith("hero-balcony"))
    ff = None if args.report else ffmpeg()
    before = after = 0
    for f in files:
        orig = ORIG / f.relative_to(MEDIA)
        orig.parent.mkdir(parents=True, exist_ok=True)
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
    make_hero(ff) if not args.report else None
    over = [f.name for f in files if f.stat().st_size > LIMIT]
    print(f"\n{len(files)} files: {human(before)} -> {human(after)}"
          + (f"\nOVER 15 MB: {over}" if over else "\nevery file is under the 15 MB artifact cap"))
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
