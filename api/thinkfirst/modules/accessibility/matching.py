from __future__ import annotations

import re
import unicodedata


def normalize_answer(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c) and c != "\u0640")
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = re.sub(r"[ىئ]", "ي", text)
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def likely_spelling_variation(answer: str, expected: str) -> bool:
    actual, target = normalize_answer(answer), normalize_answer(expected)
    if not actual or not target or actual == target or len(actual) < 4 or len(target) < 4:
        return False
    if " " in actual or " " in target:
        return False
    distance = _edit_distance(actual, target)
    return distance <= 1 and distance / max(len(actual), len(target)) <= 0.2
