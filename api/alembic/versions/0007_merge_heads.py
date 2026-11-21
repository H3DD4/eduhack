"""Merge the two migration branches that both started from 0004_shared_chunks:
  * 0005_engine -> 0006_item_quality          (learner engine columns, bandit/item/hint aggregates)
  * 0005_diagnostic_architecture              (diagnostic, behavioural tracking, consent, initial profile tables)
They touch different tables, so the order between them does not matter.

Also restores a guarantee from 0001: 0005_diagnostic_architecture runs
`GRANT ... UPDATE, DELETE ON ALL TABLES IN SCHEMA identity`, which re-granted UPDATE/DELETE on the append-only
identity.access_audit_log. Revoke them again (checked by tests/test_postgres_rls.py::test_audit_log_is_append_only).

Revision ID: 0007_merge_heads
Revises: 0006_item_quality, 0005_diagnostic_architecture
"""

from alembic import op

revision = "0007_merge_heads"
down_revision = ("0006_item_quality", "0005_diagnostic_architecture")
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
            REVOKE UPDATE, DELETE ON identity.access_audit_log FROM thinkfirst_app;
        END IF; END $$""")


def downgrade() -> None:
    pass
