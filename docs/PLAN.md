# ThinkFirst — Plan for this run (M0–M2 + demo)

Scope: M0 Foundation, M1 Course path, M2 Validation loop, and only the supporting pieces the 8-state demo needs (evidence receipts, review-date persistence, save/pause/resume + recording recovery, private-data isolation + deletion, quotas/reservations + minimal Q01). M3–M7 → `docs/BACKLOG.md`.

## 1. Architecture (summary — details in ARCHITECTURE.md)

- **`/api`** — Python 3.12 FastAPI **modular monolith** (`thinkfirst.modules.*`). Each module owns its tables (one Postgres schema per module), exposes a `service.py` interface, and reacts to other modules only through the in-process event dispatcher (`thinkfirst.core.events`).
- **`/worker`** — ARQ worker (Redis) that runs the same job functions; `JOB_MODE=inline` runs jobs synchronously (tests, no-Docker dev). Jobs are idempotent (`core.jobs.idempotency_key` unique) with tracked status.
- **`/web`** — Next.js App Router + TypeScript + Tailwind. Same-origin `/api/*` rewrite to FastAPI so the httpOnly session cookie works. Atlas Studio tokens as CSS variables.
- **Data** — PostgreSQL 16 + pgvector, Redis, MinIO (S3). Fallback for tests/no-Docker dev: SQLite + local file storage + inline jobs (log D-002).
- **AI** — `llm_gateway` is the only path to model providers; `demo` adapters (deterministic, labeled) when keys are missing; metadata-only call log. Symbolic grading (SymPy) for algebra is real, not simulated.
- **Isolation** — every private row has `owner_id`; all queries go through `owned()` helpers; on Postgres, RLS policies keyed on `app.user_id` with a non-superuser app role (defence in depth).

## 2. Data model (core tables)

| Schema (module) | Tables |
|---|---|
| core | `jobs` |
| identity | `users`, `auth_sessions`, `user_settings`, `consent_grants`, `access_audit_log` (append-only) |
| workspaces | `subjects` |
| ingestion | `sources`, `source_revisions`, `source_pages`, `source_chunks` (embedding), `concept_graph_revisions`, `concepts`, `source_items` (extracted exercises) |
| tutor | `sessions` (revision, lease, checkpoint, stage/phase), `tasks` (mode, lock, help level, server-only solution), `help_events`, `reflections` |
| assessment | `rubrics`, `attempts`, `assessments` (criteria JSON, null scoring, quotes) |
| explain_back | `audio_takes`, `transcript_versions` |
| learner_model | `evidence_records`, `review_schedules` |
| billing | `entitlements`, `reservations`, `usage_charges` |
| llm_gateway | `llm_call_log` (metadata only) |
| knowledge_library | `shared_resources` (cat. a), `licensed_content` (cat. b), `contributions` (private until rights confirmed) — stub |
| admin | (uses identity consent/audit) — stub |

## 3. Task breakdown

### M0 Foundation
1. Repo layout, docker-compose (postgres+pgvector, redis, minio, api, worker, web), `.env.example`, CI workflow.
2. API skeleton: config, DB (schema translate for SQLite), event dispatcher, jobs, metadata-only logging, error model.
3. identity: register/login/logout/me, scrypt hashing, cookie sessions, roles, Google OAuth (real flow when configured; labeled "not configured" otherwise), settings, consent grants + audit log foundation.
4. billing: mock entitlement provider, reservations (reserve/consume/release, idempotent), quota status → Q01.
5. Web: tokens, fonts (self-hosted Nunito Sans/Noto Sans Arabic + OFL), app shell (4 destinations, 5 subject tabs, mobile More), routes with screen IDs, Demo/Simulated labels, truthful scope pages for out-of-scope screens.
6. Seed script (demo account, demo course PDF fixture).

### M1 Course path (UC01–UC14, UC16, UC32–UC33, UC38)
7. A01/A02 onboarding (UC01), `/` redirect logic, return targets.
8. C01 create subject + upload (PDF/PPTX/TXT/MD/paste) with limits/rights; ingestion jobs (validate → extract → chunk/embed → propose scope); C02 phases, per-file errors, retry/replace/exclude, cancel generation (UC03–UC06).
9. C03 optional diagnostic: skip → insufficient evidence (UC07), minimal.
10. W01 vertical roadmap + W06 inspector (UC08), foundation detour bookmark (UC09 minimal).
11. S01 setup with reservation (UC10, UC38); S02 recall → cited chunk → example → exercise (UC11, UC12) with SymPy checks and misconception flag; help ladder via P01, server-enforced, confirmed reveal (UC13, UC14).
12. F01 save/pause/resume, checkpoint revisions, owner lease/takeover (UC02, UC16).
13. W04 sources list/remove (tombstone) + W07 cited page viewer (UC32, UC33).

### M2 Validation loop (UC15, UC17, UC21 + parts of UC18/UC28/UC37)
14. Explain-back: recorder state machine (all phases), IndexedDB chunk persistence + reload recovery, upload, demo STT job, transcript versions (original/corrected/supplement), confirmation, rubric assessment (quote validation, missing-criterion citations, null scoring).
15. Follow-up: one persisted question; answer via same phases.
16. Transfer: novelty-validated task, mode commit before reveal, server lock, guided conversion (irreversible, revision-serialized).
17. S03: reflection, evidence receipts, persisted review date (default +3 days, adjustable).
18. W08 minimal receipt, W05 minimal list; A03 privacy: audio retention choice, delete audio now, delete attempt (recompute evidence).

### Tests & docs
19. pytest unit (policy) + API integration; vitest (recorder machine); Playwright e2e (demo text path + voice path with fake device; transfer lock deep link).
20. ARCHITECTURE, DECISIONS, OPEN_QUESTIONS, BACKLOG, TRACEABILITY, RUN_REPORT, README.

## 4. Open questions and chosen defaults (ambiguity policy)

| Question | Default chosen | Where |
|---|---|---|
| Upload limits | Blueprint proposal: 20MB/file, 5/batch, 200 pages/file | DECISIONS D-010 |
| Validation bundle cost | 3 units (explanation + follow-up + transfer); free plan 30 units / 30 days (mock) | D-011 |
| Audio retention | Delete after confirmation (default); opt-in replay ≤7 days from upload | OPEN_QUESTIONS Q-01 (jurisdiction) |
| Minor students | Not handled; restrictive: no extra data collection | OPEN_QUESTIONS Q-02 |
| Admin access to content | None; consent grants model only, no admin UI | OPEN_QUESTIONS Q-03 |
| Contributions of past exams | Stay private; no sharing path built | OPEN_QUESTIONS Q-04 |
| LLM processor for real keys | Not chosen for production; gateway sends confirmed text only, metadata-only logs | OPEN_QUESTIONS Q-05 |
| Review interval | 3 days, adjustable (hypothesis, not optimum) | D-012 |
