"""Adaptation API.

Per student (uses their own data):
  GET  /api/subjects/{s}/learner-state     engine state (levels, retention, misconceptions) + recommendation
Stateless engine (JSON in → JSON out, no database; for teammates, other services, notebooks):
  GET  /api/engine/schema                  JSON Schema of every input/output
  POST /api/engine/fold | /recommend | /evaluate
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.modules.adaptation import engine
from thinkfirst.modules.adaptation import service as adaptation
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
