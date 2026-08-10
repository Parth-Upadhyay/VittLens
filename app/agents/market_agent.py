"""
Market Agent for FinnAI Platform.
Consumes MarketService exclusively to fetch real-time quotes, charts, profiles, and key statistics.
Returns structured Pydantic models only (zero LLM calls, zero natural language generation).
"""

import asyncio
from typing import Optional
from app.agents.base_agent import BaseAgent
from app.config.settings import Settings
from app.schemas import AgentContext, MarketAgentResult
from app.schemas import CompanyInfo, HistoricalData, KeyStatistics, StockQuote
from app.services.market_service import MarketService
from app.utils import get_logger

logger = get_logger("finnai.agents.market")


class MarketAgent(BaseAgent):
    """
    Market Domain Agent providing structured market data for target company symbols.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        market_service: Optional[MarketService] = None,
    ) -> None:
        super().__init__(name="MarketAgent", settings=settings)
        self.market_service = market_service or MarketService(self.settings)

    async def _execute(self, context: AgentContext) -> MarketAgentResult:
        """
        Execute market data retrieval for target symbols in context.
        """
        quotes: dict[str, StockQuote] = {}
        charts: dict[str, HistoricalData] = {}
        profiles: dict[str, CompanyInfo] = {}
        key_stats: dict[str, KeyStatistics] = {}
        raw_metrics: dict[str, list] = {}

        symbols = context.symbols or ["RELIANCE"]
        period = context.period or "1mo"
        interval = context.interval or "1d"

        for symbol in symbols:
            # Execute async MarketService queries directly
            quote = await self.market_service.get_stock_quote(symbol)
            chart = await self.market_service.get_chart_data(symbol, period, interval)
            profile = await self.market_service.get_company_profile(symbol)
            stats = await self.market_service.get_key_stats(symbol)
            
            try:
                from app.api.v1.endpoints.market import get_deep_analyze
                deep = await get_deep_analyze(symbol, self.market_service)
                deep_metrics = deep.get("metrics", [])
            except Exception as e:
                logger.warning(f"Failed to fetch deep analyze data for {symbol}: {e}")
                deep_metrics = []

            canonical = quote.canonical_symbol
            quotes[canonical] = quote
            charts[canonical] = chart
            profiles[canonical] = profile
            key_stats[canonical] = stats
            raw_metrics[canonical] = deep_metrics

        return MarketAgentResult(
            quotes=quotes,
            charts=charts,
            profiles=profiles,
            key_stats=key_stats,
            raw_metrics=raw_metrics,
        )
