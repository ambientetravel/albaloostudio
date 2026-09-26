#!/usr/bin/env python3
"""
Push drafts written BEFORE the base44_entity adapter existed into their base44
app, as DRAFT records. One-shot, and safe to re-run (the adapter upserts by slug
and never touches a record that is already published).

Why it exists: until 26 Sep the base44 adapter was "not implemented", so every
cruisebaz.com / ambientetravel.com draft was staged to disk and never reached
the app. The adapter now writes new drafts; these older ones would otherwise sit
in backfill/base44/ forever.

Each draft is re-processed with TODAY's rules before it is sent, because it was
written under older ones:
  * the process-talk scrub ("no sourced consensus figure…") on body and FAQ
  * the site's exclude_queries (the fabricated "Avintura" draft never goes)
  * a compliance re-check under the site's profile — a BLOCK is skipped, not sent
  * the site's CURRENT cms block (app_id, entity) from sites.yml, not the one
    frozen into the brief when it was drafted

    python3 tools/backfill_base44.py                 # dry run: prints what would go
    python3 tools/backfill_base44.py --apply         # writes (needs BASE44_ACCESS_TOKEN)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import compliance  # noqa: E402
import config  # noqa: E402
import agent2_writer_listener as a2  # noqa: E402

SRC = ROOT / "backfill" / "base44"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="actually write to base44")
    ap.add_argument("--src", default=str(SRC))
    a = ap.parse_args(argv)

    sites = {s.domain: s for s in config.load_sites(include_hold=True)}
    files = sorted(Path(a.src).glob("*.json"))
    if a.apply and not os.environ.get("BASE44_ACCESS_TOKEN"):
        print("BASE44_ACCESS_TOKEN is not set — nothing can be written. Dry run instead.")
        a.apply = False

    sent = skipped = 0
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        brief, draft = doc["brief"], dict(doc["draft"])
        dom = brief["site"]["domain"]
        site = sites.get(dom)
        tag = f"{dom}{brief['brief']['target_url_path']}"
        if not site or site.cms.get("adapter") != "base44_entity":
            print(f"  skip  {tag}: site is not a base44_entity site any more"); skipped += 1
            continue
        kw = brief["opportunity"]["primary_keyword"]
        if any(re.search(p, kw, re.I) for p in site.exclude_queries):
            print(f"  skip  {tag}: '{kw}' is in exclude_queries"); skipped += 1
            continue
        draft["body_markdown"] = a2._sanitize_body(draft.get("body_markdown", ""))
        draft["faq"] = a2._scrub_faq(draft.get("faq"))
        surface = "\n".join([draft.get("title", ""), draft.get("meta_description", ""),
                             draft["body_markdown"]] +
                            [f"{q.get('q','')}\n{q.get('a','')}" for q in draft["faq"]])
        blocks = [v for v in compliance.check(surface, site.compliance_profile)
                  if v.severity == compliance.BLOCK]
        if blocks:
            print(f"  skip  {tag}: BLOCK {blocks[0].rule} — …{blocks[0].excerpt[:70]}…")
            skipped += 1
            continue
        brief["site"]["cms"] = dict(site.cms)          # today's app_id / entity
        model = a2.ContentBrief.model_validate(brief)
        words = len(draft["body_markdown"].split())
        if not a.apply:
            print(f"  would {tag}: {words} words → {site.cms.get('app_id')}/{site.cms.get('entity')}")
            continue
        res = a2._push_base44_entity(model, draft, f"{site.base_url}{model.brief.target_url_path}")
        ok = bool(res.get("record_id")) and not res.get("staged_path")
        print(f"  {'sent ' if ok else 'FAIL '} {tag}: {res.get('note')}")
        sent += ok
        skipped += not ok
    print(f"\n{len(files)} file(s): {sent} written, {skipped} skipped"
          f"{'' if a.apply else ' (dry run — nothing written)'}")
    return 0 if (not a.apply or skipped == 0 or sent) else 1


if __name__ == "__main__":
    raise SystemExit(main())
