#!/usr/bin/env python3
"""
spriteprep — turn a generated character image into a game sprite.

The generators hand back a figure on a flat grey card, with a drop shadow, a
watermark, and whatever aspect ratio they felt like. The game needs a tight
transparent cut-out, and it needs every unit to be the same apparent size so a
spearman does not tower over an archer.

    python3 tools/spriteprep.py <in.png> <id> [--kind unit|card] [--height 256]
    python3 tools/spriteprep.py --contact [--kind unit|card]   # legibility sheet

`unit` art is a character sprite for the battlefield; `card` art is the emblem on
an Upgrade or Doctrine card, which must never contain a figure — a unit and a
trait are different kinds of thing and the art has to say so.

What it does, and why:

  1. Flood-fills the background from the corners. The generated figures carry a
     bright cream rim light all the way round, which is a gift — the fill stops
     exactly on the figure's edge.
  2. Eats the drop shadow. It touches the boots, so it survives step 3 — it IS
     part of the figure's shape. It is separated instead by being grey where the
     figure is brown, flooded from outside so enclosed greys (the spearhead, the
     scale armour) are never reached.
  3. Keeps only the largest connected shape, which removes the corner watermark
     and anything else the flood left floating.
  3. Crops to the content and normalises HEIGHT. Framing is then the tool's
     problem rather than the prompt's, so a badly-framed generation still lands
     at the right size instead of being regenerated.

Output: src/assets/units/<unit-id>.png — inside src rather than public, so Vite
hashes it and a stale sprite can never be served from a cache. Tight-cropped,
bottom-anchored by the renderer.
"""
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIRS = {
    'unit': ROOT / 'src' / 'assets' / 'units',
    'card': ROOT / 'src' / 'assets' / 'cards',
}
WORK_HEIGHT = 1024
"""Sprites are drawn at ~85 CSS px on the battlefield; 256 leaves real headroom
on a 3x screen without shipping megabytes."""
DEFAULT_HEIGHT = 256
"""How close a pixel must be to the corner colour to count as background."""
TOLERANCE = 26


def flood_background(img: Image.Image) -> Image.Image:
    """Make the flat card transparent, working in from all four corners."""
    img = img.convert('RGBA')
    w, h = img.size
    # A sentinel no illustration will contain, so the fill is unambiguous.
    KEY = (255, 0, 255, 255)
    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        if img.getpixel(corner)[:3] == KEY[:3]:
            continue
        ImageDraw.floodfill(img, corner, KEY, thresh=TOLERANCE)

    px = img.load()
    for y in range(h):
        for x in range(w):
            if px[x, y][:3] == KEY[:3]:
                px[x, y] = (0, 0, 0, 0)
    return img


def eat_shadow(img: Image.Image) -> Image.Image:
    """
    Remove the drop shadow the generators paint under the figure.

    The shadow touches the boots, so it survives "keep the largest shape" — it
    IS part of the largest shape. But it is grey (saturation under about 0.1)
    where the figure is brown (0.24 and up), and it is mid-toned where the ink
    outline is nearly black.

    This has to be a FLOOD from the outside rather than a colour filter over the
    whole image: the spearhead and the scale armour are grey too, and a global
    filter would delete them. They are enclosed by the outline, so a flood
    cannot reach them.
    """
    w, h = img.size
    px = img.load()
    seen = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()

    def greyish(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        if a == 0:
            return False
        hi, lo = max(r, g, b), min(r, g, b)
        sat = 0.0 if hi == 0 else (hi - lo) / hi
        lum = (r + g + b) / 765
        # Grey, and not the near-black outline.
        return sat < 0.16 and 0.18 < lum < 0.92

    # Seed from every transparent pixel touching the frame edge.
    for x in range(w):
        for y in (0, h - 1):
            if px[x, y][3] == 0 and not seen[y * w + x]:
                seen[y * w + x] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if px[x, y][3] == 0 and not seen[y * w + x]:
                seen[y * w + x] = 1
                q.append((x, y))

    eaten = 0
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < w and 0 <= ny < h) or seen[ny * w + nx]:
                continue
            if px[nx, ny][3] == 0:
                seen[ny * w + nx] = 1
                q.append((nx, ny))
            elif greyish(nx, ny):
                seen[ny * w + nx] = 1
                px[nx, ny] = (0, 0, 0, 0)
                eaten += 1
                q.append((nx, ny))
    if eaten:
        print(f'      removed {eaten} shadow px')
    return img


def keep_largest_shape(img: Image.Image) -> Image.Image:
    """
    Drop everything that is not the figure.

    The flood fill cannot reach inside the drop shadow or the watermark, so both
    survive as islands. The figure is always the largest one.
    """
    w, h = img.size
    px = img.load()
    seen = bytearray(w * h)
    best: list[tuple[int, int]] = []

    for sy in range(h):
        for sx in range(w):
            if seen[sy * w + sx] or px[sx, sy][3] == 0:
                continue
            shape: list[tuple[int, int]] = []
            q = deque([(sx, sy)])
            seen[sy * w + sx] = 1
            while q:
                x, y = q.popleft()
                shape.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and px[nx, ny][3] > 0:
                        seen[ny * w + nx] = 1
                        q.append((nx, ny))
            if len(shape) > len(best):
                best = shape

    keep = set(best)
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 0 and (x, y) not in keep:
                px[x, y] = (0, 0, 0, 0)
    return img


def prepare(src: Path, art_id: str, kind: str = 'unit', height: int = DEFAULT_HEIGHT) -> Path:
    img = Image.open(src).convert('RGBA')
    # Work small: the component sweep is the slow part and the output is 256px.
    if img.height > WORK_HEIGHT:
        img = img.resize(
            (round(img.width * WORK_HEIGHT / img.height), WORK_HEIGHT), Image.LANCZOS
        )

    img = flood_background(img)
    img = eat_shadow(img)
    img = keep_largest_shape(img)

    box = img.getbbox()
    if not box:
        raise SystemExit(f'{src.name}: nothing left after cut-out — is the background flat?')
    img = img.crop(box)

    # Normalise on HEIGHT so every unit reads at the same scale in the ledger.
    img = img.resize((max(1, round(img.width * height / img.height)), height), Image.LANCZOS)

    out_dir = OUT_DIRS[kind]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{art_id}.png'
    img.save(out)
    print(f'  {kind:5} {art_id:22} {img.width}x{img.height}  ← {src.name}')
    return out


def contact_sheet(kind: str = 'unit') -> None:
    """
    The legibility test, run for real rather than eyeballed.

    Every prepared sprite at the four sizes the game actually draws it. If two
    units are indistinguishable in the 22px column, the art has failed the only
    constraint that matters, however good it looks large.
    """
    # Cards are never drawn on the battlefield, so they are tested at the sizes
    # a card actually uses rather than at the unit sizes.
    sizes = [22, 26, 44, 85] if kind == 'unit' else [24, 28, 40, 64]
    sprites = sorted(OUT_DIRS[kind].glob('*.png'))
    if not sprites:
        raise SystemExit(f'no {kind} art in {OUT_DIRS[kind]} — prepare some first')

    pad, label_w = 14, 150
    row_h = max(sizes) + pad
    sheet = Image.new('RGBA', (label_w + sum(sizes) + pad * len(sizes), row_h * len(sprites) + pad),
                      (38, 32, 24, 255))
    draw = ImageDraw.Draw(sheet)

    for row, path in enumerate(sprites):
        art = Image.open(path).convert('RGBA')
        y0 = pad + row * row_h
        draw.text((8, y0 + row_h // 2 - 6), path.stem, fill=(220, 200, 160, 255))
        x = label_w
        for s in sizes:
            small = art.resize((max(1, round(art.width * s / art.height)), s), Image.LANCZOS)
            sheet.alpha_composite(small, (x, y0 + (max(sizes) - s)))
            x += s + pad

    out = ROOT / 'art-in' / f'legibility-{kind}.png'
    sheet.save(out)
    print(f'contact sheet → {out}  ({len(sprites)} sprites at {sizes})')


if __name__ == '__main__':
    args = sys.argv[1:]
    kind = args[args.index('--kind') + 1] if '--kind' in args else 'unit'
    if kind not in OUT_DIRS:
        raise SystemExit(f'--kind must be one of {sorted(OUT_DIRS)}')
    if args and args[0] == '--contact':
        contact_sheet(kind)
    elif len(args) >= 2:
        h = int(args[args.index('--height') + 1]) if '--height' in args else DEFAULT_HEIGHT
        prepare(Path(args[0]), args[1], kind, h)
    else:
        print(__doc__)
        raise SystemExit(2)
