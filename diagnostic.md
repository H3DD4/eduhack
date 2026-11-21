ThinkFirst — Architecture up to the Diagnostic
21 nov. 2026 · @TLILI YOUSSEF
Summary
This doc details everything that happens before a student's first real study session. It runs from how the team discovers what to build to the moment the diagnostic hands a calibrated profile to the tutor. It extends Document.
It covers two tracks that run in parallel:
• The team track (design thinking). How we learn what students need, decide what to build and test it: empathize, define, ideate, prototype, test.
• The system track (the student's first 15 minutes). Onboarding → consent → subject setup and knowledge space → adaptive diagnostic → initial profile. A behavioral tracking layer records evidence from the first tap.
The design in one line: the diagnostic should feel like a short, encouraging conversation, while it measures mastery, misconceptions, confidence and learning behavior at the same time, so the tutor starts from evidence instead of guesses.
At a glance
The team track loops until the riskiest assumptions are tested. Every step of the system track writes events into the tracking layer, which the diagnostic and the profile then use.
Team track: design thinking
We run the five design-thinking phases (Stanford d.school model) before and alongside the build. Each phase has a clear exit criterion, so the work can't drift into building features nobody asked for. Loops are expected: a failed test sends us back to Define or Ideate.
Phase
Key question
Activities
Artifacts
Exit criterion
1. Empathize
How do students really study, and where does AI hurt them?
12–15 interviews (5 high school, 5 university, 3 self-learners); shadow 3 study sessions; a diary study during one exam week; survey (n ≥ 50) on AI use
Interview notes, empathy maps, study-session observations, survey results
Clear patterns repeated across 5+ students
2. Define
Which problem, for whom, first?
Affinity mapping of findings; personas; journey map of a study week; jobs to be done; problem statement
2–3 personas, journey map, "How might we" questions, one-line problem statement
Team agrees on one primary persona and one core problem
3. Ideate
What could solve it?
Crazy 8s, "How might we" brainstorm, assumption mapping (desirability, feasibility, viability)
Idea board, ranked concepts, assumption map with the riskiest assumptions marked
Top 3 riskiest assumptions chosen to test
4. Prototype
What's the cheapest way to test it?
Paper prototype of onboarding; clickable Figma flow; a "Wizard of Oz" diagnostic where a team member plays the AI
Prototypes, test script
Each risky assumption has a test
5. Test
Does it work for real students?
5 usability tests per round (think-aloud); measure time, completion, confusion points; SUS questionnaire
Test findings, a list of fixes, updated assumptions
Onboarding done in < 3 min by 4 out of 5 testers, and students say the diagnostic felt fair
Riskiest assumptions to test first
1.  Students will accept an AI that won't give answers if help is graduated and the first win comes quickly.
2.  A diagnostic of 8–12 questions feels short and fair, not like an exam.
3.  Students will rate their confidence honestly before answering.
4.  Students will upload their own courses (or prefer curated chapters).
5.  A prerequisite explanation ("your real gap is X") feels helpful, not judging.
Team rituals
• Weekly insight review: 30 minutes to share what students said and did, before discussing features.
• Decision log: each decision with the evidence behind it and the assumption it rests on.
• Student panel: 6–8 classmates who test each new version through the build.
Personas and jobs to be done
These are hypothesis personas from the two source documents. The Empathize phase confirms or replaces them with real interview data.
Persona
Context
Job to be done
Main pain
What the diagnostic must do for them
Sara, 15, bac student
Struggles with equations, loves football, studies at home in the evening
"When I'm stuck on homework, help me understand it so I can do the next one alone."
Feels lost and judged; gaps from earlier years
Find the real prerequisite gap without making her feel behind; guardian consent
Amine, 20, engineering student
6 subjects, exams in 5 weeks, uses ChatGPT for exercises
"When exams are coming, help me know what to study first and prove I'm ready."
Disorganized; good homework scores, weak exam results
Fast, per-subject mastery map; honest calibration ("you think 80%, results say 45%")
Lina, 27, self-learner
Preparing a certification after work, 5 hours a week
"When I learn alone, give me a path and tell me when I've really got it."
No structure, no feedback
Place her on a roadmap quickly; respect limited time
During the Define phase, each persona gets an empathy map (says, thinks, does, feels) and a journey map of one study week.
Onboarding architecture
Onboarding takes under 3 minutes and asks only what the diagnostic and the plan actually use. Every question has a named consumer, so nothing is collected "just in case".
Step
What the student sees
Data captured
Used by
Time
1. Sign up
Google, Apple or email
Account, locale
Identity
15 s
2. Age gate
"What year were you born?"
Birth year only
Consent flow, minors rules
5 s
3. The deal
One screen: "I won't give you answers. I'll make you better at finding them."
Accepted (yes/no)
Policy gate
10 s
4. Goal
Exam, certification or mastery; exam date if known
Goal type, dates
Plan brain, diagnostic length
20 s
5. Level and field
School year or program, field
Level
Diagnostic prior (starting θ)
15 s
6. First subject
Upload course files or pick "learn solo" with a topic
Subject, sources
Subject brain
30 s
7. Self-assessment
"How confident are you in this subject?" (1–5)
Prior confidence
Calibration baseline
10 s
8. Rhythm
Typical study times, hours per week
Availability
Plan brain
20 s
9. Comfort
Language, voice on/off, interests (optional chips: football, music…)
Preferences
Presentation only
20 s
10. Start the diagnostic
"8–12 short questions to find where to start. It's not a test."
—
Session brain
—
Behavioral design
The onboarding uses established behavior-design models, applied ethically:
• Fogg Behavior Model (B = Motivation × Ability × Prompt). Keep ability high: one question per screen, tap instead of type, skip allowed on optional steps. The prompt is a single big button at each step.
• Self-determination theory (autonomy, competence, relatedness). Autonomy: the student picks the goal, subject and pace. Competence: the first diagnostic item is easy, for an early win. Relatedness: the avatar speaks warmly and uses the student's name.
• Commitment and implementation intentions. The student picks the time of their first real session ("Tomorrow at 18:00"), which raises follow-through.
• Progress cues. A light progress bar, with the remaining time shown in seconds, not steps.
• Growth framing. Everything says "where to start", never "your level" or "your score".
Ethical limits (no dark patterns): no fake urgency, no guilt messages, no hidden data collection, and no streaks before the student has chosen to set a goal.
Consent, privacy and minors gating
Consent is collected before any behavioral tracking starts. Tracking is split into tiers so students can say yes to the basics without saying yes to everything.
Tier
What it covers
Default
Can be turned off
Essential
Answers, correctness, help level, time per item, mastery
On (needed for the product to work)
No; the student can delete their account and data at any time
Learning behavior
Hesitation, edits, hint timing, session rhythm, give-ups
Asked, explained in one sentence
Yes
Voice and images
Voice explain-back, photos of paper work
Asked when first used
Yes
Anonymized research
Pooled, anonymized data to improve the product and publish outcome studies
Off until accepted
Yes
Minors (under 18)
1.  The age gate puts the account in minor mode: stricter content filters, no open web browsing, no research tier by default.
2.  Guardian consent is requested by email where the law requires it. Until it arrives, the student can try a demo subject, but no personal data beyond the account is stored.
3.  The legal age thresholds differ by country (Tunisian law 2004-63, GDPR age of digital consent by EU state): check with a legal advisor before launch.
Privacy by design
• Pseudonymous IDs in all learning events; real identity kept only in the Identity service.
• Raw events kept for a limited time (for example 12 months), then aggregated.
• Every score is traceable to its events and visible to the student.
• Export and delete at any time.
Knowledge space: from course to calibrated item bank
The diagnostic can only be as good as the map it measures against. Before any student is tested, each subject needs three things: a skill graph, a Q-matrix linking items to skills, and an item bank with known difficulty.
Pipeline
1.  Ingest: parse uploads or curated chapters; chunk and embed for RAG (see the unified design).
2.  Extract skills: the content extractor proposes skills, each one small and testable ("isolate the unknown in ax + b = c"), with its Bloom target and source pages.
3.  Link prerequisites: proposed edges (fractions → order of operations → equations). The graph must have no cycles. For curated chapters, a teacher or a strong student reviews it.
4.  Build the Q-matrix: each item is tagged with the skills it needs (often 1, sometimes 2–3). This lets one answer update several skills.
5.  Write misconception distractors: each multiple-choice item has wrong options linked to known errors ("x = 25/3" → forgot to subtract 5). Choosing one is evidence of that misconception, not just "wrong".
6.  Calibrate difficulty: start from the author's estimate (easy, medium, hard → starting Elo values). Then update from real answers. Items with too few answers stay "uncalibrated" and get lower weight.
7.  Mark diagnostic items: a smaller, high-quality set per skill (2–3 items) that is verified, unambiguous and quick to answer.
Knowledge Space Theory
We use the idea behind Knowledge Space Theory (used by ALEKS): the prerequisite graph limits which combinations of skills are plausible. If a student has mastered equations, they very likely know fractions. If they fail fractions, they very likely don't master equations. One answer therefore says something about several skills, which is why 8–12 items can cover a whole chapter.
Item bank quality rules
Rule
Why
At least 2 diagnostic items per key skill
One item alone can be a slip or a guess
Every reference answer verified (math checker, tests, or a human)
A wrong key makes the diagnostic lie
Generated items labeled and kept out of the diagnostic until calibrated
Unknown difficulty adds noise
Answerable in under 90 seconds
Keeps the diagnostic short
Written in each supported language, not machine-translated without review
Language must not become the tested skill
Behavioral tracking layer
Behavioral tracking records how a student works, not only whether the answer is right. It runs from the first onboarding tap and feeds three uses: a more accurate diagnostic, early signs of frustration or disengagement, and the Learning DNA. It is built in three layers: raw events → derived indicators → decisions.
Layer 1: event schema
Events follow the xAPI (Experience API) pattern: actor – verb – object – result – context. Using a learning-data standard keeps events consistent and exportable.
{
  "event_id": "evt_8f2c",
  "actor": "stu_42",
  "verb": "answered",
  "object": {"type": "item", "id": "maths_eq_017", "skills": ["isolate_unknown"]},
  "result": {"correct": false, "response": "x = 25/3", "misconception": "forgot_to_subtract", "duration_ms": 41200},
  "context": {"session": "ses_91", "phase": "diagnostic", "mode": "app", "help_level": 0, "confidence": 4, "device": "mobile", "locale": "fr"},
  "timestamp": "2026-11-21T18:40:12Z"
}
Core verbs: viewed, started, answered, edited, skipped, requested_help, received_hint, rated_confidence, paused, resumed, abandoned, completed, flagged_error.
Layer 2: signal catalog
Signal
Raw measure
Tier
Response time
Time from item shown to submit
Essential
Time to first action
Time before the first keystroke or tap
Learning behavior
Edits and revisions
Number of changes before submitting
Learning behavior
Help-seeking timing
Time and attempts before asking for help
Essential
Skips and give-ups
Items skipped, sessions abandoned mid-way
Essential
Confidence rating
1–5 before seeing the result
Essential
Session rhythm
Time of day, session length, breaks
Learning behavior
Focus switches
App sent to background during an item
Learning behavior
Free-text tone
Negative or frustrated wording in chat ("I'm stupid", "I give up")
Learning behavior
Layer 3: derived indicators
These are well-studied patterns in learning analytics. Each one has a simple first rule that is refined with data later.
Indicator
First rule (to calibrate)
What it changes
Rapid guessing
Answer faster than ~10% of the item's typical time
Answer gets low weight in the diagnostic; gentle "take your time" message
Gaming the system
Help requested repeatedly without real attempts, or answers cycled quickly
Policy gate keeps the ladder locked; coach checks in
Help avoidance
Long struggle, many errors, never asks for help
Professor offers a level-1 question proactively
Wheel spinning
Many attempts on one skill without mastery rising (e.g. 10+)
Switch strategy or go back to a prerequisite
Productive struggle
Slow, several edits, then correct
Positive signal: raises struggle-tolerance estimate
Frustration risk
Errors in a row + negative words + shorter answers
Short winnable item, encouragement, suggest a break
Disengagement
Long pauses, focus switches, falling response quality
Shorter session; Plan brain moves the next block
Over/under-confidence
Confidence vs. result gap over several items
Calibration feedback in the reflection step
Best study hours
Accuracy and speed by time of day
Plan brain schedules key sessions then
Indicators are probabilities with a confidence, never labels shown to the student. The student sees the effect ("let's try a shorter one"), not "you are frustrated".
What we never track
• Camera, microphone outside explicit voice features, or keystrokes outside the answer box.
• Location, contacts, other apps.
• Health or mental-health inferences. If chat signals real distress, the safety protocol directs the student to a trusted adult or a professional, and nothing is profiled.
• Any behavior data sold or shared with third parties.
Adaptive diagnostic engine
The diagnostic estimates mastery of the key skills of a subject with the fewest possible items (target 8–12, under 10 minutes). It combines computerized adaptive testing (CAT), the prerequisite graph and behavior signals.
How each step works
1.  Prior. The student's level and goal set a starting θ (Elo). All skills start uncertain. The first item is deliberately easy, for an early win.
2.  Select the skill. Pick the key skill whose mastery is most uncertain (P(L) closest to 0.5), weighted by importance (exam weight, number of skills that depend on it).
3.  Select the item. Pick the item for that skill whose predicted success is closest to 50%: that's where one answer tells us the most. Practice later targets ~70% instead, because there the goal is learning, not measuring.
p = \frac{1}{1 + 10^{(d - \theta)/400}} \qquad \text{choose the item that maximizes } p(1-p)
4.  Answer. The student rates confidence (1–5) first, then answers. An "I don't know" button is offered, so students don't guess blindly. No help is available.
5.  Check. Graded against a verified key. A wrong option linked to a misconception records that misconception. Behavior flags adjust the weight of the answer: a rapid guess counts for little, an "I don't know" counts as not mastered.
6.  Update. BKT updates every skill in the item's Q-matrix row. Elo updates θ. Graph inference spreads the evidence: a correct answer on a skill raises its prerequisites; a wrong answer lowers the skills that depend on it.
7.  Adaptive moves. Correct on an advanced skill → jump further up the graph. Wrong → go down to its prerequisite to find the real gap. Misconception detected → one follow-up item to confirm it.
Stopping rules
The diagnostic stops at the first of these:
• All key skills are clearly classified (P(L) < 0.2 or > 0.8).
• 12 items answered.
• 10 minutes reached.
• Fatigue or frustration signals: stop early, mark the profile "low confidence", and finish the measurement during the first sessions.
The last item shown is always one the student is likely to solve, so the diagnostic ends on a success.
Diagnostic output
The diagnostic ends by writing one initial profile that the tutor, the planner and the help ladder start from. Every value carries its own confidence, because a profile built from 10 answers is a starting estimate, not a verdict.
The initial profile
Field
Content
Example
Consumer
Mastery per skill
BKT prior P(L) with an evidence count
equations 0.40 (n=3), order of operations 0.35 (n=2)
Session brain, roadmap
Untested skills
Inferred from the graph, marked "inferred"
systems of equations: likely not mastered (inferred)
Subject brain
Knowledge frontier
Skills the student is ready to learn next (prerequisites met)
order of operations
Plan brain: first sessions
Ability θ
Elo level per subject
1080
Exercise selection
Expertise stage
Novice, intermediate, advanced per chapter
novice on equations
Guidance level, ladder start
Misconceptions
Detected error patterns with evidence
forgets to apply the operation to both sides (2 items)
Professor agent
Calibration
Confidence vs. accuracy gap
+25 points (over-confident)
Reflection coaching
Behavior priors
Response-time profile, help-seeking style, struggle tolerance (low confidence)
answers fast, doesn't skip
Ladder start, strategy choice
Data quality
Share of answers flagged as rapid guesses
1 of 11
Weighting; retest if high
What the student sees
The result screen is designed to motivate, not to rank:
1.  "Here's where we start": a roadmap with the frontier highlighted, not a score.
2.  One strength: something they already master (competence).
3.  The real gap, explained kindly: "Equations get easier once order of operations is solid. Let's start there."
4.  Calibration in one line: "You felt quite sure; a few answers say we should check. That's normal at the start."
5.  First session booked: at the time they chose during onboarding.
6.  Transparency: "Based on 11 answers. This gets more accurate every session."
SysBrain ownership and events
Each stage has one owning brain. Stages hand over through events, so any stage can be rebuilt or tested on its own.
Stage
Owner
Workers
Consumes
Publishes
Sign-up, age gate
Core (Identity)
—
—
user.created, age.gated
Consent
Core (policy gate)
—
age.gated
consent.updated
Onboarding conversation
Student brain
Companion voice
consent.updated
profile.seeded, goal.set
Subject setup
Subject brain
Content extractor, RAG
workspace.created
content.indexed, graph.built
Item bank and calibration
Subject brain
Generator, math checker
graph.built
items.ready
Behavioral tracking
Evidence brain
Indicator rules
All interaction events
indicator.updated
Adaptive diagnostic
Session brain
Grader, diagnostician
items.ready, profile.seeded
answer.graded, diagnostic.completed
Initial profile
Evidence brain
BKT, Elo
answer.graded, diagnostic.completed
mastery.updated, profile.ready
First plan
Plan brain
Planner solver
profile.ready, goal.set
plan.updated
Result screen
Student brain
Companion voice
profile.ready, plan.updated
—
The policy gate applies even during the diagnostic: no help on diagnostic items (they measure the starting point), and every item is graded by a verified key.
Validating the diagnostic and the onboarding
A diagnostic that is short but wrong is worse than none, so we measure it against a longer reference test before trusting it.
Check
Method
Target (to confirm)
Accuracy
Same students take the adaptive diagnostic and a full chapter test; compare mastery classification per skill
≥ 80% agreement on mastered vs. not mastered
Efficiency
Number of items and time to reach the stopping rule
8–12 items, under 10 minutes
Reliability
Retest a sample 2–3 days later with different items
Similar results for most skills
Prediction
Does initial mastery predict success in the first practice sessions?
Clear positive relation
Algorithm check offline
Run BKT, Elo and the graph inference on public datasets (ASSISTments, Junyi) before real students
Reasonable prediction accuracy vs. simple baselines
Fairness
Results by language, level and gender
No group systematically under-estimated
Onboarding completion
Funnel: sign-up → consent → subject → diagnostic done → first session
Find and fix the biggest drop-off step
Felt experience
Short survey after the result screen: fair? stressful? useful?
Most students say "fair" and "useful"
Behavior indicators
Compare rule-based indicators with what students say in think-aloud tests
Rules match observed behavior in most cases
A/B tests to run once there are enough users: diagnostic length (8 vs. 12 items), confidence rating on vs. off, and result screen wording.
Build order and open questions
The team track and the system track run in parallel. Design-thinking findings can change the system work at each step.
1.  Empathize and Define (weeks 1–3): interviews, personas, riskiest assumptions. In parallel: pick the MVP subject and 3–5 chapters.
2.  Knowledge space (weeks 2–4): skill graph, Q-matrix, 2–3 verified diagnostic items per key skill, misconception distractors.
3.  Event schema and tracking (week 3): xAPI-style events from day one, essential tier only. Indicators are computed offline at first.
4.  Prototype and test onboarding (weeks 3–5): paper, then Figma, then a Wizard-of-Oz diagnostic with 5 students.
5.  Diagnostic engine (weeks 4–6): item selection, graph inference, stopping rules, initial profile. Validate offline on public datasets.
6.  Result screen and first plan (week 6).
7.  Validation round (weeks 7–8): adaptive diagnostic vs. full chapter test with the student panel.
Open questions
[ ] Diagnostic per subject only, or also a short general check of study habits?
[ ] Which behavior indicators run live in the MVP, and which stay offline until validated?
[ ] How do we diagnose a subject built from a student's own upload, where no item bank is calibrated yet?
[ ] Retest policy: when should a diagnostic be repeated (long break, very low data quality)?
[ ] Exact legal age thresholds and guardian-consent process for each launch country.
References to verify
These are the concepts this design draws on. The list was written without looking the sources up for this doc. Check exact titles and years on Google Scholar before citing them.
• Design thinking: Stanford d.school, five-mode model (empathize, define, ideate, prototype, test); IDEO, The Field Guide to Human-Centered Design.
• Jobs to be done: Christensen et al., Competing Against Luck (2016).
• Fogg Behavior Model: B. J. Fogg, Tiny Habits (2019) and behaviormodel.org.
• Self-determination theory: Deci & Ryan; Ryan & Deci (2000), "Self-determination theory and the facilitation of intrinsic motivation".
• Implementation intentions: Gollwitzer (1999).
• Knowledge Space Theory: Doignon & Falmagne, Knowledge Spaces (1999); used by ALEKS.
• Computerized adaptive testing and IRT: Wainer et al., Computerized Adaptive Testing: A Primer; van der Linden & Glas.
• Q-matrix and cognitive diagnosis models: Tatsuoka (rule space); de la Torre (DINA model).
• Rapid guessing: Wise & Kong (2005), response-time effort.
• Gaming the system: Baker et al. (2004).
• Help avoidance and help seeking: Aleven et al. (2003).
• Wheel spinning: Beck & Gong (2013).
• Affect in learning: D'Mello & Graesser on confusion and frustration.
• Metacognition and calibration: Dunlosky & Rawson (2012) on overconfidence.
• xAPI: Experience API specification (ADL Initiative).