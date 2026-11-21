# Run report — M0–M2 + eight-state demo (2026-11-21)

## What works end to end
- **The 8-state demo storyboard** on the seeded demo account in a real browser (Playwright, Chromium with a fake
  microphone): G01 empty → C01 demo course PDF (limits + rights visible) → C02 real PDF extraction and cited-page
  scope confirmation → W01 vertical path with optional foundation + W06 → S02 recall ("I don't know" orientation),
  cited course section, `2x + 3` flagged as a *possible distribution misconception* with one targeted question,
  early help (clarify step), corrected `2x + 6` → **voice explain-back** (disclosure + retention choice → record,
  pause, resume, finish → playback → checksummed upload → labeled demo transcription → unclear word must be resolved →
  confirm) → cited rubric feedback (verbatim quotes; missing idea says "Not demonstrated" with rubric criterion and
  course page 2, no quote) → raw audio deleted by default → **one follow-up** (text) → **no-help transfer** with a
  new expression *and* context ("3 packs of (x + 4) pens"), source page denied in a second tab → "Completed without
  in-app help" → S03 with application and retention shown separately, reflection saved once, **review date
  persisted** and visible in Today and Planner.
- **Server-side policies**: help ladder (clarify → strategy → sub-step → different worked example → *confirmed*
  "End this attempt and view worked solution"); solutions never sent before an authorized reveal; transfer lock
  across endpoints, tabs and devices, surviving pause; irreversible, revision-serialized guided conversion (a raced
  submission is rejected); null scoring; idempotent attempts, jobs, help events, uploads, evidence, reservations and
  charges; stale revisions rejected; owner lease with Read-only/Take over.
- **Save/pause/resume (F01)** with honest badges (On this device / Synced / Not saved); **recording recovery**: chunks
  persisted to IndexedDB and offered after reload for explicit review, with no automatic restart.
- **Private-data isolation**: owner-scoped queries (404 for other users) plus **Postgres RLS** verified on real
  Postgres as a non-superuser role; append-only audit log; consent-scoped admin access foundation.
- **Deletion controls**: audio deleted after confirmation by default, "Delete audio now", "Delete attempt" (content
  and derived evidence removed, content-free metadata kept), source removal → citation tombstones.
- **Quotas**: validation bundle (3 units) reserved at S01 before any capture; Q01 shows actual usage and reset, no
  prices; infrastructure retries never double-charge; unused units released at Finish.
- **`docker compose up`**: Postgres 16 + pgvector (RLS), Redis + ARQ worker, SeaweedFS S3, API, web. Smoke-tested
  through the web proxy: upload → extraction **on the worker** → confirm → practice misconception → explanation
  assessed **on the worker by a real model** (Gemini was unavailable → automatic fallback to Groq
  `openai/gpt-oss-120b`), with validated quotes/missing citations; metadata-only call log confirmed in Postgres.

## What remains simulated (and is labeled in the UI)
| Area | This build | Label shown |
|---|---|---|
| Explanation assessment without keys | regex matching of predeclared essentials (demo adapter) | "Simulated assessment (demo adapter…)" |
| Transcription without STT provider | fixture transcript the student must edit | "Demo transcription (simulated)…" |
| Rubric for the distributive property | authored demo rubric | "Demo rubric — not domain-approved" |
| Prompts for explanation/follow-up, transfer items | templates | origin **AI-generated** |
| Concept extraction | deterministic heading heuristic (real, not AI) | "Heuristic extraction … (no AI used)" |
| Embeddings | hashed bag-of-words | (internal; retrieval only) |
| Entitlements/payments | mock provider | "Mock entitlement provider (no real payments)" |
| Demo course | original fixture | "Demo data" |
Real (not simulated): SymPy algebra grading, PDF/PPTX/TXT/MD extraction, browser capture, upload/receipt, storage,
RLS, jobs, quotas. With keys in `api/.env` (local only): real LLM assessment (Gemini → Groq fallback) and real
Whisper STT on Groq; then the UI names those processors before capture and labels "AI assessment … not calibrated".

## Tests actually run (all on this machine, Windows 11)
| Suite | Command | Result |
|---|---|---|
| API unit + integration (SQLite) | `python -m pytest -p no:logging` | **43 passed**, 4 skipped (Postgres-only) |
| Postgres RLS (docker Postgres, app role) | `TEST_PG_APP_URL=… pytest tests/test_postgres_rls.py` | **4 passed** |
| Recorder state machine | `npx vitest run` | **9 passed** |
| Lint/types | `ruff check .` · `tsc --noEmit` · `next lint` | ruff clean · tsc clean · eslint 0 errors (exhaustive-deps warnings) |
| mypy (advisory) | `mypy thinkfirst` | 28 errors (not gating; typing debt) |
| Playwright E2E (production build) | `npm run e2e` | **7 passed** in one run (2.8 min): demo storyboard + 6 acceptance tests |
| Production build | `next build` | succeeded |
| Docker | `docker compose build` + `up` + smoke script | all 6 services running; smoke flow succeeded |
| Real STT check | Windows offline TTS WAV → Groq Whisper adapter | transcribed (see limitations) |

Acceptance tests from `audio_accessibility_and_states.md` covered: deny/unsupported microphone (cause copy, text
path, no retry when unsupported); rapid/duplicate commands, command timeouts, late chunks, empty takes (unit);
reload recovery (e2e); dropped upload response reconciles to the same take; one charge per bundle; unclear ASR →
edit/confirm, separate supplement, null for unresolved words (API + e2e); transfer hint/deep link/second tab,
cancel/confirm conversion (API + e2e); malformed grading output → unscored (unit); session takeover and stale writer
(API); keyboard sign-in, skip link and 320 px reflow (e2e); file failure with partial success, source tombstones,
delete retained audio (API). **Not covered**: NVDA/VoiceOver, real mobile browsers/codecs, RTL, exam deadlines (M5).

## Known limitations
- **Gemini**: `gemini-2.5-flash` is closed to new keys (404); default is now the `gemini-flash-latest` alias, which
  returned 503 (overloaded) during testing — the gateway fell back to Groq as designed.
- **Whisper language detection**: a French-accented synthetic voice reading English was transcribed in French.
  Mandatory transcript confirmation catches this, but STT language hints need tuning with real users.
- MinIO images were not pullable; SeaweedFS S3 is used locally (D-026).
- C03 only supports skipping; UC05 guided topic covers algebra only; UC09 detour bookmark is not yet set from W06.
- Professor answers are retrieval-cited but the demo adapter only quotes the top chunk; real-provider answers are
  checked for leaking the current task's solution string only (simple guard).
- Explanation assessment with real models is uncalibrated; no human calibration has been done.
- No export/account-deletion jobs; backups and processor copies are outside the deletion guarantees (stated in UI).
- Paused sessions keep the focused shell until "Save and exit"/F01 (F01 navigates to Today with navigation).
- mypy not yet clean; ESLint exhaustive-deps warnings in the recorder hook (intentional stable refs).
- Usability and accessibility have **not** been validated with learners or assistive-technology users; no
  learning-outcome claims are made.

## Security notes for the owner
- The Gemini and Groq keys you shared are stored only in `api/.env` (git-ignored; verified absent from all
  committed files). They were pasted into a chat, so consider rotating them.
- `api/.env` sets `STT_PROVIDER=groq` at your request: real recordings will be sent to Groq for transcription
  (disclosed in the recorder). `.env.example` keeps the restrictive `demo` default.

## Next recommended milestone
**M3 — Evidence and profile**: delayed reviews (UC18) that use the persisted review dates, disputes (UC28) on top of
the existing `disputed`/`superseded` fields, the full W05/W08/G04, BKT + FSRS, and G01 next-action priority. Before
that, close the carry-overs in `docs/BACKLOG.md` (C03 sampled items, export/account deletion, real embeddings,
screen-reader and mobile-device recorder testing).
