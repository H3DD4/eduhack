"""Runtime configuration. All secrets come from the environment (.env.example lists them)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database: Postgres in docker-compose; SQLite fallback for tests / no-Docker dev (DECISIONS D-002).
    database_url: str = "sqlite:///./thinkfirst-dev.db"
    # Postgres runtime role that is subject to row-level security (non-superuser).
    rls_enabled: bool = True

    redis_url: str = "redis://localhost:6379/0"
    # inline = run jobs synchronously in-process; arq = enqueue to Redis worker.
    job_mode: str = "inline"

    storage_backend: str = "local"  # local | s3
    local_storage_dir: str = "./.storage"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "thinkfirst-private"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"

    app_base_url: str = "http://localhost:3000"
    session_cookie_name: str = "tf_session"
    session_cookie_secure: bool = False
    session_days: int = 14

    # Demo mode shows the seeded demo credentials on A01 and enables labeled demo tools.
    demo_mode: bool = True

    # AI providers. Empty key => labeled demo adapters (never silently "real").
    llm_provider: str = "auto"  # auto | demo | anthropic | gemini
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"  # alias; 2.5-flash is closed to new keys
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_stt_model: str = "whisper-large-v3"
    # Fallback chain when the primary provider errors or returns unusable output (e.g. gemini -> groq).
    llm_fallback: bool = True
    # demo (default, restrictive) | groq | gemini. Real STT sends raw audio to that processor (disclosed in UI).
    stt_provider: str = "demo"
    embedding_provider: str = "demo"

    google_client_id: str | None = None
    google_client_secret: str | None = None

    # Product limits (blueprint C01 proposed defaults; DECISIONS D-010).
    max_file_bytes: int = 20 * 1024 * 1024
    max_files_per_batch: int = 5
    max_pages_per_file: int = 200
    max_audio_bytes: int = 25 * 1024 * 1024

    # Mock entitlement (DECISIONS D-011).
    free_units_per_period: int = 30
    period_days: int = 30
    validation_bundle_units: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
