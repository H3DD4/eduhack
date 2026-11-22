# Accessibility module analysis

## Stack, entry points, and commands

- API: Python 3.12, FastAPI (`api/thinkfirst/main.py`), SQLAlchemy 2, Pydantic 2, Alembic, pytest.
- Web: Next.js 15 App Router, React 19, TypeScript 5.9, Tailwind 3.4. The primary web app is `web/`; `thinkfirst-web/` is a smaller duplicate/snapshot and is not used by Docker.
- Local stack: from this directory, `docker compose up --build`; open `http://localhost:3000`. Windows local-dev entry point: `run-thinkfirst.bat`.
- Tests: in `api`, `.venv\Scripts\python -m pytest -p no:logging`; in `web`, `npm test`, `npm run typecheck`, and `npm run lint`. E2E uses `npm run e2e`.
- API requests are mounted under `/api`; Next rewrites same-origin API paths to the API service. `AppShell` loads `/auth/me` and provides the user/capabilities context.

## Architecture and data flow

- UI: route pages under `web/src/app`; shared shell/components under `web/src/components`; API client/hooks under `web/src/lib`.
- API: identity and settings under `api/thinkfirst/platform/identity`; tutor/session orchestration under `modules/tutor`; RAG under `modules/rag`; grading/attempts under `modules/diagnostic/grading`; adaptation engine under `modules/adaptation/engine`; event subscribers persist evidence and feed the learner engine.
- Tutor tasks and exercises render in `web/src/components/session/Stages.tsx` and `web/src/app/subjects/[s]/sessions/[l]/page.tsx`. Free-text explain-back and transcript confirmation are in `web/src/components/session/ExplainFlow.tsx`. Professor questions are in `ProfessorPanel.tsx`; the 3D teacher has its own question input.
- Answer fields in practice/transfer are in `Stages.tsx`; explain-back text is in `ExplainFlow.tsx`; Professor input is in `ProfessorPanel.tsx`. The learner can also enter recall/retrieval drafts in `Stages.tsx`.
- Existing speech features: `SpeakButton` launches the 3D teacher from `AvatarSpeakerContext.tsx`; `TeacherAvatar.tsx` uses browser speech synthesis and speech recognition (recognition currently hardcodes English). Explain-back uses a separate `MediaRecorder` flow with explicit transcript review and server-side/demo STT. Reuse these paths rather than introduce another audio stack.
- Existing settings page: `web/src/app/settings/page.tsx`; `/me/settings` in `platform/identity/router.py` persists a validated JSON preferences object. Its language section currently says English only.
- Teacher UI is a student-facing 3D teacher page, not a teacher/class dashboard. There is no teacher/student relationship or consented reading-aid indicator to extend.

## Tutor prompts, answer checking, and mastery

- Prompt templates and their static system instructions live in `api/thinkfirst/modules/tutor/llm/prompts.py`. `llm.service.run()` resolves a template and passes `template.system` and rendered variables to the provider. There is no student reading profile in prompt construction today.
- Generated short answers are checked by `diagnostic/grading/service.py::grade_generated`; expressions use SymPy when parsable, otherwise the `grade_short_answer` LLM template. Attempts and assessments are persisted separately in the `assessment` schema.
- `tutor/service.py::submit_answer` records the attempt, grades it, and publishes `ASSESSMENT_ACCEPTED` through `_publish`. `modules/adaptation/service.py` folds these events through the existing pure JSON adaptation engine; the engine updates BKT-style evidence and related learner state. Keep changes outside the engine algorithms.
- Explain-back grades only the student-confirmed transcript. Diagnostic answers have their own Elo/BKT path and should not be accidentally changed by a practice-answer aid.

## Data, migrations, languages, and accessibility

- Models are registered through `api/thinkfirst/models.py`; module schemas are created by the initial migration. Private tables conventionally have an `owner_id` and Postgres RLS policy. SQLite tests use schema translation.
- Alembic currently ends at merge revision `0007_merge_heads`; the diagnostic and engine branches were merged there. Add a new forward revision with a reversible downgrade; avoid modifying old revisions.
- UI strings are predominantly hard-coded English. There is no i18n framework or complete French/Arabic translation catalog. The global document is currently `lang="en" dir="ltr"`. CSS has an Arabic font and basic RTL selectors, but the settings page says French/Arabic are not yet available.
- Existing accessibility includes visible focus outlines, skip links, labels, live regions, keyboard-aware dialogs, optional quiet mode, system reduced-motion preference, and clickable read-aloud controls. There is no global reading-aid profile, accessible typography/theme controls, or app-wide dictation.
- No accessibility-specific profile/table, profile export/deletion API, or student-consent flow currently exists. Account-level export/deletion is explicitly deferred in Settings.

## Risks and safeguards

- Default UI and prompt behavior must remain unchanged: gate API/UI changes with a server feature flag that defaults off and an explicitly consented, enabled per-student profile.
- Profile settings are private data: use authenticated self-service endpoints, owner-scoped access/RLS, minimal fields, and never expose them in teacher/class APIs.
- Fuzzy matching can incorrectly accept a mathematically or conceptually wrong response. Do not let edit distance alone change correctness or mastery; retain the existing grader as the semantic authority and record spelling separately.
- Browser speech availability and voices vary by browser, locale, and device. Check capability/voice availability, keep text entry available, and report unavailable voices rather than silently pretending audio worked.
- Existing static English copy and lack of an i18n framework make all-language UI and teacher workflows unsafe to claim as complete. Keep new UI in the existing English style, preserve RTL-friendly controls, and document the limitation rather than invent a partial translation system.
- The current exercise timer is informational and session-local. Do not change exam timing or make time a grading signal without a real exam timing model.

## Integration points

1. `api/thinkfirst/config.py::Settings`: default-off feature flag.
2. `api/thinkfirst/modules/accessibility/`: new private profile model, API/service, consent handling, validation, and reading-rules helper.
3. `api/thinkfirst/main.py::create_app` and `api/thinkfirst/models.py`: register the gated API/model and private-table RLS.
4. `api/alembic/versions/0008_accessibility.py`: create the new profile table and nullable `assessment.attempts.spelling_error`, with downgrade.
5. `api/thinkfirst/modules/tutor/llm/service.py` and `tutor/service.py`: append opt-in rules only to eligible tutor prompts; preserve static prompts and RAG constraints.
6. `api/thinkfirst/modules/diagnostic/grading/models.py`, grading service, and `tutor/service.py::submit_answer`: track spelling independently; do not make fuzzy distance a correctness override.
7. `web/src/app/settings/page.tsx`, `web/src/components/AppShell.tsx`, and `web/src/app/globals.css`: opt-in controls, profile state, and CSS variables only while active.
8. `web/src/components/session/Stages.tsx`, `ExplainFlow.tsx`, and existing avatar speaker components: attach opt-in reading/dictation controls at existing text and input boundaries while reusing current browser/provider paths.
9. Focused API and web tests plus `ACCESSIBILITY.md`, README, and `CHANGELOG.md`.

No existing teacher dashboard or localization system is available as an integration point; those requested extensions will be described as limitations unless an existing API is found during implementation.
