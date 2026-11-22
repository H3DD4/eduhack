"""Answer checking for numbers and expressions. SymPy when installed; returns None when it cannot decide."""

from __future__ import annotations

import re


def parse_number(s: str) -> float | None:
    s = str(s).strip().replace("\u2212", "-").replace(" ", "")
    m = re.fullmatch(r"(-?\d+(?:[.,]\d+)?)(?:e(-?\d+))?%?", s, re.I)
    if m:
        v = float(m.group(1).replace(",", "."))
        return v * (10 ** int(m.group(2))) if m.group(2) else v
    m = re.fullmatch(r"(-?\d+)/(\d+)", s)
    if m and int(m.group(2)):
        return int(m.group(1)) / int(m.group(2))
    return None


def numbers_equal(a: str, b: str, tol: float = 0.0) -> bool | None:
    x, y = parse_number(a), parse_number(b)
    if x is None or y is None:
        return None
    t = tol if tol > 0 else 1e-9 * max(1.0, abs(y))
    return abs(x - y) <= t


def _to_sympy(s: str):
    import sympy
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    s = str(s).strip().strip("$")
    s = s.replace("\\cdot", "*").replace("\\times", "*").replace("×", "*").replace("·", "*").replace("−", "-")
    s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", s)
    s = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", s)
    s = s.replace("\\left", "").replace("\\right", "").replace("{", "(").replace("}", ")").replace("\\", "")
    s = re.sub(r"\bln\b", "log", s)
    if "=" in s:
        s = s.split("=")[-1]
    tr = standard_transformations + (implicit_multiplication_application, convert_xor)
    return parse_expr(s, transformations=tr, local_dict={"e": sympy.E, "pi": sympy.pi})


def expressions_equal(a: str, b: str) -> bool | None:
    try:
        import sympy

        ea, eb = _to_sympy(a), _to_sympy(b)
        diff = sympy.simplify(ea - eb)
        if diff == 0:
            return True
        syms = list(diff.free_symbols)
        if not syms:
            return abs(complex(diff.evalf())) < 1e-9
        import random

        for _ in range(6):  # numeric spot check for forms simplify misses
            vals = {s: random.uniform(0.3, 2.7) for s in syms}
            if abs(complex(diff.evalf(subs=vals))) > 1e-6:
                return False
        return True
    except Exception:  # noqa: BLE001 - not installed / not parsable
        return None


def parses(expr: str) -> bool | None:
    try:
        _to_sympy(expr)
        return True
    except ImportError:
        return None
    except Exception:  # noqa: BLE001
        return False
