"""
LLM access for the narrative features. Three providers behind one function, complete():

  groq       OpenAI-compatible Chat Completions (default; the server's shared key, rate limited)
  gemini     Google's OpenAI-compatible endpoint
  anthropic  Claude through the official Anthropic SDK

Resolution per request:
  1. The visitor's own key (headers X-LLM-Provider / X-LLM-Key / X-LLM-Model, placed in a context variable by
     middleware). It is used for that request only and is never stored or logged.
  2. Otherwise the server key for DEFAULT_LLM_PROVIDER (shared, so subject to per-IP and per-instance budgets).
  3. Otherwise None: callers fall back to deterministic, data-driven text and the product keeps working.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend import ratelimit
from backend.config import get_settings

log = logging.getLogger("trading_engine.llm")

visitor_llm: contextvars.ContextVar[dict | None] = contextvars.ContextVar("visitor_llm", default=None)

PROVIDERS: dict[str, dict] = {
    "groq": {"label": "Groq", "base": "https://api.groq.com/openai/v1"},
    "gemini": {"label": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai"},
    "anthropic": {"label": "Anthropic Claude"},
}
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(RuntimeError):
    """The request could not be served; the message is safe to show to the visitor."""


@dataclass
class Target:
    provider: str
    key: str
    model: str
    shared: bool  # True when using the server's key


def _default_model(provider: str) -> str:
    s = get_settings()
    return {"groq": s.groq_model, "gemini": s.gemini_model, "anthropic": s.anthropic_model}[provider]


def _server_key(provider: str) -> str:
    s = get_settings()
    return {"groq": s.groq_api_key, "gemini": s.gemini_api_key, "anthropic": s.anthropic_api_key}.get(provider, "")


def resolve() -> Target | None:
    v = visitor_llm.get()
    if v and v.get("key") and v.get("provider") in PROVIDERS:
        return Target(v["provider"], v["key"], (v.get("model") or "").strip() or _default_model(v["provider"]), shared=False)
    s = get_settings()
    order = [s.default_llm_provider] + [p for p in PROVIDERS if p != s.default_llm_provider]
    for p in order:
        if p in PROVIDERS and _server_key(p):
            return Target(p, _server_key(p), _default_model(p), shared=True)
    return None


def status() -> dict:
    t = resolve()
    s = get_settings()
    return {
        "provider": t.provider if t else None,
        "provider_label": PROVIDERS[t.provider]["label"] if t else None,
        "model": t.model if t else None,
        "key_source": None if not t else ("server" if t.shared else "visitor"),
        "shared_budget": None if not t or not t.shared else {
            "per_ip_10min": s.llm_shared_per_ip_10min,
            "remaining_for_you": ratelimit.remaining(f"llm:ip:{ratelimit.client_ip.get()}", s.llm_shared_per_ip_10min, 600),
        },
        "server_providers": [p for p in PROVIDERS if _server_key(p)],
    }


def available() -> bool:
    return resolve() is not None


def _charge_shared_budget() -> None:
    s = get_settings()
    ip = ratelimit.client_ip.get()
    try:
        ratelimit.check_all([
            (f"llm:ip:{ip}", s.llm_shared_per_ip_10min, 600),
            ("llm:global:min", s.llm_shared_per_minute, 60),
            ("llm:global:day", s.llm_shared_per_day, 86400),
        ])
    except ratelimit.RateLimited as exc:
        raise LLMUnavailable(
            f"The shared AI quota is busy (retry in about {exc.retry_after}s). Add your own Groq, Gemini or Anthropic key in Settings for unlimited use."
        ) from exc


# Identical prompts (same data, same provider and model) within this window reuse the answer and spend no quota
_ANSWER_TTL_S = 600.0
_answers: dict[str, tuple[float, Any]] = {}


def _answer_key(t: Target, messages: list[dict], system: str | None, schema: dict | None) -> str:
    payload = json.dumps([t.provider, t.model, system, messages, schema], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_THINK = re.compile(r"<think>.*?</think>", re.S)


def _parse_json(text: str) -> dict:
    t = _THINK.sub("", text).strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < 0:
        raise LLMUnavailable("The AI response could not be parsed.")
    try:
        return json.loads(t[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMUnavailable("The AI response could not be parsed.") from exc


def _conform(data: dict, schema: dict) -> dict:
    """Light validation: fill missing required keys with empty values of the right type."""
    out = dict(data)
    for k in schema.get("required", []):
        typ = schema["properties"].get(k, {}).get("type")
        if k not in out or out[k] is None:
            out[k] = [] if typ == "array" else "" if typ == "string" else None
        elif typ == "array" and not isinstance(out[k], list):  # looser JSON modes may return a single value
            out[k] = [out[k]]
        enum = schema["properties"].get(k, {}).get("enum")
        if enum and out[k] not in enum:
            out[k] = enum[-1] if "neutral" not in enum else "neutral"
    return out


async def _openai_compatible(t: Target, messages: list[dict], system: str | None, effort: str, max_tokens: int, schema: dict | None) -> str:
    base = PROVIDERS[t.provider]["base"]
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    body: dict[str, Any] = {"model": t.model, "messages": msgs, "max_completion_tokens": max_tokens}
    if t.provider == "groq" and t.model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = effort if effort in ("low", "medium", "high") else "low"
        body["include_reasoning"] = False
    elif t.provider == "groq" and "qwen" in t.model:
        body["reasoning_format"] = "hidden"
    elif t.provider == "gemini":
        body["reasoning_effort"] = effort if effort in ("low", "medium", "high") else "low"
    if schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "result", "strict": True, "schema": schema}}
    headers = {"Authorization": f"Bearer {t.key}"}
    async with httpx.AsyncClient(timeout=get_settings().llm_timeout_s) as client:
        for attempt in range(2):
            try:
                r = await client.post(f"{base}/chat/completions", headers=headers, json=body)
            except httpx.HTTPError as exc:
                raise LLMUnavailable(f"Could not reach {PROVIDERS[t.provider]['label']}.") from exc
            if r.status_code == 400 and attempt == 0:
                # Some models reject reasoning or json_schema options: retry with the most portable request
                body.pop("reasoning_effort", None)
                body.pop("include_reasoning", None)
                body.pop("reasoning_format", None)
                body["max_tokens"] = body.pop("max_completion_tokens", max_tokens)
                if schema:
                    body["response_format"] = {"type": "json_object"}
                    body["messages"] = msgs[:-1] + [{
                        "role": msgs[-1]["role"],
                        "content": f"{msgs[-1]['content']}\n\nRespond with a single JSON object matching this JSON Schema:\n{json.dumps(schema)}",
                    }]
                continue
            break
    if r.status_code in (401, 403):
        raise LLMUnavailable(f"The {PROVIDERS[t.provider]['label']} key was rejected. Check it in Settings.")
    if r.status_code == 404:
        raise LLMUnavailable(f"Model {t.model} is not available on {PROVIDERS[t.provider]['label']}.")
    if r.status_code == 429:
        raise LLMUnavailable(f"{PROVIDERS[t.provider]['label']} is rate limiting requests. Try again in a minute.")
    if r.status_code >= 400:
        log.warning("LLM %s error %s: %s", t.provider, r.status_code, r.text[:300])
        raise LLMUnavailable(f"{PROVIDERS[t.provider]['label']} returned an error ({r.status_code}).")
    choice = (r.json().get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    return _THINK.sub("", text).strip()


async def _anthropic(t: Target, messages: list[dict], system: str | None, effort: str, max_tokens: int, schema: dict | None) -> str:
    import anthropic

    output_config: dict[str, Any] = {"effort": effort}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    kwargs: dict[str, Any] = {
        "model": t.model, "max_tokens": max(max_tokens, 4000), "messages": messages, "output_config": output_config,
        "betas": [ANTHROPIC_FALLBACK_BETA], "fallbacks": "default",
    }
    if system:
        kwargs["system"] = system
    client = anthropic.AsyncAnthropic(api_key=t.key, timeout=get_settings().llm_timeout_s, max_retries=1)
    try:
        resp = await client.beta.messages.create(**kwargs)
    except anthropic.AuthenticationError as exc:
        raise LLMUnavailable("The Anthropic API key was rejected. Check it in Settings.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise LLMUnavailable("The Anthropic API key does not have access to this model.") from exc
    except anthropic.NotFoundError as exc:
        raise LLMUnavailable(f"Model {t.model} is not available to this key.") from exc
    except anthropic.RateLimitError as exc:
        raise LLMUnavailable("Anthropic is rate limiting requests. Try again shortly.") from exc
    except anthropic.BadRequestError as exc:
        log.warning("Anthropic bad request: %s", exc.message)
        raise LLMUnavailable("The AI request was rejected.") from exc
    except anthropic.APIStatusError as exc:
        raise LLMUnavailable(f"Anthropic returned an error ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMUnavailable("Could not reach Anthropic.") from exc
    finally:
        await client.close()
    if resp.stop_reason == "refusal":
        raise LLMUnavailable("The model declined to answer this request.")
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


async def complete(
    prompt: str | list[dict],
    *,
    system: str | None = None,
    effort: str = "low",
    max_tokens: int = 1200,
    schema: dict | None = None,
) -> str | dict | None:
    """Return text (or a dict when `schema` is given); None when no provider is configured."""
    t = resolve()
    if t is None:
        return None
    messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
    key = _answer_key(t, messages, system, schema)
    hit = _answers.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    if t.shared:
        _charge_shared_budget()
    if t.provider == "anthropic":
        text = await _anthropic(t, messages, system, effort, max_tokens, schema)
    else:
        text = await _openai_compatible(t, messages, system, effort, max_tokens, schema)
    result = _conform(_parse_json(text), schema) if schema else text
    if len(_answers) > 256:
        _answers.clear()
    if result:
        _answers[key] = (time.time() + _ANSWER_TTL_S, result)
    return result


async def complete_or(fallback: Any, prompt: str | list[dict], **kw) -> tuple[Any, str]:
    """complete() that never raises: returns (result, source) with source 'ai', 'fallback' or a readable error."""
    try:
        out = await complete(prompt, **kw)
    except LLMUnavailable as exc:
        return fallback, str(exc)
    if out is None or out == "" or out == {}:
        return fallback, "fallback"
    return out, "ai"
