"""
Primitive schemas and value objects for financial domain data models.
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import Field, field_validator

from core.config.constants import Currency, DEFAULT_CURRENCY
from core.schemas.base import CoreBaseModel


class MonetaryAmount(CoreBaseModel):
    """Value object representing a monetary figure with strict currency declaration."""

    amount: float = Field(description="Numerical monetary value")
    currency: Currency = Field(
        default=DEFAULT_CURRENCY, description="ISO 4217 Currency code"
    )

    @property
    def formatted(self) -> str:
        """Returns clean string format (e.g., 'INR 1,000,000.00')."""
        return f"{self.currency.value} {self.amount:,.2f}"


class TickerSymbol(CoreBaseModel):
    """Financial asset ticker identification schema."""

    symbol: str = Field(description="Normalized stock symbol (e.g. RELIANCE, INFY, AAPL)")
    exchange: Optional[str] = Field(
        default=None, description="Exchange code (e.g. NSE, BSE, NASDAQ, NYSE)"
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Ticker symbol cannot be empty")
        return cleaned

    @property
    def full_ticker(self) -> str:
        return f"{self.exchange}:{self.symbol}" if self.exchange else self.symbol


class DateRange(CoreBaseModel):
    """Bounded date window for financial reporting and time-series analysis."""

    start_date: date = Field(description="Period start date")
    end_date: date = Field(description="Period end date")

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date cannot precede start_date")
        return v


class FinancialPeriod(CoreBaseModel):
    """Fiscal reporting timeframe primitive (e.g., FY2024 Q3)."""

    fiscal_year: int = Field(ge=1900, le=2100, description="Four-digit fiscal year")
    quarter: Optional[int] = Field(
        default=None, ge=1, le=4, description="Fiscal quarter (1-4, optional)"
    )
    period_type: str = Field(
        default="FY",
        description="Period classifier (e.g., 'ANNUAL', 'QUARTERLY', 'TTM')",
    )

    @property
    def label(self) -> str:
        if self.quarter:
            return f"FY{self.fiscal_year} Q{self.quarter}"
        return f"FY{self.fiscal_year}"


class SourceCitation(CoreBaseModel):
    """Metadata attribution for extracted financial facts and RAG responses."""

    title: str = Field(description="Source document title or report section name")
    url: Optional[str] = Field(default=None, description="Direct web link to source document")
    page_number: Optional[int] = Field(default=None, description="PDF or document page index")
    document_id: Optional[str] = Field(
        default=None, description="Unique document vector/blob reference ID"
    )
