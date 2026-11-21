"""Start wizard + placement test + level-adapted course summary.

  * workspaces.subjects.prior_knowledge         ("some" = test my level, "none" = start from scratch)
  * assessment.diagnostic_items.difficulty_label / cross_checked   (AI-written placement items)
  * tutor.course_summaries / tutor.course_summary_sections         (private, RLS)

Revision ID: 0008_learning_path
Revises: 0007_merge_heads
"""

import sqlalchemy as sa

import thinkfirst.models  # noqa: F401
from alembic import op
from thinkfirst.modules.tutor.models import CourseSummary, CourseSummarySection

revision = "0008_learning_path"
down_revision = "0007_merge_heads"
branch_labels = None
depends_on = None

COLUMNS = [
    ("workspaces", "subjects", sa.Column("prior_knowledge", sa.String(16), nullable=True)),
    ("assessment", "diagnostic_items", sa.Column("difficulty_label", sa.String(8), nullable=True)),
    ("assessment", "diagnostic_items", sa.Column("cross_checked", sa.Boolean(), nullable=False, server_default=sa.false())),
]
NEW_TABLES = [("tutor", "course_summaries", CourseSummary), ("tutor", "course_summary_sections", CourseSummarySection)]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for schema, table, col in COLUMNS:
        if col.name not in {c["name"] for c in insp.get_columns(table, schema=schema)}:
            op.add_column(table, col, schema=schema)
    for schema, table, model in NEW_TABLES:
        model.__table__.create(bind, checkfirst=True)
        if bind.dialect.name != "postgresql":
            continue
        exists = bind.execute(sa.text("select 1 from pg_policies where schemaname=:s and tablename=:t"),
                              {"s": schema, "t": table}).first()
        if not exists:
            op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY owner_isolation ON {schema}.{table} "
                       f"USING (owner_id = current_setting('app.user_id', true)) "
                       f"WITH CHECK (owner_id = current_setting('app.user_id', true))")
        op.execute(f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {schema}.{table} TO thinkfirst_app;
            END IF; END $$""")


def downgrade() -> None:
    for schema, table, _ in reversed(NEW_TABLES):
        op.drop_table(table, schema=schema)
    for schema, table, col in reversed(COLUMNS):
        op.drop_column(table, col.name, schema=schema)
