"""Course-likeness score: does a generated item look like it came from the student's own course?

    likeness = 0.35 vocabulary + 0.20 notation + 0.20 style + 0.15 difficulty + 0.10 format

>= 0.70 shown, 0.50-0.70 regenerated once with the weak components named, < 0.50 dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .fingerprint import NOTATION
from .textutil import norm, tokens

WEIGHTS = {"vocabulary": 0.35, "notation": 0.20, "style": 0.20, "difficulty": 0.15, "format": 0.10}


@dataclass
class CourseProfile:
    fingerprint: dict[str, Any]
    course_tokens: set[str] = field(default_factory=set)
    top_terms: set[str] = field(default_factory=set)

    @classmethod
    def build(cls, fingerprint: dict[str, Any], chunks: list[dict[str, Any]]) -> CourseProfile:
        toks: set[str] = set()
        for c in chunks:
            if c.get("origin") != "web":
                toks.update(tokens(c["text"]))
        top = {t for term, _ in fingerprint.get("vocabulary", [])[:40] for t in tokens(term)}
        return cls(fingerprint, toks, top)


def item_text(item: dict[str, Any]) -> str:
    k = item.get("kind")
    if k == "qcm":
        return item.get("stem", "") + " " + " ".join(o.get("text", "") for o in item.get("options", []))
    if k == "quiz":
        return item.get("question", "") + " " + str(item.get("answer", ""))
    if k == "fiche":
        return item.get("front", "") + " " + item.get("back", "")
    if k == "exercise":
        return item.get("statement", "") + " " + " ".join(p.get("prompt", "") for p in item.get("parts", []))
    if k == "resume":
        return " ".join(s.get("heading", "") + " " + " ".join(s.get("bullets", []) + s.get("formulas", []))
                        for s in item.get("sections", []))
    if k == "lesson":
        return " ".join(s.get("title", "") + " " + s.get("body", "") for s in item.get("sections", []))
    return str(item)


def _vocab(text: str, prof: CourseProfile) -> float:
    toks = [t for t in tokens(text) if len(t) >= 4 and not t.isdigit()]
    if not toks:
        return 0.6
    if not prof.course_tokens:
        return 0.6
    in_course = sum(1 for t in toks if t in prof.course_tokens) / len(toks)
    top_hits = len(set(toks) & prof.top_terms)
    return min(1.0, 0.75 * in_course + 0.25 * min(1.0, top_hits / 2))


def _notation(text: str, prof: CourseProfile) -> float:
    pref = prof.fingerprint.get("preferred_notation", {})
    used = checked = 0
    for fam, variants in NOTATION.items():
        if fam not in pref:
            continue
        found = [v for v, rx in variants.items() if re.search(rx, text)]
        if not found:
            continue
        checked += 1
        used += 1 if pref[fam] in found and len(found) == 1 else 0.5 if pref[fam] in found else 0
    return 1.0 if checked == 0 else used / checked


def _first_verb(text: str) -> str:
    m = re.match(r"^\W*(?:\d+[).]\s*|[a-h]\)\s*)?([A-Za-zÀ-ÿ']+(?:\s+(?:que|en|d[eé]duire))?)", text.strip())
    return norm(m.group(1)) if m else ""


def _style(item: dict[str, Any], text: str, prof: CourseProfile) -> float:
    fp = prof.fingerprint
    parts: list[float] = []
    verbs = {norm(v) for v in (fp.get("verbs") or {})}
    prompts = []
    if item.get("kind") == "exercise":
        prompts = [p.get("prompt", "") for p in item.get("parts", [])]
    elif item.get("kind") == "quiz":
        prompts = [item.get("question", "")]
    if verbs and prompts:
        hits = sum(1 for p in prompts if any(_first_verb(p).startswith(v.split()[0]) for v in verbs))
        parts.append(0.35 + 0.65 * hits / len(prompts))
    avg = fp.get("avg_question_words") or 0
    if avg and prompts:
        mean = sum(len(p.split()) for p in prompts) / len(prompts)
        parts.append(max(0.0, 1 - abs(mean - avg) / max(mean, avg, 1)))
    if item.get("kind") == "exercise" and fp.get("avg_subquestions"):
        n = len(item.get("parts", []))
        a = fp["avg_subquestions"]
        parts.append(max(0.0, 1 - abs(n - a) / max(n, a, 1)))
    return sum(parts) / len(parts) if parts else 0.8


def _difficulty(item: dict[str, Any], target: float) -> float:
    d = item.get("difficulty")
    if d is None:
        return 0.8
    return max(0.0, 1 - abs(float(d) - target) / 400)


def _format(item: dict[str, Any], prof: CourseProfile) -> float:
    qt = prof.fingerprint.get("question_types") or {}
    if not qt:
        return 0.8
    k = item.get("kind")
    if k == "qcm":
        keys = ["qcm"]
    elif k == "quiz":
        keys = ["true_false"] if item.get("answer_type") == "true_false" else ["short", "calculation"]
    elif k == "exercise":
        keys = ["calculation", "proof", "code"]
    else:
        return 0.8
    share = max(qt.get(x, 0.0) for x in keys)
    return 0.4 + 0.6 * min(1.0, share / max(qt.values()))


def likeness(item: dict[str, Any], prof: CourseProfile, *, target_difficulty: float | None = None) -> tuple[float, dict[str, float]]:
    text = item_text(item)
    target = target_difficulty if target_difficulty is not None else float(prof.fingerprint.get("difficulty_elo", 1100))
    comp = {"vocabulary": _vocab(text, prof), "notation": _notation(text, prof)}
    if item.get("kind") in ("qcm", "quiz", "exercise"):
        comp |= {"style": _style(item, text, prof), "difficulty": _difficulty(item, target), "format": _format(item, prof)}
        w = WEIGHTS
    else:  # summaries, cards, lessons: wording and notation carry the likeness
        comp |= {"style": 0.8}
        w = {"vocabulary": 0.6, "notation": 0.25, "style": 0.15}
    score = sum(comp[k] * w[k] for k in w) / sum(w.values())
    return round(score, 3), {k: round(v, 3) for k, v in comp.items()}


def decision(score: float, show: float = 0.70, regen: float = 0.50) -> str:
    return "show" if score >= show else "regenerate" if score >= regen else "drop"


def weak_components(detail: dict[str, float], below: float = 0.6) -> list[str]:
    return [k for k, v in detail.items() if v < below]
