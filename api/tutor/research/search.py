"""Web search providers behind one interface. auto: Tavily > Brave > SerpAPI > SearXNG > Wikipedia (free)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

from .. import http
from ..config import TutorSettings


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str = ""
    provider: str = ""


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, *, k: int = 5, lang: str = "fr", domains: list[str] | None = None) -> list[SearchResult]: ...


class TavilySearch:
    name = "tavily"

    def __init__(self, key: str):
        self.key = key

    def search(self, query, *, k=5, lang="fr", domains=None):
        body = {"query": query, "max_results": k, "search_depth": "basic"}
        if domains:
            body["include_domains"] = domains[:30]
        r = http.post("https://api.tavily.com/search", json=body, timeout=30,
                      headers={"authorization": f"Bearer {self.key}", "content-type": "application/json"})
        if r.status >= 400:
            raise RuntimeError(f"TAVILY_{r.status}")
        return [SearchResult(x["url"], x.get("title", ""), x.get("content", "")[:300], self.name)
                for x in r.json().get("results", [])]


class BraveSearch:
    name = "brave"

    def __init__(self, key: str):
        self.key = key

    def search(self, query, *, k=5, lang="fr", domains=None):
        r = http.get("https://api.search.brave.com/res/v1/web/search", timeout=30,
                     params={"q": query, "count": min(20, k * 2), "search_lang": lang},
                     headers={"x-subscription-token": self.key, "accept": "application/json"})
        if r.status >= 400:
            raise RuntimeError(f"BRAVE_{r.status}")
        return [SearchResult(x["url"], x.get("title", ""), x.get("description", ""), self.name)
                for x in r.json().get("web", {}).get("results", [])]


class SerpApiSearch:
    name = "serpapi"

    def __init__(self, key: str):
        self.key = key

    def search(self, query, *, k=5, lang="fr", domains=None):
        r = http.get("https://serpapi.com/search.json", timeout=30,
                     params={"engine": "google", "q": query, "hl": lang, "num": min(20, k * 2), "api_key": self.key})
        if r.status >= 400:
            raise RuntimeError(f"SERPAPI_{r.status}")
        return [SearchResult(x["link"], x.get("title", ""), x.get("snippet", ""), self.name)
                for x in r.json().get("organic_results", [])]


class SearxngSearch:
    name = "searxng"

    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def search(self, query, *, k=5, lang="fr", domains=None):
        r = http.get(f"{self.base}/search", params={"q": query, "format": "json", "language": lang}, timeout=30)
        if r.status >= 400:
            raise RuntimeError(f"SEARXNG_{r.status}")
        return [SearchResult(x["url"], x.get("title", ""), x.get("content", ""), self.name)
                for x in r.json().get("results", [])[: k * 2]]


class WikipediaSearch:
    """Free, openly licensed (CC BY-SA). Uses the MediaWiki search API, never scrapes search pages."""

    name = "wikipedia"

    def __init__(self, user_agent: str):
        self.ua = user_agent

    def search(self, query, *, k=5, lang="fr", domains=None):
        lang = lang if lang in ("fr", "en", "de", "es", "ar", "it", "pt") else "en"
        r = http.get(f"https://{lang}.wikipedia.org/w/api.php", timeout=20, headers={"user-agent": self.ua},
                     params={"action": "query", "list": "search", "srsearch": query, "format": "json",
                             "srlimit": k, "utf8": 1})
        if r.status >= 400:
            raise RuntimeError(f"WIKIPEDIA_{r.status}")
        out = []
        for x in r.json().get("query", {}).get("search", []):
            title = x["title"]
            out.append(SearchResult(f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}", title,
                                    x.get("snippet", ""), self.name))
        return out


class NoSearch:
    name = "none"

    def search(self, query, *, k=5, lang="fr", domains=None):
        return []


def build_search(s: TutorSettings) -> SearchProvider:
    p = s.search_provider
    if p in ("auto", "tavily") and s.tavily_api_key:
        return TavilySearch(s.tavily_api_key)
    if p in ("auto", "brave") and s.brave_api_key:
        return BraveSearch(s.brave_api_key)
    if p in ("auto", "serpapi") and s.serpapi_api_key:
        return SerpApiSearch(s.serpapi_api_key)
    if p in ("auto", "searxng") and s.searxng_url:
        return SearxngSearch(s.searxng_url)
    if p in ("auto", "wikipedia"):
        return WikipediaSearch(s.user_agent)
    return NoSearch()
