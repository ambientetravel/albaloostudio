"""
Cuts a mounted-unit sprite into rig parts.

Not a general tool: it knows that these sprites are a rider on a horse facing
right, drawn to a common template, and it splits on that knowledge. Four parts
is what reads at the size these are drawn — 22 to 85 pixels tall. Articulating
individual leg joints below that is work nobody can see.

  tail        the hair hanging behind, which should stream
  legs-hind   drive
  legs-front  reach
  body        horse barrel, neck, head AND the rider, kept together because the
              rider's legs straddle the barrel and no clean seam exists

Each part keeps the FULL canvas, so every piece shares one origin and a pivot is
just a coordinate. Wasteful in texture memory and worth it in not having to
track four different offsets.
"""
import sys
from PIL import Image

# The one constant: every one of these was drawn to a 256-tall template with
# the belly line in the same place. Everything else is derived per sprite,
# because the horses sit at different x in frames 168 to 260 wide and fixed
# seams put three quarters of one horse's hind legs in the front group.
LEG_TOP = 198
TAIL_TOP = 118


def _columns(px, w: int, y0: int, y1: int) -> list[bool]:
    """Which columns carry any pixel in the band."""
    return [any(px[x, y][3] > 40 for y in range(y0, y1)) for x in range(w)]


def _runs(cols: list[bool], min_gap: int = 3) -> list[tuple[int, int]]:
    """Contiguous runs of occupied columns, merging gaps thinner than min_gap."""
    out: list[list[int]] = []
    for x, on in enumerate(cols):
        if not on:
            continue
        if out and x - out[-1][1] <= min_gap:
            out[-1][1] = x
        else:
            out.append([x, x])
    return [(a, b) for a, b in out]


def cut(path: str, out_dir: str) -> None:
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    px = im.load()

    """
    Below the belly line a horse is two clusters of legs with daylight between
    them, plus — on some of these — a narrow flake where the tail hangs past the
    seam. Taking the two WIDEST clusters gets the legs and ignores the flake;
    taking the widest gap did not, and put three quarters of one horse's hind
    legs in the front group.
    """
    runs = _runs(_columns(px, w, LEG_TOP, h))
    legs = sorted(sorted(runs, key=lambda r: r[1] - r[0])[-2:])
    if len(legs) == 2:
        (hind0, hind1), (fore0, _) = legs
        front_x = (hind1 + fore0) // 2 + 1
        tail_x = hind0            # anything behind the hind legs is tail
    else:
        xs = [x for r in runs for x in r]
        front_x = (min(xs) + max(xs)) // 2 if xs else w // 2
        tail_x = 0

    parts = {k: Image.new('RGBA', (w, h), (0, 0, 0, 0)) for k in
             ('body', 'legs-front', 'legs-hind', 'tail')}
    out = {k: v.load() for k, v in parts.items()}

    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if p[3] == 0:
                continue
            # Tail first: its tip hangs BELOW the leg seam, and classified as a
            # hind leg it swung with the gait — a stray flake of hair pivoting
            # off the hock.
            if x < tail_x and y >= TAIL_TOP:
                key = 'tail'
            elif y >= LEG_TOP:
                key = 'legs-front' if x >= front_x else 'legs-hind'
            else:
                key = 'body'
            out[key][x, y] = p

    print(f'  seams: legs split at x={front_x}, tail left of x={tail_x}')
    for name, img in parts.items():
        img.save(f'{out_dir}/{name}.png')
        bbox = img.getbbox()
        print(f'  {name:11s} bbox={bbox}')


if __name__ == '__main__':
    cut(sys.argv[1], sys.argv[2])
