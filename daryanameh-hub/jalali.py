#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gregorian ↔ Jalali (Solar Hijri) conversion, no dependencies.

Readers of a Farsi cruise magazine live on two calendars at once: someone in
Tehran reads ۱۵ شهریور, someone in Hamburg reads 6 September, and plenty of
people read one fluently and the other only by counting. So every date on the
site is printed twice — Jalali first, Gregorian beside it — and the machine
readable `datetime` attribute stays ISO Gregorian.

Algorithm: Roozbeh Pournader and Mohammad Toossi's, as used by jalaali-js.
Exact for Jalali years 1178–1633 (Gregorian 1799–2254), which covers every
date this publication will ever print.
"""
from __future__ import annotations

BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
          1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178]

JALALI_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                 "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

# Gregorian months as Iranian media write them.
GREGORIAN_MONTHS_FA = ["ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن",
                       "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"]

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _div(a: int, b: int) -> int:
    """Integer division that truncates toward zero, as the reference algorithm needs.
    Python's // floors instead, which silently shifts dates by a year for negative
    intermediates — the bug this function exists to avoid."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def _mod(a: int, b: int) -> int:
    return a - _div(a, b) * b


def _jal_cal(jy: int) -> dict:
    """Leap-year flag and the Gregorian March day on which this Jalali year starts."""
    if jy < BREAKS[0] or jy >= BREAKS[-1]:
        raise ValueError(f"Jalali year {jy} outside the supported range")
    gy, leap_j, jp, jump = jy + 621, -14, BREAKS[0], 0
    for jm in BREAKS[1:]:
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return {"leap": leap, "gy": gy, "march": march}


def _g2d(gy: int, gm: int, gd: int) -> int:
    """Gregorian date to Julian Day Number."""
    d = (_div((gy + _div(gm - 8, 6) + 100100) * 1461, 4)
         + _div(153 * _mod(gm + 9, 12) + 2, 5)
         + gd - 34840408)
    return d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752


def _d2g(jdn: int) -> tuple[int, int, int]:
    """Julian Day Number to Gregorian date."""
    j = 4 * jdn + 139361631
    j += _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(_mod(j, 1461), 4) * 5 + 308
    gd = _div(_mod(i, 153), 5) + 1
    gm = _mod(_div(i, 153), 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return gy, gm, gd


def to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Gregorian (y, m, d) → Jalali (y, m, d)."""
    jdn = _g2d(gy, gm, gd)
    j_gy = _d2g(jdn)[0]
    jy = j_gy - 621
    r = _jal_cal(jy)
    k = jdn - _g2d(j_gy, 3, r["march"])
    if k >= 0:
        if k <= 185:
            return jy, 1 + _div(k, 31), _mod(k, 31) + 1
        k -= 186
    else:
        # Previous Jalali year — the leap flag is the one belonging to the year we
        # just came from, r, not to the decremented year.
        jy -= 1
        k += 179 + (1 if r["leap"] == 1 else 0)
    return jy, 7 + _div(k, 30), _mod(k, 30) + 1


def fa_digits(s) -> str:
    return str(s).translate(FA_DIGITS)


def parse_iso(iso: str) -> tuple[int, int, int] | None:
    try:
        y, m, d = (int(x) for x in str(iso).strip().split("-"))
        return y, m, d
    except (ValueError, AttributeError):
        return None


def jalali_str(iso: str) -> str:
    """'2026-09-06' → '۱۵ شهریور ۱۴۰۵'."""
    g = parse_iso(iso)
    if not g:
        return fa_digits(iso)
    jy, jm, jd = to_jalali(*g)
    return f"{fa_digits(jd)} {JALALI_MONTHS[jm - 1]} {fa_digits(jy)}"


def gregorian_str(iso: str) -> str:
    """'2026-09-06' → '۶ سپتامبر ۲۰۲۶'."""
    g = parse_iso(iso)
    if not g:
        return fa_digits(iso)
    gy, gm, gd = g
    return f"{fa_digits(gd)} {GREGORIAN_MONTHS_FA[gm - 1]} {fa_digits(gy)}"
