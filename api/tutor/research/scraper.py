"""Polite scraper: robots.txt, per-domain delay, size and type limits, allowlist, licence label, main-text
extraction that keeps headings and LaTeX (Wikipedia/MathJax), optional Playwright for JS pages.

    fetcher = PoliteFetcher(settings)
    page = fetcher.fetch("https://fr.wikipedia.org/wiki/D%C3%A9riv%C3%A9e")
    page.text, page.headings, page.licence
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from .. import http
from ..config import TutorSettings
from .policy import allowed, domain_of, licence_for

log = logging.getLogger("tutor.scraper")

OK_TYPES = ("text/html", "application/xhtml+xml", "application/pdf", "text/plain", "text/markdown")


class ScrapeRefused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class ScrapedPage:
    url: str
    final_url: str
    title: str
    text: str
    headings: list[tuple[int, str]] = field(default_factory=list)
    licence: str = "unknown"
    lang: str | None = None
    sha256: str = ""
    content_type: str = "text/html"


# ------------------------------------------------------------------------------------------- extraction
def _math_to_tex(soup) -> None:
    for m in soup.find_all("math"):
        ann = m.find("annotation", attrs={"encoding": "application/x-tex"})
        tex = ann.get_text(strip=True) if ann else m.get("alttext")
        if tex:
            m.replace_with(f" ${tex.strip()}$ ")
    for img in soup.find_all("img", class_=re.compile("mwe-math-fallback")):
        alt = img.get("alt")
        if alt:
            img.replace_with(f" ${alt.strip()}$ ")
    for s in soup.find_all("script", attrs={"type": re.compile("math/tex")}):
        s.replace_with(f" ${s.get_text(strip=True)}$ ")


BOILER = re.compile(r"(nav|menu|footer|header|sidebar|cookie|banner|advert|promo|share|social|comment|related|"
                    r"breadcrumb|toc|newsletter|subscribe|popup|modal)", re.I)


def extract_main(html: str, url: str = "") -> tuple[str, str, list[tuple[int, str]], dict[str, str], str | None]:
    """Return (title, text, headings, meta, lang). trafilatura when installed, else a BeautifulSoup heuristic."""
    from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:  # noqa: BLE001
        soup = BeautifulSoup(html, "html.parser")
    meta = {}
    for m in soup.find_all("meta"):
        k = (m.get("name") or m.get("property") or "").lower()
        if k and m.get("content"):
            meta[k] = m["content"]
    lic = soup.find("link", rel=lambda v: v and "license" in v)
    if lic and lic.get("href"):
        meta["license"] = lic["href"]
    lang = (soup.html.get("lang") if soup.html else None) or meta.get("og:locale")
    title = (meta.get("og:title") or (soup.title.get_text(strip=True) if soup.title else "")).strip()

    try:
        import trafilatura  # type: ignore

        txt = trafilatura.extract(html, url=url or None, include_tables=True, include_formatting=False,
                                  include_comments=False, favor_precision=True)
        if txt and len(txt) > 400:
            heads = [(int(h.name[1]) if h.name[1] in "123" else 3, h.get_text(" ", strip=True))
                     for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
            return title, txt, heads[:80], meta, lang
    except Exception:  # noqa: BLE001
        pass

    _math_to_tex(soup)
    for t in soup(["script", "style", "noscript", "svg", "form", "iframe", "button", "input", "select"]):
        t.decompose()
    for t in soup.find_all(["nav", "footer", "header", "aside"]):
        t.decompose()
    for t in soup.find_all(True):
        if t.attrs is None:
            continue
        cls = " ".join(t.get("class") or []) + " " + (t.get("id") or "") + " " + (t.get("role") or "")
        if BOILER.search(cls) and t.name not in ("body", "main", "article", "html"):
            t.decompose()
    for sel in ("main", "article", "[role=main]", "#mw-content-text", ".mw-parser-output", "#content", ".content",
                ".post", ".entry-content"):
        root = soup.select_one(sel)
        if root and len(root.get_text(" ", strip=True)) > 300:
            break
    else:
        candidates = soup.find_all(["div", "section", "body"])
        root = max(candidates, key=lambda el: sum(len(p.get_text(strip=True)) for p in el.find_all("p", recursive=False))
                   + len(el.find_all("p")) * 20, default=soup)
    heads, lines = [], []
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "blockquote", "dd", "dt", "td", "th"]):
        if el.find_parent(["li", "td", "th"]) and el.name in ("p",):
            continue
        t = el.get_text(" ", strip=True)
        t = re.sub(r"\[\s*(\d+|modifier|edit|citation needed|réf\. nécessaire)\s*\]", "", t)
        if len(t) < 2:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            if re.match(r"^(notes et références|références|voir aussi|liens externes|bibliographie|references|"
                        r"see also|external links|further reading)$", t, re.I):
                break
            heads.append((min(3, int(el.name[1])), t))
            lines.append("\n" + t)
        else:
            lines.append(t)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return title, text, heads, meta, lang


# ------------------------------------------------------------------------------------------- fetching
class PoliteFetcher:
    def __init__(self, settings: TutorSettings, transport=None):
        self.s = settings
        self.transport = transport or http.get       # injectable for tests
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self._cache: dict[str, ScrapedPage] = {}

    def _wait_turn(self, domain: str) -> None:
        with self._lock:
            last = self._last.get(domain, 0.0)
            delay = self.s.scrape_min_interval_s - (time.monotonic() - last)
            if delay > 0:
                time.sleep(delay)
            self._last[domain] = time.monotonic()

    def _robots_ok(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.transport(urljoin(base, "/robots.txt"), headers={"user-agent": self.s.user_agent},
                                   timeout=10, max_bytes=500_000)
                if r.status >= 500:
                    self._robots[base] = None  # unreachable robots: be conservative
                    return False
                rp.parse(r.text.splitlines() if r.status < 400 else [])
                self._robots[base] = rp
            except Exception:  # noqa: BLE001
                self._robots[base] = None
                return False
        rp = self._robots[base]
        return bool(rp and rp.can_fetch(self.s.user_agent, url))

    def fetch(self, url: str) -> ScrapedPage:
        if url in self._cache:
            return self._cache[url]
        ok, why = allowed(url, self.s)
        if not ok:
            raise ScrapeRefused(why)
        if not self._robots_ok(url):
            raise ScrapeRefused("robots_disallow")
        domain = domain_of(url)
        self._wait_turn(domain)
        try:
            r = self.transport(url, timeout=self.s.scrape_timeout_s, max_bytes=self.s.scrape_max_bytes,
                               headers={"user-agent": self.s.user_agent, "accept-language": "fr,en;q=0.8",
                                        "accept": "text/html,application/xhtml+xml,application/pdf;q=0.9"})
        except http.HttpError as e:
            raise ScrapeRefused(e.code.lower()) from e
        if r.status >= 400:
            raise ScrapeRefused(f"http_{r.status}")
        final = r.url or url
        if final != url:
            ok, why = allowed(final, self.s)
            if not ok:
                raise ScrapeRefused("redirect_" + why)
        ctype = r.headers.get("content-type", "text/html").split(";")[0].strip().lower()
        if not ctype.startswith(OK_TYPES):
            raise ScrapeRefused("content_type")
        sha = hashlib.sha256(r.content).hexdigest()
        if ctype == "application/pdf":
            from ..ingestion.parsers import parse_pdf

            doc = parse_pdf(r.content, ocr_lang="fra+eng", max_pages=60)
            page = ScrapedPage(url, final, doc.title or final.rsplit("/", 1)[-1], doc.text,
                               [h for p in doc.pages for h in p.headings], licence_for(final), None, sha, ctype)
        elif ctype.startswith("text/plain") or ctype.startswith("text/markdown"):
            page = ScrapedPage(url, final, final.rsplit("/", 1)[-1], r.text, [], licence_for(final), None, sha, ctype)
        else:
            html = r.text
            title, text, heads, meta, lang = extract_main(html, final)
            if len(text) < 300 and self.s.use_playwright:
                html = render_with_playwright(final, self.s)
                title, text, heads, meta, lang = extract_main(html, final)
            page = ScrapedPage(url, final, title, text, heads, licence_for(final, html, meta), lang, sha, ctype)
        if len(page.text) < 200:
            raise ScrapeRefused("too_little_text")
        self._cache[url] = page
        return page


def render_with_playwright(url: str, s: TutorSettings) -> str:  # pragma: no cover - needs a browser
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page(user_agent=s.user_agent)
        page.goto(url, timeout=s.scrape_timeout_s * 1000, wait_until="networkidle")
        html = page.content()
        b.close()
        return html
