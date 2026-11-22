"""Level tests that used the algebra questions on non-algebra subjects (matched by concept number only) are marked
invalid so the student can retake them. Nothing is deleted: items are switched off, sessions get status "invalid",
the algebra "mistakes" they logged become kind "invalidated", and the frontier they produced is cleared.

Revision ID: 0011_invalidate_wrong_tests
Revises: 0010_planner_deadlines
"""

import sqlalchemy as sa

from alembic import op

revision = "0011_invalidate_wrong_tests"
down_revision = "0010_planner_deadlines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    from thinkfirst.modules.diagnostic.service import CURATED_BANK, CURATED_TITLES

    prompts = [t["prompt"] for items in CURATED_BANK.values() for t in items]
    rows = bind.execute(sa.text("""
        select distinct i.subject_id, c.key, lower(trim(c.title)) from assessment.diagnostic_items i
        join workspaces.subjects s on s.id = i.subject_id
        join ingestion.concepts c on c.graph_revision_id = s.active_graph_revision_id and c.key = i.skills->>0
        where not i.generated and i.prompt = any(:p)"""), {"p": prompts}).all()
    bad = sorted({sid for sid, key, title in rows if CURATED_TITLES.get(key) != title})
    if not bad:
        return
    b = {"s": bad}
    bind.execute(sa.text("update assessment.diagnostic_items set diagnostic=false, verified=false where subject_id = any(:s)"), b)
    bind.execute(sa.text("update assessment.diagnostic_sessions set status='invalid' where subject_id = any(:s)"), b)
    bind.execute(sa.text("update memory.learning_events set kind='invalidated' where subject_id = any(:s) "
                         "and kind='misconception' and stage='diagnostic'"), b)
    bind.execute(sa.text("update learner_model.initial_profiles set frontier='[]', low_confidence=true, needs_retest=true "
                         "where subject_id = any(:s)"), b)


def downgrade() -> None:
    pass
