"""Import every module's models so metadata/migrations see all tables, and register job/event handlers."""

from thinkfirst.core import jobs  # noqa: F401
from thinkfirst.data.memory import models as _memory  # noqa: F401
from thinkfirst.data.memory import service as _memory_service  # noqa: F401  (event subscribers)
from thinkfirst.data.student_profile import models as _lm  # noqa: F401
from thinkfirst.data.student_profile import service as _lm_service  # noqa: F401  (event subscribers)
from thinkfirst.modules.adaptation import models as _adaptation  # noqa: F401
from thinkfirst.modules.adaptation import service as _adaptation_service  # noqa: F401  (event subscribers)
from thinkfirst.modules.diagnostic import placement as _placement  # noqa: F401  (job handler + subscriber)
from thinkfirst.modules.diagnostic import service as _diagnostic_service  # noqa: F401  (event subscribers)
from thinkfirst.modules.diagnostic.grading import models as _assessment_models  # noqa: F401
from thinkfirst.modules.diagnostic.grading import service as _assessment_service  # noqa: F401  (event subscriber)
from thinkfirst.modules.rag.agent import service as _rd  # noqa: F401
from thinkfirst.modules.rag.ingestion import models as _ingestion  # noqa: F401
from thinkfirst.modules.rag.ingestion import service as _ingestion_service  # noqa: F401  (job handler)
from thinkfirst.modules.rag.library import models as _kl  # noqa: F401
from thinkfirst.modules.tutor import models as _tutor  # noqa: F401
from thinkfirst.modules.tutor import packs as _packs  # noqa: F401  (job handler)
from thinkfirst.modules.tutor import service as _tutor_service  # noqa: F401  (job handlers)
from thinkfirst.modules.tutor import summary as _summary  # noqa: F401  (job handler)
from thinkfirst.modules.tutor.explain_back import models as _eb  # noqa: F401
from thinkfirst.modules.tutor.explain_back import service as _eb_service  # noqa: F401  (job handler)
from thinkfirst.modules.tutor.llm import models as _llm  # noqa: F401
from thinkfirst.platform.billing import models as _billing  # noqa: F401
from thinkfirst.platform.identity import models as _identity  # noqa: F401
from thinkfirst.platform.workspaces import models as _ws  # noqa: F401
from tutor.store import sqlalchemy_store as _tutor_tracks  # noqa: F401

# Tables holding private student data (owner_id). Postgres RLS policies are created for each.
PRIVATE_TABLES = [
    "core.jobs", "workspaces.subjects", "ingestion.sources", "ingestion.source_revisions", "ingestion.source_pages",
    "ingestion.source_chunks", "ingestion.concept_graph_revisions", "ingestion.concepts", "ingestion.source_items",
    "tutor.sessions", "tutor.tasks", "tutor.help_events", "tutor.reflections", "assessment.rubrics",
    "assessment.attempts", "assessment.assessments", "explain_back.audio_takes", "explain_back.transcript_versions",
    "learner_model.evidence_records", "learner_model.review_schedules", "billing.entitlements", "billing.reservations",
    "billing.usage_charges", "knowledge_library.contributions", "tutor.concept_packs",
    "knowledge_library.subject_resource_links", "memory.learning_events",
    "identity.student_consents", "memory.behavioral_events", "memory.behavior_indicators",
    "learner_model.skill_mastery", "learner_model.initial_profiles",
    "assessment.diagnostic_items", "assessment.diagnostic_sessions",
    *[f"tutor_tracks.{c}" for c in (
        "tracks", "documents", "chunks", "concepts", "fingerprints", "web_sources", "artifacts", "attempts",
        "learner", "tutorial", "runs", "plans",
    )],
]
