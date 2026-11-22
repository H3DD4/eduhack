"""Group 3 · Create: résumés, fiches, quizzes, QCM, exercises, mock exams and tutorial pages.

Every generator follows the same loop:
  retrieve course context -> LLM draft -> schema validation -> verifier -> likeness score
  -> show (>= 0.70) | regenerate once with the weak components named (0.50-0.70) | drop (< 0.50)
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from pydantic import ValidationError

from ..fingerprint import style_summary
from ..schemas import ITEM_MODELS, LessonPage, MockExam, Resume, new_id, now_iso
from ..similarity import decision, item_text, likeness, weak_components
from ..textutil import slugify
from .base import Ctx
from .verify import check_citations, verify_item

log = logging.getLogger("tutor.create")

FACT_TYPES = {"course", "slides", "notes", "other", "web", "solutions"}
TASK_FOR = {"qcm": ("generate_qcm", "items"), "quiz": ("generate_quiz", "items"),
            "fiche": ("generate_fiches", "fiches"), "exercise": ("generate_exercises", "exercises")}


def concept_payload(c: dict[str, Any]) -> dict[str, Any]:
    return {"key": c["key"], "title": c["title"], "chapter": c.get("chapter", ""), "keywords": c.get("keywords", []),
            "summary": c.get("summary", "")}


def gather_context(ctx: Ctx, track_id: str, concepts: list[dict[str, Any]], *, per_concept: int = 4,
                   limit: int = 14) -> list[dict[str, Any]]:
    seen, out = set(), []
    for c in concepts:
        q = " ".join([c["title"]] + c.get("keywords", [])[:5])
        origin = None if c.get("coverage", 1) < 0.34 else "course"   # web only where the course is thin
        # facts come from teaching material; exams and exercise sheets only shape the style (STYLE)
        hits = ctx.kb.context(track_id, q, k=per_concept, concept_key=c["key"], origin=origin, doc_types=FACT_TYPES)
        if not hits:
            hits = ctx.kb.context(track_id, q, k=per_concept, concept_key=c["key"], origin=origin)
        for ch in hits:
            if ch["id"] not in seen:
                seen.add(ch["id"])
                out.append(ch)
    return out[:limit]


def known_errors(ctx: Ctx, track_id: str, keys: list[str]) -> list[str]:
    tags = Counter()
    for a in ctx.store.list("attempts", track_id=track_id):
        if a.get("concept_key") in keys and a.get("correct") is False:
            tags.update(a.get("error_tags") or [])
    return [t for t, _ in tags.most_common(6)]


def _level(track: dict[str, Any]) -> str:
    return track.get("measured_level") or track.get("declared_level") or "intermediate"


def _existing_texts(ctx: Ctx, track_id: str) -> list[str]:
    out = []
    for a in ctx.store.list("artifacts", track_id=track_id):
        for it in a.get("content", {}).get("items", []):
            out.append(item_text(it))
    return out


def generate_items(ctx: Ctx, track_id: str, kind: str, concepts: list[dict[str, Any]], *, count: int,
                   difficulty: float | None = None, extra: dict[str, Any] | None = None,
                   existing: list[str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    track = ctx.track(track_id)
    task, key = TASK_FOR[kind]
    model = ITEM_MODELS[kind]
    context = gather_context(ctx, track_id, concepts)
    chunks = {c["id"]: c for c in ctx.kb.chunks(track_id)}
    prof = ctx.profile(track_id)
    target = difficulty if difficulty is not None else float(ctx.fingerprint(track_id).get("difficulty_elo", 1100))
    valid_keys = {c["key"] for c in concepts}
    existing = list(existing if existing is not None else _existing_texts(ctx, track_id))
    variables = {"concepts": [concept_payload(c) for c in concepts], "context": context, "language": track["language"],
                 "level": _level(track), "style": style_summary(ctx.fingerprint(track_id)), "count": count,
                 "difficulty": round(target), "known_errors": known_errors(ctx, track_id, list(valid_keys)),
                 **(extra or {})}
    approved: list[dict[str, Any]] = []
    stats = {"drafted": 0, "approved": 0, "regenerated": 0, "dropped": 0, "problems": []}
    pending_feedback: list[str] = []
    for round_ in range(1 + ctx.settings.max_regenerations):
        need = count - len(approved)
        if need <= 0:
            break
        if round_ > 0:
            if not pending_feedback:
                break
            variables = {**variables, "count": need, "feedback": pending_feedback[:8]}
            stats["regenerated"] += need
        try:
            raw = ctx.llm_json(task, variables, track_id).get(key, [])
        except Exception as e:  # noqa: BLE001
            stats["problems"].append(f"llm:{getattr(e, 'code', type(e).__name__)}")
            break
        pending_feedback = []
        for r in raw:
            stats["drafted"] += 1
            r = {**r, "kind": kind}
            if kind == "exercise":
                r["concept_keys"] = [k for k in r.get("concept_keys", []) if k in valid_keys] or [concepts[0]["key"]]
            else:
                r["concept_key"] = r.get("concept_key") if r.get("concept_key") in valid_keys else concepts[0]["key"]
            try:
                item = model.model_validate(r).model_dump()
            except ValidationError as e:
                stats["dropped"] += 1
                pending_feedback.append(f"invalid item shape: {e.errors()[0]['msg']}")
                continue
            v = verify_item(ctx, track_id, item, chunks=chunks, existing_texts=existing)
            score, detail = likeness(item, prof, target_difficulty=target)
            item["likeness"], item["likeness_detail"], item["verification"] = score, detail, v
            verdict = "drop" if not v["ok"] else decision(score, ctx.settings.likeness_show, ctx.settings.likeness_regenerate)
            if verdict == "show":
                approved.append(item)
                existing.append(item_text(item))
            else:
                stats["dropped"] += 1
                if v["problems"]:
                    stats["problems"] += v["problems"][:2]
                    pending_feedback += v["problems"][:2]
                else:
                    pending_feedback.append("closer to the course on: " + ", ".join(weak_components(detail)))
            if len(approved) >= count:
                break
    stats["approved"] = len(approved)
    return approved, stats


def _artifact(track: dict[str, Any], type_: str, title: str, content: dict[str, Any], *, chapter: str = "",
              concept_keys: list[str] | None = None, likeness_: float | None = None, detail=None, verification=None,
              status: str = "approved") -> dict[str, Any]:
    return {"id": new_id(), "track_id": track["id"], "owner_id": track["owner_id"], "type": type_, "title": title,
            "chapter": chapter, "concept_keys": concept_keys or [], "content": content, "likeness": likeness_,
            "likeness_detail": detail or {}, "verification": verification or {}, "status": status, "regenerations": 0,
            "created_at": now_iso()}


def _mean_likeness(items: list[dict[str, Any]]) -> float | None:
    vals = [i["likeness"] for i in items if i.get("likeness") is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def build_item_artifact(ctx: Ctx, track_id: str, kind: str, title: str, concepts: list[dict[str, Any]], *,
                        count: int, chapter: str = "", difficulty: float | None = None, type_: str | None = None,
                        save: bool = True) -> dict[str, Any] | None:
    items, stats = generate_items(ctx, track_id, kind, concepts, count=count, difficulty=difficulty)
    if not items:
        return None
    a = _artifact(ctx.track(track_id), type_ or {"fiche": "fiches", "exercise": "exercises"}.get(kind, kind), title,
                  {"items": items}, chapter=chapter, concept_keys=[c["key"] for c in concepts],
                  likeness_=_mean_likeness(items), verification=stats)
    if save:
        ctx.store.put("artifacts", a)
    return a


def build_resume(ctx: Ctx, track_id: str, chapter: str, concepts: list[dict[str, Any]]) -> dict[str, Any] | None:
    track = ctx.track(track_id)
    context = gather_context(ctx, track_id, concepts, per_concept=3, limit=18)
    chunks = {c["id"]: c for c in ctx.kb.chunks(track_id)}
    raw = ctx.llm_json("generate_resume", {"chapter": chapter, "concepts": [concept_payload(c) for c in concepts],
                                            "context": context, "language": track["language"], "level": _level(track),
                                            "style": style_summary(ctx.fingerprint(track_id))}, track_id)
    try:
        res = Resume.model_validate({**raw, "chapter": chapter}).model_dump()
    except ValidationError:
        return None
    kept = []
    for s in res["sections"]:
        if not check_citations(s, chunks, required=True) and (s["bullets"] or s["formulas"]):
            kept.append(s)
    if not kept:
        return None
    res["sections"] = kept
    score, detail = likeness(res, ctx.profile(track_id))
    a = _artifact(track, "resume", f"Résumé — {chapter}" if track["language"] == "fr" else f"Summary — {chapter}", res,
                  chapter=chapter, concept_keys=[c["key"] for c in concepts], likeness_=score, detail=detail,
                  verification={"sections": len(kept)})
    ctx.store.put("artifacts", a)
    return a


def build_probe_bank(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    """Two QCM per key concept at three difficulty levels, used by the level check."""
    track_id = state["track_id"]
    concepts = sorted(ctx.concepts(track_id), key=lambda c: (-c["exam_weight"], c["ord"]))[:10]
    items: list[dict[str, Any]] = []
    existing: list[str] = []
    for i, c in enumerate(concepts):
        for d in (950.0, 1150.0, 1350.0)[: 2 if i >= 5 else 3]:
            got, _ = generate_items(ctx, track_id, "qcm", [c], count=1, difficulty=d, existing=existing)
            for it in got:
                it["difficulty"] = d
                existing.append(item_text(it))
            items += got
    track = ctx.track(track_id)
    old = [a for a in ctx.store.list("artifacts", track_id=track_id) if a["type"] == "probe"]
    for a in old:
        ctx.store.delete("artifacts", a["id"])
    a = _artifact(track, "probe", "Level check", {"items": items}, concept_keys=[c["key"] for c in concepts])
    ctx.store.put("artifacts", a)
    ctx.save_track(ctx.track(track_id), status="awaiting_level")
    ctx.event("items.ready", {"track_id": track_id, "probe_items": len(items)})
    return {"probe_items": len(items)}


# ------------------------------------------------------------------------------------------- Valley 1
def build_revision_pack(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    track_id = state["track_id"]
    track = ctx.track(track_id)
    ctx.save_track(track, status="building")
    concepts = ctx.concepts(track_id)
    scope = track.get("chapters") or []
    learner = ctx.learner(track_id)
    chapters: dict[str, list[dict[str, Any]]] = {}
    for c in concepts:
        if not scope or c["chapter"] in scope:
            chapters.setdefault(c["chapter"], []).append(c)

    def chapter_priority(cs):
        return -sum(c["exam_weight"] * (1 - learner.get(c["key"], {}).get("p_mastery", 0.2)) for c in cs)

    built = Counter()
    fr = track["language"] == "fr"
    for chapter, cs in sorted(chapters.items(), key=lambda kv: chapter_priority(kv[1])):
        weak = sorted(cs, key=lambda c: learner.get(c["key"], {}).get("p_mastery", 0.2))
        elo = sum(learner.get(c["key"], {}).get("elo", 1100) for c in cs) / len(cs)
        if build_resume(ctx, track_id, chapter, cs):
            built["resume"] += 1
        for kind, title, n in (("fiche", "Fiches" if fr else "Cards", min(16, 3 * len(cs))),
                               ("qcm", "QCM", min(10, 2 * len(cs) + 2)),
                               ("quiz", "Quiz", min(8, 2 * len(cs))),
                               ("exercise", "Exercices" if fr else "Exercises", min(4, max(2, len(cs) // 2)))):
            # practice sits at 70 % expected success: slightly below the student's rating
            diff = elo - 147 if kind in ("qcm", "quiz") else elo
            if build_item_artifact(ctx, track_id, kind, f"{title} — {chapter}", weak, count=n, chapter=chapter,
                                   difficulty=diff):
                built[kind] += 1
    ctx.event("plan.updated", {"track_id": track_id, "artifacts": dict(built)})
    return {"built": dict(built)}


def build_mock_exam(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    track_id = state["track_id"]
    track = ctx.track(track_id)
    fp = ctx.fingerprint(track_id)
    bp = fp.get("blueprint") or {}
    cmap = ctx.concept_map(track_id)
    fr = track["language"] == "fr"
    parts = []
    existing = _existing_texts(ctx, track_id)   # the mock exam must not repeat practice items
    for p in bp.get("parts", []):
        cs = [cmap[k] for k in p.get("concept_keys", []) if k in cmap] or list(cmap.values())[:3]
        qtypes = p.get("question_types") or ["calculation"]
        kind = "qcm" if "qcm" in qtypes else "quiz" if set(qtypes) <= {"true_false", "short"} else "exercise"
        n = max(1, min(4, p.get("count", 2))) if kind != "exercise" else 1
        items, _ = generate_items(ctx, track_id, kind, cs, count=n, existing=existing)
        if not items:  # every fresh draft duplicated practice: allow reuse rather than an empty part
            items, _ = generate_items(ctx, track_id, kind, cs, count=n, existing=[])
        if not items:
            continue
        pts = float(p.get("points") or 0) or 20.0 / max(1, len(bp.get("parts", [])))
        for it in items:
            it["points"] = round(pts / len(items), 2)
            existing.append(item_text(it))
        parts.append({"title": p.get("title", ""), "points": pts, "items": items})
    if not parts:
        return {"mock_exam": False}
    total = sum(p["points"] for p in parts)
    exam = MockExam.model_validate({
        "title": ("Examen blanc — " if fr else "Mock exam — ") + track["title"], "duration_min": bp.get("duration_min") or 120,
        "total_points": total, "instructions": ("Sans aide ni documents. Le chronomètre démarre à l'ouverture."
                                                if fr else "No help, no notes. The timer starts when you open it."),
        "parts": parts}).model_dump()
    a = _artifact(track, "mock_exam", exam["title"], exam, concept_keys=list(cmap),
                  likeness_=_mean_likeness([i for p in parts for i in p["items"]]),
                  verification={"blueprint_inferred": bp.get("inferred", False)})
    ctx.store.put("artifacts", a)
    return {"mock_exam": a["id"]}


# ------------------------------------------------------------------------------------------- Valley 2
def build_lesson(ctx: Ctx, track_id: str, node: dict[str, Any]) -> dict[str, Any] | None:
    track = ctx.track(track_id)
    cmap = ctx.concept_map(track_id)
    concepts = [cmap[k] for k in node.get("concept_keys", []) if k in cmap]
    if not concepts:
        return None
    nodes = sorted(ctx.store.list("tutorial", track_id=track_id), key=lambda n: n["ord"])
    known = [n["title"] for n in nodes if n["ord"] < node["ord"] and n["kind"] == "page"][-6:]
    context = gather_context(ctx, track_id, concepts, per_concept=5, limit=14)
    chunks = {c["id"]: c for c in ctx.kb.chunks(track_id)}
    raw = ctx.llm_json("generate_lesson", {"page": {"title": node["title"], "concept_keys": node["concept_keys"]},
                                            "concepts": [concept_payload(c) for c in concepts], "context": context,
                                            "known": known, "language": track["language"], "level": _level(track),
                                            "style": style_summary(ctx.fingerprint(track_id))}, track_id)
    pages = [n for n in nodes if n["kind"] == "page"]
    i = next((k for k, n in enumerate(pages) if n["slug"] == node["slug"]), 0)
    try:
        lesson = LessonPage.model_validate({**raw, "slug": node["slug"], "title": raw.get("title") or node["title"],
                                            "chapter": node.get("chapter", ""), "concept_keys": node["concept_keys"],
                                            "level": _level(track),
                                            "prev_slug": pages[i - 1]["slug"] if i > 0 else None,
                                            "next_slug": pages[i + 1]["slug"] if i + 1 < len(pages) else None}).model_dump()
    except ValidationError:
        return None
    problems = []
    existing: list[str] = []
    for s in lesson["sections"]:
        if s["type"] in ("explain", "example"):
            problems += check_citations(s, chunks, required=False)
        if s["items"]:
            ok_items = []
            for it in s["items"]:
                it.setdefault("kind", "qcm" if "options" in it else "quiz")
                it.setdefault("concept_key", concepts[0]["key"])
                try:
                    it = ITEM_MODELS[it["kind"]].model_validate(it).model_dump()
                except (ValidationError, KeyError):
                    continue
                v = verify_item(ctx, track_id, it, chunks=chunks, existing_texts=existing, citations_required=False)
                if v["ok"]:
                    ok_items.append(it)
                    existing.append(item_text(it))
            s["items"] = ok_items
    if not any(s["type"] == "explain" and s.get("citations") for s in lesson["sections"]):
        problems.append("no grounded explanation")
    score, detail = likeness(lesson, ctx.profile(track_id))
    a = _artifact(track, "lesson", lesson["title"], lesson, chapter=node.get("chapter", ""),
                  concept_keys=node["concept_keys"], likeness_=score, detail=detail,
                  verification={"problems": problems}, status="approved" if score >= 0.5 else "draft")
    ctx.store.put("artifacts", a)
    node["artifact_id"] = a["id"]
    ctx.store.put("tutorial", node)
    return a


def build_chapter_quiz(ctx: Ctx, track_id: str, node: dict[str, Any]) -> dict[str, Any] | None:
    cmap = ctx.concept_map(track_id)
    concepts = [cmap[k] for k in node.get("concept_keys", []) if k in cmap]
    if not concepts:
        return None
    kind = "exercise" if node["kind"] == "project" else "qcm"
    a = build_item_artifact(ctx, track_id, kind, node["title"], concepts, count=1 if kind == "exercise" else 6,
                            chapter=node.get("chapter", ""), type_="exercises" if kind == "exercise" else "qcm")
    if a:
        if node["kind"] == "checkpoint":
            a["content"]["no_help"] = True
            ctx.store.put("artifacts", a)
        node["artifact_id"] = a["id"]
        ctx.store.put("tutorial", node)
    return a


def prefetch_lessons(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    """Write the first open pages up front; later pages are written when the student reaches them."""
    track_id = state["track_id"]
    nodes = sorted(ctx.store.list("tutorial", track_id=track_id), key=lambda n: n["ord"])
    done = 0
    for n in nodes:
        if n["kind"] == "page" and not n.get("artifact_id") and n["status"] in ("open", "skippable"):
            if build_lesson(ctx, track_id, n):
                done += 1
        if done >= 2:
            break
    ctx.save_track(ctx.track(track_id), status="ready")
    return {"lessons_prefetched": done}


def lesson_slug(title: str, used: set[str]) -> str:
    base = slugify(title, 50)
    s, i = base, 2
    while s in used:
        s, i = f"{base}-{i}", i + 1
    used.add(s)
    return s
