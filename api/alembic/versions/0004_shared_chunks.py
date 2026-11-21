"""Shared open-library vector index (public, openly licensed content only; NOT student data, so no RLS).

Revision ID: 0004_shared_chunks
Revises: 0003_memory
"""

import thinkfirst.models  # noqa: F401
from alembic import op
from thinkfirst.modules.rag.library.models import SharedChunk

revision = "0004_shared_chunks"
down_revision = "0003_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SharedChunk.__table__.create(bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA knowledge_library TO thinkfirst_app;
            END IF; END $$""")


def downgrade() -> None:
    op.drop_table("shared_chunks", schema="knowledge_library")
