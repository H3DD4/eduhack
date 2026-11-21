"""Diagnostic & behavioral tracking architecture tables with Postgres RLS.

Revision ID: 0005_diagnostic_architecture
Revises: 0004_shared_chunks
"""

import sqlalchemy as sa

import thinkfirst.models  # noqa: F401
from alembic import op
from thinkfirst.data.memory.models import BehavioralEvent, BehaviorIndicator
from thinkfirst.data.student_profile.models import InitialProfileRow, SkillMasteryRow
from thinkfirst.modules.diagnostic.grading.models import DiagnosticItemRow, DiagnosticSessionRow
from thinkfirst.platform.identity.models import StudentConsent

revision = "0005_diagnostic_architecture"
down_revision = "0004_shared_chunks"
branch_labels = None
depends_on = None

NEW_TABLES = [
    ("identity", "student_consents", StudentConsent),
    ("memory", "behavioral_events", BehavioralEvent),
    ("memory", "behavior_indicators", BehaviorIndicator),
    ("learner_model", "skill_mastery", SkillMasteryRow),
    ("learner_model", "initial_profiles", InitialProfileRow),
    ("assessment", "diagnostic_items", DiagnosticItemRow),
    ("assessment", "diagnostic_sessions", DiagnosticSessionRow),
]


def upgrade() -> None:
    bind = op.get_bind()
    for schema, table, model in NEW_TABLES:
        if bind.dialect.name == "postgresql":
            op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        model.__table__.create(bind, checkfirst=True)
        if bind.dialect.name != "postgresql":
            continue
        exists = bind.execute(
            sa.text("select 1 from pg_policies where schemaname=:s and tablename=:t"),
            {"s": schema, "t": table},
        ).first()
        if not exists:
            op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY owner_isolation ON {schema}.{table} "
                f"USING (owner_id = current_setting('app.user_id', true)) "
                f"WITH CHECK (owner_id = current_setting('app.user_id', true))"
            )
    if bind.dialect.name == "postgresql":
        for schema in ("identity", "memory", "learner_model", "assessment"):
            op.execute(f"""DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
                    GRANT USAGE ON SCHEMA {schema} TO thinkfirst_app;
                    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO thinkfirst_app;
                END IF; END $$""")


def downgrade() -> None:
    for schema, table, _ in reversed(NEW_TABLES):
        op.drop_table(table, schema=schema)
