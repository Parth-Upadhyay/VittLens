"""
FinnAI Core Package Foundation.

Production-grade foundation containing configuration management, structured logging,
environment validation, common utilities, and shared domain schemas.
"""

__version__ = "0.1.0"
__author__ = "FinnAI Platform Team"

from core.config import settings
from core.logging import get_logger

__all__ = ["settings", "get_logger", "__version__"]
