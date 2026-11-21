"""CLI: JSON on stdin, JSON on stdout.

    python -m thinkfirst.modules.adaptation.engine fold      < fold_request.json
    python -m thinkfirst.modules.adaptation.engine recommend < recommend_request.json
    python -m thinkfirst.modules.adaptation.engine evaluate  < evaluate_request.json
    python -m thinkfirst.modules.adaptation.engine simulate  [n_students] [seed]   (prints an EvaluateRequest)
    python -m thinkfirst.modules.adaptation.engine schema
"""

from __future__ import annotations

import json
import sys

from pydantic import ValidationError

from thinkfirst.modules.adaptation.engine import evaluate_json, fold_json, json_schemas, recommend_json
from thinkfirst.modules.adaptation.engine.simulator import simulate


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    try:
        if cmd == "schema":
            out = json_schemas()
        elif cmd == "simulate":
            sim = simulate(int(argv[1]) if len(argv) > 1 else 50, int(argv[2]) if len(argv) > 2 else 7)
            out = {"student_events": sim["students"], "concepts": sim["concepts"]}
        elif cmd in ("fold", "recommend", "evaluate"):
            payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))  # standard JSON: UTF-8 on every OS
            out = {"fold": fold_json, "recommend": recommend_json, "evaluate": evaluate_json}[cmd](payload)
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except ValidationError as exc:
        _write({"error": "INVALID_INPUT", "details": json.loads(exc.json())})
        return 1
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _write({"error": "INVALID_JSON", "details": str(exc)})
        return 1
    _write(out)
    return 0


def _write(obj: dict) -> None:
    sys.stdout.buffer.write(json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
