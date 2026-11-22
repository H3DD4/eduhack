# Reading aids implementation plan

## Rollout and data

- Add `ENABLE_ACCESSIBILITY_MODULE`, default `false`; additionally require the individual student's explicit consent and enabled profile. Feature-off and profile-inactive paths must preserve current UI, prompts, grading, and mastery.
- Add a private `accessibility_profile` table in the identity schema with nullable requested preferences and consent timestamp, plus an `enabled` switch. Scope reads/writes to the current user and add a forward Alembic migration with downgrade. Add only a nullable `spelling_error` field to attempts; do not rewrite existing rows.
- Add authenticated read/update/consent/delete/export endpoints; return no profile through class, teacher, or analytics APIs. Consent must be confirmed before saving settings.

## Features and integration

| Feature | Integration |
|---|---|
| Profile, consent, export/delete | New `modules/accessibility` model/service/router; register only when flag is enabled; tests for self-only access, defaults, consent, deletion, and export. |
| Settings and live preview | Add a “Reading aids” section to the existing settings route; only persist after consent. Use a component-local preview and retain the existing settings design. |
| Font, spacing, width, themes, focus | Add profile-driven CSS custom properties and named theme classes in `globals.css`; apply at the app shell only when active. Avoid default selectors changing. |
| Read aloud / speed | Reuse existing `SpeakButton` and browser speech in the avatar; add opt-in speed/voice configuration and explicit unavailable-language feedback. Keep user-initiated playback and text available. |
| Dictation | Add a reusable browser `STTProvider` control at existing chat and short-answer inputs; insert editable text, announce recording state, and leave the existing explain-back recording/confirmation flow intact. |
| Spelling tolerance and mastery | Add conservative text normalization/matching tests and nullable spelling metadata. Students identify language-learning subjects in settings; active non-language short-answer prompts instruct the existing semantic grader to ignore minor spelling/phonetic errors. Never promote an answer based on edit distance alone. |
| Tutor style | Add a request-scoped system suffix to eligible tutor prompt calls only when the feature flag and active profile both allow it; do not replace static rules, source constraints, or RAG behavior. Test active/inactive prompt output. |
| Time and exercise mode | Apply only to existing session setup/timer behavior where a supported control exists; do not represent the current informational timer as a secure exam timer. Document unsupported exam timing. |
| Visual aids and Arabic | Preserve existing concept maps and Arabic font/RTL affordances; add optional diacritics handling only where text is presented, and test direction/spacing. Do not claim language support beyond the app’s actual English UI. |
| Teacher view | Do not expose a profile indicator: this build has no teacher dashboard or teacher/student authorization model. Document this rather than adding an unsafe parallel teacher system. |

## Expected code and tests

- New: `api/thinkfirst/modules/accessibility/{__init__.py,models.py,service.py,router.py,matching.py}`, `api/alembic/versions/0008_accessibility.py`, `web/src/lib/accessibility/{profile.ts,SpeechInput.tsx,themes.ts,themes.test.ts}`, focused API tests, `ACCESSIBILITY.md`, and `CHANGELOG.md`.
- Minimal existing edits: API `config.py`, `models.py`, `main.py`, LLM prompt service, tutor submission/grading path, and attempt model; web settings, app shell, global CSS, session input components, `README.md`.
- Verify with the existing API suite and focused new tests, web unit tests/typecheck/lint, and a default-off regression test. Run the stack if Docker is available; otherwise report that limitation.

## Scope notes

- Existing UI copy is English-only and there is no i18n catalog or teacher/class dashboard. Do not add a partial translation or teacher disclosure mechanism; document these limitations.
- Fuzzy similarity alone cannot establish semantic correctness. It only records a likely typo; the existing semantic grader remains the authority for correctness and mastery outcomes.
- Browser voice inventories and recognition support are device-dependent; provide a clear unsupported/unavailable state and preserve typed input.
