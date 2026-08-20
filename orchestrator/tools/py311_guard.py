#!/usr/bin/env python3
"""
Catch code that compiles here and is a SyntaxError on the runner.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHY THIS EXISTS
This machine runs Python 3.14; every GitHub runner in this pipeline pins 3.11.
PEP 701 (new in 3.12) legalised two things inside f-strings that 3.11 rejects
outright:

    1. reusing the SAME quote character inside the expression
    2. backslashes inside the expression

Both parse silently here and fail the build there, and the existing guard does
not catch either. `ast.parse(src, feature_version=(3, 11))` was being used and
gives a FALSE PASS: feature_version constrains the AST, not the TOKENIZER, so
an f-string that only 3.12+ can even tokenize sails through it.

That false pass has a cost already paid. build_dashboard.py line 414 nested a
single-quoted f-string inside a single-quoted f-string. Every dashboard build
since has failed with

    SyntaxError: f-string: unterminated string

and the dashboard — the page meant to be read on a phone — has not been built
since. Three consecutive red runs, and the local check said the file was fine.

HOW IT WORKS
tokenize, not regex. On 3.12+ the tokenizer emits FSTRING_START / FSTRING_MIDDLE
/ FSTRING_END, so the inside of an f-string is walkable: record the quote the
f-string opened with, then look at what appears before its matching END.
A regex over source text cannot do this without reimplementing the lexer.

    python3 tools/py311_guard.py               # every .py under orchestrator/
    python3 tools/py311_guard.py path/to/x.py
"""

from __future__ import annotations

import io
import sys
import token as T
import tokenize
from pathlib import Path


def _quote_of(fstring_start: str) -> str:
    """`f'` -> `'` ; `rf\"\"\"` -> `\"\"\"` — the delimiter, without the prefix."""
    i = 0
    while i < len(fstring_start) and fstring_start[i] not in "\"'":
        i += 1
    rest = fstring_start[i:]
    for triple in ('"""', "'''"):
        if rest.startswith(triple):
            return triple
    return rest[:1]


def scan(path: Path) -> list[tuple[int, str]]:
    """Every 3.12+-only construct in one file, as (line, why)."""
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [(0, f"unreadable: {exc}")]

    problems: list[tuple[int, str]] = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, SyntaxError) as exc:
        return [(0, f"does not tokenize even here: {exc}")]

    # FSTRING_START only exists on 3.12+. On an older interpreter this scanner
    # finds nothing, which is correct: there, the compiler itself is the check.
    start_tok = getattr(T, "FSTRING_START", None)
    end_tok = getattr(T, "FSTRING_END", None)
    if start_tok is None or end_tok is None:
        return []

    depth = 0
    quotes: list[str] = []
    for tk in toks:
        if tk.type == start_tok:
            q = _quote_of(tk.string)
            # Reusing ANY enclosing delimiter is the fault, not just the nearest
            # one. The case that shipped was a single-quoted literal two levels
            # down inside a single-quoted f-string, with a double-quoted
            # f-string between them; comparing only against the innermost
            # delimiter missed it entirely.
            if depth > 0 and q in quotes:
                problems.append((tk.start[0],
                                 "nested f-string reuses the " + q +
                                 " delimiter of an enclosing f-string"
                                 " — legal from 3.12, SyntaxError on 3.11"))
            depth += 1
            quotes.append(q)
            continue
        if tk.type == end_tok:
            depth -= 1
            if quotes:
                quotes.pop()
            continue
        if depth <= 0:
            continue

        # A string literal inside the expression reusing any enclosing quote.
        if tk.type == T.STRING:
            inner = _quote_of(tk.string)
            if inner and inner in quotes:
                problems.append((tk.start[0],
                                 "a " + inner + "-quoted string sits inside an"
                                 " f-string delimited by " + inner +
                                 " — legal from 3.12, SyntaxError on 3.11"))
        # Backslashes inside the expression: also 3.12+ only.
        if tk.type not in (start_tok, end_tok, T.FSTRING_MIDDLE) and "\\" in tk.string:
            problems.append((tk.start[0],
                             "backslash inside an f-string expression — "
                             "legal from 3.12, SyntaxError on 3.11"))
    return problems


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]]
    if not targets:
        root = Path(__file__).resolve().parent.parent
        targets = sorted(p for p in root.rglob("*.py")
                         if "__pycache__" not in p.parts)
    bad = 0
    for p in targets:
        for line, why in scan(p):
            print(f"  {p}:{line}  {why}")
            bad += 1
    if bad:
        print(f"\n{bad} construct(s) that the 3.11 runner cannot parse.")
        return 1
    print(f"{len(targets)} file(s) are parseable by Python 3.11.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
