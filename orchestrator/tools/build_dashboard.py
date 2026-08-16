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
    competitors/competitors.json  agent 8 — us versus named rivals
    sites.yml                     the registry, which is always present

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


def _esc(v: Any) -> str:
    return html.escape(str(v), quote=True)


def _load(path: Path) -> Any | None:
    """Any unreadable file is simply absent. Never guess at its contents."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
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
@media(max-width:640px){table{font-size:13px}th,td{padding:7px 6px}
.wrap{padding:20px 12px 56px}}
"""


def _stat(k: str, v: str) -> str:
    return f'<div class="stat"><div class="v">{_esc(v)}</div><div class="k">{_esc(k)}</div></div>'


def _missing(what: str) -> str:
    return (f'<div class="panel missing">No {_esc(what)} manifest was found in this '
            f'run, so nothing is shown here. This is an absent measurement, not a '
            f'zero.</div>')


def render(scout: dict | None, writer: dict | None,
           competitors: dict | None) -> str:
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
                bad = c.get("status") != "ok"
                out.append(
                    f'<tr><td>{_esc(c.get("domain","?"))}</td>'
                    f'<td class="n">{c.get("urls_listed",0):,}</td>'
                    f'<td class="n">{c.get("median_words",0):,}</td>'
                    f'<td>{"<span class=\"pill hold\">not crawled</span>" if bad else ""}</td></tr>')
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

    Path(args.out).write_text(render(scout, writer, comp), encoding="utf-8")
    found = [n for n, v in (("agent1", scout), ("agent2", writer),
                            ("agent8", comp)) if v]
    print(f"wrote {args.out} — manifests found: {', '.join(found) or 'none'}")
    # Never fail. A dashboard missing one input is still worth reading, and a
    # red run here would mean nobody sees the parts that DID work.
    return 0


if __name__ == "__main__":
    sys.exit(main())
