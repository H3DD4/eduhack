"""Explain-back assessment (override §3.3, blueprint rubric).

``validate_explanation_output`` is applied to EVERY provider's output (demo, Anthropic, Gemini):
- a judgment about something the student said must carry a verbatim quote from the confirmed text;
  quotes that are not exact substrings are dropped, and a positive judgment left without a valid
  quote becomes *unscored*;
- missing ideas carry no quote: they cite the rubric criterion + course source and say "not demonstrated";
- quotes touching an unresolved unclear span make the criterion unscored;
- N/A criteria are excluded; no total is produced while any applicable criterion is unscored.
"""

from __future__ import annotations

import re
from typing import Any

from thinkfirst.modules.assessment.rubrics import CRITERIA
from thinkfirst.modules.llm_gateway.service import register_demo

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text: str, prefix: str = "s") -> list[dict]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text or "") if p and p.strip()]
    return [{"id": f"{prefix}{i}", "text": p} for i, p in enumerate(parts, start=1)]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


@register_demo("assess_explanation")
def demo_assess(variables: dict[str, Any]) -> dict[str, Any]:
    """Labeled demo assessor: regex matching of predeclared essentials. Quotes whole matching sentences."""
    sentences = variables["student_sentences"]
    rubric = variables["rubric"]
    out = []
    for crit in rubric["criteria"]:
        name = crit["criterion"]
        if not crit.get("applicable", True):
            out.append({"criterion": name, "status": "na", "quotes": [], "covered_essentials": [],
                        "missing_essentials": [], "rationale": "Not applicable to this task."})
            continue
        essentials = crit.get("essentials", [])
        if not essentials:
            out.append({"criterion": name, "status": "unscored", "quotes": [], "covered_essentials": [],
                        "missing_essentials": [], "rationale": "No predeclared essentials for this criterion yet."})
            continue
        contra = None
        for pat in crit.get("contradictions", []):
            contra = next((s for s in sentences if re.search(pat, s["text"], re.I)), None)
            if contra:
                break
        if contra:
            out.append({"criterion": name, "status": "absent", "quotes": [{"sentence_id": contra["id"], "text": contra["text"]}],
                        "covered_essentials": [], "missing_essentials": [e["id"] for e in essentials],
                        "rationale": "This statement contradicts the rule."})
            continue
        covered, quotes = [], []
        for ess in essentials:
            hit = next((s for s in sentences for p in ess.get("patterns", []) if re.search(p, s["text"], re.I)), None)
            if hit:
                covered.append(ess["id"])
                if all(q["sentence_id"] != hit["id"] for q in quotes):
                    quotes.append({"sentence_id": hit["id"], "text": hit["text"]})
        missing = [e["id"] for e in essentials if e["id"] not in covered]
        status = "demonstrated" if not missing else ("partial" if covered else "absent")
        out.append({"criterion": name, "status": status, "quotes": quotes, "covered_essentials": covered,
                    "missing_essentials": missing, "rationale": "Matched predeclared essentials (demo heuristic)."})
    return {"criteria": out, "sufficiency": "limited",
            "reason": "Simulated assessment: pattern matching against predeclared essentials, not calibrated."}


def validate_explanation_output(output: dict | None, sentences: list[dict], rubric: dict,
                                unresolved_spans: list[dict] | None = None,
                                only_criteria: set[str] | None = None) -> dict:
    """Normalize any provider output into safe criterion results. ``None`` output => all unscored."""
    by_id = {s["id"]: s["text"] for s in sentences}
    unresolved = [_norm(u.get("text", "")) for u in (unresolved_spans or []) if u.get("text")]
    model_items = {i.get("criterion"): i for i in (output or {}).get("criteria", []) if isinstance(i, dict)}
    rub = {c["criterion"]: c for c in rubric["criteria"]}
    citation = rubric.get("source_citation")
    results = []
    for name in CRITERIA:
        rc = rub.get(name, {"criterion": name, "applicable": False, "essentials": []})
        applicable = rc.get("applicable", True) and (only_criteria is None or name in only_criteria)
        if not applicable:
            results.append({"criterion": name, "status": "na", "score": None, "quotes": [], "missing": [],
                            "covered_essentials": [], "rationale": "Not applicable."})
            continue
        item = model_items.get(name)
        if output is None or item is None:
            results.append(_unscored(name, "There is not enough reliable information to score this yet."))
            continue
        status = item.get("status")
        if status not in ("absent", "partial", "demonstrated", "unscored", "na"):
            results.append(_unscored(name, "The assessment output was not usable."))
            continue
        if status == "na":
            status = "unscored"  # applicability is predeclared by the rubric, not decided by the model
        valid_quotes = []
        for q in item.get("quotes") or []:
            sid, text = q.get("sentence_id"), (q.get("text") or "").strip()
            if sid in by_id and text and _norm(text) in _norm(by_id[sid]):
                valid_quotes.append({"sentence_id": sid, "text": text, "supplement": sid.startswith("sup")})
        if status in ("demonstrated", "partial") and not valid_quotes:
            results.append(_unscored(name, "This judgment could not be linked to your confirmed words, so it is unscored."))
            continue
        if any(u and u in _norm(q["text"]) for q in valid_quotes for u in unresolved):
            results.append(_unscored(name, "This depends on a word you marked as unclear, so it is unscored."))
            continue
        ess = {e["id"]: e for e in rc.get("essentials", [])}
        missing = [{"essential_id": mid, "description": ess[mid]["description"], "status": "not demonstrated",
                    "criterion": name, "source": citation}
                   for mid in item.get("missing_essentials") or [] if mid in ess]
        if status == "absent" and not missing and not valid_quotes and ess:
            missing = [{"essential_id": e["id"], "description": e["description"], "status": "not demonstrated",
                        "criterion": name, "source": citation} for e in ess.values()]
        if name == "essential_coverage" and not ess and status != "unscored":
            results.append(_unscored(name, "No predeclared essential ideas exist for this concept yet."))
            continue
        results.append({"criterion": name, "status": status,
                        "score": {"absent": 0, "partial": 1, "demonstrated": 2}.get(status),
                        "quotes": valid_quotes if status != "unscored" else [], "missing": missing,
                        "covered_essentials": [c for c in item.get("covered_essentials") or [] if c in ess],
                        "rationale": str(item.get("rationale", ""))[:500]})
    applicable = [r for r in results if r["status"] != "na"]
    any_unscored = any(r["status"] == "unscored" for r in applicable)
    total = None if any_unscored or not applicable else sum(r["score"] for r in applicable)
    if not applicable or all(r["status"] == "unscored" for r in applicable):
        outcome = "unscored"
    elif all(r["status"] == "demonstrated" for r in applicable):
        outcome = "demonstrated"
    elif all(r["status"] in ("absent", "unscored") for r in applicable):
        outcome = "not_demonstrated"
    else:
        outcome = "partial"
    sufficiency = "limited" if any_unscored else (output or {}).get("sufficiency", "limited")
    if sufficiency not in ("sufficient", "limited", "needs-verification"):
        sufficiency = "limited"
    return {"criteria": results, "total": total, "outcome": outcome, "sufficiency": sufficiency,
            "reason": str((output or {}).get("reason", ""))[:500]}


def _unscored(name: str, why: str) -> dict:
    return {"criterion": name, "status": "unscored", "score": None, "quotes": [], "missing": [],
            "covered_essentials": [], "rationale": why}


def choose_followup(criteria: list[dict], bank: dict) -> dict:
    """One targeted follow-up: weakest applicable criterion, priority limits > why > example > coverage > correctness."""
    order = ["limits", "why_relationships", "example_application", "essential_coverage", "correctness"]
    rank = {"absent": 0, "unscored": 1, "partial": 2, "demonstrated": 3}
    status = {c["criterion"]: c["status"] for c in criteria}
    candidates = [c for c in order if c in bank and status.get(c, "na") != "na"]
    if not candidates:
        candidates = [c for c in order if c in bank]
    if not candidates:
        return {"id": "fu-default", "question": "Explain one situation where this idea would not apply.",
                "targets_criterion": "limits"}
    best = min(candidates, key=lambda c: (rank.get(status.get(c, "unscored"), 1), order.index(c)))
    return {**bank[best], "targets_criterion": best}
