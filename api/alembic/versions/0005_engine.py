"""Learner engine: event fields on memory.learning_events + shared adaptation.bandit_stats (aggregates only).

Revision ID: 0005_engine
Revises: 0004_shared_chunks
"""

import sqlalchemy as sa

import thinkfirst.models  # noqa: F401
from alembic import op
from thinkfirst.modules.adaptation.models import BanditStat

revision = "0005_engine"
down_revision = "0004_shared_chunks"
branch_labels = None
depends_on = None

COLS = [("outcome", sa.String(16)), ("assistance", sa.String(24)), ("evidence", sa.String(24)), ("is_fresh", sa.Boolean()),
        ("misconception_id", sa.String(64)), ("misconception_conf", sa.Float()), ("recommended_action", sa.String(32)),
        ("context_key", sa.String(96)), ("propensity", sa.Float()), ("reward", sa.Float())]


def upgrade() -> None:
    bind = op.get_bind()
    have = {c["name"] for c in sa.inspect(bind).get_columns("learning_events", schema="memory")}
    for name, typ in COLS:
        if name not in have:
            op.add_column("learning_events", sa.Column(name, typ, nullable=True), schema="memory")
    if bind.dialect.name == "postgresql":
        op.execute('CREATE SCHEMA IF NOT EXISTS "adaptation"')
    BanditStat.__table__.create(bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
                GRANT USAGE ON SCHEMA adaptation TO thinkfirst_app;
                GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA adaptation TO thinkfirst_app;
            END IF; END $$""")


def downgrade() -> None:
    op.drop_table("bandit_stats", schema="adaptation")
