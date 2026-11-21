"""Concept packs, subject resource links, licensed content body (idempotent on fresh databases).

Revision ID: 0002_packs_resources
Revises: 0001_initial
"""

import sqlalchemy as sa

import thinkfirst.models  # noqa: F401
from alembic import op
from thinkfirst.modules.rag.library.models import SubjectResourceLink
from thinkfirst.modules.tutor.models import ConceptPack

revision = "0002_packs_resources"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

NEW_PRIVATE = ["tutor.concept_packs", "knowledge_library.subject_resource_links"]


def upgrade() -> None:
    bind = op.get_bind()
    ConceptPack.__table__.create(bind, checkfirst=True)
    SubjectResourceLink.__table__.create(bind, checkfirst=True)
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("licensed_content", schema="knowledge_library")}
    for name, coltype in (("language", sa.String(8)), ("body", sa.Text()), ("provider", sa.String(32))):
        if name not in cols:
            op.add_column("licensed_content", sa.Column(name, coltype, nullable=True), schema="knowledge_library")
    if bind.dialect.name != "postgresql":
        return
    for t in NEW_PRIVATE:
        schema, name = t.split(".")
        has_policy = bind.execute(sa.text("select 1 from pg_policies where schemaname=:s and tablename=:n"),
                                  {"s": schema, "n": name}).first()
        if not has_policy:
            op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY owner_isolation ON {t} USING (owner_id = current_setting('app.user_id', true)) "
                       f"WITH CHECK (owner_id = current_setting('app.user_id', true))")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tutor, knowledge_library TO thinkfirst_app;
        END IF; END $$""")


def downgrade() -> None:
    op.drop_table("subject_resource_links", schema="knowledge_library")
    op.drop_table("concept_packs", schema="tutor")
