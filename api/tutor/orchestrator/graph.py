"""Tutor orchestrator: a small checkpointed state graph (LangGraph-compatible shape).

Nodes are agent functions `fn(ctx, state) -> patch`. After every node the run is checkpointed in the store
(`runs` collection: node, state, step log), so a crash or a restart resumes at the failed node instead of
re-doing paid LLM work. `as_langgraph()` compiles the same graph with LangGraph when it is installed.
"""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..schemas import now_iso

log = logging.getLogger("tutor.orchestrator")
END = "__end__"

NodeFn = Callable[[Any, dict[str, Any]], dict[str, Any]]
Cond = Callable[[dict[str, Any]], bool]


@dataclass
class Graph:
    name: str
    nodes: dict[str, tuple[NodeFn, str]] = field(default_factory=dict)
    edges: dict[str, list[tuple[Cond | None, str]]] = field(default_factory=dict)
    start: str | None = None

    def node(self, name: str, fn: NodeFn, label: str = "") -> Graph:
        self.nodes[name] = (fn, label or name)
        self.start = self.start or name
        return self

    def edge(self, a: str, b: str, when: Cond | None = None) -> Graph:
        self.edges.setdefault(a, []).append((when, b))
        return self

    def chain(self, *names: str) -> Graph:
        for a, b in zip(names, names[1:], strict=False):
            self.edge(a, b)
        return self.edge(names[-1], END)

    def next(self, current: str, state: dict[str, Any]) -> str:
        for cond, target in self.edges.get(current, []):
            if cond is None or cond(state):
                return target
        return END


class Runner:
    def __init__(self, ctx):
        self.ctx = ctx

    def run(self, graph: Graph, run: dict[str, Any]) -> dict[str, Any]:
        store = self.ctx.store
        state = run.setdefault("state", {})
        node = run.get("node") or graph.start
        run.update(status="running", updated_at=now_iso())
        store.put("runs", run)
        while node and node != END:
            fn, label = graph.nodes[node]
            t0 = time.monotonic()
            run["node"] = node
            store.put("runs", run)
            try:
                patch = fn(self.ctx, state) or {}
            except Exception as exc:  # noqa: BLE001 - recorded on the run, resumable
                code = getattr(exc, "code", None) or str(exc)[:120] or type(exc).__name__
                run["steps"].append({"node": node, "label": label, "status": "failed", "error": code,
                                     "ms": int((time.monotonic() - t0) * 1000), "at": now_iso()})
                run.update(status="failed", error=code, updated_at=now_iso())
                store.put("runs", run)
                log.error("run %s failed at %s: %s\n%s", run["id"], node, code, traceback.format_exc(limit=4))
                try:
                    t = self.ctx.track(run["track_id"])
                    self.ctx.save_track(t, status="failed", stats={**t.get("stats", {}), "error": code, "failed_node": node})
                except Exception:  # noqa: BLE001
                    pass
                return run
            state.update(patch)
            run["steps"].append({"node": node, "label": label, "status": "done", "result": patch,
                                 "ms": int((time.monotonic() - t0) * 1000), "at": now_iso()})
            node = graph.next(node, state)
            run.update(node=node, state=state, updated_at=now_iso())
            store.put("runs", run)
        run.update(status="succeeded", node=END, updated_at=now_iso())
        store.put("runs", run)
        return run


def as_langgraph(graph: Graph, ctx):  # pragma: no cover - optional dependency
    """Compile the same graph with LangGraph (pip install langgraph) for its tooling and checkpointers."""
    from langgraph.graph import END as LG_END
    from langgraph.graph import StateGraph

    g = StateGraph(dict)
    for name, (fn, _) in graph.nodes.items():
        g.add_node(name, lambda s, _fn=fn: {**s, **(_fn(ctx, s) or {})})
    g.set_entry_point(graph.start)
    for a, outs in graph.edges.items():
        if len(outs) == 1 and outs[0][0] is None:
            g.add_edge(a, LG_END if outs[0][1] == END else outs[0][1])
        else:
            g.add_conditional_edges(a, lambda s, _a=a: graph.next(_a, s),
                                    {t: (LG_END if t == END else t) for _, t in outs} | {END: LG_END})
    return g.compile()
