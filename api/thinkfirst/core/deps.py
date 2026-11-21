"""Shared FastAPI dependencies: DB session, current user (sets RLS context), owned-row helpers."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core.db import current_user_id, get_db
from thinkfirst.core.errors import NotFound, Unauthorized
from thinkfirst.modules.identity.models import User
from thinkfirst.modules.identity.service import resolve_session


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    user = resolve_session(db, token)
    if user is None:
        raise Unauthorized()
    # Bind the RLS context for the rest of this request's transactions.
    db.info["user_id"] = user.id
    current_user_id.set(user.id)
    if db.in_transaction() and db.get_bind().dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(text("select set_config('app.user_id', :uid, true)"), {"uid": user.id})
    return user


def get_owned[T](db: Session, model: type[T], obj_id: str, owner_id: str) -> T:
    """Fetch a private row by ID, scoped to its owner. Other owners' rows are 'Not available' (404)."""
    obj = db.scalar(select(model).where(model.id == obj_id, model.owner_id == owner_id))  # type: ignore[attr-defined]
    if obj is None:
        raise NotFound()
    return obj


def owned[T](model: type[T], owner_id: str):
    return select(model).where(model.owner_id == owner_id)  # type: ignore[attr-defined]
