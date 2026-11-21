"""Question/hint quality aggregates: adaptation.item_stats, adaptation.hint_stats (counts only, no student ids).

Revision ID: 0006_item_quality
Revises: 0005_engine
"""

import thinkfirst.models  # noqa: F401
from alembic import op
from thinkfirst.modules.adaptation.models import HintStat, ItemStat

revision = "0006_item_quality"
down_revision = "0005_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    ItemStat.__table__.create(bind, checkfirst=True)
    HintStat.__table__.create(bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
                GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA adaptation TO thinkfirst_app;
            END IF; END $$""")


def downgrade() -> None:
    op.drop_table("hint_stats", schema="adaptation")
    op.drop_table("item_stats", schema="adaptation")
