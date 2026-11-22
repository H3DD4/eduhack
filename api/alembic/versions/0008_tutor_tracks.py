"""Tutor module tables (schema tutor_tracks) with pgvector and owner row-level security.

Revision ID: 0008_tutor_tracks
Revises: 0007_merge_heads
"""

import sqlalchemy as sa

from alembic import op
from tutor.store.base import COLLECTIONS
from tutor.store.sqlalchemy_store import SCHEMA, metadata

revision = "0008_tutor_tracks"
down_revision = "0007_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name == "postgresql"
    if pg:
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    metadata.create_all(bind, checkfirst=True)
    if not pg:
        return
    for t in COLLECTIONS:
        exists = bind.execute(sa.text("select 1 from pg_policies where schemaname=:s and tablename=:t"),
                              {"s": SCHEMA, "t": t}).first()
        if not exists:
            op.execute(f"ALTER TABLE {SCHEMA}.{t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {SCHEMA}.{t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY owner_isolation ON {SCHEMA}.{t} "
                       f"USING (owner_id = current_setting('app.user_id', true)) "
                       f"WITH CHECK (owner_id = current_setting('app.user_id', true))")
    op.execute(f"CREATE INDEX IF NOT EXISTS ix_tt_chunks_embedding ON {SCHEMA}.chunks "
               f"USING hnsw (embedding vector_cosine_ops)")
    # Background runs learn their owner (only) before switching into the owner's RLS context.
    op.execute(f"""CREATE OR REPLACE FUNCTION {SCHEMA}.run_owner(rid text) RETURNS text
                  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = {SCHEMA} AS
                  $$ SELECT owner_id FROM {SCHEMA}.runs WHERE id = rid $$""")
    op.execute(f"""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
            GRANT USAGE ON SCHEMA {SCHEMA} TO thinkfirst_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {SCHEMA} TO thinkfirst_app;
            GRANT EXECUTE ON FUNCTION {SCHEMA}.run_owner(text) TO thinkfirst_app;
        END IF; END $$""")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    else:
        metadata.drop_all(bind)
