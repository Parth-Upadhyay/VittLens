"""
Deterministic Rule-Based Planner for FinnAI Platform.
Extracts company symbols from natural language queries using CompanyNormalizer
and generates an optimal multi-agent execution Plan without requiring LLM pre-planning overhead.
"""

import json
import os
import re
from typing import List, Optional, Set
from app.config.settings import Settings
from app.schemas import AgentTask, ChatRequest, Plan
from app.utils import CompanyNormalizer
from app.utils import get_logger

logger = get_logger("finnai.planner")


class Planner:
    """
    Rule-based deterministic planner creating multi-symbol AgentTask lists for domain agents.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.normalizer = CompanyNormalizer(self.settings.aliases_file_path)
        
        # Hardcoded NIFTY 20 RAG supported symbols
        self.rag_symbols: Set[str] = {
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", 
            "BHARTIARTL", "ITC", "SBIN", "LT", "HINDUNILVR", 
            "AXISBANK", "KOTAKBANK", "M&M", "MARUTI", "SUNPHARMA", 
            "BAJFINANCE", "HCLTECH", "TATAMOTORS", "TATASTEEL", "NTPC"
        }

    def extract_symbols(self, text: str, explicit_symbols: Optional[List[str]] = None) -> List[str]:
        """
        Extract canonical company symbols from text query and merge with explicit request symbols.
        Supports NIFTY 500 tickers dynamically.

        Args:
            text: Question text string.
            explicit_symbols: Optional explicit symbol list passed in ChatRequest.

        Returns:
            List of unique canonical ticker symbols.
        """
        found_symbols: Set[str] = set()

        # Add explicit symbols if provided
        if explicit_symbols:
            for sym in explicit_symbols:
                norm = self.normalizer.normalize(sym)
                if norm:
                    found_symbols.add(norm)
                else:
                    found_symbols.add(sym.strip().upper())

        # Extract symbols matching alias mappings in question
        text_lower = text.lower()

        # Match against loaded NIFTY alias dictionary
        for alias, canonical in self.normalizer.alias_map.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text_lower):
                found_symbols.add(canonical)

        # Dynamic uppercase ticker extraction (e.g. 'WIPRO', 'ZOMATO', 'ADANIENT', 'PAYTM', 'JIOFIN')
        stop_words = {
            "WHAT", "WHY", "HOW", "WHEN", "WHERE", "WHO", "CAN", "YOU", "THINK", "WILL",
            "STOCK", "PRICE", "QUOTE", "NEWS", "RATIO", "BUY", "SELL", "HOLD", "FOR",
            "TODAY", "TOMORROW", "FUTURE", "PREDICTION", "TARGET", "FORECAST", "AND",
            "THE", "THIS", "THAT", "WITH", "ABOUT", "OVER", "UNDER", "NIFTY", "SENSEX"
        }
        raw_tokens = re.findall(r"\b[A-Z0-9&\-]{2,12}\b", text)
        for token in raw_tokens:
            if token not in stop_words:
                norm = self.normalizer.normalize(token)
                if norm:
                    found_symbols.add(norm)
                elif len(token) >= 3 and not token.isdigit():
                    found_symbols.add(token)

        # Fallback default if no symbol detected
        if not found_symbols:
            found_symbols.add("RELIANCE")

        return sorted(list(found_symbols))

    def detect_intent(self, question: str, symbols: List[str]) -> str:
        """
        Detect question intent category based on keyword matching.
        """
        q_lower = question.lower()

        # Multi-symbol comparison keywords
        if len(symbols) > 1 or any(kw in q_lower for kw in ["compare", "vs", "versus", "which is better", "should i buy", "difference"]):
            return "comparison"

        # Stock price prediction, price movement, and forward outlook keywords
        has_prediction = any(
            kw in q_lower
            for kw in [
                "predict", "prediction", "forecast", "target", "tomorrow", "future",
                "outlook", "trend", "bullish", "bearish", "went down", "go down",
                "why did", "why do you think", "going up", "expect", "expected"
            ]
        )
        if has_prediction:
            return "prediction"

        # Specific domain keywords
        has_market = any(kw in q_lower for kw in ["price", "quote", "chart", "volume", "market cap", "52-week", "stock", "high", "low"])
        has_news = any(kw in q_lower for kw in ["news", "headline", "sentiment", "event", "recent", "announcement"])
        has_quant = any(kw in q_lower for kw in ["ratio", "pe", "p/e", "roe", "margin", "cagr", "valuation", "debt", "dividend", "stats", "fundamentals"])
        has_filing = any(kw in q_lower for kw in ["filing", "annual report", "10-k", "10-q", "segment", "breakdown", "strategy", "management", "sec", "visual", "table"])

        if has_market and not (has_news or has_quant or has_filing):
            return "market"
        if has_news and not (has_market or has_quant or has_filing):
            return "news"
        if has_quant and not (has_market or has_news or has_filing):
            return "quant"
        if has_filing and not (has_market or has_news or has_quant):
            return "filing"

        return "comprehensive"

    def create_plan(self, request: ChatRequest) -> Plan:
        """
        Build an execution Plan containing targeted AgentTask objects for execution.

        Args:
            request: ChatRequest Pydantic model.

        Returns:
            Plan Pydantic model.
        """
        symbols = self.extract_symbols(request.question, request.symbols)
        intent = self.detect_intent(request.question, symbols)

        tasks: List[AgentTask] = []
        q = request.question

        logger.info(f"Planner created plan for query: '{q[:40]}...' | Intent: '{intent}' | Symbols: {symbols}")

        all_in_rag = all(sym in self.rag_symbols for sym in symbols)

        is_explicit_filing_search = "search the annual report filing" in q.lower() or "search annual report filings" in q.lower()
        all_agents_requested = any(kw in q.lower() for kw in ["all agents", "every agent", "full analysis", "run all agents"])
        google_rss_requested = any(kw in q.lower() for kw in ["rss", "google rss", "live news"])

        news_params = {"limit": 5}
        if google_rss_requested:
            # Pass google_rss parameter to agent context metadata
            news_params["google_rss"] = True

        if all_agents_requested:
            tasks.append(AgentTask(agent_name="MarketAgent", symbols=symbols, query=q, params={"period": "1mo"}))
            tasks.append(AgentTask(agent_name="NewsAgent", symbols=symbols, query=q, params=news_params))
            tasks.append(AgentTask(agent_name="QuantAgent", symbols=symbols, query=q, params={}))

        elif intent in ["comparison", "comprehensive"]:
            # Dispatch to Market, News, and Quant for complete context (No FilingAgent/RAG)
            tasks.append(AgentTask(agent_name="MarketAgent", symbols=symbols, query=q, params={"period": "1mo"}))
            tasks.append(AgentTask(agent_name="NewsAgent", symbols=symbols, query=q, params=news_params))
            tasks.append(AgentTask(agent_name="QuantAgent", symbols=symbols, query=q, params={}))

        elif intent == "prediction":
            # Dispatch Market, News, and Quant agents for comprehensive forward analysis
            tasks.append(AgentTask(agent_name="MarketAgent", symbols=symbols, query=q, params={"period": "1mo"}))
            tasks.append(AgentTask(agent_name="NewsAgent", symbols=symbols, query=q, params=news_params))
            tasks.append(AgentTask(agent_name="QuantAgent", symbols=symbols, query=q, params={}))

        elif intent == "market":
            tasks.append(AgentTask(agent_name="MarketAgent", symbols=symbols, query=q, params={"period": "1mo"}))

        elif intent == "news":
            tasks.append(AgentTask(agent_name="NewsAgent", symbols=symbols, query=q, params=news_params))

        elif intent == "quant":
            tasks.append(AgentTask(agent_name="QuantAgent", symbols=symbols, query=q, params={}))

        elif intent == "filing":
            if is_explicit_filing_search and all_in_rag:
                tasks.append(AgentTask(agent_name="FilingAgent", symbols=symbols, query=q, params={"top_k": 5}))
                tasks.append(AgentTask(agent_name="QuantAgent", symbols=symbols, query=q, params={}))
            else:
                # Fallback to comprehensive routing heavily reliant on recent News and Market data
                tasks.append(AgentTask(agent_name="MarketAgent", symbols=symbols, query=q, params={"period": "1mo"}))
                tasks.append(AgentTask(agent_name="NewsAgent", symbols=symbols, query=q, params=news_params))
                tasks.append(AgentTask(agent_name="QuantAgent", symbols=symbols, query=q, params={}))

        return Plan(
            question=q,
            tasks=tasks,
            extracted_symbols=symbols,
            intent=intent,
        )
