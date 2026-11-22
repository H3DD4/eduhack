"""Document parsers: PDF, DOCX, PPTX, TXT/MD, HTML and images, with OCR fallback for scanned pages.

Each parser returns a ParsedDoc of pages; each page has its text and the headings found on it
(level 1 = chapter, 2 = section, 3 = sub-section). Headings drive concept extraction and chunk sections.

Optional dependencies, used when present:
  pypdf (text layer) -> pdfplumber (fallback) -> pypdfium2 + pytesseract (OCR, scanned pages)
  python-docx, python-pptx, beautifulsoup4, Pillow + pytesseract (images)
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("tutor.ingestion")

MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown",
    ".html": "text/html", ".htm": "text/html",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
}
SUPPORTED = tuple(MIME_BY_EXT)


class UnsupportedFormat(Exception):
    pass


@dataclass
class ParsedPage:
    number: int
    text: str
    headings: list[tuple[int, str]] = field(default_factory=list)
    ocr: bool = False


@dataclass
class ParsedDoc:
    pages: list[ParsedPage]
    title: str = ""
    mime: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)

    @property
    def outline(self) -> list[dict]:
        return [{"level": lvl, "title": t, "page": p.number} for p in self.pages for lvl, t in p.headings]

    @property
    def ocr_pages(self) -> int:
        return sum(1 for p in self.pages if p.ocr)


def ext_of(filename: str) -> str:
    m = re.search(r"\.[A-Za-z0-9]+$", filename or "")
    return m.group(0).lower() if m else ""


def parse(filename: str, data: bytes, *, ocr_lang: str = "fra+eng", max_pages: int = 300) -> ParsedDoc:
    ext = ext_of(filename)
    if ext == ".pdf" or data[:5] == b"%PDF-":
        return parse_pdf(data, ocr_lang=ocr_lang, max_pages=max_pages)
    if ext == ".docx":
        return parse_docx(data)
    if ext == ".pptx":
        return parse_pptx(data)
    if ext in (".md", ".markdown", ".txt"):
        return parse_text(data.decode("utf-8", errors="replace"), markdown=ext != ".txt")
    if ext in (".html", ".htm"):
        return parse_html(data.decode("utf-8", errors="replace"))
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        return parse_image(data, ocr_lang=ocr_lang)
    raise UnsupportedFormat(ext or "unknown")


# ------------------------------------------------------------------------------------------ headings
_H1 = re.compile(r"^(chapitre|chapter|partie|part|module|unit[ée]?|le[cç]on|lesson)\b\s*[\dIVX]*", re.I)
_ROMAN = re.compile(r"^[IVX]{1,5}[.)\-–]\s+\S")
_NUM2 = re.compile(r"^\d{1,2}[.)]\s+\S")
_NUM3 = re.compile(r"^\d{1,2}\.\d{1,2}\.?\s+\S")
_LABEL = re.compile(r"^(d[ée]finition|th[ée]or[èe]me|propri[ée]t[ée]|proposition|lemme|corollaire|m[ée]thode|"
                    r"definition|theorem|property|method|rule|r[èe]gle)\b", re.I)


def heading_level(line: str) -> int | None:
    s = line.strip()
    if not (3 <= len(s) <= 90) or s.endswith((",", ";")) or s.count(" ") > 12:
        return None
    if _H1.match(s) or (s.isupper() and len(s) > 5 and not re.search(r"\d{3,}", s)):
        return 1
    if _ROMAN.match(s):
        return 1
    if _NUM3.match(s):
        return 3
    if _NUM2.match(s) and not s.endswith("."):
        return 2
    if _LABEL.match(s) and len(s) < 60:
        return 3
    return None


def _headings_from_text(text: str) -> list[tuple[int, str]]:
    out = []
    for line in text.splitlines():
        lvl = heading_level(line)
        if lvl:
            out.append((lvl, re.sub(r"\s+", " ", line.strip())))
    return out


def _clean(text: str) -> str:
    text = text.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # de-hyphenate line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ------------------------------------------------------------------------------------------ formats
def parse_pdf(data: bytes, *, ocr_lang: str, max_pages: int) -> ParsedDoc:
    pages: list[ParsedPage] = []
    warnings: list[str] = []
    title = ""
    texts: list[str] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                raise UnsupportedFormat("encrypted_pdf") from None
        title = (reader.metadata.title if reader.metadata and reader.metadata.title else "") or ""
        for p in reader.pages[:max_pages]:
            try:
                texts.append(p.extract_text() or "")
            except Exception:  # noqa: BLE001
                texts.append("")
        if len(reader.pages) > max_pages:
            warnings.append(f"only the first {max_pages} pages were read")
    except UnsupportedFormat:
        raise
    except Exception:  # noqa: BLE001 - try the next parser
        texts = []
    if not texts or sum(len(t.strip()) for t in texts) < 20:
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                texts = [(pg.extract_text() or "") for pg in pdf.pages[:max_pages]]
        except Exception:  # noqa: BLE001
            pass
    for i, t in enumerate(texts):
        ocr = False
        if len(t.strip()) < 30:
            o = _ocr_pdf_page(data, i, ocr_lang)
            if o:
                t, ocr = o, True
        t = _clean(t)
        pages.append(ParsedPage(i + 1, t, _headings_from_text(t), ocr))
    if not pages:
        raise UnsupportedFormat("unreadable_pdf")
    if all(not p.text for p in pages):
        warnings.append("no text found (scanned PDF and OCR unavailable)")
    return ParsedDoc(pages, title=title, mime=MIME_BY_EXT[".pdf"], warnings=warnings)


def _ocr_pdf_page(data: bytes, index: int, lang: str) -> str | None:
    try:
        import pypdfium2 as pdfium
        import pytesseract

        doc = pdfium.PdfDocument(data)
        img = doc[index].render(scale=2.2).to_pil()
        return pytesseract.image_to_string(img, lang=lang) or None
    except Exception:  # noqa: BLE001 - OCR is best effort
        return None


def parse_image(data: bytes, *, ocr_lang: str) -> ParsedDoc:
    try:
        import pytesseract
        from PIL import Image

        text = _clean(pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=ocr_lang))
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedFormat("image_ocr_unavailable") from exc
    return ParsedDoc([ParsedPage(1, text, _headings_from_text(text), True)], mime="image")


def parse_docx(data: bytes) -> ParsedDoc:
    import docx  # python-docx

    d = docx.Document(io.BytesIO(data))
    pages: list[ParsedPage] = []
    cur_lines: list[str] = []
    cur_heads: list[tuple[int, str]] = []

    def flush():
        if cur_lines or cur_heads:
            pages.append(ParsedPage(len(pages) + 1, _clean("\n".join(cur_lines)), list(cur_heads)))
        cur_lines.clear()
        cur_heads.clear()

    body = d.element.body
    for el in body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            from docx.text.paragraph import Paragraph

            p = Paragraph(el, d)
            text = p.text.strip()
            style = (p.style.name if p.style is not None else "") or ""
            m = re.match(r"(?:heading|titre)\s*(\d)", style, re.I)
            if text:
                if m:
                    cur_heads.append((min(3, int(m.group(1))), text))
                elif style.lower() == "title":
                    cur_heads.append((1, text))
                else:
                    lvl = heading_level(text)
                    if lvl and len(text) < 70:
                        cur_heads.append((lvl, text))
                cur_lines.append(text)
            if 'w:type="page"' in el.xml or "lastRenderedPageBreak" in el.xml and len(cur_lines) > 40:
                flush()
        elif tag == "tbl":
            from docx.table import Table

            for row in Table(el, d).rows:
                cells = [c.text.strip() for c in row.cells]
                cur_lines.append(" | ".join(c for c in cells if c))
    flush()
    title = d.core_properties.title or (pages[0].headings[0][1] if pages and pages[0].headings else "")
    return ParsedDoc(pages or [ParsedPage(1, "")], title=title, mime=MIME_BY_EXT[".docx"],
                     warnings=["equations written with the Word equation editor may be missing"]
                     if b"m:oMath" in data or "oMath" in "".join(p.text for p in pages) else [])


def parse_pptx(data: bytes) -> ParsedDoc:
    try:
        from pptx import Presentation

        prs = Presentation(io.BytesIO(data))
        pages = []
        for i, slide in enumerate(prs.slides):
            lines, heads = [], []
            title_shape = slide.shapes.title
            if title_shape is not None and title_shape.has_text_frame and title_shape.text_frame.text.strip():
                heads.append((2, title_shape.text_frame.text.strip()))
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        t = "".join(r.text for r in para.runs).strip()
                        if t:
                            lines.append(("  " * para.level) + t)
                if getattr(shape, "has_table", False) and shape.has_table:
                    for row in shape.table.rows:
                        lines.append(" | ".join(c.text.strip() for c in row.cells))
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    lines.append(notes)
            pages.append(ParsedPage(i + 1, _clean("\n".join(lines)), heads))
        return ParsedDoc(pages, title=pages[0].headings[0][1] if pages and pages[0].headings else "",
                         mime=MIME_BY_EXT[".pptx"])
    except ModuleNotFoundError:
        import xml.etree.ElementTree as ET
        import zipfile

        pages = []
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            slide_names = sorted(
                [n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)],
                key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)),  # type: ignore[union-attr]
            )
            for i, name in enumerate(slide_names):
                root = ET.fromstring(zf.read(name))
                paras = []
                for p in root.iter():
                    if p.tag.endswith("}p") or p.tag == "p":
                        runs = [t.text for t in p.iter() if (t.tag.endswith("}t") or t.tag == "t") and t.text]
                        txt = "".join(runs).strip()
                        if txt:
                            paras.append(txt)
                heads = [(2, paras[0])] if paras else []
                pages.append(ParsedPage(i + 1, _clean("\n".join(paras)), heads))
        return ParsedDoc(pages or [ParsedPage(1, "")], title=pages[0].headings[0][1] if pages and pages[0].headings else "",
                         mime=MIME_BY_EXT[".pptx"])


def parse_text(text: str, *, markdown: bool) -> ParsedDoc:
    heads: list[tuple[int, str]] = []
    pages: list[ParsedPage] = []
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line) if markdown else None
        if m:
            heads.append((min(3, len(m.group(1))), m.group(2).strip()))
            buf.append(m.group(2).strip())
        else:
            lvl = None if markdown else heading_level(line)
            if lvl:
                heads.append((lvl, line.strip()))
            buf.append(line)
        if len(buf) >= 80:  # synthetic pages keep citations short
            pages.append(ParsedPage(len(pages) + 1, _clean("\n".join(buf)), heads))
            buf, heads = [], []
    if buf or not pages:
        pages.append(ParsedPage(len(pages) + 1, _clean("\n".join(buf)), heads))
    return ParsedDoc(pages, title=next((t for _, t in pages[0].headings), ""), mime="text/markdown")


def parse_html(html: str) -> ParsedDoc:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml") if _has_lxml() else BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
        t.decompose()
    heads, lines = [], []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "td", "blockquote"]):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            heads.append((min(3, int(el.name[1])), txt))
        lines.append(txt)
    title = soup.title.get_text(strip=True) if soup.title else ""
    return ParsedDoc([ParsedPage(1, _clean("\n".join(lines)), heads)], title=title, mime="text/html")


def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False
