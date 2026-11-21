# The 4 backend process modules

One module = one owner. Only these 4 folders live here.

```
  DIAGNOSTIC ──► ADAPTATION ──► TUTOR (LLM)
                     │              │
          data/ (profile, memory)   RAG (+ vector DB + open courses)
```

| Module | Owner | In one sentence |
|---|---|---|
| [diagnostic](diagnostic/) | _____ | Grades answers and finds where understanding breaks |
| [adaptation](adaptation/) | _____ | Decides what the student does next, and why |
| [tutor](tutor/) | _____ | Runs the learning session and talks to the AI |
| [rag](rag/) | _____ | Finds the text to teach from, with citations |

Rules for everyone:
- Call another module only through its `service.py` (never its tables).
- React to things with events (`core/events.py`), e.g. `assessment.accepted`, `misconception.detected`.
- Every module's data is private per student (Postgres row-level security).

---

## 1. diagnostic — "where does understanding break?"
| File | What it does |
|---|---|
| `service.py` | After each graded answer, publishes `misconception.detected`; optional baseline check / skip |
| `router.py` | `GET /subjects/{s}/diagnostic`, `POST .../diagnostic/check`, `POST .../diagnostic/skip` |
| `grading/mathcheck.py` | SymPy grading for algebra (exact, not AI) + misconception patterns (e.g. "multiplied only the first term") |
| `grading/explanation.py` | Checks AI rubric output: quotes must be the student's exact words; unclear ⇒ unscored, never zero |
| `grading/rubrics.py` | The 5 rubric criteria + the demo rubric |
| `grading/service.py` | Saves attempts and assessments; grades AI-generated questions (SymPy or AI grader) |
| `grading/models.py` | Tables: rubrics, attempts, assessments |
**Inputs:** an answer + the task. **Outputs:** an assessment, plus a `misconception.detected` event.
**Tests:** `tests/test_policy_unit.py` (grading), `tests/test_modules.py` (baseline, misconception → memory).

## 2. adaptation — "what next?" (the learner engine)
| File | What it does |
|---|---|
| `engine/` | **Standalone learner engine, JSON in → JSON out**: BKT mastery, FSRS retention, misconception state machine, frontier + Thompson bandit, metrics, simulator. Full explanation: `docs/ENGINE.md` |
| `service.py` | Translates app data ↔ engine JSON: concept specs + memory events → learner state; suggestions, review dates, help suggestion after a wrong answer, bandit rewards |
| `models.py` | `adaptation.bandit_stats`: shared aggregate counts only (no student id) |
| `router.py` | `GET /subjects/{s}/learner-state`, `POST /engine/fold|recommend|evaluate`, `GET /engine/schema` |
**Reads:** `data/memory` (events). **Tests:** `tests/test_engine.py` (23), `tests/test_modules.py` (app integration).

## 3. tutor — "teach, help, check"
| File | What it does |
|---|---|
| `service.py` | The session: recall → lesson → practice → explain-back → follow-up → no-help problem → summary; save/pause/resume |
| `policy.py` | Server-side rules: help ladder, confirmed solution reveal, no-help lock |
| `packs.py` | AI study pack per level: lesson, practice + hints, rubric points, follow-ups, new-situation problem |
| `generators.py` | Hints and new problems computed with SymPy (algebra) |
| `router.py` | `/sessions/...`, `/tasks/{t}/submit`, `/tasks/{t}/help`, `/professor/ask`, `/today` |
| `models.py` | Tables: sessions, tasks, help events, reflections, concept packs |
| `llm/` | **The only door to AI models**: Groq → Gemini fallback with circuit breaker, versioned prompts (`prompts.py`), metadata-only logs |
| `explain_back/` | Voice: upload → speech-to-text → student corrects the text → only then graded; audio deleted after confirmation |
**Tests:** `tests/test_demo_flow_api.py`, `tests/test_policies_api.py`.

## 4. rag — "what do we teach from?"
| File | What it does |
|---|---|
| `service.py` | `hybrid()`: 1) the student's own course files → 2) shared library → 3) live fetch if nothing found; indexing + Qdrant/Postgres fallback |
| `embedder.py` | **Hugging Face cloud embedder** (multilingual MiniLM, 384-d) — demo hashing embedder only as fallback |
| `qdrant.py` | **Qdrant** REST client: collections, upsert, filtered search (owner + subject), delete |
| `reindex.py` | `python -m thinkfirst.modules.rag.reindex` rebuilds Qdrant from Postgres |
| `vector_store.py` | Fallback vector search (pgvector / in-memory) when Qdrant or HF is down |
| `ingestion/` | Uploaded PDF/PPTX/TXT → text → chunks → proposed roadmap; typed topic → AI roadmap |
| `library/models.py` | Shared open library (open-licence content only, with licence + credit) and its vector index |
| `agent/service.py` | The resource agent: fetches openly licensed content (Wikipedia, CC BY-SA) using only the topic name |
**Tests:** `tests/test_modules.py` (citations, isolation, hybrid: fetch once, reuse for the next student).
