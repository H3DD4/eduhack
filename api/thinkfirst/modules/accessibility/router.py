from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.modules.accessibility import service
from thinkfirst.platform.identity.models import User

router = APIRouter(tags=["accessibility"])


class ConsentIn(BaseModel):
    accepted: bool


class ProfileChanges(BaseModel):
    changes: dict


@router.get("/me/accessibility")
def get_accessibility(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = service.get_profile(db, user.id)
    return {"profile": service.profile_public(profile)}


@router.post("/me/accessibility/consent")
def consent_accessibility(body: ConsentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = service.give_consent(db, user.id, body.accepted)
    return {"profile": service.profile_public(profile)}


@router.patch("/me/accessibility")
def update_accessibility(body: ProfileChanges, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = service.update_profile(db, user.id, body.changes)
    return {"profile": service.profile_public(profile)}


@router.get("/me/accessibility/export")
def export_accessibility(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = service.get_profile(db, user.id)
    return {"profile": service.profile_public(profile)}


@router.delete("/me/accessibility")
def delete_accessibility(user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.delete_profile(db, user.id)
    return {"deleted": True}
