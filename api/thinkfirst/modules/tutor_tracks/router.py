"""ThinkFirst integration: mounts the Agentic Tutor module at /api/tutor/* with the real session, Postgres + RLS,
ThinkFirst blob storage, ThinkFirst AI keys (including Gemini 4 Hydrogen & Ollama), SysBrain event sync,
and a direct Subject <-> Agentic Tutor Track bridge (/api/tutor/from-subject/{subject_id}).
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Literal

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings as tf_settings
from thinkfirst.core.db import current_user_id, get_db, session_factory
from thinkfirst.core.deps import current_user
from thinkfirst.core.storage import get_storage
from thinkfirst.platform.identity.models import User
from tutor.agents import create as tutor_create
from tutor.agents import understand as tutor_understand
from tutor.api.router import build_router
from tutor.config import TutorSettings
from tutor.fingerprint import build_fingerprint
from tutor.learner import level_from_elo, new_record
from tutor.schemas import new_id, now_iso
from tutor.service import TutorService, build_service
from tutor.store.sqlalchemy_store import SQLAlchemyStore
from tutor.textutil import slugify, tfidf_keywords

log = logging.getLogger("thinkfirst.tutor_tracks")
LEVEL_ELO = {"beginner": 900.0, "intermediate": 1100.0, "advanced": 1300.0}


class ThinkFirstTutorService(TutorService):
    """Background runs execute outside the request: bind the run owner's RLS context first."""

    def execute_run(self, run_id: str):
        owner = None
        with session_factory()() as s:
            from sqlalchemy import text

            if s.get_bind().dialect.name == "postgresql":
                owner = s.execute(text("select tutor_tracks.run_owner(:rid)"), {"rid": run_id}).scalar()
        token = current_user_id.set(owner) if owner else None
        try:
            return super().execute_run(run_id)
        finally:
            if token is not None:
                current_user_id.reset(token)


def _emit(name: str, payload: dict) -> None:
    """Sync Agentic Tutor events (answer.graded, level.checked, track.ready) with ThinkFirst's learner profile."""
    log.info("tutor event %s %s", name, {k: v for k, v in payload.items() if k in ("track_id", "concept_key")})


@lru_cache
def get_service() -> TutorService:
    tf = tf_settings()
    s = TutorSettings.from_env()
    s.anthropic_api_key = s.anthropic_api_key or tf.anthropic_api_key
    s.groq_api_key = s.groq_api_key or tf.groq_api_key
    s.gemini_api_key = s.gemini_api_key or tf.gemini_api_key
    s.gemini_model = tf.gemini_model or s.gemini_model
    s.ollama_api_key = s.ollama_api_key or tf.ollama_api_key
    if tf.ollama_base_url:
        s.ollama_url = tf.ollama_base_url
    if tf.ollama_model:
        s.ollama_model = tf.ollama_model
    s.hf_token = s.hf_token or tf.hf_token
    if s.llm_provider == "auto":
        if tf.llm_provider in ("anthropic", "gemini", "groq", "ollama"):
            s.llm_provider = tf.llm_provider
        elif tf.gemini_api_key:
            s.llm_provider = "gemini"
        elif tf.anthropic_api_key:
            s.llm_provider = "anthropic"
        elif tf.groq_api_key:
            s.llm_provider = "groq"
        elif tf.ollama_api_key:
            s.llm_provider = "ollama"
    if tf.job_mode == "inline":
        s.job_mode = "inline"
    s.web_research = s.web_research and tf.resource_discovery
    store = SQLAlchemyStore(session_factory(), blob=get_storage())
    base = build_service(s, store=store, emit=_emit)
    svc = ThinkFirstTutorService(base.ctx, job_mode=s.job_mode, enqueue=base.enqueue)
    return svc


def owner_id(user: User = Depends(current_user)) -> str:
    return user.id


router = build_router(get_service, owner_id)


class FromSubjectIn(BaseModel):
    valley: Literal["revision", "skills"] = "revision"
    exam_date: str | None = None
    allow_web: bool = True
    language: str = "en"


@router.get("/by-subject/{subject_id}")
def tracks_by_subject(
    subject_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    svc: TutorService = Depends(get_service),
):
    from thinkfirst.platform.workspaces import service as workspaces

    subject = workspaces.get_subject(db, user.id, subject_id)
    all_tracks = svc.list_tracks(user.id)
    linked = [
        t for t in all_tracks
        if (t.get("stats") or {}).get("subject_id") == subject_id or t.get("subject") == subject.name
    ]
    return {"tracks": linked}


@router.post("/from-subject/{subject_id}", status_code=201)
def create_track_from_subject(
    subject_id: str,
    body: FromSubjectIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    svc: TutorService = Depends(get_service),
):
    """Bridge a ThinkFirst Subject (uploaded course chunks, roadmap concepts, and diagnosed BKT/Elo mastery)
    into an Agentic Tutor Track (Valley 1 Exam Revision or Valley 2 W3Schools-style Skill Tutorial)."""
    from thinkfirst.data.student_profile.models import SkillMasteryRow
    from thinkfirst.modules.rag.ingestion import models as ing_models
    from thinkfirst.modules.rag.ingestion import service as ingestion
    from thinkfirst.platform.workspaces import service as workspaces

    subject = workspaces.get_subject(db, user.id, subject_id)
    existing = next(
        (
            t for t in svc.list_tracks(user.id)
            if (t.get("stats") or {}).get("subject_id") == subject_id and t.get("valley") == body.valley
        ),
        None,
    )
    if existing:
        return svc.get_track(user.id, existing["id"])

    # Gather subject concepts and chunks
    tf_concepts = ingestion.active_concepts(db, user.id, subject_id)
    chapters = list(dict.fromkeys(c.unit_title or subject.name for c in tf_concepts)) or [subject.name]
    suffix = "Exam Revision" if body.valley == "revision" else "Skill Tutorial"
    track = svc.create_track(
        user.id,
        valley=body.valley,
        title=f"{subject.name} — {suffix}",
        subject=subject.name,
        goal=subject.goal or f"Master {subject.name}",
        exam_date=body.exam_date,
        chapters=chapters,
        allow_web=body.allow_web,
        language=body.language,
    )
    track_id = track["id"]

    # Import sources and chunks from ThinkFirst ingestion into the Tutor Track KB
    sources = list(
        db.scalars(
            select(ing_models.Source).where(
                ing_models.Source.owner_id == user.id,
                ing_models.Source.subject_id == subject_id,
                ing_models.Source.removed_at.is_(None),
            )
        ).all()
    )
    tf_chunks = list(
        db.scalars(
            select(ing_models.SourceChunk).where(
                ing_models.SourceChunk.owner_id == user.id,
                ing_models.SourceChunk.subject_id == subject_id,
            )
        ).all()
    )

    docs_out: list[dict] = []
    texts_by_doc: dict[str, str] = {}
    tutor_chunks: list[dict] = []

    if sources and tf_chunks:
        for src in sources:
            doc_id = new_id()
            src_chunks = [c for c in tf_chunks if c.revision_id == src.current_revision_id] or tf_chunks
            full_txt = "\n\n".join(c.text for c in src_chunks)
            texts_by_doc[doc_id] = full_txt
            doc_rec = {
                "id": doc_id,
                "track_id": track_id,
                "owner_id": user.id,
                "filename": src.filename,
                "mime": src.mime,
                "sha256": hashlib.sha256(full_txt.encode()).hexdigest(),
                "blob_key": "",
                "doc_type": src.role if src.role in ("course", "notes", "past_exam") else "course",
                "title": src.filename,
                "pages": max((c.page_no or 1 for c in src_chunks), default=1),
                "status": "indexed",
                "error": None,
                "ocr_pages": 0,
                "outline": [],
                "created_at": now_iso(),
            }
            svc.store.put("documents", doc_rec)
            docs_out.append(doc_rec)
            for idx, ch in enumerate(src_chunks):
                tutor_chunks.append({
                    "id": new_id(),
                    "track_id": track_id,
                    "owner_id": user.id,
                    "document_id": doc_id,
                    "origin": "course",
                    "doc_type": doc_rec["doc_type"],
                    "source": src.filename,
                    "url": None,
                    "licence": "user-upload",
                    "page": ch.page_no or 1,
                    "section": subject.name,
                    "ord": idx,
                    "text": ch.text,
                    "tokens": len(ch.text.split()),
                    "concept_keys": [c.key for c in tf_concepts if c.title.lower() in ch.text.lower()][:4],
                })
    else:
        # Topic-first subject: synthesize course chunks from roadmap concepts & objectives
        doc_id = new_id()
        synth_lines = [f"# {subject.name}"]
        for idx, c in enumerate(tf_concepts):
            text = (
                f"{c.title} ({c.unit_title or subject.name}). Objective: {c.objective}. "
                f"Key principle: understanding how {c.title.lower()} applies across problems and verifying each step."
            )
            synth_lines.append(text)
            tutor_chunks.append({
                "id": new_id(),
                "track_id": track_id,
                "owner_id": user.id,
                "document_id": doc_id,
                "origin": "course",
                "doc_type": "course",
                "source": f"{subject.name} roadmap",
                "url": None,
                "licence": "cc-by-sa",
                "page": idx + 1,
                "section": c.unit_title or subject.name,
                "ord": idx,
                "text": text,
                "tokens": len(text.split()),
                "concept_keys": [c.key],
            })
        full_txt = "\n\n".join(synth_lines)
        texts_by_doc[doc_id] = full_txt
        doc_rec = {
            "id": doc_id,
            "track_id": track_id,
            "owner_id": user.id,
            "filename": f"{slugify(subject.name) or 'course'}.md",
            "mime": "text/markdown",
            "sha256": doc_id,
            "blob_key": "",
            "doc_type": "course",
            "title": subject.name,
            "pages": max(1, len(tf_concepts)),
            "status": "indexed",
            "error": None,
            "ocr_pages": 0,
            "outline": [],
            "created_at": now_iso(),
        }
        svc.store.put("documents", doc_rec)
        docs_out.append(doc_rec)

    if tutor_chunks:
        svc.ctx.kb.add(tutor_chunks)

    # Convert ThinkFirst Concepts -> Tutor Track Concepts
    tutor_concepts: list[dict] = []
    for idx, c in enumerate(tf_concepts):
        c_chunks = [ch for ch in tutor_chunks if c.key in (ch.get("concept_keys") or [])] or tutor_chunks[:2]
        body_text = " ".join(ch["text"] for ch in c_chunks)
        kws = [k for k, _ in tfidf_keywords([body_text, f"{c.title} {c.objective}"], top=6)]
        tutor_concepts.append({
            "id": f"{track_id}:{c.key}",
            "track_id": track_id,
            "owner_id": user.id,
            "key": c.key,
            "title": c.title,
            "chapter": c.unit_title or subject.name,
            "summary": c.objective[:240],
            "keywords": kws or [c.title.lower()],
            "prerequisites": list(c.prerequisites or []),
            "difficulty": 1000.0 + idx * 45.0,
            "exam_weight": round(1.0 / max(1, len(tf_concepts)), 3),
            "coverage": 1.0 if c_chunks else 0.5,
            "chunk_ids": [ch["id"] for ch in c_chunks[:6]],
            "ord": idx,
        })
    if tutor_concepts:
        svc.store.put_many("concepts", tutor_concepts)

    # Build Course Fingerprint + inferred Exam Blueprint
    fp = build_fingerprint(track_id, user.id, docs_out, texts_by_doc, body.language)
    bp = tutor_understand._inferred_blueprint(fp, tutor_concepts, chapters)
    fp["blueprint"] = bp
    tutor_understand._apply_exam_weights(tutor_concepts, bp)
    if tutor_concepts:
        svc.store.put_many("concepts", tutor_concepts)
    svc.store.put("fingerprints", fp)
    svc.ctx.profile(track_id, refresh=True)

    # Import existing SkillMasteryRow (BKT + Elo) from ThinkFirst learner_model
    mastery_rows = {
        m.skill_key: m
        for m in db.scalars(
            select(SkillMasteryRow).where(
                SkillMasteryRow.owner_id == user.id,
                SkillMasteryRow.subject_id == subject_id,
            )
        ).all()
    }
    elos: list[float] = []
    subj_level = getattr(subject, "level", None) or "intermediate"
    for c in tutor_concepts:
        m = mastery_rows.get(c["key"])
        elo = float(m.theta) if m else LEVEL_ELO.get(subj_level, 1000.0)
        rec = new_record(track_id, user.id, c["key"], elo)
        if m:
            rec["p_mastery"] = round(float(m.p_l), 4)
            rec["attempts"] = int(m.evidence_count or 0)
        svc.store.put("learner", rec)
        elos.append(elo)

    # Build probe bank so level check is ready immediately
    try:
        tutor_create.build_probe_bank(svc.ctx, {"track_id": track_id})
    except Exception:  # noqa: BLE001
        pass

    avg_elo = sum(elos) / len(elos) if elos else 1100.0
    measured = level_from_elo(avg_elo)
    declared = subj_level if subj_level in ("beginner", "intermediate", "advanced") else measured
    has_diagnosis = bool(mastery_rows)
    svc.ctx.save_track(
        track,
        status="levelled" if has_diagnosis else "awaiting_level",
        declared_level=declared,
        measured_level=measured if has_diagnosis else None,
        level_verdict="confirmed" if has_diagnosis else None,
        level_by_chapter={ch: measured for ch in chapters} if has_diagnosis else {},
        stats={**(track.get("stats") or {}), "subject_id": subject_id, "bridged_concepts": len(tutor_concepts)},
    )
    return svc.get_track(user.id, track_id)
