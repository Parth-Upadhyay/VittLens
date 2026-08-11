"""
Market Service layer for FinnAI Platform.
Encapsulates real-time market data retrieval, in-memory TTL caching, and schema parsing.
Strictly decoupled from LLMs (no LLM calls or natural language generation).
Consumes MarketRepository exclusively for yfinance data fetching.
"""

import asyncio
from typing import Any, Dict, List, Optional
from app.config.settings import Settings
from app.repositories import MarketRepository
from app.schemas import (
    CompanyInfo,
    HistoricalData,
    KeyStatistics,
    OHLCV,
    StockQuote,
)
from app.utils import get_logger
from app.utils import MarketSymbolMapper
from app.cache import cache
from app.cache import market_quote_key, market_chart_key, market_profile_key, market_stats_key

logger = get_logger("finnai.market_service")


class MarketService:
    """
    Business service providing real-time stock quotes, historical OHLCV series,
    company profiles, and financial key statistics.
    Uses robust async Redis caching to prevent hammering yfinance.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        repository: Optional[MarketRepository] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.repository = repository or MarketRepository(self.settings)
        self.mapper = MarketSymbolMapper(self.settings)

    @cache(ttl=300, key_builder=lambda self, symbol: market_quote_key(self.mapper.to_yfinance_ticker(symbol)), response_model=StockQuote)
    async def get_stock_quote(self, symbol: str) -> StockQuote:
        """Get real-time price quote and market metrics for a company symbol."""
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)
        
        # Check the 24-hour deep metrics cache first (populated by pre-warmer or deep analyze)
        from app.cache import CacheService
        deep_key = f"market:deep_metrics:{ticker_symbol}"
        cached_deep = await CacheService.get(deep_key)
        
        if cached_deep and cached_deep.get("agent_data"):
            curr = cached_deep["agent_data"].get("current", {})
            return StockQuote(
                symbol=ticker_symbol,
                canonical_symbol=canonical_symbol,
                price=curr.get("price") or 0.0,
                change=curr.get("change") or 0.0,
                change_percent=curr.get("change_percent") or 0.0,
                volume=0,
                market_cap=curr.get("marketCap"),
                day_high=curr.get("dayHigh"),
                day_low=curr.get("dayLow"),
                fifty_two_week_high=None,
                fifty_two_week_low=None,
                currency=curr.get("currency", "INR"),
            )

        raw_data = await asyncio.to_thread(self.repository.get_current_quote, ticker_symbol)
        quote = StockQuote(
            symbol=ticker_symbol,
            canonical_symbol=canonical_symbol,
            price=raw_data["price"] or 0.0,
            change=raw_data.get("change") or 0.0,
            change_percent=raw_data.get("change_percent") or 0.0,
            volume=raw_data.get("volume") or 0,
            market_cap=raw_data.get("market_cap"),
            day_high=raw_data.get("day_high"),
            day_low=raw_data.get("day_low"),
            fifty_two_week_high=raw_data.get("fifty_two_week_high"),
            fifty_two_week_low=raw_data.get("fifty_two_week_low"),
            currency=raw_data.get("currency", "INR"),
        )
        return quote

    @cache(ttl=3600, key_builder=lambda self, symbol, period="1mo", interval="1d": market_chart_key(self.mapper.to_yfinance_ticker(symbol), period, interval), response_model=HistoricalData)
    async def get_chart_data(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> HistoricalData:
        """Get historical OHLCV candlestick time series."""
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)

        raw_bars = await asyncio.to_thread(
            self.repository.get_historical_data,
            ticker_symbol=ticker_symbol, period=period, interval=interval
        )
        series = [OHLCV.model_validate(b) for b in raw_bars]

        return HistoricalData(
            canonical_symbol=canonical_symbol,
            ticker_symbol=ticker_symbol,
            period=period,
            interval=interval,
            series=series,
        )

    @cache(ttl=86400, key_builder=lambda self, symbol: market_profile_key(self.mapper.to_yfinance_ticker(symbol)), response_model=CompanyInfo)
    async def get_company_profile(self, symbol: str) -> CompanyInfo:
        """Get company profile, sector, industry, and operational details."""
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)

        raw = await asyncio.to_thread(self.repository.get_company_info, ticker_symbol)
        return CompanyInfo(
            canonical_symbol=canonical_symbol,
            company_name=raw.get("company_name", canonical_symbol),
            sector=raw.get("sector"),
            industry=raw.get("industry"),
            description=raw.get("description"),
            website=raw.get("website"),
            employees=raw.get("employees"),
            country=raw.get("country"),
            headquarters=raw.get("headquarters"),
        )

    @cache(ttl=86400, key_builder=lambda self, symbol: market_stats_key(self.mapper.to_yfinance_ticker(symbol)), response_model=KeyStatistics)
    async def get_key_stats(self, symbol: str) -> KeyStatistics:
        """Get financial ratios, valuation metrics, and balance sheet statistics."""
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)

        raw = await asyncio.to_thread(self.repository.get_key_statistics, ticker_symbol)
        return KeyStatistics(
            canonical_symbol=canonical_symbol,
            pe_ratio=raw.get("pe_ratio"),
            forward_pe=raw.get("forward_pe"),
            peg_ratio=raw.get("peg_ratio"),
            eps=raw.get("eps"),
            beta=raw.get("beta"),
            dividend_yield=raw.get("dividend_yield"),
            roe=raw.get("roe"),
            roce=raw.get("roce"),
            pb_ratio=raw.get("pb_ratio"),
            profit_margins=raw.get("profit_margins"),
            gross_margins=raw.get("gross_margins"),
            revenue=raw.get("revenue"),
            ebitda=raw.get("ebitda"),
            debt_to_equity=raw.get("debt_to_equity"),
            current_ratio=raw.get("current_ratio"),
            target_price=raw.get("target_price"),
        )
