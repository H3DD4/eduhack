"""Deterministic, tool-backed task generation (labeled ai-generated). Solutions are computed with SymPy.

Help ladder (override §3.1): clarify -> strategy cue -> sub-step -> different worked example ->
confirmed "End this attempt and view worked solution".
"""

from __future__ import annotations

import sympy

from thinkfirst.modules.assessment.mathcheck import equivalent, parse, pretty, split_product

LADDER = ["clarify", "strategy", "substep", "worked_example", "reveal"]
LADDER_LABELS = {
    "clarify": "Clarify the task",
    "strategy": "Strategy cue",
    "substep": "First sub-step",
    "worked_example": "A different worked example",
    "reveal": "Worked solution (ends this attempt)",
}


def expand_hints(expr_text: str) -> tuple[list[str], dict]:
    sp = split_product(expr_text)
    target = parse(expr_text)
    if sp is None or target is None:
        return ([f"“{expr_text}”: rewrite it without brackets.",
                 "Multiply what is outside the brackets by each term inside.",
                 "Work one term at a time.", "Compare with the example in your course.",
                 "No automatic worked solution is available for this item."], {})
    a, terms = sp.factor, sp.terms
    first = a * terms[0]
    alt_a = 4 if a != 4 else 5
    v = sympy.Symbol("y")
    example = alt_a * (v - 2)
    hints = [
        f"“Expand” means rewrite {expr_text} without brackets, as a sum of separate terms. You are not solving for x.",
        f"The factor outside the brackets, {pretty(a)}, multiplies every term inside — there are {len(terms)} terms inside.",
        f"First term: {pretty(a)} × {pretty(terms[0])} = {pretty(first)}. Now do the same for the next term: {pretty(a)} × {pretty(terms[1])} = ?",
        f"Worked example with different numbers: {alt_a}(y − 2) = {alt_a}·y − {alt_a}·2 = {pretty(sympy.expand(example))}.",
        f"{' + '.join(f'{pretty(a)}·{pretty(t)}' for t in terms)} = {pretty(sympy.expand(target))}",
    ]
    return hints, {"expanded": pretty(sympy.expand(target)), "steps": hints[4]}


EXPLAIN_HINTS = [
    "Say in your own words what the rule does, why it works, one example, and one case where it does not apply. Short is fine.",
    "Strategy: picture 2(x + 3) as two groups of (x + 3). What do the two groups add up to?",
    "Next step: reread the cited course section, then explain without copying it.",
]

VARIANTS = [(3, 5), (4, 2), (5, 1), (6, 3), (7, 2)]


def expand_variant(exclude: list[str]) -> str | None:
    for a, b in VARIANTS:
        expr = f"{a}(y + {b})"
        e = parse(expr)
        if e is not None and not any((x := parse(ex)) is not None and equivalent(e, x) for ex in exclude):
            return expr
    return None


TRANSFER_CONTEXTS = [
    ("pens", 3, 4, "You buy {a} packs of (x + {b}) pens. Write the total number of pens in two equivalent forms."),
    ("tiles", 5, 2, "A wall has {a} rows. Each row has x blue tiles and {b} white tiles. Write the total number of tiles in two equivalent forms."),
    ("tickets", 4, 3, "{a} friends each buy x cinema tickets and {b} bus tickets. Write the total number of tickets in two equivalent forms."),
]


def transfer_task(exclude_exprs: list[str]) -> dict | None:
    """Unfamiliar no-help task: new expression AND new context. Validated for novelty before use."""
    for family, a, b, tmpl in TRANSFER_CONTEXTS:
        target = f"{a}(x + {b})"
        te = parse(target)
        if te is None:
            continue
        clash = [ex for ex in exclude_exprs if (x := parse(ex)) is not None and equivalent(te, x)]
        if clash:
            continue
        return {
            "prompt": tmpl.format(a=a, b=b),
            "target": target,
            "family": f"distributive-context-{family}",
            "solution": {"forms": [target, pretty(sympy.expand(te))]},
            "novelty": {"different_expression": True, "different_context": True,
                        "excluded_expressions": exclude_exprs, "validated_by": "symbolic non-equivalence + new context"},
        }
    return None
