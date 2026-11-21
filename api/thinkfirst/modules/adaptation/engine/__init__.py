"""ThinkFirst learner engine — standalone, JSON in / JSON out (no database, no web framework).

Public API (each takes a dict or model, returns a JSON-ready dict):
    fold_json(payload)       FoldRequest      -> LearnerState     (mastery, level, retention, misconceptions)
    recommend_json(payload)  RecommendRequest -> Recommendation   (next concepts + remediation action)
    evaluate_json(payload)   EvaluateRequest  -> Metrics          (AUC, Brier, recovery, delayed recall, IPS)
    select_item_json(payload) SelectRequest   -> SelectResult     (next question: fresh, trigger, difficulty-matched)
    quality_json(payload)    QualityRequest   -> QualityReport    (question + hint quality from aggregate counts)
    json_schemas()           JSON Schema of every input/output (the contract)
CLI: python -m thinkfirst.modules.adaptation.engine {fold|recommend|evaluate|simulate|schema} < in.json > out.json
"""

from __future__ import annotations

from typing import Any

from thinkfirst.modules.adaptation.engine.fold import fold
from thinkfirst.modules.adaptation.engine.items import (
    QualityReport,
    QualityRequest,
    SelectRequest,
    SelectResult,
    quality,
    select_item,
)
from thinkfirst.modules.adaptation.engine.metrics import evaluate
from thinkfirst.modules.adaptation.engine.policy import recommend
from thinkfirst.modules.adaptation.engine.schemas import (
    ENGINE_VERSION,
    EvaluateRequest,
    FoldRequest,
    LearnerState,
    Metrics,
    Recommendation,
    RecommendRequest,
)

__all__ = ["ENGINE_VERSION", "fold_json", "recommend_json", "evaluate_json", "select_item_json", "quality_json",
           "json_schemas", "fold", "recommend", "evaluate", "select_item", "quality"]


def fold_json(payload: dict[str, Any] | FoldRequest) -> dict:
    req = payload if isinstance(payload, FoldRequest) else FoldRequest.model_validate(payload)
    return fold(req).model_dump(mode="json")


def recommend_json(payload: dict[str, Any] | RecommendRequest) -> dict:
    req = payload if isinstance(payload, RecommendRequest) else RecommendRequest.model_validate(payload)
    return recommend(req).model_dump(mode="json")


def evaluate_json(payload: dict[str, Any] | EvaluateRequest) -> dict:
    req = payload if isinstance(payload, EvaluateRequest) else EvaluateRequest.model_validate(payload)
    return evaluate(req).model_dump(mode="json")


def select_item_json(payload: dict[str, Any] | SelectRequest) -> dict:
    req = payload if isinstance(payload, SelectRequest) else SelectRequest.model_validate(payload)
    return select_item(req).model_dump(mode="json")


def quality_json(payload: dict[str, Any] | QualityRequest) -> dict:
    req = payload if isinstance(payload, QualityRequest) else QualityRequest.model_validate(payload)
    return quality(req).model_dump(mode="json")


def json_schemas() -> dict:
    return {"engine_version": ENGINE_VERSION,
            "inputs": {m.__name__: m.model_json_schema() for m in
                       (FoldRequest, RecommendRequest, EvaluateRequest, SelectRequest, QualityRequest)},
            "outputs": {m.__name__: m.model_json_schema() for m in
                        (LearnerState, Recommendation, Metrics, SelectResult, QualityReport)}}
