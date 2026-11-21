"""Question selection and question/hint quality (pure; JSON in → JSON out).

select_item — which question to give THIS student next:
  1. never an item the student already saw (a retest must be fresh — especially after help on that item)
  2. never a retired item (quality report)
  3. while a misconception is active/remediating on the concept, prefer TRIGGER items: items written so that this
     exact mistake would show again (passing them is the evidence that the bug is fixed)
  4. otherwise match difficulty to mastery: target difficulty = 0.2 + 0.6 · p_mastery
     ("desirable difficulty": weak → easy items / worked practice, strong → harder, new-context items)
     difficulty = empirical (1 − success rate) once an item has ≥ min_attempts answers, else its declared level
quality — classical item analysis from AGGREGATE counts only (no student ids):
  p_value       = success rate (fresh, unaided answers)
  discrimination = success(high-mastery students) − success(low-mastery students)
  flags: too_easy (p ≥ 0.95), too_hard (p ≤ 0.15), suspect (discrimination < 0, or strong students fail ≥ 50%)
  status: ok | watch (flagged, little data) | retire (suspect with ≥ retire_min answers → excluded from selection)
Hints use the same idea: the share of times the student's next answer on that task was correct after the hint.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from thinkfirst.modules.adaptation.engine.schemas import ENGINE_VERSION

DECLARED = {"easy": 0.25, "medium": 0.5, "hard": 0.75}


class ItemSpec(BaseModel):
    item_id: str = Field(description="Stable across students (e.g. hash of the normalised question)")
    concept_id: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    triggers: list[str] = Field([], description="Misconception ids this item is designed to expose")
    order: int = 0


class BandCounts(BaseModel):
    attempts: int = 0
    correct: float = 0.0


class ItemStats(BaseModel):
    item_id: str
    low: BandCounts = BandCounts()
    mid: BandCounts = BandCounts()
    high: BandCounts = BandCounts()


class HintStats(BaseModel):
    hint_id: str
    shown: int = 0
    followed_by_correct: float = 0.0


class QualityConfig(BaseModel):
    min_attempts: int = 10
    retire_min: int = 20
    too_easy: float = 0.95
    too_hard: float = 0.15
    strong_fail: float = 0.5
    min_band: int = 5
    hint_min: int = 10
    hint_poor: float = 0.2


class QualityRequest(BaseModel):
    items: list[ItemStats] = []
    hints: list[HintStats] = []
    config: QualityConfig = QualityConfig()


class ItemQuality(BaseModel):
    item_id: str
    attempts: int
    p_value: float | None
    discrimination: float | None
    flags: list[str]
    status: Literal["ok", "watch", "retire", "new"]
    reason: str


class HintQuality(BaseModel):
    hint_id: str
    shown: int
    success_after: float | None
    status: Literal["ok", "watch", "rewrite", "new"]
    reason: str


class QualityReport(BaseModel):
    engine_version: str = ENGINE_VERSION
    items: list[ItemQuality]
    hints: list[HintQuality]


class SelectRequest(BaseModel):
    concept_id: str
    p_mastery: float = Field(ge=0, le=1)
    active_misconceptions: list[str] = []
    seen_item_ids: list[str] = Field([], description="Items this student already answered or got help on")
    candidates: list[ItemSpec]
    item_stats: list[ItemStats] = []
    retired_item_ids: list[str] = []
    quality: QualityConfig = QualityConfig()


class SelectResult(BaseModel):
    engine_version: str = ENGINE_VERSION
    item_id: str | None
    reason: str
    target_difficulty: float
    item_difficulty: float | None = None
    is_trigger: bool = False
    excluded: dict[str, int] = {}


def _rate(b: BandCounts) -> float | None:
    return b.correct / b.attempts if b.attempts else None


def item_quality(s: ItemStats, cfg: QualityConfig) -> ItemQuality:
    n = s.low.attempts + s.mid.attempts + s.high.attempts
    if n == 0:
        return ItemQuality(item_id=s.item_id, attempts=0, p_value=None, discrimination=None, flags=[], status="new",
                           reason="No answers yet.")
    p = (s.low.correct + s.mid.correct + s.high.correct) / n
    lo, hi = _rate(s.low), _rate(s.high)
    disc = (hi - lo) if (s.low.attempts >= cfg.min_band and s.high.attempts >= cfg.min_band) else None
    flags, why = [], []
    if n >= cfg.min_attempts and p >= cfg.too_easy:
        flags.append("too_easy")
        why.append(f"{p:.0%} succeed")
    if n >= cfg.min_attempts and p <= cfg.too_hard:
        flags.append("too_hard")
        why.append(f"only {p:.0%} succeed")
    if disc is not None and disc < 0:
        flags.append("suspect")
        why.append("strong students do worse than weak ones")
    elif s.high.attempts >= cfg.min_band and hi is not None and hi < cfg.strong_fail:
        flags.append("suspect")
        why.append(f"strong students fail {1 - hi:.0%}")
    if "suspect" in flags and n >= cfg.retire_min:
        status, lead = "retire", "Retired: likely unclear question or wrong answer key"
    elif flags:
        status, lead = "watch", "Watch"
    else:
        status, lead = "ok", "OK"
    return ItemQuality(item_id=s.item_id, attempts=n, p_value=round(p, 4),
                       discrimination=round(disc, 4) if disc is not None else None, flags=flags, status=status,
                       reason=f"{lead} ({'; '.join(why) or f'{n} answers'}).")


def hint_quality(h: HintStats, cfg: QualityConfig) -> HintQuality:
    if h.shown == 0:
        return HintQuality(hint_id=h.hint_id, shown=0, success_after=None, status="new", reason="Never shown yet.")
    r = h.followed_by_correct / h.shown
    if h.shown >= cfg.hint_min and r < cfg.hint_poor:
        status, reason = "rewrite", f"Only {r:.0%} answer correctly after this hint — rewrite it."
    elif r < cfg.hint_poor:
        status, reason = "watch", f"{r:.0%} success after this hint so far ({h.shown} uses)."
    else:
        status, reason = "ok", f"{r:.0%} success after this hint ({h.shown} uses)."
    return HintQuality(hint_id=h.hint_id, shown=h.shown, success_after=round(r, 4), status=status, reason=reason)


def quality(req: QualityRequest) -> QualityReport:
    return QualityReport(items=[item_quality(s, req.config) for s in req.items],
                         hints=[hint_quality(h, req.config) for h in req.hints])


def difficulty_of(spec: ItemSpec, stats: ItemStats | None, cfg: QualityConfig) -> float:
    if stats is not None:
        n = stats.low.attempts + stats.mid.attempts + stats.high.attempts
        if n >= cfg.min_attempts:
            return 1 - (stats.low.correct + stats.mid.correct + stats.high.correct) / n
    return DECLARED[spec.difficulty]


def select_item(req: SelectRequest) -> SelectResult:
    target = round(0.2 + 0.6 * req.p_mastery, 4)
    stats = {s.item_id: s for s in req.item_stats}
    retired = set(req.retired_item_ids) | {s.item_id for s in req.item_stats if item_quality(s, req.quality).status == "retire"}
    seen = set(req.seen_item_ids)
    pool = [c for c in req.candidates if c.concept_id == req.concept_id]
    excluded = {"seen": sum(c.item_id in seen for c in pool), "retired": sum(c.item_id in retired and c.item_id not in seen for c in pool)}
    pool = [c for c in pool if c.item_id not in seen and c.item_id not in retired]
    if not pool:
        return SelectResult(item_id=None, reason="No fresh, non-retired question left for this concept.",
                            target_difficulty=target, excluded=excluded)
    trig = [c for c in pool if set(c.triggers) & set(req.active_misconceptions)]
    use, is_trig = (trig, True) if trig else (pool, False)
    best = min(use, key=lambda c: (abs(difficulty_of(c, stats.get(c.item_id), req.quality) - target), c.order, c.item_id))
    d = difficulty_of(best, stats.get(best.item_id), req.quality)
    if is_trig:
        mids = sorted(set(best.triggers) & set(req.active_misconceptions))
        reason = f"Checks whether the mistake '{mids[0]}' is fixed, with a new question."
    else:
        reason = f"Difficulty {d:.2f} is closest to the {target:.2f} that fits your current mastery."
    return SelectResult(item_id=best.item_id, reason=reason, target_difficulty=target, item_difficulty=round(d, 4),
                        is_trigger=is_trig, excluded=excluded)
