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
            try:
                from app.api.v1.endpoints.market import get_deep_analyze_metrics
                deep = await get_deep_analyze_metrics(symbol, self.market_service)
                deep_metrics = deep.get("metrics", [])
                ad = deep.get("agent_data", {})
                canonical = self.market_service.mapper.to_canonical_symbol(symbol)
                ticker_symbol = self.market_service.mapper.to_yfinance_ticker(symbol)
                
                curr = ad.get("current", {})
                val = ad.get("valuation", {})
                comp = ad.get("company", {})
                health = ad.get("health", {})
                fins = ad.get("financials", [])
                recent_fin = fins[0] if fins else {}

                quote = StockQuote(
                    symbol=ticker_symbol,
                    canonical_symbol=canonical,
                    price=curr.get("price") or 0.0,
                    change=0.0,
                    change_percent=0.0,
                    volume=0,
                    market_cap=curr.get("marketCap"),
                    day_high=curr.get("dayHigh"),
                    day_low=curr.get("dayLow"),
                    fifty_two_week_high=None,
                    fifty_two_week_low=None,
                    currency=curr.get("currency", "INR"),
                )
                
                profile = CompanyInfo(
                    canonical_symbol=canonical,
                    company_name=comp.get("name") or canonical,
                    sector=comp.get("sector"),
                    industry=comp.get("industry"),
                    description=comp.get("description"),
                    website=comp.get("website"),
                    employees=comp.get("employees"),
                    country=comp.get("country"),
                    headquarters=comp.get("headquarters"),
                )

                stats = KeyStatistics(
                    canonical_symbol=canonical,
                    pe_ratio=val.get("trailingPE"),
                    forward_pe=val.get("forwardPE"),
                    peg_ratio=None,
                    eps=recent_fin.get("eps"),
                    beta=None,
                    dividend_yield=None,
                    roe=None,
                    roce=None,
                    pb_ratio=val.get("priceToBook"),
                    profit_margins=None,
                    gross_margins=None,
                    revenue=recent_fin.get("revenue"),
                    ebitda=None,
                    debt_to_equity=health.get("debtToEquity"),
                    current_ratio=health.get("currentRatio"),
                    target_price=None,
                )

                # We still need the chart for visual rendering, but it has its own cache.
                try:
                    chart = await self.market_service.get_chart_data(symbol, period, interval)
                except Exception:
                    chart = HistoricalData(canonical_symbol=canonical, ticker_symbol=ticker_symbol, period=period, interval=interval, series=[])
                
            except Exception as e:
                logger.warning(f"Failed to fetch deep analyze data for {symbol}: {e}")
                deep_metrics = []
                canonical = self.market_service.mapper.to_canonical_symbol(symbol)
                ticker_symbol = self.market_service.mapper.to_yfinance_ticker(symbol)
                quote = StockQuote(symbol=ticker_symbol, canonical_symbol=canonical, price=0.0)
                chart = HistoricalData(canonical_symbol=canonical, ticker_symbol=ticker_symbol, period=period, interval=interval, series=[])
                profile = CompanyInfo(canonical_symbol=canonical, company_name=canonical)
                stats = KeyStatistics(canonical_symbol=canonical)

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
