"""
Quant Service layer for FinnAI Platform.
Consumes MarketService to fetch market data and passes raw parameters into QuantEngine.
Returns structured Pydantic models ONLY (zero LLM calls, zero natural language generation).
Includes in-memory TTL caching layer.
"""

import time
from typing import Any, Dict, List, Optional

from app.config.settings import Settings
from app.core.quant_engine import QuantEngine
from app.schemas import (
    DividendMetrics,
    EfficiencyRatios,
    GrowthMetrics,
    LeverageRatios,
    ProfitabilityRatios,
    QuantComparison,
    RatioSnapshot,
    ValuationRatios,
)
from app.services.market_service import MarketService
from app.utils import get_logger
from app.utils import MarketSymbolMapper

logger = get_logger("finnai.quant_service")


class QuantService:
    """
    Business service executing quantitative analysis, financial ratio calculation,
    and multi-company side-by-side comparison.
    Consumes MarketService exclusively for underlying market data.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        market_service: Optional[MarketService] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.market_service = market_service or MarketService(self.settings)
        self.mapper = MarketSymbolMapper(self.settings)
        self.cache_ttl = self.settings.yfinance_cache_ttl_seconds

        # In-memory cache store: { cache_key: (timestamp, model) }
        self._cache: Dict[str, tuple[float, Any]] = {}

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Retrieve non-expired item from in-memory cache."""
        if cache_key in self._cache:
            ts, item = self._cache[cache_key]
            if time.time() - ts < self.cache_ttl:
                logger.debug(f"QuantService cache HIT for '{cache_key}'.")
                return item
            else:
                del self._cache[cache_key]
        return None

    def _set_in_cache(self, cache_key: str, item: Any) -> None:
        """Store item in in-memory cache with timestamp."""
        self._cache[cache_key] = (time.time(), item)

    def clear_cache(self) -> None:
        """Clear all in-memory cached ratio snapshots."""
        self._cache.clear()
        logger.info("QuantService in-memory cache cleared.")

    async def _extract_raw_financial_dict(self, symbol: str) -> tuple[str, str, Dict[str, Any]]:
        """
        Helper extracting raw market quote and key stats from MarketService into a dictionary.
        """
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)

        quote = await self.market_service.get_stock_quote(symbol)
        stats = await self.market_service.get_key_stats(symbol)

        raw_data: Dict[str, Any] = {
            "price": quote.price,
            "market_cap": quote.market_cap,
            "pe_ratio": stats.pe_ratio,
            "forward_pe": stats.forward_pe,
            "peg_ratio": stats.peg_ratio,
            "eps": stats.eps,
            "eps_current": stats.eps,
            "beta": stats.beta,
            "dividend_yield": stats.dividend_yield,
            "roe": stats.roe,
            "roce": stats.roce,
            "pb_ratio": stats.pb_ratio,
            "profit_margins": stats.profit_margins,
            "gross_margins": stats.gross_margins,
            "revenue": stats.revenue,
            "revenue_current": stats.revenue,
            "ebitda": stats.ebitda,
            "debt_to_equity": stats.debt_to_equity,
            "current_ratio": stats.current_ratio,
            "target_price": stats.target_price,
        }

        return canonical_symbol, ticker_symbol, raw_data

    async def get_full_ratio_snapshot(self, symbol: str) -> RatioSnapshot:
        """
        Get comprehensive quantitative financial ratio snapshot for a company.

        Args:
            symbol: Canonical symbol (e.g. 'RELIANCE') or ticker ('RELIANCE.NS').

        Returns:
            RatioSnapshot Pydantic model.
        """
        canonical_symbol = self.mapper.to_canonical_symbol(symbol)
        cache_key = f"quant:snapshot:{canonical_symbol}"

        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        canonical, ticker, raw_data = await self._extract_raw_financial_dict(symbol)
        snapshot = QuantEngine.compute_full_snapshot(
            canonical_symbol=canonical, ticker_symbol=ticker, raw_data=raw_data
        )

        self._set_in_cache(cache_key, snapshot)
        return snapshot

    async def get_profitability_ratios(self, symbol: str) -> ProfitabilityRatios:
        """
        Get profitability and margin analysis subset.
        """
        snapshot = await self.get_full_ratio_snapshot(symbol)
        return snapshot.profitability

    async def get_valuation_ratios(self, symbol: str) -> ValuationRatios:
        """
        Get valuation multiples and price metrics subset.
        """
        snapshot = await self.get_full_ratio_snapshot(symbol)
        return snapshot.valuation

    async def get_growth_metrics(self, symbol: str) -> GrowthMetrics:
        """
        Get historical growth CAGR and YoY growth metrics subset.
        """
        snapshot = await self.get_full_ratio_snapshot(symbol)
        return snapshot.growth

    async def get_leverage_ratios(self, symbol: str) -> LeverageRatios:
        """
        Get financial leverage, solvency, and liquidity subset.
        """
        snapshot = await self.get_full_ratio_snapshot(symbol)
        return snapshot.leverage

    async def compare_symbols(self, symbols: List[str]) -> QuantComparison:
        """
        Generate side-by-side financial ratio snapshot comparisons for a list of company symbols.

        Args:
            symbols: List of company symbols (e.g. ['RELIANCE', 'TCS', 'HDFCBANK']).

        Returns:
            QuantComparison Pydantic model containing a map of canonical symbols to RatioSnapshots.
        """
        canonical_symbols = [self.mapper.to_canonical_symbol(s) for s in symbols]
        logger.info(f"Generating side-by-side quantitative comparison for symbols: {canonical_symbols}")

        metrics_map: Dict[str, RatioSnapshot] = {}
        for sym in symbols:
            canonical = self.mapper.to_canonical_symbol(sym)
            metrics_map[canonical] = await self.get_full_ratio_snapshot(sym)

        return QuantComparison(
            symbols=canonical_symbols,
            metrics_comparison=metrics_map,
        )
