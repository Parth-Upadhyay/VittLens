"""
Input sanitization, text cleanup, and financial data extraction utilities.
"""

import re
from typing import Any, Optional


def sanitize_ticker(symbol: str) -> str:
    """
    Sanitizes raw ticker string into uppercase standard ticker format.
    Strips invalid characters while preserving exchange suffixes (e.g. '.NS', '.BO').
    """
    if not symbol:
        return ""
    # Remove leading/trailing whitespaces and convert to uppercase
    cleaned = symbol.strip().upper()
    # Retain standard alphanumeric, colon, dot, and dash characters
    cleaned = re.sub(r"[^A-Z0-9\.\-_:]", "", cleaned)
    return cleaned


def sanitize_text(text: str) -> str:
    """
    Cleans raw text input by removing control characters, NULL bytes,
    and normalizing whitespace.
    """
    if not text:
        return ""
    # Remove non-printable control characters (except newline, tab)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    # Collapse multiple spaces into single space
    cleaned = re.sub(r" +", " ", cleaned)
    return cleaned.strip()


def parse_financial_number(raw_val: Any) -> Optional[float]:
    """
    Parses messy financial numbers (e.g. '$1,234.50', '₹ 10,50,000', '(150.00)', '12.5 Cr', '5.2 M').

    Args:
        raw_val: String or numeric representation

    Returns:
        Optional[float]: Extracted float value or None if unparseable
    """
    if raw_val is None:
        return None

    if isinstance(raw_val, (int, float)):
        return float(raw_val)

    s = str(raw_val).strip()
    if not s:
        return None

    # Handle accounting negative format: (123.45) -> -123.45
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1]

    # Handle Indian Crore / Lakh & Million / Billion multipliers
    multiplier = 1.0
    s_upper = s.upper()

    if s_upper.endswith("CR") or "CRORE" in s_upper:
        multiplier = 10_000_000.0
        s = re.sub(r"(?i)\b(CR|CRORE|CRORES)\b", "", s)
    elif s_upper.endswith("LK") or "LAKH" in s_upper:
        multiplier = 100_000.0
        s = re.sub(r"(?i)\b(LK|LAKH|LAKHS)\b", "", s)
    elif s_upper.endswith("M") or "MILLION" in s_upper:
        multiplier = 1_000_000.0
        s = re.sub(r"(?i)\b(M|MILLION)\b", "", s)
    elif s_upper.endswith("B") or "BILLION" in s_upper:
        multiplier = 1_000_000_000.0
        s = re.sub(r"(?i)\b(B|BILLION)\b", "", s)

    # Strip currency symbols and commas
    cleaned_num = re.sub(r"[^\d\.\-]", "", s)
    if not cleaned_num or cleaned_num == "-":
        return None

    try:
        val = float(cleaned_num) * multiplier
        return -val if is_negative else val
    except ValueError:
        return None
