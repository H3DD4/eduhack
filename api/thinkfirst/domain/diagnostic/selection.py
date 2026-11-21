"""Choosing what to ask next: the most uncertain, most important skill; the item closest to 50% predicted success."""

from __future__ import annotations

from collections.abc import Collection, Sequence

from thinkfirst.domain.diagnostic.inference import SkillState
from thinkfirst.domain.knowledge.graph import Skill, SkillGraph
from thinkfirst.domain.knowledge.qmatrix import Item
from thinkfirst.domain.mastery import elo


def is_classified(st: SkillState, low: float, high: float, min_evidence: int) -> bool:
    """Clearly mastered / not mastered. One direct answer alone can be a slip or a guess, so a measured skill
    needs `min_evidence` credible answers; a skill never measured can be classified by graph inference."""
    if low <= st.p_l <= high:
        return False
    return st.n >= min_evidence or st.n == 0 and st.inferred


def uncertainty(st: SkillState, min_evidence: int) -> float:
    """1.0 at P(L) = 0.5, 0.0 at 0 or 1. A skill with a single answer keeps a floor so it gets a second look."""
    base = 1.0 - abs(2.0 * st.p_l - 1.0)
    if 0 < st.n < min_evidence:
        base = max(base, 0.5)
    return base


def select_skill(graph: SkillGraph, states: dict[str, SkillState], available: Collection[str], *, low: float,
                 high: float, min_evidence: int) -> Skill | None:
    best: tuple[float, str] | None = None
    for s in graph.skills:
        if not s.is_key or s.id not in available:
            continue
        st = states[s.id]
        if is_classified(st, low, high, min_evidence):
            continue
        score = uncertainty(st, min_evidence) * graph.importance(s.id)
        if best is None or score > best[0]:
            best = (score, s.id)
    return graph.skill(best[1]) if best else None


def select_item(candidates: Sequence[Item], theta: float) -> Item | None:
    """Maximise p * (1 - p): the item whose predicted success is closest to 50%."""
    if not candidates:
        return None
    return max(candidates, key=lambda i: (elo.item_information(elo.expected_success(theta, i.difficulty)), -i.difficulty, i.id))


def select_first_item(candidates: Sequence[Item], graph: SkillGraph) -> Item | None:
    """The first item is deliberately easy, for an early win; ties go to the more important skill."""
    if not candidates:
        return None
    return min(candidates, key=lambda i: (i.difficulty, -max(graph.importance(s) for s in i.skills if s in graph), i.id))


def select_closing_item(candidates: Sequence[Item], states: dict[str, SkillState], theta: float, *,
                        min_success: float = 0.6, min_mastery: float = 0.6) -> Item | None:
    """The diagnostic ends on a success: an unasked item on skills the student seems to master and is likely to solve."""
    pool = [(elo.expected_success(theta, i.difficulty), i) for i in candidates
            if all(states[s].p_l >= min_mastery for s in i.skills if s in states)]
    pool = [(p, i) for p, i in pool if p >= min_success]
    if not pool:
        return None
    return max(pool, key=lambda t: (t[0], t[1].id))[1]
