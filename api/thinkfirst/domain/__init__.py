"""Pure domain layer: the algorithms behind the diagnostic and the behavioral tracking layer.

Rule (enforced by `tests/test_architecture.py`): nothing in this package imports FastAPI, SQLAlchemy, Pydantic,
HTTP clients, or any other `thinkfirst` package outside `thinkfirst.domain`. That keeps every algorithm
deterministic, testable offline (also on public datasets such as ASSISTments / Junyi) and reusable from the API,
the ARQ worker, or a notebook.

    mastery/     Elo (ability, item difficulty), BKT (per-skill mastery)
    knowledge/   skill graph (prerequisites, no cycles), Q-matrix, item bank and its quality rules
    consent/     consent tiers and minors gating
    tracking/    xAPI-style event schema, signal catalog + redaction by consent, rule-based indicators
    diagnostic/  adaptive engine: selection, graph inference, stopping rules, initial profile

Services in `modules/`, `data/` and `platform/` load and persist state, then call into this package.
"""
