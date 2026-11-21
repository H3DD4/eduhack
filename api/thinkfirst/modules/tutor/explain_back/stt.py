"""Speech-to-text behind an interface.

- ``demo`` (default): no speech recognition. Returns a clearly labeled fixture transcript that the student
  must edit to match what they said. Audio is never analyzed.
- ``gemini`` (opt-in via STT_PROVIDER=gemini + GEMINI_API_KEY): raw audio is sent to Google for transcription
  only. Only enable after disclosing the processor (OPEN_QUESTIONS Q-05).
Never scores duration, accent, fluency, pauses or emotion.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field

import httpx

from thinkfirst.config import get_settings

DEMO_TEXT = (
    "Distribution means the 2 multiplies every term inside the brackets. "
    "So 2(x + 3) is 2 times x plus 2 times 3, which gives 2x + 6. "
    "It works because 2(x + 3) means two groups of x + 3. "
    "It does not work over a product, because 2(x · 3) is just 6x, not 2x · 6."
)
DEMO_LABEL = ("Demo transcription (simulated): no speech-recognition service is configured, so this fixture text "
              "stands in for your recording. Edit it to match what you actually said.")


@dataclass
class STTResult:
    text: str
    uncertain: list[dict] = field(default_factory=list)
    label: str = ""
    simulated: bool = True
    error_code: str | None = None


def transcribe(audio: bytes, mime: str) -> STTResult:
    s = get_settings()
    if s.stt_provider == "groq" and s.groq_api_key:
        result = _groq(audio, mime)
        if result.error_code and s.gemini_api_key:
            return _gemini(audio, mime)  # reinforce: fall back to the other configured processor
        return result
    if s.stt_provider == "gemini" and s.gemini_api_key:
        return _gemini(audio, mime)
    return STTResult(text=DEMO_TEXT, uncertain=[{"id": "u1", "text": "brackets", "reason": "Low confidence (simulated)"}],
                     label=DEMO_LABEL, simulated=True)


_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav",
        "audio/x-wav": "wav"}


def _groq(audio: bytes, mime: str) -> STTResult:
    """Groq-hosted Whisper. Low-confidence segments (avg_logprob) become 'unclear' spans to resolve."""
    s = get_settings()
    base = mime.split(";")[0]
    try:
        r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions",
                       headers={"Authorization": f"Bearer {s.groq_api_key or ''}"},
                       data={"model": s.groq_stt_model, "response_format": "verbose_json", "temperature": "0"},
                       files={"file": (f"take.{_EXT.get(base, 'webm')}", audio, base)}, timeout=120)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        return STTResult(text="", label="Transcription failed", simulated=False, error_code=type(exc).__name__[:40])
    text = str(data.get("text", "")).strip()
    unclear = []
    for seg in data.get("segments", []) or []:
        seg_text = str(seg.get("text", "")).strip()
        if seg_text and seg_text in text and (seg.get("avg_logprob", 0) < -0.8 or seg.get("no_speech_prob", 0) > 0.5):
            unclear.append(seg_text)
    return STTResult(text=text, uncertain=[{"id": f"u{i}", "text": u, "reason": "Low confidence"} for i, u in enumerate(unclear, 1)],
                     label="Transcribed by Whisper on Groq (check names, numbers and meaning)", simulated=False)


def _gemini(audio: bytes, mime: str) -> STTResult:
    s = get_settings()
    prompt = ("Transcribe this student's spoken explanation verbatim, in whatever language(s) they used (French, English, "
              "Arabic or Tunisian dialect may be mixed; do not translate). Return JSON {\"text\": string, "
              "\"unclear\": [words or short phrases you are unsure about, copied exactly as they appear in text]}.")
    body = {"contents": [{"role": "user", "parts": [
        {"inline_data": {"mime_type": mime.split(";")[0], "data": base64.b64encode(audio).decode()}}, {"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    try:
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:generateContent",
                       json=body, headers={"x-goog-api-key": s.gemini_api_key or ""}, timeout=120)
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        data = json.loads("".join(p.get("text", "") for p in parts))
        text = str(data.get("text", "")).strip()
        unclear = [str(u) for u in data.get("unclear", []) if str(u) and str(u) in text]
    except Exception as exc:  # noqa: BLE001
        return STTResult(text="", label="Transcription failed", simulated=False, error_code=type(exc).__name__[:40])
    return STTResult(text=text, uncertain=[{"id": f"u{i}", "text": u, "reason": "Low confidence"} for i, u in enumerate(unclear, 1)],
                     label="Transcribed by Google Gemini (check names, numbers and meaning)", simulated=False)
