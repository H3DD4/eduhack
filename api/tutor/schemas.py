"""Typed records and artifact formats. Stored as JSON by the store; validated when produced by an LLM."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


Valley = Literal["revision", "skills"]
Level = Literal["beginner", "intermediate", "advanced"]
DocType = Literal["course", "exercises", "past_exam", "solutions", "slides", "notes", "web", "other"]
ArtifactType = Literal["resume", "fiches", "quiz", "qcm", "exercises", "mock_exam", "lesson", "probe"]
AnswerType = Literal["text", "number", "expression", "true_false", "choice"]

LEVEL_ELO: dict[str, float] = {"beginner": 900.0, "intermediate": 1100.0, "advanced": 1300.0}


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------------------------------------------------------------------------------------------- records
class Track(Model):
    id: str = Field(default_factory=new_id)
    owner_id: str
    valley: Valley
    title: str
    subject: str = ""
    goal: str = ""
    language: str = "fr"
    exam_date: str | None = None                      # ISO date, Valley 1
    chapters: list[str] = Field(default_factory=list)  # chapters the exam covers (empty = all)
    allow_web: bool = True
    status: str = "created"   # created > ingesting > awaiting_level > probing > building > ready | failed
    declared_level: Level | None = None
    measured_level: Level | None = None
    level_by_chapter: dict[str, str] = Field(default_factory=dict)
    level_verdict: str | None = None                 # confirmed | higher | lower
    budget_used: int = 0
    stats: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Document(Model):
    id: str = Field(default_factory=new_id)
    track_id: str
    owner_id: str
    filename: str
    mime: str = ""
    sha256: str = ""
    blob_key: str = ""
    doc_type: DocType = "other"
    title: str = ""
    pages: int = 0
    status: str = "uploaded"  # uploaded > parsed > indexed | failed
    error: str | None = None
    ocr_pages: int = 0
    created_at: str = Field(default_factory=now_iso)


class Chunk(Model):
    id: str = Field(default_factory=new_id)
    track_id: str
    owner_id: str
    document_id: str | None = None
    web_source_id: str | None = None
    origin: Literal["course", "web"] = "course"
    doc_type: DocType = "course"
    text: str
    page: int | None = None
    section: str = ""
    ord: int = 0
    concept_ids: list[str] = Field(default_factory=list)
    embedding: list[float] | None = Field(default=None, exclude=True)


class Concept(Model):
    id: str = Field(default_factory=new_id)
    track_id: str
    owner_id: str
    key: str                     # stable slug
    title: str
    chapter: str = ""
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)  # concept keys
    exam_weight: float = 1.0     # share of exam points (Valley 1); 1.0 when unknown
    coverage: float = 0.0        # how well the course chunks cover it (0..1)
    ord: int = 0


class BlueprintPart(Model):
    title: str
    points: float = 0.0
    question_types: list[str] = Field(default_factory=list)
    concept_keys: list[str] = Field(default_factory=list)
    count: int = 1


class Blueprint(Model):
    duration_min: int | None = None
    total_points: float | None = None
    parts: list[BlueprintPart] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    inferred: bool = False       # True when no past exam was uploaded


class Fingerprint(Model):
    track_id: str
    owner_id: str
    language: str = "fr"
    vocabulary: list[tuple[str, float]] = Field(default_factory=list)
    notation: dict[str, dict[str, int]] = Field(default_factory=dict)
    preferred_notation: dict[str, str] = Field(default_factory=dict)
    verbs: dict[str, int] = Field(default_factory=dict)
    numbering: str = ""
    question_types: dict[str, float] = Field(default_factory=dict)
    avg_question_words: float = 0.0
    avg_subquestions: float = 0.0
    numbers_per_question: float = 0.0
    difficulty_elo: float = 1100.0
    blueprint: Blueprint | None = None
    sample_exercises: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class WebSource(Model):
    id: str = Field(default_factory=new_id)
    track_id: str
    owner_id: str
    url: str
    domain: str
    title: str = ""
    licence: str = "unknown"
    query: str = ""
    concept_key: str | None = None
    sha256: str = ""
    status: str = "fetched"      # fetched | indexed | skipped | failed
    reason: str | None = None
    fetched_at: str = Field(default_factory=now_iso)


# ---------------------------------------------------------------------------------------------- items
class Citation(Model):
    chunk_id: str
    quote: str = ""
    page: int | None = None
    source: str = ""             # document title or domain
    origin: Literal["course", "web"] = "course"
    url: str | None = None


class QCMOption(Model):
    text: str
    correct: bool = False
    why: str = ""                # rationale; for wrong options: the misconception it catches


class QCMItem(Model):
    kind: Literal["qcm"] = "qcm"
    id: str = Field(default_factory=new_id)
    concept_key: str = ""
    stem: str
    options: list[QCMOption]
    multiple: bool = False
    explanation: str = ""
    difficulty: float = 1100.0
    citations: list[Citation] = Field(default_factory=list)


class QuizItem(Model):
    kind: Literal["quiz"] = "quiz"
    id: str = Field(default_factory=new_id)
    concept_key: str = ""
    question: str
    answer: str
    answer_type: AnswerType = "text"
    accept: list[str] = Field(default_factory=list)
    tolerance: float = 0.0
    explanation: str = ""
    difficulty: float = 1100.0
    citations: list[Citation] = Field(default_factory=list)


class Fiche(Model):
    kind: Literal["fiche"] = "fiche"
    id: str = Field(default_factory=new_id)
    concept_key: str = ""
    fiche_type: Literal["definition", "formula", "method", "pitfall", "example", "theorem"] = "definition"
    front: str
    back: str
    citations: list[Citation] = Field(default_factory=list)


class ExercisePart(Model):
    label: str = "a"
    prompt: str
    answer: str = ""
    answer_type: AnswerType = "text"
    check: str | None = None     # SymPy-checkable expression for the expected answer, e.g. "3*x**2"
    tolerance: float = 0.0
    points: float = 1.0
    solution_steps: list[str] = Field(default_factory=list)


class Exercise(Model):
    kind: Literal["exercise"] = "exercise"
    id: str = Field(default_factory=new_id)
    concept_keys: list[str] = Field(default_factory=list)
    title: str = ""
    statement: str
    parts: list[ExercisePart] = Field(default_factory=list)
    difficulty: float = 1100.0
    citations: list[Citation] = Field(default_factory=list)


class ResumeSection(Model):
    heading: str
    bullets: list[str] = Field(default_factory=list)
    formulas: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class Resume(Model):
    kind: Literal["resume"] = "resume"
    chapter: str
    sections: list[ResumeSection]


class MockExamPart(Model):
    title: str
    points: float
    items: list[dict[str, Any]] = Field(default_factory=list)   # QCMItem | QuizItem | Exercise dumps


class MockExam(Model):
    kind: Literal["mock_exam"] = "mock_exam"
    title: str
    duration_min: int = 60
    total_points: float = 20.0
    instructions: str = ""
    parts: list[MockExamPart]


class LessonSection(Model):
    type: Literal["intro", "explain", "example", "try", "mistakes", "summary", "quiz", "project"]
    title: str = ""
    body: str = ""               # markdown with $math$
    code: str | None = None      # for programming subjects
    language: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)   # try-it / quiz items
    citations: list[Citation] = Field(default_factory=list)


class LessonPage(Model):
    kind: Literal["lesson"] = "lesson"
    slug: str
    title: str
    chapter: str = ""
    concept_keys: list[str] = Field(default_factory=list)
    level: Level = "beginner"
    sections: list[LessonSection]
    prev_slug: str | None = None
    next_slug: str | None = None


ITEM_MODELS: dict[str, type[Model]] = {"qcm": QCMItem, "quiz": QuizItem, "fiche": Fiche, "exercise": Exercise}


def parse_item(d: dict[str, Any]) -> Model:
    return ITEM_MODELS[d.get("kind", "quiz")].model_validate(d)


# ---------------------------------------------------------------------------------------------- outputs
class Artifact(Model):
    id: str = Field(default_factory=new_id)
    track_id: str
    owner_id: str
    type: ArtifactType
    title: str
    chapter: str = ""
    concept_keys: list[str] = Field(default_factory=list)
    content: dict[str, Any]
    likeness: float | None = None
    likeness_detail: dict[str, float] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)
    status: Literal["draft", "approved", "rejected"] = "draft"
    regenerations: int = 0
    created_at: str = Field(default_factory=now_iso)


class Attempt(Model):
    id: str = Field(default_factory=new_id)
    track_id: str
    owner_id: str
    artifact_id: str | None = None
    item_id: str
    concept_key: str = ""
    context: Literal["probe", "practice", "mock", "lesson"] = "practice"
    answer: Any = None
    correct: bool | None = None
    score: float = 0.0
    ms: int | None = None
    help_level: int = 0
    rapid_guess: bool = False
    error_tags: list[str] = Field(default_factory=list)
    feedback: str = ""
    created_at: str = Field(default_factory=now_iso)


class LearnerConcept(Model):
    id: str
    track_id: str
    owner_id: str
    concept_key: str
    elo: float = 1100.0
    p_mastery: float = 0.2
    attempts: int = 0
    correct: int = 0
    help_total: int = 0
    last_seen: str | None = None
    next_review: str | None = None
    interval_days: float = 0.0


class TutorialNode(Model):
    id: str = Field(default_factory=new_id)
    track_id: str
    owner_id: str
    slug: str
    title: str
    chapter: str = ""
    ord: int = 0
    kind: Literal["chapter", "page", "quiz", "project", "checkpoint"] = "page"
    parent_slug: str | None = None
    concept_keys: list[str] = Field(default_factory=list)
    status: Literal["locked", "open", "done", "skippable"] = "locked"
    artifact_id: str | None = None


class PlanEntry(Model):
    date: str
    concept_key: str
    title: str
    activity: Literal["learn", "practice", "review", "mock_exam"]
    priority: float = 0.0
    minutes: int = 25


class Run(Model):
    id: str = Field(default_factory=new_id)
    track_id: str
    owner_id: str
    flow: str
    status: Literal["queued", "running", "waiting", "succeeded", "failed"] = "queued"
    node: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
