"""Rubric templates. Five criteria (override §3.3). Essentials are predeclared before answering.

The distributive-property rubric is demo content for the MATH 101 fixture: labelled
"Demo rubric — not domain-approved". Patterns only drive the *demo* assessor; real providers get
the essential descriptions.
"""

from __future__ import annotations

CRITERIA = ("correctness", "essential_coverage", "why_relationships", "example_application", "limits")
CRITERION_LABELS = {
    "correctness": "Correctness",
    "essential_coverage": "Essential coverage",
    "why_relationships": "Why / relationships",
    "example_application": "Example / application",
    "limits": "Limits",
}

DISTRIBUTIVE = {
    "template": "distributive-v1",
    "match": ("distribut",),
    "explain_prompt": ("Explain why 2(x + 3) equals 2x + 6, and say when 'multiply every term in the bracket' "
                       "does not apply."),
    "criteria": [
        {"criterion": "correctness", "applicable": True,
         "essentials": [{"id": "each_term", "description": "The factor multiplies every term inside the brackets",
                         "patterns": [r"(every|each|both|all)\b.{0,40}\b(term|thing|part|number)s?\b.{0,30}(inside|bracket|parenthes)",
                                      r"multipl\w*.{0,40}\b(both|each|every|all)\b",
                                      r"(both|each|every)\b.{0,25}\b(term|part)s?\b"]}],
         "contradictions": [r"only (multiply|multiplies)? ?(the )?first", r"just (the )?x\b(?!.{0,15}and)"]},
        {"criterion": "essential_coverage", "applicable": True,
         "essentials": [
             {"id": "each_term", "description": "Every term inside the brackets is multiplied",
              "patterns": [r"(every|each|both|all)\b.{0,40}\b(term|part|number)s?", r"multipl\w*.{0,40}\b(both|each|every)\b"]},
             {"id": "result", "description": "2(x + 3) = 2x + 6",
              "patterns": [r"2\s*x\s*\+\s*6"]},
             {"id": "general_rule", "description": "General rule a(b + c) = ab + ac",
              "patterns": [r"a\s*\(\s*b\s*\+\s*c\s*\)", r"\bab\s*\+\s*ac\b", r"\bany (number|value)", r"\bin general\b", r"\balways\b"]},
         ]},
        {"criterion": "why_relationships", "applicable": True,
         "essentials": [{"id": "groups", "description": "Why: a(b + c) means a groups of (b + c) (repeated addition)",
                         "patterns": [r"\bgroups?\b", r"repeated addition", r"(x\s*\+\s*3)\s*\)?\s*\+\s*\(?\s*x\s*\+\s*3",
                                      r"\btwice\b", r"two (lots|copies|times)", r"\barea\b"]}]},
        {"criterion": "example_application", "applicable": True,
         "essentials": [{"id": "own_example", "description": "Applies the rule to an example of their own",
                         "patterns": [r"(for example|e\.g\.|for instance|like|such as)\b.{0,40}\d\s*\(",
                                      r"\b(?!2\s*\(\s*x\s*\+\s*3)\d+\s*\(\s*[a-z]\s*[+\-−]\s*\d+\s*\)\s*(=|is|gives|equals|becomes)"]}]},
        {"criterion": "limits", "applicable": True,
         "essentials": [{"id": "not_products", "description": "Distribution works over + and −, not over a product inside the brackets",
                         "patterns": [r"\bnot\b.{0,40}\b(product|multipl\w*|times)\b", r"(doesn't|does not|won't|can't) (work|apply)",
                                      r"only (works|applies)\b", r"\(\s*x\s*[·*×]?\s*3\s*\)", r"\bxy\b"]}]},
    ],
    "followup_bank": {
        "limits": {"id": "fu-limits-1", "question": "Does 2(x · 3) equal 2x · 6? Explain why or why not."},
        "why_relationships": {"id": "fu-why-1",
                              "question": "Why does 2(x + 3) give the same value as 2x + 6 for every x? Use the idea of groups."},
        "example_application": {"id": "fu-example-1",
                                "question": "Give your own example of distributing a number over a bracket, and expand it."},
        "essential_coverage": {"id": "fu-coverage-1",
                               "question": "What happens to each term inside the brackets when you expand 5(a − 1)?"},
        "correctness": {"id": "fu-correct-1", "question": "Expand 4(y + 2) and say what the 4 does to each term."},
    },
}


def generic_template(title: str) -> dict:
    return {
        "template": "generic-v1",
        "explain_prompt": (f"Explain {title} in your own words: what it is, why it works, one example, "
                           "and when it does not apply."),
        "criteria": [{"criterion": c, "applicable": True, "essentials": []} for c in CRITERIA],
        "followup_bank": {"why_relationships": {"id": "fu-generic-why", "question": f"Why does {title} work? Name one relationship it depends on."}},
    }


def template_for(title: str) -> dict:
    t = title.lower()
    if any(m in t for m in DISTRIBUTIVE["match"]):
        return DISTRIBUTIVE
    return generic_template(title)
