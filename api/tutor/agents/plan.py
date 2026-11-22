"""Planner (Valley 1) and Tutorial architect (Valley 2)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..schemas import new_id
from .base import Ctx
from .create import lesson_slug


def topo_order(concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kahn's algorithm, stable on the course order; cycles fall back to course order."""
    by = {c["key"]: c for c in concepts}
    indeg = {k: 0 for k in by}
    for c in concepts:
        for p in c.get("prerequisites", []):
            if p in by:
                indeg[c["key"]] += 1
    ready = sorted([k for k, d in indeg.items() if d == 0], key=lambda k: by[k]["ord"])
    out, seen = [], set()
    while ready:
        k = ready.pop(0)
        out.append(by[k])
        seen.add(k)
        for c in concepts:
            if k in c.get("prerequisites", []) and c["key"] not in seen:
                indeg[c["key"]] -= 1
                if indeg[c["key"]] == 0:
                    ready.append(c["key"])
                    ready.sort(key=lambda x: by[x]["ord"])
    out += [c for c in sorted(concepts, key=lambda c: c["ord"]) if c["key"] not in seen]
    return out


# ------------------------------------------------------------------------------------------- Valley 1
def plan_revision(ctx: Ctx, state: dict[str, Any], *, today: date | None = None, minutes_per_day: int = 50) -> dict[str, Any]:
    track_id = state["track_id"]
    t = ctx.track(track_id)
    today = today or datetime.now(UTC).date()
    exam = date.fromisoformat(t["exam_date"]) if t.get("exam_date") else today + timedelta(days=14)
    days_left = max(1, (exam - today).days)
    learner = ctx.learner(track_id)
    scope = t.get("chapters") or []
    all_concepts = ctx.concepts(track_id)
    scope_norm = [s.strip().lower() for s in scope if s.strip()]
    concepts = [
        c for c in all_concepts
        if not scope_norm or any(s in (c["chapter"] or "").lower() or (c["chapter"] or "").lower() in s for s in scope_norm)
    ] or all_concepts
    urgency = 1 + 3 / days_left
    pri = []
    for c in concepts:
        m = learner.get(c["key"], {}).get("p_mastery", 0.2)
        pri.append((round(c["exam_weight"] * (1 - m) * urgency, 4), c, m))
    pri.sort(key=lambda x: -x[0])
    slots_per_day = max(1, minutes_per_day // 25)
    calendar: dict[date, list[dict[str, Any]]] = {}
    study_days = [today + timedelta(days=i) for i in range(max(1, days_left - 1))]

    def place(day: date, entry: dict[str, Any]) -> bool:
        if day >= exam or len(calendar.setdefault(day, [])) >= slots_per_day:
            return False
        calendar[day].append(entry)
        return True

    di = 0
    for p, c, m in pri:
        if m >= ctx.settings.mastery_threshold:
            continue
        activity = "learn" if m < 0.4 else "practice"
        while di < len(study_days) and not place(study_days[di], {"concept_key": c["key"], "title": c["title"],
                                                                  "activity": activity, "priority": p}):
            di += 1
        for gap in (1, 3, 7):  # spaced reviews before the exam
            d = study_days[min(di, len(study_days) - 1)] + timedelta(days=gap)
            while d < exam - timedelta(days=1) and not place(d, {"concept_key": c["key"], "title": c["title"],
                                                                 "activity": "review", "priority": p / 2}):
                d += timedelta(days=1)
    mock_day = exam - timedelta(days=2 if days_left > 3 else 1)
    calendar.setdefault(max(today, mock_day), []).append({"concept_key": "*", "title": "Mock exam",
                                                          "activity": "mock_exam", "priority": 1.0})
    entries = [{"date": d.isoformat(), "minutes": 60 if e["activity"] == "mock_exam" else 25, **e}
               for d in sorted(calendar) for e in calendar[d]]
    ctx.store.put("plans", {"id": track_id, "track_id": track_id, "owner_id": t["owner_id"], "exam_date": exam.isoformat(),
                            "days_left": days_left, "entries": entries,
                            "priorities": [{"concept_key": c["key"], "title": c["title"], "priority": p,
                                            "p_mastery": m, "exam_weight": c["exam_weight"]} for p, c, m in pri]})
    ctx.event("plan.updated", {"track_id": track_id, "entries": len(entries)})
    return {"plan_entries": len(entries), "days_left": days_left}


# ------------------------------------------------------------------------------------------- Valley 2
def architect_tutorial(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    track_id = state["track_id"]
    t = ctx.track(track_id)
    ctx.save_track(t, status="building")
    learner = ctx.learner(track_id)
    concepts = topo_order(ctx.concepts(track_id))
    fr = t["language"] == "fr"
    for n in ctx.store.list("tutorial", track_id=track_id):
        ctx.store.delete("tutorial", n["id"])
    chapters: list[str] = []
    for c in concepts:
        if c["chapter"] not in chapters:
            chapters.append(c["chapter"])
    nodes, used, ord_ = [], set(), 0
    first_open = False

    def node(**kw) -> dict[str, Any]:
        nonlocal ord_
        ord_ += 1
        n = {"id": new_id(), "track_id": track_id, "owner_id": t["owner_id"], "ord": ord_, "artifact_id": None,
             "status": "locked", "parent_slug": None, "concept_keys": [], "chapter": "", **kw}
        nodes.append(n)
        return n

    for ch in chapters:
        cs = [c for c in concepts if c["chapter"] == ch]
        ch_slug = lesson_slug(ch, used)
        node(slug=ch_slug, title=ch, kind="chapter", chapter=ch, concept_keys=[c["key"] for c in cs], status="open")
        for c in cs:
            r = learner.get(c["key"], {})
            mastered = r.get("p_mastery", 0) >= 0.8 or r.get("elo", 0) >= 1250
            status = "skippable" if mastered else ("open" if not first_open else "locked")
            if status == "open":
                first_open = True
            node(slug=lesson_slug(c["title"], used), title=c["title"], kind="page", chapter=ch, parent_slug=ch_slug,
                 concept_keys=[c["key"]], status=status)
        node(slug=lesson_slug(f"quiz {ch}", used), title=("Quiz — " if fr else "Quiz — ") + ch, kind="quiz", chapter=ch,
             parent_slug=ch_slug, concept_keys=[c["key"] for c in cs])
    node(slug=lesson_slug("projet" if fr else "project", used), title="Projet final" if fr else "Final project",
         kind="project", concept_keys=[c["key"] for c in concepts[-6:]])
    node(slug=lesson_slug("checkpoint", used), title="Validation de la compétence" if fr else "Skill checkpoint",
         kind="checkpoint", concept_keys=[c["key"] for c in concepts])
    if not first_open:
        for n in nodes:
            if n["kind"] == "page":
                n["status"] = "open"
                break
    ctx.store.put_many("tutorial", nodes)
    return {"tutorial_nodes": len(nodes)}


def unlock_next(ctx: Ctx, track_id: str, slug: str) -> dict[str, Any] | None:
    """Mark a page done and open the next one (pages, then the chapter quiz, then the project)."""
    nodes = sorted(ctx.store.list("tutorial", track_id=track_id), key=lambda n: n["ord"])
    cur = next((n for n in nodes if n["slug"] == slug), None)
    if cur is None:
        return None
    cur["status"] = "done"
    ctx.store.put("tutorial", cur)
    for n in nodes:
        if n["ord"] > cur["ord"] and n["kind"] != "chapter" and n["status"] in ("locked", "skippable", "open"):
            if n["status"] == "locked":
                n["status"] = "open"
                ctx.store.put("tutorial", n)
            return n
    return None
