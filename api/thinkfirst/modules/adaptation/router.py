"""Adaptation API.

Per student (uses their own data):
  GET  /api/subjects/{s}/learner-state     engine state (levels, retention, misconceptions) + recommendation
  GET  /api/subjects/{s}/journey           learning path: wizard choices + roadmap -> level -> summary -> learn
Stateless engine (JSON in → JSON out, no database; for teammates, other services, notebooks):
  GET  /api/engine/schema                  JSON Schema of every input/output
  POST /api/engine/fold | /recommend | /evaluate | /select | /quality
Aggregates (anonymous):
  GET  /api/quality                         question + hint quality report
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.modules.adaptation import engine
from thinkfirst.modules.adaptation import service as adaptation
from thinkfirst.modules.adaptation.engine.items import QualityRequest, SelectRequest
from thinkfirst.modules.adaptation.engine.schemas import EvaluateRequest, FoldRequest, RecommendRequest
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.platform.identity.models import User
from thinkfirst.platform.workspaces import service as workspaces

router = APIRouter(tags=["adaptation"])


@router.get("/subjects/{subject_id}/learner-state")
def learner_state(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    titles = {c.id: c.title for c in ingestion.active_concepts(db, user.id, subject_id)}
    return {"state": adaptation.learner_state(db, user.id, subject_id), "titles": titles,
            "recommendation": adaptation.recommend(db, user.id, subject_id)}


@router.get("/subjects/{subject_id}/journey")
def journey(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """'Your learning path': wizard choices + roadmap -> level -> summary -> learn, with one next action."""
    from thinkfirst.modules.adaptation import journey as path

    return path.journey(db, user.id, subject_id)


@router.get("/quality")
def quality(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Question + hint quality from anonymous aggregate counts (ok / watch / retire|rewrite)."""
    return adaptation.quality_report(db)


@router.get("/engine/schema")
def schema():
    return engine.json_schemas()


@router.post("/engine/fold")
def fold(body: FoldRequest, user: User = Depends(current_user)):
    return engine.fold_json(body)


@router.post("/engine/recommend")
def recommend(body: RecommendRequest, user: User = Depends(current_user)):
    return engine.recommend_json(body)


@router.post("/engine/evaluate")
def evaluate(body: EvaluateRequest, user: User = Depends(current_user)):
    return engine.evaluate_json(body)


@router.post("/engine/select")
def select(body: SelectRequest, user: User = Depends(current_user)):
    return engine.select_item_json(body)


@router.post("/engine/quality")
def quality_stateless(body: QualityRequest, user: User = Depends(current_user)):
    return engine.quality_json(body)


# ---- planner (calendar + priorities) and progress metrics

class DeadlineIn(BaseModel):
    title: str | None = None
    kind: str | None = None
    due_on: str | None = None
    importance: int | None = None
    subject_id: str | None = None
    done: bool | None = None
    notes: str | None = None


@router.get("/planner")
def planner_view(start: str | None = None, end: str | None = None, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    from datetime import date as _d

    from thinkfirst.modules.adaptation import planner

    return planner.planner(db, user.id, _d.fromisoformat(start) if start else None, _d.fromisoformat(end) if end else None)


@router.post("/deadlines")
def create_deadline(body: DeadlineIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from thinkfirst.modules.adaptation import planner

    d = planner.create_deadline(db, user.id, body.model_dump(exclude_unset=True))
    return {"deadline": planner.deadline_public(d, {})}


@router.patch("/deadlines/{deadline_id}")
def update_deadline(deadline_id: str, body: DeadlineIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from thinkfirst.modules.adaptation import planner

    d = planner.update_deadline(db, user.id, deadline_id, body.model_dump(exclude_unset=True))
    return {"deadline": planner.deadline_public(d, {})}


@router.delete("/deadlines/{deadline_id}")
def delete_deadline(deadline_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from thinkfirst.modules.adaptation import planner

    planner.delete_deadline(db, user.id, deadline_id)
    return {"ok": True}


@router.get("/me/progress-metrics")
def progress_metrics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from thinkfirst.modules.adaptation import progress

    return progress.metrics(db, user.id)
