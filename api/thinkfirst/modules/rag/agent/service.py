"""Live resource agent (override §3.8). Collects ONLY content whose license permits storage/redistribution.

Sources implemented: Wikipedia (MediaWiki API; text under CC BY-SA 4.0 — stored with license, URL and
attribution, cited, and linked out). Nothing else is scraped: robots.txt is not a content license, and course
sites/videos are only ever linked (metadata), never copied. Only the topic text is sent (no identity).
"""

from __future__ import annotations

import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.modules.rag.library.models import LicensedContent, SharedChunk, SubjectResourceLink

log = logging.getLogger("thinkfirst.resources")
UA = {"User-Agent": "ThinkFirst/0.1 (educational prototype; open-licence content only)"}
WIKI_LICENSE = ("CC-BY-SA-4.0", "https://creativecommons.org/licenses/by-sa/4.0/")
_FR = re.compile(r"[éèêàùçôîâ]|\b(les|des|le|la|et|du|loi|théorème)\b", re.I)


def _lang(topic: str) -> str:
    return "fr" if _FR.search(topic) else "en"


def _wiki(lang: str, params: dict) -> dict:
    r = httpx.get(f"https://{lang}.wikipedia.org/w/api.php", params={"format": "json", "formatversion": 2, **params},
                  headers=UA, timeout=15)
    r.raise_for_status()
    return r.json()


def discover(db: Session, owner_id: str, subject_id: str, topic: str, limit: int = 3) -> list[LicensedContent]:
    """Find openly licensed reference text for a topic and link it (privately) to the subject. Best effort."""
    if not get_settings().resource_discovery:
        return []
    lang = _lang(topic)
    try:
        hits = _wiki(lang, {"action": "query", "list": "search", "srsearch": topic, "srlimit": limit}).get("query", {}).get("search", [])
        titles = [h["title"] for h in hits][:limit]
        if not titles:
            return []
        pages = _wiki(lang, {"action": "query", "prop": "extracts|info", "explaintext": 1, "exintro": 1,
                             "inprop": "url", "titles": "|".join(titles)}).get("query", {}).get("pages", [])
    except Exception as exc:  # noqa: BLE001 — metadata-only log
        log.info("resource discovery failed", extra={"error_code": type(exc).__name__})
        return []
    out = []
    for p in pages:
        text = (p.get("extract") or "").strip()
        url = p.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{p.get('title', '').replace(' ', '_')}"
        if len(text) < 200:
            continue
        item = db.scalar(select(LicensedContent).where(LicensedContent.source_url == url))
        if item is None:
            item = LicensedContent(title=p["title"][:300], source_url=url, license_id=WIKI_LICENSE[0], license_url=WIKI_LICENSE[1],
                                   attribution=f"Wikipedia contributors, “{p['title']}”, Wikipedia ({lang}). Text under CC BY-SA 4.0.",
                                   permits_storage=True, permits_redistribution=True, origin_label="unverified-source",
                                   language=lang, body=text[:12000], provider="wikipedia")
            db.add(item)
            db.flush()
            index_item(db, item)
        link(db, owner_id, subject_id, item, topic)
        out.append(item)
    db.flush()
    return out


def index_item(db: Session, item: LicensedContent) -> int:
    """Chunk + embed shared open content once; every later user reuses it (the library grows with use)."""
    from thinkfirst.modules.rag.service import embed

    if not item.body or db.scalar(select(SharedChunk.id).where(SharedChunk.licensed_content_id == item.id)):
        return 0
    paras = [p.strip() for p in item.body.split("\n") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) > 700 and buf:
            chunks.append(buf)
            buf = ""
        buf = f"{buf}\n{p}".strip()
    if buf:
        chunks.append(buf)
    for i, c in enumerate(chunks):
        db.add(SharedChunk(licensed_content_id=item.id, ord=i, text=c, embedding=embed(f"{item.title}. {c}")))
    db.flush()
    return len(chunks)


def link(db: Session, owner_id: str, subject_id: str, item: LicensedContent, query: str) -> None:
    if not db.scalar(select(SubjectResourceLink).where(SubjectResourceLink.owner_id == owner_id,
                                                       SubjectResourceLink.subject_id == subject_id,
                                                       SubjectResourceLink.licensed_content_id == item.id)):
        db.add(SubjectResourceLink(owner_id=owner_id, subject_id=subject_id, licensed_content_id=item.id, query=query[:300]))


def for_subject(db: Session, owner_id: str, subject_id: str) -> list[LicensedContent]:
    ids = db.scalars(select(SubjectResourceLink.licensed_content_id).where(SubjectResourceLink.owner_id == owner_id,
                                                                           SubjectResourceLink.subject_id == subject_id)).all()
    if not ids:
        return []
    return list(db.scalars(select(LicensedContent).where(LicensedContent.id.in_(ids))).all())


def best_excerpt(db: Session, owner_id: str, subject_id: str, query: str, max_chars: int = 3500) -> tuple[str, list[dict]]:
    """Pick the most relevant licensed text for a concept (keyword overlap) and return text + citations."""
    items = for_subject(db, owner_id, subject_id)
    words = {w for w in re.findall(r"\w{4,}", query.lower())}
    scored = sorted(items, key=lambda i: -len(words & set(re.findall(r"\w{4,}", (i.body or "").lower()))))
    text, cites = "", []
    for i in scored[:2]:
        if not i.body:
            continue
        chunk = i.body[: max_chars // 2]
        text += f"[{i.title}]\n{chunk}\n\n"
        cites.append(public(i))
    return text.strip(), cites


def public(i: LicensedContent) -> dict:
    return {"id": i.id, "title": i.title, "url": i.source_url, "license": i.license_id, "license_url": i.license_url,
            "attribution": i.attribution, "provider": i.provider, "origin": i.origin_label,
            "summary": (i.body or "")[:280] + ("…" if i.body and len(i.body) > 280 else "")}
