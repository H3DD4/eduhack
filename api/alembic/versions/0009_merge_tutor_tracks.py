"""Merge the two 0008 branches that both start from 0007_merge_heads:
  * 0008_learning_path   (start wizard, placement test, course summary)
  * 0008_tutor_tracks    (Agentic Tutor: schema tutor_tracks, pgvector, RLS)
They create different tables, so their order does not matter. No schema change here.

Revision ID: 0009_merge_tutor_tracks
Revises: 0008_learning_path, 0008_tutor_tracks
"""

revision = "0009_merge_tutor_tracks"
down_revision = ("0008_learning_path", "0008_tutor_tracks")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
