"""llm_gateway service: the ONLY path to model providers.

- Provider routing: LLM_PROVIDER=auto picks Anthropic if ANTHROPIC_API_KEY, else Gemini if GEMINI_API_KEY,
  else the explicitly labeled demo adapter (deterministic heuristics registered by owning modules).
- Output is JSON validated against the prompt's schema keys; invalid/refused output => status != ok and
  callers treat the result as *unscored*, never zero.
- Logs are metadata only (LLMCallLog). Prompts/responses are not persisted or logged.
- Cache: short in-process TTL cache keyed by owner + prompt + version + input hash (never shared across users).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.modules.tutor.llm.models import LLMCallLog
from thinkfirst.modules.tutor.llm.prompts import REGISTRY, PromptTemplate

log = logging.getLogger("thinkfirst.llm")

DemoFn = Callable[[dict[str, Any]], dict[str, Any]]
_demo_adapters: dict[str, DemoFn] = {}
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL_S = 600
# Circuit breaker: a provider that just timed out / rate-limited / errored is skipped for a while.
_cooldown_until: dict[str, float] = {}
COOLDOWN_S = 300

# Rough public list-price estimates in USD per 1M tokens (labelled estimates, used for metadata only).
_PRICES = {"anthropic": (4.0, 20.0), "gemini": (0.30, 2.50), "groq": (0.15, 0.60), "ollama": (0.0, 0.0), "demo": (0.0, 0.0)}

PROVIDER_LABELS = {
    "demo": "Simulated assessment (demo adapter, no AI service configured)",
    "anthropic": "AI assessment (Anthropic Claude) — not calibrated",
    "gemini": "AI assessment (Google Gemini) — not calibrated",
    "groq": "AI assessment (Groq-hosted open model) — not calibrated",
    "ollama": "AI assessment (Ollama model) — not calibrated",
}
PROCESSOR_NAMES = {
    "demo": None,
    "anthropic": "Anthropic",
    "gemini": "Google (Gemini API)",
    "groq": "Groq",
    "ollama": "Ollama",
}


def register_demo(prompt_id: str):
    def deco(fn: DemoFn) -> DemoFn:
        _demo_adapters[prompt_id] = fn
        return fn

    return deco


@dataclass
class GatewayResult:
    output: dict[str, Any] | None
    provider: str
    model: str
    status: str  # ok | invalid_output | error | refused
    simulated: bool
    label: str
    error_code: str | None = None


def _has_key(p: str) -> bool:
    s = get_settings()
    return {
        "anthropic": bool(s.anthropic_api_key),
        "gemini": bool(s.gemini_api_key),
        "groq": bool(s.groq_api_key),
        "ollama": bool(s.ollama_api_key),
        "demo": True,
    }.get(p, False)


def active_provider() -> str:
    s = get_settings()
    if s.llm_provider in ("demo", "anthropic", "gemini", "groq", "ollama"):
        return s.llm_provider if _has_key(s.llm_provider) else "demo"
    for p in ("ollama", "anthropic", "groq", "gemini"):
        if _has_key(p):
            return p
    return "demo"


def provider_chain() -> list[str]:
    """Primary provider, then other configured real providers as fallbacks (never silently demo)."""
    primary = active_provider()
    if primary == "demo" or not get_settings().llm_fallback:
        return [primary]
    chain = [primary] + [p for p in ("ollama", "groq", "gemini", "anthropic") if p != primary and _has_key(p)]
    healthy = [p for p in chain if _cooldown_until.get(p, 0) <= time.time()]
    return healthy or chain  # if every provider is cooling down, still try them in order


def capabilities() -> dict[str, Any]:
    p = active_provider()
    chain = provider_chain()
    stt_p = get_settings().stt_provider if _has_key(get_settings().stt_provider) else "demo"
    return {"llm_provider": p, "fallbacks": chain[1:], "simulated": p == "demo", "label": PROVIDER_LABELS[p],
            "text_processors": [PROCESSOR_NAMES[x] for x in chain if PROCESSOR_NAMES[x]],
            "stt_provider": stt_p, "stt_simulated": stt_p == "demo", "audio_processor": PROCESSOR_NAMES.get(stt_p)}


def _validate(template: PromptTemplate, output: Any) -> bool:
    if not isinstance(output, dict):
        return False
    return all(k in output for k in template.output_schema.get("required", []))


def _call_anthropic(template: PromptTemplate, user_text: str) -> tuple[dict, int, int]:
    import anthropic

    s = get_settings()
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    resp = client.beta.messages.create(
        model=s.anthropic_model,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=template.system,
        messages=[{"role": "user", "content": user_text}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": template.output_schema}},
    )
    if resp.stop_reason == "refusal":
        raise _Refused()
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return json.loads(text), resp.usage.input_tokens, resp.usage.output_tokens


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return s


def _call_gemini(template: PromptTemplate, user_text: str) -> tuple[dict, int, int]:
    s = get_settings()
    primary = s.gemini_model[7:] if s.gemini_model.startswith("models/") else s.gemini_model
    models = [primary]
    if s.llm_fallback:
        for fb in ("gemini-2.5-flash", "gemini-flash-latest"):
            if fb not in models:
                models.append(fb)
    body = {
        "systemInstruction": {"parts": [{"text": template.system}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }
    last_err: Exception | None = None
    for idx, model_id in enumerate(models):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
        try:
            r = httpx.post(
                url,
                params={"key": s.gemini_api_key or ""},
                json=body,
                headers={"x-goog-api-key": s.gemini_api_key or ""},
                timeout=60 if idx == 0 else 25,
            )
        except httpx.TimeoutException as exc:
            last_err = _ProviderError("TIMEOUT")
            if idx + 1 < len(models):
                continue
            raise last_err from exc
        if r.status_code in (429, 503) and idx + 1 < len(models):
            last_err = _ProviderError("RATE_LIMITED" if r.status_code == 429 else "HTTP_503")
            continue
        if r.status_code == 429:
            raise _ProviderError("RATE_LIMITED")
        if r.status_code >= 400:
            raise _ProviderError(f"HTTP_{r.status_code}")
        data = r.json()
        cands = data.get("candidates") or []
        if not cands or cands[0].get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
            raise _Refused()
        text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []) if not p.get("thought"))
        usage = data.get("usageMetadata", {})
        return (
            json.loads(_strip_json_fence(text)),
            int(usage.get("promptTokenCount", 0)),
            int(usage.get("candidatesTokenCount", 0)),
        )
    raise last_err or _ProviderError("HTTP_503")


def _call_groq(template: PromptTemplate, user_text: str) -> tuple[dict, int, int]:
    s = get_settings()
    body = {"model": s.groq_model, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": template.system}, {"role": "user", "content": user_text}]}
    r = httpx.post("https://api.groq.com/openai/v1/chat/completions", json=body,
                   headers={"Authorization": f"Bearer {s.groq_api_key or ''}"}, timeout=60)
    if r.status_code == 429:
        raise _ProviderError("RATE_LIMITED")
    if r.status_code >= 400:
        raise _ProviderError(f"HTTP_{r.status_code}")
    data = r.json()
    choice = (data.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "content_filter":
        raise _Refused()
    usage = data.get("usage", {})
    return (json.loads(choice.get("message", {}).get("content") or ""), int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)))


def _call_ollama(template: PromptTemplate, user_text: str) -> tuple[dict, int, int]:
    s = get_settings()
    base = (s.ollama_base_url or "https://ollama.com/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {s.ollama_api_key}"} if s.ollama_api_key else {}
    messages = [{"role": "system", "content": template.system}, {"role": "user", "content": user_text}]

    # 1. Try OpenAI-compatible chat completions endpoint (/v1/chat/completions)
    v1_url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
    body_v1 = {
        "model": s.ollama_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    r = httpx.post(v1_url, json=body_v1, headers=headers, timeout=60)
    if r.status_code == 404:
        # 2. Fallback to native Ollama /api/chat endpoint
        root = base[:-3] if base.endswith("/v1") else (base[:-4] if base.endswith("/api") else base)
        chat_url = f"{root}/api/chat"
        r = httpx.post(
            chat_url,
            json={"model": s.ollama_model, "format": "json", "stream": False, "messages": messages,
                  "options": {"temperature": 0}},
            headers=headers,
            timeout=60,
        )
        if r.status_code == 429:
            raise _ProviderError("RATE_LIMITED")
        if r.status_code >= 400:
            raise _ProviderError(f"HTTP_{r.status_code}")
        data = r.json()
        content = (data.get("message") or {}).get("content") or ""
        return json.loads(content), int(data.get("prompt_eval_count", 0)), int(data.get("eval_count", 0))

    if r.status_code == 429:
        raise _ProviderError("RATE_LIMITED")
    if r.status_code >= 400:
        raise _ProviderError(f"HTTP_{r.status_code}")
    data = r.json()
    choice = (data.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "content_filter":
        raise _Refused()
    usage = data.get("usage", {})
    return (
        json.loads(choice.get("message", {}).get("content") or ""),
        int(usage.get("prompt_tokens", 0)),
        int(usage.get("completion_tokens", 0)),
    )


_CALLERS = {"anthropic": _call_anthropic, "gemini": _call_gemini, "groq": _call_groq, "ollama": _call_ollama}


class _Refused(Exception):
    pass


class _ProviderError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def run(db: Session, prompt_id: str, variables: dict[str, Any], *, owner_id: str | None, purpose: str,
        provider: str | None = None) -> GatewayResult:
    """Try the provider chain in order (e.g. Ollama, Gemini, Groq). One metadata log row per provider attempt."""
    chain = [provider] if provider else provider_chain()
    result: GatewayResult | None = None
    for p in chain:
        result = _run_one(db, prompt_id, variables, owner_id=owner_id, purpose=purpose, provider=p)
        if result.status == "ok":
            return result
        if result.status == "error" and p != "demo":
            _cooldown_until[p] = time.time() + COOLDOWN_S
    # If every real provider failed with quota/capacity errors (HTTP_402, HTTP_503, RATE_LIMITED, TIMEOUT)
    # in demo_mode, fall back to the explicitly labeled demo adapter (simulated=True) so local testing continues uninterrupted.
    if (
        result is not None
        and result.status == "error"
        and result.error_code in ("HTTP_402", "HTTP_503", "RATE_LIMITED", "TIMEOUT")
        and not provider
        and get_settings().demo_mode
        and prompt_id in _demo_adapters
    ):
        return _run_one(db, prompt_id, variables, owner_id=owner_id, purpose=purpose, provider="demo")
    assert result is not None
    return result


def _run_one(db: Session, prompt_id: str, variables: dict[str, Any], *, owner_id: str | None, purpose: str,
             provider: str) -> GatewayResult:
    template = REGISTRY[prompt_id]
    s = get_settings()
    model = {
        "anthropic": s.anthropic_model,
        "gemini": s.gemini_model,
        "groq": s.groq_model,
        "ollama": s.ollama_model,
    }.get(provider, "demo-heuristic-v1")
    key = hashlib.sha256(json.dumps([owner_id, prompt_id, template.version, provider, variables],
                                    sort_keys=True, default=str).encode()).hexdigest()
    entry = LLMCallLog(owner_id=owner_id, purpose=purpose, prompt_id=prompt_id, prompt_version=template.version,
                       provider=provider, model=model, status="ok", tokens_in=0, tokens_out=0,
                       cache_hit=False)
    started = time.perf_counter()
    output: dict | None = None
    cached = _cache.get(key)
    if cached and cached[0] > time.time():
        output, entry.cache_hit = cached[1], True
    else:
        try:
            if provider == "demo":
                fn = _demo_adapters.get(prompt_id)
                if fn is None:
                    raise _ProviderError("NO_DEMO_ADAPTER")
                output = fn(variables)
            else:
                output, entry.tokens_in, entry.tokens_out = _CALLERS[provider](template, template.render(variables))
            if not _validate(template, output):
                entry.status, entry.error_code, output = "invalid_output", "SCHEMA_MISMATCH", None
            else:
                _cache[key] = (time.time() + CACHE_TTL_S, output)
        except _Refused:
            entry.status, entry.error_code, output = "refused", "REFUSED", None
        except _ProviderError as exc:
            entry.status, entry.error_code, output = "error", exc.code, None
        except (json.JSONDecodeError, ValueError):
            entry.status, entry.error_code, output = "invalid_output", "INVALID_JSON", None
        except Exception as exc:  # noqa: BLE001 — metadata only
            entry.status, entry.error_code, output = "error", type(exc).__name__[:64], None
    entry.latency_ms = int((time.perf_counter() - started) * 1000)
    pin, pout = _PRICES.get(provider, (0.0, 0.0))
    entry.cost_micro_usd = int(entry.tokens_in * pin + entry.tokens_out * pout)
    db.add(entry)
    db.flush()
    log.info("llm_call", extra={"error_code": entry.error_code})
    return GatewayResult(output=output, provider=provider, model=model, status=entry.status,
                         simulated=provider == "demo", label=PROVIDER_LABELS[provider], error_code=entry.error_code)
