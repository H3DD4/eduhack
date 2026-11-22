"""Start wizard -> roadmap -> placement test (AI questions, cross-checked) -> level + metrics -> engine priors ->
level-adapted course summary with page coverage. Offline: fake AI adapters registered on the demo provider."""

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import select

from thinkfirst.core import db as dbmod
from thinkfirst.modules.diagnostic.grading.models import DiagnosticItemRow
from thinkfirst.modules.tutor.llm import service as llm

COURSE = """Unit 3: Circuits
3.1 Ohm's law
Objective: Relate voltage, current and resistance with V = R I.
Ohm's law says the voltage across a resistor equals its resistance times the current through it.
--- page 2 ---
3.2 Series circuits
Objective: Compute the equivalent resistance of resistors in series.
Prerequisites: 3.1
In a series circuit the same current flows through every resistor, and resistances add up.
--- page 3 ---
3.3 Parallel circuits
Objective: Compute the equivalent resistance of resistors in parallel.
Prerequisites: 3.1
In parallel the voltage is shared and the inverse resistances add up.
"""


def _items(v: dict) -> dict:
    out = []
    for c in v["concepts"]:
        for d in ("easy", "medium", "hard"):
            sabotaged = c["key"] == "3.1" and d == "hard"  # wrong key: the independent cross-check must reject it
            out.append({"concept_key": c["key"], "difficulty": d, "question": f"{c['title']}: {d} question?",
                        "correct": f"BAD {c['key']} {d}" if sabotaged else f"RIGHT {c['key']} {d}",
                        "distractors": [{"text": (f"RIGHT {c['key']} {d}" if sabotaged and n == 0 else f"wrong{n} {c['key']} {d}"),
                                         "misconception": f"Mix up {n}"} for n in range(3)]})
        out.append({"concept_key": c["key"], "difficulty": "easy", "question": "invalid: 2 distractors", "correct": "x",
                    "distractors": [{"text": "y", "misconception": "a"}, {"text": "z", "misconception": "b"}]})
    return {"items": out}


def _check(v: dict) -> dict:
    return {"answers": [{"qid": q["qid"], "option_id": next((o["id"] for o in q["options"] if o["text"].startswith("RIGHT")), "none")}
                        for q in v["questions"]]}


@pytest.fixture()
def fake_ai(monkeypatch):
    monkeypatch.setitem(llm._demo_adapters, "generate_placement_items", _items)
    monkeypatch.setitem(llm._demo_adapters, "cross_check_items", _check)
    from thinkfirst.modules.diagnostic import placement

    monkeypatch.setattr(placement, "_ai_available", lambda: True)


def _start(client, prior: str, goal: str = "exam", **extra) -> str:
    r = client.post("/api/subjects/start", data={"topic": "Electric circuits", "goal": goal, "prior_knowledge": prior,
                                                 "exam_date": "2030-06-01", "rights_ack": "true", "paste_text": COURSE, **extra})
    assert r.status_code == 200, r.text
    sid = r.json()["subject"]["id"]
    setup = client.get(f"/api/subjects/{sid}/setup").json()
    assert [c["key"] for c in setup["proposal"]["concepts"]] == ["3.1", "3.2", "3.3"]
    r = client.post(f"/api/subjects/{sid}/scope/confirm", json={"graph_revision_id": setup["proposal"]["id"], "edits": []})
    assert r.status_code == 200, r.text
    return sid


def test_wizard_validation(student):
    bad = student.post("/api/subjects/start", data={"topic": "X ray", "goal": "fun", "prior_knowledge": "none"})
    assert bad.status_code == 422
    no_rights = student.post("/api/subjects/start", data={"topic": "Optics", "goal": "explore", "prior_knowledge": "none",
                                                          "paste_text": "1.1 Lenses"})
    assert no_rights.status_code == 422 and "Confirm" in no_rights.json()["error"]["message"]
    bad_date = student.post("/api/subjects/start", data={"topic": "Optics", "goal": "exam", "prior_knowledge": "none",
                                                         "exam_date": "next week"})
    assert bad_date.status_code == 422


def test_from_scratch_path_is_beginner_with_low_engine_priors_and_full_coverage_summary(student):
    sid = _start(student, "none")
    j = student.get(f"/api/subjects/{sid}/journey").json()
    assert j["intent"]["goal"] == "exam" and j["intent"]["exam_date"] == "2030-06-01" and j["intent"]["has_material"]
    steps = {s["key"]: s for s in j["steps"]}
    assert steps["roadmap"]["state"] == "done"
    assert steps["level"]["state"] == "done" and "Beginner" in steps["level"]["detail"]
    assert j["level"]["basis"] == "from_scratch" and j["level"]["level"] == "beginner"
    assert steps["summary"]["state"] == "current" and j["next"]["step"] == "summary"

    state = student.get(f"/api/subjects/{sid}/learner-state").json()["state"]["concepts"]
    assert state and all(abs(c["p_mastery"] - 0.05) < 1e-6 for c in state.values())

    s = student.post(f"/api/subjects/{sid}/summary", json={}).json()["summary"]
    assert s["mode"] == "course" and s["level"] == "beginner" and s["status"] == "ready"
    assert s["coverage"]["pages_total"] == 3 and s["coverage"]["pages_covered"] == 3 and s["coverage"]["missing"] == []
    assert s["sections"][0]["content"]["blocks"] and "no AI service" in s["label"]
    # idempotent for the same level
    again = student.post(f"/api/subjects/{sid}/summary", json={}).json()["summary"]
    assert again["id"] == s["id"]
    j = student.get(f"/api/subjects/{sid}/journey").json()
    assert {x["key"]: x["state"] for x in j["steps"]}["summary"] == "done"
    assert j["next"]["step"] == "learn"


def test_placement_questions_are_generated_cross_checked_and_measure_the_level(student, fake_ai):
    sid = _start(student, "some")
    with dbmod.session_factory()() as db:
        rows = db.scalars(select(DiagnosticItemRow).where(DiagnosticItemRow.subject_id == sid,
                                                          DiagnosticItemRow.generated.is_(True))).all()
        assert len(rows) == 9  # 3 concepts x 3 valid items (the 2-distractor item is dropped)
        bad = [r for r in rows if not r.verified]
        assert len(bad) == 1 and bad[0].prompt.endswith("hard question?") and bad[0].skills == ["3.1"]
        assert all(r.cross_checked == r.verified for r in rows)
        assert {r.difficulty_label for r in rows} == {"easy", "medium", "hard"}
        assert all(sum(o["misconception"] is None for o in r.options) == 1 and len(r.options) == 4 for r in rows)
        key = {r.item_key: r for r in rows}

    j = student.get(f"/api/subjects/{sid}/journey").json()
    assert j["placement"]["state"] == "ready" and j["placement"]["verified_items"] == 8
    assert {s["key"]: s["state"] for s in j["steps"]}["level"] == "current" and j["next"]["href"].endswith("/diagnostic")
    assert j["level"]["available"] is False

    st = student.post(f"/api/subjects/{sid}/diagnostic/start", json={}).json()
    seen = []
    while st["status"] == "active":
        item = st["current_item"]
        assert item["id"] in key and key[item["id"]].verified  # only verified AI questions, no placeholders
        seen.append(item["id"])
        right = next(o["id"] for o in key[item["id"]].options if o["misconception"] is None)
        st = student.post(f"/api/subjects/{sid}/diagnostic/answer",
                          json={"item_id": item["id"], "option_id": right, "confidence": 4, "duration_ms": 20000}).json()
    assert st["status"] == "completed" and 5 <= len(seen) <= 12

    lv = student.get(f"/api/subjects/{sid}/level").json()["report"]
    assert lv["basis"] == "placement_test" and lv["level"] in ("advanced", "expert") and lv["score"] >= 60
    m = lv["metrics"]
    assert m["answered"] == len(seen) and m["accuracy"] == 100 and m["dont_know"] == 0
    assert sum(d["asked"] for d in m["by_difficulty"].values()) == len(seen)
    assert m["avg_seconds"] == 20 and "70% estimated mastery" in lv["explanation"]
    assert sum(u["total"] for u in lv["by_unit"]) == 3

    # the learner engine now starts from the measured level
    state = student.get(f"/api/subjects/{sid}/learner-state").json()["state"]["concepts"]
    assert all(c["p_mastery"] >= 0.6 and c["level"] >= 3 for c in state.values())
    assert any("placement" in r for c in state.values() for r in c["reasons"])

    s = student.post(f"/api/subjects/{sid}/summary", json={}).json()["summary"]
    assert s["level"] == lv["level"] and s["coverage"]["pages_covered"] == 3


def test_dont_know_answers_give_beginner_level(student, fake_ai):
    sid = _start(student, "some")
    st = student.post(f"/api/subjects/{sid}/diagnostic/start", json={}).json()
    while st["status"] == "active":
        st = student.post(f"/api/subjects/{sid}/diagnostic/answer",
                          json={"item_id": st["current_item"]["id"], "dont_know": True, "duration_ms": 5000}).json()
    lv = student.get(f"/api/subjects/{sid}/level").json()["report"]
    assert lv["level"] == "beginner" and lv["metrics"]["dont_know"] == lv["metrics"]["answered"]
    assert lv["metrics"]["gaps"] and not lv["metrics"]["strengths"]


def test_change_of_mind_and_no_ai_fallbacks(student):
    sid = _start(student, "none")
    r = student.patch(f"/api/subjects/{sid}/intent", json={"prior_knowledge": "some"})
    assert r.status_code == 200 and r.json()["subject"]["prior_knowledge"] == "some"
    j = student.get(f"/api/subjects/{sid}/journey").json()
    # no AI service: no generated questions, the built-in basic check is used
    assert j["placement"]["state"] == "ready" and j["placement"]["uses_ai_questions"] is False
    assert student.post(f"/api/subjects/{sid}/summary", json={}).status_code == 422  # level not known yet
    student.patch(f"/api/subjects/{sid}/intent", json={"prior_knowledge": "none"})
    assert student.post(f"/api/subjects/{sid}/summary", json={}).status_code == 200


def test_summary_coverage_repair_and_incomplete_pages_are_reported(student, monkeypatch):
    calls = []

    def skipping(v):
        calls.append(v)
        pages = v["course_pages"]
        if "note" in v and len(calls) < 3:  # first repair works for the first section only
            keep = pages
        else:
            keep = [p for p in pages if p["page"] != 2]  # always "forgets" page 2
        return {"title": "Circuits", "blocks": [{"type": "paragraph", "text": "ok", "pages": [p["page"] for p in keep]}],
                "key_terms": [], "common_mistakes": [], "check_questions": [], "covered_pages": [p["page"] for p in keep]}

    monkeypatch.setitem(llm._demo_adapters, "summarize_course_section", skipping)
    sid = _start(student, "none")
    s = student.post(f"/api/subjects/{sid}/summary", json={}).json()["summary"]
    assert s["status"] == "ready" and s["coverage"]["missing"] == []  # page 2 recovered by the repair pass
    assert any("note" in c for c in calls)

    def always_skips(v):
        keep = [p for p in v["course_pages"] if p["page"] != 2]
        return {"title": "Circuits", "blocks": [{"type": "paragraph", "text": "ok", "pages": [p["page"] for p in keep]}],
                "key_terms": [], "common_mistakes": [], "check_questions": [], "covered_pages": [p["page"] for p in keep]}

    monkeypatch.setitem(llm._demo_adapters, "summarize_course_section", always_skips)
    llm._cache.clear()
    s = student.post(f"/api/subjects/{sid}/summary", json={"regenerate": True}).json()["summary"]
    assert s["status"] == "partial" and s["coverage"]["missing"] == [{"filename": "Pasted notes.txt", "page": 2}]
    sec = s["sections"][0]
    assert sec["status"] == "incomplete" and sec["missing_pages"] == [2]
    assert student.post(f"/api/summary-sections/{sec['id']}/retry").json()["status"] in ("incomplete", "pending", "ready")


def test_topic_summary_needs_ai_and_docx_upload_builds_a_roadmap(student):
    r = student.post("/api/subjects/start", data={"topic": "Optics", "goal": "explore", "prior_knowledge": "none"})
    sid = r.json()["subject"]["id"]
    assert r.json()["subject"]["goal"] == "explore"
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paras = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in
                    ["Unit 4: Waves", "4.1 Wavelength", "Objective: Relate speed, frequency and wavelength."])
    doc = (f'<w:document xmlns:w="{W}"><w:body>{paras}<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
           f"<w:p><w:r><w:t>4.2 Interference</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>f</w:t></w:r></w:p></w:tc>"
           f"<w:tc><w:p><w:r><w:t>Hz</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
    r = student.post("/api/subjects/start", data={"topic": "Waves", "goal": "exam", "prior_knowledge": "none",
                                                  "rights_ack": "true"},
                     files=[("files", ("waves.docx", buf.getvalue(),
                                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))])
    assert r.status_code == 200, r.text
    wid = r.json()["subject"]["id"]
    setup = student.get(f"/api/subjects/{wid}/setup").json()
    assert setup["sources"][0]["page_count"] == 2
    assert [c["key"] for c in setup["proposal"]["concepts"]] == ["4.1", "4.2"]
    from thinkfirst.modules.rag.ingestion.extract import extract_pages

    assert "f | Hz" in extract_pages(buf.getvalue(), "docx", 10)[1]
    # topic without files and without an AI service: the summary is refused with a clear reason
    with dbmod.session_factory()() as db:
        from thinkfirst.platform.workspaces.models import Subject

        db.get(Subject, sid).status = "ready"
        db.commit()
    resp = student.post(f"/api/subjects/{sid}/summary", json={})
    assert resp.status_code == 422 and "AI service" in resp.json()["error"]["message"]


def test_roadmap_is_locked_until_the_level_test_then_marked_with_its_result(student, fake_ai):
    sid = _start(student, "some")
    rm = student.get(f"/api/subjects/{sid}/roadmap").json()
    assert rm["placement"]["required"] is True and rm["level"] is None
    st = student.post(f"/api/subjects/{sid}/diagnostic/start", json={}).json()
    with dbmod.session_factory()() as db:
        key = {r.item_key: r for r in db.scalars(select(DiagnosticItemRow).where(DiagnosticItemRow.subject_id == sid)).all()}
    while st["status"] == "active":
        item = st["current_item"]
        right = next(o["id"] for o in key[item["id"]].options if o["misconception"] is None)
        st = student.post(f"/api/subjects/{sid}/diagnostic/answer",
                          json={"item_id": item["id"], "option_id": right, "duration_ms": 15000}).json()
    rm = student.get(f"/api/subjects/{sid}/roadmap").json()
    assert rm["placement"]["required"] is False and rm["level"]["basis"] == "placement_test"
    marks = [c["placement_status"] for u in rm["units"] for c in u["concepts"]]
    assert marks and all(m in ("known", "partly") for m in marks) and rm["level"]["to_learn"] == 0  # all answers right


def test_journey_level_step_is_always_clickable_while_questions_are_written(student, fake_ai, monkeypatch):
    from thinkfirst.modules.diagnostic import placement

    sid = _start(student, "some")
    monkeypatch.setattr(placement, "status", lambda db, o, s: {"state": "preparing", "answered": 0, "generated_items": 0,
                                                              "verified_items": 0, "job_id": "j", "uses_ai_questions": True})
    from thinkfirst.modules.adaptation import journey

    monkeypatch.setattr(journey.placement, "status", placement.status)
    j = student.get(f"/api/subjects/{sid}/journey").json()
    lvl = next(s for s in j["steps"] if s["key"] == "level")
    assert lvl["state"] == "current" and lvl["action"]["href"].endswith("/diagnostic")


def test_model_json_is_repaired_not_dropped():
    from thinkfirst.modules.tutor.llm.service import _loads

    bs = "\\"
    raw = "```json\n{\"a\": \"$" + bs + "alpha + " + bs + "frac{1}{2}$, " + bs + "theta\", \"n\": \"x" + bs + "ny\"}\n```"
    out = _loads(raw)
    assert out == {"a": "$" + bs + "alpha + " + bs + "frac{1}{2}$, " + bs + "theta", "n": "x\ny"}
    assert _loads('Sure: {"k": [1]} done') == {"k": [1]}
    lp = _loads('{"m": "' + bs + 'begin{pmatrix}1 & 0\\\\ 0 & 1' + bs + 'end{pmatrix}", "s": "' + bs + 'text{s.t.} x ' + bs + 'Rightarrow y"}')
    assert lp == {"m": f"{bs}begin{{pmatrix}}1 & 0\\ 0 & 1{bs}end{{pmatrix}}", "s": f"{bs}text{{s.t.}} x {bs}Rightarrow y"}


JAVA = """Unit 1: Java basics
1.1 Java syntax
Objective: Declare typed variables and write a main method in Java.
A Java program starts in the main method of a class and every variable has a type.
1.2 Control flow
Objective: Use if, for and while in Java.
Loops repeat a block while a boolean condition holds, for example for and while loops.
Unit 2: Objects
2.1 Classes and Objects
Objective: Define a class and create objects with new.
A class describes fields and methods; new creates an object on the heap.
"""


def test_algebra_questions_never_reach_another_subject_with_the_same_concept_numbers(student, fake_ai, monkeypatch):
    from thinkfirst.modules.diagnostic.service import CURATED_BANK

    seen: list[dict] = []
    monkeypatch.setitem(llm._demo_adapters, "generate_placement_items", lambda v: (seen.append(v), _items(v))[1])
    sid = student.post("/api/subjects/start", data={"topic": "Java Programming Learning Roadmap", "goal": "explore",
                                                    "prior_knowledge": "some", "rights_ack": "true",
                                                    "paste_text": JAVA}).json()["subject"]["id"]
    rev = student.get(f"/api/subjects/{sid}/setup").json()["proposal"]
    assert [c["key"] for c in rev["concepts"]] == ["1.1", "1.2", "2.1"]  # same numbers as the algebra course
    student.post(f"/api/subjects/{sid}/scope/confirm", json={"graph_revision_id": rev["id"], "edits": []})
    assert seen and all(v["subject"] == "Java Programming" for v in seen)
    assert {c["key"] for v in seen for c in v["concepts"]} == {"1.1", "1.2", "2.1"}  # none skipped
    algebra = {t["prompt"] for items in CURATED_BANK.values() for t in items}
    st, asked = student.post(f"/api/subjects/{sid}/diagnostic/start", json={}).json(), []
    while st["status"] == "active":
        asked.append(st["current_item"]["prompt"])
        st = student.post(f"/api/subjects/{sid}/diagnostic/answer",
                          json={"item_id": st["current_item"]["id"], "dont_know": True, "duration_ms": 4000}).json()
    assert asked and not set(asked) & algebra and not any("core goal" in q for q in asked)


def test_invalid_session_can_be_retaken_and_is_announced(student, fake_ai):
    from thinkfirst.modules.diagnostic.grading.models import DiagnosticSessionRow

    sid = _start(student, "some")
    student.post(f"/api/subjects/{sid}/diagnostic/start", json={})
    with dbmod.session_factory()() as db:
        db.scalar(select(DiagnosticSessionRow).where(DiagnosticSessionRow.subject_id == sid)).status = "invalid"
        db.commit()
    p = student.post(f"/api/subjects/{sid}/placement/prepare").json()["placement"]
    assert p["discarded_test"] is True and p["state"] == "ready"
    assert student.get(f"/api/subjects/{sid}/diagnostic").json()["adaptive"] is None
    assert student.post(f"/api/subjects/{sid}/diagnostic/start", json={}).json()["status"] == "active"


def test_busy_ai_continues_in_new_rounds_instead_of_a_tiny_test(student, fake_ai, monkeypatch):
    calls = {"n": 0}

    def flaky(v):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("busy")
        return _items(v)

    monkeypatch.setitem(llm._demo_adapters, "generate_placement_items", flaky)
    sid = _start(student, "some")
    p = student.get(f"/api/subjects/{sid}/level").json()["placement"]
    assert calls["n"] >= 3 and p["state"] == "ready" and p["verified_items"] >= 6  # the lost batch was written again
    with dbmod.session_factory()() as db:
        keys = [r.item_key for r in db.scalars(select(DiagnosticItemRow).where(DiagnosticItemRow.subject_id == sid,
                                                                              DiagnosticItemRow.generated.is_(True))).all()]
    assert len(keys) == len(set(keys))


def test_no_silent_demo_content_when_every_ai_is_busy(app_client, monkeypatch):
    from thinkfirst.config import get_settings

    assert get_settings().llm_demo_fallback is False
    monkeypatch.setattr(llm, "provider_chain", lambda: ["groq"])
    monkeypatch.setitem(llm._CALLERS, "groq", lambda t, u: (_ for _ in ()).throw(llm._ProviderError("RATE_LIMITED")))
    with dbmod.session_factory()() as db:
        res = llm.run(db, "generate_concept_pack", {"concept": {}}, owner_id=None, purpose="x")
    assert res.status == "error" and not res.simulated
