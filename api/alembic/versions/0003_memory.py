"""memory.learning_events (Historique & mémoire) with RLS (idempotent on fresh databases).

Revision ID: 0003_memory
Revises: 0002_packs_resources
"""

import sqlalchemy as sa

import thinkfirst.models  # noqa: F401
from alembic import op
from thinkfirst.modules.memory.models import LearningEvent

revision = "0003_memory"
down_revision = "0002_packs_resources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('CREATE SCHEMA IF NOT EXISTS "memory"')
    LearningEvent.__table__.create(bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    if not bind.execute(sa.text("select 1 from pg_policies where schemaname='memory' and tablename='learning_events'")).first():
        op.execute("ALTER TABLE memory.learning_events ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE memory.learning_events FORCE ROW LEVEL SECURITY")
        op.execute("CREATE POLICY owner_isolation ON memory.learning_events USING (owner_id = current_setting('app.user_id', true)) "
                   "WITH CHECK (owner_id = current_setting('app.user_id', true))")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
            GRANT USAGE ON SCHEMA memory TO thinkfirst_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA memory TO thinkfirst_app;
        END IF; END $$""")


def downgrade() -> None:
    op.execute('DROP SCHEMA IF EXISTS "memory" CASCADE')
