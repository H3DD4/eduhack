"""identity HTTP API: A01 auth, A02 onboarding, A03 settings/privacy, consent + audit log."""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.core.errors import AppError, ValidationFailed
from thinkfirst.modules.identity import service
from thinkfirst.modules.identity.models import User

router = APIRouter(tags=["identity"])

GOALS = {"understand", "exam", "self_study", "unsure"}


def user_public(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "role": u.role,
        "is_demo": u.is_demo,
        "setup_complete": u.setup_complete,
        "goal": u.goal,
        "timezone": u.timezone,
        "preferences": u.preferences,
    }


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(s.session_cookie_name, token, httponly=True, samesite="lax",
                        secure=s.session_cookie_secure, max_age=s.session_days * 86400, path="/")


class Credentials(BaseModel):
    email: str
    password: str
    display_name: str = ""


@router.post("/auth/register")
def register(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = service.register(db, body.email, body.password, body.display_name)
    _set_cookie(response, service.create_session(db, user))
    return {"user": user_public(user)}


@router.post("/auth/login")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = service.authenticate(db, body.email, body.password)
    _set_cookie(response, service.create_session(db, user))
    return {"user": user_public(user)}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    service.revoke_session(db, request.cookies.get(get_settings().session_cookie_name))
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"user": user_public(user)}


@router.get("/auth/providers")
def providers():
    s = get_settings()
    return {
        "password": True,
        "google": bool(s.google_client_id and s.google_client_secret),
        "demo": s.demo_mode,
        "demo_credentials": {"email": "demo@thinkfirst.local", "password": "demo-password"} if s.demo_mode else None,
    }


# ---- Google OAuth (real authorization-code flow when configured; otherwise a labeled 501) ----

@router.get("/auth/google/start")
def google_start(request: Request):
    s = get_settings()
    if not (s.google_client_id and s.google_client_secret):
        raise AppError("Google sign-in is not configured in this environment.", code="PROVIDER_NOT_CONFIGURED", status=501)
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": s.google_client_id,
        "redirect_uri": f"{s.app_base_url}/api/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    resp = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
    resp.set_cookie("tf_oauth_state", state, httponly=True, samesite="lax", max_age=600, path="/")
    return resp


@router.get("/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    s = get_settings()
    if not (s.google_client_id and s.google_client_secret):
        raise AppError("Google sign-in is not configured.", code="PROVIDER_NOT_CONFIGURED", status=501)
    if not state or state != request.cookies.get("tf_oauth_state"):
        raise AppError("Sign-in could not be verified. Try again.", code="OAUTH_STATE_MISMATCH")
    token_resp = httpx.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": s.google_client_id, "client_secret": s.google_client_secret,
        "redirect_uri": f"{s.app_base_url}/api/auth/google/callback", "grant_type": "authorization_code",
    }, timeout=10)
    if token_resp.status_code != 200:
        raise AppError("Google sign-in failed.", code="OAUTH_EXCHANGE_FAILED")
    info = httpx.get("https://openidconnect.googleapis.com/v1/userinfo",
                     headers={"Authorization": f"Bearer {token_resp.json()['access_token']}"}, timeout=10).json()
    if not info.get("email_verified"):
        raise AppError("Google account email is not verified.", code="OAUTH_EMAIL_UNVERIFIED")
    user = service.upsert_google_user(db, info["sub"], info["email"], info.get("name", ""))
    resp = RedirectResponse(f"{s.app_base_url}/")
    _set_cookie(resp, service.create_session(db, user))
    resp.delete_cookie("tf_oauth_state", path="/")
    return resp


# ---- A02 onboarding / A03 settings ----

class Onboarding(BaseModel):
    goal: str = "unsure"
    timezone: str = "UTC"
    input_preference: str = "text"


@router.patch("/me/onboarding")
def onboarding(body: Onboarding, user: User = Depends(current_user)):
    if body.goal not in GOALS:
        raise ValidationFailed("Choose a goal or Unsure.", field="goal")
    user.goal = body.goal
    user.timezone = body.timezone[:64] or "UTC"
    service.update_preferences(user, {"input_preference": body.input_preference})
    user.setup_complete = True
    return {"user": user_public(user)}


class PrefChanges(BaseModel):
    changes: dict


@router.patch("/me/settings")
def update_settings(body: PrefChanges, user: User = Depends(current_user)):
    return {"preferences": service.update_preferences(user, body.changes)}


class ConsentIn(BaseModel):
    purpose: str
    scope_items: list[dict]
    hours: int = 48


@router.get("/me/consent-grants")
def list_grants(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from sqlalchemy import select

    from thinkfirst.modules.identity.models import ConsentGrant

    rows = db.scalars(select(ConsentGrant).where(ConsentGrant.student_id == user.id)).all()
    return {"grants": [{"id": g.id, "purpose": g.purpose, "scope_items": g.scope_items,
                        "expires_at": g.expires_at.isoformat(),
                        "revoked_at": g.revoked_at.isoformat() if g.revoked_at else None} for g in rows]}


@router.post("/me/consent-grants")
def create_grant(body: ConsentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    g = service.create_consent(db, user, body.purpose, body.scope_items, body.hours)
    return {"id": g.id, "expires_at": g.expires_at.isoformat()}


@router.delete("/me/consent-grants/{grant_id}")
def revoke_grant(grant_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    g = service.revoke_consent(db, user, grant_id)
    return {"id": g.id, "revoked_at": g.revoked_at.isoformat() if g.revoked_at else None}


@router.get("/me/audit-log")
def audit_log(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"entries": [{"id": r.id, "actor_role": r.actor_role, "action": r.action, "target_type": r.target_type,
                         "target_id": r.target_id, "purpose": r.purpose, "created_at": r.created_at.isoformat()}
                        for r in service.audit_log_for_student(db, user.id)]}
