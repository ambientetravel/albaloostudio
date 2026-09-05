"""
Cuts a mounted-unit sprite into rig parts.

Not a general tool: it knows these sprites are a rider on a horse facing right,
drawn to a common 256-tall template, and it splits on that knowledge. Four parts
is what reads at the size they are drawn — 22 to 85 pixels tall. Articulating
individual leg joints below that is work nobody can see.

  tail        the hair behind, which should stream
  legs-hind   drive
  legs-front  reach
  body        horse barrel, neck, head AND the rider, kept together because the
              rider's legs straddle the barrel and no clean seam exists

Each part keeps the FULL canvas, so every piece shares one origin and a pivot is
just a coordinate. Wasteful in texture memory, worth it in not tracking four
different offsets.

Usage:  python3 tools/rig/cut_horse.py <sprite.png> <out-dir> [unit-id]
"""
import json
import sys
from PIL import Image

# The one constant: these were all drawn to a template with the belly in the
# same place. Below this line the sprite is legs and nothing else.
LEG_TOP = 198
TAIL_TOP = 118

# How much of the leg mass a seam must leave on each side to be believed.
MIN_SHARE = 0.25

# Tail seams, by unit, set BY EYE against a ruler.
#
# There is no automatic answer here and pretending otherwise produced the worst
# bug in this tool: every one of these sprites has the tail touching the
# hindquarters, so the mid-band is one solid run of columns with no gap to find,
# and the "gap" the finder settled on was inside the horse. Armenian Lancer came
# out with a hindquarter classified as tail — which then swung.
#
# Values are deliberately CONSERVATIVE. Cutting short leaves a little tail in
# the body, where it simply does not move; cutting long takes a piece of horse
# and waves it about. Only one of those is recoverable by looking.
#
# A unit absent from this table keeps its tail in the body, which is a fine
# outcome: a tail swings 0.3 radians at 40px and is close to invisible, while a
# detached rump is not.
TAIL_X = {
    'persian-cavalry': 37,
    'saka-horse-archer': 24,
    'armenian-lancer': 20,
    'chorasmian-rider': 22,
    'sagartian-lassoer': 20,
}


def _columns(px, w: int, y0: int, y1: int) -> list[bool]:
    """Which columns carry any pixel in the band."""
    return [any(px[x, y][3] > 40 for y in range(y0, y1)) for x in range(w)]


def _runs(cols: list[bool], gap: int = 3) -> list[tuple[int, int]]:
    """Contiguous runs of occupied columns, merging gaps thinner than `gap`."""
    out: list[list[int]] = []
    for x, on in enumerate(cols):
        if not on:
            continue
        if out and x - out[-1][1] <= gap:
            out[-1][1] = x
        else:
            out.append([x, x])
    return [(a, b) for a, b in out]


def leg_seam(cols: list[bool]) -> int:
    """
    Where the hind legs end and the forelegs begin.

    The widest gap between leg clusters — but only among gaps that leave a real
    share of the legs on BOTH sides. That qualifier is the whole trick. Every
    one of these sprites has a stray flake at the far left (a tail tip hanging
    past the belly line), and the raw widest gap is the one just right of that
    flake, which puts the entire horse in the front group. Taking the two widest
    CLUSTERS instead fails differently, on the sprites that show four separate
    legs rather than two pairs.
    """
    runs = _runs(cols)
    if len(runs) < 2:
        xs = [x for r in runs for x in r]
        return (min(xs) + max(xs)) // 2 if xs else len(cols) // 2

    total = sum(b - a + 1 for a, b in runs)
    best, best_width = None, -1
    left = 0
    for i in range(len(runs) - 1):
        left += runs[i][1] - runs[i][0] + 1
        share = left / total
        if share < MIN_SHARE or 1 - share < MIN_SHARE:
            continue
        width = runs[i + 1][0] - runs[i][1]
        if width > best_width:
            best, best_width = (runs[i][1] + runs[i + 1][0]) // 2 + 1, width
    if best is not None:
        return best
    # Nothing balanced enough: split at the middle of the mass.
    xs = [x for r in runs for x in r]
    return (min(xs) + max(xs)) // 2


def cut(path: str, out_dir: str, unit_id: str) -> None:
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    px = im.load()

    front_x = leg_seam(_columns(px, w, LEG_TOP, h))
    tail_x = TAIL_X.get(unit_id, 0)

    parts = {k: Image.new('RGBA', (w, h), (0, 0, 0, 0))
             for k in ('body', 'legs-front', 'legs-hind', 'tail')}
    out = {k: v.load() for k, v in parts.items()}

    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if p[3] == 0:
                continue
            # Tail first: its tip hangs BELOW the leg seam, and classified as a
            # hind leg it swung with the gait — a flake of hair pivoting off the
            # hock.
            if x < tail_x and y >= TAIL_TOP:
                key = 'tail'
            elif y >= LEG_TOP:
                key = 'legs-front' if x >= front_x else 'legs-hind'
            else:
                key = 'body'
            out[key][x, y] = p

    print(f'  seams: legs split at x={front_x}, tail left of x={tail_x}')
    boxes = {}
    for name, img in parts.items():
        img.save(f'{out_dir}/{name}.png')
        boxes[name] = img.getbbox()
        print(f'  {name:11s} bbox={boxes[name]}')

    # Pivots, written out beside the parts.
    #
    # These CANNOT be one shared constant: the five sprites are 168 to 260
    # pixels wide and the horses sit at different x within them, so a pivot
    # measured on one puts another's hind legs on its shoulder. Each is derived
    # from the part it actually turns — a leg swings from the middle of its own
    # top edge, the tail from its dock, the body about the hip.
    def mid(box, default_x):
        return (box[0] + box[2]) // 2 if box else default_x

    rig = {
        'size': [w, h],
        'joints': {
            'tail': {'pivot': [tail_x, TAIL_TOP + 14], 'z': 0},
            'legs-hind': {'pivot': [mid(boxes['legs-hind'], front_x // 2), LEG_TOP + 2], 'z': 1},
            'body': {'pivot': [mid(boxes['body'], w // 2), LEG_TOP - 3], 'z': 2},
            'legs-front': {'pivot': [mid(boxes['legs-front'], front_x), LEG_TOP + 2], 'z': 3},
        },
    }
    with open(f'{out_dir}/rig.json', 'w') as fh:
        json.dump(rig, fh, indent=2)
    print(f'  pivots: ' + ', '.join(f"{k}={v['pivot']}" for k, v in rig['joints'].items()))


if __name__ == '__main__':
    src, dest = sys.argv[1], sys.argv[2]
    unit = sys.argv[3] if len(sys.argv) > 3 else src.split('/')[-1].replace('.png', '')
    cut(src, dest, unit)
