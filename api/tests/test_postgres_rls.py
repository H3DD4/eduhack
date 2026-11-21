"""Row-level security on real Postgres (runs only when TEST_PG_APP_URL is set, e.g. against docker compose).

    TEST_PG_APP_URL=postgresql+psycopg://thinkfirst_app:thinkfirst_app_dev@localhost:5432/thinkfirst
Requires: `alembic upgrade head` and `python -m thinkfirst.seed --with-subject` already run.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

URL = os.environ.get("TEST_PG_APP_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_PG_APP_URL not set (Postgres RLS tests)")


@pytest.fixture(scope="module")
def engine():
    e = create_engine(URL)
    yield e
    e.dispose()


def _demo_id(conn) -> str:
    return conn.execute(text("select id from identity.users where email='demo@thinkfirst.local'")).scalar()


def test_app_role_is_not_superuser(engine):
    with engine.connect() as c:
        row = c.execute(text("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")).one()
        assert row == (False, False)


def test_rows_invisible_without_matching_owner_context(engine):
    with engine.begin() as c:
        demo = _demo_id(c)
        c.execute(text("select set_config('app.user_id', :u, true)"), {"u": demo})
        own = c.execute(text("select count(*) from workspaces.subjects")).scalar()
        assert own >= 1
    with engine.begin() as c:
        c.execute(text("select set_config('app.user_id', :u, true)"), {"u": str(uuid.uuid4())})
        assert c.execute(text("select count(*) from workspaces.subjects")).scalar() == 0
        assert c.execute(text("select count(*) from ingestion.source_pages")).scalar() == 0
        # even an explicit filter on the demo owner returns nothing
        assert c.execute(text("select count(*) from ingestion.concepts where owner_id = :d"), {"d": demo}).scalar() == 0
    with engine.begin() as c:  # no context at all
        assert c.execute(text("select count(*) from tutor.tasks")).scalar() == 0


def test_cannot_write_rows_for_another_owner(engine):
    with engine.connect() as c:
        tx = c.begin()
        c.execute(text("select set_config('app.user_id', :u, true)"), {"u": str(uuid.uuid4())})
        with pytest.raises(DBAPIError):  # RLS WITH CHECK violation
            c.execute(text("insert into workspaces.subjects (id, owner_id, name, origin, status, created_at) "
                           "values (:i, :o, 'x', 'upload', 'ready', now())"), {"i": str(uuid.uuid4()), "o": str(uuid.uuid4())})
        tx.rollback()


def test_audit_log_is_append_only(engine):
    with engine.connect() as c:
        tx = c.begin()
        with pytest.raises(DBAPIError):  # UPDATE privilege revoked from the app role (+ trigger)
            c.execute(text("update identity.access_audit_log set action = 'x'"))
        tx.rollback()
    with engine.connect() as c:
        tx = c.begin()
        with pytest.raises(DBAPIError):
            c.execute(text("delete from identity.access_audit_log"))
        tx.rollback()
