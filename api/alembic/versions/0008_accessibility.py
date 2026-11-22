"""Private reading-aid profile and spelling metadata.

Revision ID: 0008_accessibility
Revises: 0007_merge_heads
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_accessibility"
down_revision = "0007_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    schema = "identity" if postgres else None
    user_ref = "identity.users.id" if postgres else "users.id"
    op.create_table(
        "accessibility_profile",
        sa.Column("student_id", sa.String(36), sa.ForeignKey(user_ref, ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("font", sa.String(40), nullable=True),
        sa.Column("font_size", sa.Integer(), nullable=True),
        sa.Column("line_spacing", sa.Float(), nullable=True),
        sa.Column("letter_spacing", sa.Float(), nullable=True),
        sa.Column("word_spacing", sa.Float(), nullable=True),
        sa.Column("theme", sa.String(24), nullable=True),
        sa.Column("line_width", sa.Integer(), nullable=True),
        sa.Column("focus_mode", sa.String(16), nullable=True),
        sa.Column("tts_enabled", sa.Boolean(), nullable=True),
        sa.Column("tts_speed", sa.Float(), nullable=True),
        sa.Column("speech_language", sa.String(8), nullable=True),
        sa.Column("stt_enabled", sa.Boolean(), nullable=True),
        sa.Column("extra_time_factor", sa.Float(), nullable=True),
        sa.Column("hide_timer", sa.Boolean(), nullable=True),
        sa.Column("arabic_diacritics", sa.Boolean(), nullable=True),
        sa.Column("spelling_suggestions", sa.Boolean(), nullable=True),
        sa.Column("word_prediction", sa.Boolean(), nullable=True),
        sa.Column("language_subject_ids", sa.JSON(), nullable=True),
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )
    op.add_column(
        "attempts", sa.Column("spelling_error", sa.Boolean(), nullable=True),
        schema="assessment" if postgres else None,
    )
    if postgres:
        op.execute("ALTER TABLE identity.accessibility_profile ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE identity.accessibility_profile FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY owner_isolation ON identity.accessibility_profile "
            "USING (student_id = current_setting('app.user_id', true)) "
            "WITH CHECK (student_id = current_setting('app.user_id', true))"
        )
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thinkfirst_app') THEN
                GRANT USAGE ON SCHEMA identity TO thinkfirst_app;
                GRANT SELECT, INSERT, UPDATE, DELETE ON identity.accessibility_profile TO thinkfirst_app;
            END IF; END $$""")


def downgrade() -> None:
    postgres = op.get_bind().dialect.name == "postgresql"
    op.drop_column("attempts", "spelling_error", schema="assessment" if postgres else None)
    op.drop_table("accessibility_profile", schema="identity" if postgres else None)
