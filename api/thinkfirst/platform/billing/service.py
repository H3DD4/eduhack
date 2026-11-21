"""billing service: quotas + reservations (override §3.11, blueprint Q01/UC38).

Rules:
- A costly action may only *start* with a reservation; the whole validation bundle
  (explanation + follow-up + transfer) is reserved before the explanation stage begins.
- Consuming reserved units never fails and is idempotent (retries never double-charge).
- Reservation failure returns the Q01 payload (actual usage, reset time, preserved intent). No prices.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core.db import utcnow
from thinkfirst.core.errors import Conflict, QuotaExhausted
from thinkfirst.platform.billing.models import Entitlement, Reservation, UsageCharge

VALIDATION_STAGES = ("explanation", "followup", "transfer")


def entitlement(db: Session, owner_id: str) -> Entitlement:
    ent = db.scalar(select(Entitlement).where(Entitlement.owner_id == owner_id))
    s = get_settings()
    if ent is None:
        ent = Entitlement(owner_id=owner_id, period_units=s.free_units_per_period, period_start=utcnow(),
                          period_days=s.period_days)
        db.add(ent)
        db.flush()
    # Roll the period forward (mock provider behaviour).
    while ent.period_start + timedelta(days=ent.period_days) <= utcnow():
        ent.period_start = ent.period_start + timedelta(days=ent.period_days)
    return ent


def status(db: Session, owner_id: str) -> dict:
    ent = entitlement(db, owner_id)
    consumed = db.scalar(select(func.coalesce(func.sum(UsageCharge.units), 0)).where(
        UsageCharge.owner_id == owner_id, UsageCharge.created_at >= ent.period_start)) or 0
    open_res = db.scalars(select(Reservation).where(
        Reservation.owner_id == owner_id, Reservation.status == "reserved")).all()
    held = sum(r.units_reserved - r.units_consumed for r in open_res)
    return {
        "plan": ent.plan,
        "provider": ent.provider,
        "provider_label": "Mock entitlement provider (no real payments)",
        "period_units": ent.period_units,
        "used_units": int(consumed),
        "held_units": int(held),
        "available_units": max(0, ent.period_units - int(consumed) - int(held)),
        "resets_at": (ent.period_start + timedelta(days=ent.period_days)).isoformat(),
    }


def reserve(db: Session, owner_id: str, kind: str, units: int, idempotency_key: str,
            purpose_ref: str | None = None, intent: dict | None = None) -> Reservation:
    existing = db.scalar(select(Reservation).where(Reservation.idempotency_key == idempotency_key))
    if existing:
        if existing.owner_id != owner_id:
            raise Conflict("Reservation key conflict.")
        return existing
    st = status(db, owner_id)
    if st["available_units"] < units:
        raise QuotaExhausted(
            "This action needs more allowance than is available right now. Your work is unchanged.",
            quota=st, needed_units=units, pending_intent=intent or {"kind": kind, "ref": purpose_ref},
        )
    res = Reservation(owner_id=owner_id, kind=kind, units_reserved=units, purpose_ref=purpose_ref,
                      idempotency_key=idempotency_key)
    db.add(res)
    db.flush()
    return res


def consume(db: Session, reservation: Reservation, units: int, reason: str, idempotency_key: str) -> UsageCharge:
    """Charge against an existing reservation. Idempotent; never raises for quota."""
    existing = db.scalar(select(UsageCharge).where(UsageCharge.idempotency_key == idempotency_key))
    if existing:
        return existing
    units = min(units, reservation.units_reserved - reservation.units_consumed)
    charge = UsageCharge(owner_id=reservation.owner_id, reservation_id=reservation.id, units=max(units, 0),
                         reason=reason, idempotency_key=idempotency_key)
    db.add(charge)
    reservation.units_consumed += max(units, 0)
    if reservation.units_consumed >= reservation.units_reserved:
        reservation.status = "consumed"
    db.flush()
    return charge


def release(db: Session, reservation: Reservation) -> None:
    if reservation.status == "reserved":
        reservation.status = "released"
        db.flush()


def get_reservation(db: Session, owner_id: str, reservation_id: str | None) -> Reservation | None:
    if not reservation_id:
        return None
    return db.scalar(select(Reservation).where(Reservation.id == reservation_id, Reservation.owner_id == owner_id))


def demo_set_used(db: Session, owner_id: str, used_units: int) -> dict:
    """Demo tool (DEMO_MODE only): simulate usage so Q01 can be demonstrated. Labeled in the UI."""
    ent = entitlement(db, owner_id)
    current = status(db, owner_id)["used_units"]
    delta = used_units - current
    if delta != 0:
        key = f"demo-usage:{owner_id}:{utcnow().timestamp()}"
        res = Reservation(owner_id=owner_id, kind="demo_adjustment", units_reserved=max(delta, 0),
                          units_consumed=max(delta, 0), status="consumed", idempotency_key=key)
        db.add(res)
        db.flush()
        db.add(UsageCharge(owner_id=owner_id, reservation_id=res.id, units=delta, reason="demo_adjustment",
                           idempotency_key=key))
        db.flush()
    _ = ent
    return status(db, owner_id)
