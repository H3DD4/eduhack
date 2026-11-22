# Reading aids

Reading aids are optional presentation and input tools. They do not diagnose or label a student, and they do not
lower the intellectual level of lessons or exercises.

## Enable and adjust

Set `ENABLE_ACCESSIBILITY_MODULE=true` in the API environment and restart the API. The flag defaults to `false`.
Then open **Settings → Reading aids**, review the privacy notice, and explicitly agree before a profile is stored.
Each supported aid is adjustable separately. Turning the profile off restores the current app theme and prompt
behavior; **Delete profile** removes the saved settings and consent timestamp. **Export profile** downloads the
profile as JSON.

The profile stores typography, theme, speech, dictation, timing preferences, language-subject IDs, and a consent
timestamp. API operations are authenticated and scoped to the current student. The table has a row-level security
policy. No teacher/class dashboard is present in this build, and the profile is not exposed through teacher views.

## Available controls

- Font, size (14–20 px), line spacing, letter/word spacing, line width, cream/pastel/dark/high-contrast themes,
  live preview, and a pointer/focus-following line ruler.
- Existing user-initiated read-aloud controls remain available when enabled. Speech language can be selected as
  English, French, or Arabic, and speed can be adjusted. The existing avatar player provides pause/resume,
  captions, and word highlighting when the browser emits word-boundary events. If no voice for the selected
  language is available, the text stays visible and a status message explains why audio was not played.
- Browser dictation is available in supported answer and Professor text fields. Recognized words are inserted into
  the editable field; the student can edit the transcript before submitting. Dictation is off until separately
  enabled.
- Optional browser spelling suggestions use the field's native spell-check feature. The student can mark current
  subjects as language-learning subjects so spelling is not ignored for those subjects.
- Tutor-facing prompt rules are appended only for an active, consented profile. The existing Socratic approach,
  progressive hints, course-source constraints, and citation behavior are retained. The Professor panel provides
  “Simpler”, “Shorter”, and “With a diagram” quick prompts.
- The existing concept roadmap remains the visual concept map. The “Hide the timer” preference hides the optional
  timer in the current focus sheet.

## Privacy and known limits

- The accessibility flag is off by default; API endpoints are unavailable while it is off. An inactive profile
  does not alter current rendering, tutor prompts, or assessment outcomes.
- Browser speech recognition can process microphone audio using the browser's speech service. The consent notice
  says this before the student enables dictation. Typed input remains available. The existing explain-back audio
  workflow is separate and retains its own disclosure and transcript-confirmation requirements.
- Speech synthesis/recognition support and language voices depend on the browser and device. Arabic and Tunisian
  dialect quality is not guaranteed. The current UI is English-only; there is no complete French/Arabic translation
  catalog or dynamic Arabic RTL language mode.
- Arial and Verdana are commonly installed; Lexend, Atkinson Hyperlegible, and OpenDyslexic are requested by
  family name and fall back to an available sans-serif if the device does not have them. They are not bundled in
  this build.
- Spelling variation detection is conservative and only sets the separate nullable `spelling_error` metadata.
  Edit distance never decides correctness. For short-answer grading in active, non-language subjects, the
  existing semantic grader receives an appended instruction to ignore minor spelling/phonetic errors. This is
  still model-dependent; uncertain answers remain unscored. Existing expression checking continues to use its
  symbolic checker.
- “Extra time” is stored as a preference but does not affect timing: this build has no exam mode or secure exam
  timer. Word prediction, Arabic diacritic display, generated diagrams, and short-break scheduling are not
  implemented. The current teacher page is a student-facing 3D tutor, not a teacher/class dashboard, so no
  teacher indicator or teacher suggestion flow was added.
- The database migration is additive. Downgrade drops only the new profile table and nullable spelling column.

## Verification

Focused coverage checks consent/profile/export/delete, input validation, language-subject prompt behavior,
conservative English/French/Arabic normalization, and WCAG AA contrast for the supplied reading themes. Browser
speech services remain device-dependent and should be manually checked on each supported browser.
