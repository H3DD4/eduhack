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
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/html": "html",
}
EXT_KIND = {".pdf": "pdf", ".pptx": "pptx", ".docx": "docx", ".txt": "txt", ".md": "md", ".markdown": "md",
            ".html": "html", ".htm": "html"}


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
    elif kind == "html":  # saved web page / exported notes
        pages = html_pages(data.decode("utf-8", errors="replace"))
        if len(pages) > max_pages:
            raise ExtractionError("TOO_MANY_PAGES")
    elif kind == "docx":
        pages = docx_pages(data)
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
    if kind == "pdf" and not any(p.strip() for p in pages):
        pages = [normalize(p) for p in _pdf_fallback(data, max_pages)]
    if not any(p.strip() for p in pages):
        raise ExtractionError("NO_TEXT")  # scanned PDF and no OCR engine installed
    return pages


_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "pre", "table"}


def html_pages(html: str) -> list[str]:
    """Agentic Tutor parser (main text, headings, MathJax kept) when BeautifulSoup is installed; otherwise the
    standard-library parser: text of the page, one line per block element, scripts/styles/navigation dropped."""
    try:
        from tutor.ingestion.parsers import parse_html

        return [p.text for p in parse_html(html).pages]
    except ImportError:
        pass
    from html.parser import HTMLParser

    class _Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.out, self.skip = [], 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "footer", "header", "noscript"):
                self.skip += 1
            elif tag in _BLOCK_TAGS:
                self.out.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "footer", "header", "noscript"):
                self.skip = max(0, self.skip - 1)
            elif tag in _BLOCK_TAGS:
                self.out.append("\n")

        def handle_data(self, d):
            if not self.skip:
                self.out.append(d)

    t = _Text()
    try:
        t.feed(html)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("UNREADABLE_FILE") from exc
    text = "\n".join(line.strip() for line in "".join(t.out).split("\n") if line.strip())
    return split_text_pages(text)


def _pdf_fallback(data: bytes, max_pages: int) -> list[str]:
    """No text layer: the Agentic Tutor PDF parser tries pdfplumber, then OCR (pypdfium2 + pytesseract) when those
    optional packages are installed. Returns [] when nothing more can be read."""
    try:
        from tutor.ingestion.parsers import parse_pdf

        return [p.text for p in parse_pdf(data, max_pages=max_pages).pages]
    except Exception:  # noqa: BLE001 - optional dependencies missing or unreadable file
        return []


def heading_level(line: str) -> int | None:
    """Course heading detector from the Agentic Tutor parser: 1 = chapter/unit/part (also roman numerals and
    upper-case titles), 2 = numbered section "2. ...", 3 = "1.2 ..." sub-section or a labelled block such as
    Définition / Théorème / Méthode."""
    from tutor.ingestion.parsers import heading_level as _hl

    return _hl(line)


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_pages(data: bytes) -> list[str]:
    """Word .docx without extra dependencies: read word/document.xml. Paragraphs keep their order; headings become
    lines of their own; tables become 'cell | cell' rows. Explicit page breaks split pages; otherwise ~3000-char
    pages (Word does not store layout pages)."""
    import zipfile
    from xml.etree import ElementTree

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ExtractionError("UNREADABLE_FILE") from exc
    body = root.find(f"{_W}body")
    if body is None:
        raise ExtractionError("UNREADABLE_FILE")

    def para_text(p) -> tuple[str, bool]:
        out, brk = [], False
        for node in p.iter():
            if node.tag == f"{_W}t" and node.text:
                out.append(node.text)
            elif node.tag == f"{_W}tab":
                out.append("\t")
            elif node.tag == f"{_W}br":
                if node.get(f"{_W}type") == "page":
                    brk = True
                else:
                    out.append("\n")
        return "".join(out), brk

    pages, buf, size = [], [], 0
    for el in body:
        if el.tag == f"{_W}p":
            text, brk = para_text(el)
        elif el.tag == f"{_W}tbl":
            rows = []
            for tr in el.iter(f"{_W}tr"):
                cells = [" ".join(t.text or "" for t in tc.iter(f"{_W}t")).strip() for tc in tr.iter(f"{_W}tc")]
                rows.append(" | ".join(cells))
            text, brk = "\n".join(rows), False
        else:
            continue
        if text.strip():
            buf.append(text)
            size += len(text)
        if brk or size > 3000:
            if buf:
                pages.append("\n\n".join(buf))
            buf, size = [], 0
    if buf:
        pages.append("\n\n".join(buf))
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


def _heading_offsets(page: str) -> list[int]:
    """Character offsets of chapter/section heading lines (levels 1-2) on a page."""
    out, pos = [], 0
    for line in page.split("\n"):
        if pos > 0 and (heading_level(line) or 9) <= 2:
            out.append(pos)
        pos += len(line) + 1
    return out


def chunk_pages(pages: list[str], target: int = 600) -> list[Chunk]:
    """~600-character chunks with exact page offsets (citations quote them). Heading-aware (Agentic Tutor chunker
    rule): a chunk never crosses a chapter/section heading, so a section's text is retrieved together."""
    chunks: list[Chunk] = []
    for idx, page in enumerate(pages, start=1):
        bounds = _heading_offsets(page) + [len(page)]
        start = 0
        for stop in bounds:
            while start < stop:
                end = min(stop, start + target)
                if end < stop:
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


def outline_scope(pages: list[str]) -> list[ProposedConcept]:
    """Roadmap from the course's own headings (Agentic Tutor heading rules), for courses that do not use the
    "1.2 Title" format: level-1 headings become units, level-2/3 headings become concepts, in course order, each
    citing its page and the first sentence after it. Nothing is invented; every concept is marked uncertain."""
    concepts: list[ProposedConcept] = []
    unit_no, unit_title = 1, "Unit 1"
    seen_unit = False
    for page_no, page in enumerate(pages, start=1):
        offset = 0
        lines = page.split("\n")
        for i, line in enumerate(lines):
            start = offset
            offset += len(line) + 1
            lvl = heading_level(line)
            if lvl is None:
                continue
            title = line.strip().strip(" .:")[:120]
            if lvl == 1:
                if seen_unit or concepts:
                    unit_no += 1
                unit_title, seen_unit = title, True
                continue
            if any(c.title.lower() == title.lower() and c.unit_no == unit_no for c in concepts):
                continue
            follow = next((x.strip() for x in lines[i + 1:i + 6] if len(x.strip()) > 30 and heading_level(x) is None), "")
            n = sum(1 for c in concepts if c.unit_no == unit_no) + 1
            concepts.append(ProposedConcept(key=f"{unit_no}.{n}", title=title, unit_no=unit_no, unit_title=unit_title,
                                            page=page_no, span_start=start, span_end=start + len(line),
                                            objective=follow[:240], prerequisites=[f"{unit_no}.{n - 1}"] if n > 1 else [],
                                            uncertain=True, quote=follow[:240]))
    return concepts if len(concepts) >= 2 else []


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
