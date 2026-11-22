"""Group 4 · Teach: grader, help ladder with policy gate, grounded Q&A.

Help ladder: 0 attempt first · 1 guiding question · 2 hint to the course section · 3 worked similar example ·
4 full solution. Level 2+ needs an attempt; level 4 needs two attempts. No help at all in a mock exam.
"""

from __future__ import annotations

import re
from typing import Any

from ..learner import new_record, update_concept
from ..mathcheck import expressions_equal, numbers_equal
from ..schemas import new_id, now_iso
from ..textutil import norm
from .base import Ctx

TRUE = {"true", "vrai", "v", "t", "1", "yes", "oui"}
FALSE = {"false", "faux", "f", "0", "no", "non"}


class PolicyBlocked(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _grade_simple(answer_type: str, expected: str, given: Any, *, accept: list[str] | None = None,
                  tolerance: float = 0.0) -> bool | None:
    g = str(given if given is not None else "").strip()
    if not g:
        return False
    if answer_type == "true_false":
        e = norm(str(expected))
        gv = norm(g)
        if gv not in TRUE | FALSE:
            return False
        return (gv in TRUE) == (e in TRUE)
    if answer_type == "number":
        r = numbers_equal(g, str(expected), tolerance)
        if r is not None:
            return r
    if answer_type in ("expression", "number"):
        r = expressions_equal(g, str(expected))
        if r is not None:
            return r
        return re.sub(r"\s+", "", norm(g)) == re.sub(r"\s+", "", norm(str(expected)))
    cands = [str(expected)] + list(accept or [])
    if any(re.sub(r"\W+", " ", norm(g)).strip() == re.sub(r"\W+", " ", norm(c)).strip() for c in cands):
        return True
    return None  # free text: needs the LLM grader


def grade(ctx: Ctx, track_id: str, item: dict[str, Any], answer: Any) -> dict[str, Any]:
    t = ctx.track(track_id)
    k = item.get("kind")
    tags: list[str] = []
    if k == "qcm":
        picked = set(answer if isinstance(answer, list) else [answer])
        picked = {int(x) for x in picked if str(x).lstrip("-").isdigit()}
        right = {i for i, o in enumerate(item["options"]) if o["correct"]}
        correct = picked == right
        score = 1.0 if correct else (len(picked & right) / len(right) * 0.5 if item.get("multiple") else 0.0)
        for i in picked - right:
            if 0 <= i < len(item["options"]) and item["options"][i].get("why"):
                tags.append(item["options"][i]["why"][:60])
        fb = item.get("explanation", "") if correct else (item["options"][min(picked - right)]["why"]
                                                          if picked - right else "")
        return {"correct": correct, "score": round(score, 2), "feedback": fb, "error_tags": tags}
    if k == "quiz":
        r = _grade_simple(item["answer_type"], item["answer"], answer, accept=item.get("accept"),
                          tolerance=item.get("tolerance", 0.0))
        if r is None:
            g = ctx.llm_json("grade_open", {"question": item["question"], "expected": item["answer"],
                                            "answer": str(answer), "solution": item.get("explanation", ""),
                                            "language": t["language"], "concept_title": item.get("concept_key", "")},
                             track_id, tier="small")
            return {"correct": bool(g.get("correct")), "score": float(g.get("score", 0)), "feedback": g.get("feedback", ""),
                    "error_tags": g.get("error_tags", [])}
        return {"correct": r, "score": 1.0 if r else 0.0, "feedback": item.get("explanation", "") if r else "",
                "error_tags": [] if r else ["wrong-answer"]}
    if k == "exercise":
        answers = answer if isinstance(answer, dict) else {}
        total = sum(p.get("points", 1) for p in item["parts"]) or 1
        got, feedback = 0.0, []
        for p in item["parts"]:
            a = answers.get(p["label"], "")
            exp = p.get("check") or p.get("answer", "")
            r = _grade_simple(p.get("answer_type", "text"), exp, a, tolerance=p.get("tolerance", 0.0))
            if r is None:
                g = ctx.llm_json("grade_open", {"question": p["prompt"], "expected": p.get("answer", ""), "answer": str(a),
                                                "solution": " ".join(p.get("solution_steps", [])),
                                                "language": t["language"]}, track_id, tier="small")
                s = float(g.get("score", 0))
                tags += g.get("error_tags", [])
                feedback.append(f"{p['label']} {g.get('feedback', '')}")
            else:
                s = 1.0 if r else 0.0
                if not r:
                    tags.append(f"part-{p['label']}")
            got += s * p.get("points", 1)
        score = got / total
        return {"correct": score >= 0.7, "score": round(score, 2), "feedback": "\n".join(feedback), "error_tags": tags,
                "part_scores": None}
    raise ValueError(f"cannot grade {k}")


def record_attempt(ctx: Ctx, track_id: str, artifact: dict[str, Any] | None, item: dict[str, Any], answer: Any, *,
                   context: str, ms: int | None, help_level: int) -> dict[str, Any]:
    t = ctx.track(track_id)
    g = grade(ctx, track_id, item, answer)
    ck = item.get("concept_key") or (item.get("concept_keys") or [""])[0]
    att = {"id": new_id(), "track_id": track_id, "owner_id": t["owner_id"], "artifact_id": artifact["id"] if artifact else None,
           "item_id": item["id"], "concept_key": ck, "context": context, "answer": answer, "correct": g["correct"],
           "score": g["score"], "ms": ms, "help_level": help_level, "rapid_guess": bool(ms is not None and ms < 2000),
           "error_tags": g["error_tags"], "feedback": g["feedback"], "created_at": now_iso()}
    ctx.store.put("attempts", att)
    if ck and not att["rapid_guess"]:
        rec = ctx.store.get("learner", f"{track_id}:{ck}") or new_record(track_id, t["owner_id"], ck, 1100.0)
        guess = 1 / len(item["options"]) if item.get("kind") == "qcm" else 0.05
        rec, new_diff = update_concept(rec, score=g["score"], item_difficulty=item.get("difficulty", 1100),
                                       help_level=help_level, guess=guess)
        ctx.store.put("learner", rec)
        att["mastery"] = {"concept_key": ck, "p_mastery": rec["p_mastery"], "elo": rec["elo"],
                          "mastered": rec["p_mastery"] >= ctx.settings.mastery_threshold, "next_review": rec["next_review"]}
        ctx.event("answer.graded", {"track_id": track_id, "concept_key": ck, "score": g["score"], "help_level": help_level})
    reveal = context != "mock"
    out = {**att, "solution": _solution(item) if reveal and (g["correct"] or help_level >= 4) else None}
    return out


def _solution(item: dict[str, Any]) -> dict[str, Any]:
    k = item.get("kind")
    if k == "qcm":
        return {"correct": [i for i, o in enumerate(item["options"]) if o["correct"]], "explanation": item.get("explanation", ""),
                "why": [o.get("why", "") for o in item["options"]], "citations": item.get("citations", [])}
    if k == "quiz":
        return {"answer": item["answer"], "explanation": item.get("explanation", ""), "citations": item.get("citations", [])}
    if k == "exercise":
        return {"parts": [{"label": p["label"], "answer": p.get("answer"), "steps": p.get("solution_steps", [])}
                          for p in item["parts"]], "citations": item.get("citations", [])}
    return {}


def help_for(ctx: Ctx, track_id: str, item: dict[str, Any], level: int, *, context: str) -> dict[str, Any]:
    t = ctx.track(track_id)
    fr = t["language"] == "fr"
    if context == "mock":
        raise PolicyBlocked("MOCK_EXAM_NO_HELP", "Pas d'aide pendant l'examen blanc." if fr else "No help during a mock exam.")
    tries = [a for a in ctx.store.list("attempts", track_id=track_id) if a["item_id"] == item["id"]]
    if level >= 2 and not tries:
        raise PolicyBlocked("ATTEMPT_FIRST", "Essayez d'abord une réponse, même partielle." if fr
                            else "Try an answer first, even a partial one.")
    if level >= 4 and len(tries) < 2 and not any(a["correct"] for a in tries):
        raise PolicyBlocked("TRY_AGAIN_FIRST", "Encore un essai avant la solution complète." if fr
                            else "One more try before the full solution.")
    ck = item.get("concept_key") or (item.get("concept_keys") or [""])[0]
    cmap = ctx.concept_map(track_id)
    c = cmap.get(ck, {"title": ck, "keywords": []})
    context_chunks = ctx.kb.context(track_id, " ".join([c["title"]] + c.get("keywords", [])), k=4, concept_key=ck)
    out = ctx.llm_json("tutor_help", {"item": item, "level": level, "context": context_chunks, "language": t["language"],
                                      "attempts": [a.get("answer") for a in tries][-2:]}, track_id)
    return {"level": level, "message": out["message"], "citations": out.get("citations", []),
            "autonomy_cost": {0: 0, 1: 0, 2: 0.25, 3: 0.5, 4: 1.0}[level]}


def ask(ctx: Ctx, track_id: str, question: str, *, mode: str = "study", active_item: dict[str, Any] | None = None) -> dict[str, Any]:
    t = ctx.track(track_id)
    if mode == "mock":
        raise PolicyBlocked("MOCK_EXAM_NO_HELP", "No help during a mock exam.")
    context_chunks = ctx.kb.context(track_id, question, k=6)
    out = ctx.llm_json("answer_question", {"question": question, "context": context_chunks, "mode": mode,
                                           "active_item": bool(active_item), "language": t["language"]}, track_id)
    valid = {c["id"]: c for c in context_chunks}
    cits = []
    for c in out.get("citations", []):
        ch = valid.get(c.get("chunk_id"))
        if ch:
            cits.append({**c, "source": ch["source"], "page": ch["page"], "origin": ch["origin"], "url": ch["url"]})
    return {"answer": out["answer"], "citations": cits, "grounded": bool(out.get("grounded", bool(cits))),
            "simulated": ctx.llm.simulated}
