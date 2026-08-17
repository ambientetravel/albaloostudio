#!/usr/bin/env python3
"""
One page that says what the portfolio is doing.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Everything this pipeline knows is currently spread across eight GitHub job
summaries, which means it is read by whoever happens to open the right tab on
the right day. Alireza asked for an HTML view on 16 Aug 2026 and got a billing
argument instead; this is the thing he asked for.

WHAT IT READS
─────────────
Whatever it can find, and nothing is required. Each agent already writes a
manifest; this only collects them:

    runs/*/manifest.json          agent 1 — briefs, degradation, spend
    written/manifest.json         agent 2 — drafts, PRs, where words went
    reports/strategy-*.json       agent 6 — quadrants, clusters, the calendar
    reports/geo-*.json            agent 7 — country visibility and alignment
    competitors/competitors.json  agent 8 — us versus named rivals
    sites.yml                     the registry, which is always present

The first version of this page read only agents 1, 2 and 8, which answered
"did the machine run" and said nothing about what the machine is FOR. Agent 6
already scores every gap into quick-win / big-bet / fill-in / avoid, groups
them into topic clusters with a pillar page, and lays a twelve-week calendar;
agent 5 scores each site's technical health. Leaving that out made the pipeline
look like a publishing robot rather than an SEO programme.

A missing file becomes a section that says the data is missing. It never
invents a number and never renders a zero it did not measure — a dashboard
that shows 0 briefs when it simply could not find the manifest teaches people
to distrust it, and one that is distrusted is worse than none.

WHY IT IS NOT PUBLISHED
───────────────────────
This page carries competitor research, per-run cost, and articles that have not
been reviewed yet. It is built as a private artifact and deliberately NOT
deployed to albaloostudio.com. If it ever needs to be hosted, it needs auth
first.

    python3 tools/build_dashboard.py --out dashboard.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
# Imported, not reimplemented. The dashboard and the markdown report must never
# disagree about what a given script-vs-country gap means.
from agent7_keyword_scout import reading_for as _reading  # noqa: E402


def _esc(v: Any) -> str:
    return html.escape(str(v), quote=True)


def _load(path: Path) -> Any | None:
    """Any unreadable file is simply absent. Never guess at its contents."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _newest(root: Path, pattern: str) -> Any | None:
    """Newest file matching a dated glob. Absent is absent, never an empty dict."""
    for p in sorted(root.glob(pattern), reverse=True):
        v = _load(p)
        if v:
            return v
    return None


def _latest_scout(root: Path) -> dict | None:
    """The newest agent-1 manifest, by the run id in its own directory name."""
    candidates = sorted(root.glob("runs/*/manifest.json"))
    for p in reversed(candidates):
        m = _load(p)
        if isinstance(m, dict):
            return m
    return None


# ── the registry view ────────────────────────────────────────────────────────
# Which sites can actually receive what the pipeline writes. This is the
# question the whole project turns on and it was invisible until today: eight
# active sites, and on 16 Aug exactly one of them could take an article.
_LIVE_ADAPTERS = {"astro_pr", "boutimar_ir_static", "wordpress_rest"}
_STAGE_ADAPTERS = {"static_bundle"}


def _coverage() -> list[dict[str, str]]:
    rows = []
    for s in config.load_sites(include_hold=True):
        adapter = str(s.cms.get("adapter") or "unimplemented")
        held = bool(getattr(s, "on_hold", False))
        if held:
            verdict, cls = "on hold", "hold"
        elif adapter in _LIVE_ADAPTERS:
            verdict, cls = "opens a pull request", "ok"
        elif adapter in _STAGE_ADAPTERS:
            verdict, cls = "stages a bundle — manual deploy", "warn"
        else:
            verdict, cls = "no adapter — staged only", "bad"
        rows.append({"domain": s.domain, "brand": s.brand, "locale": s.locale,
                     "adapter": adapter, "verdict": verdict, "cls": cls,
                     "competitors": str(len(getattr(s, "competitors", None) or []))})
    return rows


# ── rendering ────────────────────────────────────────────────────────────────

_CSS = """
:root{--bg:#0d1b1e;--panel:#12262b;--line:#1e3a41;--ink:#e8f1f2;--dim:#8fa9ae;
--ok:#4fb286;--warn:#d9a441;--bad:#d1615d;--hold:#6b7f85;--accent:#5ec5c7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:32px 20px 72px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:17px;margin:36px 0 10px;color:var(--accent);
text-transform:uppercase;letter-spacing:.08em}
.sub{color:var(--dim);margin:0 0 8px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin-bottom:14px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;
letter-spacing:.06em}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
.pill{display:inline-block;padding:2px 9px;border-radius:99px;font-size:12px;
font-weight:600;white-space:nowrap}
.ok{background:rgba(79,178,134,.15);color:var(--ok)}
.warn{background:rgba(217,164,65,.15);color:var(--warn)}
.bad{background:rgba(209,97,93,.16);color:var(--bad)}
.hold{background:rgba(107,127,133,.18);color:var(--hold)}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat .v{font-size:24px;font-weight:650;letter-spacing:-.02em}
.stat .k{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.missing{color:var(--dim);font-style:italic}
a{color:var(--accent)}
.note{color:var(--dim);font-size:13px;margin-top:8px}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);
color:var(--dim);font-size:13px}
/* Phone. This page is read on a phone more than anywhere else — it is the
   whole point of hosting it — and the widest tables here are seven columns
   (site, market, impressions, Persian, Iran, gap, reading). At 375px those
   force the DOCUMENT to scroll sideways, which drags the headings and stat
   cards off-screen with them and makes the page feel broken rather than wide.
   display:block turns each table into its own scroll box, so a wide table
   scrolls inside itself and the page body never moves. nowrap keeps a row on
   one line while it does. */
@media(max-width:640px){
table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;
white-space:nowrap;font-size:13px}
th,td{padding:7px 6px}
.wrap{padding:20px 12px 56px}
h1{font-size:22px}
.stat .v{font-size:20px}
/* The prose under a verdict is the opposite case: it must wrap, or a long
   detail sentence becomes a horizontal scroll of its own. */
.note,.sub{white-space:normal}
}
"""


def _stat(k: str, v: str) -> str:
    return f'<div class="stat"><div class="v">{_esc(v)}</div><div class="k">{_esc(k)}</div></div>'


def _missing(what: str) -> str:
    return (f'<div class="panel missing">No {_esc(what)} manifest was found in this '
            f'run, so nothing is shown here. This is an absent measurement, not a '
            f'zero.</div>')


def render(scout: dict | None, writer: dict | None,
           competitors: dict | None, strategy: dict | None = None,
           geo: Any = None) -> str:
    now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    cov = _coverage()
    can_publish = sum(1 for r in cov if r["cls"] == "ok")
    active = sum(1 for r in cov if r["cls"] != "hold")

    out: list[str] = [
        "<!-- generated by orchestrator/tools/build_dashboard.py -->",
        f"<style>{_CSS}</style>",
        '<div class="wrap">',
        "<h1>Albaloo orchestration</h1>",
        f'<p class="sub">Portfolio state as of {_esc(now)}. '
        f"Private — contains competitor research, cost and unreviewed drafts.</p>",
    ]

    # ── headline ────────────────────────────────────────────────────────────
    cards = [_stat("sites active", f"{active}"),
             _stat("can publish", f"{can_publish} of {active}")]
    if scout:
        t = scout.get("totals", {})
        deg, tot = t.get("degraded_briefs", 0), t.get("briefs_emitted", 0)
        cards.append(_stat("briefs, last scout", f"{tot}"))
        cards.append(_stat("degraded", f"{deg} of {tot}" if tot else "—"))
        u = scout.get("usage") or {}
        c = u.get("estimated_cost_usd")
        cards.append(_stat("scout cost", f"${c:.4f}" if c is not None else "unpriced"))
    if writer:
        wc = (writer.get("usage") or {}).get("estimated_cost_usd")
        cards.append(_stat("writer cost", f"${wc:.4f}" if wc is not None else "unpriced"))
    out.append(f'<div class="grid">{"".join(cards)}</div>')

    # ── coverage ────────────────────────────────────────────────────────────
    out.append("<h2>Can each site receive an article?</h2>")
    out.append('<div class="panel"><table><tr><th>Site</th><th>Brand</th>'
               '<th>Adapter</th><th>Publishing</th><th class="n">Rivals tracked</th></tr>')
    for r in cov:
        out.append(
            f'<tr><td>{_esc(r["domain"])}</td><td>{_esc(r["brand"])}</td>'
            f'<td><code>{_esc(r["adapter"])}</code></td>'
            f'<td><span class="pill {r["cls"]}">{_esc(r["verdict"])}</span></td>'
            f'<td class="n">{_esc(r["competitors"]) if r["competitors"] != "0" else "—"}</td></tr>')
    out.append("</table>"
               f'<p class="note">{can_publish} of {active} active sites can open a '
               f"pull request or write a live entry. The rest produce words that need "
               f"a human to move them.</p></div>")

    # ── last scout ──────────────────────────────────────────────────────────
    out.append("<h2>Last scout run</h2>")
    if not scout:
        out.append(_missing("agent 1"))
    else:
        t = scout.get("totals", {})
        deg = t.get("degraded_briefs", 0)
        out.append('<div class="panel">')
        if deg:
            out.append(
                f'<p><span class="pill warn">{deg} of {t.get("briefs_emitted",0)} '
                f"degraded</span> — the gap-analysis model was unavailable for "
                f'{_esc(", ".join(scout.get("degraded_domains", [])) or "some sites")}. '
                f"Those briefs carry no consensus figure and Agent 2 skips them.</p>")
        per = (scout.get("usage") or {}).get("by_domain") or {}
        if per:
            out.append('<table><tr><th>Property</th><th>Model</th><th class="n">In</th>'
                       '<th class="n">Out</th><th class="n">Cost</th></tr>')
            for dom, v in sorted(per.items(), key=lambda kv: -(kv[1].get("output_tokens") or 0)):
                c = v.get("estimated_cost_usd")
                out.append(
                    f'<tr><td>{_esc(dom)}</td><td><code>{_esc(v.get("model","?"))}</code></td>'
                    f'<td class="n">{v.get("input_tokens",0):,}</td>'
                    f'<td class="n">{v.get("output_tokens",0):,}</td>'
                    f'<td class="n">{("$%.4f" % c) if c is not None else "unpriced"}</td></tr>')
            out.append("</table>")
        out.append("</div>")

    # ── pages that exist and are not declared ───────────────────────────────
    # The cheapest win in the whole report: no writing, no model call, no cost.
    # These pages already rank; the sitemap just does not mention them.
    unl = [d for d in (scout or {}).get("domains", []) if d.get("unlisted_pages")]
    if unl:
        tot = (scout or {}).get("totals", {})
        out.append("<h2>Ranking, but not in any sitemap</h2>")
        out.append(f'<div class="panel"><p class="sub">'
                   f'<strong>{tot.get("unlisted_pages", 0)}</strong> page(s) earning '
                   f'<strong>{tot.get("unlisted_impressions", 0):,}</strong> impressions '
                   f'that the sitemaps never mention. Nothing here needs writing — the '
                   f'pages exist. Google found them despite the site rather than because '
                   f'of it.</p>')
        for d in sorted(unl, key=lambda x: -x.get("unlisted_impressions", 0)):
            out.append(f'<p><strong>{_esc(d["domain"])}</strong> — '
                       f'{d["unlisted_pages"]} unlisted, '
                       f'{d["unlisted_impressions"]:,} impressions</p>')
            out.append('<table><tr><th>Page</th><th class="n">Impressions</th>'
                       '<th class="n">Clicks</th></tr>')
            for u in d.get("unlisted_top", [])[:10]:
                out.append(f'<tr><td>{_esc(u["url"])}</td>'
                           f'<td class="n">{u["impressions"]:,}</td>'
                           f'<td class="n">{u["clicks"]:,}</td></tr>')
            out.append("</table>")
        out.append("</div>")

    # ── where the words went ────────────────────────────────────────────────
    out.append("<h2>Where the words went</h2>")
    if not writer:
        out.append(_missing("agent 2"))
    else:
        out.append('<div class="panel"><table><tr><th>Site</th><th>Keyword</th>'
                   '<th>Status</th><th class="n">Words</th><th>Destination</th></tr>')
        for o in writer.get("outcomes", []):
            st = o.get("status", "?")
            cls = {"drafted": "ok", "deferred": "warn", "blocked": "bad",
                   "blocked_config": "warn", "failed": "bad"}.get(st, "hold")
            if o.get("pr_url"):
                dest = f'<a href="{_esc(o["pr_url"])}">pull request</a>'
            elif o.get("staged_path"):
                dest = f'<span class="pill warn">staged, not live</span>'
            elif st == "drafted":
                dest = '<span class="pill bad">nowhere — words lost</span>'
            else:
                dest = f'<span class="missing">{_esc((o.get("error") or "")[:90])}</span>'
            out.append(
                f'<tr><td>{_esc(o.get("domain","?"))}</td><td>{_esc(o.get("keyword",""))}</td>'
                f'<td><span class="pill {cls}">{_esc(st)}</span></td>'
                f'<td class="n">{o.get("words",0):,}</td><td>{dest}</td></tr>')
        out.append("</table></div>")

    # ── what to write next ──────────────────────────────────────────────────
    # The reason this pipeline exists, and the first version of this page left
    # it out entirely: it showed whether the machinery worked and said nothing
    # about what the machinery is FOR. Agent 6 already scores every gap into a
    # quadrant, groups them into topic clusters with a pillar page, and lays a
    # twelve-week calendar that front-loads winnable pages.
    out.append("<h2>What to write next</h2>")
    if not strategy:
        out.append(_missing("agent 6 strategy"))
    else:
        opps = strategy.get("opportunities", [])
        counts: dict[str, int] = {}
        for o in opps:
            counts[o.get("quadrant", "?")] = counts.get(o.get("quadrant", "?"), 0) + 1
        label = {"quick_win": "quick wins", "big_bet": "big bets",
                 "fill_in": "fill-ins", "avoid": "not worth it"}
        cards = [_stat(label.get(k, k), str(v))
                 for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
        if cards:
            out.append(f'<div class="grid">{"".join(cards)}</div>')

        quick = [o for o in opps if o.get("quadrant") == "quick_win"][:8]
        if quick:
            out.append('<div class="panel"><strong>Quick wins — ranked, close, '
                       'and winnable now</strong>'
                       '<table><tr><th>Keyword</th><th>Site</th><th class="n">Impressions</th>'
                       '<th class="n">Position</th><th>Intent</th></tr>')
            for o in quick:
                out.append(
                    f'<tr><td>{_esc(o.get("keyword",""))}</td>'
                    f'<td>{_esc(o.get("domain",""))}</td>'
                    f'<td class="n">{o.get("impressions",0):,}</td>'
                    f'<td class="n">{o.get("position",0)}</td>'
                    f'<td>{_esc(o.get("intent",""))}</td></tr>')
            out.append("</table></div>")

        topics = strategy.get("topics") or {}
        if topics:
            out.append('<div class="panel"><strong>Topic clusters</strong>'
                       '<table><tr><th>Cluster</th><th>Pillar page</th>'
                       '<th class="n">Impressions</th><th class="n">Keywords</th></tr>')
            for name, t in list(topics.items())[:10]:
                out.append(
                    f'<tr><td>{_esc(name)}</td><td>{_esc(t.get("pillar",""))} '
                    f'<span class="missing">{_esc(t.get("pillar_words",""))} words</span></td>'
                    f'<td class="n">{t.get("impressions",0):,}</td>'
                    f'<td class="n">{len(t.get("keywords",[])):,}</td></tr>')
            out.append("</table></div>")

        cal = strategy.get("calendar") or []
        if cal:
            out.append('<div class="panel"><strong>The next twelve weeks</strong>'
                       '<p class="note">Quick wins first, on purpose — the point of '
                       'weeks 1–4 is to prove the pipeline moves rankings before '
                       'anyone commits a quarter to it.</p>'
                       '<table><tr><th class="n">Week</th><th>Starting</th>'
                       '<th>Pieces</th></tr>')
            for w in cal[:12]:
                items = "<br>".join(
                    f'{_esc(i.get("keyword",""))} '
                    f'<span class="missing">{_esc(i.get("domain",""))} · '
                    f'{_esc(i.get("type",""))} · {_esc(i.get("words",""))}w</span>'
                    for i in w.get("items", []))
                out.append(f'<tr><td class="n">{w.get("week","")}</td>'
                           f'<td>{_esc(w.get("starting",""))}</td><td>{items}</td></tr>')
            out.append("</table></div>")

    # ── site health ─────────────────────────────────────────────────────────
    out.append("<h2>Site health</h2>")
    if not strategy or not strategy.get("portfolio"):
        out.append(_missing("agent 5 audit"))
    else:
        out.append(f'<div class="panel"><p class="sub">Mean score '
                   f'<strong>{strategy.get("mean_score","—")}</strong> across '
                   f'{strategy.get("sites_audited",0)} audited '
                   f'{"site" if strategy.get("sites_audited")==1 else "sites"}'
                   f'{f", {strategy['placeholders']} still on placeholder content" if strategy.get("placeholders") else ""}.</p>'
                   '<table><tr><th>Site</th><th class="n">Score</th>'
                   '<th class="n">Findings</th><th>State</th></tr>')
        for s in strategy["portfolio"]:
            sc = s.get("score", 0)
            cls = "ok" if sc >= 70 else ("warn" if sc >= 45 else "bad")
            state = ('<span class="pill bad">placeholder content</span>'
                     if s.get("placeholder") else "")
            out.append(f'<tr><td>{_esc(s.get("domain","?"))}</td>'
                       f'<td class="n"><span class="pill {cls}">{sc}</span></td>'
                       f'<td class="n">{s.get("findings",0)}</td><td>{state}</td></tr>')
        out.append("</table></div>")

    # ── geography ───────────────────────────────────────────────────────────
    out.append("<h2>Where the audience actually is</h2>")
    if not geo:
        out.append(_missing("agent 7 geo"))
    else:
        rows = geo if isinstance(geo, list) else geo.get("sites", [])
        # Script beside country, whole estate, before the per-site panels. The
        # two numbers were never in one place, so "is this site's foreign
        # traffic really Iranians on VPNs" could not be answered by looking.
        _pct = lambda v: "—" if v is None else f"{v:.0%}"
        if any(r.get("market_alignment", {}).get("persian_query_share") is not None
               for r in rows):
            out.append('<div class="panel"><strong>Persian script vs country '
                       'attribution</strong>'
                       '<p class="note">A wide positive gap is VPN tunnelling. A wide '
                       'negative gap is Iranian IPs searching in another language. '
                       'Different findings, opposite fixes.</p>')
            out.append('<table><tr><th>Site</th><th class="n">Impressions</th>'
                       '<th class="n">Persian</th><th class="n">Iran</th>'
                       '<th class="n">Gap</th><th>Reading</th></tr>')
            for r in sorted(rows, key=lambda x: -(x.get("total_impressions") or 0)):
                ma = r.get("market_alignment", {})
                gap, imp = ma.get("script_vs_country_gap"), r.get("total_impressions") or 0
                cls = ("hold" if gap is None or imp < 100 else
                       "bad" if abs(gap) >= 0.15 else "ok")
                out.append(f'<tr><td>{_esc(r.get("domain","?"))}</td>'
                           f'<td class="n">{imp:,}</td>'
                           f'<td class="n">{_pct(ma.get("persian_query_share"))}</td>'
                           f'<td class="n">{_pct(ma.get("iran_country_share"))}</td>'
                           f'<td class="n">{"+" if (gap or 0) > 0 else ""}{_pct(gap)}</td>'
                           f'<td><span class="pill {cls}">'
                           f'{_esc(_reading(gap, impressions=imp))}</span></td></tr>')
            out.append("</table></div>")
        for r in rows:
            ma = r.get("market_alignment", {})
            verdict = str(ma.get("verdict", ""))
            # Three states, not two. "too little data" is not good news and must
            # not render green just because it is not MISALIGNED — the site with
            # fourteen impressions has a worse problem than the one serving the
            # wrong country, and colouring it like a pass hides that.
            cls = {"MISALIGNED": "bad", "concentrated": "warn",
                   "too little data": "warn", "no data": "hold"}.get(verdict, "ok")
            out.append(f'<div class="panel"><strong>{_esc(r.get("domain","?"))}</strong> '
                       f'<span class="pill {cls}">{_esc(verdict or "—")}</span>'
                       f'<p class="note">{_esc(ma.get("detail",""))}</p>')
            # The Perso-Arabic reading, on whichever plane it applies. For an IR
            # site it IS the verdict; for the others it is a caveat on the table.
            if ma.get("script_note"):
                out.append(f'<p class="note">{_esc(ma["script_note"])}</p>')
            elif ma.get("persian_query_share") is not None:
                out.append(f'<p class="note">Perso-Arabic queries: '
                           f'{ma["persian_query_share"]:.0%} of impressions.</p>')
            opps_g = r.get("opportunities", [])[:6]
            if opps_g:
                # Named "exit" for IR sites on purpose. Labelling a VPN exit node
                # "Country" is what produced "cruise24.ir's audience is German".
                head = ("Exit country (VPN)" if ma.get("measured_by") == "query script"
                        else "Country")
                out.append(f'<table><tr><th>{head}</th><th class="n">Impressions</th>'
                           '<th class="n">Position</th></tr>')
                for o in opps_g:
                    out.append(f'<tr><td>{_esc(o.get("country",""))}</td>'
                               f'<td class="n">{o.get("impressions",0):,}</td>'
                               f'<td class="n">{o.get("position","—")}</td></tr>')
                out.append("</table>")
            out.append("</div>")

    # ── competitors ─────────────────────────────────────────────────────────
    out.append("<h2>How we compare</h2>")
    if not competitors:
        out.append(_missing("agent 8"))
    else:
        out.append(f'<p class="sub">{_esc(competitors.get("note",""))}</p>')
        for s in competitors.get("sites", []):
            us, cmp_ = s.get("us", {}), s.get("comparison", {})
            out.append(f'<div class="panel"><strong>{_esc(s.get("domain","?"))}</strong>'
                       f' — {us.get("urls_listed",0):,} URLs, median '
                       f'{us.get("median_words",0):,} words'
                       f' <span class="missing">(n={us.get("pages_sampled",0)})</span>')
            out.append('<table><tr><th>Competitor</th><th class="n">URLs</th>'
                       '<th class="n">Median words</th><th>Status</th></tr>')
            for c in s.get("competitors", []):
                # Built outside the f-string. Python 3.11 — which is what the
                # runners use — forbids a backslash inside an f-string
                # expression; 3.12 relaxed it (PEP 701). This file compiled
                # cleanly on a 3.14 laptop and was a SyntaxError in CI.
                flag = ('<span class="pill hold">not crawled</span>'
                        if c.get("status") != "ok" else "")
                out.append(
                    f'<tr><td>{_esc(c.get("domain","?"))}</td>'
                    f'<td class="n">{c.get("urls_listed",0):,}</td>'
                    f'<td class="n">{c.get("median_words",0):,}</td>'
                    f'<td>{flag}</td></tr>')
            out.append("</table>")
            gap = cmp_.get("depth_gap")
            if gap is not None:
                word = (f"they publish {gap:,} more words per page than we do"
                        if gap > 0 else f"we publish {abs(gap):,} more words per page")
                out.append(f'<p class="note">Depth gap: {_esc(word)}. '
                           f"Inventory, not depth, is usually the larger gap — compare "
                           f"the URL column first.</p>")
            out.append("</div>")

    out.append(
        "<footer>Built by <code>orchestrator/tools/build_dashboard.py</code> from the "
        "agents' own manifests. Costs use the rate table in <code>config.py</code>, "
        "which is a recorded assumption rather than a live price.<br>"
        f"Architecture credit: {_esc(config.ARCHITECTURE_CREDIT)} — "
        f'<a href="{_esc(config.ARCHITECTURE_URL)}">{_esc(config.ARCHITECTURE_URL)}</a>'
        "</footer></div>")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="where to look for manifests")
    ap.add_argument("--out", default="dashboard.html")
    args = ap.parse_args(argv)

    root = Path(args.root)
    scout = _latest_scout(root)
    writer = _load(root / "written" / "manifest.json")
    comp = _load(root / "competitors" / "competitors.json")
    # Agents 5/6/7 write dated files, so take the newest of each rather than
    # guessing today's name — a Monday report read on Thursday is still the
    # current one.
    strategy = _newest(root, "reports/strategy-*.json")
    geo = _newest(root, "reports/geo-*.json")

    Path(args.out).write_text(render(scout, writer, comp, strategy, geo),
                              encoding="utf-8")
    found = [n for n, v in (("agent1", scout), ("agent2", writer),
                            ("agent8", comp), ("agent6", strategy),
                            ("agent7", geo)) if v]
    print(f"wrote {args.out} — manifests found: {', '.join(found) or 'none'}")
    # Never fail. A dashboard missing one input is still worth reading, and a
    # red run here would mean nobody sees the parts that DID work.
    return 0


if __name__ == "__main__":
    sys.exit(main())
