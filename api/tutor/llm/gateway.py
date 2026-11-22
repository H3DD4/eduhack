"""LLM gateway: the only path to model providers.

    llm = build_llm(settings)
    out = llm.json("generate_qcm", {...variables...})

- Providers: Anthropic (Messages API), OpenAI-compatible (OpenAI, Groq, Ollama, Gemini's OpenAI endpoint),
  and MockLLM, a deterministic offline adapter that builds real (simple) material from the CONTEXT chunks so
  every flow runs without keys. `simulated` is reported to the UI; mock output is never presented as AI.
- JSON only: the reply is parsed, repaired once (first {...} block), checked for required keys, and retried
  once with the parse error. Callers treat a failure as "no output", never as an empty success.
- Budget: every call reports tokens to an optional `meter(track_id, tokens)` callback.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .. import http
from ..config import TutorSettings
from .prompts import TASKS, Task, render_user

log = logging.getLogger("tutor.llm")


class LLMError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    name: str

    def complete(self, system: str, user: str, *, tier: str, max_tokens: int) -> tuple[str, LLMUsage]: ...


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start: i + 1])
    raise ValueError("unterminated JSON object")


# --------------------------------------------------------------------------------------------- providers
class AnthropicProvider:
    name = "anthropic"

    def __init__(self, s: TutorSettings):
        self.s = s

    def complete(self, system: str, user: str, *, tier: str, max_tokens: int) -> tuple[str, LLMUsage]:
        model = self.s.model_large if tier == "large" else self.s.model_small
        r = http.post("https://api.anthropic.com/v1/messages", timeout=self.s.llm_timeout_s, headers={
            "x-api-key": self.s.anthropic_api_key or "", "anthropic-version": "2023-06-01",
            "content-type": "application/json"},
            json={"model": model, "max_tokens": max_tokens, "system": system,
                  "messages": [{"role": "user", "content": user}]})
        if r.status == 429 or r.status >= 500:
            raise LLMError(f"RETRYABLE_{r.status}")
        if r.status >= 400:
            raise LLMError(f"HTTP_{r.status}")
        data = r.json()
        if data.get("stop_reason") == "refusal":
            raise LLMError("REFUSED")
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage", {})
        return text, LLMUsage(int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)))


class OpenAICompatProvider:
    """OpenAI, Groq, Ollama (/v1) and Gemini (OpenAI-compatible endpoint) share one wire format."""

    def __init__(self, name: str, base_url: str, api_key: str | None, model_large: str, model_small: str,
                 timeout: int, json_mode: bool = True):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.models = {"large": model_large, "small": model_small}
        self.timeout = timeout
        self.json_mode = json_mode

    def complete(self, system: str, user: str, *, tier: str, max_tokens: int) -> tuple[str, LLMUsage]:
        body: dict[str, Any] = {"model": self.models[tier], "temperature": 0.2, "max_tokens": max_tokens,
                                "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": user}]}
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        r = http.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=self.timeout)
        if r.status == 429 or r.status >= 500:
            raise LLMError(f"RETRYABLE_{r.status}")
        if r.status >= 400:
            raise LLMError(f"HTTP_{r.status}")
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        if choice.get("finish_reason") == "content_filter":
            raise LLMError("REFUSED")
        u = data.get("usage", {})
        return (choice.get("message", {}).get("content") or "",
                LLMUsage(int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))))


class GeminiNativeProvider:
    """Native Google Generative Language API (v1beta) supporting Gemini 4 Hydrogen with Flash fallback."""

    name = "gemini"

    def __init__(self, s: TutorSettings):
        self.s = s

    def complete(self, system: str, user: str, *, tier: str, max_tokens: int) -> tuple[str, LLMUsage]:
        primary = self.s.gemini_model[7:] if self.s.gemini_model.startswith("models/") else self.s.gemini_model
        models = [primary]
        for fb in ("gemini-2.5-flash", "gemini-flash-latest"):
            if fb not in models:
                models.append(fb)
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2, "maxOutputTokens": max_tokens},
        }
        last_status = 503
        for idx, model_id in enumerate(models):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={self.s.gemini_api_key or ''}"
            try:
                r = http.post(
                    url,
                    json=body,
                    headers={"x-goog-api-key": self.s.gemini_api_key or "", "content-type": "application/json"},
                    timeout=min(self.s.llm_timeout_s, 45) if idx == 0 else 25,
                )
            except Exception as exc:  # noqa: BLE001
                if idx + 1 < len(models):
                    continue
                raise LLMError("RETRYABLE_503") from exc
            last_status = r.status
            if r.status in (429, 503) and idx + 1 < len(models):
                continue
            if r.status == 429 or r.status >= 500:
                raise LLMError(f"RETRYABLE_{r.status}")
            if r.status >= 400:
                raise LLMError(f"HTTP_{r.status}")
            data = r.json()
            cands = data.get("candidates") or []
            if not cands or cands[0].get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
                raise LLMError("REFUSED")
            text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []) if not p.get("thought"))
            u = data.get("usageMetadata", {})
            return text, LLMUsage(int(u.get("promptTokenCount", 0)), int(u.get("candidatesTokenCount", 0)))
        raise LLMError(f"RETRYABLE_{last_status}")


# --------------------------------------------------------------------------------------------- gateway
Meter = Callable[[str | None, int], None]


class LLM:
    """Task-level JSON calls. `simulated` is True for the offline mock."""

    def __init__(self, provider: Provider | None, *, meter: Meter | None = None, mock: Any = None,
                 fallback_to_mock: bool = True):
        self.provider = provider
        self.meter = meter
        self.mock = mock
        self.fallback_to_mock = fallback_to_mock
        self.simulated = provider is None
        self.name = provider.name if provider else "mock"

    def json(self, task_name: str, variables: dict[str, Any], *, track_id: str | None = None,
             tier: str | None = None) -> dict[str, Any]:
        task: Task = TASKS[task_name]
        if self.provider is None:
            out = self.mock.run(task_name, variables)
            self._check(task, out)
            return out
        user = render_user(task, variables)
        last_err = "UNKNOWN"
        for attempt in range(3):
            try:
                text, usage = self.provider.complete(task.system, user, tier=tier or task.tier,
                                                     max_tokens=task.max_tokens)
                if self.meter:
                    self.meter(track_id, usage.input_tokens + usage.output_tokens)
                out = extract_json(text)
                self._check(task, out)
                return out
            except LLMError as e:
                last_err = e.code
                if e.code in ("HTTP_402", "RETRYABLE_503", "RETRYABLE_429") and self.fallback_to_mock and self.mock is not None:
                    out = self.mock.run(task_name, variables)
                    self._check(task, out)
                    return out
                if not e.code.startswith("RETRYABLE"):
                    raise
                time.sleep(1.5 * (attempt + 1))
            except (ValueError, KeyError) as e:  # bad JSON or missing keys: retry once with the reason
                last_err = f"INVALID_OUTPUT:{e}"
                user = f"{user}\n\nYour previous reply was not valid ({e}). Reply with the JSON object only."
        if self.fallback_to_mock and self.mock is not None:
            out = self.mock.run(task_name, variables)
            self._check(task, out)
            return out
        raise LLMError(last_err)

    @staticmethod
    def _check(task: Task, out: Any) -> None:
        if not isinstance(out, dict):
            raise ValueError("output is not an object")
        missing = [k for k in task.required if k not in out]
        if missing:
            raise KeyError(f"missing keys {missing}")


def build_llm(s: TutorSettings, *, meter: Meter | None = None) -> LLM:
    from .mock import MockLLM

    p = s.llm_provider
    if p == "auto":
        p = ("anthropic" if s.anthropic_api_key else "openai" if s.openai_api_key else
             "groq" if s.groq_api_key else "gemini" if s.gemini_api_key else
             "ollama" if s.ollama_api_key else "mock")
    provider: Provider | None
    if p == "anthropic" and s.anthropic_api_key:
        provider = AnthropicProvider(s)
    elif p == "openai" and s.openai_api_key:
        provider = OpenAICompatProvider("openai", "https://api.openai.com/v1", s.openai_api_key,
                                        s.openai_model_large, s.openai_model_small, s.llm_timeout_s)
    elif p == "groq" and s.groq_api_key:
        provider = OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", s.groq_api_key,
                                        s.groq_model, s.groq_model, s.llm_timeout_s)
    elif p == "gemini" and s.gemini_api_key:
        provider = GeminiNativeProvider(s)
    elif p == "ollama":
        base = s.ollama_url.rstrip("/")
        v1 = base if base.endswith("/v1") else f"{base}/v1"
        provider = OpenAICompatProvider("ollama", v1, s.ollama_api_key, s.ollama_model, s.ollama_model,
                                        max(s.llm_timeout_s, 180))
    else:
        provider = None
    return LLM(provider, meter=meter, mock=MockLLM(), fallback_to_mock=s.fallback_to_mock)
