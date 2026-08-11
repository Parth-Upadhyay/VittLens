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
            price = curr.get("price")
            # Guard: skip poisoned cache entries where Yahoo returned 0.0 or None
            if price and price > 0:
                return StockQuote(
                    symbol=ticker_symbol,
                    canonical_symbol=canonical_symbol,
                    price=price,
                    change=curr.get("change") or 0.0,
                    change_percent=curr.get("change_percent") or 0.0,
                    volume=curr.get("volume") or 0,
                    market_cap=curr.get("marketCap"),
                    day_high=curr.get("dayHigh"),
                    day_low=curr.get("dayLow"),
                    fifty_two_week_high=curr.get("fiftyTwoWeekHigh") or curr.get("yearHigh"),
                    fifty_two_week_low=curr.get("fiftyTwoWeekLow") or curr.get("yearLow"),
                    currency=curr.get("currency", "INR"),
                )
            else:
                # Poisoned cache — delete it so next call re-fetches
                logger.warning(f"Poisoned deep_metrics cache for {ticker_symbol} (price=0.0). Deleting.")
                await CacheService.delete(deep_key)

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
        """Get financial ratios, valuation metrics, and balance sheet statistics.
        
        Single source of truth: first checks deep_metrics Redis cache (populated by
        warm_redis.py or Deep Analyze), then falls back to live yfinance fetch.
        """
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)
        
        # Single source of truth: extract rich metrics from deep_metrics cache
        from app.cache import CacheService
        deep_key = f"market:deep_metrics:{ticker_symbol}"
        cached_deep = await CacheService.get(deep_key)
        
        if cached_deep:
            agent_data = cached_deep.get("agent_data", {})
            metrics_list = cached_deep.get("metrics", [])
            
            # Build a lookup from the metrics array: key -> value
            metric_map = {}
            for m in metrics_list:
                key = m.get("key") or m.get("label", "").replace(" ", "").lower()
                val = m.get("value")
                if val is not None:
                    metric_map[key] = val
            
            val_data = agent_data.get("valuation", {})
            health_data = agent_data.get("health", {})
            fins = agent_data.get("financials", [])
            recent_fin = fins[0] if fins else {}
            
            # Helper to find a metric by checking multiple possible keys
            def _find(*keys):
                for k in keys:
                    v = metric_map.get(k)
                    if v is not None:
                        return v
                return None
            
            stats = KeyStatistics(
                canonical_symbol=canonical_symbol,
                pe_ratio=val_data.get("trailingPE") or _find("trailingPE", "pe_ratio"),
                forward_pe=val_data.get("forwardPE") or _find("forwardPE", "forward_pe"),
                peg_ratio=_find("pegRatio", "peg_ratio"),
                eps=recent_fin.get("eps") or _find("eps", "basicEPS"),
                beta=_find("beta"),
                dividend_yield=_find("dividendYield", "dividend_yield"),
                roe=_find("roe", "returnOnEquity"),
                roce=_find("roce", "returnOnCapitalEmployed"),
                pb_ratio=val_data.get("priceToBook") or _find("priceToBook", "pb_ratio"),
                profit_margins=_find("netMargin", "profit_margins", "net_margin"),
                gross_margins=_find("grossMargins", "gross_margins", "gross_margin"),
                revenue=recent_fin.get("revenue") or _find("totalRevenue", "revenue"),
                ebitda=_find("ebitda"),
                debt_to_equity=health_data.get("debtToEquity") or _find("debtToEquity", "debt_to_equity"),
                current_ratio=health_data.get("currentRatio") or _find("currentRatio", "current_ratio"),
                target_price=_find("targetHighPrice", "targetMeanPrice", "target_price"),
            )
            
            # Only return if we actually got meaningful data
            has_data = any([stats.pe_ratio, stats.roe, stats.profit_margins, stats.debt_to_equity])
            if has_data:
                return stats

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

