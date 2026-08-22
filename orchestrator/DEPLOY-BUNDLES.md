# Deploy bundles: how to build one so it cannot land in the wrong place

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

## The mistake this exists to stop

A bundle was built with every entry prefixed `public_html/`:

    public_html/journal/index.html
    public_html/sitemap.xml

and shipped with the instruction "upload into `public_html` and extract it
there". DirectAdmin joins the destination with the paths inside the archive, so
that produces

    /domains/boutimar.com/public_html/public_html/journal/index.html

A nested tree. Nothing overwritten, the site unchanged, every verification step
failing — and the entire new build publicly fetchable at
`https://boutimar.com/public_html/…`, which is worse than the deploy simply not
happening.

It happened twice. The first bundle escaped only because that upload was
diverted for an unrelated reason. Both times the person at the panel caught it,
not the person who built the zip.

The prefix was there to SHOW A HUMAN the mapping. The instruction was written as
if the prefix were not there. Either alone is fine; together they are a trap.

## The rule

**Store paths relative to the directory the file will be extracted into.**

For a docroot deploy that means NO `public_html/` prefix:

    journal/index.html
    mice/fairs/iran-oil-show-2026/index.html
    sitemap.xml

Built from the directory whose contents map onto the target:

    cd dist && zip -q -r ../bundle.zip journal mice sitemap.xml llms.txt

Then the instruction is unambiguous and matches every other tool: stand in
`public_html`, extract, done. The destination you verify is the destination you
extract into, and there is no arithmetic to get right.

## Check before shipping any bundle

    python3 - <<'PY'
    import zipfile, sys
    z = zipfile.ZipFile(sys.argv[1] if len(sys.argv) > 1 else "bundle.zip")
    bad = [n for n in z.namelist() if n.startswith(("public_html/", "/", "../"))]
    print("REBUILD IT:" if bad else "paths are docroot-relative:", bad[:5] or "ok")
    PY

An entry starting with `public_html/`, `/` or `../` means the archive decides
where its own files go, which is exactly what a person standing in the right
directory is trying to control.

## And say which directory, every time

The instruction must name the full path and give a way to recognise it:

> Go to `/domains/boutimar.com/public_html`. Confirm the path bar reads that
> and the folder contains `_astro`, `journal`, `mice`, `index.html`. If you can
> see a `domains` folder you are at the account root — go deeper.

This account carries four sites under `/domains/<name>/public_html`. "public_html"
alone is not a location on it.
