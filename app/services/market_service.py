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

    async def get_stock_quote(self, symbol: str) -> StockQuote:
        """Get real-time price quote and market metrics for a company symbol.
        
        NOTE: No @cache decorator — cache managed manually to skip poisoned price=0.0 entries.
        """
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)
        
        from app.cache import CacheService, market_quote_key
        quote_cache_key = market_quote_key(ticker_symbol)
        
        async def _fill_missing_change(quote: StockQuote) -> None:
            needs_fill = (
                not quote.previous_close or quote.previous_close == 0.0 or 
                quote.change == 0.0 or quote.change_percent == 0.0 or 
                not quote.day_open or quote.day_open == 0.0
            )
            if needs_fill:
                try:
                    # Fetch 5 days of chart data to safely get the previous close
                    chart = await self.get_chart_data(symbol, period="5d", interval="1d")
                    if chart and chart.series and len(chart.series) >= 1:
                        # The last available bar is the previous close if it's from a prior day,
                        # or it's the current day's latest data. For fallback, data[-1] is the best guess.
                        prev_close = chart.series[-1].close
                        if prev_close and prev_close > 0:
                            if not quote.previous_close or quote.previous_close == 0.0:
                                quote.previous_close = prev_close
                            quote.change = quote.price - prev_close
                            quote.change_percent = (quote.change / prev_close) * 100
                            
                        last_open = chart.series[-1].open
                        if last_open and last_open > 0:
                            if not quote.day_open or quote.day_open == 0.0:
                                quote.day_open = last_open
                except Exception as e:
                    logger.warning(f"Failed to fill missing change data for {ticker_symbol}: {e}")

        # Check market:quote cache first — but skip if price is 0 or missing
        cached_quote = await CacheService.get(quote_cache_key)
        if cached_quote:
            try:
                cached_price = cached_quote.get("price") or 0
                if cached_price > 0:
                    logger.debug(f"Quote cache HIT with real price for {ticker_symbol}")
                    return StockQuote.model_validate(cached_quote)
                else:
                    logger.warning(f"Poisoned quote cache for {ticker_symbol} (price={cached_price}). Deleting.")
                    await CacheService.delete(quote_cache_key)
            except Exception:
                pass
        
        # Priority 1: Check deep_metrics cache (populated by warm_redis or Deep Analyze)
        deep_key = f"market:deep_metrics:{ticker_symbol}"
        cached_deep = await CacheService.get(deep_key)
        
        if cached_deep and cached_deep.get("agent_data"):
            curr = cached_deep["agent_data"].get("current", {})
            price = curr.get("price")
            if price and price > 0:
                sq = StockQuote(
                    symbol=ticker_symbol,
                    canonical_symbol=canonical_symbol,
                    price=price,
                    change=curr.get("change") or 0.0,
                    change_percent=curr.get("change_percent") or 0.0,
                    volume=curr.get("volume") or 0,
                    market_cap=curr.get("marketCap"),
                    day_open=curr.get("dayOpen"),
                    day_high=curr.get("dayHigh"),
                    day_low=curr.get("dayLow"),
                    previous_close=curr.get("previousClose"),
                    fifty_two_week_high=curr.get("fiftyTwoWeekHigh") or curr.get("yearHigh"),
                    fifty_two_week_low=curr.get("fiftyTwoWeekLow") or curr.get("yearLow"),
                    currency=curr.get("currency", "INR"),
                )
                await _fill_missing_change(sq)
                await CacheService.set(quote_cache_key, sq, ttl=300)
                return sq
            else:
                logger.warning(f"Poisoned deep_metrics for {ticker_symbol} (price=0.0). Deleting.")
                await CacheService.delete(deep_key)

        # Priority 2: Live yfinance fetch
        raw_data = await asyncio.to_thread(self.repository.get_current_quote, ticker_symbol)
        quote = StockQuote(
            symbol=ticker_symbol,
            canonical_symbol=canonical_symbol,
            price=raw_data["price"] or 0.0,
            change=raw_data.get("change") or 0.0,
            change_percent=raw_data.get("change_percent") or 0.0,
            volume=raw_data.get("volume") or 0,
            market_cap=raw_data.get("market_cap"),
            day_open=raw_data.get("day_open"),
            day_high=raw_data.get("day_high"),
            day_low=raw_data.get("day_low"),
            previous_close=raw_data.get("previous_close"),
            fifty_two_week_high=raw_data.get("fifty_two_week_high"),
            fifty_two_week_low=raw_data.get("fifty_two_week_low"),
            currency=raw_data.get("currency", "INR"),
        )
        
        await _fill_missing_change(quote)

        # Only cache if we got a real price
        if quote.price and quote.price > 0:
            await CacheService.set(quote_cache_key, quote, ttl=300)
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

    async def get_key_stats(self, symbol: str) -> KeyStatistics:
        """Get financial ratios, valuation metrics, and balance sheet statistics.
        
        Single source of truth: first checks deep_metrics Redis cache (populated by
        warm_redis.py or Deep Analyze), then falls back to live yfinance fetch.
        
        NOTE: No @cache decorator here — we manage the cache manually so stale empty
        entries don't block fresh data from the deep_metrics cache.
        """
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)
        
        # Check market:stats cache first — but only accept it if it has real data
        from app.cache import CacheService, market_stats_key
        stats_cache_key = market_stats_key(ticker_symbol)
        cached_stats = await CacheService.get(stats_cache_key)
        if cached_stats:
            try:
                ks = KeyStatistics.model_validate(cached_stats)
                # Only use if it actually has meaningful data — skip poisoned empty entries
                if any([ks.pe_ratio, ks.roe, ks.profit_margins, ks.debt_to_equity, ks.pb_ratio]):
                    logger.debug(f"KeyStats cache HIT with real data for {ticker_symbol}")
                    return ks
                else:
                    logger.warning(f"KeyStats cache has empty data for {ticker_symbol}, bypassing...")
                    await CacheService.delete(stats_cache_key)
            except Exception:
                pass

        # Priority 1: Extract rich metrics from deep_metrics cache (single source of truth)
        deep_key = f"market:deep_metrics:{ticker_symbol}"
        cached_deep = await CacheService.get(deep_key)
        
        if cached_deep:
            agent_data = cached_deep.get("agent_data", {})
            metrics_list = cached_deep.get("metrics", [])
            
            # Build a lookup from the metrics array: key -> value
            metric_map = {}
            for m in metrics_list:
                mk = m.get("key") or m.get("label", "").replace(" ", "").lower()
                val = m.get("value")
                if val is not None:
                    metric_map[mk] = val
            
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
                
            def _find_pct(*keys):
                val = _find(*keys)
                if val is not None:
                    try:
                        return float(val) / 100.0
                    except (ValueError, TypeError):
                        pass
                return None
            
            stats = KeyStatistics(
                canonical_symbol=canonical_symbol,
                pe_ratio=val_data.get("trailingPE") or _find("peRatio", "trailingPE", "pe_ratio"),
                forward_pe=val_data.get("forwardPE") or _find("forwardPE", "forward_pe"),
                peg_ratio=_find("pegRatio", "peg_ratio"),
                eps=recent_fin.get("eps") or _find("eps", "basicEPS"),
                beta=_find("beta"),
                dividend_yield=_find_pct("dividendYield", "dividend_yield"),
                roe=_find_pct("roe", "returnOnEquity"),
                roce=_find_pct("roce", "returnOnCapitalEmployed"),
                pb_ratio=val_data.get("priceToBook") or _find("priceToBook", "priceToBook", "pb_ratio"),
                profit_margins=_find_pct("netMargin", "profit_margins", "net_margin"),
                gross_margins=_find_pct("grossMargins", "gross_margins", "gross_margin"),
                revenue=recent_fin.get("revenue") or _find("totalRevenue", "revenue"),
                ebitda=_find("ebitda"),
                debt_to_equity=health_data.get("debtToEquity") or _find("debtToEquity", "debt_to_equity"),
                current_ratio=health_data.get("currentRatio") or _find("currentRatio", "current_ratio"),
                target_price=_find("targetHighPrice", "targetMeanPrice", "target_price"),
            )
            
            # Only cache and return if we actually got meaningful data
            has_data = any([stats.pe_ratio, stats.roe, stats.profit_margins, stats.debt_to_equity, stats.pb_ratio])
            if has_data:
                await CacheService.set(stats_cache_key, stats, ttl=86400)
                return stats

        # Priority 2: Live yfinance fetch as fallback
        raw = await asyncio.to_thread(self.repository.get_key_statistics, ticker_symbol)
        result = KeyStatistics(
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
        # Only cache if we got real data from yfinance
        if any([result.pe_ratio, result.roe, result.profit_margins, result.debt_to_equity]):
            await CacheService.set(stats_cache_key, result, ttl=3600)
        return result

