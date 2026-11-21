"""JSON contract of the learner engine (engine_version 1.0).

Every input and output is a Pydantic model => validated JSON in, JSON out, and a published JSON Schema
(`python -m thinkfirst.modules.adaptation.engine schema`). Nothing here touches a database or web framework.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ENGINE_VERSION = "1.0"

EventKind = Literal["attempt", "review_check", "explanation", "hint", "worked_example", "refresher", "refutation",
                    "recommendation"]
Assistance = Literal["none", "hint_l1", "hint_l2", "hint_l3", "worked_example", "solution_revealed", "guided"]
Outcome = Literal["correct", "partial", "incorrect", "unscored"]
Evidence = Literal["symbolic", "sufficient", "limited", "needs_verification"]
Action = Literal["targeted_hint", "worked_example", "prerequisite_refresher", "guided_retry", "refutation"]
MisconceptionStatus = Literal["suspected", "active", "remediating", "monitoring", "resolved"]

REMEDIATION_KINDS = {"worked_example", "refresher", "refutation"}
SCORED_KINDS = {"attempt", "review_check", "explanation"}


# ------------------------------------------------------------------ inputs

class LearningEvent(BaseModel):
    """One thing that happened. The learner state is a pure function of these (event sourcing)."""

    event_id: str = Field(description="Globally unique; duplicates are ignored (retries are free)")
    student_id: str
    concept_id: str
    ts: datetime
    kind: EventKind
    item_id: str | None = None
    is_fresh: bool = Field(True, description="First time this student sees this item")
    assistance: Assistance = "none"
    outcome: Outcome | None = Field(None, description="Required for attempt / review_check / explanation")
    evidence: Evidence = "sufficient"
    misconception_id: str | None = None
    misconception_conf: float | None = Field(None, ge=0, le=1)
    # bandit bookkeeping (kind == "recommendation")
    recommended_action: Action | None = None
    context_key: str | None = None
    propensity: float | None = Field(None, gt=0, le=1)


class MisconceptionSpec(BaseModel):
    id: str
    label: str = ""
    prerequisite_id: str | None = Field(None, description="Concept to soften and re-check when this is active")


class ConceptSpec(BaseModel):
    concept_id: str
    prerequisites: list[str] = []
    order: int = 0
    misconceptions: list[MisconceptionSpec] = []
    is_foundation: bool = False
    prior: float | None = Field(None, ge=0.0, le=1.0, description=(
        "Starting P(known) before any practice event, e.g. from a placement test or 'start from scratch'. "
        "None = BKTParams.prior."))


class BKTParams(BaseModel):
    prior: float = 0.10
    learn: float = 0.15
    guess: float = 0.15
    guess_assisted: float = 0.55
    slip: float = 0.10


class EngineConfig(BaseModel):
    bkt: BKTParams = BKTParams()
    concept_bkt: dict[str, BKTParams] = {}
    evidence_weight: dict[str, float] = {"symbolic": 1.0, "sufficient": 1.0, "limited": 0.5, "needs_verification": 0.0}
    # retention (FSRS-style)
    initial_stability_days: float = 1.0
    stability_growth: float = 1.0
    lapse_factor: float = 0.3
    min_stability_days: float = 0.5
    review_threshold_R: float = 0.85
    min_delay_for_retention_days: float = 1.0
    # misconceptions
    activate_conf: float = 0.8
    remediation_successes_needed: int = 2
    resolve_after_days: float = 3.0
    prereq_penalty: float = 0.85
    # policy
    frontier_prereq_mastery: float = 0.70
    proficient: float = 0.80
    mastered: float = 0.95
    actions: list[Action] = ["targeted_hint", "worked_example", "prerequisite_refresher", "guided_retry", "refutation"]


class FoldRequest(BaseModel):
    student_id: str
    concepts: list[ConceptSpec]
    events: list[LearningEvent]
    as_of: datetime | None = None
    config: EngineConfig = EngineConfig()


# ------------------------------------------------------------------ outputs

class MisconceptionState(BaseModel):
    id: str
    status: MisconceptionStatus
    occurrences: int = 0
    relapses: int = 0
    first_seen: datetime
    last_seen: datetime
    status_since: datetime
    successes_since_remediation: int = 0
    scored_events_since_active: int = 0
    events_to_resolve: int | None = Field(None, description="Scored events between (last) activation and resolution")
    history: list[str] = Field([], description="Status transitions, oldest first")


class ConceptState(BaseModel):
    concept_id: str
    p_mastery: float = Field(description="BKT probability the skill is known (internal; show `level`, not a %)")
    level: int = Field(ge=0, le=5)
    level_label: str
    scored_events: int = 0
    unaided_successes: int = 0
    assisted_successes: int = 0
    failures: int = 0
    stability_days: float | None = None
    last_unaided_success: datetime | None = None
    retrievability: float | None = Field(None, description="FSRS-style P(recall) at as_of")
    review_due: bool = False
    review_due_at: datetime | None = None
    delayed_checks: int = 0
    delayed_successes: int = 0
    misconceptions: list[MisconceptionState] = []
    needs_diagnostic_check: bool = False
    reasons: list[str] = Field([], description="Human-readable trace of what moved this state")


class LearnerState(BaseModel):
    engine_version: str = ENGINE_VERSION
    student_id: str
    as_of: datetime
    events_used: int
    events_ignored: int
    concepts: dict[str, ConceptState]


class RecommendRequest(BaseModel):
    student_id: str
    concepts: list[ConceptSpec]
    events: list[LearningEvent]
    as_of: datetime | None = None
    focus_concept_id: str | None = Field(None, description="If set, also choose a remediation action for this concept")
    error_class: str | None = Field(None, description="Misconception id or 'generic' for the action context")
    seed: int | None = Field(None, description="Fix for reproducible Thompson sampling")
    population_events: list[LearningEvent] = Field(
        [], description="Recommendation + answer events from all students (pseudonymous) so the bandit learns at "
                        "population level; only recommendation outcomes are used, never another student's state")
    bandit_stats: dict[str, dict[str, list[float]]] | None = Field(
        None, description="Pre-aggregated rewards: context_key -> action -> [successes, failures]. When given, it is "
                          "added to the pedagogy priors instead of folding raw events (privacy-friendly at scale)")
    config: EngineConfig = EngineConfig()


class ConceptChoice(BaseModel):
    concept_id: str
    kind: Literal["remediate", "review", "frontier", "diagnostic_check", "continue"]
    reason: str


class ActionChoice(BaseModel):
    action: Action
    context_key: str
    propensity: float = Field(description="P(this action chosen) under the sampling policy — log it for IPS")
    arm_stats: dict[str, list[float]] = Field(description="action -> [alpha, beta] used for the draw")


class Recommendation(BaseModel):
    engine_version: str = ENGINE_VERSION
    next_concepts: list[ConceptChoice]
    action: ActionChoice | None = None


class EvaluateRequest(BaseModel):
    student_events: dict[str, list[LearningEvent]]
    concepts: list[ConceptSpec]
    config: EngineConfig = EngineConfig()
    target_policy: dict[str, Action] | None = Field(None, description="context_key -> action, scored offline by IPS")


class Metrics(BaseModel):
    engine_version: str = ENGINE_VERSION
    predictions: int
    auc: float | None
    brier: float | None
    log_loss: float | None
    calibration: list[dict]
    misconceptions_activated: int
    misconceptions_resolved: int
    recovery_rate: float | None
    mean_events_to_recover: float | None
    delayed_checks: int
    delayed_recall_rate: float | None
    ips_value: float | None = None
    logged_policy_value: float | None = None
