"""Store selected accessibility support modes."""

import sqlalchemy as sa

from alembic import op

revision = "0009_support_modes"
down_revision = "0008_accessibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    schema = "identity" if postgres else None
    table = "identity.accessibility_profile" if postgres else "accessibility_profile"

    op.add_column(
        "accessibility_profile",
        sa.Column("support_modes", sa.JSON(), nullable=True),
        schema=schema,
    )
    if postgres:
        op.execute(
            "UPDATE identity.accessibility_profile "
            """SET support_modes = '["reading"]'::json """
            "WHERE enabled IS TRUE AND consent_given_at IS NOT NULL"
        )
    else:
        op.execute(
            f"UPDATE {table} SET support_modes = '[\"reading\"]' "
            "WHERE enabled = 1 AND consent_given_at IS NOT NULL"
        )


def downgrade() -> None:
    postgres = op.get_bind().dialect.name == "postgresql"
    op.drop_column("accessibility_profile", "support_modes", schema="identity" if postgres else None)
