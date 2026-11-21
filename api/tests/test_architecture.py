"""Architecture rules, enforced in CI.

1. `thinkfirst.domain` is pure: no framework, no database, no other thinkfirst package.
2. Every event type (constant or subscribed handler) has an owning brain and declared consumers.
"""

from __future__ import annotations

import ast
from pathlib import Path

import thinkfirst
import thinkfirst.models  # noqa: F401 — registers every event subscriber
from thinkfirst.core import events

ROOT = Path(thinkfirst.__file__).parent
FORBIDDEN = {"fastapi", "starlette", "sqlalchemy", "pydantic", "pydantic_settings", "httpx", "redis", "arq", "boto3",
             "alembic", "anthropic"}


def _imports(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module)
    return out


def test_domain_layer_is_pure():
    offenders: list[str] = []
    for path in (ROOT / "domain").rglob("*.py"):
        for mod in _imports(path):
            top = mod.split(".")[0]
            if top in FORBIDDEN or (top == "thinkfirst" and not mod.startswith("thinkfirst.domain")):
                offenders.append(f"{path.relative_to(ROOT)} imports {mod}")
    assert not offenders, "domain/ must stay framework-free:\n" + "\n".join(offenders)


def test_every_event_constant_has_a_contract():
    names = {v for k, v in vars(events).items() if k.isupper() and isinstance(v, str) and "." in v}
    assert names, "no event constants found"
    assert names <= set(events.EVENT_CONTRACTS), f"missing contracts: {sorted(names - set(events.EVENT_CONTRACTS))}"
    assert set(events.EVENT_CONTRACTS) <= names, "contract for an event with no constant"


def test_every_subscribed_event_has_a_contract():
    unknown = set(events._handlers) - set(events.EVENT_CONTRACTS)
    assert not unknown, f"subscribed to events with no contract: {sorted(unknown)}"


def test_event_contracts_are_well_formed():
    for name, c in events.EVENT_CONTRACTS.items():
        assert isinstance(c.owner, events.Brain), name
        assert all(isinstance(b, events.Brain) for b in c.consumers), name
