"""fold(events) → learner state. Pure, deterministic, replayable (event sourcing).

Rules applied to each event, in (ts, event_id) order after de-duplicating event_id:
  * scored event (attempt / review_check / explanation) with outcome ≠ unscored:
      - BKT update with weight w = evidence_weight[evidence]; assisted ⇔ assistance ≠ none
      - retention: unaided success after ≥ min delay grows stability; unaided failure is a lapse
      - misconception: misconception_id on a wrong/partial answer feeds the state machine
      - unaided success advances remediating / monitoring misconceptions
  * remediation event (worked_example / refresher / refutation): active → remediating
  * hint / recommendation events never move mastery (they are context for help-awareness and the bandit)
  * unscored answers are logged but move nothing (uncertain ≠ wrong)
A misconception becoming active softly lowers its prerequisite's mastery (× prereq_penalty) and flags a
diagnostic check there — graph propagation without training a network.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from thinkfirst.modules.adaptation.engine import bkt, misconceptions, retention
from thinkfirst.modules.adaptation.engine.schemas import (
    REMEDIATION_KINDS,
    SCORED_KINDS,
    ConceptSpec,
    ConceptState,
    EngineConfig,
    FoldRequest,
    LearnerState,
    LearningEvent,
    MisconceptionState,
)

OBS = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
LEVELS = {0: "Not started", 1: "Introduced", 2: "Practising", 3: "Developing", 4: "Proficient", 5: "Mastered"}

Predictor = Callable[[LearningEvent, float], None]


class _C:
    """Mutable per-concept working state (internal)."""

    def __init__(self, spec: ConceptSpec, cfg: EngineConfig):
        self.spec = spec
        self.prm = cfg.concept_bkt.get(spec.concept_id, cfg.bkt)
        self.p = self.prm.prior
        self.scored = self.unaided_ok = self.assisted_ok = self.fail = 0
        self.stability: float | None = None
        self.last_unaided: datetime | None = None
        self.delayed_checks = self.delayed_ok = 0
        self.ms: dict[str, MisconceptionState] = {}
        self.diag = False
        self.reasons: list[str] = []


def _utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def prepare(events: list[LearningEvent], student_id: str) -> tuple[list[LearningEvent], int]:
    seen, out, ignored = set(), [], 0
    for e in events:
        if e.event_id in seen or e.student_id != student_id:
            ignored += 1
            continue
        if e.kind in SCORED_KINDS and e.outcome is None:
            ignored += 1  # invalid scored event without an outcome
            continue
        seen.add(e.event_id)
        out.append(e.model_copy(update={"ts": _utc(e.ts)}))
    out.sort(key=lambda e: (e.ts, e.event_id))
    return out, ignored


def fold(req: FoldRequest, on_predict: Predictor | None = None) -> LearnerState:
    cfg = req.config
    specs = {c.concept_id: c for c in req.concepts}
    events, ignored = prepare(req.events, req.student_id)
    cs: dict[str, _C] = {cid: _C(s, cfg) for cid, s in specs.items()}

    def get(cid: str) -> _C:
        if cid not in cs:
            spec = ConceptSpec(concept_id=cid, order=len(cs))
            specs[cid] = spec
            cs[cid] = _C(spec, cfg)
        return cs[cid]

    for e in events:
        c = get(e.concept_id)
        if e.kind in REMEDIATION_KINDS:
            misconceptions.observe_remediation(c.ms, e.misconception_id, e.ts)
            c.reasons.append(f"{e.ts.date()} remediation ({e.kind})")
            continue
        if e.kind not in SCORED_KINDS or e.outcome == "unscored":
            continue
        assisted = e.assistance != "none"
        w = cfg.evidence_weight.get(e.evidence, 0.0)
        if on_predict is not None and e.outcome in ("correct", "incorrect"):
            on_predict(e, bkt.predict_correct(c.p, assisted, c.prm))
        before = c.p
        c.p = bkt.update(c.p, OBS[e.outcome], assisted, w, c.prm)
        c.scored += 1
        for m in c.ms.values():
            if m.status != "resolved":
                m.scored_events_since_active += 1
        if c.diag and not assisted and w > 0:
            c.diag = False
        correct = e.outcome == "correct"
        unaided = not assisted and w >= 0.5
        c.reasons.append(f"{e.ts.date()} {e.kind} {e.outcome}{' (assisted)' if assisted else ''}: "
                         f"mastery {before:.2f}→{c.p:.2f}")
        if correct and assisted:
            c.assisted_ok += 1
        elif correct and unaided:
            c.unaided_ok += 1
            if c.stability is None:
                c.stability = cfg.initial_stability_days
            elif c.last_unaided is not None:
                gap = retention.days_between(c.last_unaided, e.ts)
                if gap >= cfg.min_delay_for_retention_days:
                    r = retention.retrievability(c.stability, gap)
                    c.stability = retention.after_success(c.stability, r, cfg)
                    c.delayed_checks += 1
                    c.delayed_ok += 1
            c.last_unaided = e.ts
            prev = {mid: m.status for mid, m in c.ms.items()}
            misconceptions.observe_unaided_success(c.ms, e.is_fresh or e.kind == "review_check", e.ts, cfg)
            for mid, m in c.ms.items():
                if prev[mid] != "resolved" and m.status == "resolved":
                    m.events_to_resolve = m.scored_events_since_active
        elif not correct:
            c.fail += 1
            if unaided and c.stability is not None and c.last_unaided is not None:
                if retention.days_between(c.last_unaided, e.ts) >= cfg.min_delay_for_retention_days:
                    c.delayed_checks += 1
                c.stability = retention.after_lapse(c.stability, cfg)
            if e.misconception_id:
                m, activated = misconceptions.observe_error(c.ms, e.misconception_id, e.misconception_conf, e.ts, cfg)
                if activated:
                    m.scored_events_since_active = 0
                    m.events_to_resolve = None
                    _propagate(c, e, cs, get, cfg)

    as_of = _utc(req.as_of) if req.as_of else (events[-1].ts if events else datetime.now(UTC))
    out = {cid: _state(c, as_of, cfg) for cid, c in cs.items()}
    return LearnerState(student_id=req.student_id, as_of=as_of, events_used=len(events), events_ignored=ignored,
                        concepts=out)


def _propagate(c: _C, e: LearningEvent, cs: dict[str, _C], get, cfg: EngineConfig) -> None:
    spec_m = next((m for m in c.spec.misconceptions if m.id == e.misconception_id), None)
    prereq = spec_m.prerequisite_id if spec_m else None
    if prereq:
        p = get(prereq)
        before = p.p
        p.p = max(0.0001, p.p * cfg.prereq_penalty)
        p.diag = True
        p.reasons.append(f"{e.ts.date()} misconception '{e.misconception_id}' active on {c.spec.concept_id}: "
                         f"prerequisite softened {before:.2f}→{p.p:.2f}, diagnostic check requested")
    c.reasons.append(f"{e.ts.date()} misconception '{e.misconception_id}' is now active")


def level_for(c: _C, cfg: EngineConfig) -> int:
    if c.scored == 0:
        return 0
    active = any(m.status in ("active", "remediating") for m in c.ms.values())
    if c.p >= cfg.mastered and c.unaided_ok >= 2 and c.delayed_ok >= 1 and not active:
        lvl = 5
    elif c.p >= cfg.proficient and c.unaided_ok >= 1:
        lvl = 4
    elif c.p >= 0.6:
        lvl = 3
    elif c.p >= 0.3:
        lvl = 2
    else:
        lvl = 1
    return min(lvl, 3) if active else lvl  # an active misconception caps the level


def _state(c: _C, as_of: datetime, cfg: EngineConfig) -> ConceptState:
    r = due = None
    review_due = False
    if c.stability is not None and c.last_unaided is not None:
        r = retention.retrievability(c.stability, retention.days_between(c.last_unaided, as_of))
        due = retention.due_at(c.last_unaided, c.stability, cfg)
        review_due = r < cfg.review_threshold_R
    lvl = level_for(c, cfg)
    return ConceptState(concept_id=c.spec.concept_id, p_mastery=round(c.p, 4), level=lvl, level_label=LEVELS[lvl],
                        scored_events=c.scored, unaided_successes=c.unaided_ok, assisted_successes=c.assisted_ok,
                        failures=c.fail, stability_days=round(c.stability, 3) if c.stability else None,
                        last_unaided_success=c.last_unaided, retrievability=round(r, 4) if r is not None else None,
                        review_due=review_due, review_due_at=due, delayed_checks=c.delayed_checks,
                        delayed_successes=c.delayed_ok, misconceptions=list(c.ms.values()),
                        needs_diagnostic_check=c.diag, reasons=c.reasons[-12:])
