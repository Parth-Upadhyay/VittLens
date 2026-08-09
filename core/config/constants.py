"""
Global constants and enumeration types for FinnAI Platform.
"""

from enum import Enum, unique


@unique
class Environment(str, Enum):
    """Execution environment modes."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@unique
class LogLevel(str, Enum):
    """Logging severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@unique
class Currency(str, Enum):
    """Supported currency codes (ISO 4217 standard)."""

    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"


# System Constants
DEFAULT_TIMEZONE = "UTC"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_LOG_FORMAT = "json"  # 'json' for production/cloud, 'console' for dev

# Financial Constants
DEFAULT_CURRENCY = Currency.INR
FISCAL_YEAR_START_MONTH = 4  # April (Standard Indian Financial Year)
