"""Misconception state machine (closed taxonomy per concept — a "bug library").

    suspected  ──(2nd occurrence, or confidence ≥ activate_conf)──►  active
    active     ──(remediation: worked example / refresher / refutation)──►  remediating
    remediating──(N fresh unaided successes on the concept)──►  monitoring
    monitoring ──(unaided success ≥ resolve_after_days later)──►  resolved
    any state  ──(error seen again)──►  active   (relapse counted; history is never erased)
"""

from __future__ import annotations

from datetime import datetime

from thinkfirst.modules.adaptation.engine.retention import days_between
from thinkfirst.modules.adaptation.engine.schemas import EngineConfig, MisconceptionState


def _move(m: MisconceptionState, status: str, ts: datetime) -> None:
    m.history.append(f"{m.status}->{status}@{ts.isoformat()}")
    m.status = status  # type: ignore[assignment]
    m.status_since = ts


def observe_error(ms: dict[str, MisconceptionState], mid: str, conf: float | None, ts: datetime,
                  cfg: EngineConfig) -> tuple[MisconceptionState, bool]:
    """Returns (state, became_active_now)."""
    m = ms.get(mid)
    if m is None:
        m = MisconceptionState(id=mid, status="suspected", occurrences=1, first_seen=ts, last_seen=ts, status_since=ts,
                               history=[f"new->suspected@{ts.isoformat()}"])
        ms[mid] = m
        if conf is not None and conf >= cfg.activate_conf:
            _move(m, "active", ts)
            return m, True
        return m, False
    m.occurrences += 1
    m.last_seen = ts
    if m.status == "suspected":
        _move(m, "active", ts)
        return m, True
    if m.status in ("remediating", "monitoring", "resolved"):
        m.relapses += 1
        m.successes_since_remediation = 0
        _move(m, "active", ts)
        return m, True
    return m, False


def observe_remediation(ms: dict[str, MisconceptionState], mid: str | None, ts: datetime) -> None:
    for m in ms.values():
        if m.status == "active" and (mid is None or m.id == mid):
            m.successes_since_remediation = 0
            _move(m, "remediating", ts)


def observe_unaided_success(ms: dict[str, MisconceptionState], fresh: bool, ts: datetime, cfg: EngineConfig) -> None:
    for m in ms.values():
        if m.status == "remediating" and fresh:
            m.successes_since_remediation += 1
            if m.successes_since_remediation >= cfg.remediation_successes_needed:
                _move(m, "monitoring", ts)
        elif m.status == "monitoring" and days_between(m.status_since, ts) >= cfg.resolve_after_days:
            _move(m, "resolved", ts)
