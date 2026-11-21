# ThinkFirst Audio, Accessibility, And Recovery States

Research/design notes, 21 November 2026. Verified platform facts appear under Cited Findings; Inferences are proposed product contracts, not tested behavior. Scope excludes global navigation and palette. No application code or interactive/browser testing was performed.

## How Does Explain-Back Become Traceable Learning Evidence?

### Takeaway
Make voice optional and assess confirmed explanation content, not delivery. Under the supplied brief, explain-back is central validation but not cheating-proof: someone can read an AI script; independent application and later review supply different evidence.

### Cited Findings
- Microphone capture requires a secure context and permission; embedded contexts need appropriate delegation. `NotAllowedError` can mean denial, insecure context, or policy restriction; `NotFoundError` means no matching input. A permission promise can remain unresolved. [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- `MediaRecorder` exposes inactive/recording/paused states, pause/resume, final data delivery, and MIME capability detection. Do not assume one recording format. [MDN MediaRecorder](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- Chunk intervals are inexact; Safari interruptions and Android screen locking can delay delivery. Chunk count is not elapsed time. [MDN dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event)
- Transcripts convey meaningful speech/non-speech information; WAI recommends easy access beside the player. Prerecorded audio-only alternatives are Level A, subject to the standard's text-alternative exception. [WAI transcripts](https://www.w3.org/WAI/media/av/transcripts/); [WCAG 1.2.1](https://www.w3.org/TR/WCAG22/#audio-only-and-video-only-prerecorded)

### Inferences
**Placement contract.** Desktop: prompt above the central response panel. Keys: C recorder/player, T editor, P status, Q next-question introduction, R reflection replace that panel; E shows a central summary with criterion details in an adjacent rail. Mobile stacks prompt/status/response/evidence in that order. Primary/secondary CTAs sit below the central panel; pin them only without obscuring content or focus.

**State contract.** `stage` is explanation, follow-up, transfer, or review; each has an `attemptId` linked by `sessionId`. Reuse capture/confirmation/assessment phases. Disabled progress labels are not CTAs. Save/leave and error overlays are specified in section three.

| Phase / Panel | Primary; Secondary | Transition And Neutral Microcopy |
|---|---|---|
| Permission intent / C | Enable microphone; Use text | Explicit activation requests audio only. "Explain naturally. We assess your ideas, not your voice. Review the text before assessment." Show retention choice here. |
| Permission pending / C | Waiting, disabled; Use text | Grant -> ready; rejection -> blocked. At 10 seconds: "Still waiting for a microphone choice. Text works too." Never infer denial. |
| Blocked / C | Use text; Try microphone again | Distinguish denied/policy, absent, busy/hardware, unsupported/insecure. "Microphone access is unavailable. Your task is unchanged." Give cause-specific settings/device guidance; retry only on activation. |
| Ready / C | Start recording; Use text | Start acknowledgement -> recording; failure -> blocked. "Microphone connected. Recording has not started." |
| Recording / C | Finish recording; Pause | Pause acknowledgement -> paused; finish -> finalizing. "Recording. Take your time." Show elapsed capture time and text status, not a speech-quality score. |
| Paused / C | Resume; Finish recording | Resume acknowledgement -> recording. "Paused; audio is not being added. The microphone connection remains open." |
| Finalizing / C | Preparing playback, disabled; Stay here | Final data + stop -> playback; empty/corrupt output -> capture error. "Preparing your recording." Release input tracks after finalization. |
| Playback / C | Use recording; Record another take | Native play/seek controls stay inside C. Use -> uploading; retake -> ready with a new take revision, retaining the old draft. "Listen if you wish, then check the transcript." |
| Typed edit / T | Review text; Save and leave | Nonempty draft -> confirmation, bypassing microphone/audio jobs. "Typing uses the same concept rubric." Switching modes retains both drafts; explicitly select the submitted one. |
| Uploading / P | Uploading, disabled; Save and leave | Verified receipt -> transcribing; stalled/failure -> recovery. "Uploading. Assessment has not started." Show bytes only when measurable. |
| Transcribing / P | Preparing text, disabled; Save and leave | Output -> confirmation; failure -> recovery. "Turning your recording into text. You will check it first." |
| Confirmation / T | Confirm and assess; Edit text | Original ASR, editable corrected version, player, uncertainty markers. "Check names, numbers, and meaning. Unclear words are not mistakes in understanding." Unresolved meaning -> clarification/unscored, never zero. |
| Grading / P | Assessing, disabled; Save and leave | Valid assessment + evidence acknowledgement -> feedback; uncertainty -> unscored feedback; failed job -> recovery. "Checking the ideas against this task's rubric." |
| Feedback / E | Answer follow-up / Try new application / Reflect / Finish; Review evidence | Respectively: explanation -> generate follow-up; follow-up -> prepare transfer; transfer -> reflection; review -> complete. "What this answer showed, and what remains uncertain." Unscored branch below. |
| Follow-up generation / P | Preparing question, disabled; Save and leave | Valid targeted question -> Q; failure -> recovery. "Preparing one question about your reasoning." Persist its ID; retries never reroll it. |
| Follow-up introduction / Q | Answer follow-up; Save and leave | One server-selected, unexpected relationship/example/limit question -> reused answer phases. "One more question about that idea." No automatic chain of additional validation questions. |
| Transfer introduction / Q | Start without in-app help; Use guided help | Prepare/validate task first using P job states; reveal after mode commitment. "Lessons and hints stay unavailable until this attempt finishes or you switch to guided practice." |
| Transfer answer / C or T | Reuse phase CTA pair; extra Guided help below status | Keep Pause/Finish/Edit controls; lock throughout confirmation/grading. "Independent application: no in-app lesson or hint access." Conversion rules below. |
| Reflection / R | Save reflection; Skip reflection | Optional note/preference -> profile acknowledgement. "What would you try next time? This note does not change your evidence score." |
| Profile pending / P | Updating, disabled; Finish with update pending | Acknowledgement -> complete; failure -> retryable pending. "Your evidence is saved; the profile update is pending" only if evidence receipt exists. |
| Complete / E | Finish; View evidence history | "Explanation saved. Application and retention are shown separately." Never imply retention from same-session success. |

Pending recorder commands disable duplicates and show "Starting/Pausing/Resuming" without moving focus. No acknowledgement after 10 seconds -> capture error; stop tracks and retain late data for recovery. Stale permission grants cannot enter ready. Stop tracks on exit/text switch; never silently submit/erase drafts.

| Blocked Branch | Specific Copy / Exit |
|---|---|
| Permission/policy (`NotAllowedError`) | "Microphone access is blocked here. Check browser/system settings, or use text." Do not assume the student denied access. |
| No matching device (`NotFoundError`) | "No matching microphone was found. Connect one or use text." Retry -> permission pending. |
| Hardware/open failure | "The microphone could not be opened. Check your input device, then retry or use text." |
| Unsupported/insecure context | "Recording is unavailable in this browser or page. Use text." Disable retry until capability/context changes. |
| Empty/corrupt take | "No playable audio was captured. Record another take or use text." No assessment; retain recoverable draft material. |

Capture elapsed time excludes pauses; the exam clock does not. Empty typed input disables Review with "Add text to review it," without assigning a score.

**Scoring and provenance.** Declare essentials/applicability before answering. Use 0 = absent/contradicted in interpretable evidence, 1 = partial, 2 = demonstrated; null = unscored. No total with uncertain applicable dimensions; otherwise optional total, not "percent understanding." Show evidence sufficiency, not uncalibrated confidence percentages. Unscored feedback offers Review answer -> confirmation or Keep unscored -> complete with later stages pending, never independent success. Confirmation requires nonempty text and resolved or explicitly marked-unresolved spans; unresolved meaning bypasses grading to unscored feedback.

| Dimension | Evidence To Display |
|---|---|
| Correctness | Specific accurate claim or misconception, with transcript quote. |
| Essential coverage | Named required concepts covered/missing, not word count. |
| Why/relationships | Causal links, comparisons, or justified steps. |
| Example/application | Mapping an example to the concept, not merely naming it. |
| Limits | Boundary/exception when applicable; otherwise N/A, excluded from denominator. |

Keep original ASR and corrected text as separately identified versions while retained. Correction may restore words; added reasoning is a student supplement, not retroactive audio evidence. Grade only the confirmed revision; later edits supersede rather than overwrite assessments. Provide "Challenge assessment" -> identify disputed quote/criterion -> corrected-version review or reassessment; preserve the prior result as disputed, not another success.

Record assistance separately: student-reported notes/script/outside help/unknown, observed in-app help, text corrections, supplements, task novelty, and mode conversion. Never infer intelligence, personality, emotion, or understanding from accent, speed, fluency, or pauses. Text has equal independent-transfer eligibility.

**Transfer lock.** Lock when stage=transfer, mode=independent-transfer, and no terminal evidence/abandon acknowledgement exists; pauses, suspension, and reload preserve it. Deny lesson/hint, answer-revealing source previews, prior feedback, and tutoring across routes/tabs/service calls. Blocker CTAs: Return to task/Use guided help. Prompt, scratch work, accessibility tools, and current-answer replay remain available. Guided help pauses capture, then asks "Keep your work and switch to guided practice?" Cancel stays paused; explicit Resume continues. Confirm preserves/finalizes work and commits irreversible mode conversion before unlocking; failure stays locked with Retry. Serialize conversion/evidence commits by revision: raced results cannot label guided completion independent. Submission alone does not unlock. External tools remain possible; label "Completed without in-app help," not "verified independent."

Profile history separates explanation, follow-up, transfer, and delayed review. Update once per accepted revision; retries are not successes. Summary: "Essential coverage demonstrated; independent application pending; retention not checked." Independent success requires predeclared correctness/coverage/application criteria, not explanation total. Offer an adjustable three-day review as a scheduling hypothesis: Q -> reused pipeline, recording delay/assistance. Reflection records preference, not causal effectiveness.

### Gaps
No ThinkFirst-specific grading calibration, ASR dialect/equation accuracy, or transfer-novelty validation was supplied. The three-day review interval is not an established optimum. Script detection and individualized strategy-effectiveness claims are explicitly outside this design.

## Which Accessible, Responsive Interactions Must Ship?

### Takeaway
Target WCAG 2.2 AA throughout the complete workflow, with stronger touch/focus/motion choices. These notes are not a conformance audit or legal-compliance claim.

### Cited Findings
- Typical text requires 4.5:1 contrast; qualifying large text requires 3:1. Meaningful control/state graphics and required identifying boundaries need 3:1 against adjacent colors, not every decorative border. [Contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html); [Non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
- AA target size is 24 by 24 CSS pixels with specified exceptions; 44 by 44 is Enhanced/AAA, not AA. [Target minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html); [WCAG Enhanced](https://www.w3.org/TR/WCAG22/#target-size-enhanced)
- Keyboard focus must be visible; AA prohibits complete obscuration by author-created content, while complete visibility is the stronger design goal. [Focus visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html); [Focus not obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)
- Interaction-animation disabling is AAA; reducing unnecessary motion is nevertheless appropriate here. [Animation guidance](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)
- Keyboard operation, non-color-only meaning, reflow, programmatic status messages, and complete-process conformance are distinct requirements. [WCAG 2.2](https://www.w3.org/TR/WCAG22/)

### Inferences
Recommend 44px touch hit areas, readable disabled reasons, visible focus with sufficient contrast, and labels/icons/text alongside mastery colors. Use native buttons/editors/player controls with matching visible/accessibility names. No hold-to-record, drag-only upload, hover-only explanations, or global single-letter shortcuts. Do not autoplay audio or rewards.

At narrow widths/zoom, collapse the rail and keep DOM order unchanged. Support 320 CSS-pixel reflow and portrait/landscape; turn pinned actions into inline controls when the virtual keyboard or zoom risks covering focused fields. Test Arabic RTL with logical layout direction, declared content language, isolated mixed-direction formulas/numbers, and non-mirrored media chronology. Do not require Arabic students to speak standard Arabic to earn concept credit.

Announce phase changes once through polite status messages; reserve persistent alerts for actionable failures. Never announce elapsed seconds, waveform updates, or continuous transcript tokens. Retain focus during background processing; user-requested next stages focus their heading. Submission errors focus an error summary linked to fields. Dialogs constrain focus, Escape cancels, and dismissal restores the initiating control. Honor reduced-motion preferences; replace animated meters/celebration with static recording/status text.

| Delivery | Controls |
|---|---|
| First build | Equivalent typed path; complete recorder/recovery states; transcript versions; five-dimension evidence; transfer lock/conversion; deletion choice; keyboard/SR/RTL/reflow support; persistent timers and quota reservation. |
| Next | Optional transcript timestamp navigation, explicit microphone selector, longer user-selected retention only after deletion verification, accommodation usability pilots. |
| Later | Calibrated language/domain assessments and retention scheduling; longitudinal strategy comparisons with adequate evidence. Never voice-based trait inference or cheating-proof badges. |

### Gaps
No screen-reader, keyboard, mobile device, contrast, or RTL interaction tests were available. Arabic dialect coverage and mixed-direction mathematics need real-user review; a checklist cannot establish legal compliance.

## How Do Recovery, Storage, And Adjacent Task States Work?

### Takeaway
Recover from acknowledged checkpoints without inventing saved work or scores. Separate commercial quota, device storage failure, processing uncertainty, and timed-attempt rules.

### Cited Findings
- Browser storage is best-effort by default, can be evicted, and can fail with `QuotaExceededError`; private-session data is usually removed when that session ends. Storage estimates are not guarantees. [MDN storage](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
- W3C privacy principles recommend minimizing transferred data, specifying purposes, avoiding secondary uses, and facilitating withdrawal. This is technical guidance, not jurisdictional legal advice. [W3C Privacy Principles](https://www.w3.org/TR/privacy-principles/#data-minimization)
- Timing Adjustable allows turning a limit off before encountering it, sufficiently broad adjustment, or qualified extension; an "exam" label alone does not establish an essential exception. [WCAG 2.2.1](https://www.w3.org/TR/WCAG22/#timing-adjustable)

### Inferences
**Persistence/retention.** Persist chunk manifests/draft revisions locally; synchronize text/jobs/evidence with revision checks. Show "On this device," "Synced," or "Not saved." Capture navigation pauses: Stay or Finish/save/leave. Save/leave requires a checkpoint acknowledgement: local-only work resumes on this device; server jobs continue independently. Failed save stays here unless explicitly leaving unsaved. Reload validates data -> playback, otherwise text/retake; never promise undelivered/corrupt-chunk recovery or concatenate incompatible takes. Finished-with-profile-pending retains its sync badge/retry action.

Disclose recipients, purpose, and retention before capture. Only transcription receives audio; grading receives confirmed text. Choices: delete audio after confirmation (default), or replay retention ending seven days from upload; unconfirmed uploads share that cap. "Delete audio now" cancels unfinished transcription and offers text. Clear local audio after verified receipt; use authenticated playback. Inactive local drafts expire 24 hours after editing. Deletion copy: "Audio deleted; transcript history remains." Warn about shared/device-only storage. Full Delete attempt removes content/derived evidence and recomputes profile; content-free deletion metadata only. No audio analytics/training; processor/backups deletion requires verification.

| Condition | Required Recovery And Copy |
|---|---|
| Input interrupted/track ended | Pause on observable background interruption; ended track -> finalize recoverable data. Never auto-resume. "Recording was interrupted. Review the captured part." Invalid output -> retake/text, unscored. |
| Offline/upload stalled | Keep draft; 30 seconds without upload progress -> stalled. Retry looks up receipt, then resumes missing parts. "Not uploaded yet. Your recording is on this device" only after local-write acknowledgement. |
| Job slow/unknown | At 60 seconds show delay; at 180 expose Check status/Save and leave. Local timeout is not server failure. Reconcile existing job before retry; resume its actual phase. |
| Transcription/LLM uncertainty | Highlight unclear spans or unsupported assessment; Review answer/Retry assessment/Save and leave. "There is not enough reliable information to score this yet." Invalid rubric output never becomes zero. |
| Network/server failures | Maximum three automatic retries at 1/2/4-second backoff for transient failures, respecting Retry-After; then explicit Retry. Idempotency prevents duplicate jobs, evidence, or charges. |
| Authentication expires | Finish capture locally; reauthenticate before sync, preserving task/mode. "Sign in again to sync this draft." No quota/auth dialog interrupts speech. |
| Product quota/429 | Reserve the validation bundle before recording or typing, including follow-up/transfer. Reject new starts at safe boundaries; never cut active capture. Preserve queued work and show retry time, not mid-answer upsell. Infrastructure retries consume no extra student attempt. |
| Device storage exhausted | Keep recoverable data in memory; finish/review with Upload or Download options. "This draft cannot be saved on this device." Warn before leaving; physical failure cannot be hidden by quota reservation. |
| Resume conflict | Acquire session revision/owner lease; Read-only or Take over. Takeover invalidates old writer; old device keeps its draft as a separate branch. "Another session has newer work." Never last-write-wins merge. |
| Dashboard | Loading is not empty. Confirmed empty: "No evidence yet" with Choose concept/Add source. Failure: "Evidence could not load" with Retry; never render missing data as zero mastery. |
| Workspace/file | Selected -> validating -> uploading -> quarantined/scan -> extracting -> source confirmation -> ready. Show filename/limits/per-file status. Invalid/encrypted/no-text -> Replace/Paste text; rejected scan -> Remove/Replace; transient failure -> Retry same file. Only ready confirmed sources inform tasks; replacements cannot rewrite active lesson/rubric versions. |

Files use an inline source panel on both layouts: progress/Cancel, confirmation Use source/Edit extracted text, ready Open/Remove. Cancellation invalidates late callbacks; removal never destroys linked attempt history.

**Practice exam.** Offer untimed mode before start. Persist server start/deadline, duration, accommodations/extensions; derive remaining time using server clock offset, not ticks. Pause/navigation/reload/offline never reset/freeze it. Announce milestones, not seconds. Observable expiry finalizes capture/freezes input, preserving work; background cutoff cannot be guaranteed, so uncertain tails remain timing-unverified. Upload/transcription/grading consume no answer time. Post-deadline corrections are traceable; substantive additions are not timed success. Offline timing stays provisional until reconciliation, not integrity certification; reauthentication preserves work.

**Normalized frontend contract, recommendations only.** Derive controls from phase/stage/mode, not unrelated booleans; retain `returnPhase` for recoverable overlays.

| Record | Required Fields |
|---|---|
| Session/attempt | `sessionId`, `attemptId`, previous-stage evidence ID, concept/task/lesson/rubric versions, stage, phase, `attemptStatus` (draft/submitted/committed/abandoned), `mode` (practice/independent-transfer/guided-transfer), `responseKind` (audio/text), attempt revision, owner lease, server revision. |
| Capture/transcript | Recorder status, command pending, MIME, manifest/chunk sequence/checksum, elapsed capture time; original/corrected/supplement revision IDs, uncertain spans, confirmed revision, retention choice/expiry/deletion status. |
| Jobs/evidence | Job ID/type/status, uploaded bytes/cursor, idempotency key, retry count/Retry-After; criterion applicability/status/score/quotes, provenance, disputes/superseded IDs, profile revision/sync status. |
| Recovery/context | Last acknowledged checkpoint/location, local availability/expiry, error code/retryability/return phase; timer deadline/offset/timing status, quota reservation, file status/source revision. |

Normalize events with event ID, attempt/revision, timestamp, and payload: permission requested/result, capture acknowledged/interrupted/finalized, draft saved, upload acknowledged, job status, transcript confirmed, assessment accepted/disputed, help conversion committed, attempt abandoned, deadline reached, lease conflict, deletion acknowledged. Reject stale revisions/callbacks; evidence commits are idempotent.

**Acceptance tests to execute, not results.**

| Test | Required Outcome |
|---|---|
| Ignore permission; deny; remove/busy device; unsupported MIME | Text remains usable; correct cause guidance; late grant stopped; no empty recording graded. |
| Rapid start/pause/resume/finish; final chunk arrives late | One acknowledged transition; final chunk included; input released; no duplicate submission. |
| Lock phone/close/reload; corrupt or evict local draft | Explicit resume/review only; honest recovery limitation; missing work unscored, not zero. |
| Drop upload response; repeat retry; exhaust quota/storage | Receipt reconciliation; one charge/evidence event; capture not commercially interrupted; storage warning truthful. |
| Unclear ASR, edit then confirm, add reasoning, dispute | Original/corrected/supplement traceable; confirmed revision graded; uncertain score null; superseded evidence not double-counted. |
| Transfer hint/deep link/second tab; cancel/confirm help | Lock enforced by mode; canceled dialog preserves paused work; committed conversion unlocks and excludes independent success. |
| Slow jobs, malformed grading, expired sign-in | Pending/error distinguished; recover same job and draft; no fabricated score or restart. |
| Reload/offline at exam deadline; session takeover | Deadline persists; partial work retained; corrections/additions distinguished; stale writer cannot overwrite. |
| Keyboard + NVDA/VoiceOver; mobile keyboard/zoom; RTL | Complete text/audio paths; names/status readable; no timer chatter/traps/covered focus; player/file selection operable; evidence understandable without color. |
| File failure, dashboard failure, delete retained audio | No false empty/mastery/source-ready state; per-file retry; playback/deletion statuses reflect acknowledgements. |

### Gaps
Release risks: codec/chunk recovery on actual mobile browsers, processor/backups deletion, reservation costs/limits, ASR/LLM reliability, and transfer-task novelty. Minor-student privacy, regional law, and exam accommodations need specialist review. ICO guidance fetch was blocked; privacy recommendations above rely on the successfully fetched W3C statement, not an asserted regulatory interpretation.
