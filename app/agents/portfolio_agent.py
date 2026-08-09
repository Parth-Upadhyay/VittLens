"""
PortfolioAgent - Independent analysis agent for portfolio holdings.
Loads static universe data from app/data/universe.json.
Concurrently fetches market, news, and quant data across holdings.
Calculates allocation & risk metrics, and calls Groq LLM exactly once for synthesis.
Refactored to use LangGraph StateGraph orchestration.
"""

import json
import os
import re
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from app.config.settings import Settings
from app.services.market_service import MarketService
from app.services.news_service import NewsService
from app.services.quant_service import QuantService
from app.services.groq_service import GroqProvider
from app.prompts import PromptBuilder
from app.prompts import FINANCIAL_ANALYST_SYSTEM_PROMPT
from app.schemas import (
    HoldingInput,
    HoldingAnalysis,
    PortfolioMetrics,
    AllocationBreakdown,
    PortfolioAnalysisResponse,
    BenchmarkComparison,
    TaxLossHarvestingAlert,
)
from app.schemas import PortfolioState
from app.utils import CompanyNormalizer
from app.utils import get_logger

logger = get_logger("finnai.portfolio_agent")


class PortfolioAgent:
    """
    Standalone agent for comprehensive portfolio evaluation.
    Orchestrated by LangGraph StateGraph.
    """

    def __init__(self, settings: Optional[Settings] = None, db: Optional[Session] = None) -> None:
        self.settings = settings or Settings()
        self.db = db
        self.market_service = MarketService(self.settings)
        self.quant_service = QuantService()
        self.normalizer = CompanyNormalizer()
        self.llm_provider = GroqProvider(settings=self.settings)
        self.universe = self._load_universe()
        
        # Compile LangGraph StateGraph
        self.graph = self._build_graph()

    def _load_universe(self) -> Dict[str, Any]:
        """Load static universe JSON from app/data/universe.json into memory."""
        universe_path = os.path.join("app", "data", "universe.json")
        if not os.path.exists(universe_path):
            universe_path = os.path.join("data", "universe.json")

        if os.path.exists(universe_path):
            try:
                with open(universe_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load static universe JSON from '{universe_path}': {e}")

        # Fallback inline universe structure
        return {"stocks": {}, "etfs": {}, "mutual_funds": {}}

    def _lookup_asset_info(self, symbol: str) -> Dict[str, Any]:
        """Lookup metadata (type, sector, name) from static universe."""
        canonical = self.normalizer.normalize(symbol) or symbol.upper()

        if canonical in self.universe.get("stocks", {}):
            data = self.universe["stocks"][canonical]
            return {"type": "stock", "sector": data.get("sector", "Equity"), "name": data.get("name", symbol)}
        elif canonical in self.universe.get("etfs", {}):
            data = self.universe["etfs"][canonical]
            return {"type": "etf", "sector": "Broad Market ETF", "name": data.get("name", symbol)}
        elif canonical in self.universe.get("mutual_funds", {}):
            data = self.universe["mutual_funds"][canonical]
            return {"type": "mf", "sector": "Mutual Fund", "name": data.get("name", symbol)}

        return {"type": "stock", "sector": "Other", "name": symbol}

    def _analyze_single_holding(self, h: HoldingInput, news_service: Optional[NewsService]) -> HoldingAnalysis:
        """Fetch market, news, and quant data for a single holding."""
        canonical = self.normalizer.normalize(h.symbol) or h.symbol.upper()
        meta = self._lookup_asset_info(canonical)

        # 1. Fetch Market Quote
        try:
            import asyncio
            quote = asyncio.run(self.market_service.get_stock_quote(canonical))
            current_price = quote.price if quote and quote.price > 0 else h.avg_buy_price
            day_change = quote.change if quote else 0.0
        except Exception:
            current_price = h.avg_buy_price
            day_change = 0.0

        total_invested = h.quantity * h.avg_buy_price
        current_value = h.quantity * current_price
        pnl = current_value - total_invested
        pnl_percent = (pnl / total_invested * 100.0) if total_invested > 0 else 0.0

        # 2. Fetch News Summary
        news_summary = ""
        if news_service:
            articles = news_service.get_latest_by_symbol(symbol=canonical, limit=5)
            if articles:
                news_summary = articles[0].headline

        # 3. Quant Ratios
        pe_ratio = None
        debt_to_equity = None
        if meta["type"] == "stock":
            try:
                import asyncio
                snapshot = asyncio.run(self.quant_service.get_full_ratio_snapshot(canonical))
                pe_ratio = snapshot.valuation.pe_ratio
                debt_to_equity = snapshot.leverage.debt_to_equity
            except Exception:
                pass

        return HoldingAnalysis(
            symbol=canonical,
            name=h.name or meta["name"],
            asset_type=meta["type"],
            quantity=h.quantity,
            avg_buy_price=h.avg_buy_price,
            current_price=round(current_price, 2),
            total_invested=round(total_invested, 2),
            current_value=round(current_value, 2),
            pnl=round(pnl, 2),
            pnl_percent=round(pnl_percent, 2),
            day_change=round(day_change, 2),
            weight_percent=0.0,
            sector=meta["sector"],
            pe_ratio=pe_ratio,
            debt_to_equity=debt_to_equity,
            news_summary=news_summary,
        )

    # --- LangGraph Nodes ---

    def node_validate(self, state: PortfolioState) -> PortfolioState:
        holdings = state["holdings_input"]
        errors = []
        for h in holdings:
            raw_sym = h.symbol.upper().strip()
            canonical = self.normalizer.normalize(raw_sym) or raw_sym
            is_valid = (
                canonical in self.universe.get("stocks", {})
                or canonical in self.universe.get("etfs", {})
                or canonical in self.universe.get("mutual_funds", {})
                or raw_sym in self.universe.get("stocks", {})
                or raw_sym in self.universe.get("etfs", {})
                or raw_sym in self.universe.get("mutual_funds", {})
            )
            if not is_valid:
                errors.append(f"Unrecognized symbol '{h.symbol}'. Symbol is not present in static Universe.")

        if errors:
            raise ValueError(" | ".join(errors))
            
        return state

    def node_fetch_data(self, state: PortfolioState) -> PortfolioState:
        news_service = NewsService(state["db_session"]) if state["db_session"] else None
        analyzed_holdings: List[HoldingAnalysis] = []
        news_alerts: Dict[str, List[str]] = {}

        with ThreadPoolExecutor(max_workers=min(len(state["holdings_input"]), 10)) as executor:
            future_to_h = {
                executor.submit(self._analyze_single_holding, h, news_service): h
                for h in state["holdings_input"]
            }
            for future in as_completed(future_to_h):
                try:
                    res = future.result()
                    analyzed_holdings.append(res)
                    if news_service:
                        arts = news_service.get_latest_by_symbol(symbol=res.symbol, limit=5)
                        if arts:
                            news_alerts[res.symbol] = [a.headline for a in arts]
                except Exception as exc:
                    h = future_to_h[future]
                    logger.error(f"Error analyzing holding '{h.symbol}': {exc}")
                    
        return {"analyzed_holdings": analyzed_holdings, "news_alerts": news_alerts}

    def node_compute_metrics(self, state: PortfolioState) -> PortfolioState:
        analyzed_holdings = state["analyzed_holdings"]
        
        total_invested = sum(h.total_invested for h in analyzed_holdings)
        total_value = sum(h.current_value for h in analyzed_holdings)
        total_pnl = total_value - total_invested
        total_pnl_percent = (total_pnl / total_invested * 100.0) if total_invested > 0 else 0.0
        day_pnl = sum(h.day_change * h.quantity for h in analyzed_holdings)

        sector_totals: Dict[str, float] = {}
        asset_totals: Dict[str, float] = {}
        max_exposure = 0.0

        for h in analyzed_holdings:
            weight = (h.current_value / total_value * 100.0) if total_value > 0 else 0.0
            h.weight_percent = round(weight, 2)
            if weight > max_exposure:
                max_exposure = weight

            sector_totals[h.sector] = sector_totals.get(h.sector, 0.0) + h.current_value
            asset_totals[h.asset_type] = asset_totals.get(h.asset_type, 0.0) + h.current_value

        sector_breakdown = {k: round(v / total_value * 100.0, 2) if total_value > 0 else 0.0 for k, v in sector_totals.items()}
        asset_type_breakdown = {k: round(v / total_value * 100.0, 2) if total_value > 0 else 0.0 for k, v in asset_totals.items()}

        risk_score = 5
        if max_exposure > 40.0: risk_score += 2
        elif max_exposure > 25.0: risk_score += 1

        if len(sector_breakdown) < 3: risk_score += 2
        elif len(sector_breakdown) > 6: risk_score -= 1

        high_debt_count = sum(1 for h in analyzed_holdings if h.debt_to_equity and h.debt_to_equity > 1.5)
        if high_debt_count > 0: risk_score += 1
        risk_score = max(1, min(10, risk_score))

        metrics = PortfolioMetrics(
            total_value=round(total_value, 2),
            total_invested=round(total_invested, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_percent=round(total_pnl_percent, 2),
            day_pnl=round(day_pnl, 2),
            risk_score=risk_score,
            concentration_risk_percent=round(max_exposure, 2),
        )

        allocation = AllocationBreakdown(
            sector_breakdown=sector_breakdown,
            asset_type_breakdown=asset_type_breakdown,
        )

        tax_loss_harvesting: List[TaxLossHarvestingAlert] = []
        for h in analyzed_holdings:
            if h.pnl < 0:
                unrealized_loss = round(abs(h.pnl), 2)
                unrealized_loss_pct = round(abs(h.pnl_percent), 2)
                stcg_saving = round(unrealized_loss * 0.20, 2)
                ltcg_saving = round(unrealized_loss * 0.125, 2)
                rec = (f"Sell {h.symbol} position to harvest ₹{unrealized_loss:,.2f} unrealized loss. "
                       f"Offsets capital gains tax, saving up to ₹{stcg_saving:,.2f} STCG or ₹{ltcg_saving:,.2f} LTCG tax.")
                tax_loss_harvesting.append(
                    TaxLossHarvestingAlert(
                        symbol=h.symbol, name=h.name, unrealized_loss=unrealized_loss,
                        unrealized_loss_percent=unrealized_loss_pct, est_stcg_tax_saving=stcg_saving,
                        est_ltcg_tax_saving=ltcg_saving, recommendation=rec,
                    )
                )

        return {
            "analyzed_holdings": analyzed_holdings,
            "metrics": metrics,
            "allocation": allocation,
            "tax_loss_harvesting": tax_loss_harvesting
        }

    def node_fetch_benchmarks(self, state: PortfolioState) -> PortfolioState:
        nifty_benchmarks = []
        try:
            import asyncio
            chart = asyncio.run(self.market_service.get_chart_data("^NSEI", period="1y", interval="1d"))
            if chart and chart.series and len(chart.series) > 0:
                latest_close = chart.series[-1].close or 0.0
                idx_1m = max(0, len(chart.series) - 21)
                close_1m = chart.series[idx_1m].close or latest_close
                ret_1m = ((latest_close - close_1m) / close_1m * 100.0) if close_1m else 0.0
                
                idx_6m = max(0, len(chart.series) - 126)
                close_6m = chart.series[idx_6m].close or latest_close
                ret_6m = ((latest_close - close_6m) / close_6m * 100.0) if close_6m else 0.0
                
                close_1y = chart.series[0].close or latest_close
                ret_1y = ((latest_close - close_1y) / close_1y * 100.0) if close_1y else 0.0
                
                nifty_benchmarks = [
                    {"period": "1M", "nifty_return": round(ret_1m, 2)},
                    {"period": "6M", "nifty_return": round(ret_6m, 2)},
                    {"period": "1Y", "nifty_return": round(ret_1y, 2)},
                ]
        except Exception as exc:
            logger.warning(f"Failed to fetch NIFTY benchmark: {exc}")
            
        if not nifty_benchmarks:
            nifty_benchmarks = [
                {"period": "1M", "nifty_return": 1.8},
                {"period": "6M", "nifty_return": 6.5},
                {"period": "1Y", "nifty_return": 14.2},
            ]

        benchmark_comparison: List[BenchmarkComparison] = []
        port_ret = state["metrics"].total_pnl_percent
        for b in nifty_benchmarks:
            nifty_ret = b["nifty_return"]
            outperformance = round(port_ret - nifty_ret, 2)
            benchmark_comparison.append(
                BenchmarkComparison(
                    period=b["period"], portfolio_return_percent=port_ret,
                    nifty50_return_percent=nifty_ret, outperformance_percent=outperformance,
                )
            )

        return {"benchmark_comparison": benchmark_comparison}

    def node_synthesize(self, state: PortfolioState) -> PortfolioState:
        metrics = state["metrics"]
        allocation = state["allocation"]
        analyzed_holdings = state["analyzed_holdings"]
        news_alerts = state["news_alerts"]

        instructions = """\
Analyze the portfolio metrics and holdings data.
Output ONLY a raw JSON object (no markdown, no extra text) matching this schema:
{
  "summary": "Professional executive summary of portfolio health, valuation, and performance",
  "rebalancing_suggestions": [
    "Actionable rebalancing suggestion 1"
  ],
  "red_flags": [
    "Risk warning or concentration alert 1"
  ]
}
"""
        evidence = {
            "metrics": metrics.model_dump(),
            "allocation": allocation.model_dump(),
            "holdings": [h.model_dump() for h in analyzed_holdings],
            "recent_news": news_alerts,
        }

        prompt_builder = (
            PromptBuilder()
            .with_question("Synthesize portfolio health, risk score, and recommendations.")
            .with_evidence(evidence)
            .with_instructions(instructions)
        )
        user_prompt = prompt_builder.build()

        try:
            response = self.llm_provider.generate(
                system_prompt=FINANCIAL_ANALYST_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2,
            )
            content = response.content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n?", "", content)
                content = re.sub(r"\n?```$", "", content)
            parsed = json.loads(content)
        except Exception as exc:
            logger.warning(f"Groq LLM portfolio synthesis failed: {exc}. Using fallback.")
            red_flags = []
            if metrics.concentration_risk_percent > 30.0:
                red_flags.append(f"High concentration risk: Single position represents {metrics.concentration_risk_percent}% of total portfolio.")
            if metrics.risk_score >= 7:
                red_flags.append(f"Elevated risk score ({metrics.risk_score}/10) due to sector concentration or high debt levels.")

            parsed = {
                "summary": f"Portfolio total value is ₹{metrics.total_value:,.2f} with an overall P&L of ₹{metrics.total_pnl:,.2f} ({metrics.total_pnl_percent}%). Portfolio risk score is rated {metrics.risk_score}/10.",
                "rebalancing_suggestions": [
                    "Consider trimming positions exceeding 25% of total portfolio value to lower concentration risk.",
                    "Diversify holdings across non-correlated sectors."
                ],
                "red_flags": red_flags if red_flags else ["No immediate critical red flags detected."],
            }

        final_response = PortfolioAnalysisResponse(
            summary=parsed.get("summary", "Portfolio analysis completed successfully."),
            holdings=analyzed_holdings,
            portfolio_metrics=metrics,
            allocation=allocation,
            rebalancing_suggestions=parsed.get("rebalancing_suggestions", []),
            news_alerts=news_alerts,
            red_flags=parsed.get("red_flags", []),
            benchmark_comparison=state["benchmark_comparison"],
            tax_loss_harvesting=state["tax_loss_harvesting"],
            images=[],
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

        return {"final_response": final_response}

    def _build_graph(self):
        """Compile the LangGraph StateGraph."""
        builder = StateGraph(PortfolioState)
        
        # Add Nodes
        builder.add_node("validate", self.node_validate)
        builder.add_node("fetch_data", self.node_fetch_data)
        builder.add_node("compute_metrics", self.node_compute_metrics)
        builder.add_node("fetch_benchmarks", self.node_fetch_benchmarks)
        builder.add_node("synthesize", self.node_synthesize)
        
        # Add Edges
        builder.set_entry_point("validate")
        builder.add_edge("validate", "fetch_data")
        builder.add_edge("fetch_data", "compute_metrics")
        builder.add_edge("compute_metrics", "fetch_benchmarks")
        builder.add_edge("fetch_benchmarks", "synthesize")
        builder.add_edge("synthesize", END)
        
        return builder.compile()

    def analyze_portfolio(self, holdings_input: List[HoldingInput]) -> PortfolioAnalysisResponse:
        """
        Execute LangGraph portfolio analysis orchestration.
        """
        initial_state = {
            "holdings_input": holdings_input,
            "db_session": self.db
        }
        
        # Invoke LangGraph
        result_state = self.graph.invoke(initial_state)
        
        return result_state["final_response"]
