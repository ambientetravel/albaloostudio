#!/usr/bin/env python3
"""Add JSON-LD to the hand-written pages (idempotent). Generated pages get theirs
from build_journeys.page(). Run: python3 inject_jsonld.py [--check]"""
import html, re, sys
from pathlib import Path
import jsonld

HERE = Path(__file__).resolve().parent
SKIP = {"index.html", "_v1-illustrated.html"}
LD = re.compile(r'<script type="application/ld\+json">.*?</script>\n?', re.S)


def main(check=False) -> int:
    todo = 0
    for p in sorted(HERE.glob("*.html")):
        if p.name in SKIP:
            continue
        s = p.read_text(encoding="utf-8")
        if 'data-page="journeys"' in s or "</head>" not in s:
            continue   # generated: build_journeys.page() owns these
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        d = re.search(r'<meta name="description" content="([^"]*)">', s)
        c = re.search(r'<link rel="canonical" href="([^"]*)">', s)
        if not (t and d and c):
            print("skip (no title/desc/canonical):", p.name); continue
        new = jsonld.block(p.name, html.unescape(t.group(1)), html.unescape(d.group(1)), c.group(1))
        out = LD.sub("", s).replace("</head>", new + "</head>", 1)
        if out != s:
            todo += 1
            if not check:
                p.write_text(out, encoding="utf-8")
            print(("would update " if check else "updated ") + p.name)
    print(f"{todo} page(s) {'differ' if check else 'changed'}")
    return 1 if (check and todo) else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
