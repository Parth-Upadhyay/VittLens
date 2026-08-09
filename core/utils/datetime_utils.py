"""
Timezone-aware datetime utilities and financial quarter calculations.
"""

from datetime import date, datetime, timezone
from typing import Optional, Tuple


def now_utc() -> datetime:
    """Returns current UTC datetime with timezone explicit."""
    return datetime.now(timezone.utc)


def format_iso_utc(dt: Optional[datetime] = None) -> str:
    """Formats datetime as ISO 8601 UTC string."""
    target = dt or now_utc()
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    else:
        target = target.astimezone(timezone.utc)
    return target.isoformat()


def parse_iso_utc(iso_string: str) -> datetime:
    """Parses an ISO 8601 string into a UTC timezone-aware datetime object."""
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_fiscal_quarter(
    target_date: Optional[date] = None, start_month: int = 4
) -> Tuple[int, int]:
    """
    Calculates the Fiscal Year and Quarter for a date (default: Indian FY starting April).

    Args:
        target_date: Target date object (defaults to current UTC date)
        start_month: Month index (1-12) when fiscal year starts (4 for April)

    Returns:
        Tuple[int, int]: (fiscal_year, quarter_number 1-4)
    """
    d = target_date or now_utc().date()
    month = d.month
    year = d.year

    if month >= start_month:
        fiscal_year = year + 1
        quarter = ((month - start_month) // 3) + 1
    else:
        fiscal_year = year
        quarter = ((month + 12 - start_month) // 3) + 1

    return fiscal_year, quarter
