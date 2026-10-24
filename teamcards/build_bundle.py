#!/usr/bin/env python3
"""Build dist/teamcards-<date>.zip — paths relative to the docroot it is extracted into.

Allowlist, not a mirror: config.php, the database, uploads, docs and tools/ never ship.
See orchestrator/DEPLOY-BUNDLES.md for why there is no public_html/ prefix.
"""
import datetime, pathlib, zipfile

HERE = pathlib.Path(__file__).resolve().parent
PUBLISH = [
    ".htaccess", "index.php", "lib.php", "card.php", "vcf.php", "export.php", "wallet.php",
    "config.sample.php", "assets/app.css", "assets/app.js", "assets/qrcode.js",
    "data/.htaccess", "data/index.php", "uploads/.htaccess",
]

def main() -> None:
    missing = [p for p in PUBLISH if not (HERE / p).is_file()]
    if missing:
        raise SystemExit(f"missing from disk: {missing}")
    out = HERE / "dist" / f"teamcards-{datetime.date.today():%Y-%m-%d}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in PUBLISH:
            z.write(HERE / p, p)
    names = zipfile.ZipFile(out).namelist()
    bad = [n for n in names if n.startswith(("public_html/", "/", "../")) or n.endswith(("config.php", ".sqlite"))]
    if bad:
        raise SystemExit(f"REBUILD IT: {bad}")
    print(f"{out.relative_to(HERE)}  {out.stat().st_size:,} bytes  {len(names)} files, docroot-relative")

if __name__ == "__main__":
    main()
