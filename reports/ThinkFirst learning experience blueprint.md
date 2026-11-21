# ThinkFirst learning experience blueprint

Build ThinkFirst as an original Duolingo-inspired academic adventure: a visible course path, quiet problem workspace, and one obvious next action. Its central loop is explain-back -> confirmed transcript -> cited feedback -> one follow-up -> unfamiliar no-help application -> reflection -> delayed review. AI scaffolds rather than supplies premature solutions. Progress records concept evidence, assistance, and uncertainty, not instant mastery. This specification covers 29 screens/panels and 40 implementation cases; the hackathon recommendation is eight storyboard states. These are build recommendations, not validated usability or learning outcomes.

## Status and assumptions

Date: 21 November 2026. Inputs: three supplied research notes and conversation brief; no earlier report. Source review/rechecks used WebFetch only, without rendered, interactive, screenshot, mobile, accessibility, or learner testing. Color calculations are numerical, not interface certification; learning papers were accessed as indexed abstracts.

- Audience: individual university/engineering learner; private subjects/work/evidence. No teacher/parent/admin dashboards or social/public grades.
- Responsive web first; English specification/demo. Confirm release locale; French/Arabic are Next. Foundation must support localization/RTL/reflow.
- Core beta: trustworthy loop, manual planner, evidence/profile, sources, text mocks. This exceeds hackathon scope.
- Next: OCR/paper, isolated code, advanced planning/profile, reminders, annotations, localization. Later: premium/calendar/native-mobile and labs/oral mocks.
- Read navigation -> screens -> cases/contracts. Retain research IDs. Audio becomes Core beta because the latest brief makes it central.

Label mocked extraction/transcription/grading/timers/profile "Demo data" or "Simulated assessment". Content calibration, privacy review, and real integration verification are release gates.

## Design references

Duolingo is the primary reference. Its 2026 account describes consistent titles, purposeful headers, fewer type styles, and whitespace. Historical path documentation describes smaller units, integrated practice, and guidebooks; October 2026 guidance describes targeted review. Product descriptions do not validate ThinkFirst's academic effectiveness. ([Design, R01](https://blog.duolingo.com/core-tabs-redesign/)) ([Path, R02](https://blog.duolingo.com/new-duolingo-home-screen-design/)) ([Review, R03](https://blog.duolingo.com/how-to-review-lessons-on-duolingo/))

| Reference | Borrow | Adapt for ThinkFirst | Reject |
| --- | --- | --- | --- |
| Duolingo, R01-R03 | Clear path, short prompts, hierarchy, tactile actions, concise recognition | Course units, prerequisite side branches, evidence-linked discoveries, voluntary review | Owl/assets/proprietary fonts, exact layouts, punitive hearts, leagues, public grades |
| Duolingo widget, R04 | Relevant next-action reminder | Learner-controlled, quiet reminders with reasons | Increasingly desperate companion near midnight; continued-use retention is not learning retention |
| Brilliant, R05 | Guiding questions, interactive work, contextual hints | Student-owned workings with a graduated help ladder | Copying its tutor identity or asserting its marketing outcomes apply here |
| Forest, R06 | A calm concentration state and accumulated history | Persistent discoveries from learning events | Dead-tree loss, group punishment, rewards for minutes, claims this web app blocks other apps |
| NN/g, R07 | Progressive disclosure of advanced controls | Keep scope/format preview together; disclose specialist options | Hiding frequently needed help, consent, provenance, or recovery |

The widget's increasing desperation and Forest's intentional loss are deliberate exclusions; Brilliant supplies a scaffolding reference, not outcome evidence. ([Widget](https://blog.duolingo.com/widget-feature/)) ([Forest](https://www.forestapp.cc/)) ([Brilliant](https://brilliant.org/)) ([Disclosure](https://www.nngroup.com/articles/progressive-disclosure/))

## Experience principles

Loop: goal/recall -> course-grounded learn/practice -> attempt/help -> unfamiliar no-help transfer -> reflection/evidence/profile -> delayed review/planner. Retrieval and learning/performance research support later checks, not universal engineering-mastery thresholds or interface validation. ([Abstracts, R08](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%28EXT_ID%3A16507066%20AND%20SRC%3AMED%29%20OR%20DOI%3A10.1177%2F1745691615569000&resultType=core&format=json&pageSize=2))

- One dominant CTA; secondary help stays obvious and unpunished.
- "I don't know" opens orientation before answering; no minimum attempt.
- Help: clarify -> strategy -> substep -> different worked example -> confirmed "End this attempt and view worked solution". Withhold target solution until escalation.
- Inspect/start any path node; suggested foundations preserve a return bookmark, never a punitive gate.
- Evidence labels: "Introduced", "Practised with support", "New application, no in-app help", "Recalled later on [date]"; add due, mixed, disputed, and insufficient-evidence states.
- No personality/learning-style diagnosis, fake mastery percentage, readiness guarantee, or voice-based trait inference. Uncertain interpretation stays unscored.
- Optional private XP is distinct from evidence. Never hearts, guilt streaks, leaderboards, time/audio-length bonuses, help penalties, or paid learning-score boosts.

## Visual and motion system

Use the original **Atlas Studio** baseline: warm paper, deep ink, teal actions, amber discoveries, geometric diagrams, faceted compass companion. These are not Duolingo proprietary tokens. Companion is peripheral on Today/map/report, absent from recording/transfer/equations/exams.

| Token | Value | Exact role |
| --- | --- | --- |
| canvas / surface | `#F7F8F3` / `#FFFFFF` | App backdrop / working panels |
| ink / ink-muted | `#18282D` / `#526268` | Main / supporting text; placeholders remain readable |
| border / control-stroke | `#CFDAD6` / `#526268` | Decorative grouping / identifying input, checkbox, and meaningful chart boundaries |
| action / action-hover / action-base | `#00796B` / `#00695D` / `#00564D` | Primary face / hover / tactile lower edge, with white text |
| help / help-surface | `#4B52A3` / `#EEEDFA` | Constructive hints and assistance labels |
| discovery | `#F1BB58` | Optional milestone accent with ink text and ink outline where meaningful |
| success / success-surface | `#176B4E` / `#E7F4EC` | Demonstrated criterion, never a global mastery claim |
| needs-review / review-surface | `#A23D35` / `#FFF0EB` | Local corrective feedback, not shame |
| focus | `#4453B6` | 3px focus outline, 3px surface-colored offset gap |

Calculated opaque sRGB ratios, rounded: ink/canvas 14.26:1; muted/canvas 5.95:1; white/action 5.32:1; white/hover 6.61:1; help/help-surface 5.97:1; success/success-surface 5.71:1; review/review-surface 5.81:1; focus/canvas 6.23:1; ink/discovery 8.69:1. These pairs clear relevant 4.5:1/3:1 thresholds numerically. White/discovery 1.75:1 and border/white 1.43:1 fail: no white amber labels or pale sole functional boundaries. Verify rendered states/transparency/diagrams/overlays separately. ([Contrast, R12](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)) ([Non-text, R13](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html))

| System | Build values |
| --- | --- |
| Fonts | Latin/French: `Nunito Sans, Noto Sans Arabic, system-ui, sans-serif`; Arabic reverses the first two. Self-host, `font-display: swap`, retain notices. Accessible math rendering, not UI-font substitutions. |
| Type size/line height | Metadata 14/20px; body 16/26; problem 18/29; section 24/31; page 32/40, compact page 28/36. Arabic body starts 17/29, problem 19/32. Weights 400 body, 600 labels, 700 headings/buttons. Use rem equivalents; no Arabic letter-spacing or forced uppercase. |
| Spacing | 4, 8, 12, 16, 24, 32, 48, 64px. Related controls 8; form fields 16; working groups 24; sections 32. |
| Radii / icons | Detail 8px; inputs/buttons 14; task cards 20; status pills 999. Icons 24px, 2px strokes; optional 20px metadata glyphs inside 44px hit areas. |
| Controls | Recommended minimum 44x44px touch target, 8px separation. Inputs minimum 48px high; primary minimum 52px, 20px inline padding. Grow for wrapped labels. |
| Primary states | Teal face, 4px dark edge; hover tint only; press moves 2px, edge 2px. Disabled: border face, muted text, static, reason adjacent. Loading: stable footprint, "Checking reasoning...", `aria-busy`, no duplicate activation; eligible practice help remains available. |
| Geometry | Overview max 1200px; task prose max 48rem; entry form max 480px; modal max 560px; panel 320px. Cards have minimum, not fixed, heights. |
| Breakpoints | 320-767px compact: 16px gutters, stacked/full-width CTA. 768-1023: 24px gutters, still mobile navigation. >=1024: desktop shell, 24px gutters; >=1440: 32px gutters. Right columns require >=1200px viewport and adequate task width, otherwise stack/sheet. |
| Path | Straight vertical unit spine; 64px labeled concept controls, 24px minimum vertical gaps, optional foundation branches. Unit title states number/topic/objective. Shape, text, and date accompany color; no lock imagery for unseen concepts. |

Both fonts specify SIL Open Font License 1.1; embedding/redistribution requires its conditions/notices. Licensing is verified, shaping/readability untested. ([Nunito, R09](https://raw.githubusercontent.com/google/fonts/main/ofl/nunitosans/OFL.txt)) ([Noto Arabic, R10](https://raw.githubusercontent.com/google/fonts/main/ofl/notosansarabic/OFL.txt))

Easing `cubic-bezier(0.2, 0.8, 0.2, 1)`: press 80ms; release 120ms; feedback opacity 140ms; hint 180ms/<=4px translation; acknowledged evidence 240ms; discovery 260ms. Optional 500ms constellation after committed transfer/review, outside answers, without sound/waiting. Reserve space; animate opacity/transforms. Energy peaks on map/report; practice uses local transitions; recording/transfer/exams stay static. Reduced motion immediately replaces movement/count-ups/celebrations, optional opacity <=80ms. No autoplay, bobbing, shaking, particles, or fake progress. Quiet mode hides decoration/XP, not content/credit.

## Navigation and screen map

Globals: **Today, Subjects, Planner, Progress**. Avatar: account/settings/sign-out. Profile belongs in overall Progress; F01 Focus is state and P01 Professor contextual assistance, not destinations. Subject tabs: **Roadmap, Practice, Exams, Resources, Progress**; mobile **Roadmap, Practice, Exams, More**, revealing Resources/subject Progress at unchanged routes. Overall Progress aggregates subjects; subject Progress names its subject.

Parameters: `:s` subject, `:c` concept, `:d` document, `:e` evidence, `:l` session, `:x` exam attempt, `:b` planner entry. Allocate resumable drafts before setup. `/` -> A01 signed-out/A02 unfinished/G01 otherwise; protected links retain safe auth return targets. `/subjects/:s` -> W01.

| ID | Canonical route | Surface |
| --- | --- | --- |
| A01 | `/welcome` | Authentication |
| A02 | `/onboarding` | Goal/preferences |
| A03 | `/settings?section=:section` | Account, notifications, privacy, language, plan, calendar |
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
| P01 | Parent route + `panel=professor` | Contextual assistance |
| F01 | Parent S01/S02/C03 route unchanged | Focus/pause sheet |
| N01 | Parent route unchanged | Bell inbox |
| Q01 | Parent route unchanged | Quota dialog |

Desktop: 208px left rail, 64px header, breadcrumbs left/bell-avatar right; subject title/actions above tabs. Mobile: 56px header, 64px bottom bar plus safe area; subject title/Professor, owning view's primary action, tabs. Never duplicate Continue beside another primary. One right panel; non-focused sheets fit between header/navigation.

Every active S02/C03 enters the task-focused shell; active E02 also hides global navigation/workspace tabs. Optional timer/mute does not change this. Setup/summary/report/paused study restore navigation. Pause retains no-help restrictions; exit/refresh retains exam deadline. Panels preserve parent/draft/focus/return; Back closes panel before leaving task.

## Screen specifications

All surfaces inherit shell/save badges/accessibility/recovery. D = desktop; M = mobile. State-specific CTAs replace defaults; one primary owns each view. Loading is not empty; missing IDs show "Not available" with recovery.

### A01 Authentication
Layout: D 480px centered form: logo/value top, sign-in/create toggle/email/password middle, primary/privacy bottom. M same order, no global navigation. Allow password managers/paste; no cognitive puzzles.

Entry/exit: signed-out root/link -> A02/retained target. Primary Sign in/Create account; secondary switch/reset password. Data: auth, return target, non-secret fields. States: empty labeled fields; loading "Signing in..."; error linked summary retains email, not exposed secrets.

### A02 Goal and preferences
Layout: D centered stages: title/step top; Understand course/Prepare exam/Self-study/Unsure, optional level/date/availability, language/input preference middle; Continue/Back bottom. M stack, retain fields.

Entry/exit: A01 -> G02. Primary Continue; secondary Back/skip optional fields. Data: milestone/goal/timezone/preferences/dates. States: empty Unsure/defaults; loading retained form; error invalid date/save with Retry. No learning-style labels or microphone permission.

### A03 Account and settings
Layout: D sections left, controls center, policy right, Save bottom; M section picker then controls. Account/language/privacy/notifications/plan/calendar contain retention/export/deletion, quiet mode/XP visibility, credentials/sign-out, locale, reminder channels/quiet hours, and enabled integration controls.

Entry/exit: avatar -> parent. Primary Save changes/selected privacy action; secondary Cancel/Back. Data: settings/consent/capabilities/job revisions. States: empty "Not connected"; loading saved values locked; error retains edits, never false deletion/consent. Hide unavailable plan/calendar sections.

### G01 Today
Layout: D next-action/resume top-main, reviews/subject shortcuts below, nearest exam/availability right; M stack in that order. Show reason/checkpoint, not a mascot hero.

Entry/exit: return/S03 -> S01/S02 or reconciled E02/E03. Primary Start/Resume, empty Add subject; secondary Change action/snooze. Data: unfinished work/blocks/reviews/gaps/concept. States: empty C01 invitation; loading skeleton; error G02/Retry, no invented urgency.

### G02 Subjects
Layout: D title/Add subject top, course-card grid; M stacked. Cards: name, source status, supplied exam date, last concept, Continue, archive/remove menu.

Entry/exit: Subjects -> C01/C02 processing/W01 ready. Primary Add subject; secondary card Continue. Data: IDs/readiness/bookmarks/dates. States: empty upload/topic/Unsure; loading skeletons; error Retry retains cards. Confirm removal with source/evidence impact preview.

### G03 Planner
Layout: D date/timezone/Add toolbar top, week center, G05 right, backlog below; M agenda, calendar toggle, editor sheet. Core manual blocks/reviews; generated planning Next.

Entry/exit: Planner/W03/S03 -> G05/S01. Primary Add study block; secondary Add exam/view toggle. Data: availability/deadlines/blocks/evidence/plan revision. States: empty manual start; loading agenda; error cached plan marked stale/Retry. Elapsed time never marks completion.

### G04 Overall Progress
Layout: D subject summaries top, evidence center, concept profile below, private discoveries side; M same stack. No subject tabs. Counts/dates distinguish pending application and unchecked retention.

Entry/exit: overall Progress -> W05/W08. Primary Review suggested concept; secondary filters/hide XP. Data: evidence/profile revisions, subjects, labeled self-reports. States: empty "No evidence yet"/choose subject; loading not zero; error Retry. Next synthesis names observations, never traits/styles.

### G05 Planner entry editor
Layout: D right editor, centered on direct route: type/title top; subject/concept/date/start/duration/timezone/recurrence/availability middle; conflicts then Save/Cancel bottom. M sheet with identical order.

Entry/exit: G03/W03 -> G03. Primary Save entry/Confirm plan; secondary Cancel/reschedule/shrink/skip. Data: draft/exam/capacity/conflicts/revision. States: empty fields; loading retains inputs; error alternatives/backlog. Save selected revision only; Undo restores prior plan without unrelated moves.

### C01 Create subject
Layout: D upload/topic choice top; name and Course/Notes/Past exam role middle; picker/paste/topic then limits/rights/privacy and Create bottom. M stack/per-file details. Core text PDF/PPTX/TXT/MD/paste; scanned/photo OCR Next.

Entry/exit: G02 -> allocated C02. Primary Create subject; secondary Cancel/I'm unsure. Data: name/topic/files/role/capabilities/rights. Proposed defaults: 20MB/file, five/batch, 200 pages/file; show configured limits before selection. States: empty choice; validating rows; per-file errors retain accepted files, offer replace/conversion.

### C02 Processing and scope confirmation
Layout: D file/jobs left, chapter/concept/prerequisite preview center, cited-page inspector right, confirmation bottom; M status/scope/source sheet. Phases: selected/validating/uploading/queued/quarantined-scanning/extracting/awaiting-confirmation/needs-attention/cancelled/ready, no invented extraction percentages.

Entry/exit: C01/W04 -> C03 initially/W01 revision. Primary Confirm scope; secondary rename/reorder/exclude/retry/cancel. Data: source/jobs/extraction/page mappings/concepts/uncertainty. States: empty replace/paste/topic; loading actual phase/upload bytes; error retains partial success. Only confirmed ready revisions feed tasks; reject cancelled callbacks.

### C03 Optional diagnostic
Layout: D focused Exit/objective/item/save header, recall prompt/text/I don't know center, Check bottom. M same, no global bar; pause restores navigation. Sample definition/relationship/application, not ability verdict.

Entry/exit: C02 -> W01. Primary Check baseline answer; secondary Skip/orientation. Data: task/rubric/responses/assistance/checkpoint. States: empty pool permits skip; task loading; error retains answer, uncertainty unscored. Skip saves insufficient evidence, never zero ability/locks/setup XP.

### W01 Roadmap
Layout: D unit/path main, W06 right, foundations beside nodes; M vertical path/inspector sheet. Unit picker, evidence legend, Return to next concept. Open inspector replaces map's primary with Learn.

Entry/exit: ready subject -> W06/S01. Primary Continue suggested concept; secondary any node/earlier unit. Data: graph/prerequisites/bookmark/dated evidence/due flags. States: empty C02; loading reserved path; error Retry scope. No locked/damaged nodes for unseen or supported learning.

### W02 Practice selection
Layout: D reviews top, concept/input filters middle, exercise/fresh-check cards below, Start bottom; M Filter disclosure/stack. Cards show objective/origin/mode and only supplied estimates.

Entry/exit: Practice -> S01. Primary Start selected practice; secondary concept/filter. Data: pool/reviews/capabilities/scope. States: empty Learn W06/explicit generation; loading pool; error retains filters/Retry. Paper/Code/lab availability explains capability, not a fake launcher.

### W03 Exams library
Layout: D title/New mock top, Prepare/deadline then origin/policy filters/papers/attempts; M same stack. Items/pools/attempts show provenance and coached/closed-book policy.

Entry/exit: Exams -> E01/E02 resume/E03/G05 preparation. Primary New mock exam; secondary Prepare/filter/report. Data: pools/verification/deadlines/status. States: empty verified pool explains alternatives; loading attempts; error Retry preserves filter. Uploads start unverified; generated variants remain generated.

### W04 Resources
Layout: D name/type/status/version source table top, Add right, replace/remove menus; generated summaries/definitions/retrieval aids separate below. M stacked cards/sections. All private; aid generation Next.

Entry/exit: Resources/More -> W07/C02 add/replace. Primary Add source; secondary Open/replace/remove. Data: revisions/content/status/linked attempts. States: empty upload/topic; loading skeletons; error keeps prior version. Removal creates citation tombstones, not rewritten evidence; generated aids are labeled separately.

### W05 Subject Progress
Layout: D named-subject filters top, concept matrix center, receipts below; M explanation/follow-up/application/retention cards. Mixed/contradictory evidence stays beside earlier success; no mastery percentage.

Entry/exit: subject Progress/More -> W06/W08. Primary Review selected gap; secondary inspect/filter. Data: subject evidence/help/variation/dates/uncertainty/profile sync. States: empty starter check; loading placeholders; error retains receipts/Retry. Overall profile stays at G04.

### W06 Concept inspector
Layout: D 320px roadmap panel: title/close top, objective/prerequisites/citations/evidence middle, Learn bottom; M same sheet/Return to roadmap. Foundation/Continue anyway remain optional.

Entry/exit: W01/W05 -> S01/map. Primary Learn this concept; secondary Practice/foundation. Data: concept/source/prerequisite reason/bookmark/evidence. States: empty "Not checked yet"; loading inspector; error Retry/generated orientation. New selection replaces inspector, never saved task.

### W07 Cited document viewer
Layout: D thumbnails left, document/text center, source/version/notes right, search/page top, Return bottom. M document/page-source sheets/Return. Extracted text and local equation/image zoom; annotations/bookmarks Next.

Entry/exit: citation/W04 -> cited page -> origin. Primary Return to task/resources; secondary search/permitted download. Data: revision/page/span/position/return/policy. States: empty tombstone; loading page; error W04 replace/Retry. Guard target-answer previews and locked assessments.

### W08 Evidence receipt
Layout: D task/date/origin/mode top, answer/help center, five criteria right, source/version/dispute/history below; M same sequence. Audio quotes: sentence IDs, available verified timestamps; playback only while retained.

Entry/exit: W05/G04/S03/E03 -> parent/S01. Primary Try fresh check; secondary Challenge/export/delete. Data: confirmed revision/rubric/quotes/sources/provenance/status. States: no receipt offers Check job/Return; loading no score; error Retry. Preserve prior revisions during dispute/deletion; label missing audio.

### S01 Session setup
Layout: D objective/mode top, concept/time/input/focus middle, source/assistance/retention then Start bottom; M stack above global bar. Learn is a mode; Review shows adjustable date. Inputs Text/Voice, Paper/Code when enabled.

Entry/exit: G01/W02/W06 -> S02. Primary Start session; secondary goal/input/Back. Data: session/objective/capability/policy/reservation. States: empty W06; preparing; error safe alternative/Q01. Reserve explanation/follow-up/transfer before capture/typed assessment, never payment during speech.

### S02 Active learning workspace
Layout: D focused header: Save and exit left, objective/stage center, checkpoint/Focus right. Recall/prompt above central input; Text/Voice selectors below prompt; Paper/Code only when enabled. Feedback replaces or follows the answer panel; P01 occupies right rail when permitted. Bottom primary is state-specific Check/Continue; Help is secondary. M prompt -> status -> input -> feedback -> actions; no global bar while active.

Entry/exit: S01/resume -> F01 pause, W07 citation if allowed, S03 finish. Data: session/task/rubric/source versions, stage/phase/mode, drafts, assistance, policy, jobs. States: missing task offers recover/abandon; loading retains prompt/draft; error overlay restores return phase. Learn uses recall, orientation, cited chunk, example, retrieval; reading creates exposure only. Paper crop/extraction and code editor/output are modes here, not new destinations. Audio states follow below.

Next Paper mode: preview/crop/rotate center, extracted workings beside it; mobile stacks image then text. Bottom Confirm workings -> Check; secondary replace/use text. Highlight uncertain extraction; preserve original/crop revisions. Next Code mode: task/language/runtime limits top, editor left/output-tests right; mobile stacks editor/output. Primary Run tests -> Submit reasoning, secondary edit/text fallback. Running/error states retain code; an accessible text editor replaces unsupported rich editing. Neither mode adds a route.

### S03 Session outcome
Layout: D outcome/stages top, receipts/gaps center, optional reflection/review date below, Finish bottom; M same stack/global nav. Recognition only after accepted evidence.

Entry/exit: S02 -> G01/W08/G05 or preserved S02 parent context. Primary "Finish and save review date" for standalone sessions; when a parent bookmark exists, primary "Return to original task" saves child evidence before resuming the preserved S02 parent context; secondary evidence/skip/change date. Data: receipts/profile/reflection/due date. States: empty "Checks pending"; loading/profile pending; error preserves acknowledged evidence/Retry. Three-day default is adjustable, not optimal/mastery evidence.

### E01 Mock exam setup
Layout: D scope/origin/policy top, count/timed-untimed duration/accommodations middle, origin preview/Start below; M same order, advanced format disclosure. Core text; oral Later.

Entry/exit: W03 -> E02 after reservation/start. Primary Prepare then Start exam; secondary Cancel/adjust. Data: pool/task/verification/policy/duration/quota. States: empty verified pool requires broadening; generating; error excludes invalid items. Offer untimed before start; exam label alone establishes no essential timing exception.

### E02 Active mock exam
Layout: D Exit/title/deadline/save top, question index left, prompt/input center, answered/flagged status right, controls bottom; M header index/answer stack/bottom actions, no global bar. Primary Next, then Review answers/Submit; secondary Previous/Flag/Save and exit, Help only for coached policy.

Entry/exit: E01/G01 -> E03/exit G01. Data: server start/deadline/offset/items/policy/answer checkpoints. States: empty reconciles run; loading preserves deadline; error/offline retains drafts with Retry/timing-unverified status. Review lists unanswered/flags; confirm Submit or Keep working. Closed-book denies tutoring/resources/corrective feedback across requests; coached P01 help is labeled. Exit retains timer; expiry submits accepted work once.

### E03 Exam report
Layout: D submission/policy/origin top, answer/criterion table center, gaps/repair queue below, Practice bottom; M item cards. Label scored/provisional/assisted/timing-unverified/unavailable distinctly.

Entry/exit: E02 -> W08/S01. Primary Practise selected gaps; secondary receipt/challenge. Data: submission/deadline/accepted-unsynced revisions/evidence. States: empty grades pending; loading submission; error Retry same jobs. No predicted marks/readiness; late drafts are separate artifacts, not timed success.

### P01 Contextual Professor
Layout: D right panel: context/close top, help step/citations middle, scoped composer/Return bottom. M focused viewport or non-focused sheet. No companion distraction during concentration.

Entry/exit: W06/W07/S02/coached E02 -> parent. Primary Try step/Ask about concept; secondary next level/Return. Data: context/help/disclosure/source revision. States: empty choose concept; response loading; error clarification/Retry. Off-topic -> W01. Locked transfer offers conversion; closed-book exam offers Return only, never policy switching.

### F01 Focus and pause sheet
Layout: D header sheet: task/checkpoint top, optional timer/in-app mute/quiet middle, Save and pause bottom; M content sheet. Timer off/custom; no OS blocking or time credit.

Entry/exit: S01/S02/C03 -> pause/G01/active task. Primary Save and pause; secondary Stay/Resume/timer. Data: cursor/drafts/preferences/checkpoint/location/return phase. States: empty Timer off; saving pending; error Retry/explicit unsaved exit. Finalize recoverable capture before leaving; exam exit uses deadline warning.

### N01 Notification inbox
Layout: D bell panel: title/unread top, review/block/job notices middle, settings bottom; M same sheet. Queue nonessential focused notices; recording permits only capture-critical status.

Entry/exit: bell outside focus -> session/G03/C02/parent. Primary Open reminder; secondary Mark read/settings. Data: IDs/targets/read/quiet preferences. States: empty No reminders; loading list; error Retry. Browser permission only after intentional Next opt-in; in-app notices need none.

### Q01 Quota boundary dialog
Layout: D modal: usage/reset/reason top, pending action/alternatives middle, free continuation bottom; M same sheet. Never mid-recording/answer/exam upsell.

Entry/exit: failed reservation -> preserved intent. Primary Continue with resources; secondary Wait/Retry/enabled Later plan. Data: entitlement/reset/reservation/intent. States: unknown Checking availability; loading no invented price; error Retry/offline draft. Storage exhaustion is separate; close never erases work.

## Audio explain back

Core flow: S02 -> W08 receipts/S03-G04-W05 summaries. Show one focused relationship/example/limit prompt, objective, applicable criteria; never a duration target. Example: "Explain why system boundaries matter for conservation of energy; give one situation where your assumptions fail." Domain-approved versions supply essentials/citations.

D prompt above recorder/editor, feedback rail right; M prompt/status/response/evidence/actions. No voice-quality meter, companion/XP/celebration during capture/transfer. No autoplay. Text has equivalent criteria/no-help eligibility.

Capture through transfer stays in S02; Reflect opens S03. Reflection/profile closure belongs only there; returning shows the saved reflection, never asks again.

| Phase | Primary CTA | Secondary CTA | Transition / visible contract |
| --- | --- | --- | --- |
| Permission intent | Enable microphone | Use text | After quota reservation, disclose recipients/retention; intentional activation requests audio only. |
| Permission pending | Waiting, disabled | Use text | Grant -> ready; rejection -> blocked. After 10s say still waiting; do not infer denial. |
| Blocked | Use text | Try microphone again | Cause-specific guidance; unsupported/insecure retry disabled until capability changes. |
| Ready | Start recording | Use text | "Microphone connected. Recording has not started." Start acknowledgement enters recording. |
| Starting command | Starting, disabled | Stay here | Prevent duplicate recorder commands; do not move focus. |
| Recording | Finish recording | Pause | Text status and elapsed capture time, excluding pauses; no minimum duration. |
| Pausing command | Pausing, disabled | Stay here | Only acknowledged pause enters paused. |
| Paused | Resume | Finish recording | "Audio is not being added. Microphone connection remains open." |
| Resuming command | Resuming, disabled | Stay here | Only acknowledged resume enters recording; never automatic after interruption. |
| Finalizing | Preparing playback, disabled | Stay here | Wait for final data/stop, release tracks; invalid take -> capture error. |
| Capture interrupted/error | Review captured part | Record again / Use text | Review only playable acknowledged data; missing/uncertain work unscored. |
| Playback | Use recording | Record another take | User-controlled play/seek; retake creates revision, preserves prior draft until replaced deliberately. |
| Typed edit | Review text | Save and leave | Nonempty text -> confirmation; preserves audio draft on explicit mode switch. |
| Uploading | Uploading, disabled | Save and leave | Verified receipt -> transcription; display measurable bytes only. |
| Transcribing | Preparing text, disabled | Save and leave | No grading yet; output -> confirmation. |
| Transcript confirmation | Confirm and assess | Edit text | Original/corrected text, uncertainty, player if retained, separate supplement; freeze confirmed revision. |
| Assessment | Assessing, disabled | Save and leave | Valid rubric/evidence acknowledgement -> feedback; unreliable output -> unscored/recovery. |
| Explanation feedback | Answer one follow-up | Review evidence | Names demonstrated/missing ideas; generates one persisted targeted question. |
| Follow-up preparation | Preparing question, disabled | Save and leave | Retry same job/question ID, not a new random question. |
| Follow-up introduction | Answer follow-up | Save and leave | Relationship/example/limit question; reuse recording/text/confirmation phases. |
| Follow-up feedback | Try new application | Review evidence | Prepare a genuinely unfamiliar task before mode commitment. |
| Transfer preparation | Preparing task, disabled | Save and leave | Validate novelty/rubric; reconcile same job before reveal. |
| Transfer introduction | Start without in-app help | Use guided help | Commit mode before revealing task; describe blocked help/resources. |
| Transfer answer | Current capture/text CTA | Current pause/edit CTA | Separate "Use guided help" action opens conversion; lock persists through confirmation/grading. |
| Guided conversion confirmation | Switch to guided practice | Cancel | Pause capture; preserve current draft; cancel remains paused. |
| Conversion pending | Switching, disabled | Stay here | Unlock only after committed revision; failure offers Retry while locked. |
| Unscored feedback | Review answer | Keep unscored | Clarify confirmed revision or save unscored with later stages pending; no independent success. |
| Transfer feedback | Reflect | Review evidence | Accepted result separates no-help application from explanation/retention. |
| Delayed review introduction | Start review without in-app help | Use guided practice | Commit independent-review policy; reuse answer/confirmation phases. |
| Review feedback | Finish | Review evidence | Save actual interval/help; no automatic follow-up chain. |
| Reflection, S03 | Save reflection | Skip reflection | Optional strategy note; cannot change the evidence score. |
| Profile pending, S03 | Updating, disabled | Finish with update pending | Say evidence saved only after receipt; reconcile profile update once. |
| Complete | Finish | View evidence history | S03; application and retention displayed separately. |
| Job recovery | Check status / Retry | Save and leave | Reconcile receipt/job before restarting; restore actual return phase. |

Capture requires secure context, permission, and embedding policy. `NotAllowedError` includes policy/context/denial; `NotFoundError` means no matching input. Test `MediaRecorder.isTypeSupported`, negotiate actual WebM/Opus or MP4/AAC where supported; never assume codec or combine incompatible takes. Inexact chunks/background interruptions require a separate elapsed timer. ([Capture, R19](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)) ([Recorder, R20](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)) ([Chunks, R21](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event))

After 10s without command acknowledgement, stop tracks/recover late playable data. Stop stale grants and tracks on exit/text switch. Cause copy: "Access blocked here; check browser/system settings", "No microphone found; connect one", "Microphone could not open; check input device", "Recording unavailable in this browser/page", or "No playable audio captured". Each offers text; no empty take graded.

| Criterion | Evidence requirement |
| --- | --- |
| Correctness | Specific accurate claim or misconception, quoted from confirmed text |
| Essential coverage | Predeclared essential ideas covered/missing, not word count |
| Why/relationships | Causal link, comparison, assumption, or justified step |
| Example/application | Mapping an example/problem to the concept |
| Limits | Boundary/exception only when applicable; otherwise N/A |

Use absent/contradicted, partial, demonstrated: optional 0/1/2; `null` unscored, N/A excluded. No mastery percentages or uncertainty-obscuring totals. Link confirmed quote/sentence, verified timestamp if available, course page/span or generated basis. Never assess duration/accent/fluency/emotion/silence. Unknown meaning -> clarification/unscored, not zero.

Confirm requires nonempty text and resolved or explicitly unresolved spans. Unresolved score-relevant meaning stays unscored. Preserve original ASR/corrections; added reasoning is a separate supplement, not retroactive audio evidence. Assess only confirmed revision; later edits supersede prior grades. W08 disputes preserve history without duplicate success.

Persist no-help policy across routes/tabs/devices until terminal evidence/abandonment acknowledgement; deny hints/lessons/tutoring/revealing sources/prior feedback. Allow prompt/current replay/scratch/accessibility/save/pause. Conversion asks "Keep your work and switch to guided practice?", preserves work, commits irreversibly before unlocking. Cancel stays paused; failure locked/Retry. Serialize conversion/evidence revisions; raced guided results cannot count independent. Apply the same policy to independent-review; guided-review records assisted retrieval. External AI scripts remain possible: "Completed without in-app help", never cheating-proof.

Separate explanation/follow-up/transfer/review evidence. Transfer requires predeclared correctness/coverage/application and interpretable evidence, not length/total. Adjustable three-day review is a hypothesis; only actually delayed no-help performance adds retention evidence. Reflection remains self-report.

## Use case catalogue

Each case specifies trigger/precondition, numbered actions through existing screens, alternative/error, persisted result, and observable acceptance. Core means Core beta; Next/Later follow the scope above. Shared recovery/permission policies apply even when not repeated.

Illustrative first-time walkthrough: A01 sign-in -> A02 Understand course/Unsure -> G02 Add -> C01 engineering PDF -> C02 confirm extracted concepts -> optional C03 -> W01/W06 choose concept or foundation -> S01 goal/input -> S02 recall, cited learning, early hint, explain-back, follow-up, unfamiliar application -> S03 inspect evidence/reflect/book review -> G01. Uncertainty can stop scoring without stopping learning.

Returning walkthrough: G01 explains unfinished session/live exam -> current block -> due review -> exam gap -> next concept priority. Resume restores acknowledged answer/context; a due review uses S01/S02 with a fresh no-help task. Change action chooses another subject/time without punishment. Exams retain their original deadline; an expired run opens E03, not a reset timer.

### UC01 Onboard | Core
Trigger/precondition: first visit, setup incomplete. Flow: 1. A01 authenticate/create. 2. A02 choose goal or Unsure, optional dates/input preferences. 3. Continue to G02. Alternative/error: validation retains non-secret fields; Back preserves preferences. Persist: setup milestone, timezone/preferences. Acceptance: Unsure and skipped dates reach C01 without compulsory diagnosis or microphone permission.

### UC02 Return and restore | Core
Trigger/precondition: return with saved work. Flow: 1. Authenticate if needed at A01. 2. G01 inspect Resume reason. 3. S02 reconcile checkpoint and resume explicitly. Alternative/error: newer writer offers read-only/takeover; missing local audio offers text/retake. Persist: same session/task and selected branch. Acceptance: no duplicate attempt; restore only acknowledged work, with truthful save badge.

### UC03 Upload course | Core
Trigger/precondition: Add subject, permitted course materials. Flow: 1. G02 -> C01. 2. Name subject, select source role/files, acknowledge rights. 3. Create -> C02 jobs. Alternative/error: unsupported/encrypted file stays flagged while usable files proceed. Persist: subject, metadata, source/job IDs. Acceptance: navigating away/reloading restores job state; unsent binary loss requests reselection, not false completion.

### UC04 Recover ingestion | Core
Trigger/precondition: C02 job needs attention. Flow: 1. Inspect per-file cause. 2. Retry same job, replace, or exclude. 3. Review successful scope. Alternative/error: unreadable text offers paste or guided-topic continuation. Persist: successes, replacement revision, cancellation generation. Acceptance: retries do not duplicate sources or erase partial success; late cancelled responses cannot mark ready.

### UC05 Guided self-study | Core
Trigger/precondition: no usable upload or unsure topic. Flow: 1. C01 choose Unsure/guided topic. 2. Select broad discipline. 3. C02 answer one clarification and confirm starter scope. Alternative/error: ambiguity remains visibly provisional; change discipline. Persist: generated scope and basis. Acceptance: start without knowing prerequisites; generated content is never labeled extracted from the learner's course.

### UC06 Confirm or revise scope | Core
Trigger/precondition: proposed extraction exists. Flow: 1. C02 inspect source mappings. 2. Edit labels/prerequisites, exclude uncertain spans. 3. Confirm -> C03 initially/W01 for revision. Alternative/error: save fails without applying new scope. Persist: graph/source revision. Acceptance: only ready confirmed sources feed tasks; historical attempts keep their original mapping and rubric.

### UC07 Diagnostic or skip | Core
Trigger/precondition: confirmed scope, unknown baseline. Flow: 1. C03 attempt recall/sample. 2. Check or request orientation. 3. Finish/skip -> W01. Alternative/error: unavailable pool permits skip; uncertain grade unscored. Persist: dated baseline/assistance or insufficient evidence. Acceptance: skipped diagnostic never creates zero ability or locks concepts.

### UC08 Select concept | Core
Trigger/precondition: roadmap available. Flow: 1. W01 inspect any node. 2. W06 read objective/evidence/prerequisites. 3. Learn/Practice -> S01. Alternative/error: empty history offers starter session; missing concept revision requests scope refresh. Persist: selected concept/version. Acceptance: unseen and advanced nodes remain inspectable/startable; suggestion is not a hard gate.

### UC09 Prerequisite detour | Core
Trigger/precondition: guided task/concept suggests a foundation. Flow: 1. W06/S02 accept detour. 2. S02 foundation mini-session. 3. S03 Return to original task. Alternative/error: Continue anyway retains target; independent mode requires UC15 conversion first. Persist: parent bookmark, original draft, foundation evidence. Acceptance: detour restores exact context; no forced foundation completion.

### UC10 Start recommended session | Core
Trigger/precondition: G01 has eligible recommendation. Flow: 1. Read reason. 2. S01 adjust goal/input/time preference. 3. Reserve/start S02. Alternative/error: stale recommendation offers Change -> W01; reservation failure -> Q01. Persist: objective, queue, reservation. Acceptance: one dominant action and an override; no invented available study time.

### UC11 Structured Learn | Core
Trigger/precondition: selected concept needs explanation. Flow: 1. S02 recall or I don't know. 2. Read cited chunk and different example. 3. Retrieve/apply before continuing. Alternative/error: source unavailable offers replace or explicitly generated orientation, not a false citation. Persist: recall, exposure, lesson cursor/source revision. Acceptance: reading/path completion alone creates no independent-performance evidence.

### UC12 Submit exercise | Core
Trigger/precondition: interpretable response draft. Flow: 1. S02 answer. 2. Check reasoning. 3. Inspect criterion feedback, revise or continue. Alternative/error: job timeout/malformed grade retains draft; uncertainty null. Persist: accepted response/rubric/help receipt. Acceptance: repeated Check/retry creates one assessment commit; feedback points to the actual answer and source basis.

### UC13 Get early support | Core
Trigger/precondition: blank guided attempt, student cannot begin. Flow: 1. S02 I don't know/Explain prompt. 2. P01 clarify objective or strategy. 3. Return to S02 and attempt. Alternative/error: unclear prompt offers one clarification or prerequisite detour. Persist: observed assistance. Acceptance: no minimum typing requirement, penalty, or full target solution at first help.

### UC14 Escalate assistance | Core
Trigger/precondition: coached attempt still difficult. Flow: 1. P01 strategy cue. 2. Request substep then different example. 3. Confirm end/reveal target solution. 4. S02 fresh check. Alternative/error: reject reveal or choose detour. Persist: help/reveal provenance, ended assisted target. Acceptance: solution payload is withheld until authorized; revealed target never becomes independent success.

### UC15 No-help check and crossover | Core
Trigger/precondition: unfamiliar validated task ready. Flow: 1. S02 commit no-help mode. 2. Answer/confirm/submit. 3. Commit evidence -> S03. Alternative/error: Use guided help pauses, confirms conversion, preserves work, unlocks only after acknowledgement; cancel stays paused. Persist: novelty/mode/revision/conversion. Acceptance: direct hint/source requests denied while locked; guided result cannot retain independent status, including raced saves.

### UC16 Pause and resume | Core
Trigger/precondition: active study interruption. Flow: 1. S02 -> F01. 2. Pause/finalize capture, Save and pause. 3. G01 -> explicit Resume S02. Alternative/error: local-only acknowledgement restricts resume to that device; failed save requires retry or deliberate unsaved exit. Persist: cursor/drafts/lock/checkpoint. Acceptance: navigation returns when paused; no automatic recording restart or bypass of no-help policy.

### UC17 Complete and reflect | Core
Trigger/precondition: session ended, committed or pending checks. Flow: 1. S03 inspect stage receipts. 2. Save/skip reflection. 3. Accept/change delayed review, finish G01. Alternative/error: profile pending remains retryable without inventing success. Persist: reflection, receipts, review booking/profile revision. Acceptance: application and retention stay separate; time/audio length earns nothing.

### UC18 Delayed review | Core
Trigger/precondition: actual later review due. Flow: 1. G01 -> S01 Review. 2. S02 fresh unaided task, confirmed answer/check. 3. S03 receipt. Alternative/error: snooze or supported repair records assistance; failed/uncertain result recommends revisit, not punishment. Persist: elapsed interval/task/evidence. Acceptance: same-session repeat cannot be labeled retention; date and help status are visible.

### UC19 Paper response | Next
Trigger/precondition: eligible task, OCR integration enabled. Flow: 1. S02 Paper attach JPEG/PNG. 2. Crop/rotate with keyboard alternatives. 3. Confirm extracted workings, distinguishing corrections/additions. 4. Check. Alternative/error: illegible image retains artifact and offers text; no grading unconfirmed extraction. Persist: original artifact, crop/extraction revisions, assistance. Acceptance: switching modes loses no acknowledged work; OCR uncertainty remains unscored.

### UC20 Code response | Next
Trigger/precondition: coding task, approved isolated runner available. Flow: 1. S02 Code edit. 2. Run. 3. Inspect output/tests. 4. Submit explanation/code. Alternative/error: timeout/unavailable runtime retains code, offers text/pseudocode. Persist: code/version, runner/test status, rubric evidence. Acceptance: execution failures are not comprehension errors; no network/secrets/host access, and runtime/time earns no reward.

### UC21 Audio explain-back | Core
Trigger/precondition: focused explanation task and reserved bundle. Flow: 1. S02 choose Voice/retention, enable/start. 2. Record/playback. 3. Confirm transcript/corrections. 4. Inspect cited rubric. 5. Answer one follow-up. 6. UC15 unfamiliar application, UC17 reflection. Alternative/error: denial/interruption/jobs offer recovery/text; uncertain meaning unscored. Persist: consent, takes, confirmed revisions, stage evidence. Acceptance: no assessment before confirmation; no accent/duration scoring or cheating-proof claim.

### UC22 Contextual Professor | Core
Trigger/precondition: W06/W07/S02/coached E02 context, help allowed. Flow: 1. Open P01. 2. Ask/read citation. 3. Try step/Return. Alternative/error: off-topic -> W01; closed-book denies help, transfer offers UC15 conversion. Persist: scoped conversation/assistance. Acceptance: close restores task/focus; URL/API changes cannot bypass policy.

### UC23 Focus controls | Core
Trigger/precondition: learner starts/concentrates on session. Flow: 1. S01 select quiet/timer preference. 2. S02 focused shell. 3. F01 adjust/pause/exit. Alternative/error: external distraction offers optional device reminder only. Persist: preference/session state. Acceptance: only in-app decoration/notices are muted; timer is optional and pause has no XP/evidence penalty.

### UC24 Exam preparation | Next
Trigger/precondition: declared deadline and concept evidence. Flow: 1. W03 Prepare. 2. G05 inspect proposed gap/review blocks within availability. 3. Confirm -> G03/G01. Alternative/error: overcapacity offers reduced scope or explicit uncovered backlog. Persist: exam-linked plan revision. Acceptance: every proposed block has concept/reason; no guaranteed readiness or invented exam date.

### UC25 Configure mock exam | Core
Trigger/precondition: eligible confirmed item pool. Flow: 1. W03 -> E01. 2. Choose scope, Verified-only/Generated-only/Mixed, policy, count, timed/untimed. 3. Preview, reserve, Start. Alternative/error: empty verified pool requires explicit filter change; invalid generated items excluded. Persist: immutable pool/rubric/policy. Acceptance: origin labels visible; no silent generated substitution or unverified scored items.

### UC26 Run timed exam | Core
Trigger/precondition: acknowledged E01 start/reservation. Flow: 1. E02 answer/flag/revisit. 2. Autosave. 3. Submit or server deadline -> E03. Alternative/error: exit/refresh/offline does not reset time; late drafts separate. Persist: start/deadline/checkpoints/submission. Acceptance: one submission; closed-book help denied; deadline freezes accepted answer scope while retaining timing-unverified unsynced work.

### UC27 Inspect exam and repair | Core
Trigger/precondition: submitted exam. Flow: 1. E03 inspect item origin/policy/criterion evidence. 2. W08 inspect answer. 3. Select gaps -> S01 repair. Alternative/error: pending/uncertain jobs remain provisional. Persist: report/repair queue. Acceptance: coached, timing-unverified, and no-help results are distinct; report cannot imply predicted university grades.

### UC28 Challenge assessment | Core
Trigger/precondition: receipt contains questionable judgment. Flow: 1. W08 select criterion/quote. 2. Add dispute or transcript correction. 3. Confirm reassessment request. Alternative/error: network failure retains dispute draft; unsupported evidence remains unscored. Persist: disputed/superseding versions and resolution status. Acceptance: old judgment remains traceable, never silently overwritten or counted as another success.

### UC29 Build planner | Core manual; Next generated
Trigger/precondition: subject and learner-supplied date/availability. Flow: 1. G03 Add -> G05. 2. Set timezone, exam/block/availability. 3. Save manual entry or confirm generated preview. Alternative/error: impossible workload leaves explicit unscheduled scope. Persist: availability, deadline, linked blocks/revision. Acceptance: confirmed schedule fits declared capacity; no automatic completion from calendar time.

### UC30 Resolve schedule conflict | Next
Trigger/precondition: moved block/deadline conflicts. Flow: 1. G03 select entry. 2. G05 compare alternatives. 3. Save chosen revision. Alternative/error: keep unresolved with warning; failed save preserves old plan. Persist: selected move/reminder revision, undo snapshot. Acceptance: no silent changes to unrelated blocks; Undo restores the acknowledged prior revision.

### UC31 Missed study block | Core status; Next suggestions
Trigger/precondition: scheduled time passed without completion evidence. Flow: 1. G01/G03 inspect missed block. 2. G05 reschedule/shrink/skip. 3. Save. Alternative/error: no slot keeps unscheduled backlog. Persist: missed/rescheduled/skipped state, reminder revision. Acceptance: no guilt copy, lost XP, or fabricated completion; existing concept evidence remains intact.

### UC32 Manage sources | Core
Trigger/precondition: own source changed. Flow: 1. W04 add/replace -> C02. 2. Confirm revised extraction. 3. Apply for future tasks; remove requires impact confirmation. Alternative/error: import failure keeps previous ready revision. Persist: source versions/tombstones, concept mappings. Acceptance: active lessons/attempts keep frozen versions; source deletion does not silently erase learner history.

### UC33 Follow citation | Core
Trigger/precondition: eligible source link. Flow: 1. W04/W08/S02 citation -> W07 exact page/span. 2. Search/read. 3. Return to origin. Alternative/error: deleted/unavailable source shows tombstone/Retry/W04 replace; locked assessment denies revealing preview. Persist: viewer position/return target. Acceptance: return restores answer/cursor; never cite a nonexistent page as verified evidence.

### UC34 Inspect subject evidence | Core
Trigger/precondition: learner opens W05. Flow: 1. Filter concept/date/stage. 2. W08 inspect answer/help/source. 3. W06/S01 choose review. Alternative/error: confirmed empty says insufficient evidence; failed fetch does not render zero mastery. Persist: filters/history view. Acceptance: every claimed stage links accepted receipts; contradictory and disputed evidence remains visible.

### UC35 Inspect learner profile | Core basic; Next synthesis
Trigger/precondition: overall Progress requested. Flow: 1. G04 compare subject evidence summaries. 2. Inspect concept observations/self-reports. 3. W05/W08 trace claims. Alternative/error: mixed evidence recommends review; pending updates reconcile. Persist: aggregate/profile revision, display preference. Acceptance: no personality/intelligence/learning-style label; all observations name concepts, dates, assistance, and supporting receipts.

### UC36 Configure notifications | Next
Trigger/precondition: signed-in learner requests reminders. Flow: 1. A03 notifications choose channel/quiet hours. 2. Intentionally request browser permission if selected. 3. N01 open current linked task/plan. Alternative/error: permission denial keeps in-app reminders; obsolete target reconciles. Persist: consent/channel/read status. Acceptance: no unsolicited permission prompt or interruption during recording, transfer, or exam.

### UC37 Privacy and account | Core
Trigger/precondition: authenticated data-control request. Flow: 1. A03/W08 inspect retention/action impact. 2. Choose audio deletion, full attempt/account deletion, consent withdrawal, or export. 3. Confirm and monitor job. Alternative/error: reauthentication restores preview for reconfirmation; failed deletion stays pending. Persist: action receipt; recompute derived evidence after full deletion. Acceptance: audio-only deletion preserves disclosed transcript history; full deletion removes content/derived evidence with honest backup status.

### UC38 Quota boundary | Core guard; Later premium
Trigger/precondition: costly new action lacks reservation. Flow: 1. Q01 show actual usage/reset. 2. Choose resources/offline draft/wait or enabled A03 plan. 3. Return preserved intent. Alternative/error: billing/service failure changes no draft; existing reserved bundle completes. Persist: reservation/pending intent, idempotent charge. Acceptance: no payment interruption during recording/exam, no retry double charge, no fabricated pricing.

### UC39 Calendar integration | Later
Trigger/precondition: local plan, enabled provider. Flow: 1. A03 calendar select permissions/direction. 2. Preview import/export/conflicts. 3. G03 confirm synchronization. Alternative/error: revocation disconnects without deleting local plan; retry reconciles external IDs. Persist: provider IDs/sync revision/consent. Acceptance: no duplicate events or silent conflict resolution; least necessary scopes and explicit direction.

### UC40 Extended modes/mobile | Later
Trigger/precondition: enabled eligible lab/oral mode or native client. Flow: 1. W02 -> S01 lab -> S02/S03, or W03 -> E01 oral mock -> E02/E03. 2. Apply existing mode/recording/timer policy. Alternative/error: unsupported capability offers normal text setup. Persist: mode/artifact/evidence revisions. Acceptance: same four destinations and canonical evidence semantics; responsive web already works without native installation.

## Feature placement and release scope

This matrix assigns an owning surface; references are launch/readback links, not duplicate pages. Every feature requires the shared save/recovery/accessibility contracts. Next/Later capabilities remain absent or truthfully unavailable until integrated.

| Feature | Owning surface; launch/readback | Priority | Dependency |
| --- | --- | --- | --- |
| Authentication/goals | A01/A02; avatar A03 | Core beta | Identity/return target |
| Account/language/privacy controls | A03; W08 attempt actions | Core beta; localized content Next | Consent/deletion/export jobs |
| Today/next action | G01; launches S01/resume S02 | Core beta | Checkpoints, reviews, recommendations |
| Subjects/creation | G02/C01 | Core beta | Source capabilities/rights |
| Extraction/scope/prerequisites | C02; W01/W06 display | Core beta | Versioned extraction/page mapping |
| Diagnostic | C03 | Core beta | Approved sampled tasks/rubrics |
| Roadmap/concept selection | W01/W06 | Core beta | Confirmed graph/evidence |
| Practice selection | W02/S01 | Core beta | Task pool/review dates |
| Learn/retrieval/exercise | S02; W06 launch | Core beta | Frozen lesson/task/source versions |
| Help ladder/Professor | P01; W06/W07/S02/coached E02 launch | Core beta | Policy-enforced disclosure/provenance |
| Focus/pause/resume | F01/S02; G01 resume | Core beta | Checkpoint/lease, optional timer |
| Voice/text explain-back | S02; W08/S03 readback | Core beta | Reservation, capture/ASR/confirmed rubric |
| No-help transfer/conversion | S02 | Core beta | Novel task validation/server policy |
| Reflection/profile update | S03; G04/W05 readback | Core beta | Accepted evidence/idempotency |
| Per-concept evidence/history | W05/W08 | Core beta | Stage/assistance/uncertainty revisions |
| Overall skill profile | G04 | Core beta basic; Next synthesis | Traceable aggregates, no trait labels |
| Review/manual agenda/deadlines | G03/G05; G01/S03 launch | Core beta | Learner dates/timezone/evidence |
| Conflict/repair planning | G05; W03 launch | Next | Availability, capacity, plan revisions |
| Exams/origin filters/timer/report | W03/E01/E02/E03 | Core beta text | Verified/generated pools, server deadline |
| Sources/cited viewer | W04/W07 | Core beta | Source authorization/version/tombstones |
| Disputes | W08; E03 launch | Core beta | Assessment revision/audit trail |
| Photos/OCR/paper workings | C01/C02 source; S02 response | Next | OCR confirmation/artifact storage |
| Code sandbox | S02; W02/S01 launch | Next | Isolated runner/test-policy review |
| Resource aids/annotations | W04/W07 | Next | Cited generation/annotation revisions |
| Private XP/discoveries | G04, W01, S03/E03 display | Next numeric XP; Core static evidence recognition | Deduplicated learning-event receipts |
| Reminders/inbox | N01; A03 preferences | Next | Opt-in channels/quiet hours |
| Cost protection/quota | Q01; S01/E01 reservation | Core beta | Actual entitlement/bundle reservation |
| Premium | A03 plan; Q01 link | Later | Approved pricing/billing policy |
| Calendar | A03 calendar; G03 results | Later | Provider scopes/deduplicated sync |
| Extended labs/oral mocks/native | S01/S02/S03, E01/E02/E03 | Later | Domain/runtime/platform validation |

Optional XP pilot values: +5 first reasoned attempt, +10 meaningful correction with or without help, +15 distinct no-help application, +15 eligible later retrieval. These are product hypotheses, not research-derived optimal amounts. Award once per task family/event/review occasion; retries/revisions cannot farm rewards. Never subtract for help, mistakes, missed days, pauses, or uncertainty. XP never gates learning or determines evidence/grades. Hideable discoveries persist when later evidence suggests review; no destroyed rewards or streak-repair purchases.

## Accessibility and responsive behaviour

Target WCAG 2.2 AA across complete processes, not certified conformance. Typical normal text needs 4.5:1; large text 3:1, generally >=24px regular or approximately 18.67px bold. Relevant identifying controls/graphics need 3:1 against adjacent colors. AA target minimum is 24x24 CSS pixels with specified exceptions; 44x44 is the Enhanced/AAA threshold and ThinkFirst's stronger touch recommendation. ([WCAG, R11](https://www.w3.org/TR/WCAG22/)) ([Target size, R14](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html))

- Visible persistent keyboard focus; AA prohibits complete author-created obscuration, while ThinkFirst aims for full visibility. Sticky actions become inline when zoom/keyboard would cover fields. ([Focus, R15](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)) ([Obscuration, R16](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html))
- Semantic landmarks/headings/buttons/forms; visible labels match accessible names. Complete keyboard/SR flows, skip links, error summary linked to fields, focus restored on panel close. No drag-only crop/upload, hold-to-record, hover-only help, or unrestricted single-letter shortcuts.
- Reflow at 320px, 200% text resizing, user spacing overrides, portrait/landscape; equation/table overflow stays local with accessible text/list equivalents. Use wrapping labels and minimum heights, not clipped translated buttons.
- Announce phase/status once politely; actionable errors persist. Do not announce elapsed seconds/waveform/transcript tokens. Keep focus during jobs; deliberate next-stage action focuses its heading. Modal focus is constrained; Escape cancels/restores origin.
- Typed equivalent to voice; accessible player and adjacent transcript. Prerecorded audio-only alternatives are Level A, subject to the text-alternative exception; do not mistake optional timestamps for the requirement. ([Transcripts, R17](https://www.w3.org/WAI/media/av/transcripts/))
- Reduced motion/quiet settings preserve all work and recognition. Interaction-animation disabling is AAA, deliberately adopted beyond the AA target. No autoplay.
- Arabic uses logical start/end layout, page/content language and direction, isolated mixed-direction numbers/formulas, and non-mirrored audio chronology. Do not require standard Arabic pronunciation for credit; dialect/equation ASR coverage needs native-user validation.

## Loading error and recovery states

Use honest checkpoints: "Synced", "On this device", "Not saved", with acknowledged revision/time. Browser storage is best-effort, evictable, and can fail; local persistence is not an exact recovery guarantee. ([Storage, R22](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)) Clear actionable inline messages and linked error summaries follow WAI guidance. ([Feedback, R18](https://www.w3.org/WAI/tutorials/forms/notifications/))

| Condition | Required action and retained truth |
| --- | --- |
| Background/track interruption | Pause on observable suspension; ended track finalizes playable data. Never auto-resume; review captured part. Undelivered/corrupt chunks cannot be promised. |
| Upload stalled/offline | After 30s without measurable progress, show stalled; retain acknowledged local draft. Retry reconciles upload receipt/missing parts, not duplicate takes. |
| Extraction/transcription/grading slow | After 60s show delayed; after 180s offer Check status/Save and leave. Local timeout is not server failure; resume existing job. |
| Transient network/429 | At most three automatic retries at 1/2/4s, respecting Retry-After, then explicit Retry. No extra attempt/charge for infrastructure retry. |
| Invalid/unreliable grading | Keep confirmed response; show insufficient reliable information, null criteria, review/retry. Never convert an invalid output into zero. |
| Identity expired | Finish capture locally, then reauthenticate before sync; preserve task/mode/deadline. No sign-in/payment dialog interrupts speech. |
| Storage exhausted/evicted | Explain exact last checkpoint; memory-only recovery offers upload/download when available, text/retake otherwise. Warn before unsaved exit. Commercial reservation cannot prevent disk failure. |
| Across-device conflict | Session revision/owner lease; Read-only or explicit Take over. Old writer retains separate branch, cannot overwrite newer work; no last-write-wins merge. |
| Source missing/extraction failed | Per-file replace/paste/exclude/retry; partial ready sources retained. Tombstone unavailable citations; never mark a source ready or cited without acknowledgement. |
| Product quota | Reserve complete validation/exam bundle before start; new costly starts stop at safe boundaries. Honor active reservation; preserve queued work and free resources. |
| Exam deadline | Server deadline survives pause/exit/reload/offline. At expiry submit last server-accepted answers once; preserve unsynced work as timing-unverified. Prepare items before start, process answers after capture/submission; processing never resets/freezes the deadline. Background cutoff is not guaranteed. |

Recommended privacy defaults: only transcription processors receive audio; grading receives confirmed text. Before capture identify real recipients, purpose, and retention. Delete raw audio after transcript confirmation by default; optional replay retention ends seven days from upload, including unconfirmed uploads. Evidence/transcript history remains until the learner deletes it; disclose this separately. Inactive local drafts expire 24 hours after editing; clear local audio after verified server receipt unless an acknowledged offline draft is still needed. Playback requires authorization; deleted audio retains no playable link.

"Delete audio now" cancels unfinished transcription and offers text. "Delete attempt" removes response content/derived evidence and recomputes profile, preserving only permitted content-free deletion metadata. Source removal respects rights and tombstones. Export/deletion show requested/processing/completed/failed statuses, including processor/backup obligations; never promise verified erasure before confirmation. No audio analytics/training or default training on uploads. Any future upload-training opt-in is separate and non-coercive. These are technical recommendations aligned with data minimization, not regional legal compliance. ([Privacy, R23](https://www.w3.org/TR/privacy-principles/#data-minimization))

## Frontend state and data contracts

Keep one route/session model, not independent conflicting flags or a microservice diagram. Policies below must be enforced by the real integration as well as frontend controls; a prototype route guard alone is not security.

| View-model record | Necessary UX fields |
| --- | --- |
| Route/context | screen ID, subject/concept IDs, return target, selected tab/panel, locale/direction, capability set, `dataMode=real/demo` |
| Source/task | source/document/extraction/graph/lesson/task/rubric revision IDs; page/span; availability; item origin `verified-source/unverified-source/ai-generated`; verification record/date; novelty/task-family ID |
| Session/attempt | session/attempt/previous-stage evidence IDs; `stage=recall/learn/practice/explanation/follow-up/transfer/reflection/review`; phase from recorder/task table; `mode=practice/independent-transfer/guided-transfer/independent-review/guided-review`; draft/submitted/committed/abandoned; response kind; cursor/parent bookmark; revision/owner lease |
| Response/capture | recorder state/pending command/MIME; chunk manifest/sequence/checksum; capture elapsed; artifact revision; original ASR/correction/supplement/confirmed revision; sentence IDs, verified timestamps, uncertain spans; retention/expiry/deletion status |
| Assistance/evidence | in-app disclosures/reveal level; student-reported notes/script/outside help/unknown; conversion revision; applicable criteria/status/null-or-score/quotes/source pointers; assessment confidence as sufficient/limited/needs-verification with reason, not uncalibrated percent; disputes/superseded IDs |
| Jobs/save/quota | job type/ID/status/upload cursor, idempotency key, retry/Retry-After; last acknowledged checkpoint/location/local availability; server/profile revision and sync badge; reservation/entitlement/pending intent |
| Exam/planner | exam policy/start/deadline/server-clock offset/accommodations/timing verification; accepted/unsynced answer revisions; entry IDs/date/timezone/availability/conflicts/plan revision |

Capabilities: `canCaptureAudio`, `canUsePaper`, `canRunCode`, `canReadSources`, `canTutor`, `canRevealTarget`, `canSubmit`, `canStartCostlyAction`, derived from persisted stage/mode/status/lease. Guard target-answer payloads and source previews until authorized reveal, even in guided practice; never preload hidden solutions. Active closed-book policy is immutable and account/session-aware. Scored pools exclude unverified sources; verification checks provenance/extraction/key through a content process, not learner confirmation. Generated origin never changes; origin and assessment confidence are separate.

Normalized events carry event ID, session/attempt revision, timestamp, and payload: draft allocated/saved, source confirmed/cancelled, permission requested/result, capture acknowledged/interrupted/finalized, upload receipt, job status, transcript confirmed, assessment accepted/disputed, conversion committed, attempt abandoned, deadline reached, lease conflict/takeover, profile update, review booked/rescheduled, deletion acknowledged. Reject stale callbacks/revisions. Serialize assessment/conversion/deletion; saves, jobs, evidence, quota charges, XP and profile updates are idempotent. Submission alone never unlocks transfer; terminal acknowledgement does.

Exam clocks derive remaining time from server deadline/offset, not decrementing ticks. Untimed mode/adjustment is available before start; pause cannot freeze a committed timed run. Post-deadline transcription corrections are traceable; substantive additions cannot become timed success. Real answer acceptance uses server time; offline/device audio tails remain timing-unverified. Code Next requires isolation, no outbound network/secrets, bounded resources, and explicit run status; photographed work requires confirmed extraction before assessment.

ThinkFirst neither blocks OS notifications nor detects external AI; no-help labels describe enforced in-app access only.

## Usability validation

Validation status: proposed checks/tasks only. Neither UI quality nor learner outcomes have been tested. Numerical color checks do not substitute for rendered accessibility audits. Use a formative English pilot with eight adult university/engineering learners, including assistive-technology users; repeat localized tasks with native French/Arabic readers before rollout. Thresholds below are hypotheses for coordinator approval, not statistical evidence or established benchmarks.

| Learner task | Hypothesized acceptance threshold |
| --- | --- |
| Find Today next action, then upload a course with one bad file | At least 7/8 identify next action within 10s; 6/8 recover/confirm scope without moderator intervention |
| Ask for help before answering, take/bypass a prerequisite detour | 7/8 find early help and return to original task; none thinks help reduces points/access |
| Explain aloud, correct a technical ASR term, add a separate supplement | 7/8 confirm intended text; all can choose typing and distinguish correction from added reasoning |
| Inspect unclear assessment and application/retention evidence | 7/8 explain why unscored is not wrong and immediate transfer is not retained mastery |
| Request a hint during no-help transfer, cancel then confirm conversion | All understand guided mode records assisted evidence; no lost acknowledged work or policy bypass |
| Pause/reload, denied microphone, stalled upload, second-device takeover | 7/8 recover a truthful checkpoint without guidance; zero silent overwrites/automatic recording restarts |
| Refresh/exit an exam, reschedule an overfull day, delete audio | All understand continuing deadline, uncovered backlog, and transcript retention after audio deletion |

UI-only verification must cover every screen's empty/loading/error states, long labels/RTL, focus/virtual keyboard, NVDA/VoiceOver, reduced motion, codecs on actual mobile browsers, ignored/denied permission, late final chunks, duplicated commands, invalid grades, missing sources, quota/storage/auth failures, stale leases, and offline deadline reconciliation. No such tests have passed yet. Content experts must calibrate rubrics and transfer novelty; evaluate later unaided work and reported pressure, not session length, streak return, or demo XP. Any learning-effectiveness claim needs a separate appropriately designed delayed-outcome study.

### Coordinator review

Confirm release locale; content verification responsibility and source rights; domain-approved criteria/novelty and ASR dialect/equation support; proposed limits and quota-bundle costs; privacy jurisdiction/minor handling/processor and backup deletion; replay/draft retention defaults; exam accommodations and the recommended last-server-accepted/offline-tail policy. Approve or revise these explicit defaults before production, without changing canonical navigation. Browser/device capture reliability, rendered contrast, and learner usability remain validation gates.

## Build order and acceptance criteria

Implement by dependency, without assuming team size or duration:

1. Foundation: canonical routes/shell, original tokens/licensed fonts, responsive semantics, labeled fixtures, identity/draft/source versions.
2. Course path: C01/C02 -> W01/W06 -> S01/S02 recall/cited learning/exercise/early graduated help.
3. Validation: complete Voice/Text states, confirmed rubric evidence, one follow-up, unfamiliar transfer with enforced lock/conversion.
4. Closure: S03 reflection/profile/review, W08/W05/G04 history, G01 resume, G03/G05 manual planner, privacy/quota/recovery.
5. Broader Core beta: E01/E02/E03 text mocks, immutable origin/policy/deadline, disputes; verify real integrations before beta release.
6. Next then Later: OCR/code/advanced planning/reminders/localization, then premium/calendar/native/extended modes after release gates.

### Eight-view/state hackathon demonstration

Use a preauthenticated demo account and permission-cleared engineering fixture. These eight storyboard states include nested recorder/error transitions, not just eight routes. Demo session allocation explicitly preconfigures S01; full beta retains setup.

| Demo state | Screen/state | Demonstrated action |
| --- | --- | --- |
| 1 | G01 empty/next action | Add course; one clear starting CTA |
| 2 | C01 | Select supplied course PDF; limits/rights visible |
| 3 | C02 | Processing then confirm concept/source scope |
| 4 | W01 with W06 inspector | Visible unit path, optional foundation, start concept |
| 5 | S02 guided Learn/Practice | Goal/recall, cited chunk, attempt, early hint/escalation |
| 6 | S02 explanation/follow-up | Natural recording/text, confirmation, cited feedback, one follow-up |
| 7 | S02 unfamiliar transfer | No-help application; preserved-work guided conversion alternative |
| 8 | S03 | Reflection, separate evidence/profile summary, review booking, return Today |

Browser capture can be real while extraction/ASR/grading are visibly mocked. Never imply measured retention from the demo. Omit advanced E/G screens, paper/code, billing/integrations. Any shown but unimplemented navigation target opens a truthful scope explanation, not a fake dashboard.

Release checklist: IDs/routes/cases resolve; 320px/keyboard/typed paths complete; honest mastery/origin/save/deletion labels; no premature solution; cross-tab/request no-help enforcement; null uncertainty; device-tested recorder recovery; idempotent receipts/charges/rewards; immutable exam deadlines/separate late drafts; verified rights/processor retention/deletion; no unresolved critical learner-test failures.

## Sources

Indexed authoritative URLs below were successfully retrieved as source text in the notes and rechecked with WebFetch for this synthesis. Official product pages establish described design/features, not comparative effectiveness. W3C/MDN establish standards/platform constraints. R08 provides abstracts only. No source supplied proprietary Duolingo numerical tokens or ThinkFirst test results.

| ID | Source | Used for |
| --- | --- | --- |
| R01 | [Duolingo core-tabs design account, 2026](https://blog.duolingo.com/core-tabs-redesign/) | Hierarchy/spacing/consistency |
| R02 | [Duolingo learning path, 2022](https://blog.duolingo.com/new-duolingo-home-screen-design/) | Historical guided path/practice |
| R03 | [Duolingo review guidance, 2026](https://blog.duolingo.com/how-to-review-lessons-on-duolingo/) | Voluntary targeted review |
| R04 | [Duolingo widget account, 2023](https://blog.duolingo.com/widget-feature/) | Pressure mechanisms deliberately rejected |
| R05 | [Brilliant official product](https://brilliant.org/) | Guiding questions/shared work |
| R06 | [Forest official product](https://www.forestapp.cc/) | Focus metaphor/loss rejected |
| R07 | [NN/g progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/) | Simple defaults/advanced controls |
| R08 | [Europe PMC indexed abstracts](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%28EXT_ID%3A16507066%20AND%20SRC%3AMED%29%20OR%20DOI%3A10.1177%2F1745691615569000&resultType=core&format=json&pageSize=2) | Roediger/Karpicke 2006; Soderstrom/Bjork 2015; delayed learning vs performance |
| R09 | [Nunito Sans OFL](https://raw.githubusercontent.com/google/fonts/main/ofl/nunitosans/OFL.txt) | Verified font licensing |
| R10 | [Noto Sans Arabic OFL](https://raw.githubusercontent.com/google/fonts/main/ofl/notosansarabic/OFL.txt) | Verified Arabic font licensing |
| R11 | [WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/) | Complete-process AA target, reflow, timing, media, AAA distinctions |
| R12 | [WAI contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) | Text ratios/sRGB calculation |
| R13 | [WAI non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) | Relevant controls/graphics |
| R14 | [WAI target minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | 24px AA vs 44px enhanced |
| R15 | [WAI focus visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html) | Keyboard focus |
| R16 | [WAI focus not obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html) | Sticky/panel focus recovery |
| R17 | [WAI transcripts](https://www.w3.org/WAI/media/av/transcripts/) | Accessible playback/text alternative |
| R18 | [WAI form notifications](https://www.w3.org/WAI/tutorials/forms/notifications/) | Error/status placement |
| R19 | [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) | Intent/permission/context/device errors |
| R20 | [MDN MediaRecorder](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder) | Capture state/MIME/commands |
| R21 | [MDN dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event) | Chunk/interruption limitations |
| R22 | [MDN storage quotas/eviction](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria) | Honest local recovery |
| R23 | [W3C privacy principles](https://www.w3.org/TR/privacy-principles/#data-minimization) | Minimization/purpose/withdrawal; not legal advice |
