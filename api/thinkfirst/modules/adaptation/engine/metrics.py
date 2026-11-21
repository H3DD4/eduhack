"""Validation metrics (pyKT-style protocol).

  * prediction quality: before each unaided-or-assisted correct/incorrect answer, the model predicts P(correct);
    we score those predictions with AUC (Mann-Whitney, ties = 0.5), Brier score, log loss, 10-bin calibration
  * misconception recovery: activated → resolved rate, mean scored events to recover
  * delayed recall: share of delayed unaided checks that succeeded
  * offline policy evaluation: inverse propensity scoring of a target policy on logged recommendations
"""

from __future__ import annotations

import math

from thinkfirst.modules.adaptation.engine.fold import fold, prepare
from thinkfirst.modules.adaptation.engine.policy import rewards
from thinkfirst.modules.adaptation.engine.schemas import EvaluateRequest, FoldRequest, LearningEvent, Metrics


def auc(scores: list[float], labels: list[int]) -> float | None:
    """Rank-based AUC (Mann-Whitney U), O(n log n), ties get average ranks."""
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if not n_pos or not n_neg:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    rank_sum = sum(r for r, y in zip(ranks, labels, strict=True) if y == 1)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def evaluate(req: EvaluateRequest) -> Metrics:
    preds: list[float] = []
    ys: list[int] = []
    activated = resolved = 0
    recover_steps: list[int] = []
    delayed_checks = delayed_ok = 0
    logged: list[tuple[float, LearningEvent]] = []

    def hook(e: LearningEvent, p: float) -> None:
        preds.append(p)
        ys.append(1 if e.outcome == "correct" else 0)

    for sid, events in req.student_events.items():
        state = fold(FoldRequest(student_id=sid, concepts=req.concepts, events=events, config=req.config), on_predict=hook)
        for c in state.concepts.values():
            delayed_checks += c.delayed_checks
            delayed_ok += c.delayed_successes
            for m in c.misconceptions:
                if any("->active" in h for h in m.history):
                    activated += 1
                if m.status == "resolved":
                    resolved += 1
                    if m.events_to_resolve is not None:
                        recover_steps.append(m.events_to_resolve)
        own, _ = prepare(events, sid)
        logged.extend(rewards(own))

    n = len(preds)
    brier = sum((p - y) ** 2 for p, y in zip(preds, ys, strict=True)) / n if n else None
    ll = (-sum(y * math.log(max(p, 1e-6)) + (1 - y) * math.log(max(1 - p, 1e-6)) for p, y in zip(preds, ys, strict=True)) / n
          if n else None)
    bins = []
    for b in range(10):
        lo, hi = b / 10, (b + 1) / 10
        idx = [i for i, p in enumerate(preds) if lo <= p < hi or (b == 9 and p == 1.0)]
        if idx:
            bins.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(idx), "mean_predicted": round(sum(preds[i] for i in idx) / len(idx), 4),
                         "observed_correct": round(sum(ys[i] for i in idx) / len(idx), 4)})
    ips = logged_value = None
    if logged:
        logged_value = sum(r for r, _ in logged) / len(logged)
        if req.target_policy:
            usable = [(r, e) for r, e in logged if e.propensity and e.context_key]
            if usable:
                ips = sum((r / e.propensity) if req.target_policy.get(e.context_key) == e.recommended_action else 0.0
                          for r, e in usable) / len(usable)
    a = auc(preds, ys)
    return Metrics(predictions=n, auc=round(a, 4) if a is not None else None, brier=round(brier, 4) if brier is not None else None,
                   log_loss=round(ll, 4) if ll is not None else None, calibration=bins, misconceptions_activated=activated,
                   misconceptions_resolved=resolved, recovery_rate=round(resolved / activated, 4) if activated else None,
                   mean_events_to_recover=round(sum(recover_steps) / len(recover_steps), 2) if recover_steps else None,
                   delayed_checks=delayed_checks, delayed_recall_rate=round(delayed_ok / delayed_checks, 4) if delayed_checks else None,
                   ips_value=round(ips, 4) if ips is not None else None,
                   logged_policy_value=round(logged_value, 4) if logged_value is not None else None)
