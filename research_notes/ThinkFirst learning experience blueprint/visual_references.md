# ThinkFirst: Duolingo-Inspired Visual Design, Motion, and Ethical Game Mechanics

Cutoff: November 21, 2026. Scope: individual university/engineering learners; responsive web; French, English, Arabic. Method: WebFetch, not browser inspection. **Cited Findings** report source text; **Inferences** contain original recommendations, not verified Duolingo specifications. Navigation and detailed audio/accessibility design belong to other researchers.

## What Should ThinkFirst Borrow, Adapt, and Reject?

### Takeaway

Duolingo is the main inspiration for approachable, action-first learning; borrow its design discipline, not its identity or pressure mechanisms. An inviting academic expedition should foreground the problem and reasoning, not the game.

### Cited Findings

- **Discovery limitation:** [design.duolingo.com](https://design.duolingo.com/) returned a design-article hub linking the redesign and widget articles, not a readable color/typography/button/motion rule library. [duolingo.com](https://www.duolingo.com/) returned only its title. Remembered legacy tokens cannot be presented as currently observed brand rules.
- **Current design rationale:** the February 4, 2026 redesign addresses inconsistent headers, weak typography hierarchy, and inconsistent spacing through purpose-dependent header tiers, consistently positioned titles, fewer type styles, and whitespace rather than unnecessary containers. It balances consistency with purpose and simplicity with clarity. [Official design account](https://blog.duolingo.com/core-tabs-redesign/)
- **Purposeful decoration:** that article warns against header artwork occupying space without useful meaning. It reports phone prototypes and QA across languages/devices, not tests conducted here. Its engagement improvement has no published effect size. [Official design account](https://blog.duolingo.com/core-tabs-redesign/)
- **Learning-path flexibility:** the October 1, 2026 article describes personalized practice within the path and voluntary review of previously seen content. Unit labels identify section, unit, and topic; learners choose new material or targeted review. [Official product explanation](https://blog.duolingo.com/how-to-review-lessons-on-duolingo/)
- **Expression can create pressure:** the widget shows today's lesson status and streak; Duo becomes increasingly desperate near midnight. Its retention claims concern continued use, not independently demonstrated learning. [Official widget account, August 2023](https://blog.duolingo.com/widget-feature/)
- **Secondary references:** Brilliant describes a shared interactive canvas, guiding questions, hints, adaptive assessments, and targeted review. Forest describes accumulated focus sessions but intentional loss through dying trees in strict sessions, despite "no shame" positioning. These are product descriptions, not independent effectiveness findings. [Brilliant](https://brilliant.org/); [Forest](https://www.forestapp.cc/)

### Inferences

**Borrow:** clear task titles, short instructions, generous separation, readable state labels, identifiable primary actions, rounded controls, and concise feedback. Use a small component vocabulary, not many decorative card variations. Tactility, geometry, and responsive rules below are ThinkFirst proposals, not Duolingo measurements.

**Adapt:** show four evidence stages: attempted, practised with adapted help, independently transferred, reviewed later. Use original glyphs and explicit labels, not Duolingo's winding path or node arrangement. Stages record evidence, not compulsory game gates. Supported practice must look legitimate, not damaged.

**Keep action-first:** one dominant action, such as "Check my reasoning," with "Get a hint" clearly available. Feedback names the next move: "Your setup is sound; check the units." Avoid "Wrong!", exaggerated red panels, accuracy shaming, and unsupported praise.

**Reject:** Duolingo's owl, characters, illustrations, proprietary fonts, assets, trademarks, and exact layouts; distressed companions; countdown guilt; punitive hearts/energy; mandatory streaks; public leaderboards; speed competition; scarcity around help. These exclusions do not imply every current Duolingo platform uses every mechanism. Reject Forest's dead-tree loss and group punishment; adapt accumulation into persistent discoveries.

### Gaps

No rendered layouts, hover/touch behavior, animation playback, or responsiveness were tested. Fetched image descriptions are not viewed screenshots. No current brand-token library was readable, nor is a universal "best website" conclusion supported. Historical articles do not establish current availability on every platform.

## What Original Visual and Motion System Should Be Built?

### Takeaway

Default to **Atlas Studio**: warm paper, deep ink, teal actions, amber discoveries, restrained geometric companionship, and a field-notebook atmosphere. Preserve friendliness and physical feedback without making engineering study a children's cartoon.

### Cited Findings

- Duolingo prioritizes purposeful hierarchy and spacing, not maximal illustration or containers everywhere. This supports restraint but supplies none of the numerical tokens below. [Design rationale](https://blog.duolingo.com/core-tabs-redesign/)
- Nunito Sans and Noto Sans Arabic use SIL Open Font License 1.1, permitting embedding/redistribution subject to conditions, including retaining copyright/license notices. This does not authorize copying proprietary Duolingo fonts or assets. [Nunito Sans license](https://raw.githubusercontent.com/google/fonts/main/ofl/nunitosans/OFL.txt); [Noto Sans Arabic license](https://raw.githubusercontent.com/google/fonts/main/ofl/notosansarabic/OFL.txt)

### Inferences

All values in this section are **original build recommendations**. Contrast compliance, font shaping, and device performance remain implementation verification tasks.

| Token | Proposed Value and Role |
| --- | --- |
| `canvas` / `surface` | `#F7F8F3` warm canvas / `#FFFFFF` working surface |
| `ink` / `ink-muted` | `#18282D` main text / `#526268` supporting text |
| `border` | `#CFDAD6` quiet grouping, never the sole state signal |
| `action` / `action-hover` | `#00796B` / `#00695D`; white button text |
| `action-base` | `#00564D` tactile bottom edge |
| `help` / `help-surface` | `#4B52A3` / `#EEEDFA`; hints are constructive, not failure |
| `discovery` | `#F1BB58`; amber highlights with dark ink, not white small text |
| `success` / `success-surface` | `#176B4E` / `#E7F4EC` |
| `needs-review` / `review-surface` | `#A23D35` / `#FFF0EB`; local corrective feedback only |
| `focus` | `#4453B6`; reserved for a visible focus outline |

**Typography:** use Nunito Sans for English/French interface and prose, with Noto Sans Arabic for Arabic. Self-host licensed webfont files and retain notices. Use weight 400 for body, 600 for labels, 700 for headings/buttons; avoid artificially rounded novelty lettering. Proposed Latin scale: metadata 14/20 px, body 16/26, problem prose 18/29, section heading 24/31, page heading 32/40. Arabic starts at body 17/29 and problem prose 19/32; adjust after native-reader review rather than forcing identical metrics. Do not letter-space Arabic or force uppercase French/English buttons. Mathematical notation uses a dedicated math renderer, not an ordinary UI font pretending to cover all symbols.

**Space and geometry:** 4 px scale: 4, 8, 12, 16, 24, 32, 48, 64. Gaps: 8 px related controls, 16 forms, 24 working groups, 32 sections. Radii: 8 px small details, 14 buttons/inputs, 20 task cards, 999 small status pills only. Prefer whitespace over nested boxes; reserve colored panels for meaningful status/discoveries.

**Responsive hierarchy:** overview maximum 1200 px, problem prose 48rem; gutters 16 px mobile, 24 medium, 32 wide. Below an initial 768 px breakpoint, stack working regions and use full-width primary actions. Use minimum, not fixed, card heights; wrap translations; contain equation overflow locally. These require implementation testing and are not observed Duolingo breakpoints.

**Tactile primary button:** minimum 52 px height, 20 px inline padding, 14 px radius, teal face, 4 px dark bottom edge. Press translates the face 2 px and reduces the edge to 2 px; release restores it. Hover changes tint, not target size. Keep the footprint stable during "Checking reasoning..."; prevent duplicate submissions without disabling help. Secondary controls remain flat/outlined. Explain missing prerequisites; incorrect attempts never disable learning.

**Icons/illustrations:** original 24 px grid, 2 px strokes, rounded joins, labels on consequential controls. Use compass facets, contour lines, diagram fragments, and constellation discoveries. Commission original artwork, not branded packs. An optional faceted guide can nod or tilt curiously, never cry, scold, or panic. Keep it peripheral and absent from equations; restrained expression preserves adult credibility.

**Motion:** easing `cubic-bezier(0.2, 0.8, 0.2, 1)`. Press 80 ms; release 120 ms; feedback opacity 140 ms; hint reveal 180 ms with at most 4 px translation; real evidence-progress update 240 ms; discovery reveal 260 ms. Major transfer/delayed-review success may receive one 500 ms constellation flourish away from the answer, without sound or forced waiting. Animate transforms/opacity, reserve space, and avoid layout jitter. No fake progress, infinite bobbing, particle showers, elastic overshoot, shaking, or celebrations on every substep.

**Energy decreases with concentration:** overview permits expedition motifs and milestone motion. Solving removes ambient motion/decorative headers; hints update locally. Recording suppresses companions, XP toasts, and celebrations until recording ends; control details belong to the audio researcher. Exam/practice-test mode uses plain surfaces, static progress, and recognition only afterward. A selectable quiet setting preserves content/rewards.

**Reduced motion:** honor `prefers-reduced-motion`; immediate static states replace decorative movement, translation, and count-up. Optional opacity transitions last at most 80 ms. Preserve button-state contrast and explicit feedback. Completion and next actions never depend on motion; state changes never await animation.

### Gaps

These tokens have not been visually validated. No official numerical Duolingo animation/button specification was observed. Arabic shaping, translated labels, low-end-device smoothness, and implemented contrast require checks; none are claimed to have passed.

## How Should Game Mechanics Represent Learning Ethically?

### Takeaway

Reward meaningful reasoning, useful correction, independent transfer, and later retrieval. Keep XP and discoveries separate from claims of mastery: progress is encouraging, but retained capability needs appropriately scoped evidence.

### Cited Findings

- Duolingo's Score increases through lessons/units and represents course-material progression, also associated with CEFR capabilities. This product explanation is not individual certification of retained engineering competence; its 2024 availability details are not a current exhaustive feature list. [Official Score explanation](https://blog.duolingo.com/duolingo-score/)
- Duolingo says spacing may not improve immediate performance, recommends active recall, and describes accuracy plus spacing selecting practice. This official explanation is not independent ThinkFirst validation. [Official learning guidance](https://blog.duolingo.com/spaced-repetition-for-learning/)
- Roediger and Karpicke's 2006 prose-recall experiments found repeated study superior after five minutes, but previous testing superior after two days/one week. This supports delayed checks, not a universal engineering-mastery threshold. [Paper DOI](https://doi.org/10.1111/j.1467-9280.2006.01693.x); [retrieved Europe PMC abstract](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%28EXT_ID%3A16507066%20AND%20SRC%3AMED%29%20OR%20DOI%3A10.1177%2F1745691615569000&resultType=core&format=json&pageSize=2)
- Soderstrom and Bjork's 2015 review distinguishes observable instructional performance from lasting learning supporting retention/transfer. Its abstract warns that acquisition performance can be an unreliable indicator of long-term learning. [Paper DOI](https://doi.org/10.1177/1745691615569000); [retrieved indexed abstract](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%28EXT_ID%3A16507066%20AND%20SRC%3AMED%29%20OR%20DOI%3A10.1177%2F1745691615569000&resultType=core&format=json&pageSize=2)

### Inferences

**Private XP, optional display:** pilot +5 for a first reasoned attempt, even mistaken; +10 for explaining/correcting a misconception with or without help; +15 for independent application to a distinct problem; +15 for successful later retrieval. These are product hypotheses, not research-derived optimal amounts. Attempt XP acknowledges effort, not proven learning. Different evidence events are not bonuses for refusing support.

Award events once per task/concept and eligible review occasion; repeated identical submissions cannot farm points. Never subtract XP for hints, mistakes, retries, absences, or easier work. No speed multipliers, paid boosters, randomized rewards, or escalating targets. XP never gates explanations or determines academic grades.

**No recording-length incentive:** apply the same conceptual rubric to typed, drawn, or spoken reasoning. Duration, word count, accent, and silence are not learning evidence; short valid explanations suffice. Uncertain interpretation/grading shows "Needs verification" and permits correction, not invented praise or withheld help. Previous hints remain neutral history; fresh independent problems can demonstrate transfer normally.

**Evidence-card badges:** "Misconception resolved," "Applied in a new context," and "Recalled later" link to work/date. Login counts, minutes, and path completion do not earn mastery badges. Discoveries persist; later errors prompt review, not destruction. Collections stay private, hideable, and outside solving.

**Rhythm instead of pressure:** default to "2 study days this week" and learning events, with a learner-chosen target. Any streak is opt-in, schedule-based, and freely pausable. Absence never removes XP, badges, access, or evidence. No midnight danger, distressed illustrations, repair purchases, rankings, or friend obligations. Say "Ready for a short review?", not "Don't lose everything."

**Evidence, not omniscient mastery:** distinguish "Introduced," "Practised with support," "Applied independently," and "Recalled on [date]" with concept, difficulty, assistance, and recency. A pilot gate could require independently explained solutions on two variants plus later retrieval; this is not a validated universal threshold. Use subject-approved rubrics/varied contexts and validate delayed performance before broader competence claims. Avoid "87% mastered" derived from XP or AI confidence.

Evaluate independent transfer, delayed recall, voluntary return, and reported pressure, not session length/streak retention. Test whether points distract or promote superficial tasks; preserve the learning loop with rewards hidden. Quiet solving and exam modes receive equivalent credit afterward.

### Gaps

Papers were accessed as indexed abstracts, not full texts; PubMed returned a cookie challenge. Prose-memory experiments do not establish effects for this product. XP amounts, badge gates, and design tokens lack causal validation; current hearts/energy availability was not verified. Product-specific learning/pressure evaluation must precede mastery or effectiveness claims.
