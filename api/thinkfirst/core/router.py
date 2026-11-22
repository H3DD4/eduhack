from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core import jobs
from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user, get_owned
from thinkfirst.modules.tutor.llm import service as llm
from thinkfirst.platform.identity.models import User

router = APIRouter(tags=["core"])


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/capabilities")
def capabilities():
    """What is real vs simulated in this environment (drives 'Demo data' / 'Simulated assessment' labels)."""
    s = get_settings()
    from thinkfirst.modules.diagnostic import service as diagnostic
    from thinkfirst.modules.rag import service as rag

    return {**llm.capabilities(), "rag": rag.stack(), "diagnostic": diagnostic.stack(), "demo_mode": s.demo_mode,
            "job_mode": s.job_mode, "storage": s.storage_backend, "paper_mode": False, "code_sandbox": False,
            "exams": False, "planner": "review dates only", "notifications": False,
            "accessibility_module": s.enable_accessibility_module}


@router.get("/demo/course-file")
def demo_course_file(user: User = Depends(current_user)):
    """C01 'Use the demo course file' (Demo data). Uploaded through the normal path afterwards."""
    from fastapi.responses import Response

    from thinkfirst.core.errors import NotFound
    from thinkfirst.fixtures import DEMO_COURSE_FILENAME, demo_course_pdf

    if not get_settings().demo_mode:
        raise NotFound()
    return Response(demo_course_pdf(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{DEMO_COURSE_FILENAME}"'})


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return jobs.job_public(get_owned(db, jobs.Job, job_id, user.id))


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Retry the SAME job (reconcile, never restart with a new random job)."""
    job = get_owned(db, jobs.Job, job_id, user.id)
    return jobs.job_public(jobs.retry(db, job))
