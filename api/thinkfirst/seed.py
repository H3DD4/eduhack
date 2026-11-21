"""Seed the labeled demo account.

    python -m thinkfirst.seed                 # demo account, no subject (demo starts at G01 empty -> C01)
    python -m thinkfirst.seed --reset         # wipe the demo account's data first
    python -m thinkfirst.seed --with-subject  # also create the ready MATH 101 subject (jump to W01)
"""

from __future__ import annotations

import argparse

from sqlalchemy import delete, inspect, select

from thinkfirst.core.db import Base, configure, get_engine, session_factory
from thinkfirst.fixtures import DEMO_COURSE_FILENAME, demo_course_pdf
from thinkfirst.platform.identity.models import AuthSession, User
from thinkfirst.platform.identity.service import hash_password

DEMO_EMAIL = "demo@thinkfirst.local"
DEMO_PASSWORD = "demo-password"


def ensure_schema() -> None:
    import thinkfirst.models  # noqa: F401

    engine = get_engine()
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    elif not inspect(engine).has_table("users", schema="identity"):
        raise SystemExit("Database schema missing: run `python -m alembic upgrade head` first.")


def reset_user(db, user_id: str) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        if "owner_id" in table.c:
            db.execute(delete(table).where(table.c.owner_id == user_id))
        elif "student_id" in table.c and table.name != "access_audit_log":  # audit log is append-only
            db.execute(delete(table).where(table.c.student_id == user_id))
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def seed(reset: bool = False, with_subject: bool = False) -> str:
    configure()
    ensure_schema()
    with session_factory()() as db:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), display_name="Demo student",
                        is_demo=True)
            db.add(user)
        user.is_demo, user.setup_complete, user.goal = True, True, "understand"
        db.commit()
        db.info["user_id"] = user.id  # later transactions run inside the demo user's RLS context
        if reset:
            reset_user(db, user.id)
            db.commit()
        if with_subject:
            from thinkfirst.modules.rag.ingestion import service as ingestion
            from thinkfirst.platform.workspaces import service as workspaces

            subject = workspaces.create_subject(db, user.id, "MATH 101 — Algebra Foundations (Demo data)")
            ingestion.add_source(db, user.id, subject.id, DEMO_COURSE_FILENAME, "application/pdf", demo_course_pdf(),
                                 "course", True)
            rev = ingestion.proposed_revision(db, user.id, subject.id)
            if rev is None:
                raise SystemExit("Demo extraction did not produce a scope (is JOB_MODE=inline?).")
            ingestion.confirm_scope(db, user.id, subject.id, rev.id, [])
        db.commit()
        return user.id


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--with-subject", action="store_true")
    args = ap.parse_args()
    uid = seed(args.reset, args.with_subject)
    print(f"Demo account ready: {DEMO_EMAIL} / {DEMO_PASSWORD} (id {uid})")
