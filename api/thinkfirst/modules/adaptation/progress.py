"""Progress metrics (Progress page): how the student is doing overall and in each subject.

Everything is computed from the student's own records:
  * learner engine state per concept (level 0-5, P(known), retention, misconceptions)  -> mastery + concept graph
  * placement test report (level, score)                                               -> starting level
  * memory events (answers, help, explain-backs)                                       -> activity + independence
  * evidence records + sessions                                                        -> explain-backs, sessions done
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.platform.workspaces import service as workspaces

LEVEL_LABELS = {0: "Not started", 1: "Introduced", 2: "Practising", 3: "Developing", 4: "Proficient", 5: "Mastered"}


def _streak(days: set[date], today: date) -> int:
    n, d = 0, today if today in days else today - timedelta(days=1)
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


def metrics(db: Session, owner_id: str) -> dict:
    from thinkfirst.data.memory.models import LearningEvent
    from thinkfirst.data.student_profile.models import EvidenceRecord
    from thinkfirst.modules.adaptation import service as adaptation
    from thinkfirst.modules.diagnostic import placement
    from thinkfirst.modules.tutor.models import StudySession

    today = date.today()
    subjects = workspaces.list_subjects(db, owner_id)
    events = db.scalars(select(LearningEvent).where(LearningEvent.owner_id == owner_id)).all()
    answers = [e for e in events if e.outcome in ("correct", "partial", "incorrect")]
    independent = [e for e in answers if (e.assistance or "none") == "none"]
    active_days = {e.created_at.date() for e in events}
    per_day = Counter(e.created_at.date().isoformat() for e in events)
    evidence = db.scalars(select(EvidenceRecord).where(EvidenceRecord.owner_id == owner_id,
                                                       EvidenceRecord.status != "deleted")).all()
    explained = [ev for ev in evidence if ev.stage in ("explanation", "followup")]
    sessions = db.scalars(select(StudySession).where(StudySession.owner_id == owner_id)).all()

    out_subjects = []
    level_hist = Counter()
    misconceptions_total = resolved_total = 0
    for s in subjects:
        item = {"id": s.id, "name": s.name, "status": s.status, "goal": s.goal,
                "exam_date": s.exam_date.isoformat() if s.exam_date else None, "href": f"/subjects/{s.id}/start"}
        if s.status != "ready":
            out_subjects.append(item | {"ready": False})
            continue
        concepts = ingestion.active_concepts(db, owner_id, s.id)
        state = adaptation.learner_state(db, owner_id, s.id)["concepts"]
        rep = placement.report(db, owner_id, s.id)
        nodes, mis = [], []
        for c in concepts:
            st = state.get(c.id) or {}
            lvl = int(st.get("level", 0))
            if not c.is_foundation:
                level_hist[lvl] += 1
            for m in st.get("misconceptions") or []:
                if m.get("status") in ("active", "remediating", "monitoring", "resolved"):
                    misconceptions_total += 1
                    resolved_total += m["status"] == "resolved"
                    mis.append({"id": m.get("id"), "status": m["status"], "concept": c.title})
            nodes.append({"id": c.id, "key": c.key, "title": c.title, "unit_no": c.unit_no, "is_foundation": c.is_foundation,
                          "prerequisites": c.prerequisites, "level": lvl, "level_label": LEVEL_LABELS[lvl],
                          "p_mastery": round(float(st.get("p_mastery", 0.0)), 3), "review_due": bool(st.get("review_due")),
                          "href": f"/subjects/{s.id}/roadmap/concepts/{c.id}"})
        core = [n for n in nodes if not n["is_foundation"]] or nodes
        s_answers = [e for e in answers if e.subject_id == s.id]
        s_last = max((e.created_at for e in events if e.subject_id == s.id), default=None)
        sug = adaptation.suggest_concept(db, owner_id, s.id)
        item |= {
            "ready": True, "nodes": nodes,
            "level": rep.get("level_label") if rep.get("available") else None,
            "level_basis": rep.get("basis"), "score": rep.get("score") if rep.get("basis") == "placement_test" else None,
            "proficient": sum(1 for n in core if n["level"] >= 4), "total": len(core),
            "mastery_pct": round(100 * sum(n["p_mastery"] for n in core) / max(1, len(core))),
            "answers": len(s_answers),
            "accuracy": round(100 * sum(1 for e in s_answers if e.outcome == "correct") / len(s_answers)) if s_answers else None,
            "independent_pct": round(100 * sum(1 for e in s_answers if (e.assistance or "none") == "none") / len(s_answers))
            if s_answers else None,
            "explain_backs": sum(1 for ev in explained if ev.subject_id == s.id),
            "reviews_due": sum(1 for n in nodes if n["review_due"]),
            "misconceptions": mis[:6],
            "strengths": [n["title"] for n in core if n["level"] >= 4][:4],
            "gaps": [n["title"] for n in core if n["level"] <= 1][:4],
            "last_active": s_last.date().isoformat() if s_last else None,
            "next": {"title": sug["title"], "reason": sug["reason"], "href": f"/subjects/{s.id}/roadmap/concepts/{sug['concept_id']}"}
            if sug else None,
        }
        out_subjects.append(item)

    ready = [x for x in out_subjects if x.get("ready")]
    return {
        "overview": {
            "subjects": len(subjects), "concepts_total": sum(x["total"] for x in ready),
            "concepts_proficient": sum(x["proficient"] for x in ready),
            "answers": len(answers),
            "accuracy": round(100 * sum(1 for e in answers if e.outcome == "correct") / len(answers)) if answers else None,
            "independent_pct": round(100 * len(independent) / len(answers)) if answers else None,
            "explain_backs": len(explained), "sessions_completed": sum(1 for x in sessions if x.status == "completed"),
            "streak_days": _streak(active_days, today), "active_days_30": sum(1 for d in active_days if (today - d).days < 30),
            "misconceptions_seen": misconceptions_total, "misconceptions_resolved": resolved_total,
        },
        "level_distribution": [{"level": k, "label": LEVEL_LABELS[k], "count": level_hist.get(k, 0)} for k in range(6)],
        "activity": [{"date": (today - timedelta(days=i)).isoformat(), "events": per_day.get((today - timedelta(days=i)).isoformat(), 0)}
                     for i in range(83, -1, -1)],
        "subjects": out_subjects,
    }
