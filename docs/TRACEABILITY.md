# Traceability (screen / use case → route · component · endpoint · test · status)

Status: **Done** (built + tested) · **Partial** (built for the demo scope; gaps listed) · **Scope page** (truthful
"not built" notice) · **Backlog**. Tests: `api/tests/*` (pytest), `web/src/**/*.test.ts` (vitest), `web/e2e/*` (Playwright).

## Screens

| ID | Route | Component (web/src) | API endpoints | Tests | Status |
|---|---|---|---|---|---|
| A01 | `/welcome` | app/welcome/page.tsx | POST /auth/register, /auth/login, /auth/logout, GET /auth/me, /auth/providers, /auth/google/* | test_auth_errors_do_not_leak, test_csrf_header_required; e2e keyboard sign-in | Done (Google = real flow, unconfigured ⇒ labelled) |
| A02 | `/onboarding` | app/onboarding/page.tsx | PATCH /me/onboarding | e2e signUpFresh | Done |
| A03 | `/settings?section=` | app/settings/page.tsx | PATCH /me/settings, GET/POST/DELETE /me/consent-grants, GET /me/audit-log, POST /billing/demo/usage | test_admin_has_no_default_access…; e2e 320px | Partial (no export/account deletion, no password change) |
| G01 | `/today` | app/today/page.tsx | GET /today | test_lease_takeover… (resume action); e2e demo state 1, F01 test | Done (basic priority: resume → next concept) |
| G02 | `/subjects` | app/subjects/page.tsx | GET /subjects, DELETE /subjects/:s (archive) | test_private_data_isolation | Done |
| G03 | `/planner` | app/planner/page.tsx | GET /reviews | e2e demo (review persisted) | Partial (review dates only; M4) |
| G04 | `/progress` | app/progress/page.tsx | GET /progress | — | Partial (counts by state; profile M3) |
| G05 | `/planner/entries/:b` | scope page | — | — | Scope page (M4) |
| C01 | `/subjects/new` | app/subjects/new/page.tsx | POST /subjects, POST /subjects/guided, GET /limits, GET /demo/course-file | test_rights_ack_required_and_limits_visible; e2e demo state 2 | Done |
| C02 | `/subjects/:s/setup` | app/subjects/[s]/setup/page.tsx | GET /subjects/:s/setup, POST /subjects/:s/scope/confirm, POST /sources/:d/{retry,cancel,exclude,replace} | test_ingestion_recovery_partial_success, test_states_1_to_4…; e2e demo state 3 | Done |
| C03 | `/subjects/:s/diagnostic` | app/subjects/[s]/diagnostic/page.tsx | POST /subjects/:s/diagnostic/skip | — | Partial (skip ⇒ insufficient evidence; sampled items M3) |
| W01 | `/subjects/:s/roadmap` | components/Roadmap.tsx | GET /subjects/:s/roadmap | test_states_1_to_4…; e2e demo state 4 | Done |
| W02 | `/subjects/:s/practice` | scope page | — | — | Scope page (M3) |
| W03 | `/subjects/:s/exams` | scope page | — | — | Scope page (M5) |
| W04 | `/subjects/:s/resources` | app/subjects/[s]/resources/page.tsx | GET /subjects/:s/resources, GET /sources/:d/impact, DELETE /sources/:d, POST /subjects/:s/sources | test_source_removal_creates_tombstone | Done (generated aids = backlog) |
| W05 | `/subjects/:s/progress` | app/subjects/[s]/progress/page.tsx | GET /subjects/:s/evidence | test_delete_attempt… | Partial (receipt list; matrix M3) |
| W06 | `/subjects/:s/roadmap/concepts/:c` | components/Roadmap.tsx | GET /subjects/:s/concepts/:c | test_states_1_to_4…; e2e demo | Done |
| W07 | `/subjects/:s/resources/:d?page=` | app/subjects/[s]/resources/[d]/page.tsx | GET /documents/:d/pages/:p | test_full_validation_loop_text (423 while locked), tombstone test; e2e demo (second tab denied) | Done (search/annotations backlog) |
| W08 | `/subjects/:s/progress/evidence/:e` | app/subjects/[s]/progress/evidence/[e]/page.tsx | GET /evidence/:e, DELETE /evidence/:e/attempt | test_delete_attempt_removes_content_and_evidence | Partial (minimal receipt; disputes M3) |
| S01 | `/subjects/:s/sessions/:l/setup` | app/subjects/[s]/sessions/[l]/setup/page.tsx | POST /subjects/:s/sessions, POST /sessions/:l/start | test_quota_boundary_q01…; e2e | Done |
| S02 | `/subjects/:s/sessions/:l` | app/subjects/[s]/sessions/[l]/page.tsx, components/session/* | GET /sessions/:l, /lease, /checkpoint, /pause, /resume, /advance, /tasks/:t/{submit,help,commit-mode,convert,abandon,keep-unscored}, /tasks/:t/{explain,audio,typed,corrections,confirm} | test_demo_flow_api.*, test_policies_api.*; e2e demo + acceptance | Done (paper/code modes M7) |
| S03 | `/subjects/:s/sessions/:l/summary` | app/subjects/[s]/sessions/[l]/summary/page.tsx | GET /sessions/:l/summary, POST /reflection, /review, /complete | test_full_validation_loop_text; e2e demo state 8 | Done (profile update M3) |
| E01–E03 | `/subjects/:s/exams/:x/{setup,run,report}` | scope pages | — | — | Scope page (M5) |
| P01 | in S02 (right rail / sheet) | components/session/ProfessorPanel.tsx | POST /tasks/:t/help, POST /professor/ask | test_reveal_requires_confirmation…, test_help_before_typing…, lock tests; e2e demo | Done |
| F01 | in S02 | components/session/FocusSheet.tsx | POST /sessions/:l/pause | e2e "save and pause" | Done |
| N01 | header bell | components/AppShell.tsx | — | — | Scope (truthful empty panel; M7) |
| Q01 | in S01 | components/QuotaDialog.tsx | 402 QUOTA_EXHAUSTED payload | test_quota_boundary_q01_and_no_double_charge, test_reservations_idempotent_and_bounded | Done |

## Use cases

| UC | Scope this run | Implementation | Tests | Status |
|---|---|---|---|---|
| UC01 Onboard | M1 | A01/A02, Unsure goal, no mic prompt | e2e signUpFresh | Done |
| UC02 Return/restore | M1 | G01 resume, checkpoint revision + lease, Read-only/Take over | test_lease_takeover_and_stale_revision; e2e F01 | Done |
| UC03 Upload course | M1 | C01 → C02 jobs, per-file errors | test_ingestion_recovery_partial_success | Done |
| UC04 Recover ingestion | M1 | retry same job, replace (generation++), exclude, cancel rejects late callback | test_ingestion_recovery_partial_success | Done (replace path untested in e2e) |
| UC05 Guided self-study | M1 | POST /subjects/guided (algebra only), labelled AI-generated | — | Partial |
| UC06 Confirm/revise scope | M1 | edit titles/exclude, supersede proposals, rubric creation via event | test_states_1_to_4 | Done |
| UC07 Diagnostic or skip | M1 | skip ⇒ insufficient evidence | — | Partial |
| UC08 Select concept | M1 | every node inspectable/startable | e2e demo | Done |
| UC09 Prerequisite detour | M1 | optional foundation links + "Learn this foundation first"; parent bookmark field + S03 "Return to original task" | — | Partial (bookmark not set from W06 yet) |
| UC10 Start recommended session | M1 | G01 Start / Change action; reservation | e2e | Done |
| UC11 Structured Learn | M1 | recall → cited chunk → different example → retrieval; exposure = Introduced | test_full_validation_loop_text | Done |
| UC12 Submit exercise | M1 | SymPy grading, idempotent attempt, misconception | test_grade_expand…, replay test | Done |
| UC13 Early support | M1 | "I don't know" → clarify, no minimum | test_help_before_typing_has_no_minimum; e2e | Done |
| UC14 Escalate assistance | M1 | ladder to confirmed reveal, fresh generated check | test_reveal_requires_confirmation… | Done |
| UC15 No-help check/crossover | M2 | commit-mode before reveal, server lock, irreversible conversion, revision race guard | test_conversion_is_irreversible…, test_lock_survives_pause…; e2e acceptance | Done |
| UC16 Pause/resume | M1 | F01 save and pause, explicit Resume, lock persists | test_lock_survives_pause…; e2e | Done |
| UC17 Complete/reflect | M2 | S03 receipts, reflection once, review date | test_full_validation_loop_text; e2e | Done |
| UC18 Delayed review | parts | review date persisted and shown (G01/G03/W01) | test_full_validation_loop_text | Partial (sessions M3) |
| UC21 Audio explain-back | M2 | recorder machine, IDB recovery, upload receipt, demo/Groq/Gemini STT, confirmation, rubric | machine.test.ts, test_voice_path…; e2e demo + acceptance | Done |
| UC22 Contextual Professor | M1 | P01, retrieval-cited answers, solution-leak guard, lock | lock tests | Done |
| UC23 Focus controls | M1 | S01 quiet/timer, F01 | e2e F01 | Done |
| UC28 Challenge assessment | parts | `disputed`/`superseded_by_id` columns only | — | Backlog (M3) |
| UC32 Manage sources | M1 | W04 add/remove + tombstone, impact preview | test_source_removal_creates_tombstone | Done |
| UC33 Follow citation | M1 | W07 exact page + Return; tombstone; locked denial | tests above; e2e demo | Done |
| UC37 Privacy/account | parts | default audio deletion, delete audio now, delete attempt, consent/audit view | test_voice_path…, test_delete_attempt…, test_admin… | Partial (export/account deletion backlog) |
| UC38 Quota boundary | M1 | bundle reservation, Q01, idempotent charges, release | test_quota_boundary…, test_reservations… | Done |
| UC19, UC20, UC24–UC27, UC29–UC31, UC34–UC36, UC39, UC40 | later | — | — | Backlog (see BACKLOG.md) |
