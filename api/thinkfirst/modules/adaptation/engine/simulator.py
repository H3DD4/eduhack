"""Virtual students with KNOWN hidden states, to prove the engine recovers them (not LLM-simulated students).

Each virtual student follows the BKT generative story with hidden parameters:
  known? → answers correctly with prob 1-slip, else guesses; after each practice opportunity an unknown skill
  becomes known with prob `learn`. Some answers are assisted (higher guess). Students with a hidden bug produce
  the concept's misconception id on wrong answers until remediated (the simulator plays the tutor: after 2
  occurrences it gives a worked example, which raises the chance of learning). Each concept ends with a delayed
  unaided review check.
Output: JSON-ready events per student + the ground truth the engine never sees.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from thinkfirst.modules.adaptation.engine.schemas import (
    BKTParams,
    ConceptSpec,
    LearningEvent,
    MisconceptionSpec,
)


def default_concepts() -> list[ConceptSpec]:
    return [
        ConceptSpec(concept_id="F1", order=0, is_foundation=True),
        ConceptSpec(concept_id="c1", order=1),
        ConceptSpec(concept_id="c2", order=2, prerequisites=["c1", "F1"],
                    misconceptions=[MisconceptionSpec(id="first_term_only", label="Distributes to the first term only",
                                                      prerequisite_id="F1")]),
        ConceptSpec(concept_id="c3", order=3, prerequisites=["c2"]),
    ]


def simulate(n_students: int = 100, seed: int = 7, steps: int = 6, truth_params: BKTParams | None = None,
             concepts: list[ConceptSpec] | None = None, assisted_rate: float = 0.2, bug_rate: float = 0.5) -> dict:
    rng = random.Random(seed)
    prm = truth_params or BKTParams()
    concepts = concepts or default_concepts()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    students: dict[str, list[dict]] = {}
    truth: dict[str, dict] = {}
    for s in range(n_students):
        sid = f"sim{s:04d}"
        students[sid], truth[sid] = _student(rng, sid, prm, concepts, start, steps, assisted_rate, bug_rate)
    return {"concepts": [c.model_dump() for c in concepts], "students": students, "truth": truth}


def as_events(raw: list[dict]) -> list[LearningEvent]:
    return [LearningEvent.model_validate(e) for e in raw]


def _student(rng: random.Random, sid: str, prm: BKTParams, concepts: list[ConceptSpec], start: datetime, steps: int,
             assisted_rate: float, bug_rate: float) -> tuple[list[dict], dict]:
    ev: list[dict] = []
    t = start
    known_final: dict[str, bool] = {}
    oracle: dict[str, float] = {}  # event_id -> TRUE P(correct) given the hidden state (the best any model can do)

    def emit(ts: datetime, **kw) -> None:
        ev.append({"event_id": f"{sid}-{len(ev) + 1}", "student_id": sid, "ts": ts.isoformat(), **kw})

    for c in concepts:
        known = rng.random() < prm.prior
        bug = bool(c.misconceptions) and rng.random() < bug_rate
        learn = prm.learn
        bug_hits = 0
        for k in range(steps):
            t += timedelta(hours=2)
            assisted = rng.random() < assisted_rate
            g = prm.guess_assisted if assisted else prm.guess
            correct = rng.random() < ((1 - prm.slip) if known else g)
            mid = None
            if not correct and not known and bug:
                mid, bug_hits = c.misconceptions[0].id, bug_hits + 1
            oracle[f"{sid}-{len(ev) + 1}"] = (1 - prm.slip) if known else g
            emit(t, concept_id=c.concept_id, kind="attempt", item_id=f"{c.concept_id}-i{k}", is_fresh=True,
                 assistance="hint_l1" if assisted else "none", outcome="correct" if correct else "incorrect",
                 evidence="symbolic", misconception_id=mid, misconception_conf=0.9 if mid else None)
            if bug and bug_hits == 2:
                t += timedelta(minutes=10)
                emit(t, concept_id=c.concept_id, kind="worked_example", misconception_id=c.misconceptions[0].id)
                learn, bug = min(0.9, learn * 2.5), False  # remediation fixes the bug and speeds learning
            if not known and rng.random() < learn:
                known = True
        t += timedelta(days=4)
        correct = rng.random() < ((1 - prm.slip) if known else prm.guess)
        oracle[f"{sid}-{len(ev) + 1}"] = (1 - prm.slip) if known else prm.guess
        emit(t, concept_id=c.concept_id, kind="review_check", item_id=f"{c.concept_id}-review", is_fresh=True,
             assistance="none", outcome="correct" if correct else "incorrect", evidence="symbolic")
        known_final[c.concept_id] = known
    return ev, {"known": known_final, "oracle_p_correct": oracle}
