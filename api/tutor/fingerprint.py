"""Course fingerprint: what makes the student's course recognisable, measured from their own documents.

- vocabulary: top TF-IDF terms of the course
- notation: which variant the course uses for each notation family (f'(x) vs df/dx, ]a;b[ vs (a,b), 2,5 vs 2.5…)
- exercise style: imperative verbs, numbering, question length, sub-questions per exercise
- question types and, when a past exam is uploaded, the exam blueprint (parts, points, duration)

The likeness score (similarity.py) compares any generated item against this fingerprint.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .textutil import norm, tfidf_keywords

NOTATION: dict[str, dict[str, str]] = {
    "derivative": {"prime": r"\b[a-zA-Z]\s*['′]\s*\(", "leibniz": r"\bd[a-zA-Z]?\s*/\s*d[a-zA-Z]\b|\\frac\{d",
                   "dot": r"\\dot\{"},
    "vector": {"arrow": r"\\vec\{|\\overrightarrow|[a-zA-Z]\u20d7", "bold": r"\\mathbf\{[a-z]\}", "plain": r"\bvect(?:eur|or)\s+[a-z]\b"},
    "decimal": {"comma": r"\b\d+,\d+\b", "dot": r"\b\d+\.\d+\b"},
    "interval": {"french": r"[\]\[]\s*-?[\w∞]+\s*;\s*-?[\w∞+]+\s*[\]\[]", "anglo": r"[(\[]\s*-?[\w∞]+\s*,\s*-?[\w∞+]+\s*[)\]]"},
    "multiplication": {"times": r"×|\\times", "cdot": r"·|\\cdot", "star": r"\d\s*\*\s*\d"},
    "logarithm": {"ln": r"\bln\s*\(?", "log": r"\blog\s*\(?"},
    "reals": {"blackboard": r"ℝ|\\mathbb\{R\}", "letters": r"\bIR\b|\bR\b(?=\s*[:,)])"},
    "implication": {"arrow": r"⇒|\\Rightarrow|\\implies", "ascii": r"=>"},
    "code": {"python": r"\bdef \w+\(|\bprint\(|\bimport \w+", "javascript": r"\bfunction \w+\(|\bconst \w+ =|console\.log",
             "java": r"\bpublic static void\b|System\.out", "c": r"#include\s*<", "sql": r"\bSELECT\b.+\bFROM\b",
             "html": r"<(div|p|h1|body)\b"},
}

VERBS = {
    "fr": ["calculer", "déterminer", "montrer", "démontrer", "justifier", "résoudre", "étudier", "exprimer",
           "en déduire", "vérifier", "tracer", "représenter", "donner", "écrire", "expliquer", "compléter", "citer",
           "définir", "comparer", "simplifier", "factoriser", "développer", "dériver", "intégrer", "interpréter",
           "programmer", "coder", "proposer", "établir", "prouver", "conclure", "dresser", "encadrer"],
    "en": ["calculate", "compute", "determine", "show", "prove", "justify", "solve", "find", "express", "deduce",
           "verify", "sketch", "plot", "give", "write", "explain", "complete", "define", "compare", "simplify",
           "factor", "expand", "differentiate", "integrate", "interpret", "implement", "describe", "evaluate"],
}
NUMBERING = {"1)": r"(?m)^\s*\d+\)\s", "1.": r"(?m)^\s*\d+\.\s", "a)": r"(?m)^\s*[a-h]\)\s", "I-": r"(?m)^\s*[IVX]+\s*[-–.)]\s",
             "Q1": r"(?m)^\s*Q\s?\d+", "Exercice N": r"(?im)^\s*(exercice|exercise)\s+\d+"}
QTYPE_PATTERNS = {
    "qcm": r"\b(qcm|cochez|entourez|la bonne réponse|choose the correct|multiple choice|a\)\s.+\n\s*b\)\s)",
    "true_false": r"\b(vrai ou faux|true or false)\b",
    "proof": r"\b(montrer que|démontrer|prouver|show that|prove)\b",
    "calculation": r"\b(calculer|déterminer|résoudre|compute|calculate|solve|find)\b",
    "code": r"\b(écrire un programme|écrire une fonction|write a (program|function)|implement)\b",
    "short": r"\b(définir|citer|donner la définition|define|state|name)\b",
}


def notation_profile(text: str) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    counts: dict[str, dict[str, int]] = {}
    preferred: dict[str, str] = {}
    for fam, variants in NOTATION.items():
        c = {v: len(re.findall(rx, text)) for v, rx in variants.items()}
        c = {k: n for k, n in c.items() if n}
        if c:
            counts[fam] = c
            preferred[fam] = max(c, key=c.get)
    return counts, preferred


def verb_profile(text: str, lang: str) -> dict[str, int]:
    vs = VERBS.get(lang, VERBS["en"])
    t = norm(text)
    out = Counter()
    for v in vs:
        nv = norm(v)
        n = len(re.findall(rf"(?:^|[\n.;:)\-–]\s*|\d[).]\s*)({re.escape(nv)})\b", t))
        if n:
            out[v] = n
    return dict(out.most_common(12))


def question_blocks(text: str) -> list[str]:
    """Split exercise text into question lines (numbered or imperative)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    qs = []
    for ln in lines:
        if re.match(r"^(\d+[).]|[a-h]\)|Q\s?\d+|[IVX]+\s*[-–.)])\s*\S", ln) or ln.endswith("?"):
            qs.append(ln)
    return qs


def build_fingerprint(track_id: str, owner_id: str, docs: list[dict[str, Any]], texts: dict[str, str],
                      language: str) -> dict[str, Any]:
    """docs: document records; texts: document_id -> full text."""
    all_text = "\n\n".join(texts.values())
    ex_ids = [d["id"] for d in docs if d.get("doc_type") in ("exercises", "past_exam", "solutions")]
    ex_text = "\n\n".join(texts[i] for i in ex_ids if i in texts) or all_text
    vocab = tfidf_keywords(list(texts.values()) or [all_text], top=60)
    counts, preferred = notation_profile(all_text)
    verbs = verb_profile(ex_text, language)
    numbering = max(NUMBERING, key=lambda k: len(re.findall(NUMBERING[k], ex_text))) if ex_text else ""
    if numbering and not re.search(NUMBERING[numbering], ex_text):
        numbering = ""
    qs = question_blocks(ex_text)
    qwords = [len(q.split()) for q in qs] or [14]
    blocks = re.split(r"(?im)^\s*(?:exercice|exercise|problème|problem)\s*\d*", ex_text)
    subq = [len(question_blocks(b)) for b in blocks if b.strip()] or [1]
    nums = [len(re.findall(r"\d+(?:[.,]\d+)?", q)) for q in qs] or [0]
    qt = Counter()
    for k, rx in QTYPE_PATTERNS.items():
        qt[k] = len(re.findall(rx, ex_text, re.I))
    total = sum(qt.values()) or 1
    qtypes = {k: round(v / total, 3) for k, v in qt.items() if v}
    avg_sub = sum(subq) / len(subq)
    difficulty = 1100 + 35 * (min(avg_sub, 8) - 3) + 8 * (min(sum(nums) / len(nums), 6) - 2)
    samples = []
    for b in blocks:
        b = b.strip()
        if 80 < len(b) < 1500 and question_blocks(b):
            samples.append(b[:700])
        if len(samples) >= 3:
            break
    return {
        "track_id": track_id, "owner_id": owner_id, "id": track_id, "language": language,
        "vocabulary": vocab, "notation": counts, "preferred_notation": preferred, "verbs": verbs,
        "numbering": numbering, "question_types": qtypes, "avg_question_words": round(sum(qwords) / len(qwords), 1),
        "avg_subquestions": round(avg_sub, 2), "numbers_per_question": round(sum(nums) / len(nums), 2),
        "difficulty_elo": round(max(800, min(1500, difficulty))), "blueprint": None, "sample_exercises": samples,
    }


def style_summary(fp: dict[str, Any]) -> dict[str, Any]:
    """Compact version passed to generation prompts."""
    if not fp:
        return {}
    return {"language": fp.get("language"), "vocabulary": [t for t, _ in fp.get("vocabulary", [])[:40]],
            "notation": fp.get("preferred_notation", {}), "verbs": fp.get("verbs", {}),
            "numbering": fp.get("numbering"), "question_types": fp.get("question_types", {}),
            "avg_question_words": fp.get("avg_question_words"), "avg_subquestions": fp.get("avg_subquestions"),
            "sample_exercises": fp.get("sample_exercises", [])[:2]}
