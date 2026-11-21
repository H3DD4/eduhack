from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.core.errors import Forbidden
from thinkfirst.modules.billing import service
from thinkfirst.modules.identity.models import User

router = APIRouter(tags=["billing"])


@router.get("/billing/quota")
def quota(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.status(db, user.id)


class DemoUsage(BaseModel):
    used_units: int


@router.post("/billing/demo/usage")
def demo_usage(body: DemoUsage, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Demo-only control to show the Q01 safe boundary. Disabled unless DEMO_MODE and a demo account."""
    if not (get_settings().demo_mode and user.is_demo):
        raise Forbidden("Demo tools are only available on the demo account.")
    return service.demo_set_used(db, user.id, max(0, body.used_units))
