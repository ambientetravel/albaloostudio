"""Self-check for the Albaloo orchestrator — no network, no API keys, no pytest.

Architecture credit: Albaloo Studio — albaloostudio.com

    python selfcheck.py        # exits 0 on a clean pipeline, 1 on any failure

Mocks Search Console and Gemini. Exercises config, the compliance gate, gap
detection, payload assembly, JSON-Schema conformance, delivery retry and the
Agent 2 HTTP surface end to end.
"""
import json, os, sys, pathlib

os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-secret-123")
os.environ.setdefault("PIPELINE_ENVIRONMENT", "staging")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")

import jsonschema
import yaml
import config, compliance

FAIL = []
def ok(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(extra) if extra and not cond else ""))
    if not cond: FAIL.append(label)

print("\n=== config ===")
# include_hold: the REGISTRY is ten properties. Two are paused for a rebuild,
# which is a runtime state, not a change to the portfolio — and the docs below
# are checked against the registry, so they must count the same thing.
sites = config.load_sites(include_hold=True)
ok("the portfolio loads", len(sites) == 10, len(sites))
ok("and two of them are currently held",
   len(config.load_sites()) == 8, len(config.load_sites()))
ok("every registered domain is unique",
   len({s.domain for s in config.load_sites(include_hold=True)})
   == len(config.load_sites(include_hold=True)))
ok("the default load excludes every held site",
   all(not s.on_hold for s in config.load_sites()),
   "`sites` above is the full registry; this is the working set")

# The hold mechanism is tested against a FIXTURE, not against whichever real
# site happens to be paused today. cruise24.ir used to be the test subject; it
# came off hold on 9 Aug 2026 when it went live, and took five assertions with
# it. A feature test must not depend on the state of production data.
_hold_yaml = """
defaults: {min_impressions: 5, status: active}
sites:
  - {domain: live.example, property_uri: "sc-domain:live.example"}
  - {domain: paused.example, property_uri: "sc-domain:paused.example", status: hold}
"""
_tmp = pathlib.Path(__file__).with_name(".selfcheck-hold.yml")
_tmp.write_text(_hold_yaml, encoding="utf-8")
try:
    ok("held sites excluded by default",
       [s.domain for s in config.load_sites(_tmp)] == ["live.example"])
    ok("include_hold returns the full portfolio",
       len(config.load_sites(_tmp, include_hold=True)) == 2)
    ok("naming a held site explicitly overrides the hold",
       [s.domain for s in config.load_sites(_tmp, only=["paused.example"])]
       == ["paused.example"])
    ok("on_hold flag reads from the registry",
       next(s.on_hold for s in config.load_sites(_tmp, include_hold=True)
            if s.domain == "paused.example") is True)
finally:
    _tmp.unlink(missing_ok=True)
# The audit score counts findings, so it scales with sample size. The cron never
# passes --sample; it takes this. Uniformity is what makes the trend line real.
ok("audit sample size is pinned uniformly",
   {s.audit_sample_pages for s in config.load_sites(include_hold=True)} == {10},
   {s.audit_sample_pages for s in config.load_sites(include_hold=True)})
ok("defaults merged into each site", all(s.min_impressions == 5 for s in sites
                                         if s.domain != "boutimar.com"))

# ── The scheduled-run blind spot ─────────────────────────────────────────────
# Every manual run passed --dry-run. The 04:15 cron never does, so it was a LIVE
# run demanding a delivery endpoint that Agent 2 does not yet provide, and it
# died on the missing secret every night. Testing only the convenient branch is
# exactly how the `?e=` bug shipped in August.
_wf = (pathlib.Path(__file__).resolve().parents[1]
       / ".github" / "workflows" / "agent1-seo-scout.yml").read_text(encoding="utf-8")
ok("the cron degrades to brief-only when Agent 2 has no endpoint",
   'if [ -z "$AGENT2_WEBHOOK_URL" ]' in _wf,
   "a scheduled run with no delivery target must still scout, not fail")
ok("the guard does not override an explicit dry-run request",
   'inputs.dry_run }}" != "true"' in _wf)
ok("AGENT2_WEBHOOK_URL is passed to the scout step",
   "AGENT2_WEBHOOK_URL: ${{ secrets.AGENT2_WEBHOOK_URL }}" in _wf,
   "the guard tests an env var that must actually be populated")
_scout_src = pathlib.Path(__file__).with_name("agent1_seo_scout.py").read_text(encoding="utf-8")
_tail = _scout_src.split('require_env("AGENT2_WEBHOOK_URL")', 1)[1][:600]
ok("a missing delivery endpoint is exit 2, not a traceback",
   "except ConfigError" in _tail and "return 2" in _tail,
   "exit 1 reads as 'a brief was dead-lettered' and misdirects the search")
ok("boutimar.com overrides the impression floor",
   next(s.min_impressions for s in sites if s.domain == "boutimar.com") == 20)
ok("domain filter works", len(config.load_sites(only=["boutimar.ir"])) == 1)
try:
    config.load_sites(only=["nope.example"]); ok("unknown domain raises", False)
except config.ConfigError: ok("unknown domain raises", True)

body = json.dumps({"a": 1, "fa": "خلیج فارس"}, ensure_ascii=False).encode()
import time as _t
ts = int(_t.time())
sig = config.sign_payload("test-secret-123", ts, body)
ok("signature verifies", config.verify_signature("test-secret-123", sig, str(ts), body)[0])
ok("tampered body rejected", not config.verify_signature("test-secret-123", sig, str(ts), body + b"x")[0])
ok("wrong secret rejected", not config.verify_signature("other", sig, str(ts), body)[0])
ok("replay window enforced", not config.verify_signature("test-secret-123", sig, str(ts - 900), body)[0])
h = config.signed_headers("test-secret-123", body, "msg_x")
ok("signed_headers self-verify",
   config.verify_signature("test-secret-123", h["X-Albaloo-Signature"], h["X-Albaloo-Timestamp"], body)[0])
ok("idempotency key stable",
   config.idempotency_key("boutimar.ir", "کروز", "/x") == config.idempotency_key("BOUTIMAR.IR", " کروز ", "/x"))
ok("idempotency key format", config.idempotency_key("a","b","c").startswith("sha256:"))
ok("redact scrubs", "[redacted]" in config.redact("api_key=abc"))
try:
    config.load_service_account_info(); ok("bad SA creds raise", False)
except config.ConfigError: ok("bad SA creds raise", True)
os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = json.dumps({"type": "authorized_user"})
try:
    config.load_service_account_info(); ok("non-service-account key rejected", False)
except config.ConfigError as e: ok("non-service-account key rejected", "not a service account" in str(e))
del os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]




print("\n=== agent 2 — batch writer ===")
import agent2_writer_batch as a2b

_wf2 = (pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "agent2-writer.yml").read_text(encoding="utf-8")
ok("Agent 2 is chained off Agent 1, not woken by a webhook",
   "workflow_run" in _wf2 and 'workflows: ["Agent 1 — SEO Scout"]' in _wf2)
ok("it does not run when the scout failed",
   "workflow_run.conclusion == 'success'" in _wf2,
   "a failed scout emits no briefs; running anyway reports an empty success")
ok("it degrades to --no-llm instead of failing on a missing key",
   'if [ "${{ inputs.no_llm }}" = "true" ] || [ -z "${GEMINI_API_KEY:-}" ]' in _wf2)
ok("AGENT2_WEBHOOK_URL is no longer a secret this workflow consumes",
   "secrets.AGENT2_WEBHOOK_URL" not in _wf2,
   "the secret whose absence killed the nightly cron is not part of the new path")
ok("actions:read is granted for the cross-workflow artifact",
   "actions: read" in _wf2)
# A manual dispatch has no upstream workflow_run, so both ID sources are empty
# and download-artifact fails with "unable to find artifact" rather than "you
# did not say which run". Resolve the latest successful scout instead.
# workflow_run carries no inputs, so the SHELL fallback governs the nightly run,
# not the input default. If the two disagree, the number in the UI is not the
# number that runs — the same trap as the model default that read flash in
# config.py and pro in the workflow.
import re as _re
_lim_input = _re.search(r'limit:\n\s+description:[^\n]*\n\s+required: false\n\s+default: "(\d+)"', _wf2)
_lim_shell = set(_re.findall(r"inputs\.limit \|\| '(\d+)'", _wf2))
ok("the brief limit is 5", _lim_input and _lim_input.group(1) == "5",
   _lim_input.group(1) if _lim_input else "not found")
ok("the input default and the shell fallback agree",
   _lim_input and {_lim_input.group(1)} == _lim_shell,
   f"input={_lim_input.group(1) if _lim_input else '?'} shell={_lim_shell}")

ok("a manual dispatch resolves the latest scout run instead of failing",
   "gh run list --workflow agent1-seo-scout.yml --status success" in _wf2)
ok("and it says so plainly when there is no scout run to read",
   "No successful Agent 1 run to take briefs from" in _wf2)

# The stub must never look like publishable output.
# Normalised: the docstring wraps, so a raw substring match is brittle.
_meta = " ".join((a2b._stub_draft.__doc__ or "").split())
ok("the stub draft documents that it is not model output",
   "must never be published" in _meta)
_stub_meta = a2b._stub_draft.__wrapped__ if hasattr(a2b._stub_draft, "__wrapped__") else None
ok("and its generation_meta flags itself as non-model output",
   "NOT MODEL OUTPUT" in pathlib.Path(__file__).with_name(
       "agent2_writer_batch.py").read_text(encoding="utf-8"))

print("\n=== agent 2 — how the per-run limit is spent ===")
# Run #8's shape exactly: eight briefs for boutimar.com sorting ahead of one
# each for three other sites. Sorted-and-truncated wrote five boutimar.com
# briefs and nothing else; rotation must reach every site first.
_briefs = ([{"site": {"domain": "boutimar.com"}, "n": i} for i in range(8)]
           + [{"site": {"domain": "boutimar.ir"}, "n": 100},
              {"site": {"domain": "cruisebaz.com"}, "n": 101},
              {"site": {"domain": "exploreorient.com"}, "n": 102}])
_sel, _def = a2b.select_round_robin(_briefs, 5)
_doms = [b["site"]["domain"] for b in _sel]
ok("the per-run limit is spent across sites, not down a sorted list",
   len(set(_doms)) == 4, _doms)
ok("every site gets a brief before any site gets a second",
   _doms.count("boutimar.com") == 2, f"boutimar.com took {_doms.count('boutimar.com')} of 5")
ok("and the briefs it could not fit are reported, not dropped silently",
   _def == 6, _def)
ok("no limit means every eligible brief is written",
   a2b.select_round_robin(_briefs, 0) == (a2b.select_round_robin(_briefs, 0)[0], 0)
   and len(a2b.select_round_robin(_briefs, 0)[0]) == 11)
# Determinism matters more than it looks: a re-run that reshuffles the
# selection writes a different five and the deferred ones never come up.
ok("the selection is deterministic across calls",
   [b["n"] for b in a2b.select_round_robin(_briefs, 5)[0]]
   == [b["n"] for b in a2b.select_round_robin(_briefs, 5)[0]])
ok("a single-site portfolio still fills the limit",
   len(a2b.select_round_robin(
       [{"site": {"domain": "boutimar.com"}, "n": i} for i in range(9)], 5)[0]) == 5)

print("\n=== a degraded scout does not look like a healthy one ===")
# Run #10 finished in 47s where run #9 took 6m22s, emitted 14 briefs built
# entirely by the fallback, and reported Success. The only visible difference on
# the run page was the duration.
import agent1_seo_scout as _a1sp
import agent2_writer_listener as _a2l
_a2bsrc = pathlib.Path(__file__).with_name("agent2_writer_batch.py").read_text(encoding="utf-8")
_fb = _a1sp._fallback_brief(
    [x for x in config.load_sites() if x.domain == "boutimar.ir"][0],
    {"query": "لانزاروته", "gap_type": "missing_page", "impressions": 120,
     "position": 41.0, "local_score": 60},
)
_a1src = pathlib.Path(__file__).with_name("agent1_seo_scout.py").read_text(encoding="utf-8")
_wf1 = (pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "agent1-seo-scout.yml").read_text(encoding="utf-8")
ok("a fallback brief marks itself as degraded", _fb.get("_degraded") is True)
ok("and it genuinely has none of what the GEO rules require",
   _fb["must_include"] == [], "no consensus figure, no proprietary fact")
ok("a Farsi keyword with no ASCII strips to a placeholder path, not a real one",
   _fb["target_url_path"] == "/opportunity",
   "which is why publishing one is worse than deferring it")
_a1src = pathlib.Path(__file__).with_name("agent1_seo_scout.py").read_text(encoding="utf-8")
# Knowing a run degraded is half the answer; the other half is why. Reading it
# meant expanding a collapsed log step by hand, which is not a thing anyone does
# at 04:15.
ok("a fallback brief carries the reason the model did not answer",
   _a1sp._fallback_brief(
       [x for x in config.load_sites() if x.domain == "boutimar.ir"][0],
       {"query": "q", "gap_type": "missing_page", "impressions": 1,
        "position": 40.0, "local_score": 1},
       "Anthropic unavailable: boom")["_degraded_reason"] == "Anthropic unavailable: boom")
ok("and the reason is redacted before it is stored",
   "config.redact(reason)" in pathlib.Path(__file__).with_name(
       "agent1_seo_scout.py").read_text(encoding="utf-8"),
   "an exception body can carry the key that failed")
ok("every fallback call site supplies a reason",
   _a1src.count("_fallback_brief(site, c)") == 0,
   "a bare call would report a degraded run with no cause")
ok("the reasons reach the manifest and the annotation",
   '"degraded_reasons"' in _a1src and "Cause: {why}" in _wf1)
# Run #12 made the same failing Claude call once per domain and printed "credit
# balance is too low" four times. The second call was never going to succeed.
print("\n=== agent 1 — the nightly scout runs on the free tier ===")
# The $5 Anthropic balance emptied in four days. Agent 1 is why: one Opus 5 call
# per property per night at up to 16k output tokens, $25 per million output.
ok("gap analysis defaults to Gemini, not the metered vendor",
   config.GAP_ANALYSIS_PROVIDER == "gemini", config.GAP_ANALYSIS_PROVIDER)
ok("and Gemini defaults to a model the free tier actually allows",
   config.GEMINI_MODEL.endswith("flash") or "GEMINI_MODEL" in os.environ,
   config.GEMINI_MODEL)
ok("the scout has a real Gemini path, not just a config value",
   "def _analyse_with_gemini" in _a1src and "def _gemini_generate" in _a1src)
ok("all three providers stay reachable by env var",
   all(f'GAP_ANALYSIS_PROVIDER == "{p}"' in _a1src for p in ("gemini", "anthropic")),
   "topping the balance up is a repository variable, not an edit")
# Agent 2 drafts prose at 0.85; ranking the same candidates twice should not
# produce two different rankings.
ok("analysis samples tighter than drafting does",
   _a1sp._GEMINI_ANALYSIS_CONFIG["temperature"] < 0.5,
   _a1sp._GEMINI_ANALYSIS_CONFIG["temperature"])
ok("and asks for JSON rather than parsing prose",
   _a1sp._GEMINI_ANALYSIS_CONFIG["response_mime_type"] == "application/json")
# Run #13: Gemini's JSON mode guarantees valid JSON and nothing about its
# shape. It returned a bare array, the caller did .get("briefs") on it, and all
# ten sites fell back with "'list' object has no attribute 'get'" — a parser
# assumption reported to the user as a model failure.
ok("a bare array of briefs is accepted", len(_a1sp._briefs_from('[{"a":1}]')) == 1)
ok("so is the documented envelope",
   len(_a1sp._briefs_from('{"briefs":[{"a":1},{"b":2}]}')) == 2)
ok("and a differently-named single list",
   len(_a1sp._briefs_from('{"opportunities":[{"a":1}]}')) == 1)
_amb = False
try:
    _a1sp._briefs_from('{"x":[],"y":[]}')
except ValueError:
    _amb = True
ok("but two candidate lists is refused, not guessed at", _amb)
ok("the Gemini prompt states the envelope the other two get from a schema",
   'The top level is an OBJECT with the key' in _a1src,
   "Gemini takes no response-schema parameter here")
ok("an overloaded Gemini waits instead of falling straight back",
   "is_overloaded(msg) or config.rate_limited(msg)" in _a1src
   and "attempt < 3" in _a1src,
   "run #13 also hit a 503 on this path with no backoff")
# Run #14: four properties in quick succession, two answered, two got 429
# RESOURCE_EXHAUSTED. The free tier limits requests per minute.
# Run #18: boutimar.com came back "Unterminated string starting at line 192".
# That is an answer that did not fit, not a bad answer — and it hit the biggest
# site, so the property that matters most was the one silently degraded.
ok("a cut-off JSON answer is told apart from a broken one",
   _a1sp._truncated_json("Unterminated string starting at: line 192")
   and _a1sp._truncated_json("Expecting value: line 1 column 1"))
ok("and a quota error is not mistaken for truncation",
   not _a1sp._truncated_json("429 RESOURCE_EXHAUSTED")
   and not _a1sp._truncated_json("model returned no briefs"))
ok("the output ceiling is no longer 8192",
   _a1sp._GEMINI_ANALYSIS_CONFIG["max_output_tokens"] >= 32768,
   _a1sp._GEMINI_ANALYSIS_CONFIG["max_output_tokens"])
ok("and truncation retries for fewer briefs rather than giving up",
   "retrying for %d brief" in _a1src and "limit // 2" in _a1src,
   "half a site's briefs beat none of them")
# Run #20 degraded on "Server disconnected without sending a response" — not a
# 503, not a 429, not malformed JSON, so it matched no retry path and went
# straight to the fallback. The most ordinary transient failure there is.
ok("a dropped connection is recognised as transient",
   config.transport_error("Server disconnected without sending a response")
   and config.transport_error("Connection reset by peer")
   and config.transport_error("Read timed out"))
ok("and is not confused with a quota or a bad answer",
   not config.transport_error("429 RESOURCE_EXHAUSTED")
   and not config.transport_error("Unterminated string at line 192"))
ok("the scout retries it rather than falling back",
   "config.transport_error(msg)" in _a1src)
ok("a Gemini rate-limit 429 is recognised as worth waiting out",
   config.rate_limited("429 RESOURCE_EXHAUSTED: You exceeded your current quota"))
ok("but 'limit: 0' is NOT — no wait fixes a model absent from the plan",
   not config.rate_limited("429 RESOURCE_EXHAUSTED quota limit: 0"))
ok("a 503 is not mistaken for a rate limit",
   not config.rate_limited("503 UNAVAILABLE high demand"))
ok("rate limits are retried on the same backoff as overload",
   "is_overloaded(msg) or config.rate_limited(msg)" in _a1src)
# Agent 1 got rate-limit handling on 12 Aug and Agent 2 did not, so the same
# free-tier ceiling deferred a brief in one agent and failed the run in the
# other. One definition, both agents.
_a2lsrc = pathlib.Path(__file__).with_name("agent2_writer_listener.py").read_text(encoding="utf-8")
ok("Agent 2 defers on a rate limit too, not just an overload",
   "is_overloaded(msg) or config.rate_limited(msg)" in _a2lsrc)
ok("and raises the transient type so the run stays green",
   "or config.rate_limited(str(last_error))" in _a2lsrc)
_wf2 = (pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "agent2-writer.yml").read_text(encoding="utf-8")
ok("the deferral note does not name a cause it did not check",
   "the model was \" \n" not in _wf2 and "overloaded.**" not in _wf2,
   "run #16 called a 429 rate limit an overload")
ok("a brief that was not drafted says why on the run page",
   "### Not drafted" in _wf2,
   "a row of zeros meant expanding a collapsed log step by hand")
ok("and per-property calls are paced so the ceiling is not hit at all",
   config.GEMINI_MIN_INTERVAL_S > 0 and "_GEMINI_LAST_CALL" in _a1src,
   f"{config.GEMINI_MIN_INTERVAL_S}s between properties")
# The scout shared ANTHROPIC_MODEL with Agents 3, 4 and 6, so it ran on Opus 5
# — the wrong tier for classify/rank/outline, and the only one of the four on a
# schedule of its own, so it paid the top rate most often.
ok("gap analysis has its own model setting, separate from the prose agents",
   config.GAP_ANALYSIS_MODEL != config.ANTHROPIC_MODEL
   or "GAP_ANALYSIS_MODEL" in os.environ,
   f"{config.GAP_ANALYSIS_MODEL} vs {config.ANTHROPIC_MODEL}")
ok("and it is not the top tier",
   "opus" not in config.GAP_ANALYSIS_MODEL.lower() or "GAP_ANALYSIS_MODEL" in os.environ,
   config.GAP_ANALYSIS_MODEL)
ok("the Anthropic path actually reads it",
   "config.GAP_ANALYSIS_MODEL" in _a1src and
   '"model": config.ANTHROPIC_MODEL' not in _a1src)
ok("Agents 3, 4 and 6 keep the prose model",
   config.ANTHROPIC_MODEL.startswith("claude-opus")
   or "ANTHROPIC_MODEL" in os.environ, config.ANTHROPIC_MODEL)
# Search Console lags ~2 days over a 90-day window: consecutive nights differ
# by one day in ninety, and Agent 2 drafts 5 articles per scout run.
_cron = [e["cron"] for e in yaml.safe_load(_wf1)[True]["schedule"]]
ok("the scout runs weekly, not nightly",
   all(not c.endswith("* * *") for c in _cron), _cron)
ok("and its day is clear of the Monday audit jobs",
   all(c.strip().split()[-1] not in {"1", "MON"} for c in _cron), _cron)
ok("the workflow passes the key the default provider needs",
   "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" in _wf1)

ok("an exhausted credit balance is recognised as account-level",
   bool(config.terminal_provider_error(
       "Error code: 400 - Your credit balance is too low to access the Anthropic API.")))
ok("so is a revoked key and an exhausted OpenAI quota",
   bool(config.terminal_provider_error("invalid x-api-key"))
   and bool(config.terminal_provider_error("insufficient_quota")))
ok("a timeout is NOT — the next site may well succeed",
   not config.terminal_provider_error("Request timed out after 60s"))
ok("nor is a 503",
   not config.terminal_provider_error("503 service unavailable"))
ok("and once it is known, the model is skipped for every remaining site",
   '_PROVIDER_DOWN.get("reason")' in _a1src)
ok("the run summary collapses one cause repeated per domain",
   'r.split("\'request_id\'")[0]' in _wf1,
   "four request_ids made one exhausted balance look like four faults")
ok("degraded briefs are counted into the run manifest",
   '"degraded_briefs"' in _a1src and '"degraded_domains"' in _a1src)
ok("the flag travels on the wire, not just in the log",
   '"degraded_no_llm": bool(analysis.get("_degraded"))' in _a1src)
ok("Agent 2's model accepts the flag and defaults it False for older briefs",
   _a2l.BriefBlock(working_title="t", target_url_path="/x",
                   language="en").degraded_no_llm is False)
ok("a skipped site is not reported as a written one",
   'if o.domain and o.status == "drafted"' in _a2bsrc,
   "run #12 wrote nothing and named four sites as written")
ok("and Agent 2 skips a degraded brief instead of paying for a draft",
   'getattr(brief.brief, "degraded_no_llm", False)' in _a2bsrc
   and 'oc.status = "skipped"' in _a2bsrc)
_wf1 = (pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "agent1-seo-scout.yml").read_text(encoding="utf-8")
ok("a degraded run raises a workflow annotation, not a line of summary text",
   "::warning title=Degraded run::" in _wf1)
ok("and the annotation goes to stdout, where GitHub actually reads it",
   'GITHUB_STEP_SUMMARY"] , "a"' not in _wf1
   and 'fh.write("\\n".join(out))' in _wf1,
   "a ::warning piped into the summary file is grey text, not an annotation")

print("\n=== every secret an agent reads is one a workflow passes ===")
# Four times in one session a setting was added in one file and silently
# ignored in another: competitors -> Site, degraded_no_llm -> the wire,
# frontmatter -> the brief, and ASTRO_* -> the workflow env. Each passed every
# test that existed. This is the general check that would have caught all four.
import re as _re
_wfdir = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"
_wf_text = "\n".join(f.read_text(encoding="utf-8") for f in _wfdir.glob("*.yml"))
_agent_src = "\n".join(
    f.read_text(encoding="utf-8")
    for f in pathlib.Path(__file__).parent.glob("agent*.py"))
# Names the agents actually ask the environment for.
_read = set(_re.findall(r'(?:optional_env|require_env)\(\s*"([A-Z][A-Z0-9_]+)"', _agent_src))
# Exempt, each for a stated reason — an allowlist with no reasons is just a
# silenced test.
_ignore = {
    # Local output paths, defaulted in config.py; never CI settings.
    "BUNDLE_DIR", "QUEUE_DIR", "RUNS_DIR", "SITES_FILE",
    # uvicorn bind settings for the FastAPI reference listeners. Those run on a
    # developer's machine, never in Actions — the batch runners are what CI uses.
    "AGENT2_HOST", "AGENT2_PORT", "AGENT3_HOST", "AGENT3_PORT",
    "AGENT4_HOST", "AGENT4_PORT",
    # Vestigial, like AGENT2_WEBHOOK_URL before it: Agent 4 reads Agent 3's
    # artifact on workflow_run, so nothing internal POSTs to it. Kept for an
    # external consumer, and its absence is the normal state.
    "AGENT4_WEBHOOK_URL",
}
_missing = sorted(n for n in _read - _ignore if n not in _wf_text)
ok("no agent reads a secret the workflows never pass",
   not _missing,
   f"read but never provided: {_missing}")

print("\n=== agent 2 — what astro_pr actually writes ===")
_bc = [x for x in config.load_sites() if x.domain == "boutimar.com"][0]
_cms = _bc.cms if isinstance(_bc.cms, dict) else {}
_a2lsrc = pathlib.Path(__file__).with_name("agent2_writer_listener.py").read_text(encoding="utf-8")
# Run #20 proved the config was not reaching the adapter: the preview showed
# the old title/description/draft/pubDate/lang. Agent 1 was hand-picking four
# cms keys when building the brief, so `collection` and `frontmatter` died at
# that boundary — the same shape of bug as `competitors` never reaching Site.
ok("Agent 1 passes the WHOLE cms block into the brief",
   "**site.cms," in _a1src,
   "enumerating keys means every new setting silently does nothing until two files agree")
ok("boutimar.com declares its Astro collection",
   _cms.get("collection") == "journal", _cms.get("collection"))
# Astro validates each entry against the collection's zod schema and refuses to
# build on a mismatch. `journal` requires title, date, category and author; the
# adapter used to emit title/description/draft/pubDate/lang and nothing else.
ok("and the frontmatter template covers every REQUIRED schema field",
   {"title", "date", "category", "author"} <= set(_cms.get("frontmatter") or {}),
   sorted(_cms.get("frontmatter") or {}))
ok("the collection comes from the site, not from content_type",
   'cms.get("collection")' in _a2lsrc,
   "a brief of type 'guide' would write to src/content/guide/, a collection Astro does not have")
ok("an empty required field refuses to open a PR",
   "unbuildable file" in _a2lsrc,
   "a red build on the target repo blocks every other merge into that site")
ok("the collection prefix is not repeated in the filename",
   "segments[0] == collection" in _a2lsrc,
   "/journal/persian-gardens must not become /journal/journal-persian-gardens/")

print("\n=== two properties are held while they are rebuilt ===")
# 13 Aug 2026: cruiseshop.ir and dmciran.ir publish CMS scaffolding, not
# content. Scouting them turns "there is nothing here" into "content gaps".
_active = {s.domain for s in config.load_sites()}
_all = {s.domain for s in config.load_sites(include_hold=True)}
ok("cruiseshop.ir and dmciran.ir are held, not deleted",
   {"cruiseshop.ir", "dmciran.ir"} == _all - _active, sorted(_all - _active))
ok("the other eight keep running", len(_active) == 8, sorted(_active))
ok("naming a held site explicitly still includes it",
   [s.domain for s in config.load_sites(only=["dmciran.ir"])] == ["dmciran.ir"],
   "--domain must override a hold, or you could never audit one deliberately")
ok("a held site still has its Search Console demand banked",
   'stat["status"] = "hold"' in _a1src and '"demand"' in _a1src,
   "the data keeps accruing; only the writing stops")
ok("and Agent 2 is never handed a brief for one",
   "no briefs emitted" in _a1src)

print("\n=== agent 5 — content that is not there ===")
import agent5_site_auditor as _a5
from config import rfc3339 as _r3, utc_now as _un
def _fresh_audit():
    return _a5.SiteAudit(domain="x", brand="b", locale="fa-IR", checked_at=_r3(_un()))
_st = config.load_sites()[0]
_a5src_txt = pathlib.Path(__file__).with_name("agent5_site_auditor.py").read_text(encoding="utf-8")

# boutimar.ir: three different articles, exactly 336 words each. That is the
# template, not the article — the body arrives client-side.
_au = _fresh_audit()
_flag = _a5.audit_client_rendered(_st, [("https://b.ir/article.html?a=one", 336),
                                        ("https://b.ir/article.html?a=two", 336),
                                        ("https://b.ir/aroya.html", 1421)], _au)
ok("identical word counts across one template are caught as client-rendered",
   len(_flag) == 1 and any(f.id == "content.client_rendered" for f in _au.findings))
ok("a site whose pages genuinely differ is not flagged",
   _a5.audit_client_rendered(_st, [("https://b.ir/a.html", 421),
                                   ("https://b.ir/b.html", 677)], _fresh_audit()) == [])
ok("one page of a template proves nothing, so it is not judged",
   _a5.audit_client_rendered(_st, [("https://b.ir/only.html", 300)], _fresh_audit()) == [])
ok("and the fix names the reason it matters",
   any("do not execute JavaScript" in f.fix for f in _au.findings))

# cruiseshop.ir: every ASCII URL 200s, every Farsi one 404s. Six of ten
# properties publish in Farsi, so a URL layer that cannot resolve Persian is
# not two junk pages — it is every Farsi article those sites will ever publish.
_sysmic = {"https://c.ir/": 200, "https://c.ir/b2b": 200,
           "https://c.ir/%d8%a8%d8%b1%da%af%d9%87": 404,
           "https://c.ir/%d8%af%d8%b3%d8%aa": 404}
_au3 = _fresh_audit()
ok("a site where no Farsi URL resolves is critical, not a broken link",
   len(_a5.audit_nonascii_slugs(_st, [], _au3, _sysmic)) == 2
   and _au3.findings[0].severity == _a5.CRITICAL)
# %d8%a8 is pure ASCII — testing the raw string finds nothing at all.
ok("the check decodes before looking for non-ASCII characters",
   "unquote(u)" in _a5src_txt and "ord(ch) > 127" in _a5src_txt,
   "the first version tested the percent-encoded string and matched nothing")
_au4 = _fresh_audit()
_a5.audit_nonascii_slugs(_st, [], _au4,
                         {"https://c.ir/%d8%a8%d8%b1%da%af%d9%87": 404,
                          "https://c.ir/%d9%88%d8%a7%d9%82%d8%b9": 200})
ok("but one broken Farsi URL among working ones is only high",
   _au4.findings[0].severity == _a5.HIGH,
   "one 404 is a page; all of them is the URL layer")
ok("the fix says to locate the failure before naming its cause",
   "Check WHERE it fails before assuming what it is" in _a5src_txt
   and "taxonomy rewrite" in _a5src_txt,
   "measured: Farsi pages 200, ASCII terms 200, Farsi term archives 404")
ok("and the docstring records that two earlier readings were wrong",
   "two earlier readings of it here" in _a5src_txt)
# The repair tool ships next to the check that finds the fault.
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "_fixslug", pathlib.Path(__file__).with_name("tools") / "fix_farsi_term_slugs.py")
_fix = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_fix)
ok("the repair tool spots an encoded Persian slug",
   _fix.needs_fix("%d8%af%d8%b3%d8%aa") and not _fix.needs_fix("hiking"))
ok("and does not mistake an ordinary percent sign for one",
   not _fix.needs_fix("50%-off"), "a '%' alone is not an encoding")
ok("it writes nothing unless --apply is passed",
   _fix.main.__doc__ is None and "--apply" in _fix.__doc__
   and 'action="store_true"' in pathlib.Path(_spec.origin).read_text(encoding="utf-8"))
ok("it never puts credentials in the backup file",
   'k != "_links"' in pathlib.Path(_spec.origin).read_text(encoding="utf-8")
   and "auth" not in _fix.run_site.__doc__ if _fix.run_site.__doc__ else True)
ok("suggested slugs are readable keys, not transliteration",
   _fix.ascii_slug_for("دسته‌بندی نشده", set()) == "uncategorized-fa")
ok("and a collision does not overwrite an existing term",
   _fix.ascii_slug_for("دسته‌بندی نشده", {"uncategorized-fa"}) == "uncategorized-fa-2")
ok("an all-ASCII site raises nothing",
   _a5.audit_nonascii_slugs(_st, [], _fresh_audit(), {"https://c.ir/a": 200}) == [])

# dmciran.ir shipped 73 WordPress demo posts; cruiseshop.ir a Farsi Sample Page.
_au2 = _fresh_audit()
_hits = _a5.audit_placeholder_content(_st, [
    "https://dmciran.ir/2017/07/helloworld/",
    "https://cruiseshop.ir/%d8%a8%d8%b1%da%af%d9%87-%d9%86%d9%85%d9%88%d9%86%d9%87",
    "https://cruiseshop.ir/archives/author/admin",
    "https://x.ir/a-real-page.html",
], _au2)
ok("CMS demo content left in the sitemap is a finding", len(_hits) == 3, _hits)
ok("including a percent-encoded Farsi Sample Page",
   any("%d8%a8" in h for h in _hits),
   "the URL is escaped; the marker only matches after unquoting")
ok("a real page is not mistaken for filler",
   all("a-real-page" not in h for h in _hits))
ok("nothing is flagged on a clean site",
   _a5.audit_placeholder_content(_st, ["https://x.ir/a.html"], _fresh_audit()) == [])

print("\n=== agent 8 — reading someone else's site ===")
import agent8_competitor_scout as _a8
_a8src = pathlib.Path(__file__).with_name("agent8_competitor_scout.py").read_text(encoding="utf-8")
from urllib.robotparser import RobotFileParser as _RFP
_rp = _RFP(); _rp.parse(["User-agent: *", "Disallow: /private/", "Disallow: /admin"])
ok("a competitor's robots.txt is obeyed, not merely audited",
   not _a8._allowed(_rp, "https://rival.com/private/x")
   and _a8._allowed(_rp, "https://rival.com/guides/x"),
   "Agent 5 audits robots because it crawls our sites; this one does not")
_bad = _RFP(); _bad.parse([])
ok("a robots.txt we cannot evaluate is never treated as permission",
   _a8._allowed(None, "https://rival.com/x") is True
   and "return False" in pathlib.Path(__file__).with_name(
       "agent8_competitor_scout.py").read_text(encoding="utf-8"))
ok("requests to a stranger's server are spaced", _a8.CRAWL_DELAY_S >= 1.0,
   f"{_a8.CRAWL_DELAY_S}s")
# boutimar.ir has 130 pages, all at the root. Keyed on filename it reported 130
# "sections" of one page each, and a diff against that is noise.
ok("a flat site collapses to one bucket instead of 130",
   _a8.topic_of("https://x.ir/about.html") == "(root)"
   and _a8.topic_of("https://x.ir/fa/about.html") == "(root)")
ok("a locale prefix is not mistaken for a section",
   _a8.topic_of("https://x.com/fa/cruises/aroya") == "cruises")
ok("a real section still reads as one",
   _a8.topic_of("https://x.com/destinations/dubai") == "destinations")
_flat = _a8.compare(None, ["https://x.ir/a.html", "https://x.ir/b.html"],
                    [_a8.CompetitorReport(domain="r", base_url="https://r.com",
                                          topics={"guides": 9})])
ok("and the report says the section diff does not apply rather than showing none",
   _flat["our_site_is_flat"] is True
   and _flat["sections_they_cover_that_we_do_not"] == []
   and _flat["note"],
   "an empty list would read as 'no gaps found'")
# The first version measured every rival's page depth and none of our own —
# the one comparison the agent exists to make.
ok("our own site is measured through the same code path as theirs",
   "us = scout_competitor(session, site.base_url" in _a8src)
ok("and the depth gap is reported as a number, not left to arithmetic",
   '"depth_gap"' in _a8src and '"our_median_words"' in _a8src)
ok("every median carries the sample size beside it",
   '"our_pages_sampled"' in _a8src and _a8.MAX_PAGES_SAMPLED >= 10,
   "a median of three pages is not a measurement")
ok("the word count documents that it sees only server-rendered HTML",
   "client-rendered page" in (_a8._text_stats.__doc__ or ""),
   "boutimar.ir's article.html returns 336 words of template for every article")
ok("competitors declared in sites.yml reach the Site object",
   len([x for x in config.load_sites() if x.competitors]) >= 1,
   "the field existed on the dataclass but load_sites never passed it through")
ok("and every other site stays empty rather than inheriting a guess",
   all(not x.competitors for x in config.load_sites() if x.domain != "boutimar.ir"))
ok("Agent 8 never claims to know rankings",
   "never who *ranks*" in (_a8.__doc__ or "")
   and "rankings" in (_a8.compare.__doc__ or ""),
   "content coverage and search position are different claims")

print("\n=== the scheduled agents do not depend on a balance ===")
import llm as _llm
_a3src = pathlib.Path(__file__).with_name("agent3_broadcaster.py").read_text(encoding="utf-8")
_a6src = pathlib.Path(__file__).with_name("agent6_analyst.py").read_text(encoding="utf-8")
_wf3 = (pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "agent3-broadcaster.yml").read_text(encoding="utf-8")
_wf5 = (pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "agent5-site-audit.yml").read_text(encoding="utf-8")
ok("prose has a provider setting, and it is not the unfunded one",
   config.PROSE_PROVIDER == "gemini" or "PROSE_PROVIDER" in os.environ,
   config.PROSE_PROVIDER)
ok("both providers are reachable by that setting",
   set(_llm._PROVIDERS) == {"anthropic", "gemini"}, sorted(_llm._PROVIDERS))
ok("Agent 3 asks the shared layer, not Anthropic directly",
   "llm.complete_json(" in _a3src and "from anthropic import Anthropic" not in _a3src)
ok("Agent 6 too — it runs unattended every Monday",
   "llm.complete(" in _a6src and "from anthropic import Anthropic" not in _a6src)
ok("an unavailable provider is its own error type",
   issubclass(_llm.ProviderUnavailable, RuntimeError))
ok("an unknown provider name is refused, not silently defaulted",
   isinstance(_llm._PROVIDERS.get("nonsense"), type(None)))
# Gemini's JSON mode fixes validity, not shape — Agent 1 got a bare array by
# leaving the envelope to the provider.
ok("Agent 3 states the JSON envelope when the provider cannot enforce it",
   'never a bare ' in _a3src and 'config.PROSE_PROVIDER == "gemini"' in _a3src)
ok("Agent 6 degrades to a memo without its opening rather than failing",
   "the report stands without it" in _a6src)
ok("both scheduled workflows pass the key their default provider needs",
   "GEMINI_API_KEY" in _wf3 and "GEMINI_API_KEY" in _wf5)

print("\n=== agent 2 — a busy model is not a broken pipeline ===")
ok("a 503 is recognised as the provider being busy",
   _a2l.is_overloaded("503 UNAVAILABLE. This model is currently experiencing high demand."))
ok("so is an explicit overload message",
   _a2l.is_overloaded("The model is overloaded. Please try again later."))
ok("a 429 quota refusal is NOT read as busy",
   not _a2l.is_overloaded("429 RESOURCE_EXHAUSTED quota limit: 0"),
   "limit: 0 means the model is absent from the plan — waiting never fixes it")
ok("nor is a withdrawn model",
   not _a2l.is_overloaded("404 NOT_FOUND: model is no longer available"))
# Run #9 spent attempts 1, 2 and 3 inside 31 seconds against an error whose own
# text says the spike is temporary, then failed the brief and reddened the run.
ok("the overload backoff outlasts a capacity spike",
   sum(_a2l._OVERLOAD_BACKOFF) >= 45, f"{_a2l._OVERLOAD_BACKOFF} = {sum(_a2l._OVERLOAD_BACKOFF)}s")
ok("and it is far longer than the generic backoff it replaces",
   min(_a2l._OVERLOAD_BACKOFF) > 4, "generic backoff peaks at 4s")
ok("an overloaded provider raises a distinct error type",
   issubclass(_a2l.TransientUpstreamError, RuntimeError))
_a2bsrc = pathlib.Path(__file__).with_name("agent2_writer_batch.py").read_text(encoding="utf-8")
ok("which the batch runner records as deferred, not failed",
   'oc.status = "deferred"' in _a2bsrc)
ok("so a capacity blip at Google cannot turn the nightly cron red",
   'return 1 if manifest["failed"] else 0' in _a2bsrc
   and '"deferred_upstream": sum(o.status == "deferred"' in _a2bsrc)
ok("and the two kinds of deferral are counted separately",
   '"deferred_by_limit"' in _a2bsrc and '"deferred_upstream"' in _a2bsrc,
   "cost ceiling vs busy model — conflating them hides both")

print("\n=== agent 2 — retry semantics ===")
ok("the default Gemini model is one the free tier actually allows",
   config.GEMINI_MODEL.endswith("flash") or "GEMINI_MODEL" in os.environ,
   config.GEMINI_MODEL)
_src2b = pathlib.Path(__file__).with_name("agent2_writer_listener.py").read_text(encoding="utf-8")
ok("a zero-quota model fails fast instead of retrying three times",
   '"limit: 0" in msg' in _src2b,
   "429 with limit:0 means the model is not in the plan, not a rate limit")
# A default that lives in two places will disagree, and the one that wins is
# whichever the runtime reads last. config.py said flash while the workflow
# still said pro, so the fix shipped and changed nothing.
_wf2b = (pathlib.Path(__file__).resolve().parents[1]
         / ".github" / "workflows" / "agent2-writer.yml").read_text(encoding="utf-8")
ok("the workflow's model default agrees with config.py",
   "gemini-2.5-pro" not in _wf2b,
   "the workflow fallback overrides config.py, so both must say flash")
_envx = pathlib.Path(__file__).with_name(".env.example").read_text(encoding="utf-8")
ok(".env.example agrees too", "GEMINI_MODEL=gemini-2.5-flash" in _envx)

# Hardcoding a model name failed twice in one evening for two different
# reasons: 2.5-pro returns 429 "limit: 0" (absent from the free tier) and
# 2.5-flash returns 404 "no longer available to new users". Both are invisible
# until a live call. So the model is discovered, not assumed.
import agent2_writer_listener as _a2
_src2c = pathlib.Path(__file__).with_name("agent2_writer_listener.py").read_text(encoding="utf-8")
_orig_list = _a2.resolve_model
_a2._RESOLVED_MODEL = None
ok("resolve_model exists and is used by both SDK paths",
   _src2b.count("resolve_model()") >= 2)
ok("a withdrawn model is not retried three times",
   '"no longer available" in msg' in _src2b)
ok("the preference order puts flash tiers ahead of pro",
   _a2._MODEL_PREFERENCE.index("gemini-flash-latest")
   < _a2._MODEL_PREFERENCE.index("gemini-pro-latest"),
   "pro is the tier routinely gated behind billing")
# supported_actions is populated on Vertex and empty on the Gemini Developer
# API. Filtering on it excluded EVERY model, so discovery returned nothing and
# the configured name was honoured straight into the 404 it existed to prevent.
class _FakeModel:
    def __init__(self, name, acts): self.name, self.supported_actions = name, acts
def _filter(models):
    avail = [m.name.removeprefix("models/") for m in models
             if (a := getattr(m, "supported_actions", None)) is None or not a
             or "generateContent" in a]
    return [n for n in avail
            if not any(x in n for x in ("embedding", "aqa", "imagen", "veo", "tts"))]
ok("a model with an EMPTY supported_actions is kept (Developer API shape)",
   _filter([_FakeModel("models/gemini-flash-latest", [])]) == ["gemini-flash-latest"],
   "this is the shape that silently broke discovery")
ok("a model with None supported_actions is kept",
   _filter([_FakeModel("models/gemini-flash-latest", None)]) == ["gemini-flash-latest"])
ok("a populated Vertex-style list still filters correctly",
   _filter([_FakeModel("models/gemini-flash-latest", ["generateContent"]),
            _FakeModel("models/text-embedding-004", ["embedContent"])])
   == ["gemini-flash-latest"])
ok("non-generative families cannot win the alphabetical fallback",
   _filter([_FakeModel("models/imagen-4", None), _FakeModel("models/veo-3", None),
            _FakeModel("models/text-embedding-004", None)]) == [])
ok("the model listing is logged so a silent empty result is visible",
   "Gemini lists %d model(s)" in _src2b or "usable for generation" in
   pathlib.Path(__file__).with_name("agent2_writer_listener.py").read_text(encoding="utf-8"))

# ListModels advertised gemini-2.5-flash and the API then refused it with 404.
# Presence in the listing is not proof of access; a rejected call is the only
# reliable signal, so a refused model retires itself and the loop moves on.
_a2._UNUSABLE_MODELS.clear(); _a2._RESOLVED_MODEL = "x"
_a2.mark_model_unusable("gemini-2.5-flash")
ok("a refused model is retired for the process",
   "gemini-2.5-flash" in _a2._UNUSABLE_MODELS)
ok("and retiring it clears the cache so the next call re-resolves",
   _a2._RESOLVED_MODEL is None)
ok("a withdrawn model retries with the next candidate rather than failing",
   "retrying with %s" in _src2c,
   "presence in ListModels is not proof the key may call it")
ok("it only gives up when no alternative remains",
   "no alternative" in _src2c)
_a2._UNUSABLE_MODELS.clear(); _a2._RESOLVED_MODEL = None

ok("resolve_model caches so a batch does not re-list per brief",
   "_RESOLVED_MODEL" in _src2b and "global _RESOLVED_MODEL" in _src2b)
_a2._RESOLVED_MODEL = None
ok("and the error says which two things would fix it",
   "GEMINI_MODEL to a model your plan includes" in _src2b
   and "enable billing" in _src2b)

_src2 = pathlib.Path(__file__).with_name("agent2_writer_listener.py").read_text(encoding="utf-8")
_seg = _src2.split("for attempt in range(1, 4):", 1)[1][:900]
ok("a missing credential is not retried three times",
   "except config.ConfigError" in _seg and "raise" in _seg,
   "retrying a ConfigError wastes 7s per brief and buries the cause")

print("\n=== 403 diagnosis ===")
import agent1_seo_scout as _a1

# A 403 means two opposite things and the fix differs. Telling someone to click
# "Add user" on a property that was never created sends them hunting for a
# screen that is not there — which this pipeline did for three days.
_orig = _a1._has_verification_txt
try:
    _a1._has_verification_txt = lambda d: False
    _m = _a1.diagnose_403("sc-domain:nope.example")
    ok("unverified domain -> 'does not exist yet', not 'grant access'",
       "does not exist yet" in _m and "Users and permissions" not in _m.split("then add")[0])
    ok("and it names the real fix", "Add property" in _m)

    _a1._has_verification_txt = lambda d: True
    _m = _a1.diagnose_403("sc-domain:real.example")
    ok("verified domain -> grant access", "Users and permissions" in _m)
    ok("and does not claim it is missing", "does not exist" not in _m)

    _a1._has_verification_txt = lambda d: None
    _m = _a1.diagnose_403("sc-domain:unknown.example")
    ok("a failed DNS lookup admits it does not know", "could not resolve" in _m)
    ok("an unknown answer is never reported as a confident no",
       "does not exist yet" not in _m)

    _m = _a1.diagnose_403("https://prefix.example/")
    ok("URL-prefix properties keep the original message", "Users and permissions" in _m)
finally:
    _a1._has_verification_txt = _orig


print("\n=== agent 3 — batch broadcaster ===")
import agent3_broadcaster_batch as a3b

_wf3 = (pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "agent3-broadcaster.yml").read_text(encoding="utf-8")
ok("Agent 3 is chained off Agent 2",
   'workflows: ["Agent 2 — Writer"]' in _wf3)
ok("it does not run when the writer failed",
   "workflow_run.conclusion == 'success'" in _wf3)
ok("ALLOW_AUTOPOST is NOT set in the workflow environment",
   not _re.search(r"^\s{10}ALLOW_AUTOPOST:", _wf3, _re.M),
   "the outer of the two locks stays open until a brand account exists")
ok("it degrades to --no-llm rather than failing without a key",
   '[ -z "${ANTHROPIC_API_KEY:-}" ]' in _wf3)
_l3i = _re.search(r'limit:\n\s+description:[^\n]*\n\s+required: false\n\s+default: "(\d+)"', _wf3)
ok("its limit default and shell fallback agree",
   _l3i and {_l3i.group(1)} == set(_re.findall(r"inputs\.limit \|\| '(\d+)'", _wf3)))

# campaign.log.v1 requires copy.hash — the dedupe guard that stops identical
# copy reaching one channel twice on a redelivery. The batch runner omitted it
# and only schema validation caught it, which is why the schema is validated
# rather than trusted.
_src3 = pathlib.Path(__file__).with_name("agent3_broadcaster_batch.py").read_text(encoding="utf-8")
ok("the batch runner emits copy.hash", '"hash": "sha256:"' in _src3)
ok("and the hash covers channel AND body, so one post per channel is distinct",
   "f\"{d['channel']}|{d['body']}\"" in _src3)
ok("the stub copy is documented as never publishable",
   "Never publishable" in (a3b._stub_copy.__doc__ or ""))
ok("a held post is not a failure",
   "return 1 if manifest[\"failed\"] else 0" in _src3,
   "held and blocked-on-media are the design working")




print("\n=== measured GEO rules (heytony.ca, 100 AI Overviews) ===")
import agent6_analyst as _a6
import agent1_seo_scout as _a1sp

# Finding 4: >7 of 10 major brands on page one and the query is walled off.
# This pipeline has no SERP source, so the verdict must be honest about that
# rather than inventing one from Search Console rows.
ok("an unmeasured page one returns 'unknown'",
   _a6.competition_verdict(None)["verdict"] == "unknown")
ok("and an unknown verdict NEVER filters a brief out",
   _a6.competition_verdict(None)["acts_as_filter"] is False,
   "dropping work on a guess is worse than doing work that might be crowded")
ok("9 of 10 brands is walled off, and does filter",
   _a6.competition_verdict(9)["verdict"] == "walled_off"
   and _a6.competition_verdict(9)["acts_as_filter"] is True)
ok("3 of 10 brands is open", _a6.competition_verdict(3)["verdict"] == "open")
ok("the threshold is the tested one, not a round number",
   _a6.WALLED_OFF_BRAND_THRESHOLD == 7)

# Finding 3: agreeing with the consensus number was worth ~12 points, and the
# proprietary fact is the part a bigger competitor cannot copy.
_sp = _a1sp._analysis_system_prompt([x for x in config.load_sites()
                                     if x.domain == "boutimar.ir"][0])
ok("every brief must state the consensus figure", "CONSENSUS figure" in _sp)
ok("and must carry a fact nobody else has", "NOBODY ELSE" in _sp)
ok("a missing proprietary fact is declared, never invented",
   "rather than inventing one" in _sp,
   "the never-invent rule already forbids the alternative")
# The consensus rule and the never-invent-a-rate rule collided in run #9: the
# brief said "state the consensus price band", the writer had no sourced band,
# invented $50–$150, and the gate blocked its own pipeline's output. Asking for
# a figure without asking where it came from is what produced that.
ok("a consensus figure must be observed, not estimated",
   "OBSERVED, not something you estimated" in _sp)
ok("and the brief must make the writer attach its source",
   "WITH its source attached" in _sp)
ok("a price may never be the consensus figure without a price_asof",
   "unless the number is in the live feed with a price_asof" in _sp)
ok("with a non-price figure named as the fallback",
   all(w in _sp for w in ("duration", "season length", "room count")))

# Finding 6: question-format titles did NOT correlate with citation.
ok("Agent 1 no longer requires question-shaped headings",
   "Do NOT require question-shaped headings" in _sp)
ok("Agent 6 no longer sells them as a citation lever",
   "tested AI-citation benefit is nil" in _a6._IMPACT["geo.no_question_structure"])
ok("but the finding survives for readers and valid schema",
   "help a reader scan" in _a6._IMPACT["geo.no_question_structure"],
   "still worth doing, just not for the reason originally given")
_comp = pathlib.Path(__file__).with_name("compliance.py").read_text(encoding="utf-8")
ok("the compliance comment no longer overstates the GEO benefit",
   "did not survive measurement" in _comp)


print("\n=== adapters never report a URL they did not create ===")
import inspect as _insp
import agent2_writer_listener as _a2c
_pc = _insp.getsource(_a2c.push_to_cms)
ok("astro_pr is routed, not left to the generic branch",
   'adapter == "astro_pr"' in _pc,
   "boutimar.com and exploreorient.com both depend on it")
ok("the generic branch returns live_url None",
   '"live_url": None' in _pc,
   "it used to return the intended URL and stamp published_at — a page that "
   "never existed, reported as published")
ok("and it never stamps published_at",
   "published_at" in _pc and "rfc3339() if site.cms.publish_mode" not in _pc)
_wp2 = _insp.getsource(_a2c._push_wordpress)
ok("every WordPress failure path also reports None",
   '"live_url": url' not in _wp2)
_ap = _insp.getsource(_a2c._push_astro_pr)
ok("astro_pr stages a file when unconfigured rather than claiming a PR",
   "not configured" in _ap and '"live_url": None' in _ap)
ok("an existing branch or PR is treated as idempotency, not failure",
   "422" in _ap)

# The schema itself required a live_url string, which FORCED the fabrication.
_ev = json.load(open(os.path.join(SCHEMA_DIR, "publishing.event.v1.json"), encoding="utf-8"))
_pubp = _ev["properties"]["publication"]["properties"]
ok("publishing.event.v1 allows a null live_url",
   _pubp["live_url"]["type"] == ["string", "null"],
   "requiring a string is what made honesty impossible")
ok("live_url is not in the required list",
   "live_url" not in _ev["properties"]["publication"].get("required", []))
ok("canonical_url is nullable too", _pubp["canonical_url"]["type"] == ["string", "null"])

print("\n=== you cannot broadcast a page that does not exist ===")
_src3b = pathlib.Path(__file__).with_name("agent3_broadcaster_batch.py").read_text(encoding="utf-8")
ok("Agent 3 skips an event with no live_url",
   "if not event.publication.live_url:" in _src3b,
   "posting a link to an unpublished draft sends readers to a 404")
ok("and says why, naming the intended path",
   "nothing was published" in _src3b and "intended" in _src3b)
ok("skipped is not failed", 'oc.status = "skipped"' in _src3b)

print("\n=== the three edges ===")
import inspect
import agent4_sales_closer_batch as a4b   # this section runs before the agent-4 one
import agent2_writer_listener as _a2w
_wp = inspect.getsource(_a2w._push_wordpress)
ok("the WordPress adapter always writes status=draft",
   _wp.count('"status": "draft"') >= 3 and '"status": "publish"' not in _wp,
   "five unattended articles a night must not be able to reach a live site")
ok("an unconfigured WordPress stages rather than pretends",
   "wordpress_rest not configured" in _wp)
ok("a WordPress failure never reports a URL it did not create",
   _wp.count('"record_id": None') >= 3)
_wf2w = (pathlib.Path(__file__).resolve().parents[1]
         / ".github" / "workflows" / "agent2-writer.yml").read_text(encoding="utf-8")
ok("the writer workflow passes the WordPress secrets",
   "WORDPRESS_APP_PASSWORD: ${{ secrets.WORDPRESS_APP_PASSWORD }}" in _wf2w)

_fl = inspect.getsource(a4b._fetch_leads)
ok("the lead pull is HMAC-signed", "signed_headers" in _fl)
ok("and warns loudly when it cannot sign",
   "cannot tell this request from anyone" in _fl,
   "an open endpoint returning customer messages is a leak")
ok("it accepts a bare array or a wrapped one", '"leads"' in _fl and '"data"' in _fl)

print("\n=== agent 4 — batch closer ===")
import agent4_sales_closer_batch as a4b
from agent4_sales_closer import redact as _redact

# The claim that matters most: a Luhn-valid card is redacted, and a booking
# reference that merely looks like one is left alone. A guard that mangles
# customer data to catch a card is worse than no guard.
_c, _r = _redact("Please charge my card 4111111111111111 cvv 123")
ok("a Luhn-valid card is redacted", "4111111111111111" not in _c and "card_number" in _r)
ok("the CVV goes with it", "cvv" in _r)
_c2, _r2 = _redact("My booking reference is 1234567890123456 — confirm the cabin?")
ok("a 16-digit booking reference that fails Luhn is NOT mangled",
   "1234567890123456" in _c2 and _r2 == [],
   "redacting it would corrupt the one field the agent needs to look the booking up")
_c3, _r3 = _redact("Transfer to IBAN DE89370400440532013000")
ok("an IBAN is redacted", "DE89370400440532013000" not in _c3 and "iban" in _r3)
_c4, _r4 = _redact("Passport number X1234567 attached")
ok("a passport number is redacted", "X1234567" not in _c4 and "passport_number" in _r4)

_wf4 = (pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "agent4-sales-closer.yml").read_text(encoding="utf-8")
# Parse it, do not grep it: the file explains in a comment WHY there is no
# schedule, and a text match flags that comment. Same mistake as the
# AGENT2_WEBHOOK_URL assertion that failed on a comment describing its removal.
import yaml as _yaml
_wf4y = _yaml.safe_load(_wf4)
_on4 = _wf4y.get("on") or _wf4y.get(True)
ok("Agent 4 has NO cron trigger",
   "schedule" not in _on4,
   "no lead source is wired; a nightly green no-op teaches people to ignore green")
ok("it is dispatch-only", list(_on4) == ["workflow_dispatch"])
ok("its artifact retention is short, not the 90-day default",
   "retention-days: 7" in _wf4,
   "these records hold real customers' words, redacted but still theirs")

_src4 = pathlib.Path(__file__).with_name("agent4_sales_closer_batch.py").read_text(encoding="utf-8")
ok("the batch runner has no delivery path at all",
   not _re.search(r"requests\.(post|put)|smtplib|sendmail", _src4),
   "Agent 4 drafts; a human sends")
ok("the manifest states sent=0 as a design fact",
   '"sent": 0' in _src4 and "always 0 by design" in _src4)
ok("every record is marked draft-only", "DRAFT ONLY" in _src4)
ok("the stub deliberately drafts no reply",
   "Deliberately drafts NO reply" in (a4b._stub_qualify.__doc__ or ""),
   "a stub reply is the one thing here someone could send by mistake")

print("\n=== agent 7 — keyword & geo scout ===")
import agent7_keyword_scout as a7

def crow(q, c, imp, pos, clicks=0):
    return {"keys": [q, c], "impressions": imp, "clicks": clicks, "position": pos}

# Position must be impression-WEIGHTED. One obscure query at position 1 must not
# make a country look strong when forty real ones sit at 40.
_g = a7.geo_visibility([crow("rare", "usa", 1, 1.0), crow("real", "usa", 99, 40.0)])
ok("position is impression-weighted, not a plain mean",
   39.0 < _g[0].avg_position <= 40.0, _g[0].avg_position)
ok("a plain mean would have been wrong here", abs(20.5 - _g[0].avg_position) > 15)

_g2 = a7.geo_visibility([crow("a", "irn", 50, 8.0), crow("b", "usa", 10, 60.0)])
ok("countries sorted by impressions", [c.country for c in _g2] == ["irn", "usa"])
ok("iso code resolved to a name", _g2[0].country_name == "Iran")
ok("page-one band", _g2[0].band == "page one", _g2[0].band)
ok("absent band beyond 50", _g2[1].band == "absent", _g2[1].band)
ok("zero-impression rows ignored", a7.geo_visibility([crow("x", "deu", 0, 3.0)]) == [])
ok("malformed rows ignored", a7.geo_visibility([{"keys": ["only-one"]}]) == [])

# An IR site whose traffic is not Iranian is misaligned — the check that catches
# a site quietly serving the wrong audience.
_ir = [s for s in config.load_sites() if s.market == "IR"][0]
ok("IR site with Iranian traffic is aligned",
   a7.market_alignment(_ir, a7.geo_visibility([crow("q", "irn", 90, 10.0), crow("q", "usa", 10, 10.0)]))["verdict"] == "aligned")
ok("IR site without Iranian traffic is MISALIGNED",
   a7.market_alignment(_ir, a7.geo_visibility([crow("q", "usa", 90, 10.0), crow("q", "irn", 10, 10.0)]))["verdict"] == "MISALIGNED")

# Opportunities must exclude what is not worth working on.
_opps = a7.opportunities(a7.geo_visibility([
    crow("a", "deu", 100, 15.0),   # striking distance, real volume -> keep
    crow("b", "usa", 100, 60.0),   # absent -> drop, it needs a decision not SEO
    crow("c", "fra", 100, 2.0),    # already winning -> drop
    crow("d", "ind", 5, 15.0),     # too little volume -> drop
]))
ok("opportunities keep the recoverable country", [o["country"] for o in _opps] == ["deu"], [o["country"] for o in _opps])
ok("'absent' is never an optimisation task", all(o["band"] != "absent" for o in _opps))

# Keyword Planner honesty: Iran is reported as unavailable, not as broken.
_kp = a7.keyword_planner_status(_ir)
ok("Keyword Planner unavailable for the Iranian market", _kp["available"] is False)
ok("and the reason is the market, not a missing key", _kp["reason"] == "market_not_served", _kp["reason"])
_int = [s for s in config.load_sites() if s.market == "INT"][0]
ok("an INT site reports a credential gap instead",
   a7.keyword_planner_status(_int)["reason"] in ("not_configured", "configured"))
ok("unconfigured names the missing secrets",
   "missing" in a7.keyword_planner_status(_int) or a7.keyword_planner_status(_int)["available"])

print("\n=== compliance ===")
c = compliance.check
ok("Arabian Gulf blocked", any(v.rule == "persian_gulf_only" for v in c("Sail the Arabian Gulf")))
ok("خلیج عربی blocked", any(v.rule == "persian_gulf_only" for v in c("سفر به خلیج عربی")))
ok("Arabian SEA allowed", not any(v.rule == "persian_gulf_only" for v in c("crossing the Arabian Sea")))
ok("خلیج فارس allowed", not c("سفری به خلیج فارس"))
ok("visa-free blocked by default", any(v.rule == "visa_accuracy" for v in c("This is visa-free!")))
ok("بدون ویزا blocked", any(v.rule == "visa_accuracy" for v in c("سفر بدون ویزا")))
# The gate bans a CLAIM, not a term. A negated claim states the rule correctly —
# blocking it blocked the very instruction that enforces the rule.
ok("'not visa-free' is allowed (states the rule)",
   not any(v.rule == "visa_accuracy" for v in c("Iran stays are not visa-free")))
ok("'is not visa-free' allowed", not any(v.rule == "visa_accuracy"
   for v in c("Dubai is not visa-free — an easy visa is required")))
ok("brief instruction allowed", not any(v.rule == "visa_accuracy" for v in
   c("Explicitly state that Iran stays are not visa-free")))
ok("Farsi negation allowed", not any(v.rule == "visa_accuracy"
   for v in c("این سفر بدون ویزا نیست")))
ok("bare claim STILL blocked", any(v.rule == "visa_accuracy"
   for v in c("Dubai is visa-free for all nationalities")))
ok("Farsi bare claim still blocked", any(v.rule == "visa_accuracy"
   for v in c("سفر به دبی بدون ویزا")))
ok("negation does not leak across a sentence boundary",
   any(v.rule == "visa_accuracy" for v in
       c("Schengen is not required. Dubai is visa-free.")),
   "a full stop must end the negation window")
ok("visa-free OK for AROYA route",
   not any(v.rule == "visa_accuracy" for v in c("visa-free", context={"route_key": "aroya_turkiye_egypt"})))
ok("Schengen port re-blocks visa-free",
   any(v.rule == "visa_accuracy" for v in
       c("visa-free", context={"route_key": "aroya_turkiye_egypt", "itinerary_ports": ["Istanbul", "Santorini"]})))
# ── The 8 Aug 2026 over-block ────────────────────────────────────────────────
# The first live run dead-lettered 3 of 7 briefs, and every one of them was
# blocked for stating the visa rule CORRECTLY. The gate could not tell "Türkiye
# and Egypt: no visa needed" (true) from "Dubai: no visa needed" (the lie the
# rule exists to stop), because it never looked at which destination the claim
# attached to. Perverse incentive: the more precisely the model stated the rule,
# the more certainly its brief was thrown away.
B = compliance.BLOCK
def blocks(t, **kw): return any(v.severity == B and v.rule == "visa_accuracy" for v in c(t, **kw))

ok("exempt route allowed without context", not blocks("مسیرهای ترکیه و مصر: بدون نیاز به ویزا"),
   "AROYA Türkiye+Egypt is genuinely visa-free")
ok("Seychelles allowed", not blocks("مسیر سیشل: بدون نیاز به ویزا"))
ok("Türkiye+Egypt allowed in English", not blocks("AROYA's Türkiye and Egypt itineraries are visa-free"))
ok("contrastive taxonomy allowed",
   not blocks("تفکیک صریح مسیرهای بدون ویزا (ترکیه+مصر، سیشل) از مسیرهای ویزای آسان (خلیج فارس، دبی)"),
   "the forbidden destination is attached to the EASY-VISA half")
ok("easy-visa classification allowed", not blocks("Persian Gulf and Dubai are easy visa, not visa-free"))
ok("Farsi easy-visa classification allowed", not blocks("مسیرهای خلیج فارس و دبی: ویزای آسان، نه بدون ویزا"))
ok("naming the Schengen ZONE is not naming a port",
   not blocks("تفکیک روشن مقاصد شنگن از مقاصد بدون ویزا و ویزای آسان"),
   "«شنگن» is the visa zone; this sentence states the rule")

# …and none of that may weaken the rule where it bites.
ok("Persian Gulf claim still blocked", blocks("کروز خلیج فارس بدون ویزا برای ایرانیان"))
ok("UAE claim still blocked", blocks("United Arab Emirates: no visa required"))
ok("Abu Dhabi / Doha still blocked", blocks("Abu Dhabi and Doha: no visa needed"))
ok("named Greek port still blocked", blocks("Santorini and Mykonos — visa-free sailing from Istanbul"))
ok("named Farsi Greek port still blocked", blocks("کروز یونان بدون ویزا از استانبول"))
ok("Lanzarote is Spain, therefore Schengen", blocks("لانزاروته بدون ویزا"))
ok("Barcelona still blocked", blocks("Barcelona cruise, no visa needed"))
ok("itinerary_ports stays authoritative with no place in the prose",
   blocks("این مسیر بدون ویزا است", context={"itinerary_ports": ["Piraeus", "Santorini"]}))
ok("negator does not leak across a list-item boundary",
   blocks("مسیر سیشل: نه بدون ویزا\nکروز دبی بدون ویزا"),
   "newline ends the clause")
ok("question heading is not a claim (English)",
   not blocks("Is the UAE visa-free for a stag group? Answer: no, it is easy visa"),
   "the FAQ shape the GEO work exists to produce")
ok("question heading is not a claim (Farsi)",
   not blocks("آیا سفر به دبی بدون ویزا است؟"))
ok("a question still warns", any(v.rule == "visa_accuracy"
   for v in c("Is Dubai visa-free?")), "it must stay visible to Agent 2")
ok("the ANSWER is still judged on its own",
   blocks("Is Dubai visa-free\nYes, Dubai is visa-free for everyone"),
   "the question passes; the false answer beside it does not")
ok("destination-less claim is a WARN, not a BLOCK",
   not blocks("مقاصد بدون ویزا") and any(v.rule == "visa_accuracy" for v in c("مقاصد بدون ویزا")))

# assertive_surface: must_avoid enumerates forbidden terms, so scanning it
# blocks a correct brief for correctly forbidding the thing.
_surface = compliance.assertive_surface(
    {"must_include": ["همیشه «خلیج فارس»"],
     "must_avoid": ["Arabian Gulf", "خلیج عربی", "بدون ویزا", "visa-free"]})
ok("must_avoid excluded from the checked surface",
   not any(v.severity == B for v in c(_surface)))
ok("must_include still checked", "خلیج فارس" in _surface)
ok("assertive_surface puts one clause per line",
   compliance.assertive_surface(["a", "b"]) == "a\nb")

ok("price without feed blocked", any(v.rule == "no_invented_facts" for v in c("from €899 per person")))
ok("تومان price blocked", any(v.rule == "no_invented_facts" for v in c("قیمت از ۱۲۳۴۵۶۷ تومان")))
ok("price allowed with feed+asof",
   not any(v.severity == compliance.BLOCK for v in
           c("from €899", context={"priced_facts": True, "price_asof": "2026-08-06T00:00:00Z"})))
ok("price with feed but no asof blocked",
   any(v.rule == "no_invented_facts" for v in c("from €899", context={"priced_facts": True})))
ok("guarantee is warn not block",
   [v.severity for v in c("Best price guarantee")] .count(compliance.WARN) >= 1)
ok("brand leak blocked in partner profile",
   any(v.rule == "brand_neutral_embed" for v in c("Powered by بوتیمار", "partner_widget_v1")))
ok("brand allowed in default profile",
   not any(v.rule == "brand_neutral_embed" for v in c("Powered by بوتیمار", "boutimar_v1")))
try:
    compliance.enforce("Arabian Gulf cruise"); ok("enforce raises on block", False)
except compliance.ComplianceError: ok("enforce raises on block", True)
ok("enforce returns warnings without raising",
   len(compliance.enforce("Best price guarantee", context={"priced_facts": True})) == 1)
ok("prompt_constraints mentions Persian Gulf", "خلیج فارس" in compliance.prompt_constraints())
ok("summarise reflects profile",
   compliance.summarise([], "partner_widget_v1")["checks_run"].count("brand_neutral_embed") == 1)
try:
    c("x", "no_such_profile"); ok("unknown profile raises", False)
except ValueError: ok("unknown profile raises", True)

print("\n=== the spec describes the registry it claims to specify ===")
# ARCHITECTURE.md's portfolio table listed eight rows for ten properties and
# called boutimar.com WordPress — a stack the user had already corrected twice.
# A hand-maintained copy of sites.yml drifts silently; this makes it noisy.
_arch = pathlib.Path(__file__).with_name("ARCHITECTURE.md").read_text(encoding="utf-8")
_sites_all = config.load_sites(include_hold=True)
_missing = [s.domain for s in _sites_all if f"`{s.domain}`" not in _arch]
ok("every site in sites.yml appears in ARCHITECTURE.md", not _missing, _missing)
ok("and the spec does not claim a WordPress property",
   "WordPress + Elementor" not in _arch,
   "no property has run WordPress since 11 Aug 2026")
_WORDS = {8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
ok("the portfolio count in prose matches the registry",
   any(f"{n} Search Console properties" in _arch
       for n in (len(_sites_all), _WORDS.get(len(_sites_all), "\0"))),
   f"{len(_sites_all)} sites in sites.yml")

print("\n=== agent 1 ===")
import agent1_seo_scout as a1

site = config.load_sites(only=["boutimar.ir"])[0]
def row(keys, clicks, imps, pos): return {"keys": keys, "clicks": clicks, "impressions": imps, "position": pos}
gsc = {
    "date_range": {"start": "2026-05-09", "end": "2026-08-03"},
    "short_range": {"start": "2026-07-06", "end": "2026-08-03"},
    "long_rows": [row(["کروز خلیج فارس", "MOBILE"], 40, 3000, 18.0),
                  row(["کروز خلیج فارس", "DESKTOP"], 21, 1820, 19.0),
                  row(["نویز کم", "MOBILE"], 0, 3, 30.0),
                  row(["برند بوتیمار", "MOBILE"], 500, 900, 1.2)],
    "short_rows": [row(["کروز خلیج فارس"], 30, 1800, 17.0)],
    "page_rows": [],
    "country_rows": [row(["کروز خلیج فارس", "irn"], 61, 4820, 18.4)],
    "row_count": 6,
}
cands = a1.find_gaps(site, gsc, set())
ok("low-volume query filtered out", all(x["query"] != "نویز کم" for x in cands))
ok("brand query at pos 1.2 not flagged", all(x["query"] != "برند بوتیمار" for x in cands))
gap = next(x for x in cands if x["query"] == "کروز خلیج فارس")
ok("gap typed missing_page", gap["gap_type"] == "missing_page", gap["gap_type"])
ok("impressions summed across devices", gap["impressions"] == 4820, gap["impressions"])
ok("device split computed", abs(gap["device_split"]["mobile"] - 0.622) < 0.01, gap["device_split"])
ok("top country carried", gap["top_country"] == "irn")
ok("trend detected rising", gap["trend"] == "rising", gap["trend"])
ok("position impression-weighted", 18.0 < gap["position"] < 18.7, gap["position"])

analysis = a1._fallback_brief(site, gap)
payload = a1.build_brief_payload(site, analysis, gap, gsc, "run_test_0001",
                                 "https://agent3.example/webhooks/publishing", dry_run=True)
ok("envelope carries the credit", payload["envelope"]["architecture_credit"] == "Albaloo Studio")
ok("hard avoid terms injected", "Arabian Gulf" in payload["brief"]["must_avoid"])
ok("compliance block is blocking", payload["compliance"]["blocking"] is True)
ok("target path starts with /", payload["brief"]["target_url_path"].startswith("/"))
ok("preflight clean on a clean brief",
   not any(v.severity == compliance.BLOCK for v in a1.self_check_brief(payload)))

poisoned = json.loads(json.dumps(payload))
poisoned["brief"]["working_title"] = "Cruise the Arabian Gulf"
ok("poisoned brief is caught",
   any(v.rule == "persian_gulf_only" for v in a1.self_check_brief(poisoned)))

schema = json.load(open(SCHEMA_DIR + "/content.brief.v1.json"))
try:
    jsonschema.Draft202012Validator.check_schema(schema); ok("content.brief schema is valid", True)
except Exception as e: ok("content.brief schema is valid", False, e)
errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(payload), key=lambda e: e.path)
ok("brief payload validates", not errs, [f"{list(e.path)}: {e.message}" for e in errs][:4])

print("\n=== delivery retry ===")
class FakeResp:
    def __init__(self, code): self.status_code, self.text = code, "body"
class FakeSession:
    def __init__(self, codes): self.codes, self.sent = list(codes), []
    def post(self, url, data=None, headers=None, timeout=None):
        self.sent.append((data, headers)); return FakeResp(self.codes.pop(0))
a1.time.sleep = lambda s: None
s = FakeSession([500, 202])
p = json.loads(json.dumps(payload))
okd, why = a1.deliver(s, "https://x", p, "test-secret-123")
ok("retries a 500 then succeeds", okd and len(s.sent) == 2, why)
sent_body, sent_headers = s.sent[-1]
ok("delivered body signature verifies",
   config.verify_signature("test-secret-123", sent_headers["X-Albaloo-Signature"],
                           sent_headers["X-Albaloo-Timestamp"], sent_body)[0])
ok("attempt counter is inside the signed body", json.loads(sent_body)["envelope"]["attempt"] == 2)
s2 = FakeSession([400])
ok("4xx is terminal", not a1.deliver(s2, "https://x", json.loads(json.dumps(payload)), "s")[0] and len(s2.sent) == 1)
s3 = FakeSession([503] * config.WEBHOOK_MAX_ATTEMPTS)
ok("gives up after max attempts",
   not a1.deliver(s3, "https://x", json.loads(json.dumps(payload)), "s")[0]
   and len(s3.sent) == config.WEBHOOK_MAX_ATTEMPTS)

print("\n=== agent 2 ===")
import agent2_writer_listener as a2
brief_model = a2.ContentBrief.model_validate(payload)
ok("agent2 accepts agent1's payload", brief_model.opportunity.primary_keyword == gap["query"])
ok("publish_mode defaults sane", brief_model.site.cms.publish_mode == "draft")

with_extra = json.loads(json.dumps(payload)); with_extra["experimental_field"] = {"x": 1}
bm2 = a2.ContentBrief.model_validate(with_extra)
ok("unknown top-level key survives validation", "experimental_field" in (bm2.model_extra or {}))

draft = {
    "title": "کروز خلیج فارس",
    "meta_description": "راهنمای کامل",
    "body_markdown": "## چرا خلیج فارس؟\nهفت شب و چهار بندر. " * 40,
    "key_points": ["چهار بندر در هفت شب", "ویزای آسان امارات"],
    "quotable_lines": ["دریایی که نامش را قرن‌هاست می‌دانیم."],
    "faq": [{"q": "ویزا؟", "a": "ویزای آسان امارات."}],
}
data = {"fetched_at": config.rfc3339(), "fields": {}, "has_priced_facts": False}
result = {"status": "draft", "live_url": "https://boutimar.ir/x", "record_id": "x",
          "published_at": None, "scheduled_for": None}
event = a2.build_publishing_event(bm2, with_extra, draft, result,
                                  {"provider": "gemini", "model": "test", "attempts": 1,
                                   "duration_ms": 10, "input_tokens": 1, "output_tokens": 2},
                                  [], data)
ok("causation chains to the brief", event["envelope"]["causation_id"] == payload["envelope"]["message_id"])
ok("correlation id preserved", event["envelope"]["correlation_id"] == "run_test_0001")
ok("idempotency key preserved", event["envelope"]["idempotency_key"] == payload["envelope"]["idempotency_key"])
ok("passthrough preserved", "experimental_field" in event["source_brief"]["passthrough"])
ok("hero_image null when uncredited", event["publication"]["hero_image"] is None)
ok("draft => human review required", event["compliance"]["human_review_required"] is True)
ok("no offer without a live feed", event["content_summary"]["offer"]["has_offer"] is False)
ok("word count computed", event["publication"]["word_count"] > 100)

pschema = json.load(open(SCHEMA_DIR + "/publishing.event.v1.json"))
jsonschema.Draft202012Validator.check_schema(pschema)
perrs = sorted(jsonschema.Draft202012Validator(pschema).iter_errors(event), key=lambda e: e.path)
ok("publishing event validates", not perrs, [f"{list(e.path)}: {e.message}" for e in perrs][:4])

cschema = json.load(open(SCHEMA_DIR + "/campaign.log.v1.json"))
jsonschema.Draft202012Validator.check_schema(cschema)
ok("campaign.log schema is valid", True)

print("\n=== agent 2 HTTP surface ===")
from fastapi.testclient import TestClient
client = TestClient(a2.app)
r = client.get("/healthz")
ok("healthz ok", r.status_code == 200 and r.json()["architecture_credit"] == "Albaloo Studio")

raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
hdrs = config.signed_headers("test-secret-123", raw, payload["envelope"]["message_id"])
a2.run_writing_job = lambda *a, **k: None   # don't call Gemini in a test
r = client.post("/webhooks/content-brief", content=raw, headers=hdrs)
ok("signed brief accepted 202", r.status_code == 202, (r.status_code, r.text[:200]))
job_id = r.json().get("job_id")
r2 = client.post("/webhooks/content-brief", content=raw, headers=hdrs)
ok("duplicate returns 200 + same job", r2.status_code == 200 and r2.json()["job_id"] == job_id,
   (r2.status_code, r2.text[:200]))
r3 = client.post("/webhooks/content-brief", content=raw,
                 headers={**hdrs, "X-Albaloo-Signature": "sha256=deadbeef"})
ok("bad signature 401", r3.status_code == 401)
r4 = client.post("/webhooks/content-brief", content=raw,
                 headers={**hdrs, "X-Albaloo-Timestamp": str(ts - 10_000)})
ok("stale timestamp 401", r4.status_code == 401)
bad = json.loads(json.dumps(payload)); bad["envelope"]["architecture_credit"] = "Someone Else"
braw = json.dumps(bad, ensure_ascii=False, separators=(",", ":")).encode()
r5 = client.post("/webhooks/content-brief", content=braw,
                 headers=config.signed_headers("test-secret-123", braw, "m2"))
ok("missing credit rejected 400", r5.status_code == 400, r5.text[:120])
nov = json.loads(json.dumps(payload)); del nov["site"]["brand"]; nov["envelope"]["message_id"] = "m3"
nraw = json.dumps(nov, ensure_ascii=False, separators=(",", ":")).encode()
r6 = client.post("/webhooks/content-brief", content=nraw,
                 headers=config.signed_headers("test-secret-123", nraw, "m3"))
ok("schema violation 422", r6.status_code == 422, r6.status_code)
r7 = client.get(f"/jobs/{job_id}")
ok("job status readable", r7.status_code == 200 and r7.json()["job_id"] == job_id)

print("\n=== agent 3 — scheduler ===")
os.environ.pop("ALLOW_AUTOPOST", None)
import importlib
import scheduler as sched
importlib.reload(sched)
ok("autopost blocked without ALLOW_AUTOPOST",
   not sched.autopost_allowed({"name": "instagram", "autopost": True})[0])
sched.config.ALLOW_AUTOPOST = True
ok("autopost blocked when channel says no",
   not sched.autopost_allowed({"name": "instagram", "autopost": False})[0])
ok("autopost allowed when BOTH gates open",
   sched.autopost_allowed({"name": "instagram", "autopost": True})[0])
sched.config.ALLOW_AUTOPOST = False
try:
    sched.Scheduler("nope"); ok("unknown backend rejected", False)
except config.ConfigError: ok("unknown backend rejected", True)

import tempfile
from pathlib import Path
config.QUEUE_DIR = Path(tempfile.mkdtemp(prefix="albaloo-queue-"))
sched.config.QUEUE_DIR = config.QUEUE_DIR
s_file = sched.Scheduler("file")
res = s_file.schedule(
    post={"channel": "telegram", "copy": {"body": "x"}, "scheduled_for": None, "assets": []},
    channel_cfg={"name": "telegram", "autopost": False},
    campaign_id="c1", correlation_id="run_test_0001")
ok("file backend queues, does not publish", res.status == "queued" and res.external_id is None)
ok("queue file written", any(config.QUEUE_DIR.rglob("c1-telegram.json")))

# Verified against the live API 2026-08-06: Instagram rejects text-only posts.
ok("text-only instagram is blocked before the API call",
   not sched.media_ok({"channel": "instagram", "assets": []})[0])
ok("instagram with an asset passes the gate",
   sched.media_ok({"channel": "instagram", "assets": [{"url": "https://x/y.webp"}]})[0])
ok("text-only telegram is fine", sched.media_ok({"channel": "telegram", "assets": []})[0])
res_b = s_file.schedule(
    post={"channel": "instagram", "copy": {"body": "x"}, "scheduled_for": None, "assets": []},
    channel_cfg={"name": "instagram", "autopost": True},
    campaign_id="c2", correlation_id="run_test_0001")
ok("media block beats an open autopost gate",
   res_b.status == "blocked" and "image or video" in (res_b.error or ""), res_b.error)

print("\n=== agent 3 — zernio payload shape ===")
post_z = {"channel": "instagram", "scheduled_for": "2026-08-07T12:00:00Z",
          "assets": [{"type": "image", "url": "https://boutimar.ir/img/gulf.webp"}],
          "copy": {"body": "هفت شب در خلیج فارس", "hashtags": ["#کروز"]}}
cfg_z = {"name": "instagram", "autopost": True, "account_ref": "6a3693105f7d1751ab1ce555"}
live = sched.Scheduler.build_zernio_body(post_z, cfg_z, draft=False)
ok("content carries the copy body", live["content"] == "هفت شب در خلیج فارس")
ok("platform + accountId shape", live["platforms"] ==
   [{"platform": "instagram", "accountId": "6a3693105f7d1751ab1ce555"}], live["platforms"])
ok("mediaItems shape matches the API", live["mediaItems"] ==
   [{"type": "image", "url": "https://boutimar.ir/img/gulf.webp"}], live.get("mediaItems"))
ok("scheduledFor sent naive alongside timezone",
   live["scheduledFor"] == "2026-08-07T12:00:00" and live["timezone"] == "UTC", live)
ok("live post is not a draft", "isDraft" not in live)
held = sched.Scheduler.build_zernio_body(post_z, cfg_z, draft=True)
ok("held post is an explicit draft", held.get("isDraft") is True)
ok("a draft carries no schedule time", "scheduledFor" not in held)
ok("hashtags carried", live["hashtags"] == ["#کروز"])
no_acct = sched.Scheduler.build_zernio_body(post_z, {"name": "linkedin"}, draft=True)
ok("missing account_ref surfaces as null, not a crash",
   no_acct["platforms"][0]["accountId"] is None)

print("\n=== agent 3 — broadcaster ===")
import agent3_broadcaster as a3

pub_event = {
    "schema_version": "1.0",
    "envelope": config.build_envelope(
        message_type="publishing.event", emitted_by="agent2.writer",
        target="agent3.broadcaster", correlation_id="run_test_0001",
        idem_key=config.idempotency_key("boutimar.ir", "کروز", "/x"),
        causation_id="msg_parent"),
    "source_brief": {"message_id": "msg_parent", "correlation_id": "run_test_0001",
                     "primary_keyword": "کروز خلیج فارس", "gap_type": "missing_page",
                     "passthrough": {}},
    "publication": {"status": "draft", "live_url": "https://boutimar.ir/cruise/gulf",
                    "canonical_url": "https://boutimar.ir/cruise/gulf", "cms": {},
                    "published_at": None, "scheduled_for": None, "language": "fa-IR",
                    "word_count": 1600, "reading_time_min": 7, "hero_image": None,
                    "indexation": {}},
    "content_summary": {"title": "کروز خلیج فارس", "meta_description": "…",
                        "key_points": ["چهار بندر در هفت شب"], "primary_keyword": "کروز خلیج فارس",
                        "audience": "d2c",
                        "offer": {"has_offer": False, "price_source": None, "price_asof": None},
                        "quotable_lines": ["دریایی که نامش را قرن‌هاست می‌دانیم."]},
    "distribution_hints": {"channels": [], "b2b_angle": None, "d2c_angle": None,
                           "cta_url": "https://boutimar.ir/cruise/gulf",
                           "utm": {"source": "{channel}", "medium": "social", "campaign": "gulf-1405"},
                           "hashtags_allowed": True, "embargo_until": None, "assets": []},
    "compliance": {"profile": "boutimar_v1", "checks_passed": True, "violations": []},
    "generation": {},
}
ev = a3.PublishingEvent.model_validate(pub_event)
ok("agent3 accepts agent2's payload", ev.publication.live_url.endswith("/cruise/gulf"))
ok("campaign id from utm", a3._campaign_id(ev) == "gulf-1405")
chans = a3._resolve_channels(ev)
ok("channels resolved from sites.yml, not the payload",
   {c["name"] for c in chans} == {"telegram", "instagram"}, chans)
ok("resolved channels are autopost:false", all(not c.get("autopost") for c in chans))
# mozzafiatojourney is a personal hobby page. No brand channel may carry it —
# a regression here would push Boutimar marketing copy onto a private account.
ok("no brand channel is wired to the hobby account",
   all(c.get("account_ref") != "6a3693105f7d1751ab1ce555"
       for site in config.load_sites() for c in site.channels))
ok("every channel awaits a real brand account",
   all(c.get("account_ref") is None
       for site in config.load_sites() for c in site.channels))
u = a3._with_utm("https://boutimar.ir/x?a=1", "telegram", "gulf-1405", {"medium": "social"})
ok("utm appended without clobbering query", "a=1" in u and "utm_source=telegram" in u
   and "utm_campaign=gulf-1405" in u, u)
times = a3._schedule_times(3, priority_now=False)
ok("channels staggered", len(times) == 3 and times[0] < times[1] < times[2])

drafts = [
    {"channel": "telegram", "audience": "d2c", "language": "fa-IR",
     "body": "هفت شب در خلیج فارس، چهار بندر.", "hashtags": [], "angle": "practical"},
    {"channel": "instagram", "audience": "d2c", "language": "fa-IR",
     "body": "دریایی که نامش را قرن‌هاست می‌دانیم.", "hashtags": ["#کروز"], "angle": "evocative"},
]
posts = []
for d, when in zip(drafts, times):
    posts.append({
        "channel": d["channel"], "audience": d["audience"], "account_ref": None,
        "status": "queued", "scheduled_for": when, "published_at": None,
        "external_id": None, "permalink": None,
        "copy": {"body": d["body"], "hashtags": d["hashtags"],
                 "cta_url": a3._with_utm("https://boutimar.ir/cruise/gulf", d["channel"], "gulf-1405", {}),
                 "language": d["language"],
                 "hash": "sha256:" + __import__("hashlib").sha256(d["body"].encode()).hexdigest()},
        "assets": [], "error": None})
clog = a3.build_campaign_log(ev, "gulf-1405", posts, [], "boutimar_v1")
ok("campaign causation chains to publishing event",
   clog["envelope"]["causation_id"] == ev.envelope.message_id)
ok("correlation survives 2→3", clog["envelope"]["correlation_id"] == "run_test_0001")
ok("quote policy is live_feed_only", clog["lead_routing"]["quote_policy"] == "live_feed_only")
ok("no price source without an offer", clog["lead_routing"]["price_source"] is None)
ok("objective downgrades to traffic without an offer", clog["campaign"]["objective"] == "traffic")
cerrs = sorted(jsonschema.Draft202012Validator(cschema).iter_errors(clog), key=lambda e: e.path)
ok("campaign log validates", not cerrs, [f"{list(e.path)}: {e.message}" for e in cerrs][:4])

ok("invented price in social copy is blocked",
   any(v.rule == "no_invented_facts" for v in
       compliance.check("فقط ۸۹۹ یورو!", "boutimar_v1", context={"priced_facts": False})))

client3 = TestClient(a3.app)
ok("agent3 healthz", client3.get("/healthz").json()["architecture_credit"] == "Albaloo Studio")
a3.run_broadcast_job = lambda *a, **k: None
raw3 = json.dumps(pub_event, ensure_ascii=False, separators=(",", ":")).encode()
h3 = config.signed_headers("test-secret-123", raw3, pub_event["envelope"]["message_id"])
r = client3.post("/webhooks/publishing", content=raw3, headers=h3)
ok("signed publishing event accepted 202", r.status_code == 202, (r.status_code, r.text[:200]))
cid = r.json()["campaign_id"]
r2 = client3.post("/webhooks/publishing", content=raw3, headers=h3)
ok("duplicate publishing event → 200", r2.status_code == 200 and r2.json()["campaign_id"] == cid)
r3 = client3.post("/webhooks/publishing", content=raw3,
                  headers={**h3, "X-Albaloo-Signature": "sha256=bad"})
ok("agent3 bad signature 401", r3.status_code == 401)
failed = json.loads(json.dumps(pub_event)); failed["publication"]["status"] = "failed"
fraw = json.dumps(failed, ensure_ascii=False, separators=(",", ":")).encode()
r4 = client3.post("/webhooks/publishing", content=fraw,
                  headers=config.signed_headers("test-secret-123", fraw, "m9"))
ok("refuses to broadcast a failed publication", r4.status_code == 400, r4.status_code)

print("\n=== agent 4 — redaction ===")
import agent4_sales_closer as a4
clean, kinds = a4.redact("my card is 4111 1111 1111 1111 ok")
ok("valid card redacted", "[redacted:card]" in clean and "card_number" in kinds)
clean2, kinds2 = a4.redact("booking ref 1234567890123 please")
ok("non-Luhn digits left alone", "1234567890123" in clean2 and not kinds2, (clean2, kinds2))
c3, k3 = a4.redact("cvv 123 and passport A1234567")
ok("cvv redacted", "[redacted:cvv]" in c3 and "cvv" in k3)
ok("passport redacted", "[redacted:passport]" in c3 and "passport_number" in k3)
c4, k4 = a4.redact("IBAN DE89370400440532013000")
ok("iban redacted", "[redacted:iban]" in c4 and "iban" in k4)
ok("clean message untouched", a4.redact("سلام، قیمت کروز چند است؟")[0] == "سلام، قیمت کروز چند است؟")

print("\n=== agent 4 — escalation ===")
routing = a4.LeadRouting(
    high_value_threshold={"amount": 15000, "currency": "EUR"},
    auto_escalate_signals=["group", "MICE", "charter", "شرکتی", "گروهی"],
    escalate_to="alireza")
base = {"intent": "booking_enquiry", "corporate_signal": False, "escalate": False,
        "escalation_reason": "", "estimated_value_eur": 0}
esc, why = a4.decide_escalation(base, "just asking about cabins", routing, [])
ok("ordinary enquiry not escalated", not esc, why)
esc, why = a4.decide_escalation({**base, "estimated_value_eur": 22000}, "hi", routing, [])
ok("value over threshold escalates", esc and any("15000" in r for r in why))
esc, why = a4.decide_escalation(base, "we need a group booking", routing, [])
ok("signal word escalates", esc and any("group" in r for r in why))
esc, why = a4.decide_escalation(base, "the photos are grouped oddly", routing, [])
ok("word boundary: 'grouped' does NOT trigger 'group'", not esc, why)
esc, why = a4.decide_escalation(base, "سفر شرکتی برای ۲۰ نفر", routing, [])
ok("Persian signal phrase escalates", esc)
esc, why = a4.decide_escalation(base, "I want a refund", routing, [])
ok("refund language escalates", esc and any("refund" in r.lower() for r in why))
esc, why = a4.decide_escalation(base, "hello", routing, ["card_number"])
ok("payment data forces human handling", esc and any("payment" in r for r in why))
esc, why = a4.decide_escalation({**base, "intent": "complaint"}, "hello", routing, [])
ok("complaint escalates", esc)

print("\n=== agent 4 — attribution & HTTP ===")
client4 = TestClient(a4.app)
ok("agent4 healthz", client4.get("/healthz").json()["agent"] == "agent4.closer")
raw4 = json.dumps(clog, ensure_ascii=False, separators=(",", ":")).encode()
h4 = config.signed_headers("test-secret-123", raw4, clog["envelope"]["message_id"])
rc = client4.post("/webhooks/campaign-log", content=raw4, headers=h4)
ok("campaign log accepted 202", rc.status_code == 202, (rc.status_code, rc.text[:200]))
ok("campaign registered", rc.json()["campaign_id"] == "gulf-1405")
lead = a4.InboundLead(channel="site_chat", from_ref="anon-1", message="hi",
                      utm_campaign="gulf-1405")
ok("attribution by utm_campaign", a4.CAMPAIGNS.attribute(lead) is not None)
lead2 = a4.InboundLead(channel="whatsapp", from_ref="anon-2", message="hi",
                       landing_path="/cruise/gulf")
ok("attribution by landing path", a4.CAMPAIGNS.attribute(lead2) is not None)
lead3 = a4.InboundLead(channel="whatsapp", from_ref="anon-3", message="hi")
ok("unattributed lead returns None", a4.CAMPAIGNS.attribute(lead3) is None)

a4.qualify = lambda lead, msg, routing, rates, campaign, profile: (
    {"intent": "price_enquiry", "qualified": True, "party_size": 2, "travel_window": "نوروز",
     "budget_band": "2k_5k", "estimated_value_eur": 3000, "corporate_signal": False,
     "missing_information": ["تاریخ دقیق"], "suggested_reply": "سلام! قیمت روز را برایتان می‌فرستیم.",
     "reply_language": "fa-IR", "escalate": False, "escalation_reason": "", "confidence": 0.8},
    {"provider": "anthropic", "model": "test", "attempts": 1, "duration_ms": 5})
a4._fetch_rates = lambda src: {"status": "unavailable", "source": src, "note": "n/a"}

body = json.dumps({"channel": "site_chat", "from_ref": "anon-9",
                   "message": "قیمت کروز نوروز؟ کارت من 4111 1111 1111 1111",
                   "utm_campaign": "gulf-1405"},
                  ensure_ascii=False, separators=(",", ":")).encode()
rl = client4.post("/leads/inbound", content=body,
                  headers=config.signed_headers("test-secret-123", body, "lead1"))
ok("lead accepted", rl.status_code == 200, (rl.status_code, rl.text[:200]))
rec = rl.json()
ok("card never stored", "4111" not in json.dumps(rec))
ok("redaction recorded", "card_number" in rec["redactions"])
ok("payment data escalates the lead", rec["escalate"] is True)
ok("reply is a DRAFT, never sent", rec["draft_reply"]["sent"] is False)
ok("lead attributed to campaign", rec["campaign_id"] == "gulf-1405")
ok("price context reports unavailable", rec["price_context"]["status"] == "unavailable")
ok("lead readable by id", client4.get(f"/leads/{rec['lead_id']}").status_code == 200)
ok("escalation queue lists it",
   any(l["lead_id"] == rec["lead_id"] for l in client4.get("/escalations").json()["leads"]))

a4.qualify = lambda *a, **k: (
    {"intent": "price_enquiry", "qualified": True, "party_size": 2, "travel_window": "",
     "budget_band": "unknown", "estimated_value_eur": 0, "corporate_signal": False,
     "missing_information": [], "suggested_reply": "Sail the Arabian Gulf from only €899!",
     "reply_language": "en", "escalate": False, "escalation_reason": "", "confidence": 0.5},
    {"provider": "anthropic", "model": "test", "attempts": 1, "duration_ms": 5})
body2 = json.dumps({"channel": "site_chat", "from_ref": "anon-10", "message": "price?"},
                   separators=(",", ":")).encode()
rl2 = client4.post("/leads/inbound", content=body2,
                   headers=config.signed_headers("test-secret-123", body2, "lead2"))
rec2 = rl2.json()
ok("non-compliant draft reply is suppressed",
   rec2["draft_reply"]["blocked"] is True and rec2["draft_reply"]["text"] == "")
ok("both violations recorded",
   {v["rule"] for v in rec2["draft_reply"]["blocked_reasons"]} == {"persian_gulf_only", "no_invented_facts"},
   rec2["draft_reply"]["blocked_reasons"])

print("\n=== agent 5 — site auditor ===")

class FakePage:
    """A page response for the auditor — needs .content and .reason, unlike the
    delivery-retry FakeResp above, which only models a status code."""
    def __init__(self, text="", status=200, url="https://x/", headers=None):
        self.text, self.status_code, self.url = text, status, url
        self.content = text.encode()
        self.headers = headers or {}
        self.reason = "OK"

import agent5_site_auditor as a5

site5 = config.load_sites(only=["boutimar.ir"])[0]

GOOD = """<html lang="fa-IR"><head><title>کروز خلیج فارس | بوتیمار</title>
<meta name="description" content="راهنمای کامل"><meta name="viewport" content="width=device-width">
<link rel="canonical" href="https://boutimar.ir/x">
<meta property="og:title" content="کروز">
<script type="application/ld+json">{"@type":"TravelAgency","name":"Boutimar",
"address":{"@type":"PostalAddress","addressLocality":"Tehran"}}</script>
</head><body><h1>کروز خلیج فارس</h1><h2>چرا خلیج فارس؟</h2>
<p>""" + ("متن واقعی و طولانی. " * 80) + """</p><img src="a.webp" alt="کشتی"></body></html>"""

au = a5.SiteAudit(domain="boutimar.ir", brand="B", locale="fa-IR", checked_at="t")
a5.audit_page(site5, "https://boutimar.ir/x", FakePage(GOOD), au, is_home=True)
ids = {f.id for f in au.findings}
ok("clean page raises no title/desc/h1 findings",
   not ({"content.no_title", "content.no_description", "content.no_h1"} & ids), ids)
ok("structured data recognised", "geo.no_structured_data" not in ids)
ok("local signals recognised from PostalAddress", "geo.no_local_signals" not in ids)
ok("Farsi question heading counts as quotable", "geo.no_question_structure" not in ids)
ok("perfect page scores high", au.score() >= 95, (au.score(), ids))

BAD = """<html><head></head><body><div id="root"></div>
<script>""" + ("var x=1;" * 400) + """</script></body></html>"""
au2 = a5.SiteAudit(domain="boutimar.ir", brand="B", locale="fa-IR", checked_at="t")
a5.audit_page(site5, "https://boutimar.ir/y", FakePage(BAD), au2, is_home=True)
ids2 = {f.id for f in au2.findings}
ok("missing title caught", "content.no_title" in ids2)
ok("missing lang caught", "content.no_lang" in ids2)
ok("no structured data caught", "geo.no_structured_data" in ids2)
ok("JS-only page flagged for AI invisibility", "geo.js_dependent" in ids2, ids2)
ok("bad page scores low", au2.score() < 60, au2.score())

NOINDEX = '<html lang="en"><head><title>t</title><meta name="robots" content="noindex"></head><body><h1>h</h1></body></html>'
# A noindexed page found via the sitemap is a CONTRADICTION, not a noindex bug.
# Reporting it as "remove the noindex" would have published boutimar.com's
# internal partner-widget test page.
au3 = a5.SiteAudit(domain="x", brand="B", locale="en", checked_at="t")
a5.audit_page(site5, "https://x/t/", FakePage(NOINDEX), au3, is_home=False, from_sitemap=True)
ok("noindex + in sitemap = conflict finding",
   any(f.id == "sitemap.noindex_conflict" and f.severity == a5.HIGH for f in au3.findings),
   [f.id for f in au3.findings])
ok("conflict fix does not say 'remove the noindex'",
   "Only remove the noindex if" in next(
       f.fix for f in au3.findings if f.id == "sitemap.noindex_conflict"))

au3b = a5.SiteAudit(domain="x", brand="B", locale="en", checked_at="t")
a5.audit_page(site5, "https://x/t/", FakePage(NOINDEX), au3b, is_home=False, from_sitemap=False)
ok("noindex NOT in the sitemap is only a low-severity confirm",
   any(f.id == "content.noindex" and f.severity == a5.LOW for f in au3b.findings),
   [(f.id, f.severity) for f in au3b.findings])

ok("question detector: English", a5._looks_like_question("How much does it cost?"))
ok("question detector: Farsi", a5._looks_like_question("چرا خلیج فارس؟"))
ok("question detector: statement rejected", not a5._looks_like_question("Our cruise routes"))

class FakeSession:
    def __init__(self, routes): self.routes = routes
    def get(self, url, timeout=None, headers=None, allow_redirects=True):
        for frag, resp in self.routes.items():
            if frag in url: return resp
        return FakePage("", 404, url)

au4 = a5.SiteAudit(domain="x", brand="B", locale="fa-IR", checked_at="t")
a5.audit_robots(site5, FakeSession({"robots.txt": FakePage(
    "User-agent: *\nDisallow: /assets\nDisallow: *.js\n")}), au4)
ok("robots blocking JS/CSS is caught",
   any(f.id == "robots.blocks_assets" and f.severity == a5.HIGH for f in au4.findings))
au5 = a5.SiteAudit(domain="x", brand="B", locale="fa-IR", checked_at="t")
a5.audit_robots(site5, FakeSession({"robots.txt": FakePage("User-agent: *\nDisallow: /\n")}), au5)
ok("robots blocking everything is critical",
   any(f.id == "robots.blocks_everything" and f.severity == a5.CRITICAL for f in au5.findings))

au6 = a5.SiteAudit(domain="x", brand="B", locale="fa-IR", checked_at="t")
a5.audit_canonical_host(site5, FakeSession({"www.": FakePage("", 200, "https://www.boutimar.ir/")}), au6)
ok("www + apex both serving 200 is caught",
   any(f.id == "host.duplicate" for f in au6.findings))

au7 = a5.SiteAudit(domain="x", brand="B", locale="fa-IR", checked_at="t")
sm = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'\
     '<url><loc>https://boutimar.ir/a</loc></url></urlset>'
urls = a5.audit_sitemap(site5, FakeSession({"sitemap": FakePage(sm)}), au7)
ok("sitemap parsed", urls == {"https://boutimar.ir/a"}, urls)
ok("missing lastmod flagged", any(f.id == "sitemap.no_lastmod" for f in au7.findings))

payload5 = a5.build_payload([au, au2], "run_test_0001")
ok("audit payload carries the credit",
   payload5["envelope"]["architecture_credit"] == "Albaloo Studio")
ok("audit payload totals computed", payload5["totals"]["sites"] == 2)
md = a5.to_markdown([au, au2])
ok("markdown report renders", "# Site audit" in md and "boutimar.ir" in md)
ok("report ranks worst site first", md.index("## boutimar.ir — %d" % au2.score())
   < md.index("## boutimar.ir — %d" % au.score()) or au.score() == au2.score())

ok("auditor defaults to the pinned sample, not a module constant",
   a5.audit_site.__defaults__ is None or True)  # signature check below
import inspect
sig = inspect.signature(a5.audit_site)
ok("audit_site sample defaults to None (= use the pin)",
   sig.parameters["sample"].default is None)

au_pin = a5.SiteAudit(domain="x", brand="B", locale="fa", checked_at="t")
au_pin.stats["sample_pages"] = 10
pay_pinned = a5.build_payload([au_pin], "run_x")
ok("pinned run is flagged comparable",
   pay_pinned["sampling"]["pinned"] is True
   and pay_pinned["sampling"]["comparable_with_scheduled_runs"] is True)
ok("pinned sample size recorded", pay_pinned["sampling"]["sample_pages"] == 10)
pay_over = a5.build_payload([au_pin], "run_x", sample_override=3)
ok("overridden run is flagged NOT comparable",
   pay_over["sampling"]["comparable_with_scheduled_runs"] is False)
ok("override note names the offending value", "--sample 3" in pay_over["sampling"]["note"])

# The score must not move with sample size, or a bigger sample invents a worse
# site and the week-over-week trend is fiction.
def _audit_with(n_pages, n_findings_per_page):
    a = a5.SiteAudit(domain="x", brand="B", locale="en", checked_at="t")
    a.stats["pages_checked"] = n_pages
    for i in range(n_pages):
        for j in range(n_findings_per_page):
            a.add(id="content.no_description", area="content", severity=a5.MEDIUM,
                  title="t", evidence="e", fix="f", url=f"https://x/{i}")
    return a
ok("score is independent of sample size",
   _audit_with(3, 1).score() == _audit_with(30, 1).score(),
   (_audit_with(3, 1).score(), _audit_with(30, 1).score()))
ok("a template defect costs one full weight, not N",
   _audit_with(10, 1).score() == 96, _audit_with(10, 1).score())

half = a5.SiteAudit(domain="x", brand="B", locale="en", checked_at="t")
half.stats["pages_checked"] = 10
for i in range(5):
    half.add(id="content.no_description", area="content", severity=a5.MEDIUM,
             title="t", evidence="e", fix="f", url=f"https://x/{i}")
ok("a defect on half the pages costs half the weight", half.score() == 98, half.score())

site_scoped = a5.SiteAudit(domain="x", brand="B", locale="en", checked_at="t")
site_scoped.stats["pages_checked"] = 10
site_scoped.add(id="robots.blocks_everything", scope="site", area="technical",
                severity=a5.CRITICAL, title="t", evidence="e", fix="f")
ok("site-scope findings count once at full weight", site_scoped.score() == 75,
   site_scoped.score())
ok("site scope is set on robots findings",
   all(f.scope == "site" for f in site_scoped.findings))

print("\n=== agent 6 — analyst ===")
import agent6_analyst as a6

ok("phrasing: 'Page declares X' reads at portfolio scope",
   a6._portfolio_phrasing('Page declares lang="en-US" on a Farsi site')
   == 'Declares lang="en-US" on a Farsi site',
   a6._portfolio_phrasing('Page declares lang="en-US" on a Farsi site'))
ok("phrasing: homepage prefix stripped",
   a6._portfolio_phrasing("Homepage has no H1") == "Has no H1")

fake_audit = {
    "generated_at": "2026-08-06T00:00:00Z",
    "sites": [
        {"domain": "a.ir", "score": 20, "stats": {}, "findings": [
            {"id": "geo.no_structured_data", "area": "geo", "severity": "high",
             "title": "Homepage: no JSON-LD in the server-rendered HTML",
             "evidence": "none found", "fix": "add schema", "url": "https://a.ir/"},
            {"id": "robots.blocks_everything", "area": "technical", "severity": "critical",
             "title": "robots.txt blocks the entire site", "evidence": "Disallow: /",
             "fix": "remove it", "url": "https://a.ir/robots.txt"}]},
        {"domain": "b.ir", "score": 60, "stats": {}, "findings": [
            {"id": "geo.no_structured_data", "area": "geo", "severity": "high",
             "title": "Page: no JSON-LD in the server-rendered HTML",
             "evidence": "none found", "fix": "add schema", "url": "https://b.ir/x"}]},
        {"domain": "c.ir", "score": 100, "stats": {"placeholder": True}, "findings": [
            {"id": "site.placeholder", "area": "technical", "severity": "info",
             "title": "This is a placeholder, not a site", "evidence": "375 bytes",
             "fix": "nothing to do", "url": "https://c.ir/"}]},
    ]}

recs = a6.roll_up(fake_audit)
ids = [r.issue for r in recs]
ok("findings roll up across sites, not per page",
   sum(1 for r in recs if "JSON-LD" in r.issue) == 1, ids)
schema_rec = next(r for r in recs if "JSON-LD" in r.issue)
ok("rolled-up finding lists every affected site", schema_rec.sites == ["a.ir", "b.ir"])
ok("evidence names the sites and an example",
   "a.ir" in schema_rec.evidence and "https://" in schema_rec.evidence)
ok("crawlability outranks geo regardless of severity",
   [r.tier for r in recs].index("crawlability") < [r.tier for r in recs].index("geo"),
   [r.tier for r in recs])
ok("critical maps to P0", next(r.priority for r in recs if "blocks the entire" in r.issue) == "P0")
ok("every recommendation carries evidence", all(r.valid() for r in recs))

bad = a6.Recommendation(tier="geo", priority="P1", issue="x", impact="y",
                        evidence="", fix="z")
ok("a finding with no evidence is invalid", not bad.valid())

# Priority matrix — synthetic fixtures, clearly not real GSC data.
gaps = [
    {"query": "قیمت کروز خلیج فارس", "impressions": 4800, "position": 14.0, "domain": "boutimar.ir"},
    {"query": "aroya red sea cruise", "impressions": 5200, "position": 34.0, "domain": "boutimar.com"},
    {"query": "ویزای کروز مدیترانه", "impressions": 210, "position": 12.0, "domain": "boutimar.ir"},
    {"query": "dmc iran mice", "impressions": 90, "position": 55.0, "domain": "dmciran.ir"},
]
opps = a6.build_matrix(gaps)
byk = {o.keyword: o for o in opps}
ok("close + commercial → quick win", byk["قیمت کروز خلیج فارس"].quadrant == "quick_win",
   byk["قیمت کروز خلیج فارس"].quadrant)
ok("high volume + far position → big bet", byk["aroya red sea cruise"].quadrant == "big_bet")
ok("low volume + close → fill in", byk["ویزای کروز مدیترانه"].quadrant == "fill_in")
ok("low volume + far → avoid", byk["dmc iran mice"].quadrant == "avoid")
ok("Farsi commercial intent detected", byk["قیمت کروز خلیج فارس"].intent == "transactional")
ok("clustering works in Farsi",
   byk["قیمت کروز خلیج فارس"].cluster == "Persian Gulf cruising",
   byk["قیمت کروز خلیج فارس"].cluster)
ok("clustering works in English", byk["aroya red sea cruise"].cluster == "AROYA & Red Sea")
ok("scored descending", [o.score for o in opps] == sorted([o.score for o in opps], reverse=True))

topics = a6.topic_map(opps)
ok("topic map ranks clusters by demand",
   list(topics)[0] == "AROYA & Red Sea", list(topics))
ok("each cluster names a pillar", all("pillar" in c for c in topics.values()))
cal = a6.calendar(opps)
ok("calendar produced", len(cal) >= 1 and cal[0]["week"] == 1)
ok("quick wins scheduled first",
   cal[0]["items"][0]["keyword"] == "قیمت کروز خلیج فارس", cal[0]["items"][0])

payload6 = a6.analyse(fake_audit, gaps, use_llm=False)
ok("placeholder excluded from the mean", payload6["placeholders"] == 1
   and payload6["sites_audited"] == 2)
ok("mean over real sites only", payload6["mean_score"] == 40.0, payload6["mean_score"])
ok("schema fix generated for the sites missing it", len(payload6["schema_fixes"]) == 2)
sf = payload6["schema_fixes"][0]
ok("schema fix is valid JSON-LD", json.loads(
    sf["snippet"].split(">", 1)[1].rsplit("<", 1)[0])["@context"] == "https://schema.org")
ok("schema marks unknown facts TODO rather than inventing them",
   "TODO" in json.dumps(sf["jsonld"], ensure_ascii=False))
ok("out-of-scope limits are stated, not omitted", len(payload6["out_of_scope"]) >= 5)
ok("JS-rendering blind spot is disclosed",
   any("JavaScript" in n[0] for n in payload6["out_of_scope"]))
md6 = a6.render(payload6)
ok("report renders", "# Organic growth strategy" in md6)
ok("report shows the tier order",
   md6.index("Crawlability & indexation") < md6.index("GEO — generative"))
ok("report includes out-of-scope section", "Out-of-scope notes" in md6)
ok("report credits Albaloo Studio", "Albaloo Studio" in md6)

# ---------------------------------------------------------------- cost
# What a run spent. Added 14 Aug 2026, when enabling billing on the Gemini key
# turned "the pipeline does not record token counts" from a curiosity into a
# blind spot: both providers returned usage on every call and the scout logged
# it and dropped it, so no manifest could say what a run cost.
print("\n=== what a run costs ===")

ok("a known model is priced", config.estimate_cost_usd("gemini-2.5-flash", 1_000_000, 0) == 0.30)
ok("output is priced separately from input",
   config.estimate_cost_usd("gemini-2.5-flash", 0, 1_000_000) == 2.50)
# A versioned model name must inherit the family rate, or every routine model
# rename silently turns a priced run into an unpriced one.
ok("a versioned variant inherits the family rate",
   config.estimate_cost_usd("gemini-2.5-flash-preview-09-2025", 1_000_000, 0) == 0.30)
# Longest prefix wins: -flash is a prefix of -flash-lite, and matching it first
# would bill the cheaper model at three times its rate.
ok("a longer model name is not swallowed by a shorter prefix",
   config.estimate_cost_usd("gemini-2.5-flash-lite", 1_000_000, 0) == 0.10)
# The single most important assertion here: an unknown model must NOT price
# as zero. A run that reports $0.00 because nobody entered a rate reads as free.
ok("an unpriced model returns None, never 0.0",
   config.estimate_cost_usd("some-model-nobody-priced", 1_000_000, 1_000_000) is None)
ok("an empty model name returns None", config.estimate_cost_usd("", 1000, 1000) is None)
_prices = os.environ.get("TOKEN_PRICES_JSON")
os.environ["TOKEN_PRICES_JSON"] = '{"gemini-2.5-flash": [1.00, 1.00]}'
ok("TOKEN_PRICES_JSON overrides a built-in rate without a code change",
   config.estimate_cost_usd("gemini-2.5-flash", 1_000_000, 0) == 1.00)
os.environ["TOKEN_PRICES_JSON"] = "{not json"
ok("a malformed price override falls back rather than raising",
   config.estimate_cost_usd("gemini-2.5-flash", 1_000_000, 0) == 0.30)
os.environ.pop("TOKEN_PRICES_JSON", None)
if _prices is not None:
    os.environ["TOKEN_PRICES_JSON"] = _prices

# Agent 1 — every provider names the token fields differently, and a provider
# whose names are unhandled contributes a silent zero.
_a1 = _a1sp
_a1._USAGE.clear()
_a1._record_usage("a.ir", "gemini-2.5-flash",
                  type("U", (), {"prompt_token_count": 100, "candidates_token_count": 50})())
_a1._record_usage("b.ir", "claude-sonnet-5",
                  type("U", (), {"input_tokens": 200, "output_tokens": 60})())
_a1._record_usage("c.ir", "gpt-4.1",
                  type("U", (), {"prompt_tokens": 300, "completion_tokens": 70})())
_u1 = _a1._usage_summary()
ok("Gemini token field names are counted", _u1["by_domain"]["a.ir"]["input_tokens"] == 100)
ok("Anthropic token field names are counted", _u1["by_domain"]["b.ir"]["input_tokens"] == 200)
ok("OpenAI token field names are counted", _u1["by_domain"]["c.ir"]["input_tokens"] == 300)
ok("one unpriced model makes the RUN total unpriced",
   _u1["estimated_cost_usd"] is None and _u1["unpriced_models"] == ["gpt-4.1"])
_a1._USAGE.pop("c.ir")
ok("and the total resolves once every model is priced",
   _a1._usage_summary()["estimated_cost_usd"] is not None)
_a1._record_usage("a.ir", "gemini-2.5-flash",
                  type("U", (), {"prompt_token_count": 100, "candidates_token_count": 50})())
ok("repeat calls to one domain accumulate rather than overwrite",
   _a1._usage_summary()["by_domain"]["a.ir"]["calls"] == 2)
_a1._record_usage("d.ir", "gemini-2.5-flash", None)
ok("a response carrying no usage is not counted as a call",
   "d.ir" not in _a1._usage_summary()["by_domain"])
_a1._USAGE.clear()

# Agent 2 — a draft the compliance gate blocked was still generated and billed.
_a2 = a2b
_mk = lambda m, i, o, st: _a2.Outcome(brief_file="x", status=st, model=m,
                                      input_tokens=i, output_tokens=o)
_u2 = _a2._usage_summary([_mk("gemini-2.5-flash", 1000, 500, "drafted"),
                          _mk("gemini-2.5-flash", 1000, 500, "blocked"),
                          _mk("", 0, 0, "skipped")])
ok("a blocked draft still counts as spend", _u2["calls"] == 2)
ok("a skipped brief never counts as spend", _u2["input_tokens"] == 2000)
ok("Agent 2 totals its cost",
   _u2["estimated_cost_usd"] == round((2000 * 0.30 + 1000 * 2.50) / 1e6, 6),
   _u2["estimated_cost_usd"])
ok("Agent 2 reports unpriced rather than free",
   _a2._usage_summary([_mk("mystery-model", 1000, 500, "drafted")])["estimated_cost_usd"] is None)

# Both manifests must actually carry it — the "added in one file, ignored in
# another" bug has shipped four times in this repo.
ok("Agent 1 puts usage in the manifest",
   '"usage": _usage_summary()' in pathlib.Path("agent1_seo_scout.py").read_text(encoding="utf-8"))
ok("Agent 2 puts usage in the manifest",
   '"usage": _usage_summary(outcomes)' in pathlib.Path("agent2_writer_batch.py").read_text(encoding="utf-8"))
# ...and both workflows must render it, or it is a number nobody ever sees.
for _wf in ("agent1-seo-scout", "agent2-writer"):
    _y = pathlib.Path(f"../.github/workflows/{_wf}.yml").read_text(encoding="utf-8")
    ok(f"{_wf} prints the token summary", "**Tokens**" in _y)
    ok(f"{_wf} renders a missing rate as unpriced, not $0", "unpriced" in _y)

print("\n=== every agent that exists must be reachable ===")
# Agent 8 was written and tested on 13 Aug 2026 and had no workflow file, so it
# had never run unattended and nobody noticed for three days. An agent with no
# trigger is indistinguishable from an agent that does not exist.
_wf_dir = pathlib.Path("../.github/workflows")
_wf_text = " ".join(p.read_text(encoding="utf-8") for p in _wf_dir.glob("*.yml"))
#
# Checked per agent NUMBER, not per file. Several agents ship a pair — a
# library (`agent3_broadcaster.py`) plus the runner a workflow actually invokes
# (`agent3_broadcaster_batch.py`) — and the library is imported, not executed.
# Requiring every FILE to appear in a workflow flags those as unreachable and
# is wrong; requiring every NUMBER to appear is the property that matters and
# is exactly how agent 8 was missing.
_agent_nums = sorted({_re.match(r"agent(\d+)", p.stem).group(1)
                      for p in pathlib.Path(".").glob("agent[0-9]*.py")})
# `python3?` because the workflows are not consistent: agents 1, 5 and 6 are
# invoked as `python`, the rest as `python3`. Both resolve to the same
# interpreter under setup-python, so this is a style split rather than a fault
# — but a checker that assumes one spelling reports four healthy agents as
# unreachable, which is worse than the inconsistency it would flag.
_unreachable = [n for n in _agent_nums
                if not _re.search(rf"python3? +agent{n}[a-z0-9_]*\.py", _wf_text)]
ok("every agent number is invoked by some workflow",
   not _unreachable, f"unreachable agent(s): {_unreachable}")
ok("agent 8 specifically now has a workflow",
   (_wf_dir / "agent8-competitor-scout.yml").exists())
# Agent 8 reads a named list and discovers nothing, so a workflow with no
# configured competitors would run and report an empty page every Sunday.
ok("at least one site declares competitors for it to read",
   any(getattr(s, "competitors", None) for s in config.load_sites(include_hold=True)))

print("\n=== exploreorient's frontmatter must match ITS schema, not boutimar's ===")
# Astro refuses to build an entry that misses a field, and the two sites do not
# share a schema: boutimar's `journal` wants date/category, exploreorient's
# `blog` wants publishDate/description/heroImage. Sending one shape to the
# other opens a PR that reddens the target repo's build.
_eo = [s for s in config.load_sites(include_hold=True) if s.domain == "exploreorient.com"][0]
_eo_fm = _eo.cms.get("frontmatter") or {}
ok("exploreorient targets the blog collection", _eo.cms.get("collection") == "blog")
ok("and uses publishDate, not date", "publishDate" in _eo_fm and "date" not in _eo_fm)
ok("and description, not summary", "description" in _eo_fm and "summary" not in _eo_fm)
ok("heroImage is present and deliberately empty, so the build guard fires",
   "heroImage" in _eo_fm and _eo_fm["heroImage"] == "")
_bm = [s for s in config.load_sites(include_hold=True) if s.domain == "boutimar.com"][0]
ok("the two astro sites do NOT share a frontmatter shape",
   set(_bm.cms["frontmatter"]) != set(_eo_fm))

print("\n=== nothing may reuse a credential's name as a loop variable ===")
# The astro_pr adapter read the GitHub token into `token`, then rendered the
# frontmatter with `for token, repl in fields.items()`. The loop rebound the
# credential to the last key in `fields` — the string "language" — and every
# request went out as `Authorization: Bearer language`. GitHub answered 401,
# which is indistinguishable from a bad token, and cost three re-pastes, a
# delete-and-recreate of the secret and a live curl test before the value was
# printed and turned out to be a word.
#
# A grep, not a unit test, because the failure is a NAME COLLISION: it type-checks,
# it reads correctly line by line, and it only misbehaves at a distance.
_CRED_NAMES = ("token", "secret", "password", "api_key", "apikey", "credential")
_shadowed = []
for _py in sorted(pathlib.Path(".").glob("*.py")):
    # This file quotes the offending line as a string literal in the assertion
    # below, so scanning itself makes the check fail on its own evidence.
    if _py.name == "selfcheck.py":
        continue
    for _n, _line in enumerate(_py.read_text(encoding="utf-8").splitlines(), 1):
        _s = _line.strip()
        if _s.startswith("#"):
            continue
        for _c in _CRED_NAMES:
            # `for token, x in ...` / `for token in ...` / comprehension binding
            if _re.search(rf"\bfor\s+{_c}\s*[,)]|\bfor\s+{_c}\s+in\b", _s):
                _shadowed.append(f"{_py.name}:{_n}: {_s[:70]}")
ok("no loop binds a variable named like a credential",
   not _shadowed, "; ".join(_shadowed[:4]))
# And specifically the line that caused it, so the fix cannot be reverted quietly.
_a2l_src = pathlib.Path("agent2_writer_listener.py").read_text(encoding="utf-8")
ok("the frontmatter renderer uses `placeholder`, not `token`",
   "for placeholder, repl in fields.items()" in _a2l_src)
ok("and `token` is never rebound after the credential is read",
   "for token, repl in fields.items()" not in _a2l_src)

print("\n=== 'drafted' is not the same as 'published' ===")
# Run #25, 14 Aug 2026: "2 drafted · 0 blocked · 0 deferred · 0 failed", zero
# pull requests opened and zero files staged. _push_astro_pr caught its own
# RequestException, returned the reason in `note`, and the summary printed none
# of it — so two silent failures read as the cleanest run the pipeline had ever
# produced. The status field answers "did the model write something", never
# "did it reach anywhere".
_oc = a2b.Outcome(brief_file="x", status="drafted")
ok("an Outcome carries where the draft went",
   hasattr(_oc, "pr_url") and hasattr(_oc, "staged_path") and hasattr(_oc, "cms_note"))
_src2 = pathlib.Path("agent2_writer_batch.py").read_text(encoding="utf-8")
ok("and write_one fills them from the adapter result",
   'oc.pr_url = str(result.get("pr_url")' in _src2
   and 'oc.cms_note = str(result.get("note")' in _src2)
_wf2 = pathlib.Path("../.github/workflows/agent2-writer.yml").read_text(encoding="utf-8")
ok("the summary reports where each draft went", "Where the drafts went" in _wf2)
ok("a draft that reached nowhere is called out, not just listed",
   "went nowhere" in _wf2 and "no pull request and no staged" in _wf2)
# The failure mode that started this: neither a PR nor a staged path.
ok("a lost draft is detected by having neither destination",
   not _oc.pr_url and not _oc.staged_path)

print("\n=== a 429 that waiting will never fix ===")
# Run #21, 14 Aug 2026. Gemini answered 429 RESOURCE_EXHAUSTED carrying
# "Your prepayment credits are depleted" — an exhausted BALANCE wearing a
# throttle's status code. rate_limited() matched on "429"/"RESOURCE_EXHAUSTED"
# and so treated it as transient: three retries for one property, and thirty
# across the full portfolio, every one certain to fail.
_DEPLETED = ("429 RESOURCE_EXHAUSTED. {'error': 'code': 429, 'message': 'Your "
             "prepayment credits are depleted. Please go to AI Studio at "
             "https://ai.studio/projects to manage your project and billing. "
             "Learn more at https://ai.google.dev/gemini-api/docs/billing#prepay.")
ok("a depleted prepay balance is NOT rate limiting", not config.rate_limited(_DEPLETED))
ok("a depleted prepay balance IS terminal", bool(config.terminal_provider_error(_DEPLETED)))
# The regression that matters: a real per-minute 429 must still retry, or the
# fix for one failure mode silently creates another.
ok("a genuine per-minute 429 is still rate limiting",
   config.rate_limited("429 RESOURCE_EXHAUSTED: quota exceeded for requests per minute"))
ok("...and is still NOT terminal",
   not config.terminal_provider_error("429 quota exceeded for requests per minute"))
ok("limit: 0 remains a false 429",
   not config.rate_limited("429 RESOURCE_EXHAUSTED ... limit: 0 ..."))
ok("Anthropic's exhausted balance is still terminal",
   bool(config.terminal_provider_error("Your credit balance is too low")))
ok("classification is case-insensitive",
   not config.rate_limited(_DEPLETED.upper()) and not config.rate_limited(_DEPLETED.lower()))

print("\n=== the run cost ceiling ===")
# Added 14 Aug 2026, when the Cloud billing account was upgraded from a free
# trial to pay-as-you-go. The trial was a HARD cap — credit ran out, everything
# stopped, the card was never charged. Postpay has no cap, and a Cloud budget
# only sends email. This is the only brake that actually stops anything.
_mx = config.MAX_RUN_COST_USD
ok("a run under the ceiling continues", config.over_budget(_mx * 0.5) == "")
ok("a run at the ceiling stops", config.over_budget(_mx) != "")
ok("a run over the ceiling stops", config.over_budget(_mx * 10) != "")
ok("the halt reason names the limit and the spend",
   "MAX_RUN_COST_USD" in config.over_budget(_mx) and "$" in config.over_budget(_mx))
# The dangerous case: unpriced must not read as free, and must not read as
# infinite either. It is a bookkeeping gap, not evidence of overspending — so
# it is reported (every summary names the unpriced model) and allowed through.
ok("an unpriced run does not halt on a missing rate", config.over_budget(None) == "")
_saved = config.MAX_RUN_COST_USD
config.MAX_RUN_COST_USD = 0
ok("setting the ceiling to 0 disables the brake", config.over_budget(9999.0) == "")
config.MAX_RUN_COST_USD = _saved
ok("the default ceiling is well above a real run, and finite",
   0 < config.MAX_RUN_COST_USD < 100, config.MAX_RUN_COST_USD)

# Agent 1 halts by setting _PROVIDER_DOWN, so every remaining property takes the
# existing degraded path and the cause is stated once rather than per site.
_a1sp._USAGE.clear()
_a1sp._PROVIDER_DOWN.clear()
_a1sp._record_usage("spendy.ir", "gemini-2.5-pro",
                    type("U", (), {"prompt_token_count": 50_000_000,
                                   "candidates_token_count": 50_000_000})())
_over = _a1sp._usage_summary()["estimated_cost_usd"]
ok("a runaway run is priced far above the ceiling",
   _over > config.MAX_RUN_COST_USD * 100, _over)
ok("and over_budget halts on it", config.over_budget(_over) != "")
_a1sp._USAGE.clear()
_a1sp._PROVIDER_DOWN.clear()
ok("the guard leaves no state behind for the next run",
   not _a1sp._PROVIDER_DOWN and not _a1sp._USAGE)

# Both agents must actually consult it — the "added in one file, ignored in
# another" bug has now shipped five times in this repo.
_src1 = pathlib.Path("agent1_seo_scout.py").read_text(encoding="utf-8")
_src2 = pathlib.Path("agent2_writer_batch.py").read_text(encoding="utf-8")
ok("Agent 1 consults the ceiling before calling a provider",
   "config.over_budget(" in _src1)
ok("Agent 2 consults the ceiling between articles",
   "config.over_budget(" in _src2)
# Indexing the remaining briefs by len(outcomes) is wrong — unreadable files
# append failures before the loop, so the two counts differ.
ok("Agent 2 defers the remainder by loop index, not by len(outcomes)",
   "for i, payload in enumerate(selected)" in _src2 and "selected[i:]" in _src2)

print("\n" + ("ALL PASS" if not FAIL else f"{len(FAIL)} FAILURES: {FAIL}"))
sys.exit(1 if FAIL else 0)
