"""
Cuts a foot-soldier sprite into rig parts.

Three parts, not four: a man is a torso and two legs. There is no tail, and the
weapon arm stays on the torso because an arm overlaps the body with no seam a
column scan can find — the same reason the horse's rider was never cut off the
horse.

  leg-rear    the trailing leg (lower x; these all face right)
  leg-lead    the leading leg
  body        everything above the hip, plus both arms and the weapon

NOT every foot unit can be rigged, and that is a fact about the art rather than
a limitation of the tool:

  * the Immortal and the Apple-bearer wear floor-length court robes. There are
    no legs in the image to separate, and a man in a robe to the ankles does not
    show a stride anyway.
  * the Shield-bearer stands behind a wicker spara taller than he is, and the
    Bactrian archer's cloak closes the gap between his legs.

Those four keep the procedural march, which is the right answer for them.

Detection walks the hip line UP from the ankles and takes the highest line that
still yields two clusters which are (a) narrow enough to be legs rather than a
shield, (b) similar in width to each other, and (c) both standing on the ground.
Every one of those three conditions was added because leaving it out produced a
confident, wrong answer: without (a) the Shield-bearer's spara is a leg, without
(c) a spear butt is.

Usage:  python3 tools/rig/cut_foot.py <sprite.png> <out-dir> [unit-id]
"""
import json
import sys
from PIL import Image

MIN_LEG_RUN = 7          # narrower than this is a strap, not a limb
MAX_LEG_SHARE = 0.40     # of sprite width; wider is a shield
MIN_LEG_RATIO = 0.40     # legs are roughly alike; a leg and a shield are not
MIN_GAP = 4              # daylight between the legs
GROUND_BAND = 14         # a leg reaches the bottom of the frame
# The hip must sit high enough that there is a LEG below it and not just a boot.
#
# Several of these figures wear a tunic to the knee, and the highest line where
# two clusters separate is the ankle. A boot swinging about its own top is about
# two pixels of movement at display size and reads, when it reads at all, as a
# shoe coming off. Requiring real leg drops half the roster and is still right.
MAX_HIP_SHARE = 0.78


def _runs(cols: list[bool], gap: int = 3) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for x, on in enumerate(cols):
        if not on:
            continue
        if out and x - out[-1][1] <= gap:
            out[-1][1] = x
        else:
            out.append([x, x])
    return [(a, b) for a, b in out]


def find_legs(px, w: int, h: int):
    """(hip, seam, [rear, lead]) or None if this figure has no separable legs."""
    def grounded(a: int, b: int) -> bool:
        return any(px[x, y][3] > 40 for x in range(a, b + 1) for y in range(h - GROUND_BAND, h))

    best = None
    for hip in range(h - 24, 148, -3):
        cols = [any(px[x, y][3] > 40 for y in range(hip, h)) for x in range(w)]
        runs = [c for c in _runs(cols) if c[1] - c[0] >= MIN_LEG_RUN]
        if len(runs) != 2:
            continue
        a, b = runs
        wa, wb = a[1] - a[0] + 1, b[1] - b[0] + 1
        if max(wa, wb) > w * MAX_LEG_SHARE:
            continue
        if min(wa, wb) / max(wa, wb) < MIN_LEG_RATIO:
            continue
        if b[0] - a[1] < MIN_GAP:
            continue
        if not (grounded(*a) and grounded(*b)):
            continue
        best = (hip, (a[1] + b[0]) // 2 + 1, runs)
    if best and best[0] > h * MAX_HIP_SHARE:
        return None
    return best


def _largest_blob(img: Image.Image) -> Image.Image:
    """
    Keeps only the biggest connected shape.

    Weapons reach below the hip: the Ethiopian bowman's bow tip and the Greek
    mercenary's spear butt both landed inside a leg and would have swung with
    it. Same failure `spriteprep.py` guards against, same fix.
    """
    w, h = img.size
    px = img.load()
    seen = [[False] * w for _ in range(h)]
    best: list[tuple[int, int]] = []
    for sy in range(h):
        for sx in range(w):
            if seen[sy][sx] or px[sx, sy][3] == 0:
                continue
            stack, blob = [(sx, sy)], []
            seen[sy][sx] = True
            while stack:
                x, y = stack.pop()
                blob.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and px[nx, ny][3] > 0:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if len(blob) > len(best):
                best = blob
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    op = out.load()
    for x, y in best:
        op[x, y] = px[x, y]
    return out


def cut(path: str, out_dir: str, unit_id: str) -> bool:
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    px = im.load()

    found = find_legs(px, w, h)
    if not found:
        print(f'  {unit_id}: no leg split — robe, shield or overlap. Stays a still sprite.')
        return False
    hip, seam, runs = found

    parts = {k: Image.new('RGBA', (w, h), (0, 0, 0, 0)) for k in ('body', 'leg-rear', 'leg-lead')}
    out = {k: v.load() for k, v in parts.items()}
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if p[3] == 0:
                continue
            if y >= hip:
                key = 'leg-lead' if x >= seam else 'leg-rear'
            else:
                key = 'body'
            out[key][x, y] = p

    # Legs keep only their largest blob; the body keeps everything, because a
    # body legitimately has a shield and a spear floating clear of the torso.
    for leg in ('leg-rear', 'leg-lead'):
        parts[leg] = _largest_blob(parts[leg])

    boxes = {}
    for name, img in parts.items():
        img.save(f'{out_dir}/{name}.png')
        boxes[name] = img.getbbox()

    # A leg swings from the hip: the middle of its own top edge. The body turns
    # about the same line, so torso and legs stay joined as it leans.
    def mid(box, fallback):
        return (box[0] + box[2]) // 2 if box else fallback

    rig = {
        'size': [w, h],
        'joints': {
            'leg-rear': {'pivot': [mid(boxes['leg-rear'], seam // 2), hip + 1], 'z': 0},
            'body': {'pivot': [mid(boxes['body'], w // 2), hip - 2], 'z': 1},
            'leg-lead': {'pivot': [mid(boxes['leg-lead'], seam), hip + 1], 'z': 2},
        },
    }
    with open(f'{out_dir}/rig.json', 'w') as fh:
        json.dump(rig, fh, indent=2)
    print(f'  {unit_id}: hip y={hip}, seam x={seam}, legs {runs}')
    return True


if __name__ == '__main__':
    src, dest = sys.argv[1], sys.argv[2]
    unit = sys.argv[3] if len(sys.argv) > 3 else src.split('/')[-1].replace('.png', '')
    sys.exit(0 if cut(src, dest, unit) else 1)
