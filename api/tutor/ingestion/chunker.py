"""Heading-aware chunking. Chunks never cross a level-1/2 heading, keep their page and section path, and
overlap by a few words so a definition split over two chunks is still retrievable."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .parsers import ParsedDoc


@dataclass
class RawChunk:
    text: str
    page: int | None
    section: str
    ord: int


def chunk_document(doc: ParsedDoc, *, target_words: int = 260, overlap: int = 40, min_words: int = 12) -> list[RawChunk]:
    out: list[RawChunk] = []
    path: dict[int, str] = {}
    buf: list[str] = []
    buf_page: int | None = None

    def section() -> str:
        return " › ".join(path[k] for k in sorted(path))

    def flush(force: bool = False):
        nonlocal buf, buf_page
        text = " ".join(buf).strip()
        n = len(text.split())
        if n >= min_words or (force and n > 0 and not out):
            out.append(RawChunk(text, buf_page, section(), len(out)))
            tail = text.split()[-overlap:] if overlap and n > overlap else []
            buf = [" ".join(tail)] if tail and not force else []
        elif force:
            if out and n:
                out[-1].text += " " + text
            buf = []
        buf_page = None

    for page in doc.pages:
        heads = {t: lvl for lvl, t in page.headings}
        for para in re.split(r"\n\s*\n|\n(?=[-•*]\s)|\n(?=\d+[.)]\s)", page.text):
            para = re.sub(r"\s*\n\s*", " ", para).strip()
            if not para:
                continue
            first_line = para[:90]
            lvl = next((lv for t, lv in heads.items() if para.startswith(t) or first_line == t), None)
            if lvl is not None and lvl <= 2:
                flush(force=True)
                title = next(t for t, lv in heads.items() if para.startswith(t) or first_line == t)
                for k in [k for k in path if k >= lvl]:
                    del path[k]
                path[lvl] = title[:80]
            elif lvl == 3:
                for k in [k for k in path if k >= 3]:
                    del path[k]
                path[3] = next(t for t, lv in heads.items() if para.startswith(t))[:80]
            if buf_page is None:
                buf_page = page.number
            words = para.split()
            while words:
                room = target_words - sum(len(b.split()) for b in buf)
                take, words = words[:max(room, 1)], words[max(room, 1):]
                buf.append(" ".join(take))
                if sum(len(b.split()) for b in buf) >= target_words:
                    flush()
                    if buf_page is None:
                        buf_page = page.number
    flush(force=True)
    return out
