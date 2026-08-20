"""
Albaloo Orchestration Pipeline — the compliance gate (ARCHITECTURE.md §7).

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

These rules are enforced twice: injected into every prompt as a constraint, and
re-checked against generated output before anything is published. A prompt
instruction is guidance; this module is enforcement.

Matching note — the port-name lesson from boutimar.ir applies here too: never
substring-match a *short* Persian token, because «رم» sits inside «مارماریس»
and «کن» inside «اسکندریه». Every pattern below is either a multi-word phrase
or word-boundary anchored for exactly that reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Iterable

BLOCK = "block"
WARN = "warn"


@dataclass(frozen=True)
class Violation:
    rule: str
    severity: str           # block | warn
    excerpt: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["action"] = "blocked" if self.severity == BLOCK else "flagged"
        return d


class ComplianceError(RuntimeError):
    def __init__(self, violations: list[Violation]):
        self.violations = violations
        super().__init__(
            "; ".join(f"{v.rule}: {v.message}" for v in violations if v.severity == BLOCK)
        )


# ── §7.1 Persian Gulf ────────────────────────────────────────────────────────
# "Arabian Sea" / «دریای عرب» is a DIFFERENT body of water and is left alone.
# The pattern matches Gulf, never Arabian on its own.

_ARABIAN_GULF = re.compile(
    r"(?i)\b(arabian|arabic|a\.?\s*rabian)\s+gulf\b"
    r"|خلیج\s*عرب(ی|ي)?"
    r"|الخليج\s*العرب(ي|ی)"
)

# ── §7.2 Visa accuracy ───────────────────────────────────────────────────────
# Truly visa-free: AROYA's Türkiye + Egypt routes, and Seychelles. Nothing else.
# Persian Gulf and Dubai are EASY VISA. One Greek/Italian/Spanish/French port
# makes the whole itinerary Schengen — even sailing from Istanbul.

VISA_FREE_ROUTES = frozenset({"aroya_turkiye_egypt", "seychelles"})

_SCHENGEN_PORT_MARKERS = (
    "greece", "greek", "santorini", "mykonos", "piraeus", "rhodes", "crete", "corfu",
    "italy", "italian", "rome", "civitavecchia", "naples", "venice", "genoa", "bari",
    "spain", "spanish", "barcelona", "valencia", "palma", "malaga",
    "france", "french", "marseille", "nice", "cannes",
    "یونان", "سانتورینی", "میکونوس", "ایتالیا", "رم", "ناپل", "ونیز",
    "اسپانیا", "بارسلون", "فرانسه", "مارسی",
)

_NO_VISA_CLAIM = re.compile(
    r"(?i)\bvisa[-\s]?free\b"
    r"|\bno\s+visa\s+(required|needed)\b"
    r"|\bwithout\s+a?\s*visa\b"
    r"|بدون\s*ویزا"
    r"|بدون\s*نیاز\s*به\s*ویزا"
    r"|معاف\s*از\s*ویزا"
    r"|نیازی\s*به\s*ویزا\s*ندار"
)

_SCHENGEN_MISLABEL = re.compile(r"(?i)\bschengen[-\s]?free\b|بدون\s*شنگن")

# Destinations where a visa-free claim is FALSE. This is the harm the rule
# exists to prevent, and the only case that earns a BLOCK on its own.
_VISA_FORBIDDEN_DEST = re.compile(
    r"(?i)persian\s+gulf|\bdubai\b|\bu\.?a\.?e\.?\b|united\s+arab\s+emirates"
    r"|\babu\s*dhabi\b|\bdoha\b|\bqatar\b|\bbahrain\b|\bmuscat\b|\boman\b"
    r"|خلیج\s*فارس|دبی|امارات|ابوظبی|دوحه|قطر|بحرین|مسقط|عمان"
)

# Destinations where it is TRUE: AROYA's Türkiye+Egypt routes, and Seychelles.
_VISA_EXEMPT_DEST = re.compile(
    r"(?i)\bt(ü|u)rkiye\b|\bturkey\b|\begypt\b|\bseychelles\b"
    r"|ترکیه|تركيه|مصر|سیشل|سیشیل"
)

# Schengen ports named in the prose itself. `itinerary_ports` in the context is
# the authoritative signal, but Agent 1 has no itinerary to pass — so a brief
# saying "Santorini, visa-free" sailed straight through. Deliberately a SUBSET
# of _SCHENGEN_PORT_MARKERS: «رم» sits inside «مارماریس» and «کن» inside
# «اسکندریه», so short Persian tokens are excluded from free-text matching and
# left to the port-list path, where they are compared whole.
_SCHENGEN_IN_TEXT = re.compile(
    r"(?i)\bgreece\b|\bgreek\b|\bsantorini\b|\bmykonos\b|\bpiraeus\b|\brhodes\b"
    r"|\bcrete\b|\bcorfu\b|\bitaly\b|\bitalian\b|\bcivitavecchia\b|\bnaples\b"
    r"|\bvenice\b|\bgenoa\b|\bspain\b|\bspanish\b|\bbarcelona\b|\bvalencia\b"
    r"|\bmalaga\b|\bfrance\b|\bfrench\b|\bmarseille\b|\blanzarote\b|\bcanary\b"
    r"|یونان|سانتورینی|میکونوس|ایتالیا|ناپل|ونیز|اسپانیا|بارسلون|فرانسه|مارسی"
    r"|لانزاروته|قناری"
)
# Note what is NOT here: the word "Schengen" itself. It is the visa zone, not a
# port, and copy that says «تفکیک مقاصد شنگن از مقاصد بدون ویزا» is stating the
# rule correctly. Naming a *place* beside a visa-free claim blocks; naming the
# zone falls through to the warn branch, and a real itinerary still blocks via
# `itinerary_ports`, which is the authoritative signal.

# "Persian Gulf and Dubai: easy visa, not visa-free" and "separate the visa-free
# routes (Türkiye, Seychelles) from the easy-visa ones (Gulf, Dubai)" both name
# a forbidden destination beside a visa-free claim, yet both are correct — the
# forbidden destination is attached to the *easy-visa* half. This marker is how
# the gate tells contrastive taxonomy from a false claim.
_EASY_VISA_MARKER = re.compile(
    r"(?i)\beasy[-\s]?visa\b|\bvisa[-\s]?on[-\s]?arrival\b"
    r"|ویزای\s*آسان|ویزا\s*در\s*بدو\s*ورود"
)

# A brief or an article is a list of discrete instructions, not one long
# sentence. Without a boundary the ±60-char window around «بدون ویزا» in
# "Seychelles: no visa needed | Persian Gulf: easy visa" straddles both items
# and condemns the correct one for its neighbour. Callers must join list items
# with one of these; assertive_surface() does it for them.
_CLAUSE_BOUNDARY = re.compile(r"[.!?؟\n؛;•|]")

# A question asserts nothing. "Is the UAE visa-free?" is a heading; the answer
# ("no — easy visa") is the next list item and is judged on its own.
#
# The original note here said this shape was "what the GEO work exists to
# produce". That overstated it: a 100-query AI Overview study found
# question-format titles had NO positive correlation with citation. The
# interrogative guard stays, because blocking a question that asserts nothing is
# simply wrong — but the justification is correctness, not a citation benefit
# that did not survive measurement.
_INTERROGATIVE = re.compile(
    r"(?i)^\s*(is|are|was|were|do|does|did|can|could|will|would|should|has|have"
    r"|which|what|when|where|how|why)\b"
    r"|^\s*آیا\b|\bآیا\b"
)


# Citation grammar with nothing behind it. All three Agent 2 drafts reviewed on
# 20 Aug carried one, and the shape is identical every time: a claim, a comma,
# and an official-sounding body that was never consulted.
#
#   "as verified by Yazd Cultural Heritage and Tourism Department lodging records"
#   "as documented in official Iran International Exhibitions Company (IIEC)…"
#   "documented by the Geological & Heritage Survey of Iran"
#
# The third names an organisation that does not exist — a hybrid of the
# Geological Survey of Iran and a cultural-heritage authority. This is worse
# than an unsourced claim: it manufactures the appearance of verification, and
# a reader who trusts it has been given a reason to that we invented.
#
# The pipeline has no research tool and reads no registry, so a model asserting
# it checked one is asserting something that could not have happened. There is
# no legitimate use of this phrasing in Agent 2's output, which is why it
# BLOCKS rather than warns.
_FAKE_CITATION = re.compile(
    r"\b(?:as\s+)?(?:verified|documented|confirmed|recorded|certified|registered|"
    r"published|listed)\s+(?:by|in|with|per)\s+"
    r"(?:the\s+|an?\s+|official\s+)*"
    r"[A-Z][\w&'’-]*(?:\s+(?:of|and|for|&)?\s*[A-Z][\w&'’-]*){1,7}",
    re.UNICODE,
)


def _clause_bounds(text: str, match: re.Match[str]) -> tuple[int, int]:
    """Offsets of the single clause containing `match`, never spilling into its neighbours."""
    before = text[:match.start()]
    after = text[match.end():]
    left = max((m.end() for m in _CLAUSE_BOUNDARY.finditer(before)), default=0)
    right_m = _CLAUSE_BOUNDARY.search(after)
    right = match.end() + (right_m.start() if right_m else len(after))
    return left, right

# Negation guard. `visa_accuracy` bans a CLAIM, not a term: "Dubai is not
# visa-free" is the correct sentence, and "state that Iran stays are not
# visa-free" is the instruction that enforces the rule. A context-blind match
# blocked both — it blocked the fix as readily as the error.
#
# `persian_gulf_only` deliberately gets NO such guard: that rule bans a term
# outright, and "Arabian Gulf" is wrong in any framing.
_NEG_BEFORE = re.compile(
    r"(?i)\b(not|isn'?t|aren'?t|never|non|no)\b[^.!?؟\n]{0,24}$"
    r"|(نه|نمی|بدون\s+اینکه)[^.!?؟\n]{0,24}$"
)
_NEG_AFTER = re.compile(
    r"(?i)^[^.!?؟\n]{0,24}\b(is|are)\s+(not|never)\b"
    r"|^[^.!?؟\n]{0,24}(نیست|نیستند|نمی[‌\s]*باشد|ندارد)"
)


def _is_negated(text: str, match: re.Match[str], *, lo: int = 0, hi: int | None = None) -> bool:
    """
    True when the surrounding clause denies the claim rather than making it.

    `lo`/`hi` bound the search to one clause. Without them a negator belonging
    to the *previous* item ("…easy visa, not visa-free | Dubai: visa-free")
    would excuse the next item's real violation.
    """
    hi = len(text) if hi is None else hi
    return bool(
        _NEG_BEFORE.search(text[max(lo, match.start() - 60):match.start()])
        or _NEG_AFTER.search(text[match.end():min(hi, match.end() + 60)])
    )

# ── §7.3 Never invent ────────────────────────────────────────────────────────

# Digits: ASCII, Persian (۰-۹) and Arabic-Indic (٠-٩). A Farsi price written
# «۸۹۹ یورو» is a price; an ASCII-only pattern lets an invented rate walk
# straight through the gate on the two Farsi-first sites.
_DIGITS = "0-9۰-۹٠-٩"
_CURRENCY = r"(?:€|\$|£|eur|usd|gbp|تومان|ریال|یورو|دلار|درهم|درم)"
_PRICE = re.compile(
    rf"(?i){_CURRENCY}\s?[{_DIGITS}][{_DIGITS}.,٬]{{2,}}"
    rf"|[{_DIGITS}][{_DIGITS}.,٬]{{2,}}\s?{_CURRENCY}"
)

_GUARANTEE = re.compile(
    r"(?i)\b(guaranteed|lowest\s+price|best\s+price\s+guarantee|price\s+match)\b"
    r"|تضمین\s*قیمت|ارزان‌?ترین\s*قیمت\s*تضمینی"
)

_PHOTO_CREDIT_GUESS = re.compile(r"(?i)\b(photo|image)\s*(credit)?\s*:\s*(unknown|n/?a|tbd|—|-)\s*$")

# ── §7.4 Brand & scope ───────────────────────────────────────────────────────

_BOUTIMAR_BRAND = re.compile(r"(?i)بوتیمار|\bboutimar\b")
_BOUTIMAR_LINK = re.compile(r"(?i)https?://(www\.)?boutimar\.(ir|com)")

PROFILES: dict[str, dict[str, bool]] = {
    "boutimar_v1": {
        "persian_gulf_only": True,
        "visa_accuracy": True,
        "no_invented_facts": True,
        "brand_neutral_embed": False,
        "sanctions_check": True,
    },
    "partner_widget_v1": {
        "persian_gulf_only": True,
        "visa_accuracy": True,
        "no_invented_facts": True,
        "brand_neutral_embed": True,   # the embed runs inside partner agency sites
        "sanctions_check": True,
    },
}


# Fields that enumerate what the copy must NOT say. Every string in them is a
# forbidden term by definition, so scanning them guarantees a false positive on
# a *correctly written* brief — and the more precisely the model states the
# rule, the more certainly its own brief is dead-lettered. Never check these.
PROHIBITION_FIELDS = frozenset({"must_avoid", "avoid", "banned_terms", "do_not"})


def assertive_surface(obj: Any) -> str:
    """
    Flatten a brief/draft into the text the gate should judge: every assertion,
    no prohibition, one clause per line.

    The newlines matter. These are discrete instructions, not prose — joined by
    spaces, the window around one item's «بدون ویزا» reaches into the next
    item's destination and condemns the correct statement for its neighbour.
    """
    lines: list[str] = []

    def walk(node: Any, key: str | None = None) -> None:
        if key in PROHIBITION_FIELDS:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and node.strip():
            lines.append(node.strip())

    walk(obj)
    return "\n".join(lines)


def _excerpt(text: str, match: re.Match[str], width: int = 60) -> str:
    start = max(0, match.start() - width)
    end = min(len(text), match.end() + width)
    return text[start:end].replace("\n", " ").strip()


def check(
    text: str,
    profile: str = "boutimar_v1",
    *,
    context: dict[str, Any] | None = None,
) -> list[Violation]:
    """
    Run every rule enabled by `profile` over `text`.

    context keys (all optional):
      route_key        str  — e.g. "aroya_turkiye_egypt"; unlocks a visa-free claim
      itinerary_ports  list — port/country names; a Schengen marker forbids visa-free
      priced_facts     bool — True when a live rate feed backed this copy
      price_asof       str  — RFC3339; a price without one is not a price
    """
    ctx = context or {}
    rules = PROFILES.get(profile)
    if rules is None:
        raise ValueError(f"Unknown compliance profile {profile!r}")

    out: list[Violation] = []

    if rules["persian_gulf_only"]:
        for m in _ARABIAN_GULF.finditer(text):
            out.append(
                Violation(
                    "persian_gulf_only",
                    BLOCK,
                    _excerpt(text, m),
                    'Use «خلیج فارس» / "Persian Gulf". "Arabian Gulf" is never acceptable.',
                )
            )

    if rules["visa_accuracy"]:
        route_ok = ctx.get("route_key") in VISA_FREE_ROUTES
        ports = " ".join(str(p) for p in ctx.get("itinerary_ports") or []).lower()
        schengen = any(marker in ports for marker in _SCHENGEN_PORT_MARKERS)
        for m in _NO_VISA_CLAIM.finditer(text):
            if route_ok and not schengen:
                continue
            lo, hi = _clause_bounds(text, m)
            if _is_negated(text, m, lo=lo, hi=hi):
                continue  # "not visa-free" states the rule, it does not break it

            # Which destination the claim attaches to is the whole question.
            # "Türkiye and Egypt: no visa needed" is the rule stated correctly;
            # "Dubai: no visa needed" is the lie the rule exists to stop. A
            # context-blind match cannot tell them apart, so it blocked every
            # brief that explained the policy accurately — the better the model
            # stated the rule, the more certainly the brief was dead-lettered.
            clause = text[lo:hi]

            # Interrogative: the clause asks rather than claims. Kept as a
            # warning, not dropped — a question about visa status is precisely
            # where the writer downstream could answer it wrongly, so it should
            # stay visible in the compliance block that travels with the brief.
            # `terminator` is "" at end-of-text, and "" in "?؟" is True — which
            # made every trailing clause read as a question. Test the truthiness.
            terminator = text[hi:hi + 1]
            if (terminator and terminator in "?؟") or _INTERROGATIVE.search(clause):
                out.append(Violation(
                    "visa_accuracy", WARN, _excerpt(text, m),
                    "A question about visa-free status, not a claim. The answer must "
                    "say easy visa for Persian Gulf/Dubai and Schengen for any "
                    "Greek, Italian, Spanish or French port.",
                ))
                continue

            forbidden = _VISA_FORBIDDEN_DEST.search(clause)
            exempt = _VISA_EXEMPT_DEST.search(clause)
            # A clause that classifies the forbidden destination as easy-visa is
            # stating the rule, not breaking it.
            classified = _EASY_VISA_MARKER.search(clause)

            if forbidden and not classified:
                out.append(Violation(
                    "visa_accuracy", BLOCK, _excerpt(text, m),
                    "Only AROYA's Türkiye+Egypt routes and Seychelles are visa-free. "
                    "Persian Gulf and Dubai are EASY VISA, not visa-free.",
                ))
            elif schengen or _SCHENGEN_IN_TEXT.search(clause):
                out.append(Violation(
                    "visa_accuracy", BLOCK, _excerpt(text, m),
                    "One Schengen port makes the whole itinerary Schengen — even "
                    "sailing from Istanbul.",
                ))
            elif exempt or forbidden:
                continue  # names a sanctioned exception and nothing else
            else:
                # No destination attached. Not a false claim, but vague enough
                # to become one downstream — surface it without dead-lettering.
                out.append(Violation(
                    "visa_accuracy", WARN, _excerpt(text, m),
                    "A visa-free claim with no destination attached. Name the route: "
                    "only AROYA Türkiye+Egypt and Seychelles qualify.",
                ))
        for m in _SCHENGEN_MISLABEL.finditer(text):
            out.append(
                Violation(
                    "visa_accuracy",
                    BLOCK,
                    _excerpt(text, m),
                    "Do not describe an itinerary as exempt from Schengen.",
                )
            )

    if rules["no_invented_facts"]:
        if not ctx.get("priced_facts"):
            for m in _PRICE.finditer(text):
                out.append(
                    Violation(
                        "no_invented_facts",
                        BLOCK,
                        _excerpt(text, m),
                        "A figure appears but no live rate feed backed this copy. "
                        "If the data is not there, say it is not there.",
                    )
                )
        elif not ctx.get("price_asof") and _PRICE.search(text):
            out.append(
                Violation(
                    "no_invented_facts",
                    BLOCK,
                    _excerpt(text, _PRICE.search(text)),  # type: ignore[arg-type]
                    "A price with no price_asof timestamp is not a price.",
                )
            )
        for m in _GUARANTEE.finditer(text):
            out.append(
                Violation(
                    "no_invented_facts",
                    WARN,
                    _excerpt(text, m),
                    "Price guarantee language is a commercial commitment nobody signed off.",
                )
            )
        for m in _FAKE_CITATION.finditer(text):
            out.append(
                Violation(
                    "no_invented_facts",
                    BLOCK,
                    _excerpt(text, m),
                    "This cites an authority as having verified the claim. Nothing "
                    "in this pipeline reads a registry, an archive or a records "
                    "office, so that verification did not happen. State the fact "
                    "plainly or leave it out — an invented source is worse than "
                    "no source, because it manufactures a reason to be believed.",
                )
            )
        for m in _PHOTO_CREDIT_GUESS.finditer(text):
            out.append(
                Violation(
                    "no_invented_facts",
                    BLOCK,
                    _excerpt(text, m),
                    "An image with no known credit is omitted, never captioned 'unknown'.",
                )
            )

    if rules["brand_neutral_embed"]:
        for pattern, msg in (
            (_BOUTIMAR_BRAND, "The partner embed stays brand-neutral — no «بوتیمار»."),
            (_BOUTIMAR_LINK, "The partner embed must not link to boutimar.ir/.com."),
        ):
            for m in pattern.finditer(text):
                out.append(Violation("brand_neutral_embed", BLOCK, _excerpt(text, m), msg))

    return out


def enforce(
    text: str,
    profile: str = "boutimar_v1",
    *,
    context: dict[str, Any] | None = None,
) -> list[Violation]:
    """check(), but a BLOCK-severity violation raises. Returns the warnings."""
    violations = check(text, profile, context=context)
    if any(v.severity == BLOCK for v in violations):
        raise ComplianceError(violations)
    return violations


def prompt_constraints(profile: str = "boutimar_v1") -> str:
    """
    The same rules, phrased for an LLM system prompt. Injected by every agent so
    the model is steered *and* audited — belt and braces, on purpose.
    """
    rules = PROFILES.get(profile, PROFILES["boutimar_v1"])
    lines = [
        "NON-NEGOTIABLE EDITORIAL RULES (violating any one voids the entire output):",
    ]
    if rules["persian_gulf_only"]:
        lines.append(
            '1. Always «خلیج فارس» / "Persian Gulf". Never "Arabian Gulf" / «خلیج عربی» '
            "— in body copy, headings, alt text, meta, schema or relabelled source "
            'data. ("Arabian Sea" is a different body of water; leave it alone.)'
        )
    if rules["visa_accuracy"]:
        lines.append(
            "2. Visa accuracy. Only AROYA's Türkiye+Egypt routes and Seychelles are "
            "truly visa-free. Persian Gulf itineraries and Dubai are EASY VISA, not "
            "visa-free. Any Greek, Italian, Spanish or French port makes the "
            "itinerary Schengen — even when it sails from Istanbul."
        )
    if rules["no_invented_facts"]:
        lines.append(
            "- NEVER write that a fact was verified, documented, confirmed or "
            "recorded by any organisation, ministry, department, survey or "
            "records office. You have not consulted one and cannot. State the "
            "fact on its own or omit it."
        )
        lines.append(
            "3. Never invent a rate, a departure date, an inclusion or a photo "
            "credit. Use only the figures supplied in the brief's data. If the data "
            "is not there, write that it is not there. No price guarantees."
        )
    if rules["brand_neutral_embed"]:
        lines.append(
            "4. Brand-neutral output: no «بوتیمار»/Boutimar mention, no link to "
            "boutimar.ir or boutimar.com. This copy runs inside partner agency sites."
        )
    lines.append(
        "5. Do not name a company in anything that resembles an outbound API header "
        "or supplier-facing text; the CruiseHost contract belongs to Ambiente Tours."
    )
    return "\n".join(lines)


def summarise(
    violations: Iterable[Violation], profile: str = "boutimar_v1"
) -> dict[str, Any]:
    """The `compliance` block every payload carries."""
    vs = list(violations)
    rules = PROFILES.get(profile, PROFILES["boutimar_v1"])
    return {
        "checks_run": sorted(name for name, on in rules.items() if on),
        "checks_passed": not any(v.severity == BLOCK for v in vs),
        "violations": [v.as_dict() for v in vs],
    }
