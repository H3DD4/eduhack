"""Whole textbooks (table of contents), several files, retries, malformed AI answers, long summaries."""

from __future__ import annotations

from thinkfirst.core import jobs
from thinkfirst.modules.rag.ingestion import extract
from thinkfirst.modules.tutor.llm import service as llm

TITLES = ["Fundamentals", "Types and Variables", "Functions", "Streams", "Operators", "Control Flow", "Classes", "Templates"]


def _book(n_pages: int = 100) -> list[str]:
    toc = "\n".join(f"Chapter {i} {t} {1 + (i - 1) * 10}\nBasics of {t} {2 + (i - 1) * 10}\nExercises {8 + (i - 1) * 10}"
                    for i, t in enumerate(TITLES, 1))
    pages = ["Preface", toc] + [f"Running text. 12.34561 will be rounded\n2.5 raised to the power 3\npage body {i} with enough words "
                                "to look like a paragraph of a book." for i in range(n_pages)]
    for i, t in enumerate(TITLES):  # printed page 1 is PDF page 5 (offset 4)
        pages[4 + i * 10] = f"{i + 1}\n{t}\nThis chapter explains {t} with several examples and exercises."
    return pages


def test_table_of_contents_becomes_the_roadmap_with_real_pdf_pages():
    cs = extract.toc_scope(_book())
    assert [c.title for c in cs] == TITLES
    assert [c.page for c in cs] == [5 + i * 10 for i in range(8)] and not cs[0].uncertain
    assert [c.key for c in cs][:8] == ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "2.1", "2.2"]
    assert cs[6].prerequisites == ["1.6"] and "Basics of Classes" in cs[6].objective and "Exercises" not in cs[6].objective


def test_decimals_in_running_text_are_never_concepts():
    assert extract.heuristic_scope(_book())[0] == []


def test_second_file_with_the_same_numbers_is_kept(student):
    a = b"Unit 1: Waves\n1.1 Wavelength\nObjective: a\n1.2 Frequency\nObjective: b\n"
    b = b"Unit 1: Optics\n1.1 Refraction\nObjective: c\n1.2 Lenses\nObjective: d\nPrerequisites: 1.1\n"
    r = student.post("/api/subjects/start", data={"topic": "Physics", "goal": "exam", "prior_knowledge": "none", "rights_ack": "true"},
                     files=[("files", ("a.txt", a, "text/plain")), ("files", ("b.txt", b, "text/plain"))])
    cs = student.get(f"/api/subjects/{r.json()['subject']['id']}/setup").json()["proposal"]["concepts"]
    assert [(c["key"], c["title"]) for c in cs] == [("1.1", "Wavelength"), ("1.2", "Frequency"), ("2.1", "Refraction"), ("2.2", "Lenses")]
    assert cs[3]["prerequisites"] == ["2.1"]


def test_retry_gets_a_new_queue_id_so_the_queue_cannot_drop_it():
    class Db:
        info: dict = {}

    job = jobs.Job(id="j1", attempts=0)
    jobs._queue(Db, job)
    job.attempts = 1
    jobs._queue(Db, job)
    assert Db.info["after_commit_jobs"] == ["j1:0", "j1:1"]


def test_malformed_ai_answer_is_rejected_not_crashing():
    t = llm.REGISTRY["generate_topic_scope"]
    assert not llm._validate(t, {"title": "x", "units": ["Unit 1", "Unit 2"]})
    assert llm._validate(t, {"title": "x", "units": [{"no": 1, "title": "u", "concepts": []}]})


def test_book_upload_end_to_end_and_summary_on_demand(student):
    text = "\f".join(p + " lorem ipsum" * 300 for p in _book())
    r = student.post("/api/subjects/start", data={"topic": "C++", "goal": "explore", "prior_knowledge": "none", "rights_ack": "true"},
                     files=[("files", ("cpp.txt", text.encode(), "text/plain"))])
    sid = r.json()["subject"]["id"]
    setup = student.get(f"/api/subjects/{sid}/setup").json()
    assert setup["proposal"]["label"].startswith("From your book") and len(setup["proposal"]["concepts"]) == 8
    student.post(f"/api/subjects/{sid}/scope/confirm", json={"graph_revision_id": setup["proposal"]["id"], "edits": []})
    sm = student.post(f"/api/subjects/{sid}/summary", json={}).json()["summary"]
    assert sm["progress"]["done"] == 4 and sm["progress"]["later"] > 10 and sm["status"] == "ready"
    assert sm["coverage"]["pages_covered"] < sm["coverage"]["pages_total"]  # honest coverage
    after = student.post(f"/api/subjects/{sid}/summary/more").json()["summary"]
    assert after["progress"]["done"] == 9
    one = next(x for x in after["sections"] if x["status"] == "later")
    assert student.post(f"/api/summary-sections/{one['id']}/retry").json()["status"] == "ready"
