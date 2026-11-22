"""Group 1 · Understand: ingest uploads, extract the concept graph, fingerprint the course, fill gaps from the web."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..fingerprint import build_fingerprint
from ..ingestion.chunker import chunk_document
from ..ingestion.parsers import ParsedDoc, ParsedPage, UnsupportedFormat, parse
from ..research.policy import domain_of
from ..research.scraper import ScrapeRefused
from ..schemas import Blueprint, new_id, now_iso
from ..textutil import detect_language, norm, overlap_ratio, slugify, tokens
from .base import Ctx

log = logging.getLogger("tutor.understand")
NUMBER_PREFIX = re.compile(r"^\s*(?:[IVX]+|\d+(?:\.\d+)*|[a-h])\s*[.)\-–:]\s*|^\s*\d+-(?=[a-z])")


def _parsed_key(doc_id: str) -> str:
    return f"parsed/{doc_id}.json"


def load_parsed(ctx: Ctx, doc_id: str) -> ParsedDoc | None:
    try:
        raw = json.loads(ctx.store.get_blob(_parsed_key(doc_id)).decode())
    except Exception:  # noqa: BLE001
        return None
    return ParsedDoc([ParsedPage(p["number"], p["text"], [tuple(h) for h in p["headings"]], p["ocr"]) for p in raw["pages"]],
                     title=raw.get("title", ""))


# ------------------------------------------------------------------------------------------- ingest
def ingest_documents(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    track_id = state["track_id"]
    track = ctx.track(track_id)
    ctx.save_track(track, status="ingesting")
    docs = ctx.store.list("documents", track_id=track_id)
    indexed, failed, langs = 0, [], []
    for d in docs:
        if d["status"] == "indexed":
            indexed += 1
            continue
        try:
            data = ctx.store.get_blob(d["blob_key"])
            parsed = parse(d["filename"], data)
        except UnsupportedFormat as e:
            d.update(status="failed", error=f"unsupported:{e}")
            ctx.store.put("documents", d)
            failed.append(d["filename"])
            continue
        ctx.store.put_blob(_parsed_key(d["id"]), json.dumps({"title": parsed.title, "pages": [
            {"number": p.number, "text": p.text, "headings": p.headings, "ocr": p.ocr} for p in parsed.pages]},
            ensure_ascii=False).encode())
        excerpt = parsed.text[:2500]
        lang = detect_language(parsed.text)
        langs.append(lang)
        cls = ctx.llm_json("classify_document", {"filename": d["filename"], "excerpt": excerpt, "language": lang},
                           track_id, tier="small")
        doc_type = cls.get("doc_type") if cls.get("doc_type") in (
            "course", "exercises", "past_exam", "solutions", "slides", "notes", "other") else "course"
        raws = chunk_document(parsed, target_words=ctx.settings.chunk_words, overlap=ctx.settings.chunk_overlap)
        chunks = [{"id": new_id(), "track_id": track_id, "owner_id": d["owner_id"], "document_id": d["id"],
                   "web_source_id": None, "origin": "course", "doc_type": doc_type, "text": r.text, "page": r.page,
                   "section": r.section, "ord": r.ord, "concept_ids": []} for r in raws]
        ctx.kb.add(chunks)
        d.update(status="indexed", doc_type=doc_type, title=cls.get("title") or parsed.title or d["filename"],
                 pages=len(parsed.pages), ocr_pages=parsed.ocr_pages, error=None)
        ctx.store.put("documents", d)
        indexed += 1
    if langs:
        lang = max(set(langs), key=langs.count)
        ctx.save_track(ctx.track(track_id), language=lang)
    if indexed == 0:
        raise RuntimeError("NO_READABLE_DOCUMENT")
    ctx.event("content.indexed", {"track_id": track_id, "documents": indexed})
    return {"documents_indexed": indexed, "documents_failed": failed}


# ------------------------------------------------------------------------------------------- concepts
def build_concepts(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    track_id = state["track_id"]
    track = ctx.track(track_id)
    docs = [d for d in ctx.store.list("documents", track_id=track_id) if d["status"] == "indexed"]
    # course documents first: their headings define the structure
    docs.sort(key=lambda d: {"course": 0, "slides": 1, "notes": 2}.get(d["doc_type"], 3))
    outline, excerpts = [], []
    for d in docs:
        p = load_parsed(ctx, d["id"])
        if p is None:
            continue
        if d["doc_type"] in ("course", "slides", "notes", "other"):
            outline += p.outline
        excerpts += [pg.text[:1200] for pg in p.pages[:60]]
    out = ctx.llm_json("extract_concepts", {"outline": outline[:300], "excerpts": excerpts[:80],
                                            "language": track["language"], "subject": track.get("subject") or track["title"]},
                       track_id, tier="small")
    seen: dict[str, dict[str, Any]] = {}
    for i, c in enumerate(out.get("concepts", [])):
        c["title"] = NUMBER_PREFIX.sub("", c.get("title") or "").strip()
        key = slugify(NUMBER_PREFIX.sub("", c.get("key") or "") or c["title"] or f"concept-{i}")
        if key in seen or not c.get("title"):
            continue
        seen[key] = {"id": f"{track_id}:{key}", "track_id": track_id, "owner_id": track["owner_id"], "key": key,
                     "title": c["title"][:120], "chapter": (c.get("chapter") or track.get("subject") or "")[:120],
                     "summary": c.get("summary", "")[:400], "keywords": [k for k in c.get("keywords", []) if k][:8],
                     "prerequisites": [slugify(p) for p in c.get("prerequisites", []) if p], "exam_weight": 1.0,
                     "coverage": 0.0, "ord": i}
    for c in seen.values():
        c["prerequisites"] = [p for p in c["prerequisites"] if p in seen and p != c["key"]]
    concepts = list(seen.values())
    _tag_chunks_and_coverage(ctx, track_id, concepts)
    ctx.store.put_many("concepts", concepts)
    chapters = []
    for c in concepts:
        if c["chapter"] not in chapters:
            chapters.append(c["chapter"])
    ctx.save_track(ctx.track(track_id), stats={**track.get("stats", {}), "concepts": len(concepts), "chapters": chapters})
    ctx.event("graph.built", {"track_id": track_id, "concepts": len(concepts)})
    return {"concepts": len(concepts)}


def _tag_chunks_and_coverage(ctx: Ctx, track_id: str, concepts: list[dict[str, Any]], origin: str | None = "course") -> None:
    chunks = {c["id"]: c for c in ctx.kb.chunks(track_id)}
    for c in concepts:
        q = " ".join([c["title"]] + c.get("keywords", []))
        hits = ctx.kb.search(track_id, q, k=6, origin=origin)
        terms = set(tokens(q))
        strong = 0
        for h in hits:
            ov = len(terms & set(tokens(h.chunk["text"] + " " + h.chunk.get("section", "")))) / max(1, len(terms))
            if ov >= 0.5 or norm(c["title"]) in norm(h.chunk.get("section", "")):
                strong += 1
                ch = chunks.get(h.chunk["id"])
                if ch is not None and c["key"] not in ch["concept_ids"]:
                    ch["concept_ids"].append(c["key"])
        c["coverage"] = round(min(1.0, strong / 3), 2)
    ctx.store.put_many("chunks", list(chunks.values()))
    ctx.kb.invalidate(track_id)


# ------------------------------------------------------------------------------------------- fingerprint
def build_course_fingerprint(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    track_id = state["track_id"]
    track = ctx.track(track_id)
    docs = [d for d in ctx.store.list("documents", track_id=track_id) if d["status"] == "indexed"]
    texts = {}
    for d in docs:
        p = load_parsed(ctx, d["id"])
        if p:
            texts[d["id"]] = p.text
    fp = build_fingerprint(track_id, track["owner_id"], docs, texts, track["language"])
    concepts = ctx.concepts(track_id)
    exams = [d for d in docs if d["doc_type"] == "past_exam"]
    if exams:
        bp_raw = ctx.llm_json("extract_blueprint", {
            "exam_text": "\n\n".join(texts.get(d["id"], "") for d in exams)[:20000],
            "concepts": [{"key": c["key"], "title": c["title"], "keywords": c["keywords"]} for c in concepts]},
            track_id, tier="small")
        bp = Blueprint.model_validate({**bp_raw, "source_document_ids": [d["id"] for d in exams]}).model_dump()
        _map_blueprint_concepts(ctx, track_id, bp, concepts)
    else:
        bp = _inferred_blueprint(fp, concepts, track.get("chapters") or [])
    fp["blueprint"] = bp
    _apply_exam_weights(concepts, bp)
    ctx.store.put_many("concepts", concepts)
    ctx.store.put("fingerprints", fp)
    ctx.profile(track_id, refresh=True)
    return {"fingerprint": True, "blueprint_inferred": bp.get("inferred", False)}


def _map_blueprint_concepts(ctx: Ctx, track_id: str, bp: dict[str, Any], concepts: list[dict[str, Any]]) -> None:
    keys = {c["key"] for c in concepts}
    for part in bp["parts"]:
        part["concept_keys"] = [k for k in part.get("concept_keys", []) if k in keys]
        if not part["concept_keys"]:  # match by text of the part title
            hits = [c["key"] for c in concepts if overlap_ratio(c["title"], part["title"]) > 0.5]
            part["concept_keys"] = hits[:4]


def _inferred_blueprint(fp: dict[str, Any], concepts: list[dict[str, Any]], scope: list[str]) -> dict[str, Any]:
    """No past exam: a 20-point, 2-hour exam shaped like the course's own exercise types."""
    chapters = []
    for c in concepts:
        if (not scope or c["chapter"] in scope) and c["chapter"] not in chapters:
            chapters.append(c["chapter"])
    chapters = chapters[:4] or ["Cours"]
    qtypes = sorted((fp.get("question_types") or {"calculation": 1}).items(), key=lambda x: -x[1])
    main = [q for q, _ in qtypes[:2]] or ["calculation"]
    pts = round(20 / len(chapters), 1)
    parts = [{"title": ch, "points": pts, "question_types": main,
              "concept_keys": [c["key"] for c in concepts if c["chapter"] == ch][:6], "count": 3} for ch in chapters]
    return {"duration_min": 120, "total_points": 20.0, "parts": parts, "source_document_ids": [], "inferred": True}


def _apply_exam_weights(concepts: list[dict[str, Any]], bp: dict[str, Any]) -> None:
    total = sum(p.get("points") or 0 for p in bp["parts"]) or len(bp["parts"]) or 1
    w: dict[str, float] = {}
    for p in bp["parts"]:
        ks = p.get("concept_keys") or []
        for k in ks:
            w[k] = w.get(k, 0.0) + ((p.get("points") or 1) / total) / len(ks)
    top = max(w.values(), default=1.0) or 1.0
    for c in concepts:
        # concepts absent from past exams still matter a little (they may come up)
        c["exam_weight"] = round(0.25 + 0.75 * (w.get(c["key"], 0.0) / top), 3)


# ------------------------------------------------------------------------------------------- research
def research_gaps(ctx: Ctx, state: dict[str, Any]) -> dict[str, Any]:
    track_id = state["track_id"]
    track = ctx.track(track_id)
    if not (track.get("allow_web") and ctx.settings.web_research and ctx.search and ctx.fetcher):
        return {"web_pages": 0, "research": "off"}
    concepts = ctx.concepts(track_id)
    gaps = [c for c in sorted(concepts, key=lambda c: (c["coverage"], -c["exam_weight"])) if c["coverage"] < 0.34][:6]
    if not gaps:
        return {"web_pages": 0, "research": "no_gaps"}
    already = ctx.store.list("web_sources", track_id=track_id)
    budget = ctx.settings.max_web_pages_per_track - len([w for w in already if w["status"] == "indexed"])
    if budget <= 0:
        return {"web_pages": 0, "research": "budget"}
    q = ctx.llm_json("research_queries", {"gaps": [{"key": g["key"], "title": g["title"]} for g in gaps],
                                          "language": track["language"], "subject": track.get("subject") or track["title"]},
                     track_id, tier="small")
    seen_urls = {w["url"] for w in already}
    added, new_chunks = 0, []
    for entry in q.get("queries", [])[:10]:
        if added >= budget:
            break
        try:
            results = ctx.search.search(entry["query"], k=5, lang=track["language"],
                                        domains=None if ctx.settings.allow_any_domain else ctx.settings.allowed_domains)
        except Exception as e:  # noqa: BLE001
            log.warning("search failed: %s", e)
            continue
        for r in results:
            if added >= budget or r.url in seen_urls:
                continue
            seen_urls.add(r.url)
            ws = {"id": new_id(), "track_id": track_id, "owner_id": track["owner_id"], "url": r.url,
                  "domain": domain_of(r.url), "title": r.title, "licence": "unknown", "query": entry["query"],
                  "concept_key": entry.get("concept_key"), "sha256": "", "status": "fetched", "reason": None,
                  "fetched_at": now_iso()}
            try:
                page = ctx.fetcher.fetch(r.url)
            except ScrapeRefused as e:
                ws.update(status="skipped", reason=e.reason)
                ctx.store.put("web_sources", ws)
                continue
            except Exception as e:  # noqa: BLE001
                ws.update(status="failed", reason=type(e).__name__)
                ctx.store.put("web_sources", ws)
                continue
            ws.update(title=page.title or r.title, licence=page.licence, sha256=page.sha256, url=page.final_url)
            parsed = ParsedDoc([ParsedPage(1, page.text, page.headings)], title=page.title)
            raws = chunk_document(parsed, target_words=ctx.settings.chunk_words, overlap=ctx.settings.chunk_overlap)
            ck = entry.get("concept_key")
            chunks = [{"id": new_id(), "track_id": track_id, "owner_id": track["owner_id"], "document_id": None,
                       "web_source_id": ws["id"], "origin": "web", "doc_type": "web", "text": rc.text, "page": None,
                       "section": rc.section or page.title, "ord": rc.ord, "concept_ids": [ck] if ck else []}
                      for rc in raws[:40]]
            new_chunks += chunks
            ws["status"] = "indexed"
            ctx.store.put("web_sources", ws)
            added += 1
    if new_chunks:
        ctx.kb.add(new_chunks)
        for g in gaps:  # coverage now counts web material too, but at a discount
            hits = ctx.kb.search(track_id, g["title"] + " " + " ".join(g["keywords"]), k=4, origin="web")
            g["coverage"] = round(min(1.0, g["coverage"] + 0.2 * len(hits)), 2)
        ctx.store.put_many("concepts", gaps)
    return {"web_pages": added, "research": "done"}


def is_reference_section(title: str) -> bool:
    return bool(re.match(r"^(références|bibliographie|references|sources)$", title.strip(), re.I))
