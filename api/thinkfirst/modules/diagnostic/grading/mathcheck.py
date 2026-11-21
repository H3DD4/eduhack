"""Symbolic grading with SymPy (tool-based, not simulated). Unreadable input => unscored (None), never zero."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
_SAFE = re.compile(r"^[A-Za-z0-9+\-*/^(). ]{1,120}$")
_LOCALS = {c: sympy.Symbol(c) for c in string.ascii_letters}
_MATH_RUN = re.compile(r"[A-Za-z0-9+\-*/^(). ×·−]+")


def _clean(text: str) -> str:
    return (text.replace("×", "*").replace("·", "*").replace("−", "-").replace("–", "-")
            .replace(" ", " ").strip().rstrip("."))


def parse(text: str, evaluate: bool = True) -> sympy.Expr | None:
    """Parse a short algebraic expression. Restricted alphabet => no code execution surface."""
    s = _clean(text)
    if not s or not _SAFE.match(s):
        return None
    try:
        expr = parse_expr(s, local_dict=_LOCALS, transformations=_TRANSFORMS, evaluate=evaluate)
    except Exception:  # noqa: BLE001
        return None
    return expr if isinstance(expr, sympy.Expr) else None


def equivalent(a: sympy.Expr, b: sympy.Expr) -> bool:
    try:
        return sympy.simplify(sympy.expand(a) - sympy.expand(b)) == 0
    except Exception:  # noqa: BLE001
        return False


def is_expanded(text: str) -> bool:
    """Structural check on the UNEVALUATED parse: SymPy would auto-distribute 3*(x + 4) on evaluation."""
    e = parse(text, evaluate=False)
    if e is None:
        return False
    for node in sympy.preorder_traversal(e):
        if isinstance(node, sympy.Mul) and any(isinstance(a, sympy.Add) for a in node.args):
            return False
        if isinstance(node, sympy.Pow) and isinstance(node.base, sympy.Add):
            return False
    return True


def pretty(e: sympy.Expr) -> str:
    return str(e).replace("**", "^").replace("*", "")


@dataclass
class Split:
    factor: sympy.Expr
    terms: list[sympy.Expr]


def split_product(expr_text: str) -> Split | None:
    """a(t1 + t2 + ...) -> factor a, terms [t1, t2, ...]."""
    e = parse(expr_text, evaluate=False)
    if e is None or not isinstance(e, sympy.Mul):
        return None
    adds = [a for a in e.args if isinstance(a, sympy.Add)]
    if len(adds) != 1:
        return None
    factor = sympy.Mul(*[a for a in e.args if a is not adds[0]])
    return Split(factor=factor, terms=list(adds[0].args))


@dataclass
class CriterionResult:
    criterion: str
    status: str  # absent | partial | demonstrated | unscored | na
    quotes: list[dict] = field(default_factory=list)
    covered_essentials: list[str] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    rationale: str = ""

    @property
    def score(self) -> int | None:
        return {"absent": 0, "partial": 1, "demonstrated": 2}.get(self.status)

    def as_dict(self) -> dict:
        return {"criterion": self.criterion, "status": self.status, "score": self.score, "quotes": self.quotes,
                "covered_essentials": self.covered_essentials, "missing": self.missing, "rationale": self.rationale}


NA_EXERCISE = ("essential_coverage", "why_relationships", "example_application", "limits")


@dataclass
class GradeResult:
    criteria: list[CriterionResult]
    outcome: str
    sufficiency: str
    feedback: str
    reason: str = ""
    misconception: dict | None = None


def grade_expand(answer: str, expr_text: str) -> GradeResult:
    target = parse(expr_text)
    ans = parse(answer)
    na = [CriterionResult(c, "na") for c in NA_EXERCISE]
    quote = [{"sentence_id": "answer", "text": answer.strip()}]
    if target is None:
        return GradeResult([CriterionResult("correctness", "unscored", rationale="Task expression unreadable.")] + na,
                           "unscored", "needs-verification", "This task could not be checked automatically.",
                           reason="TASK_UNPARSEABLE")
    if ans is None:
        return GradeResult([CriterionResult("correctness", "unscored", rationale="Could not read this as an expression.")] + na,
                           "unscored", "limited",
                           "There is not enough reliable information to score this yet. Try writing it like 3x + 5.",
                           reason="ANSWER_UNPARSEABLE")
    if equivalent(ans, target):
        if is_expanded(answer):
            return GradeResult([CriterionResult("correctness", "demonstrated", quote,
                                                rationale="Equivalent to the original and fully expanded.")] + na,
                               "demonstrated", "sufficient",
                               f"Your expansion is equivalent and fully expanded: {pretty(sympy.expand(target))}.")
        return GradeResult([CriterionResult("correctness", "partial", quote,
                                            rationale="Equivalent, but still contains brackets.")] + na,
                           "partial", "sufficient", "Equivalent, but it still has brackets. Expand every term.")
    misconception = detect_distribution_misconception(answer, expr_text)
    feedback = f"Not equivalent to {expr_text}. Check each term."
    if misconception:
        feedback = misconception["message"]
    return GradeResult([CriterionResult("correctness", "absent", quote, rationale="Not equivalent to the original expression.")] + na,
                       "not_demonstrated", "sufficient", feedback, misconception=misconception)


def detect_distribution_misconception(answer: str, expr_text: str) -> dict | None:
    sp = split_product(expr_text)
    ans = parse(answer)
    if sp is None or ans is None or len(sp.terms) < 2:
        return None
    a, terms = sp.factor, sp.terms
    first_only = a * terms[0] + sympy.Add(*terms[1:])
    if equivalent(ans, first_only):
        return {
            "code": "distribution_first_term_only",
            "message": (f"Possible distribution misconception: the {pretty(a)} multiplied {pretty(terms[0])} "
                        f"but not {pretty(sympy.Add(*terms[1:]))}."),
            "targeted_question": (f"In {expr_text}, the {pretty(a)} multiplies the whole bracket. "
                                  f"What is {pretty(a)} × {pretty(terms[1])}?"),
        }
    sign_flip = a * terms[0] - a * sympy.Add(*terms[1:])
    if equivalent(ans, sign_flip):
        return {"code": "sign_error", "message": "Possible sign error in the second term.",
                "targeted_question": f"What sign does {pretty(a)} × {pretty(terms[1])} have?"}
    return None


def extract_forms(answer: str) -> list[tuple[str, sympy.Expr | None]]:
    parts = re.split(r"\s*(?:=|,|;|\band\b|\bor\b|\n)\s*", _clean(answer), flags=re.I)
    forms: list[tuple[str, sympy.Expr | None]] = []
    for part in parts:
        if not part.strip():
            continue
        runs = [r.strip() for r in _MATH_RUN.findall(part) if any(ch.isdigit() for ch in r) or "(" in r]
        runs = [r for r in runs if len(r) >= 2]
        candidate = max(runs, key=len) if runs else part.strip()
        forms.append((candidate, parse(candidate)))
    return forms


def grade_equivalent_forms(answer: str, target_text: str) -> GradeResult:
    """Transfer task: write the quantity in two equivalent forms (e.g. factored and expanded)."""
    target = parse(target_text)
    forms = [(t, e) for t, e in extract_forms(answer) if t]
    parsed = [(t, e) for t, e in forms if e is not None]
    why, limits = CriterionResult("why_relationships", "na"), CriterionResult("limits", "na")
    if target is None or not parsed:
        unsc = [CriterionResult(c, "unscored", rationale="Could not read the expressions.")
                for c in ("correctness", "essential_coverage", "example_application")]
        return GradeResult(unsc + [why, limits], "unscored", "limited",
                           "There is not enough reliable information to score this yet.", reason="ANSWER_UNPARSEABLE")
    good = [(t, e) for t, e in parsed if equivalent(e, target)]
    bad = [(t, e) for t, e in parsed if not equivalent(e, target)]
    q = lambda items: [{"sentence_id": "answer", "text": t} for t, _ in items]  # noqa: E731
    correctness = (CriterionResult("correctness", "demonstrated", q(good), rationale="Every expression is equivalent to the quantity.")
                   if not bad else CriterionResult("correctness", "absent", q(bad), rationale="At least one expression is not equivalent."))
    expanded = [g for g in good if is_expanded(g[0])]
    unexpanded = [g for g in good if not is_expanded(g[0])]
    distinct = {re.sub(r"\s+", "", t) for t, _ in good}
    covered = (["factored_form"] if unexpanded else []) + (["expanded_form"] if expanded else [])
    missing = [{"essential_id": e, "description": d, "status": "not demonstrated"} for e, d in
               (("factored_form", "A grouped (factored) form"), ("expanded_form", "An expanded form")) if e not in covered]
    if len(covered) == 2 and len(distinct) >= 2:
        coverage = CriterionResult("essential_coverage", "demonstrated", q(good), covered, [], "Two distinct equivalent forms.")
    elif covered:
        coverage = CriterionResult("essential_coverage", "partial", q(good), covered, missing, "One form given.")
    else:
        coverage = CriterionResult("essential_coverage", "absent", [], [], missing, "No equivalent form given.")
    application = (CriterionResult("example_application", "demonstrated", q(good[:1]), rationale="The situation is modeled correctly.")
                   if good else CriterionResult("example_application", "absent", [], rationale="The situation is not modeled correctly.",
                                                missing=[{"essential_id": "model", "description": "An expression for the total",
                                                          "status": "not demonstrated"}]))
    crits = [correctness, coverage, application, why, limits]
    statuses = [c.status for c in (correctness, coverage, application)]
    outcome = ("demonstrated" if all(s == "demonstrated" for s in statuses)
               else "not_demonstrated" if all(s == "absent" for s in statuses) else "partial")
    fb = {"demonstrated": "Both forms are equivalent and model the situation.",
          "partial": "Part of this is shown; see each criterion.",
          "not_demonstrated": "These expressions do not yet match the situation."}[outcome]
    return GradeResult(crits, outcome, "sufficient", fb)
