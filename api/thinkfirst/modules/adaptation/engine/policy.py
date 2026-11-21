"""Policy: WHICH concept next (frontier, ZPDES-style) and WHICH remediation action (Thompson-sampling bandit).

Concept order (each with a reason):
  1. remediate   — concepts with an active / remediating misconception
  2. review      — FSRS says recall probability fell below the threshold
  3. diagnostic  — a prerequisite was softened by a misconception upstream
  4. frontier    — not yet proficient, and every non-foundation prerequisite ≥ frontier_prereq_mastery
                   (foundations are optional refreshers, never gates)
  5. continue    — fallback: least-mastered remaining concept
Action bandit:
  context = "<error_class>|<mastery bucket low/mid/high>"; one Beta(α, β) per (context, action),
  starting from pedagogy priors; reward = next fresh UNAIDED scored answer on that concept after the
  recommendation (correct 1, incorrect 0, partial 0.5). Choice = argmax of one Beta draw per action;
  propensity = P(that action wins) estimated by Monte-Carlo, logged for offline IPS evaluation.
The bandit only orders what to OFFER first; the student's help ladder is never withheld.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

from thinkfirst.modules.adaptation.engine.fold import fold, prepare
from thinkfirst.modules.adaptation.engine.schemas import (
    SCORED_KINDS,
    ActionChoice,
    ConceptChoice,
    EngineConfig,
    FoldRequest,
    LearnerState,
    LearningEvent,
    Recommendation,
    RecommendRequest,
)

MC_DRAWS = 4000


def bucket(p: float) -> str:
    return "low" if p < 0.4 else "mid" if p < 0.7 else "high"


def context_key(error_class: str | None, p: float) -> str:
    return f"{error_class or 'generic'}|{bucket(p)}"


def priors(ctx: str, cfg: EngineConfig) -> dict[str, list[float]]:
    """Pedagogy priors (not zero): worked examples for low mastery, refutation for named misconceptions."""
    err, b = ctx.split("|")
    table = {a: [1.0, 1.0] for a in cfg.actions}
    if b == "low":
        table["worked_example"][0] += 2
        table["prerequisite_refresher"][0] += 1
    elif b == "mid":
        table["targeted_hint"][0] += 1
        table["guided_retry"][0] += 1
    else:
        table["guided_retry"][0] += 1
    if err not in ("generic", "none"):
        table["refutation"][0] += 2
    return table


def bandit_table(events: list[LearningEvent], cfg: EngineConfig) -> dict[str, dict[str, list[float]]]:
    """Fold logged recommendations + their observed rewards into Beta parameters per context."""
    tables: dict[str, dict[str, list[float]]] = {}
    for reward, rec in rewards(events):
        if not rec.context_key or not rec.recommended_action:
            continue
        t = tables.setdefault(rec.context_key, priors(rec.context_key, cfg))
        t[rec.recommended_action][0] += reward
        t[rec.recommended_action][1] += 1 - reward
    return tables


def rewards(events: list[LearningEvent]) -> list[tuple[float, LearningEvent]]:
    """Pair each recommendation with the next fresh unaided scored answer on the same concept."""
    out = []
    ordered = sorted(events, key=lambda e: (e.ts, e.event_id))
    for i, rec in enumerate(ordered):
        if rec.kind != "recommendation":
            continue
        for e in ordered[i + 1:]:
            if (e.student_id == rec.student_id and e.concept_id == rec.concept_id and e.kind in SCORED_KINDS and e.is_fresh and e.assistance == "none"
                    and e.outcome in ("correct", "incorrect", "partial")):
                out.append(({"correct": 1.0, "partial": 0.5, "incorrect": 0.0}[e.outcome], rec))
                break
    return out


def choose_action(ctx: str, table: dict[str, list[float]], seed: int | None) -> ActionChoice:
    rng = random.Random(seed)
    draws = {a: rng.betavariate(ab[0], ab[1]) for a, ab in table.items()}
    action = max(draws, key=lambda a: (draws[a], a))
    mc = random.Random(None if seed is None else seed + 1)
    wins = 0
    for _ in range(MC_DRAWS):
        d = {a: mc.betavariate(ab[0], ab[1]) for a, ab in table.items()}
        wins += max(d, key=lambda a: (d[a], a)) == action
    return ActionChoice(action=action, context_key=ctx, propensity=round(max(wins, 1) / MC_DRAWS, 4),
                        arm_stats={a: [round(x, 3) for x in ab] for a, ab in table.items()})


def next_concepts(state: LearnerState, req: RecommendRequest) -> list[ConceptChoice]:
    cfg = req.config
    specs = {c.concept_id: c for c in req.concepts}
    order = {cid: specs[cid].order if cid in specs else 10_000 for cid in state.concepts}
    cs = sorted(state.concepts.values(), key=lambda c: (order[c.concept_id], c.concept_id))
    out: list[ConceptChoice] = []
    seen: set[str] = set()

    def add(cid: str, kind: str, reason: str) -> None:
        if cid not in seen:
            seen.add(cid)
            out.append(ConceptChoice(concept_id=cid, kind=kind, reason=reason))  # type: ignore[arg-type]

    for c in cs:
        act = [m.id for m in c.misconceptions if m.status in ("active", "remediating")]
        if act:
            add(c.concept_id, "remediate", f"Misconception '{act[0]}' is still active here.")
    for c in cs:
        if c.review_due:
            add(c.concept_id, "review", f"Estimated recall {c.retrievability:.0%} has dropped below "
                                        f"{cfg.review_threshold_R:.0%} since your last unaided success.")
    for c in cs:
        if c.needs_diagnostic_check:
            add(c.concept_id, "diagnostic_check", "A mistake on a later concept points back to this one.")
    for c in cs:
        spec = specs.get(c.concept_id)
        if c.p_mastery >= cfg.proficient or (spec and spec.is_foundation):
            continue
        gates = [p for p in (spec.prerequisites if spec else []) if p in state.concepts
                 and not (specs.get(p) and specs[p].is_foundation)]
        if all(state.concepts[p].p_mastery >= cfg.frontier_prereq_mastery for p in gates):
            add(c.concept_id, "frontier", "Its prerequisites are in place and it isn't proficient yet.")
    rest = sorted((c for c in cs if c.p_mastery < cfg.mastered and c.concept_id not in seen
                   and not (specs.get(c.concept_id) and specs[c.concept_id].is_foundation)), key=lambda c: c.p_mastery)
    for c in rest[:1]:
        add(c.concept_id, "continue", "Least-developed concept remaining.")
    return out[:5]


def recommend(req: RecommendRequest) -> Recommendation:
    state = fold(FoldRequest(student_id=req.student_id, concepts=req.concepts, events=req.events,
                             as_of=req.as_of or datetime.now(UTC), config=req.config))
    choice = None
    if req.focus_concept_id:
        c = state.concepts.get(req.focus_concept_id)
        p = c.p_mastery if c else req.config.bkt.prior
        ctx = context_key(req.error_class, p)
        if req.bandit_stats is not None:
            table = priors(ctx, req.config)
            for action, (succ, fail) in req.bandit_stats.get(ctx, {}).items():
                if action in table:
                    table[action] = [table[action][0] + succ, table[action][1] + fail]
        else:
            own, _ = prepare(req.events, req.student_id)
            seen = {e.event_id for e in own}
            pooled = own + [e for e in req.population_events if e.event_id not in seen]
            table = bandit_table(pooled, req.config).get(ctx) or priors(ctx, req.config)
        choice = choose_action(ctx, table, req.seed)
    return Recommendation(next_concepts=next_concepts(state, req), action=choice)
