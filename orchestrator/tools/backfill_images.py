#!/usr/bin/env python3
"""
Give every LIVE article that has no photo a real, freely licensed one — the same
Commons rules as new drafts (images.py): CC0/PD/CC BY/CC BY-SA only, a named
creator, the caption copied from the file's own metadata, self-hosted.

One pull request per site, on an agent2/ branch, so it appears on the Notion
Content Review board and Alireza approves the photos before anything goes live
(5 Oct 2026: "use pictures for all the journal articles, relevant pictures").

  boutimar.com      src/content/journal/*.md   → `image:` + lead photo + caption
  exploreorient.com src/content/blog/*.md      → `heroImage:` + caption
  boutimar.ir       data/articles.json         → `image` + Farsi caption paragraph

The search phrase is the article's own English title (EN sites) or an English
scene phrase from the LLM (Farsi titles do not search Commons well).

    python3 tools/backfill_images.py                # dry run: what each article would get
    python3 tools/backfill_images.py --apply        # commits + opens the PRs
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import images  # noqa: E402

DOMAIN = {"boutimar": "boutimar.com", "exploreorient": "exploreorient.com",
          "boutimarfarsi": "boutimar.ir", "cruise24-ir": "cruise24.ir"}


def image_cfg(repo: str) -> dict:
    """prefer/avoid from the site's cms.images in sites.yml — one list for the writer and here."""
    try:
        site = config.load_sites(only=[DOMAIN[repo.split("/")[1]]], include_hold=True)[0]
        cms = site.cms.model_dump() if hasattr(site.cms, "model_dump") else dict(site.cms or {})
        return cms.get("images") or {}
    except Exception:  # noqa: BLE001
        return {}

API = "https://api.github.com"
SITES = [
    {"repo": "ambientetravel/boutimar", "kind": "md", "dir": "src/content/journal", "field": "image",
     "img_dir": "public/img/journal", "prefix": "/img/journal", "inline": True, "lang": "en"},
    {"repo": "ambientetravel/exploreorient", "kind": "md", "dir": "src/content/blog", "field": "heroImage",
     "img_dir": "public/img/journal", "prefix": "/img/journal", "inline": False, "lang": "en"},
    {"repo": "ambientetravel/boutimarfarsi", "kind": "json", "path": "data/articles.json",
     "img_dir": "img/daryanameh", "lang": "fa"},
    {"repo": "ambientetravel/cruise24-ir", "kind": "bundle", "dir": "content/blog", "lang": "fa"},
]


def _hdr() -> dict:
    return {"Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
            "Accept": "application/vnd.github+json", "User-Agent": config.USER_AGENT}


def gh(method: str, path: str, **kw):
    return requests.request(method, API + path, headers=_hdr(), timeout=40, **kw)


def raw(repo: str, path: str, ref: str = "main") -> tuple[str, str]:
    r = gh("GET", f"/repos/{repo}/contents/{path}", params={"ref": ref})
    r.raise_for_status()
    d = r.json()
    return base64.b64decode(d["content"]).decode("utf-8"), d["sha"]


_FM = re.compile(r"^---\n(.*?)\n---\n", re.S)


def fm_value(text: str, key: str) -> str:
    m = _FM.match(text)
    v = re.search(rf"^{re.escape(key)}:\s*(.*)$", m.group(1), re.M) if m else None
    val = v.group(1).strip().strip("'\"") if v else ""
    return "" if val in ("null", "~") else val


def set_fm(text: str, key: str, value: str) -> str:
    m = _FM.match(text)
    block = m.group(1)
    line = f"{key}: {json.dumps(value, ensure_ascii=False)}"
    if re.search(rf"^{re.escape(key)}:", block, re.M):
        block = re.sub(rf"^{re.escape(key)}:.*$", line, block, count=1, flags=re.M)
    else:
        block += "\n" + line
    return f"---\n{block}\n---\n" + text[m.end():]


def query_for(title: str, summary: str = "", lang: str = "en", prefer=()) -> tuple[str, str]:
    """A precise English Commons search phrase that NAMES the place (Kyrgyzstan
    yurt camp, Mount Damavand). The title alone searched badly (5 Oct dry run)."""
    try:
        import llm
        out, _ = llm.complete_json(
            "You choose search phrases for finding a real photograph on Wikimedia Commons.",
            f"Article title: {title}\nSummary: {summary}\n\nReturn JSON {{\"q\": \"3-6 English words: "
            f"the specific named place, landmark, venue or ship plus what to see (e.g. 'Mount Damavand "
            f"summit', 'Kyrgyzstan yurt camp Song-Kol', 'Ait Benhaddou kasbah Morocco'). It MUST contain a "
            f"proper place name. If the article is about an event or business topic with no photographable "
            f"place, return the city or venue it happens in (e.g. 'Tehran International Exhibition Center')."
            + (f" For a cruise topic not about one named ship or port, name a ship of one of these lines: "
               f"{', '.join(prefer)} — never another cruise line's ship." if prefer else "")
            + f"\", "
            f"\"alt\": \"one short sentence in {'Farsi' if lang == 'fa' else 'English'} describing that scene\"}}.",
            {"type": "object", "additionalProperties": False,
             "properties": {"q": {"type": "string"}, "alt": {"type": "string"}}, "required": ["q", "alt"]},
            max_tokens=200, purpose="image query")
        return str(out.get("q", "")).strip(), str(out.get("alt", "")).strip()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! image query failed for {title[:50]!r}: {type(exc).__name__}: {str(exc)[:120]}")
        return "", ""


def plan(site: dict) -> list[dict]:
    todo = []
    if site["kind"] == "md":
        r = gh("GET", f"/repos/{site['repo']}/contents/{site['dir']}")
        r.raise_for_status()
        for f in r.json():
            if not f["name"].endswith(".md"):
                continue
            text, sha = raw(site["repo"], f"{site['dir']}/{f['name']}")
            if fm_value(text, site["field"]):
                continue
            todo.append({"file": f"{site['dir']}/{f['name']}", "slug": f["name"][:-3],
                         "title": fm_value(text, "title"), "text": text, "sha": sha,
                         "summary": fm_value(text, "summary") or fm_value(text, "description")})
    elif site["kind"] == "bundle":
        r = gh("GET", f"/repos/{site['repo']}/contents/{site['dir']}")
        r.raise_for_status()
        for d in r.json():
            if d["type"] != "dir":
                continue
            try:
                text, sha = raw(site["repo"], f"{site['dir']}/{d['name']}/manifest.json")
            except requests.HTTPError:
                continue
            man = json.loads(text)
            if man.get("hero_image"):
                continue
            todo.append({"dir": f"{site['dir']}/{d['name']}", "slug": d["name"], "title": man.get("title", ""),
                         "summary": man.get("meta_description", ""), "manifest": man, "sha": sha})
    else:
        text, sha = raw(site["repo"], site["path"])
        store = json.loads(text)
        for a in store.get("articles", []):
            if not a.get("image"):
                todo.append({"slug": a["slug"], "title": a.get("title", ""), "article": a,
                             "summary": a.get("dek", "")})
    return todo


def run(apply: bool, only: list[str] | None = None) -> list[str]:
    log = []
    # Minute stamp: a second run the same day must not collide with an open branch
    # (a PUT onto an existing file without its sha fails).
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    for site in SITES:
        # Exact repo name: a substring test made `--only boutimar` also run boutimarfarsi.
        if only and site["repo"].split("/")[1] not in only:
            continue
        todo = plan(site)
        cfg = image_cfg(site["repo"])
        found, used = [], set()
        for t in todo:
            q, _ = query_for(t["title"], t.get("summary", ""), site["lang"], cfg.get("prefer") or ())
            img = images.find_image(q, avoid=cfg.get("avoid") or (), exclude=used,
                                    context=t["title"]) if q else None
            if img:
                used.add(img["source_page"])
                # Alt from the CHOSEN file's own record, not from the article's wish.
                img["alt"] = images.describe(img, site["lang"])
                t["alt"] = img["alt"]
            log.append(f"{site['repo'].split('/')[1]:14} {t['slug'][:48]:48} q={q!r} → "
                       + (f"{img['title'][:40]} ({img['creator'][:25]}, {img['licence']}) alt={img['alt'][:60]!r}"
                          if img else "no acceptable photo"))
            if img:
                found.append((t, img))
        if not apply or not found:
            continue
        repo, branch = site["repo"], f"agent2/photos-{stamp}"
        base_sha = gh("GET", f"/repos/{repo}/git/ref/heads/main").json()["object"]["sha"]
        rb = gh("POST", f"/repos/{repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": base_sha})
        if rb.status_code not in (201, 422):
            rb.raise_for_status()
        store = store_sha = None
        if site["kind"] == "json":
            text, store_sha = raw(repo, site["path"], branch)
            store = json.loads(text)
        done = 0
        for t, img in found:
            data = images.fetch(img)
            if not data:
                continue
            path = (f"{t['dir']}/hero{img['ext']}" if site["kind"] == "bundle"
                    else f"{site['img_dir']}/{t['slug']}{img['ext']}")
            gh("PUT", f"/repos/{repo}/contents/{path}", json={
                "message": f"photo for {t['slug']} ({img['licence']}, {img['creator']})"[:72],
                "content": base64.b64encode(data).decode(), "branch": branch}).raise_for_status()
            credit = images.credit_line(img, site["lang"])
            if site["kind"] == "bundle":
                man, msha = raw(repo, f"{t['dir']}/manifest.json", branch)
                man = json.loads(man)
                man["hero_image"] = {"src": f"hero{img['ext']}", "credit": img["creator"], "licence": img["licence"],
                                     "source_page": img["source_page"],
                                     "alt": images.clean(t.get("alt") or t["title"], 160)}
                gh("PUT", f"/repos/{repo}/contents/{t['dir']}/manifest.json", json={
                    "message": f"hero photo: {t['slug']}"[:72], "branch": branch, "sha": msha,
                    "content": base64.b64encode(json.dumps(man, ensure_ascii=False, indent=2).encode("utf-8")).decode()
                }).raise_for_status()
            elif site["kind"] == "md":
                public = f"{site['prefix']}/{t['slug']}{img['ext']}"
                text, sha = raw(repo, t["file"], branch)
                new = set_fm(text, site["field"], public)
                head, body = new[:_FM.match(new).end()], new[_FM.match(new).end():]
                body = (f"\n![{img['alt'] or img['title']}]({public})\n*{credit}*\n" + body) if site["inline"] \
                    else body.rstrip() + f"\n\n*{credit}*\n"
                gh("PUT", f"/repos/{repo}/contents/{t['file']}", json={
                    "message": f"photo: {t['slug']}"[:72], "branch": branch, "sha": sha,
                    "content": base64.b64encode((head + body).encode("utf-8")).decode()}).raise_for_status()
            else:
                for a in store["articles"]:
                    if a.get("slug") == t["slug"]:
                        a["image"] = path
                        a["body"] = list(a.get("body") or []) + [{"p": credit}]
            done += 1
        if site["kind"] == "json" and done:
            gh("PUT", f"/repos/{repo}/contents/{site['path']}", json={
                "message": f"photos for {done} article(s)", "branch": branch, "sha": store_sha,
                "content": base64.b64encode(json.dumps(store, ensure_ascii=False, indent=2).encode("utf-8")).decode()
            }).raise_for_status()
        if done:
            rp = gh("POST", f"/repos/{repo}/pulls", json={
                "title": f"Agent 2 draft: photos for {done} article(s)", "head": branch, "base": "main",
                "body": ("Real, freely licensed photos (Wikimedia Commons: CC0 / public domain / CC BY / "
                         "CC BY-SA, named creator) for live articles that had none. Each caption is copied "
                         "from the file's own licence record. Files are self-hosted in this repo.\n\n"
                         "Review on the Notion Content Review board; Approved merges and deploys.")})
            log.append(f"  PR {repo}: {rp.status_code} {rp.json().get('html_url', rp.text[:120])}")
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", action="append", help="repo name filter, e.g. cruise24-ir")
    a = ap.parse_args(argv)
    print("\n".join(run(a.apply, a.only)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
