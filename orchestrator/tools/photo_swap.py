#!/usr/bin/env python3
"""
Photo-swap adapters: a photo the team chose (or removed) in the Albaloo Ops app goes
into the article itself, on its draft, before anyone publishes it.

Architecture credit: Albaloo Studio — albaloostudio.com. Spec: OPS-APP.md.

ops_sync.relay_photo_requests() records each request on the draft and hands it here.
One adapter per way the sites store a lead photo (sites.yml → cms.images):

  astro_pr     boutimar.com, exploreorient.com   front-matter field (image / heroImage)
               + file in public/img/journal + the "*Photo: …*" credit line
               (boutimar.com also puts the photo inline above the text)
  json         boutimar.ir (boutimarfarsi)       articles.json item.image + img/daryanameh
               file + the {"p": "عکس: …"} credit block
  bundle       cruise24.ir                       content/blog/<dir>/hero.<ext> +
               manifest.json hero_image {src, credit, licence, source_page, alt}
  base44       cruisebaz.com                     Article image_url / image_credit /
               image_source, the photo re-hosted in the app's own storage (visitors
               in Iran often cannot reach upload.wikimedia.org)

Rules that never bend:
  * the credit is the photo's real one — Commons metadata for a Commons file, or the
    credit + licence + rights confirmation the team entered; ops_sync refuses the
    request before it reaches here otherwise
  * only an open draft is changed (PR head branch, or a base44 draft record); a merged
    or closed PR is left alone and reported
  * a removal deletes the file, the field and the credit line — exploreorient's
    heroImage is nullish and boutimar.com's image is not templated, so the page builds

    python3 tools/photo_swap.py --pid exploreorient#22 --url <url> --credit … --licence …   # dry run
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion_review_sync as nrs  # noqa: E402

REPO_SITE = {"boutimar": "boutimar.com", "exploreorient": "exploreorient.com",
             "boutimarfarsi": "boutimar.ir", "cruise24-ir": "cruise24.ir"}
CREDIT_LINE = re.compile(r"^\s*\*?\s*(Photo:|عکس:).*$", re.M)
IMG_RE = re.compile(r"\.(jpe?g|png|webp)$", re.I)
MAX_BYTES = 4_000_000


# ── the photo ────────────────────────────────────────────────────────────────
def credit_text(req: dict, fa: bool) -> str:
    """The caption: Commons' own credit line for a Commons file, else the team's."""
    if req.get("commons"):
        import images
        return images.credit_line(req["commons"], "fa" if fa else "en")
    if fa:
        return f"عکس: {req['credit']} — {req['licence']}"
    return f"Photo: {req['credit']}, {req['licence']}"


def download(url: str) -> tuple[bytes, str]:
    """(bytes, ext). Refuses anything that is not a JPEG/PNG of a sane size."""
    import config
    r = requests.get(url, timeout=30, headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
    ext = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png"}.get(ctype)
    if not ext:
        raise ValueError(f"not a JPEG or PNG ({ctype or 'no content-type'})")
    if not r.content or len(r.content) > MAX_BYTES:
        raise ValueError(f"photo is {len(r.content)} bytes (limit {MAX_BYTES})")
    return r.content, ext


# ── GitHub helpers ───────────────────────────────────────────────────────────
def _get(repo: str, path: str, ref: str) -> tuple[bytes, str] | None:
    code, d = nrs.gh("GET", f"/repos/{repo}/contents/{path}?ref={ref}")
    if code != 200 or not isinstance(d, dict):
        return None
    return base64.b64decode(d.get("content") or ""), d["sha"]


def _put(repo: str, path: str, branch: str, data: bytes, sha: str | None, msg: str) -> None:
    body = {"message": msg[:72], "branch": branch, "content": base64.b64encode(data).decode()}
    if sha:
        body["sha"] = sha
    code, d = nrs.gh("PUT", f"/repos/{repo}/contents/{path}", body)
    if code not in (200, 201):
        raise RuntimeError(f"commit refused for {path} ({code}): {str(d)[:160]}")


def _delete(repo: str, path: str, branch: str, sha: str, msg: str) -> None:
    code, d = nrs.gh("DELETE", f"/repos/{repo}/contents/{path}", {"message": msg[:72], "branch": branch, "sha": sha})
    if code not in (200, 204):
        raise RuntimeError(f"delete refused for {path} ({code}): {str(d)[:160]}")


def _site_images(domain: str) -> dict:
    import yaml
    for s in (yaml.safe_load((ROOT / "sites.yml").read_text(encoding="utf-8")) or {}).get("sites") or []:
        if s.get("domain") == domain:
            return ((s.get("cms") or {}).get("images")) or {}
    return {}


# ── pure edits (tested without any network) ──────────────────────────────────
def edit_markdown(text: str, field: str, old_public: str, new_public: str, credit: str,
                  inline: bool, alt: str) -> str:
    """Front matter `field`, the inline photo (boutimar.com) and the credit line.
    new_public "" removes all three."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fm, body = (m.group(1), text[m.end():]) if m else ("", text)
    lines = [ln for ln in fm.split("\n") if not re.match(rf"^{re.escape(field)}\s*:", ln)] if fm else []
    if new_public:
        lines.append(f"{field}: {json.dumps(new_public)}")
    if old_public:
        body = re.sub(rf"!\[[^\]]*\]\({re.escape(old_public)}\)\n?", "", body)
    body = CREDIT_LINE.sub("", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip("\n")
    if new_public:
        if inline:
            body = f"![{alt}]({new_public})\n*{credit}*\n\n{body}"
        else:
            body = f"{body}\n\n*{credit}*"
    head = "---\n" + "\n".join(ln for ln in lines if ln.strip()) + "\n---\n" if (fm or new_public) else ""
    return head + body + "\n"


def edit_json_item(item: dict, new_path: str, credit: str) -> dict:
    """boutimar.ir: item.image + the 'عکس:' credit block at the end of item.body."""
    out = dict(item)
    out["image"] = new_path
    blocks = [b for b in (out.get("body") or [])
              if not (isinstance(b, dict) and str(b.get("p", "")).startswith(("عکس:", "Photo:")))]
    if new_path:
        blocks.append({"p": credit})
    out["body"] = blocks
    return out


def edit_manifest(manifest: dict, src: str, req: dict, alt: str) -> dict:
    """cruise24.ir: manifest.hero_image, or no hero_image at all on removal."""
    out = dict(manifest)
    if not src:
        out.pop("hero_image", None)
        return out
    c = req.get("commons") or {}
    out["hero_image"] = {"src": src, "credit": c.get("creator") or req["credit"],
                         "licence": c.get("licence") or req["licence"],
                         "source_page": c.get("source_page") or req.get("url", ""), "alt": alt}
    return out


# ── adapters ─────────────────────────────────────────────────────────────────
def swap_pr(pid: str, req: dict, apply: bool) -> str:
    repo_name, num = pid.split("#")
    repo, p = nrs.pr_state(pid)
    if not p or p.get("state") != "open":
        raise RuntimeError("the PR is not open (merged or closed) — nothing changed")
    branch, sha = p["head"]["ref"], p["head"]["sha"]
    domain = REPO_SITE.get(repo_name, "")
    cfg = _site_images(domain)
    fa = domain.endswith(".ir")
    code, files = nrs.gh("GET", f"/repos/{repo}/pulls/{num}/files?per_page=100")
    names = [f["filename"] for f in files if f.get("status") != "removed"] if isinstance(files, list) else []
    old_img = next((n for n in names if IMG_RE.search(n)), "")
    removing = req.get("removed")
    data, ext = (b"", "") if removing else download(req["download_url"])
    alt = req.get("alt") or req.get("title") or ""
    credit = "" if removing else credit_text(req, fa)
    msg = f"Photo {'removed' if removing else 'changed'} in Albaloo Ops ({req.get('by') or 'team'})"
    steps: list[str] = []

    def write_image(path: str) -> None:
        old = _get(repo, path, sha)
        steps.append(f"write {path} ({len(data)} B)")
        if apply:
            _put(repo, path, branch, data, old[1] if old else None, msg)

    def drop_old(keep: str = "") -> None:
        if old_img and old_img != keep:
            got = _get(repo, old_img, sha)
            steps.append(f"delete {old_img}")
            if apply and got:
                _delete(repo, old_img, branch, got[1], msg)

    if repo_name in ("boutimar", "exploreorient"):                     # astro_pr
        md = next((n for n in names if n.endswith((".md", ".mdx")) and "content/" in n), "")
        if not md:
            raise RuntimeError("no article file in the PR")
        text_b, md_sha = _get(repo, md, sha) or (b"", "")
        slug = Path(md).stem
        new_path = "" if removing else (old_img.rsplit(".", 1)[0] + ext if old_img else
                                        f"{cfg.get('dir', 'public/img/journal').rstrip('/')}/{slug}{ext}")
        public = lambda path: f"{cfg.get('url_prefix', '/img/journal').rstrip('/')}/{Path(path).name}" if path else ""  # noqa: E731
        new_text = edit_markdown(text_b.decode("utf-8"), cfg.get("field", "image"), public(old_img), public(new_path),
                                 credit, bool(cfg.get("inline")), alt)
        if new_path:
            write_image(new_path)
        drop_old(keep=new_path)
        steps.append(f"edit {md}")
        if apply:
            _put(repo, md, branch, new_text.encode("utf-8"), md_sha, msg)
    elif repo_name == "boutimarfarsi":                                     # json
        jf = next((n for n in names if n.endswith("articles.json")), "")
        if not jf:
            raise RuntimeError("no articles.json in the PR")
        raw, jsha = _get(repo, jf, sha) or (b"", "")
        doc = json.loads(raw.decode("utf-8"))
        lst = doc if isinstance(doc, list) else next(v for v in doc.values() if isinstance(v, list))
        base = _get(repo, jf, p["base"]["ref"])
        bdoc = json.loads(base[0].decode("utf-8")) if base else []
        blst = bdoc if isinstance(bdoc, list) else next((v for v in bdoc.values() if isinstance(v, list)), [])
        have = {a.get("slug") for a in blst}
        idx = next((i for i, a in enumerate(lst) if a.get("slug") not in have), None)
        if idx is None:
            raise RuntimeError("no new article in articles.json")
        slug = lst[idx].get("slug") or "article"
        new_path = "" if removing else (old_img.rsplit(".", 1)[0] + ext if old_img else
                                        f"{cfg.get('dir', 'img/daryanameh').rstrip('/')}/{slug}{ext}")
        lst[idx] = edit_json_item(lst[idx], new_path, credit)
        if new_path:
            write_image(new_path)
        drop_old(keep=new_path)
        steps.append(f"edit {jf} (item {slug})")
        if apply:
            _put(repo, jf, branch, (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), jsha, msg)
    elif repo_name == "cruise24-ir":                                       # bundle
        mf = next((n for n in names if n.endswith("manifest.json")), "")
        if not mf:
            raise RuntimeError("no manifest.json in the PR")
        raw, msha = _get(repo, mf, sha) or (b"", "")
        manifest = json.loads(raw.decode("utf-8"))
        folder = mf.rsplit("/", 1)[0]
        new_path = "" if removing else f"{folder}/hero{ext}"
        manifest = edit_manifest(manifest, Path(new_path).name if new_path else "", req, alt)
        if new_path:
            write_image(new_path)
        drop_old(keep=new_path)
        steps.append(f"edit {mf}")
        if apply:
            _put(repo, mf, branch, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), msha, msg)
    else:
        raise RuntimeError(f"no photo adapter for {repo_name}")
    return "; ".join(steps)


def swap_base44(pid: str, req: dict, apply: bool) -> str:
    """cruisebaz.com: the draft Article record. A published record is never touched."""
    found = nrs.base44_record(pid)
    if not found:
        raise RuntimeError("base44 draft record not found")
    app, rec = found
    if str(rec.get("status") or "").lower() in ("published", "live"):
        raise RuntimeError("the base44 article is already published — nothing changed")
    if req.get("removed"):
        fields = {"image_url": "", "image_credit": "", "image_source": ""}
    else:
        data, ext = download(req["download_url"])
        fields = {"image_credit": credit_text(req, True),
                  "image_source": (req.get("commons") or {}).get("source_page") or req.get("url", "")}
        if apply:
            import config
            up = requests.post(f"https://app.base44.com/api/files/apps/{app}/upload",
                               headers={"Authorization": f"Bearer {os.environ.get('BASE44_ACCESS_TOKEN', '')}",
                                        "User-Agent": config.USER_AGENT},
                               files={"file": (f"{pid.split('/', 1)[-1].strip('/') or 'article'}{ext}", data,
                                               "image/jpeg" if ext == ".jpg" else "image/png")},
                               data={"visibility": "public"}, timeout=60)
            up.raise_for_status()
            import agent2_writer_listener as a2
            hosted = a2.base44_public_image_url(up.json() or {}, app)
            if not hosted:
                raise RuntimeError("base44 stored the photo but no public URL serves it")
            fields["image_url"] = hosted
    if apply:
        code, d = nrs.b44("PUT", f"/{app}/entities/Article/{rec['id']}", fields)
        if code != 200:
            raise RuntimeError(f"base44 {code}: {str(d)[:160]}")
    return f"base44 Article {rec.get('id')}: " + ", ".join(sorted(fields))


def swap(pid: str, req: dict, apply: bool) -> str:
    return swap_pr(pid, req, apply) if "#" in pid else swap_base44(pid, req, apply)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pid", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--credit", default="")
    ap.add_argument("--licence", default="")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    req = {"removed": a.remove, "download_url": a.url, "url": a.url, "credit": a.credit, "licence": a.licence}
    print(swap(a.pid, req, a.apply) + ("" if a.apply else "  (dry run)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
