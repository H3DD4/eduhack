"""Planner calendar: workspaces.deadlines (exams, certificates, assignments, goals), private with RLS.

Revision ID: 0010_planner_deadlines
Revises: 0009_merge_tutor_tracks
"""

import sqlalchemy as sa

import thinkfirst.models  # noqa: F401
from alembic import op
from thinkfirst.platform.workspaces.models import Deadline

revision = "0010_planner_deadlines"
down_revision = "0009_merge_tutor_tracks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Deadline.__table__.create(bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    exists = bind.execute(sa.text("select 1 from pg_policies where schemaname='workspaces' and tablename='deadlines'")).first()
    if not exists:
        op.execute("ALTER TABLE workspaces.deadlines ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE workspaces.deadlines FORCE ROW LEVEL SECURITY")
        op.execute("CREATE POLICY owner_isolation ON workspaces.deadlines "
                   "USING (owner_id = current_setting('app.user_id', true)) "
                   "WITH CHECK (owner_id = current_setting('app.user_id', true))")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON workspaces.deadlines TO thinkfirst_app;
        END IF; END $$""")


def downgrade() -> None:
    op.drop_table("deadlines", schema="workspaces")
