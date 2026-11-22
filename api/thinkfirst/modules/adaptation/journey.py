"""'Your learning path' for one subject: the start-wizard choices and the four steps that follow, with ONE next action.

  1. Roadmap   — built from your files, or generated for the topic; you confirm it.
  2. Level     — placement test ("I know some of this") or "start from scratch" (= beginner).
  3. Summary   — your course summary, written for your level (covers every page of your files).
  4. Learn     — the learner engine's first concept (fix / review / frontier / next).
Read-only: it only aggregates other modules' state.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from thinkfirst.modules.diagnostic import placement
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.modules.tutor import summary as summaries
from thinkfirst.platform.workspaces import service as workspaces

GOAL_LABELS = {"exam": "Preparing for an exam", "explore": "Learning something new"}


def journey(db: Session, owner_id: str, subject_id: str) -> dict:
    from thinkfirst.modules.adaptation import service as adaptation

    subject = workspaces.get_subject(db, owner_id, subject_id)
    base = f"/subjects/{subject_id}"
    sources = [s for s in ingestion.sources_public(db, owner_id, subject_id) if s["status"] not in ("removed", "excluded")]
    concepts = ingestion.active_concepts(db, owner_id, subject_id) if subject.status == "ready" else []
    days = (subject.exam_date - date.today()).days if subject.exam_date else None
    intent = {
        "goal": subject.goal, "goal_label": GOAL_LABELS.get(subject.goal or "", "Learning"),
        "exam_date": subject.exam_date.isoformat() if subject.exam_date else None, "days_to_exam": days,
        "prior_knowledge": subject.prior_knowledge, "has_material": bool(sources),
        "material": {"files": len(sources), "pages": sum(s.get("page_count") or 0 for s in sources),
                     "names": [s["filename"] for s in sources][:6]},
    }
    steps: list[dict] = []

    # 1. roadmap
    if subject.status == "ready":
        units = len({c.unit_no for c in concepts})
        steps.append({"key": "roadmap", "state": "done", "title": "Your roadmap",
                      "detail": f"{len([c for c in concepts if not c.is_foundation])} levels in {units} unit(s)",
                      "action": {"label": "Open roadmap", "href": f"{base}/roadmap"}})
    else:
        building = subject.status == "processing"
        steps.append({"key": "roadmap", "state": "current", "title": "Your roadmap",
                      "detail": "Building it from your material…" if building else "Check the proposed roadmap and confirm it.",
                      "action": {"label": "Review roadmap", "href": f"{base}/setup"}})

    # 2. level
    pl = placement.status(db, owner_id, subject_id)
    rep = placement.report(db, owner_id, subject_id) if subject.status == "ready" else {"available": False}
    if subject.status != "ready":
        steps.append({"key": "level", "state": "todo", "title": "Your level",
                      "detail": "Level test" if subject.prior_knowledge == "some" else "Starting from scratch"})
    elif rep.get("available"):
        steps.append({"key": "level", "state": "done", "title": "Your level",
                      "detail": f"{rep['level_label']}" + {"placement_test": f" · {rep['score']}/100",
                                                           "from_scratch": " · starting from scratch"}.get(rep["basis"],
                                                                                                         " · no level test yet"),
                      "action": {"label": "See details", "href": f"{base}/start#level"}})
    else:
        st = pl["state"]
        detail, action = {
            "preparing": ("Your test questions are being written and double-checked (about 30–60 s). Open the test: it "
                          "starts as soon as they are ready.", {"label": "Open the level test", "href": f"{base}/diagnostic"}),
            "ready": ("About 5–12 multiple-choice questions, ~5 minutes. No help, no penalty for “I don't know”.",
                      {"label": "Take the level test", "href": f"{base}/diagnostic"}),
            "in_progress": (f"{pl['answered']} answered so far.", {"label": "Continue the test", "href": f"{base}/diagnostic"}),
            "failed": ("The test questions could not be prepared. Use the basic check, or start from scratch.",
                       {"label": "Take the basic check", "href": f"{base}/diagnostic"}),
        }.get(st, ("", None))
        steps.append({"key": "level", "state": "current", "title": "Your level", "detail": detail, "action": action,
                      "placement_state": st})

    # 3. summary
    sm = summaries.public(db, owner_id, subject_id)["summary"] if subject.status == "ready" else None
    if not rep.get("available"):
        steps.append({"key": "summary", "state": "todo", "title": "Your course summary",
                      "detail": "Written for your level once it is known."})
    elif sm is None or sm["level"] != rep["level"]:
        steps.append({"key": "summary", "state": "current", "title": "Your course summary",
                      "detail": (f"A {rep['level_label'].lower()}-level summary of " +
                                 ("every page of your course." if intent["has_material"] else "the whole roadmap.")),
                      "action": {"label": "Prepare my summary", "href": f"{base}/summary", "create": True}})
    elif sm["status"] == "building":
        steps.append({"key": "summary", "state": "current", "title": "Your course summary",
                      "detail": f"Writing section {sm['progress']['done'] + 1} of {sm['progress']['total']}…",
                      "action": {"label": "Read it as it arrives", "href": f"{base}/summary"}})
    else:
        cov = sm.get("coverage")
        steps.append({"key": "summary", "state": "done", "title": "Your course summary",
                      "detail": (f"{sm['progress']['total']} sections" +
                                 (f" · covers {cov['pages_covered']}/{cov['pages_total']} pages" if cov else "")),
                      "action": {"label": "Read summary", "href": f"{base}/summary"}})

    # 4. learn
    sug = adaptation.suggest_concept(db, owner_id, subject_id) if subject.status == "ready" else None
    if sug:
        steps.append({"key": "learn", "state": "current" if all(s["state"] == "done" for s in steps) else "todo",
                      "title": "Learn and practise",
                      "detail": sug["reason"], "concept": {"id": sug["concept_id"], "title": sug["title"], "kind": sug["kind"]},
                      "action": {"label": f"Start “{sug['title']}”", "href": f"{base}/roadmap/concepts/{sug['concept_id']}"}})
    else:
        steps.append({"key": "learn", "state": "todo", "title": "Learn and practise",
                      "detail": "Lessons, practice and checks adapt to your level."})

    nxt = next((s for s in steps if s["state"] == "current" and s.get("action")), None)
    return {"subject": workspaces.subject_public(subject), "intent": intent, "steps": steps,
            "next": nxt["action"] | {"step": nxt["key"]} if nxt else None,
            "placement": pl, "level": rep, "summary": sm}
