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
import re
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

    try:
        resp = create(**kwargs)
    except Exception as beta_exc:                       # SDK-specific, so by text
        # The server-side fallbacks beta is optional; broadcasting is not. Some
        # models (claude-sonnet-5) reject the parameter with a 400 rather than
        # ignoring it, and the outer retry loop would otherwise re-send the same
        # rejected kwargs three times and fail the whole run. Strip the beta and
        # retry once on the plain endpoint — mirrors Agents 1 and 2, which grew
        # their own _call_anthropic before this shared helper existed.
        if "fallbacks" in str(beta_exc).lower() and "betas" in kwargs:
            log.warning("anthropic rejects the fallbacks beta; retrying without it")
            kwargs.pop("betas", None)
            kwargs.pop("fallbacks", None)
            resp = client.messages.create(**kwargs)
        else:
            raise
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
    from agent2_writer_listener import resolve_model, mark_model_unusable

    cfg: dict[str, Any] = {"temperature": 0.4, "top_p": 0.95,
                           "max_output_tokens": max_tokens}
    if schema:
        cfg["response_mime_type"] = "application/json"

    # Retire a withdrawn model HERE, not only in the agents that grew their own
    # handling. Agents 1 and 2 each call mark_model_unusable() from their own
    # Gemini paths; Agent 3 goes through this module, which resolved a name and
    # then never reacted when the API refused it.
    #
    # On 23 Aug that cost the first real broadcast run: gemini-2.5-flash now
    # answers 404 "no longer available to new users", Agent 3 retried the same
    # dead name three times, and two articles that had just gone live failed to
    # produce a single post. The resolution machinery existed and this caller
    # simply never told it anything was wrong.
    #
    # One retry, because re-resolution either yields a different name or it
    # does not; looping past that is how a dead account burns its rate limit.
    last: Exception | None = None
    for _try in range(2):
        model_name = resolve_model()
        try:
            return _gemini_once(system, prompt, model_name, cfg)
        except Exception as exc:                      # SDK-specific, so by text
            msg = str(exc)
            retired = ("no longer available" in msg
                       or ("404" in msg and "models/" in msg)
                       or "NOT_FOUND" in msg.upper())
            if not retired:
                raise
            log.warning("gemini model %s is retired (%s) — re-resolving",
                        model_name, msg[:90])
            mark_model_unusable(model_name)
            last = exc
    raise last if last else RuntimeError("gemini call failed with no error recorded")


def _gemini_once(system: str, prompt: str, model_name: str,
                 cfg: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """One attempt against one named model. Split out so the caller can retire."""
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


def _openai(system: str, prompt: str, *, max_tokens: int,
            schema: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    """
    The third brain. Mirrors Agent 1's OpenAI call (chat.completions with
    structured output) so GPT can draft (Agent 2) and compose social copy
    (Agent 3) through the same PROSE_PROVIDER knob, not just analyse gaps.

    OpenAI's strict json_schema demands additionalProperties:false and every key
    required — the same shape Anthropic wants. When a caller's schema is not
    strict-safe the API 400s; drafting matters more than strictness, so we retry
    once as a plain json_object (the task is still described in the prompt).
    """
    from openai import OpenAI

    client = OpenAI(api_key=config.require_env("OPENAI_API_KEY"))
    kwargs: dict[str, Any] = {
        "model": config.OPENAI_MODEL,
        "temperature": 0.4,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
    }
    if schema:
        kwargs["response_format"] = {"type": "json_schema",
            "json_schema": {"name": "payload", "strict": True, "schema": schema}}
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:                             # SDK-specific, so by text
        if schema and re.search(r"schema|strict|additionalProperties|required|response_format",
                                str(exc), re.I):
            log.warning("openai rejected the strict json_schema; retrying as json_object")
            kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
        else:
            raise
    text = (resp.choices[0].message.content or "").strip()
    usage = getattr(resp, "usage", None)
    return text, {
        "provider": "openai",
        "model": getattr(resp, "model", config.OPENAI_MODEL),
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
    }


_PROVIDERS = {"anthropic": _anthropic, "gemini": _gemini, "openai": _openai}


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
