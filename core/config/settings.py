"""
Production-grade configuration management using Pydantic Settings.

Supports environment variables, .env file loading, default values,
and strict type validation for Cloud Run & containerized deployment.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    HAS_PYDANTIC_SETTINGS = True
except ImportError:
    from pydantic import BaseModel as BaseSettings  # type: ignore
    SettingsConfigDict = None  # type: ignore
    HAS_PYDANTIC_SETTINGS = False

from core.config.constants import Environment, LogLevel


class AppConfig(BaseSettings):
    """General Application Settings."""

    name: str = Field(default="FinnAI Platform", description="Application name")
    env: Environment = Field(
        default=Environment.DEVELOPMENT, description="Execution environment"
    )
    debug: bool = Field(default=False, description="Debug mode flag")
    version: str = Field(default="0.1.0", description="Application version")

    @property
    def is_production(self) -> bool:
        return self.env == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.env == Environment.DEVELOPMENT


class LoggingConfig(BaseSettings):
    """Logging Configuration."""

    level: LogLevel = Field(default=LogLevel.INFO, description="Log level severity")
    format: str = Field(
        default="json",
        description="Log output format ('json' for Docker/Cloud Run, 'console' for dev)",
    )
    capture_stdout: bool = Field(
        default=True, description="Capture standard output/err streams"
    )


class ResilienceConfig(BaseSettings):
    """Resilience and Retry Settings for External Calls."""

    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry count")
    backoff_factor: float = Field(
        default=1.5, ge=0.1, description="Exponential backoff factor in seconds"
    )
    timeout_seconds: float = Field(
        default=30.0, ge=1.0, description="Default HTTP/Client operation timeout"
    )


class Settings(BaseSettings):
    """
    Main Application Settings aggregator.

    Reads environment variables automatically. Variables can be overridden
    with uppercase names or prefixed names matching the section.
    """

    if HAS_PYDANTIC_SETTINGS and SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            case_sensitive=False,
        )

    # Core sub-configs
    app: AppConfig = Field(default_factory=AppConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)

    # Base workspace directory
    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )


# Singleton instance of global settings
settings = Settings()
