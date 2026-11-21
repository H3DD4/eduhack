# ThinkFirst

**AI that makes you think, not AI that thinks for you.** A private learning environment for university and
engineering students. The student does the thinking; ThinkFirst organizes, guides, checks, and keeps honest evidence.

This repository implements milestones **M0–M2** plus the eight-state demo (see `docs/RUN_REPORT.md`).

```
api/      FastAPI backend (Python 3.12)
            thinkfirst/domain/    pure algorithms: mastery (Elo, BKT), knowledge graph, consent, tracking, adaptive diagnostic
            thinkfirst/modules/   the 4 process modules: diagnostic, adaptation, tutor, rag
            thinkfirst/data/      student_profile, memory
            thinkfirst/platform/  identity, billing, workspaces
            thinkfirst/core/      db, events, jobs, storage
worker/   ARQ (Redis) worker running the same idempotent jobs
web/      Next.js App Router + TypeScript + Tailwind (Atlas Studio tokens), Playwright e2e
infra/    Postgres init (non-superuser RLS role)
docs/     SPEC_NOTES, PLAN, ARCHITECTURE, DECISIONS, OPEN_QUESTIONS, BACKLOG, TRACEABILITY, RUN_REPORT
```

## Run everything with Docker (Windows, macOS, Linux)

```bash
docker compose up --build
```

Open http://localhost:3000 and sign in with the **demo account** `demo@thinkfirst.local` / `demo-password`
(the account and its course fixture are labeled *Demo data*). The stack runs Postgres 16 + pgvector with row-level
security, Redis + ARQ worker, SeaweedFS (S3-compatible), the API (http://localhost:8000/api/docs) and the web app.

Optional AI keys go in `api/.env` (copy `.env.example`; git-ignored). Without keys, every AI step uses clearly
labeled demo adapters ("Simulated assessment", "Demo transcription"). Algebra checks are real (SymPy) either way.

## Run without Docker (fast local dev)

On Windows, double-click or run **`run-thinkfirst.bat`** (or `start.bat`, or `run-thinkfirst.bat --docker` for the Docker stack). It seeds the database and calibrated diagnostic item bank, syncs the `branding/` assets, installs missing packages, starts the FastAPI backend on port `8000` and the Next.js frontend on port `3000`, and opens `http://localhost:3000`.

Prerequisites: Python 3.12 (`uv` recommended), Node 22.

```bash
# API (SQLite + inline jobs + local storage — DECISIONS D-002)
cd api
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
# Windows:  .venv\Scripts\python -m thinkfirst.seed
# macOS/Linux: .venv/bin/python -m thinkfirst.seed
.venv/Scripts/python -m thinkfirst.seed            # demo account (add --with-subject to skip upload)
.venv/Scripts/python -m uvicorn thinkfirst.main:app --port 8000

# Web (second terminal)
cd web
npm install
npm run dev            # http://localhost:3000 (proxies /api to http://127.0.0.1:8000)
```

## Demo walkthrough (8 states)
1. **Today (G01)** is empty → *Add subject*.
2. **C01**: *Use the demo course file* (MATH 101 PDF); limits and the study-use statement are visible.
3. **C02**: extraction finishes → check a cited page → *Confirm scope*.
4. **W01/W06**: vertical path with an optional foundation → *1.2 The distributive property* → *Learn this concept*.
5. **S02**: recall ("I don't know" is fine) → cited course section → expand `2(x + 3)`; typing `2x + 3` flags a
   possible distribution misconception with one targeted question; help is always available.
6. Explain distribution by **voice or text**, confirm/correct the transcript, read cited rubric feedback, answer
   **one follow-up**.
7. **No-help transfer**: "You buy 3 packs of (x + 4) pens…" — hints, Professor and course pages are locked
   (server-side, every tab) unless you switch to guided practice.
8. **S03**: "Applied independently (no in-app help)", retention shown separately, reflection, review date saved.

## Tests

```bash
cd api && .venv/Scripts/python -m pytest -p no:logging          # unit + API integration (SQLite)
# Postgres RLS tests (with docker compose running):
#   TEST_PG_APP_URL=postgresql+psycopg://thinkfirst_app:thinkfirst_app_dev@localhost:5432/thinkfirst \
#   .venv/Scripts/python -m pytest tests/test_postgres_rls.py
cd web && npm test              # recorder state machine (vitest)
cd web && npm run typecheck && npm run lint
cd web && npx playwright install chromium && npm run e2e        # starts API + production web build itself
```

Use `.venv/bin/python` instead of `.venv/Scripts/python` on macOS/Linux. A Makefile is intentionally not required.

## Privacy defaults (summary)
Private by default; Postgres RLS per student; raw audio deleted after transcript confirmation (7-day replay is
opt-in); confirmed text only to LLMs; metadata-only logs; admins have no default access (scoped, expiring,
revocable consent + append-only audit log); no training on student data. See `docs/ARCHITECTURE.md` and
`docs/OPEN_QUESTIONS.md`.

## Licenses
Fonts: Nunito Sans and Noto Sans Arabic (SIL OFL 1.1), self-hosted, with notices in `web/public/fonts/`.
The MATH 101 demo course text is original to this project.
