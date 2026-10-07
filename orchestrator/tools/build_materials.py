#!/usr/bin/env python3
"""
Albaloo Materials Library — everything the pipeline has made, per property,
rebuilt from the LATEST agent outputs and the live repos.

The 14 Sep library was a one-off snapshot built by throwaway scripts, so it
froze: articles showed as "staged" after they had PRs, closed PRs still looked
pending, and nothing from later runs appeared. This rebuilds it from source
every time:

  * published articles — listed from each site's repo on `main` (what is merged)
  * every draft ever written — from all unexpired agent2-written artifacts,
    deduped to the newest per URL, with its CURRENT state read from GitHub
    (open PR / merged / merged-then-reverted / closed / staged)
  * this run's briefs and improvement opportunities — latest seo-scout-run
  * site audit, keyword & geo, competitors, social copy — latest artifacts
  * portfolio strategy + health

    python3 tools/build_materials.py          # writes _materials/INDEX.html

Auth: GITHUB_TOKEN, or the git credential for github.com. Read-only.
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

REPO = "ambientetravel/albaloostudio"
API = "https://api.github.com"
OUT = ROOT / "_materials" / "INDEX.html"
TEMPLATE = Path(__file__).with_name("materials_template.html")

# Where each site's PUBLISHED articles live on main, and how a file maps to a URL.
LIVE_SOURCES = {
    "boutimar.com": ("ambientetravel/boutimar", "src/content/journal", "md", "https://boutimar.com/journal/{name}/"),
    "exploreorient.com": ("ambientetravel/exploreorient", "src/content/blog", "md", "https://exploreorient.com/journal/{name}/"),
    "cruise24.ir": ("ambientetravel/cruise24-ir", "content/blog", "bundle", "https://cruise24.ir{path}"),
    "boutimar.ir": ("ambientetravel/boutimarfarsi", "data/articles.json", "json", "https://boutimar.ir/daryanameh/{slug}.html"),
}
ORDER = ["boutimar.com", "boutimar.ir", "cruise24.ir", "exploreorient.com", "cruisebaz.com",
         "ambientetravel.com", "cruise24.me", "albaloostudio.com"]
BLURB = {
    "boutimar.com": "Iran DMC · MICE · tours (EN)", "boutimar.ir": "Farsi cruise storefront + دریانامه",
    "cruise24.ir": "Farsi cruise storefront (blog under /blog/)", "exploreorient.com": "European brand · Silk Road, Caucasus, Middle East",
    "cruisebaz.com": "Farsi cruise site on base44", "ambientetravel.com": "Ambiente Travel on base44 (DACH)",
    "cruise24.me": "English cruise site (GoDaddy builder — no publish API)", "albaloostudio.com": "Studio site (one page)",
}


# ── GitHub ────────────────────────────────────────────────────────────────────
def _token() -> str:
    t = os.environ.get("GITHUB_TOKEN", "")
    if t:
        return t
    r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True)
    m = re.search(r"^password=(.+)$", r.stdout, re.M)
    return m.group(1) if m else ""


TOK = _token()


def _get(url: str, raw: bool = False, binary: bool = False):
    hdr = ["-H", f"Authorization: Bearer {TOK}", "-H",
           "Accept: application/vnd.github.raw" if raw else "Accept: application/vnd.github+json"]
    r = subprocess.run(["curl", "-sSL", "--max-time", "60", *hdr, "-w", "\n%{http_code}",
                        url if url.startswith("http") else API + url], capture_output=True)
    body, _, code = r.stdout.rpartition(b"\n")
    if int(code or 0) >= 400:
        return None
    if binary:
        return body
    txt = body.decode("utf-8", "replace")
    return txt if raw else json.loads(txt or "null")


def artifacts(name: str, n: int = 1) -> list[zipfile.ZipFile]:
    d = _get(f"/repos/{REPO}/actions/artifacts?name={name}&per_page=100") or {}
    out = []
    for a in [x for x in d.get("artifacts", []) if not x.get("expired")][:n]:
        b = _get(a["archive_download_url"], binary=True)
        if b:
            out.append(zipfile.ZipFile(io.BytesIO(b)))
    return out


def zjson(z: zipfile.ZipFile, pattern: str) -> list[tuple[str, object]]:
    return [(n, json.loads(z.read(n))) for n in z.namelist() if re.search(pattern, n)]


def ztext(z: zipfile.ZipFile, pattern: str) -> str:
    for n in sorted(z.namelist(), reverse=True):
        if re.search(pattern, n):
            return z.read(n).decode("utf-8", "replace")
    return ""


# ── tiny markdown → html (headings, lists, quotes, tables, code, bold, links) ─
def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r'<code class="mono">\1</code>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s


def md(text: str, shift: int = 2) -> str:
    out, para, lst, tbl, code = [], [], None, [], None

    def flush():
        nonlocal para, lst, tbl
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>"); para = []
        if lst:
            out.append(f"<{lst[0]}>" + "".join(f"<li>{_inline(i)}</li>" for i in lst[1]) + f"</{lst[0]}>"); lst = None
        if tbl:
            rows = [r for r in tbl if not re.match(r"^\|?\s*:?-{2,}", r)]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            if cells:
                h = "".join(f"<th>{_inline(c)}</th>" for c in cells[0])
                b = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
                out.append(f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>')
            tbl = []

    for line in (text or "").splitlines():
        if code is not None:
            if line.startswith("```"):
                out.append("<pre>" + html.escape("\n".join(code)) + "</pre>"); code = None
            else:
                code.append(line)
            continue
        if line.startswith("```"):
            flush(); code = []; continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush(); lvl = min(6, len(m.group(1)) + shift)
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>"); continue
        if line.strip().startswith("|"):
            if para or lst:
                flush()
            tbl.append(line); continue
        elif tbl:
            flush()
        m = re.match(r"^\s*([-*]|\d+\.)\s+(.*)", line)
        if m:
            kind = "ol" if m.group(1)[0].isdigit() else "ul"
            if para:
                flush()
            if not lst or lst[0] != kind:
                if lst:
                    flush()
                lst = (kind, [])
            lst[1].append(m.group(2)); continue
        if line.startswith(">"):
            flush(); out.append("<blockquote>" + _inline(line.lstrip("> ")) + "</blockquote>"); continue
        if re.match(r"^\s*(---|\*\*\*)\s*$", line):
            flush(); out.append("<hr>"); continue
        if not line.strip():
            flush(); continue
        if lst and line.startswith("  "):
            lst[1][-1] += " " + line.strip(); continue
        para.append(line.strip())
    flush()
    if code is not None:
        out.append("<pre>" + html.escape("\n".join(code)) + "</pre>")
    return "\n".join(out)


def section_of(report: str, domain: str) -> str:
    """The `## <domain>…` section of a per-domain markdown report."""
    m = re.search(rf"(?ms)^## {re.escape(domain)}\b.*?(?=^## |\Z)", report)
    return m.group(0) if m else ""


E = lambda s: html.escape(str(s or ""))  # noqa: E731
RTL = lambda s: bool(re.search(r"[؀-ۿ]", s or ""))  # noqa: E731


# ── gather ────────────────────────────────────────────────────────────────────
def live_articles(domain: str) -> list[tuple[str, str]]:
    src = LIVE_SOURCES.get(domain)
    if not src:
        return []
    repo, path, kind, url = src
    out = []
    if kind == "json":
        items = json.loads(_get(f"/repos/{repo}/contents/{path}?ref=main", raw=True) or "[]")
        for it in items if isinstance(items, list) else items.get("articles", []):
            out.append((it.get("title") or it.get("slug"), url.format(slug=it.get("slug", ""))))
        return out
    listing = _get(f"/repos/{repo}/contents/{path}?ref=main") or []
    for f in listing:
        if kind == "md" and f["name"].endswith((".md", ".mdx")):
            name = f["name"].rsplit(".", 1)[0]
            raw = _get(f"/repos/{repo}/contents/{f['path']}?ref=main", raw=True) or ""
            t = re.search(r'(?m)^title:\s*"?(.+?)"?\s*$', raw)
            out.append(((t.group(1) if t else name.replace("-", " ")), url.format(name=name)))
        elif kind == "bundle" and f["type"] == "dir":
            man = json.loads(_get(f"/repos/{repo}/contents/{f['path']}/manifest.json?ref=main", raw=True) or "{}")
            if man.get("target_url_path"):
                out.append((man.get("title") or f["name"], url.format(path=man["target_url_path"])))
    return sorted(out)


_PR_CACHE: dict[str, dict] = {}


def pr_state(pr_url: str) -> tuple[str, str]:
    """(css class, label) for a draft's PR, read live."""
    m = re.match(r"https://github.com/([^/]+/[^/]+)/pull/(\d+)", pr_url or "")
    if not m:
        return "draft", "staged, no PR"
    repo, num = m.groups()
    if pr_url not in _PR_CACHE:
        _PR_CACHE[pr_url] = _get(f"/repos/{repo}/pulls/{num}") or {}
    p = _PR_CACHE[pr_url]
    if p.get("merged_at"):
        files = _get(f"/repos/{repo}/pulls/{num}/files") or []
        added = [f["filename"] for f in files if f.get("status") == "added"]
        if added and _get(f"/repos/{repo}/contents/{added[0]}?ref=main") is None:
            return "bad", f"merged, then reverted · #{num}"
        return "live", f"merged · #{num}"
    if p.get("state") == "closed":
        return "bad", f"closed · #{num}"
    if p.get("state") == "open":
        return "pend", f"open PR · #{num}"
    return "draft", f"PR #{num}"


def drafts_by_domain() -> dict[str, list[dict]]:
    best: dict[tuple[str, str], dict] = {}
    for z in artifacts("agent2-written", n=60):
        for name, d in zjson(z, r"drafts/[^/]+\.json$"):
            b, dr, cms = d.get("brief", {}), d.get("draft", {}), d.get("cms") or {}
            dom = b.get("site", {}).get("domain")
            path = b.get("brief", {}).get("target_url_path") or ""
            at = b.get("envelope", {}).get("emitted_at", "")
            if dom and (dom, path) not in best or (dom and at > best[(dom, path)]["at"]):
                best[(dom, path)] = {"dom": dom, "path": path, "at": at, "draft": dr, "cms": cms,
                                     "kw": b.get("opportunity", {}).get("primary_keyword", "")}
    out: dict[str, list[dict]] = {}
    for r in best.values():
        out.setdefault(r["dom"], []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r["at"], reverse=True)
    return out


# ── render ────────────────────────────────────────────────────────────────────
def draft_block(r: dict) -> str:
    cls, label = pr_state(r["cms"].get("pr_url") or "")
    if r.get("excluded"):
        cls, label = "bad", "DO NOT PUBLISH — subject on the site's blocked list"
    dr = r["draft"]
    body = dr.get("body_markdown", "")
    faq = "".join(f"<p><b>{E(q.get('q'))}</b><br>{E(q.get('a'))}</p>" for q in dr.get("faq") or [])
    d = ' dir="rtl"' if RTL(dr.get("title", "")) else ""
    words = len(body.split())
    pr = r["cms"].get("pr_url")
    link = f' · <a href="{E(pr)}" target="_blank" rel="noopener">PR</a>' if pr else ""
    return (f'<details><summary><span class="s-t"{d}>{E(dr.get("title") or r["path"])}</span>'
            f'<span class="s-m"><span class="cc {cls}">{E(label)}</span> {words} words · {E(r["at"][:10])}</span></summary>'
            f'<div class="body"{d}><h4>{E(dr.get("title"))}</h4><blockquote>{E(dr.get("meta_description"))}</blockquote>'
            f'<p class="note" dir="ltr">Target <code class="mono">{E(r["path"])}</code> · keyword “{E(r["kw"])}”{link}</p><hr>'
            f'{md(body, shift=3)}{("<hr><h5>FAQ</h5>" + faq) if faq else ""}</div></details>')


def brief_block(b: dict) -> str:
    o, br = b.get("opportunity", {}), b.get("brief", {})
    d = ' dir="rtl"' if RTL(br.get("working_title", "") or o.get("primary_keyword", "")) else ""
    outline = "".join(f"<li>{E(s.get('heading'))}</li>" for s in br.get("outline", []) or [])
    return (f'<details><summary><span class="s-t"{d}>{E(br.get("working_title") or o.get("primary_keyword"))}</span>'
            f'<span class="s-m"><span class="cc brief">{E(o.get("gap_type"))}</span> {E(br.get("target_url_path"))}</span></summary>'
            f'<div class="body"{d}><p><b>Keyword:</b> {E(o.get("primary_keyword"))} · <b>priority</b> {E(o.get("priority_score"))}</p>'
            f'<p>{E(o.get("rationale"))}</p>{("<h5>Outline</h5><ul>" + outline + "</ul>") if outline else ""}</div></details>')


def build() -> str:
    sites = {s.domain: s for s in config.load_sites(include_hold=True)}
    drafts = drafts_by_domain()
    scout = artifacts("seo-scout-run")
    briefs, improvements, run_id = {}, {}, ""
    if scout:
        z = scout[0]
        for _, m in zjson(z, r"/manifest\.json$"):
            run_id = m.get("run_id", "")
        for _, b in zjson(z, r"/briefs/[^/]+\.json$"):
            briefs.setdefault(b["site"]["domain"], []).append(b)
        for _, i in zjson(z, r"/improvements/[^/]+\.json$"):
            improvements[i["domain"]] = i.get("candidates", [])
    audit = strategy = health = ""
    for z in artifacts("site-audit"):
        audit = ztext(z, r"reports/audit-.*\.md$")
        strategy = ztext(z, r"reports/strategy-.*\.md$")
        health = ztext(z, r"reports/health-latest\.md$")
    geo = "".join(ztext(z, r"geo-.*\.md$") for z in artifacts("keyword-geo-reports"))
    live_report = "".join(ztext(z, r"merge-watch-.*\.md$") for z in artifacts("merge-watch"))
    comp = {}
    for z in artifacts("competitor-scout"):
        for _, c in zjson(z, r"competitors\.json$"):
            comp = {s["domain"]: s for s in c.get("sites", [])}
    social: dict[str, list] = {}
    for z in artifacts("agent3-broadcast"):
        for _, p in zjson(z, r"broadcast/posts/[^/]+\.json$"):
            for post in p.get("posts", []):
                dom = re.sub(r"^https?://(www\.)?([^/]+).*", r"\2", (post.get("copy") or {}).get("cta_url", ""))
                social.setdefault(dom, []).append((p.get("campaign_id"), post))

    nav, panes, totals = [], [], {"live": 0, "pend": 0, "draft": 0}
    for dom in ORDER:
        if dom not in sites:
            continue
        pid = dom.replace(".", "-")
        live = live_articles(dom)
        ds = drafts.get(dom, [])
        for r in ds:   # e.g. "avintura": a fabricated subject must never read as publishable
            r["excluded"] = any(re.search(pat, r["kw"] or "", re.I) for pat in sites[dom].exclude_queries)
        states = [pr_state(r["cms"].get("pr_url") or "")[0] for r in ds]
        n_pend = states.count("pend")
        n_draft = sum(1 for s in states if s == "draft")
        bs, imps, posts = briefs.get(dom, []), improvements.get(dom, []), social.get(dom, [])
        totals["live"] += len(live); totals["pend"] += n_pend; totals["draft"] += n_draft
        cts = [f'<span class="cc live">{len(live)} live</span>' if live else "",
               f'<span class="cc pend">{n_pend} PR</span>' if n_pend else "",
               f'<span class="cc draft">{n_draft} draft</span>' if n_draft else "",
               f'<span class="cc brief">{len(bs)} brief</span>' if bs else "",
               f'<span class="cc social">{len(posts)} social</span>' if posts else "",
               '<span class="cc an">analysis</span>']
        nav.append(f'<button class="navrow" data-p="{pid}"><span class="nm">{dom}</span>'
                   f'<span class="cts">{" ".join(c for c in cts if c)}</span></button>')
        s = sites[dom]
        cms = s.cms or {}
        p = [f'<div class="prop" id="p-{pid}" hidden><h2>{dom}</h2><p class="sub">{E(BLURB.get(dom, ""))} · '
             f'publishes via <code class="mono">{E(cms.get("adapter") or "none")}</code>'
             f'{" · on hold" if s.on_hold else ""}</p>']
        if live:
            p.append(f'<section class="grp"><h3><span class="chip live">ON MAIN</span> Published articles <b>{len(live)}</b></h3>'
                     '<ul class="links">' + "".join(
                         f'<li{" dir=rtl" if RTL(t) else ""}><a href="{E(u)}" target="_blank" rel="noopener">{E(t)}</a></li>'
                         for t, u in live) + "</ul><p class=\"note\">Merged on the site's repo. Live once deployed.</p></section>")
        if ds:
            p.append(f'<section class="grp"><h3><span class="chip draft">DRAFTS</span> Every article the writer produced <b>{len(ds)}</b></h3>'
                     + "".join(draft_block(r) for r in ds) + "</section>")
        if bs:
            p.append(f'<section class="grp"><h3><span class="chip brief">BRIEFS</span> This run <b>{len(bs)}</b></h3>'
                     + "".join(brief_block(b) for b in bs) + "</section>")
        if imps:
            p.append(f'<section class="grp"><h3><span class="chip an">IMPROVE</span> Existing pages that underperform <b>{len(imps)}</b></h3>'
                     '<ul class="links">' + "".join(
                         f'<li><b>{E(c.get("query"))}</b> · {E(c.get("gap_type"))} · pos {E(c.get("position"))} · '
                         f'{E(c.get("impressions"))} impr. — <a href="{E(c.get("current_url") or "")}" target="_blank" rel="noopener">{E(c.get("current_url") or "no page")}</a></li>'
                         for c in imps) + "</ul><p class=\"note\">Fixed in place by the site's session. Never briefed as new pages.</p></section>")
        if posts:
            p.append(f'<section class="grp"><h3><span class="chip social">SOCIAL</span> Composed posts <b>{len(posts)}</b></h3>'
                     + "".join(f'<div class="held"><b>{E(po.get("channel"))}</b> · {E(cid)} · {E(po.get("status"))}'
                               f'{(" — " + E(po.get("hold_reason"))) if po.get("hold_reason") else ""}'
                               f'<br>{E((po.get("copy") or {}).get("body"))}</div>' for cid, po in posts)
                     + '<p class="note">Held until a Zernio account is connected. Nothing has been posted.</p></section>')
        an = []
        a = section_of(audit, dom)
        if a:
            an.append(f"<details><summary><span class=\"s-t\">Site audit</span><span class=\"s-m\">{E(a.splitlines()[0][3:])}</span></summary><div class=\"body\">{md(a, 2)}</div></details>")
        g = section_of(geo, dom)
        if g:
            an.append(f"<details><summary><span class=\"s-t\">Keyword &amp; geo</span><span class=\"s-m\">where it is found</span></summary><div class=\"body\">{md(g, 2)}</div></details>")
        c = comp.get(dom)
        if c:
            rows = "".join(f"<tr><td>{E(x['domain'])}</td><td>{E(x.get('urls_listed'))}</td><td>{E(x.get('median_words'))}</td></tr>"
                           for x in c.get("competitors", []))
            gaps = "".join(f"<li>{E(g['section'])} — {E(g['their_pages'])} pages</li>"
                           for g in (c.get("comparison") or {}).get("sections_they_cover_that_we_do_not", [])[:12])
            an.append(f'<details><summary><span class="s-t">Competitors</span><span class="s-m">{len(c.get("competitors", []))} named rivals</span></summary>'
                      f'<div class="body"><p>Us: {E(c.get("our_urls_listed"))} URLs, median {E((c.get("us") or {}).get("median_words"))} words.</p>'
                      f'<div class="tw"><table><thead><tr><th>Rival</th><th>URLs</th><th>Median words</th></tr></thead><tbody>{rows}</tbody></table></div>'
                      f'{("<h5>Sections they cover that we do not</h5><ul>" + gaps + "</ul>") if gaps else ""}</div></details>')
        if an:
            p.append('<section class="grp"><h3><span class="chip an">ANALYSIS</span> Research <b>' + str(len(an)) +
                     '</b></h3>' + "".join(an) + '<p class="note">Findings are acted on by the site\'s own session, not by hand.</p></section>')
        if len(p) == 1:
            p.append('<p class="empty">Nothing produced for this property yet.</p>')
        p.append("</div>")
        panes.append("".join(p))
    nav.append('<button class="navrow" data-p="portfolio"><span class="nm">Portfolio</span><span class="cts"><span class="cc an">strategy · health</span></span></button>')
    panes.append('<div class="prop" id="p-portfolio" hidden><h2>Portfolio</h2><p class="sub">Strategy across all sites, and pipeline health</p>'
                 + (f'<details open><summary><span class="s-t">Strategy</span><span class="s-m">agent 6</span></summary><div class="body">{md(strategy, 1)}</div></details>' if strategy else "")
                 + (f'<details><summary><span class="s-t">What is actually live</span><span class="s-m">merge-watch</span></summary><div class="body">{md(live_report, 1)}</div></details>' if live_report else "")
                 + (f'<details><summary><span class="s-t">Pipeline health</span><span class="s-m">latest</span></summary><div class="body">{md(health, 1)}</div></details>' if health else "")
                 + "</div>")
    now = datetime.now(timezone.utc)
    body = (f'<button class="theme" id="tg" aria-label="Toggle theme">◐</button><div class="wrap"><aside>'
            f'<div class="brand">🍒 Albaloo Studio<small>Materials library · {now:%Y-%m-%d %H:%M} UTC</small></div>'
            f'<div class="stat"><div class="k"><b>{totals["live"]}</b><span>articles on main</span></div>'
            f'<div class="k"><b>{totals["pend"]}</b><span>open PRs</span></div>'
            f'<div class="k"><b>{totals["draft"]}</b><span>staged drafts</span></div></div>'
            f'<nav>{"".join(nav)}</nav></aside><main><div class="banner"><h1>Everything the pipeline has made</h1>'
            f'<p>Rebuilt from the latest agent runs and the live repos: published articles, every draft with its current state, '
            f'this run’s briefs ({E(run_id)}), pages to improve, social copy and research. Four sites publish today '
            f'(boutimar.com, boutimar.ir, cruise24.ir, exploreorient); cruisebaz and ambientetravel write into base44 once billing and the token are in place.</p></div>'
            f'{"".join(panes)}</main></div>')
    tpl = TEMPLATE.read_text(encoding="utf-8")
    assert tpl.count("{{BODY}}") == 1, "template must hold exactly one {{BODY}} slot"
    return tpl.replace("{{BODY}}", body)


def main() -> int:
    if not TOK:
        print("no GitHub token (GITHUB_TOKEN or git credential) — cannot read the artifacts")
        return 2
    page = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({len(page):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
