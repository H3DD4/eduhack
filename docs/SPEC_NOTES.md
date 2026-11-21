# ThinkFirst — Spec notes (STEP 0)

All four spec files were opened and read in full on 2026-11-21:

| # | File | Lines read |
|---|---|---|
| 1 | `reports/ThinkFirst learning experience blueprint.md` (master) | 1–636 (all) |
| 2 | `research_notes/ThinkFirst learning experience blueprint/screens_and_use_cases.md` | 1–155 (all) |
| 3 | `research_notes/ThinkFirst learning experience blueprint/audio_accessibility_and_states.md` | 1–166 (all) |
| 4 | `research_notes/ThinkFirst learning experience blueprint/visual_references.md` | 1–113 (all) |

None were missing or unreadable.

Precedence: **(1) approved overrides in the build prompt §3 → (2) blueprint → (3) research notes → (4) `docs/DECISIONS.md`.**

---

## 1. Blueprint (master spec)

### Main sections
Intro · Status and assumptions · Design references (R01–R07 borrow/adapt/reject) · Experience principles · Visual and motion system (tokens, type, spacing, controls, breakpoints, path, motion) · Navigation and screen map · Screen specifications (A01…Q01) · Audio explain back (phase table, capture rules, rubric) · Use case catalogue (UC01–UC40) · Feature placement and release scope · Accessibility and responsive behaviour · Loading error and recovery states · Frontend state and data contracts · Usability validation · Coordinator review · Build order and acceptance criteria (8-state demo) · Sources (R01–R23).

### Screens (29) and canonical routes
| ID | Route | Surface |
|---|---|---|
| A01 | `/welcome` | Authentication |
| A02 | `/onboarding` | Goal/preferences |
| A03 | `/settings?section=:section` | account, notifications, privacy, language, plan, calendar |
| G01 | `/today` | Next action |
| G02 | `/subjects` | Subject collection |
| G03 | `/planner` | Planner |
| G04 | `/progress` | Overall evidence/profile |
| G05 | `/planner/entries/:b` | Entry editor |
| C01 | `/subjects/new` | Create subject |
| C02 | `/subjects/:s/setup` | Processing/scope |
| C03 | `/subjects/:s/diagnostic` | Optional baseline |
| W01 | `/subjects/:s/roadmap` | Learning path |
| W02 | `/subjects/:s/practice` | Practice selection |
| W03 | `/subjects/:s/exams` | Exam library |
| W04 | `/subjects/:s/resources` | Sources/aids |
| W05 | `/subjects/:s/progress` | Subject evidence |
| W06 | `/subjects/:s/roadmap/concepts/:c` | Concept inspector |
| W07 | `/subjects/:s/resources/:d?page=:p` | Document viewer |
| W08 | `/subjects/:s/progress/evidence/:e` | Evidence receipt |
| S01 | `/subjects/:s/sessions/:l/setup` | Learn/Practice/Review setup |
| S02 | `/subjects/:s/sessions/:l` | Active task modes |
| S03 | `/subjects/:s/sessions/:l/summary` | Session outcome |
| E01 | `/subjects/:s/exams/:x/setup` | Exam setup |
| E02 | `/subjects/:s/exams/:x/run` | Exam run |
| E03 | `/subjects/:s/exams/:x/report` | Exam report |
| P01 | parent route + `panel=professor` | Contextual assistance |
| F01 | parent S01/S02/C03 route | Focus/pause sheet |
| N01 | parent route | Bell inbox |
| Q01 | parent route | Quota dialog |

Routing rules: `/` → A01 (signed out) / A02 (setup unfinished) / G01. `/subjects/:s` → W01. Protected links keep a safe return target. Drafts are allocated before setup opens.

Shell: desktop 208px rail, 64px header (breadcrumbs left, bell+avatar right), subject title/actions above 5 tabs. Mobile 56px header, 64px bottom bar + safe area, tabs Roadmap/Practice/Exams/More. Active S02/C03 (and E02) use the task-focused shell (no global nav); setup/summary/paused restore nav. One right panel at a time; Back closes the panel before leaving the task.

### Use cases (UC01–UC40) — blueprint priority
| UC | Name | Priority (blueprint) |
|---|---|---|
| UC01 | Onboard | Core |
| UC02 | Return and restore | Core |
| UC03 | Upload course | Core |
| UC04 | Recover ingestion | Core |
| UC05 | Guided self-study | Core |
| UC06 | Confirm or revise scope | Core |
| UC07 | Diagnostic or skip | Core |
| UC08 | Select concept | Core |
| UC09 | Prerequisite detour | Core |
| UC10 | Start recommended session | Core |
| UC11 | Structured Learn | Core |
| UC12 | Submit exercise | Core |
| UC13 | Get early support | Core |
| UC14 | Escalate assistance | Core |
| UC15 | No-help check and crossover | Core |
| UC16 | Pause and resume | Core |
| UC17 | Complete and reflect | Core |
| UC18 | Delayed review | Core |
| UC19 | Paper response | Next |
| UC20 | Code response | Next |
| UC21 | Audio explain-back | Core |
| UC22 | Contextual Professor | Core |
| UC23 | Focus controls | Core |
| UC24 | Exam preparation | Next |
| UC25 | Configure mock exam | Core |
| UC26 | Run timed exam | Core |
| UC27 | Inspect exam and repair | Core |
| UC28 | Challenge assessment | Core |
| UC29 | Build planner | Core manual; Next generated |
| UC30 | Resolve schedule conflict | Next |
| UC31 | Missed study block | Core status; Next suggestions |
| UC32 | Manage sources | Core |
| UC33 | Follow citation | Core |
| UC34 | Inspect subject evidence | Core |
| UC35 | Inspect learner profile | Core basic; Next synthesis |
| UC36 | Configure notifications | Next |
| UC37 | Privacy and account | Core |
| UC38 | Quota boundary | Core guard; Later premium |
| UC39 | Calendar integration | Later |
| UC40 | Extended modes/mobile | Later |

### Audio explain-back phase list (blueprint table, in order)
Permission intent → Permission pending → Blocked → Ready → Starting command → Recording → Pausing command → Paused → Resuming command → Finalizing → Capture interrupted/error → Playback → Typed edit → Uploading → Transcribing → Transcript confirmation → Assessment → Explanation feedback → Follow-up preparation → Follow-up introduction → Follow-up feedback → Transfer preparation → Transfer introduction → Transfer answer → Guided conversion confirmation → Conversion pending → Unscored feedback → Transfer feedback → Delayed review introduction → Review feedback → Reflection (S03) → Profile pending (S03) → Complete → Job recovery.

Primary/secondary CTA per phase are taken verbatim from the table (e.g. Recording: "Finish recording" / "Pause"; Transcript confirmation: "Confirm and assess" / "Edit text"; Transfer introduction: "Start without in-app help" / "Use guided help"; Guided conversion: "Switch to guided practice" / "Cancel").

Capture rules: secure context + permission + embedding policy; `NotAllowedError` = policy/context/denial (don't assume denial); `NotFoundError` = no input; detect `MediaRecorder.isTypeSupported`; elapsed timer excludes pauses, separate from chunk count; 10s without command ack → stop tracks, recover late data; stop tracks on exit/text switch. Cause copy: "Access blocked here; check browser/system settings", "No microphone found; connect one", "Microphone could not open; check input device", "Recording unavailable in this browser/page", "No playable audio captured". No empty take is graded.

### Rubric (5 criteria)
Correctness (quoted claim/misconception) · Essential coverage (predeclared essentials, not word count) · Why/relationships · Example/application · Limits (only when applicable, else N/A). Scale: absent/contradicted 0, partial 1, demonstrated 2, `null` unscored, N/A excluded. No mastery % and no totals that hide uncertainty. Never assess duration/accent/fluency/emotion/silence.

### Evidence states (blueprint wording)
"Introduced", "Practised with support", "New application, no in-app help", "Recalled later on [date]", plus due, mixed, disputed, insufficient-evidence. (Override renames the third — see conflicts.)

### Help ladder
clarify → strategy → substep → different worked example → confirmed "End this attempt and view worked solution". "I don't know" opens orientation; no minimum attempt; target solution withheld until escalation.

### Design tokens (Atlas Studio)
| Token | Value |
|---|---|
| canvas / surface | `#F7F8F3` / `#FFFFFF` |
| ink / ink-muted | `#18282D` / `#526268` |
| border / control-stroke | `#CFDAD6` / `#526268` |
| action / action-hover / action-base | `#00796B` / `#00695D` / `#00564D` (white text) |
| help / help-surface | `#4B52A3` / `#EEEDFA` |
| discovery | `#F1BB58` (ink text only) |
| success / success-surface | `#176B4E` / `#E7F4EC` |
| needs-review / review-surface | `#A23D35` / `#FFF0EB` |
| focus | `#4453B6`, 3px outline + 3px surface offset |

Type (px size/line): metadata 14/20, body 16/26, problem 18/29, section 24/31, page 32/40, compact page 28/36; Arabic body 17/29, problem 19/32; weights 400/600/700; no Arabic letter-spacing or forced uppercase. Fonts `Nunito Sans, Noto Sans Arabic, system-ui, sans-serif` (Arabic swaps first two), self-hosted, `font-display: swap`, OFL notices retained.
Spacing 4/8/12/16/24/32/48/64. Radii 8 detail, 14 inputs/buttons, 20 task cards, 999 pills. Icons 24px/2px stroke. Targets ≥44×44, 8px separation; inputs ≥48px; primary ≥52px, 20px inline padding, 4px dark edge, press −2px. Max widths: overview 1200, task prose 48rem, entry form 480, modal 560, panel 320. Breakpoints: 320–767 compact (16px gutters), 768–1023 (24px, mobile nav), ≥1024 desktop shell (24px), ≥1440 (32px); right columns only ≥1200px.
Motion: easing `cubic-bezier(0.2,0.8,0.2,1)`; press 80ms, release 120, feedback 140, hint 180 (≤4px), evidence 240, discovery 260, optional 500ms constellation; reduced motion → static, opacity ≤80ms. Recording/transfer/exams static. No autoplay/bobbing/particles/fake progress.
Path: straight vertical unit spine, 64px labeled concept controls, ≥24px gaps, optional foundation branches, no lock imagery.

### Rules to enforce (blueprint)
- One dominant CTA per view; help secondary but obvious, never penalised.
- Every node inspectable/startable; foundations are suggestions with a return bookmark.
- Reading/path completion ≠ independent evidence; revealed target never counts independent.
- Transfer lock persists across routes/tabs/devices until terminal evidence/abandon acknowledgement; denies hints/lessons/tutoring/revealing sources/prior feedback; conversion "Keep your work and switch to guided practice?" commits irreversibly before unlock; raced guided results can't count independent; label "Completed without in-app help", never cheating-proof.
- Assess only confirmed transcript revision; original ASR, corrections and supplement kept separate; later edits supersede.
- Honest save badges: "Synced", "On this device", "Not saved".
- Retries: ≤3 automatic at 1/2/4s honoring Retry-After; idempotent jobs/evidence/charges; reject stale revisions; owner lease + Read-only/Take over; no last-write-wins.
- Jobs: delayed notice at 60s, Check status/Save and leave at 180s.
- Quota: reserve the whole validation bundle before capture/typed assessment; never interrupt speech/exam with payment; Q01 shows actual usage/reset, no invented price.
- Privacy defaults: only transcription receives audio, grading receives confirmed text; raw audio deleted after confirmation by default; optional replay retention 7 days from upload; local drafts expire 24h; "Audio deleted; transcript history remains"; delete attempt removes content + derived evidence and recomputes; no training on student data.
- Labels "Demo data" / "Simulated assessment" on mocked extraction/transcription/grading/timers/profile.
- Origin labels `verified-source` / `unverified-source` / `ai-generated`; generated origin never changes; uploads start unverified.
- Capabilities derived server-side: `canCaptureAudio, canUsePaper, canRunCode, canReadSources, canTutor, canRevealTarget, canSubmit, canStartCostlyAction`; hidden solutions never preloaded.
- A11y: WCAG 2.2 AA target, keyboard/SR complete flows, skip links, error summary, polite single announcements (no seconds/waveform chatter), focus restore, no hold-to-record/drag-only/hover-only, reflow 320px.
- Ethics: no hearts, guilt streaks, leaderboards, help penalties, time/audio-length rewards, paid boosts; private optional XP (+5/+10/+15/+15 pilot, Next).
- Copy: no cheat-proofing, readiness guarantee, predicted grades, proven outcomes.

### 8-state demo storyboard
1 G01 empty/next action · 2 C01 select supplied course PDF (limits/rights visible) · 3 C02 processing → confirm scope · 4 W01 + W06 (path, optional foundation, start concept) · 5 S02 guided Learn/Practice (recall, cited chunk, attempt, early hint/escalation) · 6 S02 explanation/follow-up (record/text, confirmation, cited feedback, one follow-up) · 7 S02 unfamiliar no-help transfer (guided conversion alternative) · 8 S03 (reflection, separate evidence summary, review booking, return Today). Capture may be real; extraction/ASR/grading visibly mocked; never imply measured retention.

---

## 2. `screens_and_use_cases.md`

Sections: canonical IA (takeaway, findings, navigation contract, routes table — same 29 IDs/routes as above), desktop/mobile placement table (per screen group), shared state contracts (ingestion stages, learning contract, evidence contract, privacy defaults), use-case catalogue table UC01–UC40 with trigger/screens/alternative/saved result/acceptance, gaps.

Additional details used: ingestion stages "transferring, queued, extracting/topic generation, scope review, ready; needs attention, failed, cancelled"; no invented extraction percentages; help ladder identical to blueprint; evidence stages "assisted, independent-recent, delayed-retention" + due/contradictory; origin labels "Verified source/Unverified source/AI-generated"; exam filters Verified-only/Generated-only/Mixed; privacy: subjects private, training opt-in separate.

Priorities differ from blueprint for UC21 (Next), UC28 (Next), UC29 (Next), UC31 (Next), UC35 (Next), UC38 (Later) — see conflicts.

## 3. `audio_accessibility_and_states.md`

Sections: explain-back traceability (placement contract with panel keys C recorder, T editor, P status, Q next question, R reflection, E summary+rail; phase/panel table; blocked branch copy; scoring & provenance; transfer lock), accessible responsive interactions (contrast, targets, focus, motion, delivery tiers First build/Next/Later), recovery/storage/adjacent states (persistence/retention, recovery table, practice exam timing, normalized frontend contract, acceptance tests).

Phase list (note's version): Permission intent/C · Permission pending/C · Blocked/C · Ready/C · Recording/C · Paused/C · Finalizing/C · Playback/C · Typed edit/T · Uploading/P · Transcribing/P · Confirmation/T · Grading/P · Feedback/E · Follow-up generation/P · Follow-up introduction/Q · Transfer introduction/Q · Transfer answer/C or T · Reflection/R · Profile pending/P · Complete/E. Microcopy used verbatim, e.g. "Explain naturally. We assess your ideas, not your voice. Review the text before assessment."; "Microphone connected. Recording has not started."; "Recording. Take your time."; "Check names, numbers, and meaning. Unclear words are not mistakes in understanding."; "There is not enough reliable information to score this yet."; "What would you try next time? This note does not change your evidence score."

**Acceptance tests listed (to execute, M0–M2 applicability):**
| Test | Applies this run |
|---|---|
| Ignore permission; deny; remove/busy device; unsupported MIME | Yes (state machine unit tests + e2e fake device) |
| Rapid start/pause/resume/finish; late final chunk | Yes (state machine unit tests) |
| Lock phone/close/reload; corrupt/evicted local draft | Partial (reload recovery of IndexedDB chunks; no real phone) |
| Drop upload response; repeat retry; exhaust quota/storage | Yes (idempotent upload/receipt, quota) |
| Unclear ASR, edit then confirm, add reasoning, dispute | Yes except dispute (M3) |
| Transfer hint/deep link/second tab; cancel/confirm help | Yes |
| Slow jobs, malformed grading, expired sign-in | Yes (malformed grading → unscored; job status) |
| Reload/offline at exam deadline; session takeover | Takeover yes; exams M5 |
| Keyboard + NVDA/VoiceOver; mobile zoom; RTL | Keyboard via Playwright; SR/RTL not testable here |
| File failure, dashboard failure, delete retained audio | Yes |

## 4. `visual_references.md`

Sections: borrow/adapt/reject (Duolingo discipline, not identity or pressure), original visual and motion system (same Atlas Studio tokens, typography, space, responsive, tactile primary button, icons/illustrations — faceted compass guide that "can nod or tilt curiously, never cry, scold, or panic", motion, energy decreases with concentration, reduced motion), ethical mechanics (private XP pilot values, no recording-length incentive, evidence-card badges "Misconception resolved"/"Applied in a new context"/"Recalled later", rhythm not pressure: "2 study days this week", evidence not omniscient mastery).

Evidence wording here: "Introduced", "Practised with support", "Applied independently", "Recalled on [date]".

---

## 5. Conflicts and resolution

| # | Conflict | Resolution |
|---|---|---|
| 1 | Third evidence label: blueprint "New application, no in-app help" vs visual note "Applied independently" vs prompt override "Applied independently (no in-app help)" | **Override wins**: `Applied independently (no in-app help)`. Fourth label `Recalled later on [date]` (blueprint + override). |
| 2 | UC21 audio: research note *Next* vs blueprint *Core* | Blueprint (and override §3.3): Core, built in M2. |
| 3 | UC28 disputes: note *Next* vs blueprint *Core* | Blueprint says Core, but build prompt schedules it for M3 → backlog; data model keeps `disputed`/`superseded_by` fields now. |
| 4 | UC29/UC31 planner: note *Next* vs blueprint *Core manual* | Blueprint priority stands; prompt scopes this run to review-date persistence only (M4 backlog). |
| 5 | UC35 profile: note *Next* vs blueprint *Core basic* | Prompt: basic receipts only this run; profile observations M3. |
| 6 | UC38 quota: note *Later* vs blueprint *Core guard* | Blueprint + override §3.11: Core guard now (minimal Q01). |
| 7 | Gutters: visual note "16 mobile, 24 medium, 32 wide" vs blueprint breakpoints (24 at ≥1024, 32 at ≥1440) | Blueprint's precise breakpoints. |
| 8 | Help ladder: prompt override "Attempt before the *solution*, not before any support" vs blueprint "Withhold target solution until escalation" | Consistent; override adds "End this attempt…" must be **confirmed**. |
| 9 | Companion: blueprint "peripheral on Today/map/report", G01 "not a mascot hero"; override "present on Today, Roadmap, session summaries with short text; hidden during recording/transfer/exams" | Override; implemented as small peripheral compass + one-line text, never a hero. |
| 10 | Demo state 1–3 (empty G01 → C01 upload PDF → C02) vs prompt "pre-seeded demo account with a first-year math subject" | Both: seeded account starts with **no subject** but a permission-cleared demo course PDF (MATH 101 fixture) offered in C01 as "Use the demo course file (Demo data)"; a seed flag `--with-subject` pre-creates the ready subject for jumping straight to state 4. Logged in DECISIONS D-003. |
| 11 | Blueprint "Demo account preauthenticated" vs real auth | Demo account uses the real email/password auth with seeded credentials shown on A01 only when `DEMO_MODE=true`, labeled "Demo data". |
| 12 | Raw-audio retention: override "deleted after confirmation by default" vs blueprint optional 7-day replay | Same default; the 7-day replay option is implemented as an explicit opt-in choice at permission intent. |
| 13 | Research note's demo engineering example (energy conservation) vs prompt math demo `2(x+3)` | Prompt wins (override §6 demo). |
