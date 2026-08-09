"""
Application settings configuration using Pydantic.
Strongly typed container for application environment configuration.
"""

import json
import os
from typing import List
from dotenv import load_dotenv
from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings
    SettingsConfigDict = None

# Ensure .env file is loaded into environment
load_dotenv()

# Verified active models on Groq
DEFAULT_FALLBACK_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "groq/compound",
    "groq/compound-mini",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]


class Settings(BaseSettings):
    """
    Strongly typed application settings loaded from environment variables.
    Exposes LLM settings, Fallback Models, Database URL, Auth credentials, Guest Mode, yfinance, and Orchestrator settings.
    """

    groq_api_key: str = Field(
        default_factory=lambda: os.getenv("GROQ_API_KEY", ""),
        alias="GROQ_API_KEY",
        description="API Key for authenticating with Groq service.",
    )
    groq_model: str = Field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        alias="GROQ_MODEL",
        description="Groq LLM primary model name to use for general chat completions.",
    )
    synthesis_model: str = Field(
        default_factory=lambda: os.getenv("SYNTHESIS_MODEL", "llama-3.1-8b-instant"),
        alias="SYNTHESIS_MODEL",
        description="High-capacity Groq LLM model name used for multi-agent financial synthesis.",
    )
    max_context_tokens: int = Field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_TOKENS", "4500")),
        alias="MAX_CONTEXT_TOKENS",
        description="Maximum prompt token budget for ContextBuilder token guard (Default: 4,500).",
    )
    secret_key: str = Field(
        default_factory=lambda: os.getenv("SECRET_KEY", "finnai-super-secret-key-2026"),
        alias="SECRET_KEY",
        description="Secret key for signing JWT tokens and guest session cookies.",
    )
    google_client_id: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID", ""),
        alias="GOOGLE_CLIENT_ID",
        description="Google OAuth 2.0 Client ID.",
    )
    google_client_secret: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CLIENT_SECRET", ""),
        alias="GOOGLE_CLIENT_SECRET",
        description="Google OAuth 2.0 Client Secret.",
    )
    frontend_url: str = Field(
        default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:3000"),
        alias="FRONTEND_URL",
        description="Frontend application URL.",
    )
    guest_query_limit: int = Field(
        default_factory=lambda: int(os.getenv("GUEST_QUERY_LIMIT", "-1")),
        alias="GUEST_QUERY_LIMIT",
        description="Maximum queries allowed for Guest Mode (-1 for Unlimited).",
    )
    cors_origins: str = Field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "*"),
        alias="CORS_ORIGINS",
        description="Allowed CORS origins comma-separated string or *.",
    )
    groq_fallback_models: List[str] = Field(
        default_factory=lambda: json.loads(
            os.getenv(
                "GROQ_FALLBACK_MODELS",
                json.dumps(DEFAULT_FALLBACK_MODELS),
            )
        ) if isinstance(os.getenv("GROQ_FALLBACK_MODELS"), str) else DEFAULT_FALLBACK_MODELS,
        description="Priority-ordered fallback models when primary model is rate-limited.",
    )
    groq_timeout: float = Field(
        default_factory=lambda: float(os.getenv("GROQ_TIMEOUT", "12.0")),
        alias="GROQ_TIMEOUT",
        description="Request timeout in seconds for Groq API calls.",
    )
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        alias="LOG_LEVEL",
        description="Logging verbosity level (DEBUG, INFO, WARNING, ERROR).",
    )

    # Database & News Pipeline settings
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            os.getenv("POSTGRES_URL", "sqlite:///./finnai.db"),
        ),
        alias="DATABASE_URL",
        description="PostgreSQL / SQLite database connection URL.",
    )
    redis_url: str = Field(
        default_factory=lambda: (lambda url: url if "://" in url else f"redis://{url}")(os.getenv("REDIS_URL", "redis://localhost:6379/0").replace("https://", "rediss://").replace("http://", "redis://")),
        alias="REDIS_URL",
        description="Redis server connection URL.",
    )
    redis_max_connections: int = Field(
        default_factory=lambda: int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
        alias="REDIS_MAX_CONNECTIONS",
        description="Maximum connections in the Redis connection pool.",
    )
    cache_enabled: bool = Field(
        default_factory=lambda: os.getenv("CACHE_ENABLED", "True").lower() in ("true", "1", "yes"),
        alias="CACHE_ENABLED",
        description="Global toggle for Redis caching.",
    )
    marketaux_api_key: str = Field(
        default_factory=lambda: os.getenv("MARKETAUX_API_KEY", ""),
        alias="MARKETAUX_API_KEY",
        description="API key for Marketaux primary news fetcher.",
    )
    news_fetch_interval_hours: int = Field(
        default_factory=lambda: int(os.getenv("NEWS_FETCH_INTERVAL_HOURS", "1")),
        alias="NEWS_FETCH_INTERVAL_HOURS",
        description="Interval in hours for news ingestion worker execution.",
    )
    news_article_ttl_days: int = Field(
        default_factory=lambda: int(os.getenv("NEWS_ARTICLE_TTL_DAYS", "15")),
        alias="NEWS_ARTICLE_TTL_DAYS",
        description="Time to live in days for news articles (Default: 15 days).",
    )
    max_articles_per_company: int = Field(
        default_factory=lambda: int(os.getenv("MAX_ARTICLES_PER_COMPANY", "5")),
        alias="MAX_ARTICLES_PER_COMPANY",
        description="Maximum news articles to ingest per company per cycle (Default: 5).",
    )
    aliases_file_path: str = Field(
        default_factory=lambda: os.getenv(
            "ALIASES_FILE_PATH",
            "config/nifty500_aliases.json" if os.path.exists("config/nifty500_aliases.json") else "config/nifty20_aliases.json",
        ),
        alias="ALIASES_FILE_PATH",
        description="Path to JSON file containing NIFTY company alias mappings.",
    )

    # yfinance Market Data Service settings
    yfinance_symbol_suffix: str = Field(
        default_factory=lambda: os.getenv("YFINANCE_SYMBOL_SUFFIX", ".NS"),
        alias="YFINANCE_SYMBOL_SUFFIX",
        description="Ticker suffix for NIFTY stocks on yfinance (Default: '.NS').",
    )
    yfinance_cache_ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("YFINANCE_CACHE_TTL_SECONDS", "600")),
        alias="YFINANCE_CACHE_TTL_SECONDS",
        description="In-memory TTL cache duration in seconds for yfinance market data (Default: 600s / 10 min).",
    )
    yfinance_max_retries: int = Field(
        default_factory=lambda: int(os.getenv("YFINANCE_MAX_RETRIES", "5")),
        alias="YFINANCE_MAX_RETRIES",
        description="Maximum retry attempts for yfinance HTTP requests (Default: 5).",
    )
    yfinance_timeout: float = Field(
        default_factory=lambda: float(os.getenv("YFINANCE_TIMEOUT", "10.0")),
        alias="YFINANCE_TIMEOUT",
        description="Request timeout in seconds for yfinance queries (Default: 10.0s).",
    )

    if SettingsConfigDict:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            populate_by_name=True,
        )

    @property
    def api_key(self) -> str:
        """Expose API key property."""
        return self.groq_api_key

    @property
    def model_name(self) -> str:
        """Expose model name property."""
        return self.groq_model

    @property
    def timeout(self) -> float:
        """Expose timeout property in seconds."""
        return self.groq_timeout

    @property
    def logging_level(self) -> str:
        """Expose logging level property."""
        return self.log_level.upper()
