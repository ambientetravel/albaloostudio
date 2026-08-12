#!/usr/bin/env python3
"""
Albaloo Orchestration Pipeline — one place to ask a model for something.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Agents 3, 4 and 6 each grew their own Anthropic call. That was fine while one
key paid for everything and wrong the moment it stopped: on 12 Aug 2026 the $5
balance ran out and three agents needed the same edit in three places, one of
which (Agent 6) runs unattended every Monday and would have failed silently
until someone opened the run.

So the provider is a setting, not a call site. `PROSE_PROVIDER` picks it and
defaults to Gemini, which is where the pipeline's paid work already went — the
free tier has no balance to exhaust. Anthropic stays one variable away.

This module deliberately does NOT cover Agent 1's gap analysis: that call is
schema-constrained per provider and already has its own tuned path, and folding
it in here would mean one abstraction serving two quite different contracts.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import config

log = logging.getLogger("orchestrator.llm")


class ProviderUnavailable(RuntimeError):
    """
    The provider could not be reached at all, or refused at the account level.

    Distinct from a bad answer: callers should degrade — hold the copy, omit
    the narrative — rather than fail the run, because nothing about the payload
    is wrong and nothing a retry does will change the outcome this run.
    """


def _anthropic(system: str, prompt: str, *, max_tokens: int,
               schema: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    """
    Request-shape notes for this model family, all of which are 400s if broken:
    no temperature/top_p/top_k, no assistant prefill, thinking on by default and
    `budget_tokens` removed — depth is `output_config.effort`. Structured output
    replaces the prefill trick.
    """
    from anthropic import Anthropic

    client = Anthropic(api_key=config.require_env("ANTHROPIC_API_KEY"))
    out_cfg: dict[str, Any] = {"effort": config.ANTHROPIC_EFFORT}
    if schema:
        out_cfg["format"] = {"type": "json_schema", "schema": schema}

    kwargs: dict[str, Any] = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": out_cfg,
    }
    if config.ANTHROPIC_FALLBACKS.lower() not in {"", "off", "false", "0"}:
        kwargs["betas"] = [config.ANTHROPIC_FALLBACK_BETA]
        kwargs["fallbacks"] = config.ANTHROPIC_FALLBACKS
        create = client.beta.messages.create
    else:
        create = client.messages.create

    resp = create(**kwargs)
    # Check stop_reason before touching content — a refusal leaves it empty, so
    # indexing content[0] would raise IndexError and hide the real reason.
    if getattr(resp, "stop_reason", None) == "refusal":
        detail = getattr(resp, "stop_details", None)
        raise ProviderUnavailable(
            f"declined by safety classifiers (category="
            f"{getattr(detail, 'category', None)!r})"
        )
    text = "".join(b.text for b in resp.content
                   if getattr(b, "type", "") == "text").strip()
    usage = getattr(resp, "usage", None)
    return text, {
        "provider": "anthropic",
        "model": getattr(resp, "model", config.ANTHROPIC_MODEL),
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


def _gemini(system: str, prompt: str, *, max_tokens: int,
            schema: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    """
    Reuses Agent 2's model resolution rather than pinning a name — pinning has
    failed twice, once because 2.5-pro is absent from the free tier (429
    "limit: 0", which reads as rate-limiting and is not) and once because
    2.5-flash is withdrawn for keys issued after a certain date.

    JSON mode guarantees valid JSON and NOTHING about its shape, so callers
    that need a particular envelope must say so in the prompt. Agent 1 learned
    that by getting a bare array where it expected an object.
    """
    from agent2_writer_listener import resolve_model

    model_name = resolve_model()
    cfg: dict[str, Any] = {"temperature": 0.4, "top_p": 0.95,
                           "max_output_tokens": max_tokens}
    if schema:
        cfg["response_mime_type"] = "application/json"

    try:
        from google import genai as new_genai
        from google.genai import types as genai_types

        client = new_genai.Client(api_key=config.require_env("GEMINI_API_KEY"))
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(system_instruction=system, **cfg),
        )
        text, usage = (resp.text or "").strip(), getattr(resp, "usage_metadata", None)
    except ImportError:
        import google.generativeai as genai   # legacy SDK — deprecated by Google

        genai.configure(api_key=config.require_env("GEMINI_API_KEY"))
        model = genai.GenerativeModel(model_name=model_name,
                                      system_instruction=system,
                                      generation_config=cfg)
        resp = model.generate_content(prompt)
        text, usage = (resp.text or "").strip(), getattr(resp, "usage_metadata", None)

    return text, {
        "provider": "gemini",
        "model": model_name,
        "input_tokens": getattr(usage, "prompt_token_count", None),
        "output_tokens": getattr(usage, "candidates_token_count", None),
    }


_PROVIDERS = {"anthropic": _anthropic, "gemini": _gemini}


def complete(system: str, prompt: str, *, max_tokens: int = 4000,
             schema: dict[str, Any] | None = None,
             purpose: str = "") -> tuple[str, dict[str, Any]]:
    """
    Ask the configured provider for a completion. Returns (text, meta).

    Raises ProviderUnavailable when the provider cannot answer at all — an
    exhausted balance, a revoked key, a rate limit, a safety refusal. Callers
    hold their output rather than failing the run: a busy or unfunded provider
    is not a defect in the payload, and every one of these agents has a
    degraded path that is honest about producing nothing.
    """
    name = config.PROSE_PROVIDER
    fn = _PROVIDERS.get(name)
    if fn is None:
        raise ProviderUnavailable(
            f"PROSE_PROVIDER={name!r} is not one of {sorted(_PROVIDERS)}"
        )
    try:
        text, meta = fn(system, prompt, max_tokens=max_tokens, schema=schema)
    except ProviderUnavailable:
        raise
    except Exception as exc:
        msg = str(exc)
        if config.terminal_provider_error(msg) or config.rate_limited(msg):
            raise ProviderUnavailable(f"{name} unavailable: {config.redact(msg)}") from exc
        raise
    if not text:
        raise ProviderUnavailable(f"{name} returned an empty response")
    log.info("%s via %s (%s): %s in / %s out", purpose or "completion",
             meta["provider"], meta["model"],
             meta["input_tokens"], meta["output_tokens"])
    return text, meta


def complete_json(system: str, prompt: str, schema: dict[str, Any],
                  *, max_tokens: int = 4000,
                  purpose: str = "") -> tuple[Any, dict[str, Any]]:
    """`complete()` plus parsing. A provider that returns unparseable JSON is a
    bad answer, not an unavailable provider — that raises ValueError, so the
    caller can tell "try again later" apart from "this came back wrong"."""
    text, meta = complete(system, prompt, max_tokens=max_tokens,
                          schema=schema, purpose=purpose)
    try:
        return json.loads(text), meta
    except json.JSONDecodeError as exc:
        raise ValueError(f"{meta['provider']} returned unparseable JSON: {exc}") from exc
