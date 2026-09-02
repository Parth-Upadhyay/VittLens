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
                comp_is_dict = isinstance(comp, dict)
                comp_name = comp.get("name") if comp_is_dict else (comp if isinstance(comp, str) and comp else canonical)
                health = ad.get("health", {}) if isinstance(ad.get("health"), dict) else {}
                fins = ad.get("financials", []) if isinstance(ad.get("financials"), list) else []
                recent_fin = fins[0] if fins and isinstance(fins[0], dict) else {}

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
                    fifty_two_week_high=curr.get("fiftyTwoWeekHigh"),
                    fifty_two_week_low=curr.get("fiftyTwoWeekLow"),
                    currency=curr.get("currency", "INR"),
                )
                
                profile = CompanyInfo(
                    canonical_symbol=canonical,
                    company_name=comp_name or canonical,
                    sector=comp.get("sector") if comp_is_dict else None,
                    industry=comp.get("industry") if comp_is_dict else None,
                    description=comp.get("description") if comp_is_dict else None,
                    website=comp.get("website") if comp_is_dict else None,
                    employees=comp.get("employees") if comp_is_dict else None,
                    country=comp.get("country") if comp_is_dict else None,
                    headquarters=comp.get("headquarters") if comp_is_dict else None,
                )

                metric_map = {m.get("key"): m.get("value") for m in deep_metrics}
                
                stats = KeyStatistics(
                    canonical_symbol=canonical,
                    pe_ratio=val.get("trailingPE") or metric_map.get("trailingPE"),
                    forward_pe=val.get("forwardPE") or metric_map.get("forwardPE"),
                    peg_ratio=metric_map.get("pegRatio"),
                    eps=recent_fin.get("eps") or metric_map.get("eps"),
                    beta=metric_map.get("beta"),
                    dividend_yield=metric_map.get("dividendYield"),
                    roe=metric_map.get("roe"),
                    roce=metric_map.get("roce"),
                    pb_ratio=val.get("priceToBook") or metric_map.get("priceToBook"),
                    profit_margins=metric_map.get("netMargin"),
                    gross_margins=metric_map.get("grossMargins"),
                    revenue=recent_fin.get("revenue"),
                    ebitda=metric_map.get("ebitda"),
                    debt_to_equity=health.get("debtToEquity") or metric_map.get("debtToEquity"),
                    current_ratio=health.get("currentRatio") or metric_map.get("currentRatio"),
                    target_price=metric_map.get("targetHighPrice") or metric_map.get("targetMeanPrice"),
                )

                # We still need the chart for visual rendering, but it has its own cache.
                try:
                    chart = await self.market_service.get_chart_data(symbol, period, interval)
                except Exception:
                    chart = HistoricalData(canonical_symbol=canonical, ticker_symbol=ticker_symbol, period=period, interval=interval, series=[])
                
            except Exception as e:
                logger.warning(f"Failed to fetch deep analyze data for {symbol}: {e}. Falling back to basic quotes.")
                deep_metrics = []
                canonical = self.market_service.mapper.to_canonical_symbol(symbol)
                ticker_symbol = self.market_service.mapper.to_yfinance_ticker(symbol)
                
                try:
                    quote = await self.market_service.get_stock_quote(symbol)
                except Exception:
                    quote = StockQuote(symbol=ticker_symbol, canonical_symbol=canonical, price=0.0)
                    
                try:
                    profile = await self.market_service.get_company_profile(symbol)
                except Exception:
                    profile = CompanyInfo(canonical_symbol=canonical, company_name=canonical)
                    
                try:
                    stats = await self.market_service.get_key_stats(symbol)
                except Exception:
                    stats = KeyStatistics(canonical_symbol=canonical)
                    
                try:
                    chart = await self.market_service.get_chart_data(symbol, period, interval)
                except Exception:
                    chart = HistoricalData(canonical_symbol=canonical, ticker_symbol=ticker_symbol, period=period, interval=interval, series=[])

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
