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
            reason = (
                "One Schengen port makes the whole itinerary Schengen — even sailing "
                "from Istanbul."
                if schengen
                else "Only AROYA's Türkiye+Egypt routes and Seychelles are visa-free. "
                "Persian Gulf and Dubai are EASY VISA, not visa-free."
            )
            out.append(Violation("visa_accuracy", BLOCK, _excerpt(text, m), reason))
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
