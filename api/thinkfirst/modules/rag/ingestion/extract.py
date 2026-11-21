"""Pure extraction helpers: file validation, text extraction, chunking, demo embeddings, heuristic scope.

The heuristic scope parser is the *labeled* demo adapter for the ``propose_concepts`` prompt: it reads
numbered headings/objectives/prerequisites/exercises. It is deterministic and never invents content.
"""

from __future__ import annotations

import hashlib
import io
import math
import re
from dataclasses import dataclass, field

SUPPORTED = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
    "text/markdown": "md",
}
EXT_KIND = {".pdf": "pdf", ".pptx": "pptx", ".txt": "txt", ".md": "md"}


class ExtractionError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def detect_kind(filename: str, mime: str) -> str | None:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXT_KIND.get(ext) or SUPPORTED.get(mime)


def extract_pages(data: bytes, kind: str, max_pages: int) -> list[str]:
    if kind == "pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError("UNREADABLE_FILE") from exc
        if reader.is_encrypted:
            raise ExtractionError("ENCRYPTED_FILE")
        if len(reader.pages) > max_pages:
            raise ExtractionError("TOO_MANY_PAGES")
        pages = [(p.extract_text() or "") for p in reader.pages]
    elif kind == "pptx":
        from pptx import Presentation

        try:
            prs = Presentation(io.BytesIO(data))
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError("UNREADABLE_FILE") from exc
        pages = []
        for slide in prs.slides:
            texts = [sh.text_frame.text for sh in slide.shapes if getattr(sh, "has_text_frame", False)]
            pages.append("\n".join(texts))
        if len(pages) > max_pages:
            raise ExtractionError("TOO_MANY_PAGES")
    elif kind in ("txt", "md"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExtractionError("UNREADABLE_FILE") from exc
        pages = split_text_pages(text)
        if len(pages) > max_pages:
            raise ExtractionError("TOO_MANY_PAGES")
    else:
        raise ExtractionError("UNSUPPORTED_TYPE")
    pages = [normalize(p) for p in pages]
    if not any(p.strip() for p in pages):
        raise ExtractionError("NO_TEXT")  # scanned PDFs need OCR (Next)
    return pages


_PAGE_MARK = re.compile(r"^\s*-{3,}\s*page\s*\d*\s*-{3,}\s*$", re.I | re.M)


def split_text_pages(text: str) -> list[str]:
    if "\f" in text:
        return text.split("\f")
    if _PAGE_MARK.search(text):
        return [p for p in _PAGE_MARK.split(text) if p.strip()]
    pages, buf = [], []
    size = 0
    for para in text.split("\n\n"):
        buf.append(para)
        size += len(para)
        if size > 3000:
            pages.append("\n\n".join(buf))
            buf, size = [], 0
    if buf:
        pages.append("\n\n".join(buf))
    return pages


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace(" ", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


@dataclass
class Chunk:
    page_no: int
    start: int
    end: int
    text: str


def chunk_pages(pages: list[str], target: int = 600) -> list[Chunk]:
    chunks: list[Chunk] = []
    for idx, page in enumerate(pages, start=1):
        start = 0
        while start < len(page):
            end = min(len(page), start + target)
            if end < len(page):
                cut = page.rfind("\n", start, end)
                if cut > start + target // 3:
                    end = cut
            piece = page[start:end].strip()
            if piece:
                chunks.append(Chunk(idx, start, end, piece))
            start = end
    return chunks


_WORD = re.compile(r"[\w']+", re.U)


def demo_embed(text: str, dim: int = 256) -> list[float]:
    """Labeled demo embedding: hashed bag-of-words (no embedding service configured)."""
    vec = [0.0] * dim
    for w in _WORD.findall(text.lower()):
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


# ---- heuristic scope (demo adapter for propose_concepts) ----

_UNIT = re.compile(r"^\s*(?:Unit|Chapter|Chapitre)\s+(\d+)\s*[:.\-–]\s*(.+?)\s*$", re.I)
_CONCEPT = re.compile(r"^\s*(\d+\.\d+)\s+([^\d\s].{2,120}?)\s*$")
_FOUNDATION = re.compile(r"^\s*(F\d+)\s+(.{3,120}?)\s*$")
_MD_HEADING = re.compile(r"^\s*#{1,3}\s+(.{3,120}?)\s*$")
_OBJECTIVE = re.compile(r"^\s*Objective\s*:\s*(.+?)\s*$", re.I)
_PREREQ = re.compile(r"^\s*Prerequisites?\s*:\s*(.+?)\s*$", re.I)
_EXERCISE = re.compile(r"^\s*Exercise\b[^:]*:\s*(.+?)\s*$", re.I)
_EXPAND = re.compile(r"^(Expand|Simplify)\s+(.+?)\.?\s*$", re.I)


@dataclass
class ProposedConcept:
    key: str
    title: str
    unit_no: int
    unit_title: str
    page: int
    span_start: int
    span_end: int = 0
    objective: str = ""
    prerequisites: list[str] = field(default_factory=list)
    is_foundation: bool = False
    uncertain: bool = False
    quote: str = ""


@dataclass
class ProposedItem:
    concept_key: str | None
    kind: str
    prompt: str
    expression: str | None
    page: int


def heuristic_scope(pages: list[str]) -> tuple[list[ProposedConcept], list[ProposedItem]]:
    concepts: list[ProposedConcept] = []
    items: list[ProposedItem] = []
    unit_no, unit_title = 1, "Unit 1"
    current: ProposedConcept | None = None
    md_mode = not any(_CONCEPT.match(line) for p in pages for line in p.split("\n"))
    for page_no, page in enumerate(pages, start=1):
        offset = 0
        for line in page.split("\n"):
            line_start = offset
            offset += len(line) + 1
            if m := _UNIT.match(line):
                unit_no, unit_title = int(m.group(1)), m.group(2)
                continue
            m_c = _CONCEPT.match(line)
            m_f = _FOUNDATION.match(line)
            m_h = _MD_HEADING.match(line) if md_mode else None
            if m_c or m_f or m_h:
                if current:
                    current.span_end = current.span_end or line_start
                if m_c:
                    key, title, foundation = m_c.group(1), m_c.group(2), False
                elif m_f:
                    key, title, foundation = m_f.group(1), m_f.group(2), True
                else:
                    key, title, foundation = f"H{len(concepts) + 1}", m_h.group(1), False  # type: ignore[union-attr]
                current = ProposedConcept(key=key, title=title.strip(" .:"), unit_no=unit_no,
                                          unit_title=unit_title, page=page_no, span_start=line_start,
                                          is_foundation=foundation, uncertain=m_h is not None)
                concepts.append(current)
                continue
            if current is None:
                continue
            if m := _OBJECTIVE.match(line):
                current.objective = m.group(1)
            elif m := _PREREQ.match(line):
                current.prerequisites = [k.strip() for k in re.split(r"[,;]", m.group(1)) if k.strip()]
            elif m := _EXERCISE.match(line):
                body = m.group(1)
                em = _EXPAND.match(body)
                kind = em.group(1).lower() if em else "open"
                items.append(ProposedItem(current.key, kind, body, em.group(2) if em else None, page_no))
            elif not current.quote and len(line.strip()) > 30:
                current.quote = line.strip()[:240]
        if current and current.page == page_no:
            current.span_end = current.span_end or len(page)
    for c in concepts:
        if not c.objective:
            c.uncertain = True
    return concepts, items
