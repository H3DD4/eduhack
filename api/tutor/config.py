"""Tutor module settings. Everything comes from environment variables prefixed with TUTOR_.

The defaults run fully offline: SQLite store, hashing embedder, mock LLM, Wikipedia-only research.
Set real keys to switch each part on; nothing silently pretends to be real (see `capabilities()`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(f"TUTOR_{name}", os.environ.get(name, default))


def _bool(name: str, default: bool) -> bool:
    v = _env(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    v = _env(name)
    return default if v is None else int(v)


def _float(name: str, default: float) -> float:
    v = _env(name)
    return default if v is None else float(v)


def _list(name: str, default: list[str]) -> list[str]:
    v = _env(name)
    return default if not v else [x.strip() for x in v.split(",") if x.strip()]


DEFAULT_ALLOWED_DOMAINS = [
    "wikipedia.org", "wikibooks.org", "wikiversity.org", "khanacademy.org", "openstax.org", "libretexts.org",
    "mit.edu", "ocw.mit.edu", "bibmath.net", "maths-et-tiques.fr", "lumni.fr", "eduscol.education.fr",
    "w3schools.com", "developer.mozilla.org", "docs.python.org", "geeksforgeeks.org", "britannica.com",
    "physicsclassroom.com", "hyperphysics.phy-astr.gsu.edu", "chem.libretexts.org", "arxiv.org",
]


@dataclass
class TutorSettings:
    # Storage
    store_backend: str = "sqlite"            # sqlite | sqlalchemy
    sqlite_path: str = "./tutor-dev.db"
    database_url: str | None = None          # used by the sqlalchemy store (Postgres + pgvector)
    blob_dir: str = "./.tutor-blobs"

    # LLM
    llm_provider: str = "auto"               # auto | mock | anthropic | openai | groq | ollama | gemini
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    ollama_api_key: str | None = None
    ollama_url: str = "http://localhost:11434"
    model_large: str = "claude-sonnet-5-5"   # generation, lesson writing, critic
    model_small: str = "claude-haiku-5-5"    # classification, concept tagging, probe items
    openai_model_large: str = "gpt-4.1"
    openai_model_small: str = "gpt-4.1-mini"
    groq_model: str = "openai/gpt-oss-120b"
    gemini_model: str = "gemini-4-hydrogen"
    ollama_model: str = "qwen2.5:14b"
    llm_timeout_s: int = 90
    llm_budget_tokens_per_track: int = 600_000
    fallback_to_mock: bool = True

    # Embeddings and retrieval
    embedder: str = "auto"                   # auto | hashing | sentence-transformers | hf
    embed_model: str = "BAAI/bge-m3"         # multilingual; alt: intfloat/multilingual-e5-base
    hf_token: str | None = None
    reranker: str = "auto"                   # auto | none | cross-encoder
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    chunk_words: int = 260
    chunk_overlap: int = 40
    retrieve_k: int = 8

    # Research (search + scraping)
    web_research: bool = True
    search_provider: str = "auto"            # auto | tavily | brave | searxng | serpapi | wikipedia | none
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
    serpapi_api_key: str | None = None
    searxng_url: str | None = None
    allowed_domains: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_DOMAINS))
    blocked_domains: list[str] = field(default_factory=lambda: ["chegg.com", "coursehero.com", "brainly.com"])
    allow_any_domain: bool = False
    max_web_pages_per_track: int = 12
    scrape_max_bytes: int = 4_000_000
    scrape_timeout_s: int = 20
    scrape_min_interval_s: float = 1.0       # politeness delay per domain
    user_agent: str = "ThinkFirstTutorBot/1.0 (+https://thinkfirst.app/bot; educational research)"
    use_playwright: bool = False             # render JS-heavy pages (needs `playwright install chromium`)

    # Learning science
    probe_min_items: int = 6
    probe_max_items: int = 10
    likeness_show: float = 0.70
    likeness_regenerate: float = 0.50
    max_regenerations: int = 1
    mastery_threshold: float = 0.95

    # Jobs
    job_mode: str = "thread"                 # inline | thread | arq
    redis_url: str = "redis://localhost:6379/0"

    @classmethod
    def from_env(cls) -> TutorSettings:
        d = cls()
        return cls(
            store_backend=_env("STORE_BACKEND", d.store_backend) or d.store_backend,
            sqlite_path=_env("SQLITE_PATH", d.sqlite_path) or d.sqlite_path,
            database_url=_env("DATABASE_URL"),
            blob_dir=_env("BLOB_DIR", d.blob_dir) or d.blob_dir,
            llm_provider=_env("LLM_PROVIDER", d.llm_provider) or d.llm_provider,
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            openai_api_key=_env("OPENAI_API_KEY"),
            groq_api_key=_env("GROQ_API_KEY"),
            gemini_api_key=_env("GEMINI_API_KEY"),
            ollama_api_key=_env("OLLAMA_API_KEY"),
            ollama_url=_env("OLLAMA_URL", d.ollama_url) or d.ollama_url,
            model_large=_env("MODEL_LARGE", d.model_large) or d.model_large,
            model_small=_env("MODEL_SMALL", d.model_small) or d.model_small,
            openai_model_large=_env("OPENAI_MODEL_LARGE", d.openai_model_large) or d.openai_model_large,
            openai_model_small=_env("OPENAI_MODEL_SMALL", d.openai_model_small) or d.openai_model_small,
            groq_model=_env("GROQ_MODEL", d.groq_model) or d.groq_model,
            gemini_model=_env("GEMINI_MODEL", d.gemini_model) or d.gemini_model,
            ollama_model=_env("OLLAMA_MODEL", d.ollama_model) or d.ollama_model,
            llm_timeout_s=_int("LLM_TIMEOUT_S", d.llm_timeout_s),
            llm_budget_tokens_per_track=_int("LLM_BUDGET_TOKENS_PER_TRACK", d.llm_budget_tokens_per_track),
            embedder=_env("EMBEDDER", d.embedder) or d.embedder,
            embed_model=_env("EMBED_MODEL", d.embed_model) or d.embed_model,
            hf_token=_env("HF_TOKEN"),
            reranker=_env("RERANKER", d.reranker) or d.reranker,
            rerank_model=_env("RERANK_MODEL", d.rerank_model) or d.rerank_model,
            chunk_words=_int("CHUNK_WORDS", d.chunk_words),
            chunk_overlap=_int("CHUNK_OVERLAP", d.chunk_overlap),
            retrieve_k=_int("RETRIEVE_K", d.retrieve_k),
            web_research=_bool("WEB_RESEARCH", d.web_research),
            search_provider=_env("SEARCH_PROVIDER", d.search_provider) or d.search_provider,
            tavily_api_key=_env("TAVILY_API_KEY"),
            brave_api_key=_env("BRAVE_API_KEY"),
            serpapi_api_key=_env("SERPAPI_API_KEY"),
            searxng_url=_env("SEARXNG_URL"),
            allowed_domains=_list("ALLOWED_DOMAINS", d.allowed_domains),
            blocked_domains=_list("BLOCKED_DOMAINS", d.blocked_domains),
            allow_any_domain=_bool("ALLOW_ANY_DOMAIN", d.allow_any_domain),
            max_web_pages_per_track=_int("MAX_WEB_PAGES_PER_TRACK", d.max_web_pages_per_track),
            scrape_max_bytes=_int("SCRAPE_MAX_BYTES", d.scrape_max_bytes),
            scrape_timeout_s=_int("SCRAPE_TIMEOUT_S", d.scrape_timeout_s),
            scrape_min_interval_s=_float("SCRAPE_MIN_INTERVAL_S", d.scrape_min_interval_s),
            user_agent=_env("USER_AGENT", d.user_agent) or d.user_agent,
            use_playwright=_bool("USE_PLAYWRIGHT", d.use_playwright),
            probe_min_items=_int("PROBE_MIN_ITEMS", d.probe_min_items),
            probe_max_items=_int("PROBE_MAX_ITEMS", d.probe_max_items),
            likeness_show=_float("LIKENESS_SHOW", d.likeness_show),
            likeness_regenerate=_float("LIKENESS_REGENERATE", d.likeness_regenerate),
            max_regenerations=_int("MAX_REGENERATIONS", d.max_regenerations),
            mastery_threshold=_float("MASTERY_THRESHOLD", d.mastery_threshold),
            job_mode=_env("JOB_MODE", d.job_mode) or d.job_mode,
            redis_url=_env("REDIS_URL", d.redis_url) or d.redis_url,
        )


@lru_cache
def get_settings() -> TutorSettings:
    return TutorSettings.from_env()
