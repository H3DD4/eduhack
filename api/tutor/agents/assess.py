"""Group 2 · Assess: the level check (declare -> probe -> reconcile).

The student declares Beginner / Intermediate / Advanced (Elo 900 / 1100 / 1300). A short adaptive QCM probe
(6-10 items, aiming at 50 % success) moves the estimate; answers faster than 2.5 s are treated as rapid
guesses and do not count. The reconcile step reports confirmed / higher / lower, per chapter, and seeds the
learner model so the first material starts at the right difficulty.
"""

from __future__ import annotations

from typing import Any

from ..learner import bkt_update, elo_update, level_from_elo, new_record
from ..schemas import LEVEL_ELO, new_id, now_iso
from .base import Ctx

RAPID_MS = 2500


def public_item(it: dict[str, Any]) -> dict[str, Any]:
    """What the student sees: never the key, rationales or explanation before answering."""
    out = {k: v for k, v in it.items() if k not in ("explanation", "likeness_detail", "verification", "citations",
                                                   "accept", "answer")}
    if "options" in out:
        out["options"] = [{"text": o["text"]} for o in out["options"]]
    if "parts" in out:
        out["parts"] = [{k: v for k, v in p.items() if k not in ("answer", "check", "solution_steps")} for p in out["parts"]]
    return out


def _bank(ctx: Ctx, track_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    arts = [a for a in ctx.store.list("artifacts", track_id=track_id) if a["type"] == "probe"]
    if not arts:
        return None, []
    return arts[-1], arts[-1]["content"]["items"]


def start(ctx: Ctx, track_id: str, declared: str, per_chapter: dict[str, str] | None = None) -> dict[str, Any]:
    t = ctx.track(track_id)
    theta = LEVEL_ELO[declared]
    probe = {"theta": theta, "asked": [], "scored": 0, "history": [theta], "per_concept": {}, "done": False,
             "declared_by_chapter": per_chapter or {}}
    ctx.save_track(t, declared_level=declared, status="probing", stats={**t.get("stats", {}), "probe": probe})
    return probe


def next_item(ctx: Ctx, track_id: str) -> dict[str, Any] | None:
    t = ctx.track(track_id)
    probe = t["stats"].get("probe")
    if not probe or probe["done"]:
        return None
    _, items = _bank(ctx, track_id)
    remaining = [i for i in items if i["id"] not in probe["asked"]]
    if not remaining or probe["scored"] >= ctx.settings.probe_max_items:
        return None
    asked_concepts = {i["concept_key"] for i in items if i["id"] in probe["asked"]}
    fresh = [i for i in remaining if i["concept_key"] not in asked_concepts] or remaining
    target = probe["theta"]  # 50 % success: item difficulty == ability
    it = min(fresh, key=lambda i: abs(i.get("difficulty", 1100) - target))
    return {**public_item(it), "progress": {"answered": probe["scored"], "max": ctx.settings.probe_max_items}}


def answer(ctx: Ctx, track_id: str, item_id: str, choice: list[int] | int, ms: int | None) -> dict[str, Any]:
    t = ctx.track(track_id)
    probe = t["stats"]["probe"]
    art, items = _bank(ctx, track_id)
    it = next((i for i in items if i["id"] == item_id), None)
    if it is None or item_id in probe["asked"]:
        raise KeyError("item")
    picked = set([choice] if isinstance(choice, int) else choice)
    correct_set = {k for k, o in enumerate(it["options"]) if o["correct"]}
    correct = picked == correct_set
    rapid = ms is not None and ms < RAPID_MS
    probe["asked"].append(item_id)
    ck = it["concept_key"]
    if not rapid:
        n = probe["scored"]
        k = max(24.0, 80.0 / (1 + 0.35 * n))
        theta, _ = elo_update(probe["theta"], it.get("difficulty", 1100), 1.0 if correct else 0.0, k_student=k, k_item=0)
        probe["theta"] = round(theta, 1)
        pc = probe["per_concept"].setdefault(ck, {"elo": probe["history"][0], "right": 0, "wrong": 0})
        pc["elo"], _ = elo_update(pc["elo"], it.get("difficulty", 1100), 1.0 if correct else 0.0, k_student=64, k_item=0)
        pc["elo"] = round(pc["elo"], 1)
        pc["right" if correct else "wrong"] += 1
        probe["scored"] = n + 1
        probe["history"].append(probe["theta"])
    tags = []
    if not correct:
        for k_ in picked:
            if 0 <= k_ < len(it["options"]) and not it["options"][k_]["correct"] and it["options"][k_].get("why"):
                tags.append(it["options"][k_]["why"][:60])
    ctx.store.put("attempts", {"id": new_id(), "track_id": track_id, "owner_id": t["owner_id"],
                               "artifact_id": art["id"] if art else None, "item_id": item_id, "concept_key": ck,
                               "context": "probe", "answer": sorted(picked), "correct": correct,
                               "score": 1.0 if correct else 0.0, "ms": ms, "help_level": 0, "rapid_guess": rapid,
                               "error_tags": tags, "feedback": "", "created_at": now_iso()})
    s = ctx.settings
    h = probe["history"]
    stable = len(h) >= 4 and max(abs(h[-1] - h[-2]), abs(h[-2] - h[-3]), abs(h[-3] - h[-4])) < 25
    remaining = [i for i in items if i["id"] not in probe["asked"]]
    probe["done"] = (probe["scored"] >= s.probe_max_items or (probe["scored"] >= s.probe_min_items and stable)
                     or not remaining)
    ctx.save_track(t, stats={**t["stats"], "probe": probe})
    # no right/wrong feedback during the probe: it measures, it does not teach
    return {"recorded": True, "rapid_guess": rapid, "done": probe["done"],
            "progress": {"answered": probe["scored"], "max": s.probe_max_items}}


def reconcile(ctx: Ctx, state: dict[str, Any] | None = None, *, track_id: str | None = None) -> dict[str, Any]:
    track_id = track_id or (state or {})["track_id"]
    t = ctx.track(track_id)
    probe = t["stats"].get("probe") or {"theta": LEVEL_ELO[t.get("declared_level") or "intermediate"], "scored": 0,
                                        "per_concept": {}}
    declared = t.get("declared_level") or "intermediate"
    theta = probe["theta"]
    measured = level_from_elo(theta) if probe["scored"] >= 3 else declared
    order = ["beginner", "intermediate", "advanced"]
    verdict = ("unverified" if probe["scored"] < 3 else "confirmed" if measured == declared
               else "higher" if order.index(measured) > order.index(declared) else "lower")
    concepts = ctx.concepts(track_id)
    by_chapter: dict[str, list[float]] = {}
    for c in concepts:
        pc = probe["per_concept"].get(c["key"])
        if pc:
            by_chapter.setdefault(c["chapter"], []).append(pc["elo"])
    # few items per chapter: shrink each chapter estimate halfway toward the overall ability
    level_by_chapter = {ch: level_from_elo(0.5 * sum(v) / len(v) + 0.5 * theta) for ch, v in by_chapter.items()}
    for ch, lvl in (probe.get("declared_by_chapter") or {}).items():
        level_by_chapter.setdefault(ch, lvl)
    attempts = [a for a in ctx.store.list("attempts", track_id=track_id) if a["context"] == "probe" and not a["rapid_guess"]]
    records = []
    for c in concepts:
        pc = probe["per_concept"].get(c["key"])
        ch_vals = by_chapter.get(c["chapter"])
        elo = (0.5 * pc["elo"] + 0.5 * theta) if pc else (0.5 * sum(ch_vals) / len(ch_vals) + 0.5 * theta if ch_vals else theta)
        rec = ctx.store.get("learner", f"{track_id}:{c['key']}") or new_record(track_id, t["owner_id"], c["key"], elo)
        rec["elo"] = round(elo, 1)
        p = {"beginner": 0.1, "intermediate": 0.3, "advanced": 0.5}[level_from_elo(elo)]
        for a in attempts:
            if a["concept_key"] == c["key"]:
                p = bkt_update(p, bool(a["correct"]))
        rec["p_mastery"] = round(p, 4)
        records.append(rec)
    ctx.store.put_many("learner", records)
    result = {"declared": declared, "measured": measured, "verdict": verdict, "theta": round(theta),
              "level_by_chapter": level_by_chapter, "items_scored": probe["scored"],
              "rapid_guesses": sum(1 for a in ctx.store.list("attempts", track_id=track_id)
                                   if a["context"] == "probe" and a["rapid_guess"])}
    ctx.save_track(ctx.track(track_id), measured_level=measured, level_verdict=verdict,
                   level_by_chapter=level_by_chapter, status="levelled",
                   stats={**ctx.track(track_id)["stats"], "level_result": result})
    ctx.event("diagnostic.completed", {"track_id": track_id, **result})
    return result
