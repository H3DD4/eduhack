"""TutorService: the facade the API (and ThinkFirst integration) calls. Owns ownership checks, job dispatch and
the public views (answers are never sent before the student has attempted)."""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .agents import assess, create, plan, teach
from .agents.base import Ctx
from .config import TutorSettings, get_settings
from .ingestion.parsers import SUPPORTED, ext_of
from .llm.gateway import build_llm
from .orchestrator.flows import FLOWS
from .orchestrator.graph import Runner
from .rag.embed import build_embedder
from .rag.index import build_reranker
from .rag.kb import KnowledgeBase
from .research.scraper import PoliteFetcher
from .research.search import build_search
from .schemas import Track, new_id, now_iso

log = logging.getLogger("tutor.service")
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_FILES_PER_TRACK = 20


class TutorError(Exception):
    status = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str = "", code: str | None = None, status: int | None = None):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.code = code or self.code
        self.status = status or self.status


class NotFound(TutorError):
    status, code = 404, "NOT_FOUND"


class Conflict(TutorError):
    status, code = 409, "CONFLICT"


class Locked(TutorError):
    status, code = 423, "POLICY_LOCKED"


class TutorService:
    def __init__(self, ctx: Ctx, *, job_mode: str = "thread", enqueue=None):
        self.ctx = ctx
        self.job_mode = job_mode
        self.enqueue = enqueue                       # arq: callable(run_id)
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tutor") if job_mode == "thread" else None

    # ------------------------------------------------------------------ helpers
    @property
    def store(self):
        return self.ctx.store

    def _track(self, owner_id: str, track_id: str) -> dict[str, Any]:
        t = self.store.get("tracks", track_id)
        if not t or t["owner_id"] != owner_id:
            raise NotFound()
        return t

    def _meter(self, track_id: str | None, tokens: int) -> None:
        if not track_id:
            return
        t = self.store.get("tracks", track_id)
        if t:
            t["budget_used"] = t.get("budget_used", 0) + tokens
            self.store.put("tracks", t)

    def _find_item(self, track_id: str, item_id: str) -> tuple[dict[str, Any], dict[str, Any], str]:
        for a in self.store.list("artifacts", track_id=track_id):
            c = a["content"]
            pools = [c.get("items", [])]
            pools += [p.get("items", []) for p in c.get("parts", [])] if a["type"] == "mock_exam" else []
            pools += [s.get("items", []) for s in c.get("sections", [])] if a["type"] == "lesson" else []
            for pool in pools:
                for it in pool:
                    if it.get("id") == item_id:
                        return a, it, a["type"]
        raise NotFound("item")

    def capabilities(self) -> dict[str, Any]:
        s = self.ctx.settings
        return {"llm": self.ctx.llm.name, "simulated": self.ctx.llm.simulated, "embedder": self.ctx.kb.embedder.name,
                "reranker": bool(self.ctx.kb.reranker), "search": getattr(self.ctx.search, "name", "none"),
                "web_research": s.web_research, "formats": list(SUPPORTED), "job_mode": self.job_mode,
                "math_check": _has("sympy")}

    # ------------------------------------------------------------------ tracks and documents
    def create_track(self, owner_id: str, *, valley: str, title: str, subject: str = "", goal: str = "",
                     exam_date: str | None = None, chapters: list[str] | None = None, allow_web: bool = True,
                     language: str = "fr") -> dict[str, Any]:
        t = Track(owner_id=owner_id, valley=valley, title=title, subject=subject, goal=goal, exam_date=exam_date,
                  chapters=chapters or [], allow_web=allow_web, language=language).model_dump()
        self.store.put("tracks", t)
        self.ctx.event("track.created", {"track_id": t["id"], "valley": valley})
        return t

    def list_tracks(self, owner_id: str) -> list[dict[str, Any]]:
        return sorted(self.store.list("tracks", owner_id=owner_id), key=lambda t: t["updated_at"], reverse=True)

    def get_track(self, owner_id: str, track_id: str) -> dict[str, Any]:
        t = self._track(owner_id, track_id)
        docs = self.store.list("documents", track_id=track_id)
        concepts = self.ctx.concepts(track_id)
        runs = sorted(self.store.list("runs", track_id=track_id), key=lambda r: r["created_at"])
        fp = self.ctx.fingerprint(track_id)
        return {**t, "documents": docs, "concepts": concepts, "last_run": runs[-1] if runs else None,
                "fingerprint": {k: fp.get(k) for k in ("language", "preferred_notation", "verbs", "numbering",
                                                       "question_types", "blueprint")} if fp else None,
                "web_sources": self.store.list("web_sources", track_id=track_id)}

    def update_track(self, owner_id: str, track_id: str, **changes: Any) -> dict[str, Any]:
        t = self._track(owner_id, track_id)
        allowed = {k: v for k, v in changes.items() if k in ("title", "subject", "goal", "exam_date", "chapters",
                                                            "allow_web") and v is not None}
        return self.ctx.save_track(t, **allowed)

    def delete_track(self, owner_id: str, track_id: str) -> None:
        self._track(owner_id, track_id)
        self.store.delete_track(track_id)
        self.ctx.kb.invalidate(track_id)

    def add_document(self, owner_id: str, track_id: str, filename: str, data: bytes) -> dict[str, Any]:
        t = self._track(owner_id, track_id)
        if ext_of(filename) not in SUPPORTED:
            raise TutorError(f"Unsupported format. Use {', '.join(SUPPORTED)}.", code="UNSUPPORTED_FORMAT")
        if len(data) > MAX_FILE_BYTES:
            raise TutorError("File too large (25 MB max).", code="FILE_TOO_LARGE", status=413)
        docs = self.store.list("documents", track_id=track_id)
        if len(docs) >= MAX_FILES_PER_TRACK:
            raise TutorError("Too many files for one track.", code="TOO_MANY_FILES")
        sha = hashlib.sha256(data).hexdigest()
        dup = next((d for d in docs if d["sha256"] == sha), None)
        if dup:
            return dup
        doc_id = new_id()
        key = f"tutor/{owner_id}/{track_id}/{doc_id}{ext_of(filename)}"
        self.store.put_blob(key, data)
        d = {"id": doc_id, "track_id": track_id, "owner_id": owner_id, "filename": filename[:200], "mime": "",
             "sha256": sha, "blob_key": key, "doc_type": "other", "title": "", "pages": 0, "status": "uploaded",
             "error": None, "ocr_pages": 0, "created_at": now_iso()}
        self.store.put("documents", d)
        if t["status"] in ("ready", "levelled", "awaiting_level", "failed"):
            self.ctx.save_track(t, status="created")   # new material: prepare again
        return d

    def remove_document(self, owner_id: str, track_id: str, doc_id: str) -> None:
        self._track(owner_id, track_id)
        d = self.store.get("documents", doc_id)
        if not d or d["track_id"] != track_id:
            raise NotFound()
        for c in self.store.list("chunks", track_id=track_id, where={"document_id": doc_id}):
            self.store.delete("chunks", c["id"])
        self.store.delete("documents", doc_id)
        self.ctx.kb.invalidate(track_id)

    # ------------------------------------------------------------------ flows
    def start_flow(self, owner_id: str, track_id: str, flow: str) -> dict[str, Any]:
        t = self._track(owner_id, track_id)
        active = [r for r in self.store.list("runs", track_id=track_id) if r["status"] in ("queued", "running")]
        if active:
            return active[-1]
        if flow == "build":
            flow = "revision" if t["valley"] == "revision" else "skills"
        if flow not in FLOWS:
            raise TutorError("unknown flow")
        if flow == "prepare" and not self.store.list("documents", track_id=track_id) and t["valley"] == "revision":
            raise TutorError("Upload at least one course document first.", code="NO_DOCUMENTS")
        if flow in ("revision", "skills") and t["status"] not in ("levelled", "ready", "awaiting_level", "failed"):
            raise Conflict("Finish the level check first.", code="LEVEL_FIRST")
        run = {"id": new_id(), "track_id": track_id, "owner_id": owner_id, "flow": flow, "status": "queued",
               "node": None, "steps": [], "error": None, "state": {"track_id": track_id}, "created_at": now_iso(),
               "updated_at": now_iso()}
        self.store.put("runs", run)
        self._dispatch(run["id"])
        return self.store.get("runs", run["id"])

    def resume_run(self, owner_id: str, run_id: str) -> dict[str, Any]:
        run = self.get_run(owner_id, run_id)
        if run["status"] != "failed":
            return run
        run["status"], run["error"] = "queued", None
        self.store.put("runs", run)
        self._dispatch(run_id)
        return self.store.get("runs", run_id)

    def _dispatch(self, run_id: str) -> None:
        if self.job_mode == "inline":
            self.execute_run(run_id)
        elif self.job_mode == "arq" and self.enqueue:
            self.enqueue(run_id)
        else:
            assert self._pool is not None
            self._pool.submit(self.execute_run, run_id)

    def execute_run(self, run_id: str) -> dict[str, Any]:
        run = self.store.get("runs", run_id)
        if run is None or run["status"] in ("succeeded",):
            return run
        return Runner(self.ctx).run(FLOWS[run["flow"]](), run)

    def get_run(self, owner_id: str, run_id: str) -> dict[str, Any]:
        r = self.store.get("runs", run_id)
        if not r or r["owner_id"] != owner_id:
            raise NotFound()
        return r

    # ------------------------------------------------------------------ level check
    def declare_level(self, owner_id: str, track_id: str, level: str, per_chapter: dict[str, str] | None = None,
                      skip_probe: bool = False) -> dict[str, Any]:
        t = self._track(owner_id, track_id)
        if t["status"] not in ("awaiting_level", "probing", "levelled", "ready"):
            raise Conflict("The course is still being prepared.", code="NOT_READY")
        assess.start(self.ctx, track_id, level, per_chapter)
        if skip_probe:
            return {"result": assess.reconcile(self.ctx, track_id=track_id)}
        return {"item": assess.next_item(self.ctx, track_id)}

    def probe_answer(self, owner_id: str, track_id: str, item_id: str, choice, ms: int | None) -> dict[str, Any]:
        self._track(owner_id, track_id)
        try:
            r = assess.answer(self.ctx, track_id, item_id, choice, ms)
        except KeyError:
            raise NotFound("item") from None
        if r["done"]:
            return {**r, "result": assess.reconcile(self.ctx, track_id=track_id)}
        return {**r, "item": assess.next_item(self.ctx, track_id)}

    def probe_finish(self, owner_id: str, track_id: str) -> dict[str, Any]:
        self._track(owner_id, track_id)
        return assess.reconcile(self.ctx, track_id=track_id)

    # ------------------------------------------------------------------ material
    def plan(self, owner_id: str, track_id: str) -> dict[str, Any] | None:
        self._track(owner_id, track_id)
        return self.store.get("plans", track_id)

    def artifacts(self, owner_id: str, track_id: str, type_: str | None = None) -> list[dict[str, Any]]:
        self._track(owner_id, track_id)
        arts = [a for a in self.store.list("artifacts", track_id=track_id)
                if a["type"] != "probe" and (type_ is None or a["type"] == type_)]
        return [self._summary(a) for a in arts]

    @staticmethod
    def _summary(a: dict[str, Any]) -> dict[str, Any]:
        c = a["content"]
        n = len(c.get("items", [])) or len(c.get("sections", [])) or sum(len(p.get("items", [])) for p in c.get("parts", []))
        return {k: a[k] for k in ("id", "type", "title", "chapter", "concept_keys", "likeness", "status", "created_at")} | {
            "count": n}

    def artifact(self, owner_id: str, artifact_id: str) -> dict[str, Any]:
        a = self.store.get("artifacts", artifact_id)
        if not a or a["owner_id"] != owner_id or a["type"] == "probe":
            raise NotFound()
        return self.public_artifact(a)

    def public_artifact(self, a: dict[str, Any]) -> dict[str, Any]:
        a = {**a, "content": dict(a["content"])}
        done = {x["item_id"] for x in self.store.list("attempts", track_id=a["track_id"])
                if x.get("artifact_id") == a["id"] and (x["correct"] or x["help_level"] >= 4)}
        if a["type"] in ("qcm", "quiz", "exercises"):
            a["content"]["items"] = [it if it["id"] in done else assess.public_item(it) for it in a["content"]["items"]]
        elif a["type"] == "mock_exam":
            a["content"]["parts"] = [{**p, "items": [assess.public_item(i) for i in p["items"]]} for p in a["content"]["parts"]]
        elif a["type"] == "lesson":
            a["content"]["sections"] = [{**s, "items": [i if i["id"] in done else assess.public_item(i) for i in s["items"]]}
                                        for s in a["content"]["sections"]]
        return a

    def regenerate(self, owner_id: str, artifact_id: str) -> dict[str, Any]:
        a = self.store.get("artifacts", artifact_id)
        if not a or a["owner_id"] != owner_id:
            raise NotFound()
        track_id = a["track_id"]
        cmap = self.ctx.concept_map(track_id)
        cs = [cmap[k] for k in a["concept_keys"] if k in cmap]
        new = None
        kind = {"qcm": "qcm", "quiz": "quiz", "fiches": "fiche", "exercises": "exercise"}.get(a["type"])
        if kind:
            self.store.delete("artifacts", artifact_id)   # its items must not count as duplicates
            new = create.build_item_artifact(self.ctx, track_id, kind, a["title"], cs,
                                             count=max(1, len(a["content"].get("items", []))), chapter=a["chapter"])
            if new is None:
                self.store.put("artifacts", a)
        elif a["type"] == "resume":
            new = create.build_resume(self.ctx, track_id, a["chapter"], cs)
            if new:
                self.store.delete("artifacts", artifact_id)
        elif a["type"] == "mock_exam":
            r = create.build_mock_exam(self.ctx, {"track_id": track_id})
            new = self.store.get("artifacts", r["mock_exam"]) if r.get("mock_exam") else None
        elif a["type"] == "lesson":
            node = next((n for n in self.store.list("tutorial", track_id=track_id) if n.get("artifact_id") == artifact_id), None)
            if node:
                new = create.build_lesson(self.ctx, track_id, node)
                if new:
                    self.store.delete("artifacts", artifact_id)
        if new is None:
            raise Conflict("Could not produce a better version from the course material.", code="REGENERATE_FAILED")
        return self.public_artifact(new)

    # ------------------------------------------------------------------ practice
    def attempt(self, owner_id: str, track_id: str, item_id: str, answer: Any, *, ms: int | None = None,
                help_level: int = 0) -> dict[str, Any]:
        self._track(owner_id, track_id)
        art, item, typ = self._find_item(track_id, item_id)
        if typ == "mock_exam":
            raise Locked("Mock exam answers are submitted together.", code="SUBMIT_MOCK_EXAM")
        if typ == "probe":
            raise Locked("Use the level check endpoints.", code="PROBE_ITEM")
        return teach.record_attempt(self.ctx, track_id, art, item, answer,
                                    context="lesson" if typ == "lesson" else "practice", ms=ms, help_level=help_level)

    def submit_mock(self, owner_id: str, artifact_id: str, answers: dict[str, Any], elapsed_s: int | None = None) -> dict[str, Any]:
        a = self.store.get("artifacts", artifact_id)
        if not a or a["owner_id"] != owner_id or a["type"] != "mock_exam":
            raise NotFound()
        if any(x.get("artifact_id") == artifact_id for x in self.store.list("attempts", track_id=a["track_id"])):
            raise Conflict("This mock exam was already submitted. Generate a new one.", code="ALREADY_SUBMITTED")
        parts_out, total, got = [], 0.0, 0.0
        for p in a["content"]["parts"]:
            pg = 0.0
            items_out = []
            for it in p["items"]:
                r = teach.record_attempt(self.ctx, a["track_id"], a, it, answers.get(it["id"]), context="mock",
                                         ms=None, help_level=0)
                pts = it.get("points", 1.0)
                pg += r["score"] * pts
                items_out.append({"item_id": it["id"], "score": r["score"], "points": pts, "feedback": r["feedback"],
                                  "solution": teach._solution(it)})   # solutions after submission
            total += p["points"]
            got += pg
            parts_out.append({"title": p["title"], "points": p["points"], "score": round(pg, 2), "items": items_out})
        scale = a["content"].get("total_points") or total or 20
        result = {"score": round(got, 2), "out_of": round(total, 2), "grade_20": round(20 * got / (total or 1), 1),
                  "parts": parts_out, "elapsed_s": elapsed_s, "duration_min": a["content"].get("duration_min"),
                  "scale": scale}
        a.setdefault("verification", {})["submission"] = {"score": result["score"], "out_of": result["out_of"],
                                                           "at": now_iso()}
        self.store.put("artifacts", a)
        return result

    def new_mock_exam(self, owner_id: str, track_id: str) -> dict[str, Any]:
        self._track(owner_id, track_id)
        r = create.build_mock_exam(self.ctx, {"track_id": track_id})
        if not r.get("mock_exam"):
            raise Conflict("Not enough course material for a mock exam.", code="MOCK_EXAM_FAILED")
        return self.public_artifact(self.store.get("artifacts", r["mock_exam"]))

    def help(self, owner_id: str, track_id: str, item_id: str, level: int) -> dict[str, Any]:
        self._track(owner_id, track_id)
        art, item, typ = self._find_item(track_id, item_id)
        no_help = typ in ("mock_exam", "probe") or art["content"].get("no_help")
        try:
            return teach.help_for(self.ctx, track_id, item, max(1, min(4, level)),
                                  context="mock" if no_help else "practice")
        except teach.PolicyBlocked as e:
            raise Locked(e.message, code=e.code) from None

    def ask(self, owner_id: str, track_id: str, question: str, *, mode: str = "study", item_id: str | None = None) -> dict[str, Any]:
        self._track(owner_id, track_id)
        item = self._find_item(track_id, item_id)[1] if item_id else None
        try:
            return teach.ask(self.ctx, track_id, question, mode=mode, active_item=item)
        except teach.PolicyBlocked as e:
            raise Locked(e.message, code=e.code) from None

    # ------------------------------------------------------------------ Valley 2
    def tutorial(self, owner_id: str, track_id: str) -> dict[str, Any]:
        self._track(owner_id, track_id)
        nodes = sorted(self.store.list("tutorial", track_id=track_id), key=lambda n: n["ord"])
        learner = self.ctx.learner(track_id)
        out = []
        for n in nodes:
            m = [learner.get(k, {}).get("p_mastery", 0.0) for k in n["concept_keys"]]
            out.append({**n, "mastery": round(sum(m) / len(m), 3) if m else 0.0})
        return {"nodes": out}

    def lesson(self, owner_id: str, track_id: str, slug: str) -> dict[str, Any]:
        self._track(owner_id, track_id)
        node = next((n for n in self.store.list("tutorial", track_id=track_id) if n["slug"] == slug), None)
        if node is None:
            raise NotFound()
        if node["status"] == "locked":
            raise Locked("Finish the previous page first.", code="PAGE_LOCKED")
        a = self.store.get("artifacts", node["artifact_id"]) if node.get("artifact_id") else None
        if a is None:
            if node["kind"] == "page":
                a = create.build_lesson(self.ctx, track_id, node)
            elif node["kind"] in ("quiz", "project", "checkpoint"):
                a = create.build_chapter_quiz(self.ctx, track_id, node)
            if a is None:
                raise Conflict("Could not write this page from the course material.", code="LESSON_FAILED")
        return {"node": node, "artifact": self.public_artifact(a)}

    def complete_page(self, owner_id: str, track_id: str, slug: str) -> dict[str, Any]:
        self._track(owner_id, track_id)
        node = next((n for n in self.store.list("tutorial", track_id=track_id) if n["slug"] == slug), None)
        if node is None:
            raise NotFound()
        if node["status"] == "locked":
            raise Locked("Finish the previous page first.", code="PAGE_LOCKED")
        if node["kind"] in ("quiz", "project", "checkpoint"):
            atts = [x for x in self.store.list("attempts", track_id=track_id)
                    if node.get("artifact_id") and x.get("artifact_id") == node["artifact_id"]]
            if node["kind"] == "checkpoint":   # the skill is earned without help
                atts = [x for x in atts if x["help_level"] <= 1]
            mark = 0.8 if node["kind"] == "checkpoint" else 0.7
            score = sum(x["score"] for x in atts) / len(atts) if atts else 0.0
            if score < mark:
                raise Locked(f"Score at least {int(mark * 100)} % to finish this step.", code="PASS_MARK")
        nxt = plan.unlock_next(self.ctx, track_id, slug)
        result = {"next": nxt}
        if node["kind"] == "checkpoint":
            result["skill"] = self.report(owner_id, track_id)
        if nxt and nxt["kind"] == "page" and not nxt.get("artifact_id"):
            self._prefetch(track_id, nxt)
        return result

    def _prefetch(self, track_id: str, node: dict[str, Any]) -> None:
        if self.job_mode == "thread" and self._pool:
            self._pool.submit(create.build_lesson, self.ctx, track_id, node)

    # ------------------------------------------------------------------ reporting
    def report(self, owner_id: str, track_id: str) -> dict[str, Any]:
        t = self._track(owner_id, track_id)
        learner = self.ctx.learner(track_id)
        concepts = self.ctx.concepts(track_id)
        atts = self.store.list("attempts", track_id=track_id)
        rows, num, den = [], 0.0, 0.0
        for c in concepts:
            r = learner.get(c["key"], {})
            p = r.get("p_mastery", 0.0)
            ca = [a for a in atts if a["concept_key"] == c["key"] and a["context"] != "probe"]
            indep = [a for a in ca if a["help_level"] <= 1]
            rows.append({"concept_key": c["key"], "title": c["title"], "chapter": c["chapter"], "p_mastery": p,
                         "elo": r.get("elo"), "attempts": len(ca), "independent_success": round(
                    sum(1 for a in indep if a["correct"]) / len(indep), 2) if indep else None,
                         "exam_weight": c["exam_weight"], "next_review": r.get("next_review"),
                         "mastered": p >= self.ctx.settings.mastery_threshold})
            num += c["exam_weight"] * p
            den += c["exam_weight"]
        chapters: dict[str, list[float]] = {}
        for r in rows:
            chapters.setdefault(r["chapter"], []).append(r["p_mastery"])
        mocks = [a["verification"]["submission"] for a in self.store.list("artifacts", track_id=track_id)
                 if a["type"] == "mock_exam" and a.get("verification", {}).get("submission")]
        weak = sorted([r for r in rows if not r["mastered"]], key=lambda r: -(r["exam_weight"] * (1 - r["p_mastery"])))[:5]
        return {"track_id": track_id, "valley": t["valley"], "readiness": round(num / den, 3) if den else 0.0,
                "concepts": rows, "chapters": {k: round(sum(v) / len(v), 3) for k, v in chapters.items()},
                "mock_exams": mocks, "focus_next": weak, "level": {"declared": t.get("declared_level"),
                                                                    "measured": t.get("measured_level"),
                                                                    "verdict": t.get("level_verdict")}}


def _has(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:  # noqa: BLE001
        return False


def build_service(settings: TutorSettings | None = None, *, store=None, emit=None, enqueue=None,
                  search=None, fetcher=None) -> TutorService:
    s = settings or get_settings()
    if store is None:
        if s.store_backend == "sqlalchemy":
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            from .store.sqlalchemy_store import SQLAlchemyStore

            engine = create_engine(s.database_url, pool_pre_ping=True)
            store = SQLAlchemyStore(sessionmaker(bind=engine, expire_on_commit=False))
            store.create_all(engine)
            store.blob = _LocalBlob(s.blob_dir)  # blobs on local disk unless a blob backend is passed
        else:
            from .store.sqlite import SQLiteStore

            store = SQLiteStore(s.sqlite_path, s.blob_dir)
    holder: dict[str, TutorService] = {}
    llm = build_llm(s, meter=lambda tid, n: holder["svc"]._meter(tid, n) if "svc" in holder else None)
    embedder = build_embedder(s)
    kb = KnowledgeBase(store, embedder, build_reranker(s))
    ctx = Ctx(settings=s, store=store, llm=llm, kb=kb, search=search or build_search(s),
              fetcher=fetcher or PoliteFetcher(s), emit=emit)
    svc = TutorService(ctx, job_mode=s.job_mode, enqueue=enqueue)
    holder["svc"] = svc
    return svc


class _LocalBlob:
    def __init__(self, root: str):
        from pathlib import Path

        self.root = Path(root)

    def put(self, key: str, data: bytes, content_type: str = "") -> None:
        p = self.root / key.replace("..", "_")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return (self.root / key.replace("..", "_")).read_bytes()

    def delete(self, key: str) -> None:
        p = self.root / key.replace("..", "_")
        if p.exists():
            p.unlink()
