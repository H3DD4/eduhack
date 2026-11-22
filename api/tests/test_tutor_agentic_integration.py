"""End-to-end integration tests for the merged Agentic Tutor system (`tutor` + `thinkfirst.modules.tutor.tracks`
+ enhanced `thinkfirst.modules.tutor.packs`)."""

from __future__ import annotations

import pytest

from thinkfirst.core import db as dbmod
from thinkfirst.core.storage import LocalStorage, set_storage
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.modules.tutor import packs
from thinkfirst.modules.tutor.tracks import router as tutor_tracks_router
from thinkfirst.platform.identity import service as identity
from thinkfirst.platform.workspaces import service as workspaces
from tutor.config import TutorSettings
from tutor.service import build_service
from tutor.store.sqlalchemy_store import SQLAlchemyStore


@pytest.fixture()
def db_session(tmp_path):
    engine = dbmod.configure(f"sqlite:///{tmp_path / 'test.db'}")
    dbmod.create_all_for_tests(engine)
    set_storage(LocalStorage(str(tmp_path / "storage")))
    with dbmod.session_factory()() as s:
        yield s
    engine.dispose()


def _ready_subject(db, owner_id: str, name: str = "Algebra 101"):
    sub = workspaces.create_subject(db, owner_id, name, origin="guided_topic", goal="exam")
    rev = ingestion.create_guided_scope(db, owner_id, sub.id, "algebra")
    ingestion.confirm_scope(db, owner_id, sub.id, rev.id, edits=[])
    db.commit()
    return sub


def test_enhanced_concept_pack_computes_course_fingerprint_and_likeness(db_session, monkeypatch):
    from thinkfirst.config import get_settings

    db = db_session
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "demo")

    user = identity.register(db, "student@example.com", "password123", "Student")
    subj = _ready_subject(db, user.id, "Analyse — Dérivation")

    concepts = ingestion.active_concepts(db, user.id, subj.id)
    assert concepts
    target = concepts[0]

    pack = packs.ensure_pack(db, user.id, subj.id, target.id)
    db.refresh(pack)

    assert pack.status == "ready"
    assert pack.content["lesson"]["summary"]
    assert pack.content["lesson"]["likeness"] >= 0.5
    assert "course_fingerprint" in pack.content
    assert len(pack.content["practice"]) >= 2
    first_item = pack.content["practice"][0]
    assert first_item["verified"] is True
    assert first_item["likeness"] >= 0.5
    assert len(first_item["hints"]) >= 4
    assert pack.content["transfer"] is not None


def test_subject_to_agentic_tutor_bridge_and_two_valleys(db_session, tmp_path):
    db = db_session
    user = identity.register(db, "student@example.com", "password123", "Student")
    subj = _ready_subject(db, user.id, "Algèbre et Dérivation")

    store = SQLAlchemyStore(dbmod.session_factory(), blob=LocalStorage(str(tmp_path / "tutor-blobs")))
    settings = TutorSettings(
        store_backend="sqlalchemy",
        llm_provider="mock",
        embedder="hashing",
        reranker="none",
        web_research=False,
        job_mode="inline",
        blob_dir=str(tmp_path / "tutor-blobs"),
    )
    svc = build_service(settings, store=store)

    # 1. Bridge ThinkFirst Subject -> Valley 1 (Exam Revision Track)
    body_rev = tutor_tracks_router.FromSubjectIn(valley="revision", language="fr", allow_web=False)
    track_rev = tutor_tracks_router.create_track_from_subject(subj.id, body_rev, user=user, db=db, svc=svc)
    assert track_rev["valley"] == "revision"
    assert len(track_rev["concepts"]) >= 3
    assert track_rev["fingerprint"] is not None

    # Level check (skip probe to confirm declared level) + Build Valley 1 Revision Pack
    lvl = svc.declare_level(user.id, track_rev["id"], "intermediate", skip_probe=True)
    assert lvl["result"]["measured"] == "intermediate"
    run = svc.start_flow(user.id, track_rev["id"], "build")
    assert run["status"] == "succeeded"

    arts = svc.artifacts(user.id, track_rev["id"])
    art_types = {a["type"] for a in arts}
    assert {"resume", "fiches", "qcm", "quiz", "exercises", "mock_exam"} <= art_types

    # Practice attempt + help ladder policy gate
    qcm_summary = next(a for a in arts if a["type"] == "qcm")
    qcm_art = svc.artifact(user.id, qcm_summary["id"])
    item = qcm_art["content"]["items"][0]
    assert "correct" not in item["options"][0]  # hidden before attempt

    # Level 1 nudge is allowed before attempt
    h1 = svc.help(user.id, track_rev["id"], item["id"], 1)
    assert h1["level"] == 1 and h1["message"]

    # Attempt item -> updates BKT & Elo mastery
    att = svc.attempt(user.id, track_rev["id"], item["id"], 0, ms=4500, help_level=1)
    assert "mastery" in att
    rep = svc.report(user.id, track_rev["id"])
    assert rep["track_id"] == track_rev["id"]

    # 2. Bridge ThinkFirst Subject -> Valley 2 (Progressive Skill Tutorial Track)
    body_sk = tutor_tracks_router.FromSubjectIn(valley="skills", language="fr", allow_web=False)
    track_sk = tutor_tracks_router.create_track_from_subject(subj.id, body_sk, user=user, db=db, svc=svc)
    assert track_sk["valley"] == "skills"
    svc.declare_level(user.id, track_sk["id"], "beginner", skip_probe=True)
    run_sk = svc.start_flow(user.id, track_sk["id"], "build")
    assert run_sk["status"] == "succeeded"

    tut = svc.tutorial(user.id, track_sk["id"])
    pages = [n for n in tut["nodes"] if n["kind"] == "page"]
    assert pages and pages[0]["status"] in ("open", "skippable")
    lesson = svc.lesson(user.id, track_sk["id"], pages[0]["slug"])
    assert lesson["artifact"]["type"] == "lesson"
    assert len(lesson["artifact"]["content"]["sections"]) >= 3


def test_track_without_uploaded_documents_and_http_404_llm_fallback(db_session, tmp_path):
    """Uploading a document is optional in both Valley 1 (revision) and Valley 2 (skills),
    and an HTTP_404 from an upstream LLM provider during ingest falls back cleanly without failing the run."""
    from tutor.llm.gateway import LLM, LLMError

    db = db_session
    user = identity.register(db, "nodocs@example.com", "password123", "NoDocs")

    store = SQLAlchemyStore(dbmod.session_factory(), blob=LocalStorage(str(tmp_path / "tutor-blobs-nodocs")))
    settings = TutorSettings(
        store_backend="sqlalchemy",
        llm_provider="mock",
        embedder="hashing",
        reranker="none",
        web_research=False,
        job_mode="inline",
        blob_dir=str(tmp_path / "tutor-blobs-nodocs"),
    )
    svc = build_service(settings, store=store)

    # Simulate an upstream LLM provider that raises HTTP_404 on every call
    class Broken404Provider:
        name = "broken404"

        def complete(self, system: str, user: str, *, tier: str, max_tokens: int):
            raise LLMError("HTTP_404")

    svc.ctx.llm = LLM(Broken404Provider(), mock=svc.ctx.llm.mock, fallback_to_mock=True)

    # Create a Valley 1 Exam Revision track with ZERO uploaded documents
    track = svc.create_track(
        user.id,
        valley="revision",
        title="Maths — Dérivation et Variations",
        subject="Mathématiques",
        goal="Réussir le DS sur la dérivation",
        chapters=["Nombre dérivé et tangente", "Opérations sur les dérivées", "Variations et extremums"],
        allow_web=False,
        language="fr",
    )
    run_prep = svc.start_flow(user.id, track["id"], "prepare")
    assert run_prep["status"] == "succeeded", run_prep
    t_after = svc.get_track(user.id, track["id"])
    assert t_after["status"] == "awaiting_level"
    assert len(t_after["documents"]) == 1
    assert len(t_after["concepts"]) >= 2

    svc.declare_level(user.id, track["id"], "intermediate", skip_probe=True)
    run_build = svc.start_flow(user.id, track["id"], "build")
    assert run_build["status"] == "succeeded", run_build
    arts = svc.artifacts(user.id, track["id"])
    assert {"resume", "fiches", "qcm", "quiz", "exercises"} <= {a["type"] for a in arts}

