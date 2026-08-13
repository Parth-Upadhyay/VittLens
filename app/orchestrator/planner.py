"""
Deterministic Rule-Based Planner for FinnAI Platform.
Extracts company symbols from natural language queries using CompanyNormalizer
and generates an optimal multi-agent execution Plan without requiring LLM pre-planning overhead.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
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

        # Load company metadata for sector-based discovery
        _meta_path = Path(__file__).parent.parent / "macro_agent" / "rules" / "company_metadata.json"
        try:
            with open(_meta_path, encoding="utf-8") as f:
                self._company_meta: Dict[str, dict] = json.load(f)
        except Exception:
            self._company_meta: Dict[str, dict] = {}

        # Sector/theme keyword → list of sectors in company_metadata
        self._sector_theme_map: Dict[str, List[str]] = {
            "it": ["IT Services"],
            "tech": ["IT Services"],
            "software": ["IT Services"],
            "banking": ["Banking"],
            "bank": ["Banking"],
            "nbfc": ["NBFC", "NBFC & Insurance", "NBFC & Fintech"],
            "pharma": ["Pharma"],
            "healthcare": ["Healthcare", "Pharma"],
            "fmcg": ["FMCG", "FMCG & Conglomerate"],
            "consumer": ["FMCG", "Consumer Discretionary", "Retail"],
            "auto": ["Automobile"],
            "automobile": ["Automobile"],
            "ev": ["Automobile"],
            "energy": ["Energy", "Energy & Conglomerate", "Power & Utilities"],
            "oil": ["Energy", "Energy & Conglomerate"],
            "power": ["Power & Utilities"],
            "telecom": ["Telecom"],
            "steel": ["Metals & Mining"],
            "metal": ["Metals & Mining"],
            "cement": ["Building Materials"],
            "infra": ["Engineering & Construction"],
            "defence": ["Conglomerate", "Engineering & Construction"],
            "insurance": ["Insurance", "NBFC & Insurance"],
            "realty": ["Real Estate"],
            "real estate": ["Real Estate"],
            "internet": ["Consumer Internet"],
            "fintech": ["NBFC & Fintech"],
            "aviation": ["Aviation"],
            "airline": ["Aviation"],
            "retail": ["Retail"],
            "conglomerate": ["Conglomerate", "Energy & Conglomerate"],
            "capital goods": ["Capital Goods & Consumer Electronics", "Engineering & Capital Goods"],
            "chemicals": ["Chemicals & Consumer", "Agrochemicals"],
            "agro": ["Agrochemicals"],
        }

    def _discover_companies_by_sector(self, text_lower: str, max_companies: int = 7) -> List[str]:
        """
        Discover relevant company symbols when no explicit company is mentioned.
        Matches query keywords to sectors in company_metadata.json.
        Returns up to max_companies symbols.
        """
        matched_sectors: Set[str] = set()
        for keyword, sectors in self._sector_theme_map.items():
            if keyword in text_lower:
                matched_sectors.update(sectors)

        if not matched_sectors:
            return []

        matched_symbols = []
        for sym, meta in self._company_meta.items():
            sym_sector = meta.get("sector", "")
            sym_subsectors = meta.get("subsectors", [])
            all_sym_sectors = {sym_sector} | set(sym_subsectors)
            if matched_sectors & all_sym_sectors:
                matched_symbols.append(sym)

        # Cap at max_companies
        return sorted(matched_symbols)[:max_companies]

    def extract_symbols(
        self,
        text: str,
        explicit_symbols: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[str]:
        """
        Extract canonical company symbols from text query, co-references in chat history,
        and explicit request symbols.
        Supports NIFTY 500 tickers dynamically without false-positive bluechip fallbacks.
        """
        found_symbols: Set[str] = set()

        # 1. Add explicit symbols if provided
        if explicit_symbols:
            for sym in explicit_symbols:
                norm = self.normalizer.normalize(sym)
                if norm:
                    found_symbols.add(norm)
                else:
                    found_symbols.add(sym.strip().upper())

        # 2. Extract symbols matching alias mappings in question
        text_lower = text.lower()
        for alias, canonical in self.normalizer.alias_map.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text_lower):
                found_symbols.add(canonical)

        # 3. Dynamic uppercase ticker extraction (e.g. 'WIPRO', 'ZOMATO', 'ADANIENT', 'PAYTM', 'JIOFIN')
        stop_words = {
            "WHAT", "WHY", "HOW", "WHEN", "WHERE", "WHO", "CAN", "YOU", "THINK", "WILL",
            "STOCK", "PRICE", "QUOTE", "NEWS", "RATIO", "BUY", "SELL", "HOLD", "FOR",
            "TODAY", "TOMORROW", "FUTURE", "PREDICTION", "TARGET", "FORECAST", "AND",
            "THE", "THIS", "THAT", "WITH", "ABOUT", "OVER", "UNDER", "NIFTY", "SENSEX",
            "USA", "US", "US-", "GDP", "CPI", "FED", "RBI", "SEBI", "ECONOMY", "GLOBAL", 
            "WORLD", "MARKET", "MARKETS", "SECTOR", "INDUSTRY", "COMPANY", "COMPANIES", 
            "INFO", "DATA", "RATE", "RATES", "INFLATION", "WAR", "IMPACT", "IMPACTED",
            "OIL", "GOLD", "SILVER", "COMMODITY", "RUSSIA", "IRAN", "ISRAEL", "CHINA",
            "INDIA", "UK", "EUROPE", "CRUDE", "BRENT", "NOW", "ALL", "BOTH", "FOUR", "COMPARE"
        }
        
        if not text.isupper():
            raw_tokens = re.findall(r"\b[A-Z0-9&\-]{2,12}\b", text)
            for token in raw_tokens:
                if token not in stop_words:
                    norm = self.normalizer.normalize(token)
                    if norm:
                        found_symbols.add(norm)
                    elif len(token) >= 3 and not token.isdigit():
                        found_symbols.add(token)

        # 4. Chat history co-reference resolution (e.g., "compare all 4", "compare both", "them", "these companies")
        coref_patterns = [
            r"\ball\s+(\d+|four|three|two|both)\b",
            r"\b(all\s+of\s+them|all\s+4|all\s+four|all\s+3|all\s+three|both|these|them|those|all\s+of\s+these|compare\s+all)\b",
            r"\b(the\s+first\s+one|the\s+second\s+one|the\s+former|the\s+latter)\b"
        ]
        has_coref = any(re.search(pat, text_lower) for pat in coref_patterns)

        if (not found_symbols or has_coref) and chat_history:
            history_symbols: List[str] = []
            # Scan chat history messages in reverse order to collect recent symbols
            for msg in reversed(chat_history):
                content = msg.get("content", "")
                # Check for $SYMBOL tags or tickers
                dollar_syms = re.findall(r"\$([A-Z0-9&\-]{2,12})\b", content)
                for s in dollar_syms:
                    norm = self.normalizer.normalize(s) or s
                    if norm not in history_symbols and norm not in stop_words:
                        history_symbols.append(norm)

                # Check for aliases in content
                c_lower = content.lower()
                for alias, canonical in self.normalizer.alias_map.items():
                    if re.search(r"\b" + re.escape(alias) + r"\b", c_lower):
                        if canonical not in history_symbols:
                            history_symbols.append(canonical)

            if history_symbols:
                # Check if user specified a count like "all 4", "all 3", "both"
                count_match = re.search(r"\b(\d+|four|three|two|both)\b", text_lower)
                count_limit = None
                if count_match:
                    w = count_match.group(1).lower()
                    word_to_num = {"two": 2, "both": 2, "three": 3, "four": 4, "2": 2, "3": 3, "4": 4, "5": 5}
                    count_limit = word_to_num.get(w)

                if has_coref:
                    target_syms = history_symbols[:count_limit] if count_limit else history_symbols[:8]
                    found_symbols.update(target_syms)

        # 5. Sector-theme discovery if query explicitly asks for a sector
        if not found_symbols:
            sector_query_keywords = ["sector", "industry", "stocks", "companies", "players", "space", "theme"]
            if any(k in text_lower for k in sector_query_keywords):
                discovered = self._discover_companies_by_sector(text_lower)
                if discovered:
                    found_symbols.update(discovered)

        # 6. Broad NIFTY index overview ONLY if explicitly requested
        if not found_symbols:
            broad_index_keywords = ["nifty 50 overview", "top stocks in india", "indian stock market overview", "nifty index overview"]
            if any(k in text_lower for k in broad_index_keywords):
                found_symbols.update(["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "SBIN"])

        # Return found symbols (can be empty for macro/general questions!)
        return sorted(list(found_symbols))[:8]

    def detect_intent(self, question: str, symbols: List[str]) -> str:
        """
        Detect question intent category based on keyword matching and extracted symbols.
        """
        q_lower = question.lower()

        # If no specific company symbols were identified, categorize as macro or general
        if not symbols:
            macro_keywords = [
                "war", "economy", "gdp", "cpi", "inflation", "rbi", "fed", "interest rate",
                "rate hike", "repo", "budget", "deficit", "crude", "oil", "rupee", "usd",
                "dollar", "currency", "trade", "import", "export", "geopolitics", "iran",
                "israel", "russia", "china", "usa", "recession", "fiscal", "policy", "sanction"
            ]
            if any(kw in q_lower for kw in macro_keywords):
                return "macro"
            return "general"

        # Multi-symbol comparison keywords
        if len(symbols) > 1 or any(kw in q_lower for kw in ["compare", "vs", "versus", "which is better", "should i buy", "difference", "all 4", "all four", "both"]):
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
        symbols = self.extract_symbols(request.question, request.symbols, request.chat_history)
        intent = self.detect_intent(request.question, symbols)

        tasks: List[AgentTask] = []
        q = request.question

        logger.info(f"Planner created plan for query: '{q[:40]}...' | Intent: '{intent}' | Symbols: {symbols}")

        all_agents_requested = any(kw in q.lower() for kw in ["all agents", "every agent", "full analysis", "run all agents"])
        google_rss_requested = any(kw in q.lower() for kw in ["rss", "google rss", "live news"])

        news_params = {"limit": 5}
        if google_rss_requested:
            news_params["google_rss"] = True

        if intent in ["macro", "general"]:
            # For macro/economic/general questions without specific stocks,
            # query live news with the full question to bring recent geopolitical/macro context
            tasks.append(AgentTask(agent_name="NewsAgent", symbols=symbols or [], query=q, params={"google_rss": True, "limit": 5}))

        elif all_agents_requested:
            tasks.append(AgentTask(agent_name="MarketAgent", symbols=symbols, query=q, params={"period": "1mo"}))
            tasks.append(AgentTask(agent_name="NewsAgent", symbols=symbols, query=q, params=news_params))
            tasks.append(AgentTask(agent_name="QuantAgent", symbols=symbols, query=q, params={}))

        elif intent in ["comparison", "comprehensive"]:
            tasks.append(AgentTask(agent_name="MarketAgent", symbols=symbols, query=q, params={"period": "1mo"}))
            tasks.append(AgentTask(agent_name="NewsAgent", symbols=symbols, query=q, params=news_params))
            tasks.append(AgentTask(agent_name="QuantAgent", symbols=symbols, query=q, params={}))

        elif intent == "prediction":
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
            tasks.append(AgentTask(agent_name="FilingAgent", symbols=symbols, query=q, params={"top_k": 5}))

        return Plan(
            question=q,
            tasks=tasks,
            extracted_symbols=symbols,
            intent=intent,
        )
