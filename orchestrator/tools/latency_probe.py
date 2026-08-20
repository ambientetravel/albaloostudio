#!/usr/bin/env python3
"""
How long the portfolio takes to answer, and from where.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

WHY THIS EXISTS
Every Iranian-audience site in this portfolio is served from Germany. Verified
20 Aug: boutimar.com, boutimar.ir, cruise24.ir and dmciran.ir all answer on
116.202.139.162, and cruiseshop.ir on .172 — Hetzner, country DE. Netafraz
sells the hosting inside Iran; the metal is not inside Iran.

boutimar.ir takes ~94% of its impressions from Iranian IPs. Every one of those
requests crosses the international links, which are throttled and filtered in
ways no measurement taken elsewhere can reproduce. So the number that matters
cannot be collected from a laptop in Istanbul or a runner in Virginia — it has
to come from the connection the audience actually uses.

This prints one row per site per vantage point and says WHERE IT WAS RUN, so
two runs can be compared without anyone having to remember which was which.
It also refuses to guess: the vantage label comes from Cloudflare's own trace
endpoint on a property we already own, not from an assumption about the host.

    python3 tools/latency_probe.py                  # every active site, 3 samples
    python3 tools/latency_probe.py --samples 5
    python3 tools/latency_probe.py --format json    # for diffing two vantages
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

# A property already behind Cloudflare, so the vantage point is established
# from our own infrastructure rather than a third-party geolocation service.
TRACE_URL = "https://cruisebaz.com/cdn-cgi/trace"

_FIELDS = ("time_namelookup", "time_connect", "time_appconnect",
           "time_starttransfer", "time_total", "size_download", "http_code")
_FMT = " ".join("%{" + f + "}" for f in _FIELDS)


def vantage() -> dict[str, str]:
    """Country and Cloudflare colo this machine egresses from. Never the IP."""
    try:
        out = subprocess.run(["curl", "-sS", "--max-time", "20", TRACE_URL],
                             capture_output=True, text=True, timeout=30).stdout
    except (subprocess.SubprocessError, OSError):
        return {"loc": "unknown", "colo": "unknown"}
    kv = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
    # ip deliberately dropped — a latency report does not need to carry it.
    return {"loc": kv.get("loc", "unknown"), "colo": kv.get("colo", "unknown"),
            "warp": kv.get("warp", "unknown")}


def probe(url: str, samples: int) -> dict[str, Any]:
    rows = []
    for i in range(samples):
        try:
            out = subprocess.run(
                ["curl", "-sS", "-o", "/dev/null", "-L", "--max-time", "45",
                 "-A", config.USER_AGENT, "-w", _FMT, f"{url}?cb=probe{i}"],
                capture_output=True, text=True, timeout=60).stdout.split()
        except (subprocess.SubprocessError, OSError):
            continue
        if len(out) != len(_FIELDS):
            continue
        rows.append(dict(zip(_FIELDS, (float(x) for x in out))))
    if not rows:
        return {"url": url, "error": "no successful sample"}
    med = lambda k: round(statistics.median(r[k] for r in rows), 3)
    return {
        "url": url,
        "samples": len(rows),
        # Median, not mean. One slow sample on a throttled link is the norm
        # rather than an outlier, and a mean lets it swallow the other two.
        "dns": med("time_namelookup"),
        "connect": med("time_connect"),
        "tls": med("time_appconnect"),
        "ttfb": med("time_starttransfer"),
        "total": med("time_total"),
        "bytes": int(statistics.median(r["size_download"] for r in rows)),
        "http": int(rows[0]["http_code"]),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--domain", action="append")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    v = vantage()
    sites = config.load_sites(only=args.domain)
    rows = [probe(s.base_url + "/", args.samples) for s in sites]

    if args.format == "json":
        print(json.dumps({"vantage": v, "sites": rows}, indent=2))
        return 0

    print(f"# Load time from {v['loc']} (Cloudflare colo {v['colo']}, warp {v['warp']})")
    print()
    print("Median of %d sample(s). TTFB is the number that moves when a request "
          "crosses a throttled link; total also carries page weight." % args.samples)
    print()
    print("| Site | HTTP | TTFB | Total | Size |")
    print("|---|---:|---:|---:|---:|")
    for r in rows:
        if r.get("error"):
            print(f"| {r['url']} | — | — | — | {r['error']} |")
            continue
        print(f"| {r['url']} | {r['http']} | {r['ttfb']:.3f}s | "
              f"{r['total']:.3f}s | {r['bytes']/1024:.0f} KB |")
    print()
    print(f"*Vantage: {v['loc']}. Run this again from a Tehran connection and "
          f"compare the TTFB column — that difference is what the audience pays "
          f"for hosting in Germany.*")
    return 0


if __name__ == "__main__":
    sys.exit(main())
