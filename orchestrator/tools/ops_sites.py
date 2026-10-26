#!/usr/bin/env python3
"""
ops-sync: the Sites tab of the Albaloo Ops app — one card per property, the
"can each site receive an article?" table from the old Orchestration dashboard,
kept live.

Architecture credit: Albaloo Studio — albaloostudio.com. Spec: OPS-APP.md.

Per site, from sources the pipeline already has (nothing is estimated):
  sites.yml                      brand, language, market, hosting, publishing adapter,
                                 lead source, social channels, whether it can receive
                                 an article (an adapter exists and the site is active)
  Notion Content Review board    drafts waiting, published to date, last draft date
  the app's Lead table           leads to date, hot leads
  weekly index-coverage report   sitemap pages, pages Google has shown, coverage %
                                 (blank when the weekly report is not available)

Row key: domain. Read-only towards everything but the app's Site entity.

    python3 tools/ops_sites.py --coverage <index-coverage artifact dir>            # dry run
    python3 tools/ops_sites.py --coverage <dir> --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion_review_sync as nrs  # noqa: E402
import ops_sync  # noqa: E402

ENTITY = "Site"
PUBLISHING = {"astro_pr": "opens a pull request", "boutimar_ir_static": "opens a pull request",
              "bundle_pr": "opens a pull request", "static_bundle": "stages a deploy bundle",
              "base44_entity": "writes a base44 draft", "wordpress_rest": "WordPress draft"}


def _ent(path: str = "") -> str:
    return f"/{ops_sync.OPS_APP}/entities/{ENTITY}{path}"


def site_rows() -> list[dict]:
    import yaml
    out = []
    for s in (yaml.safe_load((ROOT / "sites.yml").read_text(encoding="utf-8")) or {}).get("sites") or []:
        cms = s.get("cms") or {}
        adapter = str(cms.get("adapter") or "")
        hold = bool(s.get("hold") or s.get("on_hold") or str(s.get("status", "")).lower() in ("hold", "on_hold"))
        out.append({
            "domain": s["domain"], "brand": str(s.get("brand") or ""), "language": str(s.get("locale") or ""),
            "market": str(s.get("market") or ""), "hosting": str(s.get("hosting") or ""),
            "adapter": adapter or "none",
            "publishing": "on hold" if hold else PUBLISHING.get(adapter, "no adapter"),
            "can_publish": "yes" if (adapter in PUBLISHING and not hold) else "no",
            "lead_source": "yes" if s.get("lead_source") else "no",
            "channels": ", ".join(str(c.get("name")) for c in s.get("channels") or [] if c.get("name")),
        })
    return out


def coverage(folder: Path | None) -> dict[str, dict]:
    if not folder or not folder.exists():
        return {}
    files = sorted(folder.glob("**/index-coverage-*.json"))
    if not files:
        return {}
    rows = json.loads(files[-1].read_text(encoding="utf-8"))
    return {r["domain"]: r for r in rows if isinstance(r, dict) and r.get("domain") and not r.get("error")}


def build(sites: list[dict], board: list[dict], leads: list[dict], cov: dict[str, dict], now: str) -> list[dict]:
    out = []
    for s in sites:
        d = s["domain"]
        mine = [r for r in board if r.get("site") == d]
        written = sorted(str(r.get("written") or "") for r in mine if r.get("written"))
        ld = [x for x in leads if x.get("property") == d]
        c = cov.get(d) or {}
        row = {**s,
               "drafts_waiting": sum(r.get("status") == "To review" for r in mine),
               "published_total": sum(r.get("status") == "Published" for r in mine),
               "last_draft_at": written[-1] if written else "",
               "leads_total": len(ld),
               "leads_hot": sum(x.get("qualification") == "hot" for x in ld),
               "synced_at": now}
        if c.get("declared") is not None:
            row["pages_in_sitemap"] = c["declared"]
            row["pages_shown_by_google"] = c.get("declared_and_surfaced") or 0
            row["coverage_pct"] = round(100 * float(c.get("coverage") or 0), 1)
        out.append(row)
    return out


def run(apply: bool, cov_dir: Path | None) -> list[str]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    code, d = nrs.b44("GET", _ent("/v2/list?limit=200"))
    if code != 200:
        return [f"Site entity not reachable (HTTP {code}) — paste OPS-APP-OVERVIEW-PROMPT.md into base44 first"]
    have = {h.get("domain"): h for h in nrs._b44_items(d)}
    board = ops_sync.board(os.environ.get("NOTION_REVIEW_DB") or nrs.DEFAULT_DB) if os.environ.get("NOTION_TOKEN") else []
    lc, ldata = nrs.b44("GET", f"/{ops_sync.OPS_APP}/entities/Lead/v2/list?limit=1000")
    leads = nrs._b44_items(ldata) if lc == 200 else []
    rows = build(site_rows(), board, leads, coverage(cov_dir), now)
    errors = 0
    for r in rows:
        h = have.get(r["domain"])
        if apply:
            c, _ = (nrs.b44("PUT", _ent(f"/{h['id']}"), r) if h else nrs.b44("POST", _ent(), r))
            errors += c not in (200, 201)
    shown = sum(1 for r in rows if "coverage_pct" in r)
    return [f"sites: {len(rows)} ({sum(r['can_publish'] == 'yes' for r in rows)} can publish) · "
            f"coverage for {shown} · {errors} error(s)" + ("" if apply else "  (dry run — nothing written)")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--coverage", default="", help="folder with the weekly index-coverage artifact")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if not os.environ.get("BASE44_ACCESS_TOKEN"):
        print("not configured: BASE44_ACCESS_TOKEN — nothing synced")
        return 0
    print("\n".join(run(a.apply, Path(a.coverage) if a.coverage else None)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
