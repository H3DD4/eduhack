"""Concurrency & lock-safety tests for SQLite WAL, iterative inline jobs, deferred LLM logs, and 503 handler."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from thinkfirst.config import get_settings
from thinkfirst.core import db as dbmod
from thinkfirst.core import jobs
from thinkfirst.modules.tutor.llm import service as llm
from thinkfirst.modules.tutor.llm.models import LLMCallLog
from thinkfirst.platform.workspaces import service as workspaces
from thinkfirst.platform.workspaces.models import Subject


@pytest.fixture()
def sqlite_file_env(tmp_path):
    url = f"sqlite:///{tmp_path / 'concurrent.db'}"
    engine = dbmod.configure(url)
    dbmod.create_all_for_tests(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_sqlite_engine_uses_wal_and_busy_timeout(sqlite_file_env):
    with sqlite_file_env.connect() as conn:
        main_mode = str(conn.execute(text("PRAGMA journal_mode")).scalar()).lower()
        tutor_mode = str(conn.execute(text("PRAGMA tutor_tracks.journal_mode")).scalar()).lower()
        timeout = int(conn.execute(text("PRAGMA busy_timeout")).scalar() or 0)
    assert main_mode == "wal"
    assert tutor_mode == "wal"
    assert timeout >= 30000


def test_inline_chained_jobs_release_sqlite_write_lock_during_handler(sqlite_file_env):
    trace: list[str] = []
    job_type = "test.chain_concurrent"

    @jobs.job_handler(job_type)
    def _handler(db, job):
        step = job.payload["step"]
        trace.append(f"step{step}")
        if step == 1:
            # Independent request/writer must be able to commit while job 1 is mid-execution.
            with dbmod.session_factory()() as concurrent_db:
                concurrent_db.info["is_request_session"] = True
                workspaces.create_subject(concurrent_db, "u-other", "Concurrent Write")
                concurrent_db.commit()
            jobs.enqueue(db, job_type, job.owner_id, {"step": 2}, "test-chain-2")
        return {"step": step}

    try:
        with dbmod.session_factory()() as db:
            db.info["is_request_session"] = True
            workspaces.create_subject(db, "u-main", "Initial Before Job")
            j1 = jobs.enqueue(db, job_type, "u-main", {"step": 1}, "test-chain-1")
            db.commit()
            j1_id = j1.id

        with dbmod.session_factory()() as verify_db:
            names = set(verify_db.scalars(select(Subject.name)).all())
            statuses = dict(verify_db.execute(select(jobs.Job.idempotency_key, jobs.Job.status)).all())
        assert trace == ["step1", "step2"]
        assert {"Initial Before Job", "Concurrent Write"} <= names
        assert statuses["test-chain-1"] == jobs.SUCCEEDED
        assert statuses["test-chain-2"] == jobs.SUCCEEDED
        assert j1_id
    finally:
        jobs._registry.pop(job_type, None)


def test_llm_run_defers_call_logs_until_after_fallback(sqlite_file_env, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "auto")
    monkeypatch.setattr(s, "llm_fallback", True)
    monkeypatch.setattr(s, "ollama_api_key", None)
    monkeypatch.setattr(s, "anthropic_api_key", None)
    monkeypatch.setattr(s, "groq_api_key", "g-test")
    monkeypatch.setattr(s, "gemini_api_key", "gem-test")
    llm._cooldown_until.clear()
    llm._cache.clear()

    seen_new_logs_during_gemini: list[int] = []

    def fail_groq(template, user_text):
        raise llm._ProviderError("RATE_LIMITED")

    with dbmod.session_factory()() as db:
        def ok_gemini(template, user_text):
            # Neither session buffer nor DB table should hold a flushed failure log before Gemini returns.
            seen_new_logs_during_gemini.append(
                sum(1 for obj in db.new if isinstance(obj, LLMCallLog))
                + int(db.scalar(select(func.count()).select_from(LLMCallLog)) or 0)
            )
            return {"message": "ok", "citations": [], "on_topic": True}, 12, 8

        monkeypatch.setitem(llm._CALLERS, "groq", fail_groq)
        monkeypatch.setitem(llm._CALLERS, "gemini", ok_gemini)

        res = llm.run(db, "professor_scaffold", {"student_question": "q-lock"}, owner_id="u1", purpose="test_defer")
        assert res.status == "ok" and res.provider == "gemini"
        assert seen_new_logs_during_gemini == [0]

        logs = list(db.scalars(select(LLMCallLog).order_by(LLMCallLog.created_at)).all())
        assert [(row.provider, row.status) for row in logs] == [("groq", "error"), ("gemini", "ok")]

    llm._cooldown_until.clear()
    llm._cache.clear()


def test_db_locked_operational_error_returns_503(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'handler.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    dbmod.configure(url)
    coro = None
    try:
        from thinkfirst.main import create_app

        app = create_app()
        handler = app.exception_handlers[OperationalError]
        exc = OperationalError("INSERT INTO sessions ...", {}, Exception("database is locked"))
        coro = handler(None, exc)
        with pytest.raises(StopIteration) as done:
            coro.send(None)
        resp = done.value.value
        assert resp.status_code == 503
        assert b"DB_BUSY" in resp.body
    finally:
        if coro is not None:
            coro.close()
        dbmod.get_engine().dispose()
        get_settings.cache_clear()


def test_normalize_database_url():
    assert dbmod.normalize_database_url("postgres://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert dbmod.normalize_database_url("postgresql://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert dbmod.normalize_database_url("postgresql+psycopg://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert dbmod.normalize_database_url("sqlite:///./thinkfirst-dev.db") == "sqlite:///./thinkfirst-dev.db"
