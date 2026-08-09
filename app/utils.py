from __future__ import annotations

# Merged from utils/*

from app.config.settings import Settings
from typing import Any
from typing import Dict, List, Optional
from typing import Optional
import datetime
import json
import logging
import os
import sys


def get_logger(name: str = "finnai.llm", log_level: str = "INFO") -> logging.Logger:
    """
    Get or create a configured logger instance.

    Args:
        name: Name of the logger module.
        log_level: Desired log level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger is already initialized
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    return logger


def log_llm_request(
    logger: logging.Logger,
    model: str,
    latency_ms: float,
    success: bool,
    error_msg: str | None = None,
    extra_details: dict[str, Any] | None = None,
) -> None:
    """
    Structured logger helper for tracking every LLM generation request.

    Args:
        logger: Logger instance to output to.
        model: Name of the LLM model used.
        latency_ms: Request latency in milliseconds.
        success: True if generation succeeded, False otherwise.
        error_msg: Error message if success is False.
        extra_details: Optional additional metadata dict to include.
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status_str = "SUCCESS" if success else "FAILED"

    log_payload = {
        "timestamp": timestamp,
        "model": model,
        "latency_ms": round(latency_ms, 2),
        "status": status_str,
    }

    if error_msg:
        log_payload["error"] = error_msg

    if extra_details:
        log_payload["details"] = extra_details

    msg = f"LLM Generation [{status_str}] - Model: {model} | Latency: {latency_ms:.2f}ms"
    if error_msg:
        msg += f" | Error: {error_msg}"

    if success:
        logger.info(msg)
    else:
        logger.error(msg)

"""
Market Symbol Mapper utility for FinnAI Platform.
Maps normalized canonical company symbols (e.g. 'RELIANCE') or raw aliases (e.g. 'HUL') to yfinance ticker symbols (e.g. 'HINDUNILVR.NS').
Suffix format is configurable via Settings.yfinance_symbol_suffix (Default: '.NS').
"""








"""
Company Name Normalization Utility for FinnAI Platform.
Normalizes company name variations to standardized canonical ticker symbols (e.g. NIFTY Top 20).
Loads alias dictionary from external JSON config file.
"""


logger = get_logger("finnai.company_normalizer")


class CompanyNormalizer:
    """
    Normalizes company names and brand variations into canonical stock ticker symbols.
    """

    def __init__(self, aliases_file_path: Optional[str] = None) -> None:
        self.settings = Settings()
        if aliases_file_path and "nifty500" in aliases_file_path:
            self.file_path = aliases_file_path
        elif os.path.exists("config/nifty500_aliases.json"):
            self.file_path = "config/nifty500_aliases.json"
        else:
            self.file_path = aliases_file_path or self.settings.aliases_file_path
        self._alias_map: Dict[str, str] = {}
        self._canonical_symbols: List[str] = []
        self._load_aliases()

    @property
    def alias_map(self) -> Dict[str, str]:
        """Expose dictionary mapping lower-case alias strings to canonical symbols."""
        return self._alias_map

    def _load_aliases(self) -> None:
        """Load and process alias mappings from configured JSON file."""
        if not os.path.exists(self.file_path):
            logger.warning(f"Alias configuration file not found at '{self.file_path}'. Normalizer initialized with empty mappings.")
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data: Dict[str, List[str]] = json.load(f)

            self._alias_map.clear()
            self._canonical_symbols = list(data.keys())

            for canonical_symbol, aliases in data.items():
                # Self-mapping: symbol maps to itself
                self._alias_map[canonical_symbol.lower()] = canonical_symbol.upper()

                for alias in aliases:
                    cleaned_alias = alias.lower().strip()
                    self._alias_map[cleaned_alias] = canonical_symbol.upper()

            logger.info(f"Loaded {len(self._canonical_symbols)} canonical symbols with {len(self._alias_map)} aliases from '{self.file_path}'.")

        except Exception as e:
            logger.error(f"Failed to parse company aliases from '{self.file_path}': {e}")

    def normalize(self, name: str) -> Optional[str]:
        """
        Normalize a raw company name or string snippet to its canonical symbol.

        Args:
            name: Raw string containing company name or title.

        Returns:
            Canonical symbol (e.g. 'RELIANCE') or None if no match found.
        """
        if not name:
            return None

        cleaned = name.strip().lower()
        if "." in cleaned:
            cleaned = cleaned.split(".")[0]

        if cleaned in self._alias_map:
            return self._alias_map[cleaned]

        # Substring / partial match search
        for alias, canonical in self._alias_map.items():
            if len(alias) > 3 and alias in cleaned:
                return canonical

        return None

    def get_all_symbols(self) -> List[str]:
        """Return list of all loaded canonical ticker symbols."""
        return self._canonical_symbols

    def get_primary_name(self, symbol: str) -> str:
        """
        Get the longest (most descriptive) alias for a canonical symbol.
        Prevents acronym collision in Google News searches (e.g. LT -> Larsen & Toubro).
        """
        aliases = [alias for alias, canonical in self._alias_map.items() if canonical == symbol.upper() and alias != symbol.lower()]
        if aliases:
            return max(aliases, key=len).title()
        return symbol

"""
Custom exception hierarchy for LLM Layer.
Ensures raw SDK exceptions are encapsulated and never leaked upstream.
Provides provider-agnostic exception classes with backward-compatible vendor aliases.
"""


class LLMBaseError(Exception):
    """Base exception for all LLM layer errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class LLMAuthenticationError(LLMBaseError):
    """Raised when LLM API authentication fails (e.g. invalid or missing API key). Non-retryable."""

    pass


class LLMTimeoutError(LLMBaseError):
    """Raised when a request to LLM API times out. Retryable."""

    pass


class LLMRateLimitError(LLMBaseError):
    """Raised when LLM API rate limits are hit (HTTP 429). Retryable."""

    pass


class LLMGenerationError(LLMBaseError):
    """Raised when LLM API fails to generate a response due to transient or server errors."""

    pass


# Backward-compatible Groq vendor aliases
GroqBaseError = LLMBaseError
GroqAuthenticationError = LLMAuthenticationError
GroqTimeoutError = LLMTimeoutError
GroqRateLimitError = LLMRateLimitError
GroqGenerationError = LLMGenerationError

"""
Centralized logging utility for FinnAI LLM Layer.
Provides structured logging for request metadata, latency, and outcome tracking.
Ensures sensitive tokens and API keys are never exposed in log outputs.
"""



class MarketSymbolMapper:
    """
    Utility mapping raw company names / aliases / canonical symbols to yfinance-compatible exchange tickers.
    """
    
    SPECIAL_TICKERS = {
        "^NSEI": "^NSEI",
        "PPFCF": "0P0000XW8F.BO",
        "SBICAP": "0P0000XWAA.BO",
        "AXISMID": "0P0000YWL1.BO",
        "HDFCTOP": "0P0000XW1A.BO",
        "ICICIPRU": "0P0000XW4L.BO",
        "MIRAEASSET": "0P0000YWA1.BO",
        "NIPPONSMALL": "0P0000XW8E.BO",
        "QUANTLONG": "0P0000YWH7.BO",
        "UTINIFTY": "0P0000XW8L.BO"
    }

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.suffix = self.settings.yfinance_symbol_suffix
        self.normalizer = CompanyNormalizer()

    def to_yfinance_ticker(self, symbol: str) -> str:
        """
        Convert a canonical symbol or raw string (e.g. 'HUL', 'HUL.NS', 'RELIANCE') to a yfinance-compatible ticker.

        Args:
            symbol: Canonical ticker symbol or raw alias.

        Returns:
            Formatted yfinance ticker string (e.g. 'HINDUNILVR.NS').
        """
        if not symbol:
            return f"RELIANCE{self.suffix}"

        cleaned = symbol.strip().upper()

        # Handle base symbol before dot (e.g. 'HUL' from 'HUL.NS')
        raw_base = cleaned.split(".")[0] if "." in cleaned else cleaned

        # Normalize alias to canonical symbol if available (e.g. 'HUL' -> 'HINDUNILVR')
        canonical = self.normalizer.normalize(raw_base)
        target_base = canonical if canonical else raw_base

        # Check if it's in our special list
        if target_base in self.SPECIAL_TICKERS:
            return self.SPECIAL_TICKERS[target_base]
            
        # Don't append suffix if it already has a dot (like .BO, .NS)
        if "." in target_base:
            return target_base

        return f"{target_base}{self.suffix}"

    def to_canonical_symbol(self, ticker: str) -> str:
        """
        Convert a yfinance ticker or raw string back to canonical symbol format.

        Args:
            ticker: yfinance ticker string (e.g. 'HINDUNILVR.NS', 'HUL').

        Returns:
            Canonical symbol string (e.g. 'HINDUNILVR').
        """
        if not ticker:
            return "RELIANCE"

        cleaned = ticker.strip().upper()
        raw_base = cleaned.split(".")[0] if "." in cleaned else cleaned
        canonical = self.normalizer.normalize(raw_base)
        return canonical if canonical else raw_base
