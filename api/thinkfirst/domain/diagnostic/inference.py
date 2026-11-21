"""Per-skill state and graph inference.

A correct answer on a skill raises its prerequisites; a wrong answer lowers the skills that depend on it.
Directly measured skills resist inference (damped by their evidence count) and inferred values are flagged
"inferred" so the profile can say so.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from thinkfirst.domain.knowledge.graph import SkillGraph


@dataclass(frozen=True)
class SkillState:
    skill_id: str
    p_l: float                # BKT P(L)
    n: int = 0                # credible direct answers (rapid guesses do not count)
    rapid: int = 0            # rapid guesses that touched this skill (kept for data quality)
    inferred: bool = False    # moved by graph inference only, never measured directly


def spread(graph: SkillGraph, states: dict[str, SkillState], skill_id: str, correct: bool, *,
           strength: float = 0.3, decay: float = 0.5) -> dict[str, SkillState]:
    """Return new states after propagating one answer along the prerequisite graph."""
    out = dict(states)
    targets = graph.ancestors_with_distance(skill_id) if correct else graph.descendants_with_distance(skill_id)
    for sid, dist in targets.items():
        st = out[sid]
        delta = strength * (decay ** (dist - 1)) / (1 + st.n)
        p = st.p_l + (1.0 - st.p_l) * delta if correct else st.p_l * (1.0 - delta)
        out[sid] = replace(st, p_l=p, inferred=st.n == 0)
    return out
