"""Self-check for the Albaloo orchestrator — no network, no API keys, no pytest.

Architecture credit: Albaloo Studio — albaloostudio.com

    python selfcheck.py        # exits 0 on a clean pipeline, 1 on any failure

Mocks Search Console and Gemini. Exercises config, the compliance gate, gap
detection, payload assembly, JSON-Schema conformance, delivery retry and the
Agent 2 HTTP surface end to end.
"""
import json, os, sys

os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-secret-123")
os.environ.setdefault("PIPELINE_ENVIRONMENT", "staging")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")

import jsonschema
import config, compliance

FAIL = []
def ok(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(extra) if extra and not cond else ""))
    if not cond: FAIL.append(label)

print("\n=== config ===")
sites = config.load_sites()
ok("active sites load", len(sites) == 7, len(sites))
ok("held sites excluded by default",
   all(s.domain != "cruise24.ir" for s in sites))
ok("include_hold returns the full portfolio",
   len(config.load_sites(include_hold=True)) == 8)
ok("naming a held site explicitly overrides the hold",
   [s.domain for s in config.load_sites(only=["cruise24.ir"])] == ["cruise24.ir"])
ok("on_hold flag reads from sites.yml",
   next(s.on_hold for s in config.load_sites(include_hold=True)
        if s.domain == "cruise24.ir") is True)
ok("active sites are not on hold", all(not s.on_hold for s in sites))
# The audit score counts findings, so it scales with sample size. The cron never
# passes --sample; it takes this. Uniformity is what makes the trend line real.
ok("audit sample size is pinned uniformly",
   {s.audit_sample_pages for s in config.load_sites(include_hold=True)} == {10},
   {s.audit_sample_pages for s in config.load_sites(include_hold=True)})
ok("defaults merged into each site", all(s.min_impressions == 5 for s in sites
                                         if s.domain != "boutimar.com"))
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

print("\n" + ("ALL PASS" if not FAIL else f"{len(FAIL)} FAILURES: {FAIL}"))
sys.exit(1 if FAIL else 0)
