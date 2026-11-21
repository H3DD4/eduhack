"""Test harness: SQLite file DB per test, inline jobs, local storage, deterministic demo adapters.

Env vars override api/.env, so real provider keys present on a dev machine are never used by tests.
"""

from __future__ import annotations

import os

os.environ.update({
    "LLM_PROVIDER": "demo", "STT_PROVIDER": "demo", "JOB_MODE": "inline", "STORAGE_BACKEND": "local",
    "GEMINI_API_KEY": "", "GROQ_API_KEY": "", "ANTHROPIC_API_KEY": "", "DEMO_MODE": "true",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from thinkfirst.config import get_settings  # noqa: E402
from thinkfirst.core import db as dbmod  # noqa: E402
from thinkfirst.core.storage import LocalStorage, set_storage  # noqa: E402


@pytest.fixture()
def app_client(tmp_path):
    get_settings.cache_clear()
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.db'}"
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "storage")
    get_settings.cache_clear()
    engine = dbmod.configure(os.environ["DATABASE_URL"])
    dbmod.create_all_for_tests(engine)
    set_storage(LocalStorage(str(tmp_path / "storage")))
    from thinkfirst.modules.llm_gateway import service as llm

    llm._cache.clear()
    from thinkfirst.main import create_app

    client = TestClient(create_app())
    client.headers["x-thinkfirst-client"] = "web"
    yield client
    engine.dispose()


def register(client: TestClient, email: str = "student@example.com") -> dict:
    r = client.post("/api/auth/register", json={"email": email, "password": "correct horse"})
    assert r.status_code == 200, r.text
    return r.json()["user"]


@pytest.fixture()
def student(app_client):
    register(app_client)
    return app_client


@pytest.fixture()
def db_session():
    with dbmod.session_factory()() as s:
        yield s


def upload_demo_subject(client: TestClient) -> str:
    from thinkfirst.fixtures import DEMO_COURSE_FILENAME, demo_course_pdf

    r = client.post("/api/subjects", data={"name": "MATH 101", "role": "course", "rights_ack": "true"},
                    files=[("files", (DEMO_COURSE_FILENAME, demo_course_pdf(), "application/pdf"))])
    assert r.status_code == 200, r.text
    return r.json()["subject"]["id"]


def ready_subject(client: TestClient) -> tuple[str, dict]:
    sid = upload_demo_subject(client)
    setup = client.get(f"/api/subjects/{sid}/setup").json()
    assert setup["proposal"], setup
    r = client.post(f"/api/subjects/{sid}/scope/confirm", json={"graph_revision_id": setup["proposal"]["id"], "edits": []})
    assert r.status_code == 200, r.text
    road = client.get(f"/api/subjects/{sid}/roadmap").json()
    return sid, road


def concept_by_title(road: dict, needle: str) -> dict:
    for u in road["units"]:
        for c in u["concepts"] + u["foundations"]:
            if needle.lower() in c["title"].lower():
                return c
    raise AssertionError(f"concept {needle} not found")
