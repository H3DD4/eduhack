"""core.unfinished_jobs(): (id, attempts) of queued/running jobs, so the worker can resume them after a crash.
Content-free SECURITY DEFINER function, same pattern as core.job_owner.

Revision ID: 0012_unfinished_jobs
Revises: 0011_invalidate_wrong_tests
"""

from alembic import op

revision = "0012_unfinished_jobs"
down_revision = "0011_invalidate_wrong_tests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""CREATE OR REPLACE FUNCTION core.unfinished_jobs() RETURNS TABLE(id text, attempts int)
                  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core AS
                  $$ SELECT id::text, attempts FROM core.jobs WHERE status IN ('queued', 'running') $$""")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
            GRANT EXECUTE ON FUNCTION core.unfinished_jobs() TO thinkfirst_app;
        END IF; END $$""")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS core.unfinished_jobs()")
