# ThinkFirst Screens and Learner Use Cases

## What Is the Canonical Information Architecture?

### Takeaway
Keep four global destinations and five subject tabs. Learning and Focus are session modes/states; Professor is contextual assistance, not another destination. The following blueprint is a recommendation for the full vision, not a hackathon delivery commitment.

### Cited Findings
- NN/g recommends exposing frequently needed choices first, moving specialized choices behind clearly labeled controls, and making the disclosure mechanism obvious. [NN/g, Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
- Duolingo's 2022 redesign describes a guided path, smaller units, integrated practice, and unit guidebooks. This is historical product documentation, not evidence that its current navigation or academic effectiveness transfers to ThinkFirst. [Duolingo, Introducing the New Learning Path](https://blog.duolingo.com/new-duolingo-home-screen-design/)

### Inferences
**Assumptions and priorities:** One student owns subjects, drafts, plans, and evidence; no other role portals. Responsive web is sufficient initially. English labels here are specification handles; launch locale is undecided, with French/English/Arabic localization later. Core means a trustworthy learning loop; Next means enrichment; Later means optional integrations/modes. Original assets, compact path units, and one clear next action provide Duolingo inspiration without hearts, leagues, punitive streaks, or noisy celebration.

**Navigation contract:** Today, Subjects, Planner, Progress, in that order. Profile menu contains account/settings and sign-out; learner profile belongs inside global Progress. Subjects contains Roadmap, Practice, Exams, Resources, Progress. Desktop shows all five. Mobile shows Roadmap, Practice, Exams, More; More opens Resources and subject Progress, retaining their canonical routes. Global Progress means all subjects; subject Progress means the named subject. Direct source/evidence links prevent More from burying frequent contextual actions. G04's basic cross-subject summary is Core; derived learner-profile signals are Next.

**Canonical routes and stable IDs:** `:s` subject, `:c` concept, `:d` document, `:e` evidence, `:l` session, `:x` exam, `:b` planner entry. New session/exam/entry commands allocate resumable drafts before opening setup. `/` redirects to `/welcome` if signed out, `/onboarding` if setup is unfinished, otherwise `/today`; protected links preserve a return target through sign-in.

| ID | Route | Screen |
| --- | --- | --- |
| A01 | `/welcome` | Sign-in/create account states |
| A02 | `/onboarding` | Goal/preferences setup |
| A03 | `/settings?section=:section` | One value: account, notifications, privacy, language, plan, calendar |
| G01 | `/today` | Recommended next action |
| G02 | `/subjects` | Subject collection |
| G03 | `/planner` | Agenda/calendar |
| G04 | `/progress` | Cross-subject evidence/profile |
| G05 | `/planner/entries/:b` | Exam, availability, or study-block editor |
| C01 | `/subjects/new` | Upload/guided-topic creation |
| C02 | `/subjects/:s/setup` | Processing status/scope confirmation |
| C03 | `/subjects/:s/diagnostic` | Optional baseline session |
| W01 | `/subjects/:s/roadmap` | Concept/prerequisite path |
| W02 | `/subjects/:s/practice` | Review/exercise selection |
| W03 | `/subjects/:s/exams` | Exam library/preparation |
| W04 | `/subjects/:s/resources` | Source collection |
| W05 | `/subjects/:s/progress` | Subject evidence |
| W06 | `/subjects/:s/roadmap/concepts/:c` | Concept inspector; Roadmap selected |
| W07 | `/subjects/:s/resources/:d?page=:p` | Document viewer; Resources selected |
| W08 | `/subjects/:s/progress/evidence/:e` | Attempt/evidence receipt; Progress selected |
| S01 | `/subjects/:s/sessions/:l/setup` | Learn/Practice/Review setup |
| S02 | `/subjects/:s/sessions/:l` | Active learning shell |
| S03 | `/subjects/:s/sessions/:l/summary` | Session outcome/review booking |
| E01 | `/subjects/:s/exams/:x/setup` | Exam configuration/generation |
| E02 | `/subjects/:s/exams/:x/run` | Active exam |
| E03 | `/subjects/:s/exams/:x/report` | Report/repair actions |
| P01 | Parent route + `panel=professor` | Contextual Professor panel |
| F01 | Parent session route unchanged | Focus controls/pause sheet |
| N01 | Parent route unchanged | Notification inbox |
| Q01 | Parent route unchanged | Optional quota dialog |

`/subjects/:s` redirects to Roadmap. Panels preserve parent state and a close/return action. Global navigation is present throughout the authenticated app except active focused sessions/diagnostics/exams; setup, paused, summary, and report states restore it. All active tasks enter the focused shell; optional Focus controls configure timer/muting, not another route. Pre-onboarding uses an entry shell, not hidden application navigation.

### Gaps
Launch language, source verification ownership, and commercial policy need decisions. The underlying long-form blueprint was not supplied in this folder; this specification follows the assignment's constraints rather than claiming compatibility with unseen screens.

## What Exists Where on Desktop and Mobile?

### Takeaway
Use stable navigation outside tasks and a task-first shell inside sessions. Keep source provenance, save status, contextual help, and next actions attached to the work they describe.

### Cited Findings
- W3C recommends concise success/error feedback, explanations for recovery, inline feedback near controls, and an overall error list above the form. This supports the placement recommendations below, not a complete accessibility specification. [W3C, User Notification](https://www.w3.org/WAI/tutorials/forms/notifications/)

### Inferences
**Geometry recommendations:** At widths >=1024px, use a 208px left global rail and 64px top header; content starts below the header, beside the rail, with 24px gutters and a 1200px maximum width. Header breadcrumbs are left; notification bell and profile menu are far right. Context panels occupy a 320px right column; only one opens at once, with Professor temporarily replacing inspector/notes. Below 1024px, use a 56px header, single-column content, and a fixed 64px four-destination bottom bar plus safe-area space. Arabic later mirrors start/end placement, not evidence meaning. These dimensions specify structure, not visual tokens.

Subject header: title/course selector left, Continue and Professor right; local tabs immediately beneath. Mobile places title and Professor on one row, Continue below, then four local tabs. More remains selected when showing Resources or subject Progress. Non-focused mobile sheets occupy the space between header and global bottom bar. Sticky action bars sit above global navigation; focused actions occupy the viewport bottom instead. Active sessions replace the global rail/workspace tabs with the task shell; Save and exit remains top-left.

| Screens | Desktop component order/location | Mobile adaptation |
| --- | --- | --- |
| A01-A02 | Centered form; step/title top, fields middle, Back/Continue bottom. Goal includes Unsure; dates/level optional. | Full-width staged form; retained fields on Back. |
| G01 | Main: Resume/next-action card, due reviews, subject shortcuts. Right: nearest exam and availability; stack right column below main under 1200px. | Same reading order; one primary Start/Resume above secondary choices. |
| G02 | Add subject top-right; cards below with name, source status, exam date, Continue. Empty state offers uploads/topic/Unsure. | Add subject below title; stacked cards. |
| C01-C02 | Upload/topic choice first; PDF/PPTX/TXT/MD/pasted-note inputs and configured limits below; scope preview next; Continue bottom-right. Per-file failures stay beside file. | Vertical choices; sticky Continue; expandable file details. |
| W01/W06 | Recommended unit sequence and labeled concept nodes in main column; inspector right: objective, prerequisite links, evidence/due flags, Learn/Practice. | Vertical path; inspector opens in-content sheet with Return to roadmap. |
| W02/S01 | Due review first, concept filters next, exercise choices below; setup shows objective, estimated duration, input and Focus options. | Filters collapse behind labeled button; setup actions above bottom bar. |
| W03/E01 | Prepare and New exam top-right; attempts below. Setup: scope, provenance filter, coached/strict policy, item count/duration, preview, Start. | Same order; advanced format controls disclosed beneath basics. |
| W04/W07 | Sources table first, labeled generated study aids below; Add top-right, row menu replace/remove. Viewer: thumbnails left, document center, notes/source metadata right; page/search controls top. | Document first; page picker and source/notes sheets; Return restores originating task. |
| W05/W08/G04 | Filters top; concept evidence matrix and receipts below. Global profile follows subject summary; receipt shows answer, assistance, date, rubric, source links. | Stacked concept cards and receipt sections; no wide matrix dependency. |
| G03/G05 | Week grid main; date/availability/Add exam toolbar top; selected-entry editor right, conflict alternatives above Save. | Agenda default; entry sheet with date/duration/concept fields; calendar optional toggle. |
| S02/C03 | Header: Exit left, objective/task position center, save/Focus right. Recall/prompt above answer; eligible Text/Paper/Code/Voice controls below prompt. Check/Continue bottom; Help opens P01 right. | Prompt, input, feedback stacked; Help beside Check; no global bar while active. |
| E02 | Header: Exit, exam title, deadline, save status. Question list left; question/answer center; flag/navigation/Submit bottom. Strict mode has no Professor. | Question index opens from header; bottom Previous/Next/Submit; no global bar. |
| S03/E03 | Outcome first, evidence links next, gaps/repair queue below; next-session/plan CTA last. Pending grades show placeholders, not achievements. | Same order; global bar restored. |
| P01/F01 | Professor: context/close top, steps/citations middle, composer/Return bottom. F01 header sheet: duration, Start/Pause timer, in-app mute, Save and pause session. | Professor occupies focused viewport or non-focused content sheet; task draft retained. |
| A03/N01/Q01 | Settings sections left, controls right. Inbox anchored to bell. Quota dialog shows usage/reset, free continuation, optional plan link. | Single settings section; inbox/quotas remain contextual, not destinations. |

**Shared state contracts:** Drafts retain answers, scope, and configuration; distinguish server-confirmed saves from local pending work. Reauthentication returns to the draft. Failed file reads retain metadata/choices but may require file reselection; do not promise unsent binary persistence. Ingestion stages are transferring, queued, extracting/topic generation, scope review, ready; needs attention, failed, and cancelled branch from processing. Partial successes remain usable. Show byte progress only for transfer, not invented extraction percentages. Ready requires scope confirmation; unsupported/encrypted/unreadable documents offer replace, exclude, or guided-topic continuation. Text extraction is Core; scanned-source OCR is Next.

**Learning contract:** Start with retrieval and visible "I don't know"/orientation. Help progresses through clarification, strategy cue, substep, different worked example, then "End this attempt and view worked solution" confirmation. No required minimum attempt, hint penalties, or duration rewards. Revealing an answer makes that target assisted; a new task validates independence. Persist mode/capabilities and enforce permitted help/resources/reveals at the service boundary; withhold target solution payloads until authorized reveal. Hiding buttons or prompting the model alone is insufficient. Strict closed-book exams deny Professor/resources even through direct requests; coached mocks allow scaffolding and label assisted results.

**Evidence contract:** Separate assisted, independent-recent, and delayed-retention evidence; add due/contradictory flags instead of a false mastery percentage. One answer never proves durable mastery. Fresh checks use unseen targets, not revealed solutions or identical repeats. Every claim links W08 with task/version, response, help, date, grading confidence, and source. Label items `Verified source`, `Unverified source`, or `AI-generated` in selection, task, and report. Uploaded past exams are not automatically verified; generated variants remain generated. Verification needs checked provenance/extraction/answer key. Exam filters are Verified-only, Generated-only, Mixed; unverified source items stay outside scored pools until validated. Provenance and grading confidence are separate; uncertain grades remain provisional.

**Privacy defaults recommended:** Subjects are private; model-training use of uploads requires separate opt-in. Settings expose retention/export/deletion status. Removing source content leaves only permitted receipt metadata/tombstones; explicit account deletion follows the documented data policy.

### Gaps
Geometry needs testing at narrow widths, zoom, and long translated mathematics. Evidence thresholds, item verification, OCR support/limits, code execution safety, and exam interruption policy need domain/service specifications. Detailed accessibility, visual tokens, and audio grading remain separate research scopes.

## Which End-to-End Learner Cases Must Work?

### Takeaway
The catalogue specifies observable transitions and retained outcomes, not just feature names. All cases inherit the state, provenance, assistance, and navigation contracts above.

### Cited Findings
- NN/g distinguishes staged setup from progressive disclosure and cautions against separating controls that users need to adjust together. Recommend compact scope/format previews rather than an overlong exam wizard. [NN/g, Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)

### Inferences
**First visit:** A01 > A02 > G02 empty > C01 upload or guided topic > C02 status/scope > optional C03 > W01 > S01 > S02 > S03 > G01. Unsure is valid throughout; diagnostic skipping yields insufficient evidence, not failure.

**Return:** Sign-in if needed > G01. Recommended order: unfinished session, current planned block, due review, exam-related gap, next concept; show the reason and Change action. Choose another subject/time without punishment. Strict exam resumption respects its original deadline.

| Case / Priority | Trigger; Precondition | Ordered Screens / Actions | Alternative / Error Route | Saved Result | Observable Acceptance |
| --- | --- | --- | --- | --- | --- |
| UC01 Onboard / Core | First visit; no completed setup. | A01 sign-in/create > A02 goal, optional preferences > G02. | A01 error retains non-secret fields; A02 Back retains choices. | Setup milestone/preferences. | Unsure and skipped dates still reach subject creation. |
| UC02 Return / Core | Return; account/draft exists. | A01 authenticate > G01 Resume > S02. | Expired identity returns A01, preserving return target. | Restored draft/context. | Same question and saved answer return, without duplicate attempt. |
| UC03 Upload / Core | Add subject; course files available. | G02 > C01 select PDF/slides/notes/past exams > C02 queue. | Unsupported file stays flagged in C01; accepted files continue. | Subject, source metadata, job IDs. | Status survives navigation; subject card links processing job. |
| UC04 Recover ingestion / Core | Processing fails; partial job exists. | C02 inspect file error > retry/replace/exclude > scope preview. | Unreadable text: C02 guided-topic continuation. | Successful files and corrected queue. | Retry neither duplicates sources nor discards previous success. |
| UC05 Guided start / Core | Unsure; no usable course upload. | C01 Unsure > choose broad subject/topic > C02 starter scope. | Ambiguous topic: C02 asks one clarifying choice. | Provisional generated scope. | Learner can start without naming prerequisites or exact chapter. |
| UC06 Confirm scope / Core | Extraction complete; proposed concepts exist. | C02 inspect/edit scope > accept > C03 initially, W01 for revisions. | Doubtful extraction remains excluded/unverified in C02. | Versioned roadmap/source mapping. | Accepting revisions preserves existing evidence and labels uncertainty. |
| UC07 Diagnostic / Core | Scope accepted; baseline unknown. | C03 recall/sample tasks > submit or skip > W01. | Don't know offers orientation; save failure retains responses. | Baseline receipts or insufficient-evidence status. | Skipping never locks learning or fabricates low ability. |
| UC08 Choose concept / Core | Explore subject; roadmap exists. | W01 node > W06 objective/prerequisites/evidence > S01. | Empty evidence: W06 offers starter session. | Selected concept/version. | Every concept is inspectable and startable, including unseen ones. |
| UC09 Prerequisite detour / Core | Gap detected; target selected. | W06/S02 offer foundation > S02 mini-session > S03 return target. | Continue anyway returns original S02 with scaffolding. | Parent bookmark/gap evidence. | No hard lock; detour restores original task context. |
| UC10 Next session / Core | Today opened; subject exists. | G01 inspect reason > S01 adjust time/goal > Start S02. | Stale recommendation: G01 Change > W01 selection. | Session objective/queue. | One primary next action; learner can override recommendation. |
| UC11 Structured Learn / Core | Concept selected; explanation needed. | S02 recall > orientation > cited lesson chunk/example > practice. | Missing source: label generated explanation; offer W07 when available. | Lesson position/recall response. | Reading alone creates no independent-performance evidence. |
| UC12 Exercise / Core | Task active; response ready. | S02 answer > Check > diagnostic feedback > Continue. | Evaluation error stays S02 with Retry and retained answer. | Attempt/rubric/help receipt. | Double submission produces one receipt; uncertainty is visible. |
| UC13 Early help / Core | Blank attempt; learner unsure. | S02 Don't know/Explain prompt > P01 orientation > S02. | Ambiguity: P01 clarification or prerequisite option. | Assistance level/context. | Help works before typing without exposing target solution. |
| UC14 Escalate help / Core | Struggle; coached task active. | P01 cue > substep > different example > explicit reveal > fresh check. | Unhelpful cue offers detour, not automatic reveal. | Assisted receipt/reveal state. | No hint point loss; revealed target cannot count independent. |
| UC15 Independent check / Core | Guided work finished; fresh task available. | S02 new check > unaided response > Check > S03. | Help converts task to coached; another fresh check follows. | Independent-recent receipt/review due. | New task has no target help; no durable-mastery badge. |
| UC16 Pause/resume / Core | Interruption; session active. | S02 > F01 Save and pause > G01 > Resume S02. | Offline: retain local draft, show pending save. | Cursor, answer, queue, context. | Navigation returns on pause; resume restores exact work. |
| UC17 Finish session / Core | Queue finished; receipts exist. | S03 inspect outcomes/evidence > accept review date > G01. | Pending grading remains S03 pending, retryable. | Summary/delayed-review booking. | Every achievement links evidence; time/audio length earn nothing. |
| UC18 Delayed review / Core | Review due; earlier evidence exists. | G01 review > S01 Review > S02 new task > S03. | Snooze from G01; failure adds revisit recommendation. | Dated retention/revisit receipt. | Only delayed unaided performance adds retention evidence. |
| UC19 Paper work / Next | Handwritten response; eligible task. | S02 Paper > attach/crop > confirm extraction > Check. | Illegible image stays attached; switch to text S02. | Artifact/confirmed workings. | Assessment uses learner-confirmed extraction; original work remains recoverable. |
| UC20 Code work / Next | Coding task; safe runner available. | S02 editor > Run > inspect output/tests > submit. | Timeout/unavailable runner retains code and offers text fallback. | Code/test/assessment receipts. | Execution failure loses no code; runtime earns no reward. |
| UC21 Voice entry/exit / Next | Explain aloud; eligible task. | S02 Voice > consent/record > review/confirm > feedback > fresh/text task. | Permission denied returns text S02. | Consented artifact/context receipt. | No length/time reward; grading details belong to audio specification. |
| UC22 Professor context / Core | Question about current work; context exists. | W06/W07/S02 Professor > P01 ask/citations > Return. | Strict E02 rejects help; off-topic asks choose W01 concept. | Scoped transcript/context. | Close restores task; direct requests obey persisted mode permissions. |
| UC23 Focus / Core | Wants concentration; session starting. | S01 Focus option > S02 task-only view > F01 pause/exit. | External distractions: offer reminder, not blocking claim. | Focus preference/session state. | Only in-app distractions muted; website claims no system control. |
| UC24 Exam preparation / Next | Exam approaching; subject/date exists. | W03 Prepare > G03/G05 preview gap-based blocks > confirm > G01. | Overcapacity: G05 reduce scope or leave explicit gaps. | Exam-linked preparation plan. | Blocks link concepts/evidence, not unsupported readiness predictions. |
| UC25 Configure exam / Core | New mock; subject has item pool. | W03 > E01 scope/provenance/policy/count/duration > preview > generate. | Verified-only empty: E01 broaden explicitly or cancel. | Draft/pool version/policy. | Every item labeled; no silent generated substitution. |
| UC26 Run exam / Core | E01 ready; policy acknowledged. | E02 Start > answer/flag/revisit > Submit > E03. | Disconnect: E02 retains pending work; Exit > G01 does not pause deadline. | Autosaves/deadline/submission receipt. | Refresh restores timer; strict help denied; submission occurs once. |
| UC27 Exam report / Core | Submitted exam; grading available. | E03 inspect per-item evidence/gaps > repair > S01. | Uncertain grading stays provisional in E03. | Report/selected repair queue. | Coached versus independent results and provenance stay distinct. |
| UC28 Dispute item / Next | Suspected incorrect grading; receipt exists. | W08 Flag issue > attach explanation > Send. | Send failure retains W08 dispute draft. | Dispute/audit status. | Pending item adds no new readiness claim; old record not silently rewritten. |
| UC29 Build planner / Next | Exam date/availability known; subject exists. | G03 > G05 dates/timezone/availability > plan preview > confirm. | Impossible workload: G05 warns and shows uncovered scope. | Availability/exam/linked blocks. | Confirmed blocks fit declared availability; no invented dates. |
| UC30 Resolve conflict / Next | Block moved or exam changed; plan exists. | G03 edit > G05 conflict alternatives > choose > Save. | Keep unresolved with visible warning in G03. | Plan revision/reminder update. | No silent movement of unrelated blocks; Undo restores revision. |
| UC31 Missed block / Next | Planned time passed; no completion receipt. | G01/G03 missed block > G05 reschedule/shrink/skip. | No slot: retain unscheduled backlog in G03. | Missed/rescheduled/skipped status. | Elapsed calendar time earns no completion; no penalty points. |
| UC32 Manage sources / Core | Source changed; subject exists. | W04 add/replace > C02 review/apply; remove > confirm. | Failed import leaves previous version in W04. | Source versions/mapping/history. | Old attempts retain references; source edits never erase progress. |
| UC33 Document viewer / Core | Citation/resource selected; document exists. | W04/receipt citation > W07 page/search > Return. | Missing/deleted source: W07 tombstone > W04 replace. | Reading position/return context. | Exact cited page opens; returning restores originating task. |
| UC34 Subject evidence / Core | Checks progress; subject has attempts. | W05 concept > W06/W08 inspect response/help/date/source. | Empty W05 offers S01 baseline, not fake scores. | Filters/evidence view. | Every status links receipts or states insufficient evidence. |
| UC35 Learner profile / Next | Reviews growth; evidence exists. | G04 subject summary/profile > W05 > W08 receipts. | Contradictory evidence remains mixed, with review recommendation. | Evidence-based aggregates/self-reports separate. | No fixed learning-style diagnosis; displayed claims trace to observations. |
| UC36 Notifications / Next | Wants reminders; signed in. | A03 notifications opt-in > G01 bell/N01 > linked G03/session. | Browser permission denied: in-app reminders remain available. | Channel/quiet-time/read preferences. | Permission requested only after opt-in; links resolve current state. |
| UC37 Privacy/account / Core | Changes data controls; authenticated. | A03 privacy/account > storage/consent/export/delete preview > confirm. | Expired identity: A01 > A03 preview/reconfirm. | Consent/action status receipts. | No silent deletion; deleted citations become explicit tombstones. |
| UC38 Optional quota / Later | Costly action requested; quota exhausted. | Q01 usage/reset > free continuation or A03 plan > return draft. | Decline/wait returns unchanged parent task. | Usage/pending intent. | No mid-exam cutoff; existing resources/evidence remain accessible. |
| UC39 Calendar integration / Later | Wants synchronization; plan exists. | A03 calendar connect/permissions > import/export preview > G03 confirm. | Revocation returns A03 disconnected; local plan preserved. | External IDs/direction/sync status. | Retry creates no duplicate events; conflicts require confirmation. |
| UC40 Future modes / Later | Enabled extended mode; eligible content. | W02 > S01 problem lab > S02/S03; W03 > E01 oral mock > E02/E03. | Unsupported mode offers normal text setup. | Mode policy/artifacts/receipts. | Reuses canonical shells; no fifth destination or infinite-chat portal. |

### Gaps
Recommendations require learner testing, not a claim of validated usability. Test first upload failure, Unsure onboarding, prerequisite bypass, early help, exact resume, verified-only empty exams, stale deadlines, and contradictory evidence. For timed disconnections, recommend submitting last server-accepted answers at the deadline, retaining unsynced work separately and marking interruption; finalize this policy before release. Open decisions include source rights/retention, dispute resolution, evidence calibration, quota pricing, and calendar provider capabilities. Bookmarks/annotations are Next enrichment in W07. Localization and future modes must reuse IDs and retain canonical navigation; audio scoring/detail is deliberately not specified here.
