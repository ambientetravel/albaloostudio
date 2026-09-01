#!/usr/bin/env python3
"""
Agent 2 — Writer, batch runner.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Reads the briefs Agent 1 produced, drafts each one with Gemini, runs the
compliance gate on the OUTPUT, pushes to the site's CMS adapter, and writes a
publishing.event.v1 per success.

Why this exists instead of the base44 service in BASE44-AGENT2.md
-----------------------------------------------------------------
That contract assumed Agent 2 would be an external HTTP service, so Agent 1
signed a webhook and POSTed to it. Checked properly on 9 Aug 2026, base44
cannot do the job:

  * Six of the ten registered sites need git or filesystem writes it does not
    have — astro_pr opens a pull request, boutimar_ir_static and static_bundle
    write files. Only the two base44-hosted sites are native to it.
  * The contract requires verifying an HMAC over the RAW request bytes before
    parsing. Hosted app builders typically hand you a parsed object; re-
    serialising changes key order and separators and the MAC never matches.
  * It must answer 202 in about two seconds and then draft for 30–90s. That is
    real background work, not a request handler.

Running here instead makes three problems disappear rather than solving them:
git and file writes are native, the secrets already exist, and the six-hour job
limit removes all timeout pressure.

And it deletes a moving part. The signed webhook between Agent 1 and Agent 2
existed only because Agent 2 was going to live somewhere else. Both now run in
the same place, so Agent 2 reads the briefs directly — one less credential, one
less network hop, and AGENT2_WEBHOOK_URL, whose absence killed the nightly cron
on 9 Aug, is no longer part of the design.

The rest of BASE44-AGENT2.md still stands: the payload shape, the compliance
rules, the idempotency requirement and the publishing.event contract are
unchanged. Only the transport is superseded.

    python3 agent2_writer_batch.py --briefs runs/<run_id>/briefs
    python3 agent2_writer_batch.py --briefs briefs/ --dry-run
    python3 agent2_writer_batch.py --briefs briefs/ --limit 2
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import compliance
import config
from agent2_writer_listener import (
    AdapterNotConfigured,
    ContentBrief,
    TransientUpstreamError,
    _call_gemini,
    _generate_draft,
    _resolve_data_dependencies,
    build_publishing_event,
    push_to_cms,
)

log = logging.getLogger("agent2.writer_batch")

ARCHITECTURE_CREDIT = config.ARCHITECTURE_CREDIT


@dataclass
class Outcome:
    brief_file: str
    domain: str = ""
    keyword: str = ""
    # blocked        = the compliance gate rejected the words
    # blocked_config = the TARGET SITE cannot accept them, by its own config
    # deferred       = the provider blinked; retry next run
    # failed         = an actual fault, and the only one that reddens the run
    status: str = "pending"
    target_url: str = ""
    words: int = 0
    error: str = ""
    violations: list[dict[str, Any]] = field(default_factory=list)
    warnings: int = 0
    # What this one article cost to draft. _call_gemini already returned these
    # and only build_publishing_event ever looked at them, so the counts reached
    # the event file and never the manifest — the one place anybody reads.
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    # What the CMS adapter actually achieved. "drafted" only ever meant "the
    # model produced text and the gate passed it" — it says nothing about
    # whether the article reached anywhere. Run #25 reported `2 drafted`, opened
    # zero pull requests, and staged zero files: the astro_pr adapter caught its
    # own RequestException, returned the reason in `note`, and nothing printed
    # it. Two silent failures read as a clean run.
    pr_url: str = ""
    staged_path: str = ""
    cms_note: str = ""


def _usage_summary(outcomes: list["Outcome"]) -> dict[str, Any]:
    """
    What this run spent on drafting, totalled from the per-article counts.

    Cost is None — rendered "unpriced" — the moment any model in the run has no
    entry in the price table, rather than being silently totalled as if the
    unpriced calls were free.
    """
    billed = [o for o in outcomes if o.input_tokens or o.output_tokens]
    priced, total = True, 0.0
    for o in billed:
        c = config.estimate_cost_usd(o.model, o.input_tokens, o.output_tokens)
        if c is None:
            priced = False
        else:
            total += c
    return {
        "calls": len(billed),
        "input_tokens": sum(o.input_tokens for o in billed),
        "output_tokens": sum(o.output_tokens for o in billed),
        "estimated_cost_usd": round(total, 6) if priced and billed else None,
        "unpriced_models": sorted({o.model for o in billed
                                   if config.estimate_cost_usd(
                                       o.model, o.input_tokens, o.output_tokens) is None}),
    }


def _draft_surface(draft: dict[str, Any]) -> str:
    """
    The text the compliance gate judges.

    One clause per line, and prohibition fields excluded — the same rule the
    scout learned the hard way when `must_avoid` entries got read as claims and
    dead-lettered three correct briefs. assertive_surface() owns that logic so
    every agent inherits the fix.
    """
    return compliance.assertive_surface(
        [
            draft.get("title", ""),
            draft.get("meta_description", ""),
            draft.get("body_markdown", ""),
            draft.get("key_points", []),
            draft.get("quotable_lines", []),
            [f"{f.get('q','')} {f.get('a','')}" for f in draft.get("faq", [])],
        ]
    )


def _stub_draft(brief: ContentBrief) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    A draft assembled from the brief itself, with no model involved.

    This is not a preview of what Gemini would write and must never be
    published — it exists so the rest of the machine can be exercised without a
    credential: payload parsing, the compliance gate, the CMS adapters, event
    assembly. Every one of those has broken before for reasons that had nothing
    to do with the model, and each cost a full API round-trip to discover.
    """
    b = brief.brief
    body = [f"# {b.working_title}", ""]
    for s in b.outline:
        body.append(f"{'#' * max(2, s.h)} {s.heading}")
        body.extend(f"- {c}" for c in (s.must_cover or []))
        body.append("")
    return (
        {
            "title": b.working_title,
            "meta_description": b.meta.description if b.meta else "",
            "body_markdown": "\n".join(body),
            "key_points": list(b.must_include or []),
            "quotable_lines": [],
            "faq": [],
        },
        {"provider": "stub", "model": "none", "attempts": 0, "duration_ms": 0,
         "note": "NOT MODEL OUTPUT — structural test only"},
    )


def write_one(payload: dict[str, Any], out_dir: Path, *, dry_run: bool,
              no_llm: bool = False) -> Outcome:
    """Draft, gate, publish and record one brief. Never raises."""
    name = payload.get("envelope", {}).get("message_id", "unknown")
    oc = Outcome(brief_file=name)

    try:
        brief = ContentBrief.model_validate(payload)
    except Exception as exc:
        oc.status, oc.error = "failed", f"payload does not match content.brief.v1: {exc}"
        return oc

    oc.domain = brief.site.domain
    oc.keyword = brief.opportunity.primary_keyword
    oc.target_url = brief.brief.target_url_path

    try:
        # A brief Agent 1 built without its LLM is not a brief, it is a keyword
        # and an impression count. It carries no consensus figure, no
        # proprietary fact and an unranked slug for a URL — the three things
        # that make a page worth publishing at all — so drafting it produces an
        # article that fails the pipeline's own content rules at full model
        # cost. Run #10 spent four Gemini calls this way before anyone noticed
        # the scout had degraded. The brief is not lost: Agent 1 re-scouts the
        # same gap on the next run, with its model back.
        if getattr(brief.brief, "degraded_no_llm", False):
            oc.status = "skipped"
            oc.error = ("Agent 1 built this brief without its LLM step — no "
                        "consensus figure, no proprietary fact, raw-slug URL. "
                        "Re-scouted next run rather than drafted from it.")
            return oc

        # Resolved ONCE and reused. The gate must judge against the same data
        # snapshot the model saw, or it is checking a different article.
        data = _resolve_data_dependencies(brief)
        draft, gen_meta = _stub_draft(brief) if no_llm else _generate_draft(brief, data)
        # Captured here rather than after the compliance gate: a draft that is
        # blocked downstream was still generated and still billed.
        oc.model = gen_meta.get("model", "") or ""
        oc.input_tokens = int(gen_meta.get("input_tokens") or 0)
        oc.output_tokens = int(gen_meta.get("output_tokens") or 0)
        oc.words = len(draft.get("body_markdown", "").split())

        ctx = {
            "priced_facts": data["has_priced_facts"],
            "price_asof": data["fetched_at"] if data["has_priced_facts"] else None,
            "itinerary_ports": brief.brief.must_include,
        }
        warnings = compliance.enforce(_draft_surface(draft), brief.compliance.profile, context=ctx)
        oc.warnings = len(warnings)

        if dry_run:
            oc.status = "drafted"
            (out_dir / "drafts").mkdir(parents=True, exist_ok=True)
            (out_dir / "drafts" / f"{name}.json").write_text(
                json.dumps({"brief": payload, "draft": draft}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            return oc

        result = push_to_cms(brief, draft)
        oc.pr_url = str(result.get("pr_url") or "")
        oc.staged_path = str(result.get("staged_path") or "")
        oc.cms_note = str(result.get("note") or "")
        event = build_publishing_event(brief, payload, draft, result, gen_meta, warnings, data)

        (out_dir / "events").mkdir(parents=True, exist_ok=True)
        (out_dir / "events" / f"{name}.json").write_text(
            json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "drafts").mkdir(parents=True, exist_ok=True)
        (out_dir / "drafts" / f"{name}.json").write_text(
            json.dumps({"brief": payload, "draft": draft, "cms": result},
                       ensure_ascii=False, indent=2), encoding="utf-8")

        oc.status = "drafted"
        return oc

    except compliance.ComplianceError as exc:
        oc.status = "blocked"
        oc.error = str(exc)[:400]
        oc.violations = [v.as_dict() for v in exc.violations if v.severity == compliance.BLOCK]
        (out_dir / "blocked").mkdir(parents=True, exist_ok=True)
        (out_dir / "blocked" / f"{name}.json").write_text(
            json.dumps({"brief": payload, "violations": oc.violations},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        return oc
    except AdapterNotConfigured as exc:
        # Not a fault. The target site is configured in a way that makes
        # publishing impossible, on purpose and in writing — exploreorient's
        # required heroImage, which sites.yml leaves empty so that no
        # unbuildable pull request is ever opened. Reported loudly, never red:
        # run #33 failed on this and would have failed every Sunday after it,
        # for a decision already recorded.
        oc.status = "blocked_config"
        oc.error = config.redact(str(exc))[:400]
        return oc
    except TransientUpstreamError as exc:
        # Not a failure of this pipeline. The brief is untouched and drafts on
        # the next run; saying "failed" would put a red cross on the nightly
        # cron for a capacity spike at Google, and a cron that is red for
        # reasons nobody can act on is a cron nobody opens.
        oc.status = "deferred"
        oc.error = config.redact(str(exc))[:400]
        return oc
    except Exception as exc:  # one bad brief must not end the batch
        oc.status = "failed"
        oc.error = config.redact(str(exc))[:400]
        return oc


def select_round_robin(
    briefs: list[dict[str, Any]], limit: int
) -> tuple[list[dict[str, Any]], int]:
    """
    Take one brief per site in rotation until the limit is reached.

    --limit used to cut a filename-sorted list, and Agent 1 names brief files
    by domain. Run #8 scouted eight properties, emitted 11 briefs, wrote 5 —
    and all five were boutimar.com. The other seven sites were scouted and not
    one of them got a word, and no amount of re-running would have changed
    that: the same five briefs sort first every night.

    The limit is a cost ceiling, not a priority order. Rotating spends it on
    breadth, and a site that has more briefs than the others still gets its
    extra ones — just after every site has had a first.

    Site order is first-appearance in the input, which is the sorted filename
    order, so the rotation is deterministic and a re-run writes the same five.
    Returns the selection and how many eligible briefs it deferred.
    """
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for payload in briefs:
        dom = str(payload.get("site", {}).get("domain", "")).lower()
        by_domain.setdefault(dom, []).append(payload)

    ordered: list[dict[str, Any]] = []
    while any(by_domain.values()):
        for queue in by_domain.values():
            if queue:
                ordered.append(queue.pop(0))

    if limit and limit < len(ordered):
        return ordered[:limit], len(ordered) - limit
    return ordered, 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--briefs", required=True, help="directory of content.brief.v1 JSON files")
    ap.add_argument("--out", default="written", help="where drafts, events and blocks are written")
    ap.add_argument("--limit", type=int, default=0, help="stop after N briefs (0 = all)")
    ap.add_argument("--domain", action="append", help="restrict to a domain (repeatable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="draft and gate, but do not touch any CMS")
    ap.add_argument("--no-llm", action="store_true",
                    help="assemble the draft from the brief instead of calling "
                         "Gemini. Exercises parsing, the gate, the adapters and "
                         "event assembly with no credential and no cost. Never "
                         "publishable output.")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")

    briefs_dir = Path(args.briefs)
    if not briefs_dir.is_dir():
        log.error("no such directory: %s", briefs_dir)
        return 2

    files = sorted(p for p in briefs_dir.glob("*.json") if p.name != "manifest.json")
    if not files:
        log.warning("no briefs in %s — nothing to write", briefs_dir)
        return 0

    if not args.no_llm:
        try:
            config.require_env("GEMINI_API_KEY")
        except config.ConfigError as exc:
            log.error("%s", exc)
            log.error("Agent 2 drafts with Gemini. Set GEMINI_API_KEY, or run "
                      "--no-llm to exercise everything except the model call.")
            return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    wanted = {d.lower() for d in (args.domain or [])}
    outcomes: list[Outcome] = []

    # Read and group before writing anything, so the limit can be spent across
    # sites rather than down a sorted list.
    eligible: list[dict[str, Any]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            # Never counts against the limit: an unreadable file is a fault to
            # report, not a brief that consumed a slot.
            outcomes.append(Outcome(brief_file=path.name, status="failed",
                                    error=f"unreadable: {exc}"))
            continue
        dom = str(payload.get("site", {}).get("domain", "")).lower()
        if wanted and dom not in wanted:
            continue
        eligible.append(payload)

    selected, deferred = select_round_robin(eligible, args.limit)
    if deferred:
        log.warning("--limit %d: writing %d of %d eligible briefs, %d deferred "
                    "to the next run", args.limit, args.limit, len(eligible), deferred)

    for i, payload in enumerate(selected):
        # Stop spending, do not fail. Each article is a separate model call, so
        # the ceiling is checked between them rather than inside one — a single
        # draft cannot overshoot by much, a hundred of them can. Remaining
        # briefs are deferred, which already means "nothing is wrong with these,
        # they run next time".
        #
        # Indexed by enumerate, not by len(outcomes): unreadable files above
        # already appended failures, so the two are not the same number and
        # slicing by the wrong one would silently skip or duplicate briefs.
        halt = config.over_budget(_usage_summary(outcomes)["estimated_cost_usd"])
        if halt:
            log.error("BUDGET: %s", halt)
            for rest in selected[i:]:
                outcomes.append(Outcome(
                    brief_file=rest.get("envelope", {}).get("message_id", "unknown"),
                    domain=str(rest.get("site", {}).get("domain", "")),
                    keyword=str(rest.get("brief", {}).get("primary_keyword", "")),
                    status="deferred", error=halt))
            break

        oc = write_one(payload, out_dir, dry_run=args.dry_run, no_llm=args.no_llm)
        outcomes.append(oc)
        log.info("%s — %s — %r → %s%s",
                 oc.domain or "?", oc.status, oc.keyword, oc.target_url or "-",
                 f"  ({oc.words} words)" if oc.words else "")
        if oc.status == "blocked":
            for v in oc.violations[:3]:
                log.error("    BLOCKED %s: %s", v.get("rule"), str(v.get("excerpt"))[:100])
        elif oc.status == "deferred":
            log.warning("    %s", oc.error)
        elif oc.status == "failed":
            log.error("    %s", oc.error)

    manifest = {
        "architecture_credit": ARCHITECTURE_CREDIT,
        "owner": config.OWNER,
        "dry_run": args.dry_run,
        "no_llm": args.no_llm,
        "briefs_seen": len(files),
        "processed": len(outcomes),
        # Two different deferrals, and conflating them would hide both: one is
        # this run's cost ceiling, the other is the model being busy.
        "deferred_by_limit": deferred,
        "deferred_upstream": sum(o.status == "deferred" for o in outcomes),
        # Drafted only. Listing every domain the run touched labelled four sites
        # as written in run #12, where all five briefs were skipped and not one
        # word was produced.
        "domains_written": sorted({o.domain for o in outcomes
                                   if o.domain and o.status == "drafted"}),
        "domains_skipped": sorted({o.domain for o in outcomes
                                   if o.domain and o.status == "skipped"}),
        "drafted": sum(o.status == "drafted" for o in outcomes),
        "blocked": sum(o.status == "blocked" for o in outcomes),
        "blocked_config": sum(o.status == "blocked_config" for o in outcomes),
        "failed": sum(o.status == "failed" for o in outcomes),
        "usage": _usage_summary(outcomes),
        "outcomes": [o.__dict__ for o in outcomes],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Agent 2 finished — %d drafted, %d blocked, %d deferred, %d failed "
             "(of %d briefs)", manifest["drafted"], manifest["blocked"],
             manifest["deferred_upstream"], manifest["failed"], len(files))

    # A blocked brief is the gate working, not the run failing. Only a genuine
    # error — an unreadable payload, a model or adapter fault — is exit 1.
    return 1 if manifest["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
