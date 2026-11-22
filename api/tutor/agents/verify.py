"""Verifier and critic. Nothing reaches the student until it passes: structure, citations that exist and
support the text, a consistent answer key (SymPy where possible), no duplicates, and an LLM critic pass when
a real model is configured."""

from __future__ import annotations

from typing import Any

from ..mathcheck import expressions_equal, parse_number, parses
from ..similarity import item_text
from ..textutil import norm, overlap_ratio, tokens
from .base import Ctx


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def check_citations(item: dict[str, Any], chunks: dict[str, dict[str, Any]], *, required: bool = True) -> list[str]:
    problems = []
    cits = item.get("citations") or []
    valid = []
    for c in cits:
        ch = chunks.get(c.get("chunk_id"))
        if ch is None:
            problems.append(f"citation to unknown chunk {c.get('chunk_id')}")
            continue
        q = c.get("quote") or ""
        if q and overlap_ratio(q, ch["text"]) < 0.5:
            problems.append("citation quote not found in the cited chunk")
            continue
        c["page"] = ch.get("page")
        c["origin"] = ch.get("origin", "course")
        valid.append(c)
    item["citations"] = valid
    if required and not valid:
        problems.append("no valid citation")
    return problems


def check_answer_key(item: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    problems, flags = [], {}
    k = item.get("kind")
    if k == "qcm":
        opts = item.get("options", [])
        n_ok = sum(1 for o in opts if o.get("correct"))
        if len(opts) < 3:
            problems.append("fewer than 3 options")
        if n_ok == 0 or (n_ok > 1 and not item.get("multiple")):
            problems.append(f"{n_ok} correct options")
        texts = [norm(o.get("text", "")) for o in opts]
        if len(set(texts)) != len(texts) or any(not t for t in texts):
            problems.append("duplicate or empty options")
    elif k == "quiz":
        a, t = str(item.get("answer", "")).strip(), item.get("answer_type")
        if not a:
            problems.append("empty answer")
        if t == "number" and parse_number(a) is None:
            problems.append("answer is not a number")
        if t == "expression":
            ok = parses(a)
            flags["math_checked"] = ok is not None
            if ok is False:
                problems.append("answer expression does not parse")
        if t == "true_false" and norm(a) not in ("true", "false", "vrai", "faux"):
            problems.append("true/false answer expected")
    elif k == "exercise":
        if not item.get("parts"):
            problems.append("exercise without parts")
        for p in item.get("parts", []):
            if not p.get("prompt"):
                problems.append("part without prompt")
            if p.get("check") and p.get("answer_type") in ("expression", "number"):
                eq = expressions_equal(p["check"], p.get("answer") or p["check"])
                if eq is None:
                    flags["math_checked"] = False
                elif eq is False:
                    problems.append(f"part {p.get('label')}: answer and check disagree")
                else:
                    flags["math_checked"] = True
    return problems, flags


def verify_item(ctx: Ctx, track_id: str, item: dict[str, Any], *, chunks: dict[str, dict[str, Any]],
                existing_texts: list[str], citations_required: bool = True) -> dict[str, Any]:
    problems = check_citations(item, chunks, required=citations_required)
    p2, flags = check_answer_key(item)
    problems += p2
    txt = item_text(item)
    if any(_jaccard(txt, e) >= 0.85 for e in existing_texts):
        problems.append("duplicate of an existing item")
    if not problems and not ctx.llm.simulated and item.get("kind") in ("qcm", "quiz", "exercise"):
        ctx_chunks = [{"id": c["chunk_id"], "text": chunks[c["chunk_id"]]["text"]} for c in item.get("citations", [])
                      if c["chunk_id"] in chunks]
        try:
            crit = ctx.llm_json("critic", {"item": item, "context": ctx_chunks}, track_id)
            if not crit.get("ok", True):
                problems += [f"critic: {p}" for p in crit.get("problems", [])][:3] or ["critic rejected"]
                if crit.get("fixed_answer") and item.get("kind") == "quiz":
                    flags["critic_fix"] = crit["fixed_answer"]
            flags["critic"] = True
        except Exception:  # noqa: BLE001 - critic is an extra check, not a single point of failure
            flags["critic"] = False
    return {"ok": not problems, "problems": problems, **flags}
