"""Language-light text helpers shared by retrieval, fingerprinting, likeness and the offline mock LLM."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

STOP = {
    "fr": set("""a à afin ai aie ainsi alors au aucun aussi autre aux avec avoir bon car ce ceci cela celle celles
        celui ces cet cette chaque ci comme comment dans de des du donc dont elle elles en encore entre est et étaient
        été être eu fait faire fois ici il ils je la le les leur leurs lors lui ma mais me même mes moi mon ne ni nos
        notre nous on ont ou où par parce pas peu peut plus pour pourquoi quand que quel quelle quelles quels qui sa
        sans se ses si sinon son sont sous soit sur ta te tes toi ton tous tout toute toutes très tu un une vos votre
        vous y d l qu n s c j m t""".split()),
    "en": set("""a about above after again all also am an and any are as at be because been before being below
        between both but by can could did do does doing down during each few for from further had has have having he
        her here hers him his how i if in into is it its itself just me more most my no nor not of off on once only or
        other our out over own same she should so some such than that the their them then there these they this those
        through to too under until up very was we were what when where which while who whom why will with you your
        let given using use""".split()),
    "de": set("""der die das und oder ein eine einer eines einem einen ist sind war waren mit für auf aus bei bis
        durch gegen ohne um von zu zum zur im in am an als auch nicht nur noch wie wir ihr sie er es""".split()),
    "es": set("""el la los las un una unos unas y o de del al en con por para es son fue como que se su sus lo le
        les no sí más muy""".split()),
}
ALL_STOP = set().union(*STOP.values())

_word = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ؀-ۿ][A-Za-zÀ-ÖØ-öø-ÿ؀-ۿ0-9'’_-]*")
_sent = re.compile(r"(?<=[.!?;:])\s+(?=[A-ZÀ-Ö0-9؀-ۿ$(«\"])")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str) -> str:
    return strip_accents(s.lower())


def stem(w: str) -> str:
    """Very light suffix stripping that works acceptably for FR/EN/ES (plural, a few derivations)."""
    for suf in ("ements", "ement", "ations", "ation", "ités", "ité", "ings", "ing", "ies", "es", "s", "e"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def words(text: str) -> list[str]:
    return [m.group(0).strip("'’-_") for m in _word.finditer(text)]


def tokens(text: str, *, stop: bool = True, stemmed: bool = True) -> list[str]:
    out = []
    for w in words(text):
        n = norm(w).replace("’", "'")
        if "'" in n:  # l'intégrale -> intégrale
            n = n.split("'")[-1]
        if len(n) < 2 or (stop and n in ALL_STOP):
            continue
        out.append(stem(n) if stemmed else n)
    return out


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return [s.strip() for s in _sent.split(text) if len(s.strip()) > 2]


def detect_language(text: str) -> str:
    sample = [norm(w) for w in words(text[:20000])]
    if not sample:
        return "fr"
    arabic = sum(1 for w in sample if re.match(r"[؀-ۿ]", w))
    if arabic > len(sample) * 0.3:
        return "ar"
    scores = {lang: sum(1 for w in sample if w in {strip_accents(x) for x in sw}) for lang, sw in STOP.items()}
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "fr"


def slugify(s: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")
    return s[:max_len].strip("-") or "item"


def cosine(a: dict[str, float] | Counter, b: dict[str, float] | Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def tfidf_keywords(docs: Iterable[str], top: int = 40, min_df: int = 1) -> list[tuple[str, float]]:
    """Top terms over a corpus. Terms keep their most frequent surface form for display."""
    docs = list(docs)
    df: Counter = Counter()
    tf: Counter = Counter()
    surface: dict[str, Counter] = {}
    for d in docs:
        toks = []
        for w in words(d):
            n = norm(w).split("'")[-1]
            if len(n) < 3 or n in ALL_STOP or n.isdigit():
                continue
            s = stem(n)
            toks.append(s)
            surface.setdefault(s, Counter())[w.lower()] += 1
        tf.update(toks)
        df.update(set(toks))
    n = max(1, len(docs))
    scored = []
    for t, f in tf.items():
        if df[t] < min_df:
            continue
        idf = math.log((1 + n) / (1 + df[t])) + 1
        scored.append((surface[t].most_common(1)[0][0], (1 + math.log(f)) * idf))
    scored.sort(key=lambda x: -x[1])
    return scored[:top]


def overlap_ratio(a: str, b: str) -> float:
    """Share of content tokens of `a` that also appear in `b` (citation support check)."""
    ta = set(tokens(a))
    if not ta:
        return 0.0
    tb = set(tokens(b))
    return len(ta & tb) / len(ta)


def numbers_in(text: str) -> list[str]:
    return re.findall(r"-?\d+(?:[.,]\d+)?", text)
