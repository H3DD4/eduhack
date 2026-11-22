"""FastAPI router for the Tutor module. Mount it in any app:

    from tutor.api.router import build_router, install_error_handler
    app.include_router(build_router(get_service, current_owner_id), prefix="/api")
    install_error_handler(app)

`current_owner_id` is a FastAPI dependency returning the signed-in user's id (ThinkFirst: current_user().id).
Errors use ThinkFirst's shape: {"error": {"code", "message"}}.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..service import TutorError, TutorService


class TrackIn(BaseModel):
    valley: Literal["revision", "skills"]
    title: str = Field(min_length=1, max_length=160)
    subject: str = ""
    goal: str = ""
    exam_date: str | None = None
    chapters: list[str] = Field(default_factory=list)
    allow_web: bool = True
    language: str = "fr"


class TrackPatch(BaseModel):
    title: str | None = None
    subject: str | None = None
    goal: str | None = None
    exam_date: str | None = None
    chapters: list[str] | None = None
    allow_web: bool | None = None


class LevelIn(BaseModel):
    level: Literal["beginner", "intermediate", "advanced"]
    per_chapter: dict[str, Literal["beginner", "intermediate", "advanced"]] = Field(default_factory=dict)
    skip_probe: bool = False


class ProbeAnswerIn(BaseModel):
    item_id: str
    choice: int | list[int]
    ms: int | None = None


class AttemptIn(BaseModel):
    answer: Any = None
    ms: int | None = None
    help_level: int = Field(0, ge=0, le=4)


class HelpIn(BaseModel):
    level: int = Field(1, ge=1, le=4)


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    mode: Literal["study", "practice"] = "study"
    item_id: str | None = None


class MockSubmitIn(BaseModel):
    answers: dict[str, Any]
    elapsed_s: int | None = None


def install_error_handler(app) -> None:
    async def _handler(_, exc: TutorError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})

    app.add_exception_handler(TutorError, _handler)


def build_router(get_service: Callable[[], TutorService], current_owner_id: Callable[..., str], *,
                 prefix: str = "/tutor") -> APIRouter:
    r = APIRouter(prefix=prefix, tags=["tutor"])
    Svc = Depends(get_service)
    Owner = Depends(current_owner_id)

    @r.get("/capabilities")
    def capabilities(svc: TutorService = Svc):
        return svc.capabilities()

    # -------------------------------------------------------------- tracks
    @r.post("/tracks", status_code=201)
    def create_track(body: TrackIn, svc: TutorService = Svc, owner: str = Owner):
        return svc.create_track(owner, **body.model_dump())

    @r.get("/tracks")
    def list_tracks(svc: TutorService = Svc, owner: str = Owner):
        return {"tracks": svc.list_tracks(owner)}

    @r.get("/tracks/{track_id}")
    def get_track(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.get_track(owner, track_id)

    @r.patch("/tracks/{track_id}")
    def patch_track(track_id: str, body: TrackPatch, svc: TutorService = Svc, owner: str = Owner):
        return svc.update_track(owner, track_id, **body.model_dump())

    @r.delete("/tracks/{track_id}", status_code=204)
    def delete_track(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        svc.delete_track(owner, track_id)

    @r.post("/tracks/{track_id}/documents", status_code=201)
    async def upload(track_id: str, files: list[UploadFile] = File(...), svc: TutorService = Svc, owner: str = Owner):
        out = []
        for f in files[:10]:
            data = await f.read()
            out.append(svc.add_document(owner, track_id, f.filename or "document", data))
        return {"documents": out}

    @r.delete("/tracks/{track_id}/documents/{doc_id}", status_code=204)
    def remove_document(track_id: str, doc_id: str, svc: TutorService = Svc, owner: str = Owner):
        svc.remove_document(owner, track_id, doc_id)

    # -------------------------------------------------------------- flows
    @r.post("/tracks/{track_id}/prepare", status_code=202)
    def prepare(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.start_flow(owner, track_id, "prepare")

    @r.post("/tracks/{track_id}/build", status_code=202)
    def build(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.start_flow(owner, track_id, "build")

    @r.get("/runs/{run_id}")
    def get_run(run_id: str, svc: TutorService = Svc, owner: str = Owner):
        run = svc.get_run(owner, run_id)
        return {k: v for k, v in run.items() if k != "state"}

    @r.post("/runs/{run_id}/resume", status_code=202)
    def resume(run_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.resume_run(owner, run_id)

    # -------------------------------------------------------------- level check
    @r.post("/tracks/{track_id}/level")
    def declare(track_id: str, body: LevelIn, svc: TutorService = Svc, owner: str = Owner):
        return svc.declare_level(owner, track_id, body.level, body.per_chapter, body.skip_probe)

    @r.post("/tracks/{track_id}/probe/answer")
    def probe_answer(track_id: str, body: ProbeAnswerIn, svc: TutorService = Svc, owner: str = Owner):
        return svc.probe_answer(owner, track_id, body.item_id, body.choice, body.ms)

    @r.post("/tracks/{track_id}/probe/finish")
    def probe_finish(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.probe_finish(owner, track_id)

    # -------------------------------------------------------------- material
    @r.get("/tracks/{track_id}/plan")
    def get_plan(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.plan(owner, track_id) or {"entries": [], "priorities": []}

    @r.get("/tracks/{track_id}/artifacts")
    def list_artifacts(track_id: str, type: str | None = Query(None), svc: TutorService = Svc, owner: str = Owner):
        return {"artifacts": svc.artifacts(owner, track_id, type)}

    @r.get("/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.artifact(owner, artifact_id)

    @r.post("/artifacts/{artifact_id}/regenerate")
    def regenerate(artifact_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.regenerate(owner, artifact_id)

    @r.post("/tracks/{track_id}/mock-exams", status_code=201)
    def new_mock(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.new_mock_exam(owner, track_id)

    @r.post("/mock-exams/{artifact_id}/submit")
    def submit_mock(artifact_id: str, body: MockSubmitIn, svc: TutorService = Svc, owner: str = Owner):
        return svc.submit_mock(owner, artifact_id, body.answers, body.elapsed_s)

    # -------------------------------------------------------------- practice
    @r.post("/tracks/{track_id}/items/{item_id}/attempt")
    def attempt(track_id: str, item_id: str, body: AttemptIn, svc: TutorService = Svc, owner: str = Owner):
        return svc.attempt(owner, track_id, item_id, body.answer, ms=body.ms, help_level=body.help_level)

    @r.post("/tracks/{track_id}/items/{item_id}/help")
    def help_(track_id: str, item_id: str, body: HelpIn, svc: TutorService = Svc, owner: str = Owner):
        return svc.help(owner, track_id, item_id, body.level)

    @r.post("/tracks/{track_id}/ask")
    def ask(track_id: str, body: AskIn, svc: TutorService = Svc, owner: str = Owner):
        return svc.ask(owner, track_id, body.question, mode=body.mode, item_id=body.item_id)

    # -------------------------------------------------------------- Valley 2
    @r.get("/tracks/{track_id}/tutorial")
    def tutorial(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.tutorial(owner, track_id)

    @r.get("/tracks/{track_id}/lessons/{slug}")
    def lesson(track_id: str, slug: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.lesson(owner, track_id, slug)

    @r.post("/tracks/{track_id}/lessons/{slug}/complete")
    def complete(track_id: str, slug: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.complete_page(owner, track_id, slug)

    # -------------------------------------------------------------- report
    @r.get("/tracks/{track_id}/report")
    def report(track_id: str, svc: TutorService = Svc, owner: str = Owner):
        return svc.report(owner, track_id)

    return r
