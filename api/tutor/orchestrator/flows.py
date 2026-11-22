"""The three flows of the Tutor module.

prepare   (both valleys)  ingest -> concepts -> fingerprint -> research -> probe bank      -> awaiting level
revision  (Valley 1)      plan -> revision pack -> mock exam -> ready
skills    (Valley 2)      tutorial tree -> first lesson pages -> ready
"""

from __future__ import annotations

from ..agents import create, plan, understand
from .graph import Graph


def _ready(ctx, state):
    t = ctx.track(state["track_id"])
    ctx.save_track(t, status="ready")
    return {"ready": True}


def prepare_flow() -> Graph:
    g = Graph("prepare")
    g.node("ingest", understand.ingest_documents, "Ingest uploads")
    g.node("concepts", understand.build_concepts, "Concept graph")
    g.node("fingerprint", understand.build_course_fingerprint, "Course fingerprint and exam blueprint")
    g.node("research", understand.research_gaps, "Fill gaps from the web")
    g.node("probe_bank", create.build_probe_bank, "Level check questions")
    return g.chain("ingest", "concepts", "fingerprint", "research", "probe_bank")


def revision_flow() -> Graph:
    g = Graph("revision")
    g.node("plan", plan.plan_revision, "Priorities and revision plan")
    g.node("pack", create.build_revision_pack, "Revision pack")
    g.node("mock_exam", create.build_mock_exam, "Mock exam")
    g.node("ready", _ready, "Ready")
    return g.chain("plan", "pack", "mock_exam", "ready")


def skills_flow() -> Graph:
    g = Graph("skills")
    g.node("architect", plan.architect_tutorial, "Tutorial tree")
    g.node("prefetch", create.prefetch_lessons, "First lesson pages")
    return g.chain("architect", "prefetch")


FLOWS = {"prepare": prepare_flow, "revision": revision_flow, "skills": skills_flow}
