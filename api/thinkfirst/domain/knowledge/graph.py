"""Skill graph: small testable skills linked by prerequisites. Must be acyclic.

Knowledge Space Theory in one sentence: the prerequisite graph limits which combinations of skills are
plausible, so one answer says something about several skills.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Iterable
from dataclasses import dataclass


class GraphError(ValueError):
    pass


@dataclass(frozen=True)
class Skill:
    id: str
    name: str = ""
    chapter: str = ""
    weight: float = 1.0       # importance (exam weight)
    is_key: bool = True       # key skills are what the diagnostic must classify
    bloom: str | None = None  # Bloom target proposed by the content extractor


class SkillGraph:
    """`edges` are (prerequisite_id, skill_id) pairs."""

    def __init__(self, skills: Iterable[Skill], edges: Iterable[tuple[str, str]] = ()):
        self._skills: dict[str, Skill] = {}
        for s in skills:
            if s.id in self._skills:
                raise GraphError(f"duplicate skill {s.id!r}")
            self._skills[s.id] = s
        self._prereqs: dict[str, set[str]] = {sid: set() for sid in self._skills}
        self._dependents: dict[str, set[str]] = {sid: set() for sid in self._skills}
        for pre, sk in edges:
            if pre not in self._skills or sk not in self._skills:
                raise GraphError(f"edge ({pre!r}, {sk!r}) references an unknown skill")
            if pre == sk:
                raise GraphError(f"skill {sk!r} cannot be its own prerequisite")
            self._prereqs[sk].add(pre)
            self._dependents[pre].add(sk)
        self._order = self._toposort()

    # ---- basics ----
    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, skill_id: object) -> bool:
        return skill_id in self._skills

    @property
    def skills(self) -> list[Skill]:
        """Skills in topological order (prerequisites first)."""
        return [self._skills[sid] for sid in self._order]

    def skill(self, skill_id: str) -> Skill:
        return self._skills[skill_id]

    def prerequisites(self, skill_id: str) -> frozenset[str]:
        return frozenset(self._prereqs[skill_id])

    def dependents(self, skill_id: str) -> frozenset[str]:
        return frozenset(self._dependents[skill_id])

    # ---- traversal ----
    def _walk(self, start: str, nbrs: dict[str, set[str]]) -> dict[str, int]:
        dist: dict[str, int] = {}
        queue = deque([(start, 0)])
        while queue:
            node, d = queue.popleft()
            for nxt in nbrs[node]:
                if nxt not in dist:
                    dist[nxt] = d + 1
                    queue.append((nxt, d + 1))
        return dist

    def ancestors_with_distance(self, skill_id: str) -> dict[str, int]:
        """All (transitive) prerequisites with their shortest distance."""
        return self._walk(skill_id, self._prereqs)

    def descendants_with_distance(self, skill_id: str) -> dict[str, int]:
        """All (transitive) dependents with their shortest distance."""
        return self._walk(skill_id, self._dependents)

    def ancestors(self, skill_id: str) -> frozenset[str]:
        return frozenset(self.ancestors_with_distance(skill_id))

    def descendants(self, skill_id: str) -> frozenset[str]:
        return frozenset(self.descendants_with_distance(skill_id))

    # ---- derived ----
    def importance(self, skill_id: str) -> float:
        """Exam weight, boosted by the number of skills that depend on this one."""
        return self._skills[skill_id].weight * (1 + len(self.descendants(skill_id)))

    def frontier(self, mastered: Collection[str]) -> list[str]:
        """Skills ready to learn next: not mastered, every direct prerequisite mastered (topological order)."""
        done = set(mastered)
        return [sid for sid in self._order if sid not in done and self._prereqs[sid] <= done]

    def _toposort(self) -> list[str]:
        index = {sid: i for i, sid in enumerate(self._skills)}
        indeg = {sid: len(p) for sid, p in self._prereqs.items()}
        ready = sorted((s for s, d in indeg.items() if d == 0), key=index.get)
        order: list[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dep in sorted(self._dependents[node], key=index.get):
                indeg[dep] -= 1
                if indeg[dep] == 0:
                    ready.append(dep)
            ready.sort(key=index.get)
        if len(order) != len(self._skills):
            stuck = sorted(s for s, d in indeg.items() if d > 0)
            raise GraphError(f"prerequisite cycle among skills: {stuck}")
        return order
