"""MockLLM: deterministic, offline stand-in for every task.

It is NOT an AI: it builds simple but real material from the CONTEXT chunks (cloze QCM, true/false quiz,
definition cards, extractive summaries) so the whole pipeline, the UI and the tests work without keys.
The API reports `simulated: true` whenever this adapter is active.
"""

from __future__ import annotations

import hashlib
import random
import re
from typing import Any

from ..textutil import norm, overlap_ratio, sentences, slugify, tfidf_keywords, tokens

L = {
    "fr": {"complete": "Complétez : ", "what": "Qu'est-ce que {t} ?", "true": "vrai", "false": "faux",
           "tf": "Vrai ou faux : ", "define": "Définir {t} et donner un exemple tiré du cours.",
           "explain": "Expliquer {t} avec vos propres mots.", "intro": "Dans cette page, vous allez découvrir {t}.",
           "example": "Exemple", "try": "À vous de jouer", "mistakes": "Erreurs fréquentes",
           "summary": "À retenir", "confuse": "Ne pas confondre « {a} » et « {b} ».",
           "q1": "Que demande exactement la question ? Quelles notions du cours sont en jeu ?",
           "q2": "Relisez la partie « {s} » du cours : {q}",
           "q3": "Voici un exemple proche : {q}", "q4": "Solution : {a}",
           "noanswer": "Le cours ne contient pas cette information. Cherchez « {t} » dans une source fiable.",
           "guide": "Avant de donner la réponse : qu'avez-vous déjà essayé ? Quelle définition du cours s'applique ?",
           "fb_ok": "Bonne réponse.", "fb_part": "Une partie est juste ; revoyez « {s} ».",
           "fb_no": "Pas encore. Revenez à la définition de « {s} ».", "exercise": "Exercice"},
    "en": {"complete": "Fill in the blank: ", "what": "What is {t}?", "true": "true", "false": "false",
           "tf": "True or false: ", "define": "Define {t} and give an example from the course.",
           "explain": "Explain {t} in your own words.", "intro": "On this page you will learn {t}.",
           "example": "Example", "try": "Try it yourself", "mistakes": "Common mistakes", "summary": "Remember",
           "confuse": "Do not confuse “{a}” with “{b}”.",
           "q1": "What exactly does the question ask? Which course ideas are involved?",
           "q2": "Re-read the “{s}” part of the course: {q}", "q3": "Here is a similar example: {q}",
           "q4": "Solution: {a}", "noanswer": "The course does not contain this. Look up “{t}” in a reliable source.",
           "guide": "Before the answer: what have you tried? Which course definition applies here?",
           "fb_ok": "Correct.", "fb_part": "Part of it is right; review “{s}”.",
           "fb_no": "Not yet. Go back to the definition of “{s}”.", "exercise": "Exercise"},
}


def _lang(v: dict[str, Any]) -> dict[str, str]:
    return L.get(v.get("language", "fr"), L["en"])


def _rng(*parts: Any) -> random.Random:
    return random.Random(int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16))


def _cite(chunk: dict[str, Any], quote: str = "") -> dict[str, Any]:
    return {"chunk_id": chunk["id"], "quote": (quote or chunk["text"])[:160]}


def _concept_terms(c: dict[str, Any]) -> list[str]:
    terms = [c.get("title", "")] + list(c.get("keywords") or [])
    return [t for t in terms if t]


def _best_sentences(concept: dict[str, Any], ctx: list[dict[str, Any]], n: int = 3) -> list[tuple[str, dict]]:
    terms = _concept_terms(concept)
    qtoks = set(tokens(" ".join(terms)))
    scored = []
    for ch in ctx:
        head = (ch.get("section") or "").split(" › ")[-1]
        for s in sentences(ch["text"]):
            if head and s.startswith(head) and len(s) > len(head) + 20:
                s = s[len(head):].strip(" :.-")
            if len(s) < 25 or len(s) > 400:
                continue
            st = set(tokens(s))
            score = len(qtoks & st) + (0.5 if any(norm(t) in norm(s) for t in terms) else 0)
            if score > 0:
                scored.append((score, s, ch))
    scored.sort(key=lambda x: -x[0])
    seen, out = set(), []
    for _, s, ch in scored:
        if s not in seen:
            seen.add(s)
            out.append((s, ch))
        if len(out) >= n:
            break
    if not out and ctx:
        out = [(sentences(ctx[0]["text"])[0] if sentences(ctx[0]["text"]) else ctx[0]["text"][:200], ctx[0])]
    return out


def _blank_target(sentence: str, concept: dict[str, Any], vocab: list[str]) -> str | None:
    cands = sorted(_concept_terms(concept), key=len, reverse=True) + vocab
    for t in cands:
        if len(t) >= 3 and re.search(rf"\b{re.escape(t)}\b", sentence, re.I):
            return t
    ws = [w for w in re.findall(r"[A-Za-zÀ-ÿ]{6,}", sentence)]
    return max(ws, key=len) if ws else None


class MockLLM:
    def run(self, task: str, v: dict[str, Any]) -> dict[str, Any]:
        fn = getattr(self, f"t_{task}", None)
        if fn is None:
            raise KeyError(f"mock has no task {task}")
        return fn(v)

    # ------------------------------------------------------------------ understanding
    def t_classify_document(self, v: dict[str, Any]) -> dict[str, Any]:
        text = norm(v.get("excerpt", "") + " " + v.get("filename", ""))
        if re.search(r"\b(examen|exam|devoir surveille|ds|bac|partiel|duree\s*:|baremes?)\b", text) or \
                re.search(r"\d+\s*(pts|points)\b", text):
            t = "past_exam"
        elif re.search(r"\b(corrige|correction|solutions?)\b", text):
            t = "solutions"
        elif re.search(r"\b(td|tp|exercices?|serie|worksheet|exercises?)\b", text):
            t = "exercises"
        elif v.get("filename", "").lower().endswith((".ppt", ".pptx")):
            t = "slides"
        else:
            t = "course"
        title = re.sub(r"[_-]+", " ", re.sub(r"\.[a-z0-9]+$", "", v.get("filename", "Document"))).strip()
        return {"doc_type": t, "title": title[:80] or "Document", "language": v.get("language", "fr")}

    def t_extract_concepts(self, v: dict[str, Any]) -> dict[str, Any]:
        outline: list[dict[str, Any]] = v.get("outline") or []
        excerpts: list[str] = v.get("excerpts") or []
        concepts: list[dict[str, Any]] = []
        chapter = v.get("subject") or "Cours"
        prev = None
        for h in outline:
            title = h["title"].strip(" :.-")
            if not title or len(title) > 90:
                continue
            if h.get("level", 2) <= 1:
                chapter = title
                continue
            key = slugify(title)
            if any(c["key"] == key for c in concepts):
                continue
            body = " ".join(e for e in excerpts if norm(title)[:20] in norm(e))[:1500]
            kws = [k for k, _ in tfidf_keywords([body], top=5)] if body else []
            concepts.append({"key": key, "title": title, "chapter": chapter, "summary": (sentences(body) or [""])[0][:200],
                             "keywords": kws, "prerequisites": [prev] if prev else []})
            prev = key
            if len(concepts) >= 40:
                break
        if len(concepts) < 3:  # no usable headings: cluster on top keywords
            kws = tfidf_keywords(excerpts, top=12)
            prev = None
            concepts = []
            for k, _ in kws[:10]:
                key = slugify(k)
                concepts.append({"key": key, "title": k.capitalize(), "chapter": chapter, "summary": "",
                                 "keywords": [k], "prerequisites": [prev] if prev else []})
                prev = key
        return {"concepts": concepts}

    def t_extract_blueprint(self, v: dict[str, Any]) -> dict[str, Any]:
        text = v.get("exam_text", "")
        dur = None
        m = re.search(r"dur[ée]e\s*:?\s*(\d+)\s*h\s*(\d+)?", text, re.I) or re.search(r"(\d+)\s*h(?:eures?|ours?)?\b", text)
        if m:
            dur = int(m.group(1)) * 60 + (int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 0)
        m2 = re.search(r"(\d+)\s*(?:min|minutes)\b", text, re.I)
        if not dur and m2:
            dur = int(m2.group(1))
        parts = []
        heads = list(re.finditer(r"(?im)^\s*((?:exercice|exercise|partie|part|problème|problem|question)\s*[IVX\d]+[^\n]{0,60})", text))
        concepts = v.get("concepts") or []
        for i, h in enumerate(heads):
            seg = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
            pts = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:pts|points?)", h.group(1) + seg[:200], re.I)
            qtypes = []
            nseg = norm(seg)
            if re.search(r"\b(qcm|cochez|entourez|choisir la bonne)\b", nseg):
                qtypes.append("qcm")
            if re.search(r"\b(vrai ou faux|true or false)\b", nseg):
                qtypes.append("true_false")
            if re.search(r"\b(montrer|demontrer|prove|show that)\b", nseg):
                qtypes.append("proof")
            if re.search(r"\b(calculer|determiner|compute|calculate|resoudre|solve)\b", nseg):
                qtypes.append("calculation")
            if not qtypes:
                qtypes.append("short")
            ckeys = [c["key"] for c in concepts if any(norm(k) in nseg for k in _concept_terms(c) if len(k) > 3)][:6]
            count = max(1, len(re.findall(r"(?m)^\s*(?:\d+[).]|[a-z][).])", seg)))
            parts.append({"title": h.group(1).strip()[:60], "points": float(pts.group(1).replace(",", ".")) if pts else 0.0,
                          "question_types": qtypes, "concept_keys": ckeys, "count": count})
        total = sum(p["points"] for p in parts) or None
        return {"duration_min": dur, "total_points": total, "parts": parts}

    def t_research_queries(self, v: dict[str, Any]) -> dict[str, Any]:
        word = "cours" if v.get("language", "fr") == "fr" else "explained"
        subj = v.get("subject", "")
        return {"queries": [{"concept_key": g["key"], "query": f"{g['title']} {subj} {word}".strip()}
                            for g in v.get("gaps", [])]}

    # ------------------------------------------------------------------ generation
    def t_generate_resume(self, v: dict[str, Any]) -> dict[str, Any]:
        tr, ctx = _lang(v), v.get("context", [])
        sections = []
        concepts = v.get("concepts", [])
        for c in concepts:
            best = _best_sentences(c, ctx, 3)
            formulas = [s for s, _ in best if "=" in s or "$" in s][:2]
            bullets = [s for s, _ in best if s not in formulas][:3]
            pit = []
            others = [o for o in concepts if o["key"] != c["key"]]
            if others:
                pit.append(tr["confuse"].format(a=c["title"], b=others[0]["title"]))
            sections.append({"heading": c["title"], "bullets": bullets, "formulas": formulas, "pitfalls": pit,
                             "citations": [_cite(ch, s) for s, ch in best[:2]]})
        return {"chapter": v.get("chapter", ""), "sections": sections}

    def t_generate_fiches(self, v: dict[str, Any]) -> dict[str, Any]:
        tr, ctx = _lang(v), v.get("context", [])
        out = []
        for c in v.get("concepts", []):
            best = _best_sentences(c, ctx, 2)
            if not best:
                continue
            s, ch = best[0]
            out.append({"concept_key": c["key"], "fiche_type": "formula" if "=" in s else "definition",
                        "front": tr["what"].format(t=c["title"]), "back": s, "citations": [_cite(ch, s)]})
            if len(best) > 1:
                s2, ch2 = best[1]
                out.append({"concept_key": c["key"], "fiche_type": "example" if re.search(r"\d", s2) else "method",
                            "front": c["title"] + " — " + (tr["example"] if re.search(r"\d", s2) else "?"),
                            "back": s2, "citations": [_cite(ch2, s2)]})
        return {"fiches": out[: max(1, int(v.get("count", 12)))]}

    def t_generate_qcm(self, v: dict[str, Any]) -> dict[str, Any]:
        tr, ctx = _lang(v), v.get("context", [])
        concepts = v.get("concepts", [])
        vocab = [t for t in (v.get("style", {}).get("vocabulary") or [])][:60]
        pool = sorted({t for c in concepts for t in _concept_terms(c) if 3 <= len(t) <= 40} | set(vocab[:30]))
        items = []
        n = max(1, int(v.get("count", 6)))
        for i, c in enumerate(concepts * 3):
            if len(items) >= n:
                break
            best = _best_sentences(c, ctx, 3)
            if not best:
                continue
            off = int(float(v.get("difficulty", 1100)) // 200)
            s, ch = best[(i // max(1, len(concepts)) + off) % len(best)]
            target = _blank_target(s, c, vocab)
            if not target:
                continue
            stem = re.sub(rf"\b{re.escape(target)}\b", "_____", s, count=1, flags=re.I)
            if stem == s or any(it["stem"].endswith(stem) for it in items):
                continue
            rng = _rng(c["key"], s)
            distract = [t for t in pool if norm(t) != norm(target) and norm(t) not in norm(s)]
            rng.shuffle(distract)
            opts = [{"text": target, "correct": True, "why": ""}] + [
                {"text": d, "correct": False, "why": f"« {d} » ≠ « {target} »"} for d in distract[:3]]
            if len(opts) < 3:
                continue
            rng.shuffle(opts)
            items.append({"concept_key": c["key"], "stem": tr["complete"] + stem, "multiple": False, "options": opts,
                          "explanation": s, "difficulty": float(v.get("difficulty", 1100)), "citations": [_cite(ch, s)]})
        return {"items": items}

    def t_generate_quiz(self, v: dict[str, Any]) -> dict[str, Any]:
        tr, ctx = _lang(v), v.get("context", [])
        concepts = v.get("concepts", [])
        items = []
        n = max(1, int(v.get("count", 6)))
        for i, c in enumerate(concepts * 2):
            if len(items) >= n:
                break
            best = _best_sentences(c, ctx, 2)
            if not best:
                continue
            s, ch = best[0 if i < len(concepts) else -1]
            truth = (i % 2 == 0)
            stmt = s
            if not truth:
                others = [o for o in concepts if o["key"] != c["key"] and re.search(rf"\b{re.escape(c['title'])}\b", s, re.I)]
                if others:
                    stmt = re.sub(rf"\b{re.escape(c['title'])}\b", others[0]["title"], s, count=1, flags=re.I)
                else:
                    truth = True
            if any(it["question"].endswith(stmt) for it in items):
                continue
            items.append({"concept_key": c["key"], "question": tr["tf"] + stmt, "answer": "true" if truth else "false",
                          "answer_type": "true_false", "accept": [tr["true"] if truth else tr["false"]],
                          "explanation": s, "difficulty": float(v.get("difficulty", 1000)), "citations": [_cite(ch, s)]})
        return {"items": items}

    def t_generate_exercises(self, v: dict[str, Any]) -> dict[str, Any]:
        tr, ctx = _lang(v), v.get("context", [])
        style = v.get("style", {})
        verbs = list((style.get("verbs") or {}).keys())
        out = []
        for c in v.get("concepts", [])[: max(1, int(v.get("count", 3)))]:
            best = _best_sentences(c, ctx, 2)
            if not best:
                continue
            s, ch = best[0]
            verb = verbs[0].capitalize() if verbs else None
            p1 = f"{verb} {c['title'].lower()}." if verb else tr["define"].format(t=c["title"])
            parts = [{"label": "1)", "prompt": p1, "answer": s, "answer_type": "text", "points": 2,
                      "solution_steps": [s]},
                     {"label": "2)", "prompt": tr["explain"].format(t=c["title"]),
                      "answer": best[-1][0], "answer_type": "text", "points": 2, "solution_steps": [best[-1][0]]}]
            out.append({"concept_keys": [c["key"]], "title": f"{tr['exercise']} — {c['title']}",
                        "statement": s[:300], "difficulty": float(v.get("difficulty", 1150)),
                        "parts": parts, "citations": [_cite(ch, s)]})
        return {"exercises": out}

    def t_generate_lesson(self, v: dict[str, Any]) -> dict[str, Any]:
        tr, ctx = _lang(v), v.get("context", [])
        page = v.get("page", {})
        concepts = v.get("concepts", []) or [{"key": slugify(page.get("title", "x")), "title": page.get("title", "")}]
        sections = [{"type": "intro", "title": page.get("title", ""), "body": tr["intro"].format(
            t=", ".join(c["title"] for c in concepts))}]
        try_items = []
        for c in concepts:
            best = _best_sentences(c, ctx, 4)
            if not best:
                continue
            expl = [s for s, _ in best if not re.search(r"\b(exemple|example|e\.g\.)\b", s, re.I)][:3]
            ex = [s for s, _ in best if re.search(r"\b(exemple|example|par exemple)\b|\d", s, re.I)][:1]
            sections.append({"type": "explain", "title": c["title"], "body": " ".join(expl),
                             "citations": [_cite(ch, s) for s, ch in best[:2]]})
            if ex:
                sections.append({"type": "example", "title": tr["example"], "body": ex[0]})
            q = self.t_generate_qcm({**v, "concepts": [c], "count": 1})["items"]
            try_items += q
        sections.append({"type": "try", "title": tr["try"], "body": "", "items": try_items[:3]})
        if len(concepts) > 1:
            sections.append({"type": "mistakes", "title": tr["mistakes"],
                             "body": "- " + tr["confuse"].format(a=concepts[0]["title"], b=concepts[1]["title"])})
        sections.append({"type": "summary", "title": tr["summary"],
                         "body": "\n".join(f"- {c['title']}" for c in concepts)})
        return {"title": page.get("title", ""), "sections": sections}

    # ------------------------------------------------------------------ checking and teaching
    def t_critic(self, v: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "problems": [], "fixed_answer": None}

    def t_grade_open(self, v: dict[str, Any]) -> dict[str, Any]:
        tr = _lang(v)
        exp, ans = v.get("expected", ""), v.get("answer", "")
        score = round(min(1.0, overlap_ratio(exp, ans) * 1.25), 2) if ans.strip() else 0.0
        s = v.get("concept_title", "")
        fb = tr["fb_ok"] if score >= 0.7 else tr["fb_part"].format(s=s) if score >= 0.35 else tr["fb_no"].format(s=s)
        return {"score": score, "correct": score >= 0.7, "feedback": fb,
                "error_tags": [] if score >= 0.7 else ["incomplete-answer"]}

    def t_tutor_help(self, v: dict[str, Any]) -> dict[str, Any]:
        tr = _lang(v)
        level = int(v.get("level", 1))
        ctx = v.get("context", [])
        item = v.get("item", {})
        if level <= 1 or not ctx:
            return {"message": tr["q1"], "citations": []}
        ch = ctx[0]
        sent = (sentences(ch["text"]) or [ch["text"][:200]])[0]
        if level == 2:
            return {"message": tr["q2"].format(s=ch.get("section") or "…", q=sent), "citations": [_cite(ch, sent)]}
        if level == 3:
            alt = sentences(ctx[-1]["text"])
            return {"message": tr["q3"].format(q=(alt[-1] if alt else sent)), "citations": [_cite(ctx[-1])]}
        answer = item.get("answer") or next((o["text"] for o in item.get("options", []) if o.get("correct")), "")
        return {"message": tr["q4"].format(a=f"{answer}. {item.get('explanation', '')}".strip()),
                "citations": [_cite(ch, sent)]}

    def t_answer_question(self, v: dict[str, Any]) -> dict[str, Any]:
        tr = _lang(v)
        q, ctx = v.get("question", ""), v.get("context", [])
        if v.get("mode") == "practice" and v.get("active_item"):
            return {"answer": tr["guide"], "citations": [], "grounded": True}
        qt = set(tokens(q))
        scored = []
        for ch in ctx:
            for s in sentences(ch["text"]):
                ov = len(qt & set(tokens(s)))
                if ov:
                    scored.append((ov, s, ch))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return {"answer": tr["noanswer"].format(t=q[:60]), "citations": [], "grounded": False}
        top = scored[:2]
        return {"answer": " ".join(s for _, s, _ in top), "citations": [_cite(ch, s) for _, s, ch in top],
                "grounded": True}
