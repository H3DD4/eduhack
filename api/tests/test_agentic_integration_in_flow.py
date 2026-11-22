"""The Agentic Tutor pipeline inside the main flow: heading-based roadmaps, heading-aware chunks, HTML uploads,
answer-key verifier on placement questions, course style + likeness on summaries."""

from __future__ import annotations

from thinkfirst.modules.rag.ingestion import extract

FRENCH = """CHAPITRE 1 : DÉRIVATION
Définition du nombre dérivé
Le nombre dérivé de f en a est la limite du taux d'accroissement quand h tend vers 0.
Théorème des fonctions usuelles
La dérivée de x^n est n x^(n-1) pour tout entier n supérieur ou égal à 1.
CHAPITRE 2 : PRIMITIVES
Méthode de calcul d'une primitive
On reconnaît la forme u' u^n et on applique la formule correspondante pas à pas.
"""


def test_outline_scope_builds_a_roadmap_from_french_headings():
    cs = extract.outline_scope([FRENCH])
    assert [(c.key, c.unit_no) for c in cs] == [("1.1", 1), ("1.2", 1), ("2.1", 2)]
    assert cs[0].unit_title.startswith("CHAPITRE 1") and cs[0].title.startswith("Définition")
    assert cs[0].objective.startswith("Le nombre dérivé") and cs[1].prerequisites == ["1.1"]
    assert extract.heuristic_scope([FRENCH])[0] == []  # the numbered-heading parser alone finds nothing


def test_chunks_never_cross_a_chapter_heading_and_keep_exact_offsets():
    page = ("Intro text " * 20).strip() + "\nCHAPITRE 2 : PRIMITIVES\n" + ("Body text " * 20).strip()
    chunks = extract.chunk_pages([page], target=10_000)
    assert len(chunks) == 2 and chunks[1].text.startswith("CHAPITRE 2")
    assert all(page[c.start:c.end].strip() == c.text for c in chunks)


def test_french_course_without_numbering_gets_a_roadmap_offline(student):
    r = student.post("/api/subjects/start", data={"topic": "Analyse", "goal": "exam", "prior_knowledge": "none",
                                                  "rights_ack": "true", "paste_text": FRENCH})
    sid = r.json()["subject"]["id"]
    setup = student.get(f"/api/subjects/{sid}/setup").json()
    assert setup["proposal"]["basis"] == "extracted-outline"
    assert [c["key"] for c in setup["proposal"]["concepts"]] == ["1.1", "1.2", "2.1"]
    assert all(c["citations"][0]["page"] == 1 for c in setup["proposal"]["concepts"])


def test_html_upload_is_extracted(student):
    html = b"<html><body><h1>Unit 5: Optics</h1><h2>5.1 Refraction</h2><p>Light bends when it changes medium.</p></body></html>"
    r = student.post("/api/subjects/start", data={"topic": "Optics", "goal": "explore", "prior_knowledge": "none",
                                                  "rights_ack": "true"}, files=[("files", ("optics.html", html, "text/html"))])
    assert r.status_code == 200, r.text
    setup = student.get(f"/api/subjects/{r.json()['subject']['id']}/setup").json()
    assert setup["sources"][0]["status"] != "needs_attention" and setup["sources"][0]["page_count"] >= 1


def test_placement_answer_key_verifier():
    from thinkfirst.modules.diagnostic.placement import _key_ok

    good = {"question": "q", "options": [{"text": t, "misconception": m} for t, m in
                                         (("a", None), ("b", "x"), ("c", "y"), ("d", "z"))]}
    two_right = {"question": "q", "options": [{"text": t, "misconception": None} for t in "abcd"]}
    assert _key_ok(good) and not _key_ok(two_right)


def test_summary_course_style_and_likeness_gate(student, monkeypatch):
    from thinkfirst.core import db as dbmod
    from thinkfirst.modules.tutor import summary
    from thinkfirst.modules.tutor.llm import service as llm
    from thinkfirst.modules.tutor.models import CourseSummary

    r = student.post("/api/subjects/start", data={"topic": "Analyse", "goal": "exam", "prior_knowledge": "none",
                                                  "rights_ack": "true", "paste_text": FRENCH})
    sid = r.json()["subject"]["id"]
    setup = student.get(f"/api/subjects/{sid}/setup").json()
    student.post(f"/api/subjects/{sid}/scope/confirm", json={"graph_revision_id": setup["proposal"]["id"], "edits": []})
    with dbmod.session_factory()() as db:
        owner = setup["subject"]["id"] and db.get(CourseSummary, "x")  # noqa: F841
        from thinkfirst.platform.workspaces.models import Subject

        subj = db.get(Subject, sid)
        sm = CourseSummary(owner_id=subj.owner_id, subject_id=sid, level="beginner", mode="course")
        style, profile = summary._course_style(db, sm)
        assert style.get("vocabulary") and profile is not None
        off = {"blocks": [{"type": "paragraph", "text": "Unrelated words about gardening tomatoes", "pages": [1]}],
               "key_terms": [], "common_mistakes": [], "check_questions": []}

        def better(*a, **k):
            return llm.GatewayResult(output={"title": "t", "blocks": [{"type": "definition", "text": FRENCH, "pages": [1]}],
                                             "key_terms": [], "common_mistakes": [], "check_questions": [], "covered_pages": [1]},
                                     provider="groq", model="m", status="ok", simulated=False, label="AI")
        monkeypatch.setattr(summary.llm, "run", better)

        class Sec:
            title = "Dérivation"
        out = summary._likeness_gate(db, sm, Sec(), off, profile, [{"page": 1, "text": FRENCH}], {}, "f", style)
        assert out["likeness"] >= 0.5 and "Le nombre dérivé" in out["blocks"][0]["text"]  # rewritten, closer to the course
