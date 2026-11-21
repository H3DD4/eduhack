# ThinkFirst learner engine (v1.0)

**One sentence:** the event log is the memory, BKT + FSRS + a misconception state machine per concept is the
dynamic profile, and a prerequisite frontier + a Thompson-sampling bandit is the adaptation.

Code: `api/thinkfirst/modules/adaptation/engine/`. It is **pure Python**: no database, no web framework.
**JSON in → JSON out**, with a published JSON Schema. Tests: `api/tests/test_engine.py` (23) plus app integration tests.

```
            ┌─────────────────────────── engine (pure) ───────────────────────────┐
 events ──► │ 1 prepare: dedupe by event_id, drop other students, sort by time      │
 (JSON)     │ 2 evidence weight: symbolic/sufficient 1.0 · limited 0.5 · unsure 0   │
            │ 3 per concept:  BKT mastery · FSRS retention · misconception machine  │ ──► LearnerState (JSON)
            │                 + prerequisite softening                              │
            │ 4 policy: which concept (frontier) · which help (bandit)              │ ──► Recommendation (JSON)
            │ 5 metrics: AUC, Brier, recovery, delayed recall, IPS                  │ ──► Metrics (JSON)
            └───────────────────────────────────────────────────────────────────────┘
```

| File | Job |
|---|---|
| `schemas.py` | The JSON contract (inputs, outputs, config). Version `1.0` |
| `bkt.py` | Mastery: Bayesian Knowledge Tracing, help-aware |
| `retention.py` | Forgetting: FSRS-style stability and review dates |
| `misconceptions.py` | Mistake life-cycle state machine |
| `fold.py` | Replays events into the learner state (the heart) |
| `policy.py` | Next concept + next help action (bandit) |
| `metrics.py` | Is the model right? Is the policy helping? |
| `simulator.py` | Virtual students with known hidden states (for proof) |
| `__main__.py` | CLI: JSON on stdin → JSON on stdout |

---

## 1. Input: events (event sourcing)

The engine never stores anything. You give it the student's events and it **recomputes** the state, so a
correction or deletion just means "replay without that event".

```json
{"event_id": "e1", "student_id": "s1", "concept_id": "c2", "ts": "2026-03-01T09:00:00Z",
 "kind": "attempt", "item_id": "task-42", "is_fresh": true, "assistance": "none",
 "outcome": "incorrect", "evidence": "symbolic",
 "misconception_id": "distribution_first_term_only", "misconception_conf": 0.9}
```

| Field | Meaning |
|---|---|
| `kind` | `attempt`, `review_check`, `explanation` (scored) · `hint` (no effect) · `worked_example`, `refresher`, `refutation` (remediation) · `recommendation` (bandit log) |
| `assistance` | `none`, `hint_l1/2/3`, `worked_example`, `solution_revealed`, `guided` — any help makes the answer weaker evidence |
| `outcome` | `correct`, `partial`, `incorrect`, `unscored` (unscored moves nothing) |
| `evidence` | how reliable the grading was: `symbolic` (SymPy), `sufficient`, `limited`, `needs_verification` |
| `is_fresh` | first time this student sees this item |

Concepts come with their prerequisites and a closed misconception list:

```json
{"concept_id": "c2", "prerequisites": ["c1", "F1"], "order": 2,
 "misconceptions": [{"id": "distribution_first_term_only", "prerequisite_id": "F1"}]}
```

## 2. Mastery = BKT (Corbett & Anderson 1994), help-aware (Beck et al. 2008)

`p` = probability the student knows the concept (starts at `prior = 0.10`).

```
P(correct | knows)   = 1 − slip                 slip  = 0.10
P(correct | doesn't) = guess                    guess = 0.15 unaided, 0.55 with help
correct:   p_post = p(1−slip) / [p(1−slip) + (1−p)·guess]
incorrect: p_post = p·slip    / [p·slip + (1−p)(1−guess)]
partial:   average of both
weighting: p_post = w·p_post + (1−w)·p          w from `evidence`
learning:  p_new  = p_post + (1 − p_post)·learn learn = 0.15
```

**Worked example:** p = 0.10, a correct unaided answer → 0.10·0.9 / (0.09 + 0.9·0.15) = **0.40**, then learning →
0.40 + 0.6·0.15 = **0.49**. The same correct answer *with a hint* only gives about 0.25. That is why help
never counts as proof.

Parameters are set by hand for now. Fitting them needs ≥ 50–100 students (pyBKT later).

## 3. Retention = FSRS-style forgetting curve

`S` = stability, in days, until recall probability falls to 90%.

```
R(t) = (1 + t / (9·S))^−1                      recall probability t days after the last unaided success
first unaided success:            S = 1 day
unaided success ≥ 1 day later:    S ← S · (1 + 0.5 + 2·(1 − R))   (harder recall → bigger growth)
unaided failure (lapse):          S ← max(0.5, 0.3·S)
same-day repeats / helped answers: no change (spacing effect)
review due when R < 0.85  →  due date = last success + 9·S·(1/0.85 − 1) ≈ 1.59·S days
```

Example: S = 1 day, and the student succeeds 3 days later. Then R = (1 + 3/9)^−1 = 0.75, so S grows to 1·(1 + 0.5 + 0.5) = 2 days.

## 4. Misconception state machine (closed "bug library")

```
suspected ──(2nd time, or confidence ≥ 0.8)──► active
active ──(worked example / refresher / refutation)──► remediating
remediating ──(2 fresh unaided successes)──► monitoring
monitoring ──(unaided success ≥ 3 days later)──► resolved
any ──(same mistake again)──► active   (relapse counted, history kept)
```

**Prerequisite propagation (graph idea without a neural network):** when a misconception becomes active and its
taxonomy entry points to a prerequisite, that prerequisite's mastery is multiplied by 0.85 and flagged for a
diagnostic check. An active misconception also caps the concept's level at 3.

## 5. Levels (what the student sees — never a raw %)

| Level | Label | Rule |
|---|---|---|
| 0 | Not started | no scored answer |
| 1 | Introduced | p < 0.3 |
| 2 | Practising | p ≥ 0.3 |
| 3 | Developing | p ≥ 0.6 |
| 4 | Proficient | p ≥ 0.8 **and** ≥ 1 unaided success |
| 5 | Mastered | p ≥ 0.95 **and** ≥ 2 unaided successes **and** a successful delayed check, no active misconception |

## 6. Policy

**Which concept** (ZPDES-style frontier, each with a written reason), in this order:
1. `remediate`: an active/remediating misconception
2. `review`: FSRS recall below 85%
3. `diagnostic_check`: a prerequisite softened by a mistake upstream
4. `frontier`: not proficient yet, and every (non-foundation) prerequisite ≥ 0.70
5. `continue`: least-developed remaining concept

Foundations are optional refreshers, never gates.

**Which help to offer first** (Thompson-sampling bandit):
- context = `"<misconception or generic>|<mastery low/mid/high>"`
- actions = targeted hint · worked example · prerequisite refresher · guided retry · refutation
- each (context, action) has a Beta(α, β), starting from **pedagogy priors**: worked examples favoured at low
  mastery, refutation favoured for a named misconception
- reward = the student's **next fresh unaided answer** on that concept (1 correct / 0 wrong / 0.5 partial)
- pick = the highest single Beta draw; **propensity** = P(that action wins), logged for offline evaluation
- learns at **population level** from an aggregate table (counts only, no student IDs)
- it only decides what to *offer first*: the student's help ladder is never withheld

## 7. Validation (how we know it works)

`python -m thinkfirst.modules.adaptation.engine simulate 200 3 | python -m thinkfirst.modules.adaptation.engine evaluate`

Results on 200 virtual students following the BKT story with hidden truth (seed 3):

| Metric | Value | Meaning |
|---|---|---|
| State recovery | **88.5%** | engine's "proficient" call matches the hidden truth |
| AUC (next-answer prediction) | **0.774** | vs **0.872 oracle ceiling** (a perfect model knowing the hidden state) → 89% of the possible |
| Brier score | 0.191 | calibration error (lower is better) |
| Misconceptions activated / resolved | 91 / 29 | full life-cycle exercised |
| Delayed recall rate | 0.76 | share of delayed unaided checks passed |
| IPS | supported | scores a new help policy on logged data without risking students |

The tests prove: the hand-checked BKT numbers, the forgetting curve, order-independence and dedupe, that unscored
moves nothing, that deletion replays, the level rules, the full misconception life-cycle and relapse, prerequisite
softening, frontier order, bandit reproducibility and learning, AUC and IPS values, simulator recovery ≥ 85%, and
CLI/HTTP JSON validation.

## 8. How to call it

**Python**
```python
from thinkfirst.modules.adaptation.engine import fold_json, recommend_json, evaluate_json, json_schemas
state = fold_json({"student_id": "s1", "concepts": [...], "events": [...]})
```
**CLI** (UTF-8 JSON on any OS)
```
python -m thinkfirst.modules.adaptation.engine fold      < fold_request.json      > state.json
python -m thinkfirst.modules.adaptation.engine recommend < recommend_request.json > rec.json
python -m thinkfirst.modules.adaptation.engine evaluate  < evaluate_request.json  > metrics.json
python -m thinkfirst.modules.adaptation.engine schema
```
**HTTP** (logged in): `POST /api/engine/fold | /recommend | /evaluate`, `GET /api/engine/schema`.
For the logged-in student: `GET /api/subjects/{id}/learner-state`.

## 9. How the app feeds it

| App moment | Event written to `memory.learning_events` |
|---|---|
| answer graded | `attempt` / `explanation` / `review_check` with outcome, help level, evidence, fresh?, misconception code |
| help step 1–3 | `hint` (no effect on mastery) |
| worked example / solution | `worked_example` (remediation) |
| wrong practice answer | engine picks a help → `recommendation` row (action, context, propensity) and the UI suggests it |
| next fresh unaided answer | rewards that recommendation → `adaptation.bandit_stats` (+1 success or failure) |

`modules/adaptation/service.py` only translates the app's data into engine JSON and back. The learning logic lives
only in the engine, so features can change without touching it.

## 10. Extending it safely
- New misconceptions: add them to `TAXONOMY` (or per-concept specs). The engine needs no change.
- New action type: add it to `EngineConfig.actions` and its prior in `policy.priors`.
- Tune numbers: everything is in `EngineConfig` and can be passed per request (`"config": {...}`).
- Breaking contract change: bump `ENGINE_VERSION`.
- With ≥ 1000 students: fit BKT with pyBKT; compare DKT/simpleKT through pyKT against this baseline using the same
  `evaluate` metrics; only then consider graph models.
