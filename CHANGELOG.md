# Changelog

## Reading aids

### Existing files modified

- `README.md` — added opt-in rollout instructions and linked the limitations.
- `api/thinkfirst/config.py` — added the default-off accessibility feature flag.
- `api/thinkfirst/core/router.py` — exposed the flag through capabilities for conditional UI.
- `api/thinkfirst/main.py` and `api/thinkfirst/models.py` — registered the profile router and model.
- `api/thinkfirst/modules/diagnostic/grading/models.py` — added nullable spelling metadata to attempts.
- `api/thinkfirst/modules/diagnostic/grading/service.py` — provided subject context to the opt-in spelling-aware grader prompt.
- `api/thinkfirst/modules/tutor/llm/service.py` — appended opt-in prompt instructions without replacing existing system prompts.
- `api/thinkfirst/modules/tutor/service.py` — recorded conservative spelling metadata for active profiles and supplied subject context.
- `web/src/components/AppShell.tsx` — loaded an available profile and applied/removed its scoped CSS variables.
- `web/src/app/globals.css` — added profile-scoped typography, theme, and focus-ruler styles; preserved the default style values.
- `web/src/app/settings/page.tsx` — added consent, reading controls, live preview, language-subject choices, export, and delete.
- `web/src/components/avatar/AvatarSpeakerContext.tsx` and `web/src/components/avatar/TeacherAvatar.tsx` — reused browser speech with profile voice/rate settings and added voice availability feedback.
- `web/src/components/session/Stages.tsx`, `ExplainFlow.tsx`, and `ProfessorPanel.tsx` — added opt-in editable dictation and spell-check controls at existing input points.
- `web/src/app/subjects/[s]/sessions/[l]/page.tsx` — applied the hide-timer preference to the optional focus-sheet timer.

### New files

- `ANALYSIS.md` and `ACCESSIBILITY_PLAN.md` — required repository analysis and implementation plan.
- `ACCESSIBILITY.md` — aid behavior, privacy, and known limitations.
- `api/thinkfirst/modules/accessibility/` — profile model, API, validation, prompt rules, and conservative spelling normalization.
- `api/alembic/versions/0008_accessibility.py` — additive profile and spelling-metadata migration with downgrade.
- `api/tests/test_accessibility.py` — profile, consent, validation, prompt, and normalization tests.
- `web/src/lib/accessibility/` — profile types, browser speech provider interfaces/control, theme palette, and contrast tests.
