"""Prompt registry. One entry per task; the gateway renders `instructions` + the JSON input + the output shape.

Rules shared by every generation prompt (BASE_SYSTEM):
- ground every fact in CONTEXT chunks and cite their ids; never invent course content;
- write in the course language and reuse the course's own notation, vocabulary and exercise style;
- ThinkFirst principle: the student thinks first. Hints guide, they do not give the answer away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BASE_SYSTEM = (
    "You are part of ThinkFirst, a tutor that makes students think instead of thinking for them. "
    "You produce study material that looks like the student's own course: same language, same notation, "
    "same vocabulary, same exercise phrasing. Use ONLY the facts in CONTEXT; every item cites the ids of the "
    "chunks it relies on in `citations` as objects {\"chunk_id\": \"...\", \"quote\": \"short supporting quote\"}. "
    "If CONTEXT is not enough, produce fewer items rather than inventing. Math uses $...$ LaTeX. "
    "Reply with one JSON object only, no prose, no code fences."
)


@dataclass(frozen=True)
class Task:
    name: str
    instructions: str
    output_shape: dict[str, Any]
    required: tuple[str, ...]
    tier: str = "large"          # large | small
    max_tokens: int = 4000
    system: str = BASE_SYSTEM
    extra: dict[str, Any] = field(default_factory=dict)


CIT = [{"chunk_id": "c-12", "quote": "..."}]

TASKS: dict[str, Task] = {}


def _t(task: Task) -> Task:
    TASKS[task.name] = task
    return task


_t(Task(
    "classify_document",
    "Classify the uploaded document. doc_type is one of course, exercises, past_exam, solutions, slides, notes, "
    "other. A past_exam has a duration, points or an exam header. Give a short human title and the ISO language.",
    {"doc_type": "course", "title": "Chapitre 3 — Dérivation", "language": "fr"},
    ("doc_type",), tier="small", max_tokens=300,
))

_t(Task(
    "extract_concepts",
    "From the course OUTLINE and EXCERPTS, list the concepts a student must master, in teaching order. "
    "key is a short kebab-case slug. prerequisites are keys of earlier concepts. chapter is the course chapter "
    "title it belongs to. 4 to 40 concepts. Keep the course's own wording for titles.",
    {"concepts": [{"key": "derivee-definition", "title": "Définition de la dérivée", "chapter": "Dérivation",
                   "summary": "one sentence", "keywords": ["taux d'accroissement"], "prerequisites": []}]},
    ("concepts",), tier="small", max_tokens=5000,
))

_t(Task(
    "extract_blueprint",
    "Read the past exam(s) and describe their structure: duration in minutes, total points, and each part "
    "with its points, question types (qcm, true_false, short, calculation, proof, problem, code) and the "
    "concept keys (from CONCEPTS) it assesses.",
    {"duration_min": 120, "total_points": 20, "parts": [{"title": "Exercice 1", "points": 5,
     "question_types": ["calculation"], "concept_keys": ["derivee-definition"], "count": 3}]},
    ("parts",), tier="small", max_tokens=2000,
))

_t(Task(
    "research_queries",
    "The course does not cover these concepts well (GAPS). Write precise web search queries in the course "
    "language that would find a clear explanation at the student's level. 1 or 2 queries per gap.",
    {"queries": [{"concept_key": "derivee-definition", "query": "dérivée définition taux d'accroissement cours"}]},
    ("queries",), tier="small", max_tokens=800,
))

_t(Task(
    "generate_resume",
    "Write a revision summary (résumé) of the CHAPTER for an exam. Sections follow the course order. "
    "Bullets are short; formulas use the course notation; pitfalls are the mistakes students make. "
    "Adapt depth to LEVEL.",
    {"chapter": "Dérivation", "sections": [{"heading": "...", "bullets": ["..."], "formulas": ["$f'(a)=...$"],
                                            "pitfalls": ["..."], "citations": CIT}]},
    ("sections",), max_tokens=5000,
))

_t(Task(
    "generate_fiches",
    "Write revision cards (fiches). front is a cue or question, back is the answer in at most 4 lines. "
    "fiche_type is definition, formula, method, theorem, pitfall or example. One idea per card.",
    {"fiches": [{"concept_key": "...", "fiche_type": "formula", "front": "...", "back": "...", "citations": CIT}]},
    ("fiches",), max_tokens=4000,
))

_t(Task(
    "generate_qcm",
    "Write multiple-choice questions (QCM) in the style of the course. Exactly one correct option unless "
    "multiple is true. Each wrong option targets a real misconception (use KNOWN_ERRORS when given) and its "
    "`why` names it. Target DIFFICULTY (Elo, 1100 = average).",
    {"items": [{"concept_key": "...", "stem": "...", "multiple": False, "options": [
        {"text": "...", "correct": True, "why": "..."}, {"text": "...", "correct": False, "why": "confuses ..."}],
        "explanation": "...", "difficulty": 1100, "citations": CIT}]},
    ("items",), max_tokens=5000,
))

_t(Task(
    "generate_quiz",
    "Write short-answer quiz questions. answer_type is text, number, expression or true_false. For number "
    "give tolerance; for expression give the answer as a SymPy-parsable expression; accept lists equivalent "
    "wordings.",
    {"items": [{"concept_key": "...", "question": "...", "answer": "...", "answer_type": "number",
                "tolerance": 0.01, "accept": [], "explanation": "...", "difficulty": 1100, "citations": CIT}]},
    ("items",), max_tokens=4000,
))

_t(Task(
    "generate_exercises",
    "Write exercises that could appear in this course's exam: copy the course's statement style (see "
    "STYLE: verbs, numbering, data presentation). Each part has a worked solution and, when the answer is "
    "mathematical, a SymPy `check` expression of the expected result.",
    {"exercises": [{"concept_keys": ["..."], "title": "Exercice", "statement": "On considère ...", "difficulty": 1150,
                    "parts": [{"label": "1)", "prompt": "Calculer ...", "answer": "...", "answer_type": "expression",
                               "check": "3*x**2", "points": 2, "solution_steps": ["..."]}], "citations": CIT}]},
    ("exercises",), max_tokens=6000,
))

_t(Task(
    "generate_lesson",
    "Write one tutorial page in a progressive W3Schools style: a short intro, a clear explanation, one or "
    "two worked examples, a 'Try it yourself' block with 1-3 small items the student must attempt "
    "(each item uses the quiz or qcm item shape), common mistakes, and a 3-line summary. "
    "Start from what the student already knows (KNOWN) and stay at LEVEL. For programming topics put runnable "
    "code in `code` with `language`.",
    {"title": "...", "sections": [
        {"type": "intro", "title": "...", "body": "..."},
        {"type": "explain", "title": "...", "body": "...", "citations": CIT},
        {"type": "example", "title": "Exemple", "body": "...", "code": None, "language": None},
        {"type": "try", "title": "À vous", "body": "...", "items": [{"kind": "quiz", "question": "...",
                                                                    "answer": "...", "answer_type": "number"}]},
        {"type": "mistakes", "title": "Erreurs fréquentes", "body": "- ..."},
        {"type": "summary", "title": "À retenir", "body": "..."}]},
    ("sections",), max_tokens=6000,
))

_t(Task(
    "critic",
    "Check the ITEM against CONTEXT. Is the answer key correct? Is exactly the marked option correct? Is the "
    "item answerable from the course? List concrete problems. If the key is wrong and you are sure, give "
    "fixed_answer.",
    {"ok": True, "problems": [], "fixed_answer": None},
    ("ok",), max_tokens=800,
))

_t(Task(
    "grade_open",
    "Grade the student's ANSWER to QUESTION against the EXPECTED answer and solution. score is 0..1. "
    "error_tags name the misconception (short kebab-case). Feedback says what is right first, then the one "
    "thing to fix, without giving the full solution.",
    {"score": 0.5, "correct": False, "feedback": "...", "error_tags": ["sign-error"]},
    ("score", "correct"), tier="small", max_tokens=600,
))

_t(Task(
    "tutor_help",
    "The student is stuck on ITEM. Give help at LEVEL only: 1 = a guiding question, 2 = a hint pointing to "
    "the course section (cite it), 3 = a worked similar example with different numbers, 4 = the full "
    "solution with reasoning. Never go beyond LEVEL. Use the course language.",
    {"message": "...", "citations": CIT},
    ("message",), max_tokens=1200,
))

_t(Task(
    "answer_question",
    "Answer the student's QUESTION using CONTEXT and cite it. If MODE is practice and the question asks for "
    "the answer to an active exercise, guide with a question instead. If CONTEXT does not contain the "
    "answer, say so and suggest what to look up.",
    {"answer": "...", "citations": CIT, "grounded": True},
    ("answer",), max_tokens=1500,
))


def render_user(task: Task, variables: dict[str, Any]) -> str:
    import json

    shape = json.dumps(task.output_shape, ensure_ascii=False)
    body = json.dumps(variables, ensure_ascii=False, default=str)
    return (f"TASK: {task.name}\n{task.instructions}\n\nINPUT (JSON):\n{body}\n\n"
            f"Return JSON with this shape (keys {', '.join(task.required)} are required):\n{shape}")
