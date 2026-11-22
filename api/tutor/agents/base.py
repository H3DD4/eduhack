"""Shared context every agent receives: settings, store, LLM gateway, knowledge base, search and scraper.

Agents never call each other. They read the track state from the store, do one job, write their results,
and return a small state patch. The orchestrator decides what runs next.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..config import TutorSettings
from ..schemas import now_iso
from ..similarity import CourseProfile

log = logging.getLogger("tutor.agents")


@dataclass
class Ctx:
    settings: TutorSettings
    store: Any
    llm: Any
    kb: Any
    search: Any = None
    fetcher: Any = None
    emit: Callable[[str, dict[str, Any]], None] | None = None   # event hook (SysBrain bus)
    _profiles: dict[str, CourseProfile] = field(default_factory=dict)

    # --------------------------------------------------------------- records
    def track(self, track_id: str) -> dict[str, Any]:
        t = self.store.get("tracks", track_id)
        if t is None:
            raise KeyError(f"track {track_id}")
        return t

    def save_track(self, t: dict[str, Any], **changes: Any) -> dict[str, Any]:
        t.update(changes)
        t["updated_at"] = now_iso()
        self.store.put("tracks", t)
        return t

    def concepts(self, track_id: str) -> list[dict[str, Any]]:
        return sorted(self.store.list("concepts", track_id=track_id), key=lambda c: c.get("ord", 0))

    def concept_map(self, track_id: str) -> dict[str, dict[str, Any]]:
        return {c["key"]: c for c in self.concepts(track_id)}

    def fingerprint(self, track_id: str) -> dict[str, Any]:
        return self.store.get("fingerprints", track_id) or {}

    def profile(self, track_id: str, refresh: bool = False) -> CourseProfile:
        if refresh or track_id not in self._profiles:
            self._profiles[track_id] = CourseProfile.build(self.fingerprint(track_id), self.kb.chunks(track_id))
        return self._profiles[track_id]

    def learner(self, track_id: str) -> dict[str, dict[str, Any]]:
        return {r["concept_key"]: r for r in self.store.list("learner", track_id=track_id)}

    def event(self, name: str, payload: dict[str, Any]) -> None:
        if self.emit:
            try:
                self.emit(name, payload)
            except Exception:  # noqa: BLE001 - events never break a flow
                log.exception("event hook failed")

    def llm_json(self, task: str, variables: dict[str, Any], track_id: str, tier: str | None = None) -> dict[str, Any]:
        t = self.track(track_id)
        if t.get("budget_used", 0) > self.settings.llm_budget_tokens_per_track and not self.llm.simulated:
            raise BudgetExceeded(track_id)
        return self.llm.json(task, variables, track_id=track_id, tier=tier)


class BudgetExceeded(Exception):
    pass
