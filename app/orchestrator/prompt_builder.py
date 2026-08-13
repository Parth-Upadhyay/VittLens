"""
Orchestrator Prompt Builder for FinnAI Platform.
Converts InvestorContext into a structured, highly formatted prompt string for Groq LLM.
Supports single-symbol deep dives and multi-symbol side-by-side comparison layouts.
Includes automated Lakh Crore currency conversion and sector metadata injection.
"""

from typing import List, Optional, Dict, Any, Set
from pathlib import Path
import json
from app.schemas import InvestorContext

_COMPANY_META_PATH = Path(__file__).parent.parent / "macro_agent" / "rules" / "company_metadata.json"
try:
    with open(_COMPANY_META_PATH, encoding="utf-8") as _f:
        _COMPANY_META: Dict[str, Any] = json.load(_f)
except Exception:
    _COMPANY_META: Dict[str, Any] = {}


class OrchestratorPromptBuilder:
    """
    Constructs comprehensive multi-agent financial prompts for single LLM synthesis calls.
    """

    @staticmethod
    def format_pct(val: Optional[float]) -> str:
        """Format raw decimal float into clean percentage string (e.g. 0.1384 -> 13.84%)."""
        if val is None:
            return "N/A"
        return f"{val * 100.0:.2f}%"

    @staticmethod
    def format_num(val: Optional[float], suffix: str = "") -> str:
        """Format ratio or numeric float cleanly."""
        if val is None:
            return "N/A"
        return f"{val:.2f}{suffix}"

    @staticmethod
    def format_market_cap(raw_cap: Optional[int]) -> str:
        """
        Format raw market cap in INR into clean Lakh Crores and Crores.

        1 Crore = 10,000,000 INR (10^7)
        1 Lakh Crore = 10,000,000,000,000 INR (10^12)
        """
        if not raw_cap or raw_cap <= 0:
            return "N/A"

        cap_in_crores = raw_cap / 10_000_000.0
        cap_in_lakh_crores = raw_cap / 1_000_000_000_000.0

        if cap_in_lakh_crores >= 1.0:
            return f"₹{cap_in_lakh_crores:.2f} Lakh Crores (₹{cap_in_crores:,.0f} Crores)"
        else:
            return f"₹{cap_in_crores:,.0f} Crores"

    @staticmethod
    def _get_queried_sectors(symbols: List[str]) -> Set[str]:
        """Return all sectors/subsectors for the queried symbols using company_metadata.json."""
        sectors: Set[str] = set()
        for sym in symbols:
            meta = _COMPANY_META.get(sym)
            if meta:
                if meta.get("sector"):
                    sectors.add(meta["sector"])
                for sub in meta.get("subsectors", []):
                    sectors.add(sub)
        return sectors

    @staticmethod
    def _sectors_overlap(impact_sectors_str: str, queried_sectors: Set[str]) -> bool:
        """Check if a macro sector impact string overlaps with any queried sector or contains universal macro terms."""
        if not impact_sectors_str:
            return False
            
        impact_lower = impact_sectors_str.lower()
        
        # Universal macro terms that should ALWAYS trigger a connection
        universal_terms = [
            "economy", "global", "india", "market", "finance", "macro", 
            "geopolitics", "index", "nifty", "interest", "rate", "inflation", 
            "war", "broad", "all", "general", "world", "crisis", "growth",
            "gdp", "fdi", "export", "import", "currency", "rupee", "usd",
            "rbi", "fed", "central bank", "policy", "treasury", "bond"
        ]
        
        if any(term in impact_lower for term in universal_terms):
            return True
            
"""
Orchestrator Prompt Builder for FinnAI Platform.
Converts InvestorContext into a structured, highly formatted prompt string for Groq LLM.
Supports single-symbol deep dives and multi-symbol side-by-side comparison layouts.
Includes automated Lakh Crore currency conversion and sector metadata injection.
"""

from typing import List, Optional, Dict, Any, Set
from pathlib import Path
import json
from app.schemas import InvestorContext

_COMPANY_META_PATH = Path(__file__).parent.parent / "macro_agent" / "rules" / "company_metadata.json"
try:
    with open(_COMPANY_META_PATH, encoding="utf-8") as _f:
        _COMPANY_META: Dict[str, Any] = json.load(_f)
except Exception:
    _COMPANY_META: Dict[str, Any] = {}


class OrchestratorPromptBuilder:
    """
    Constructs comprehensive multi-agent financial prompts for single LLM synthesis calls.
    """

    @staticmethod
    def format_pct(val: Optional[float]) -> str:
        """Format raw decimal float into clean percentage string (e.g. 0.1384 -> 13.84%)."""
        if val is None:
            return "N/A"
        return f"{val * 100.0:.2f}%"

    @staticmethod
    def format_num(val: Optional[float], suffix: str = "") -> str:
        """Format ratio or numeric float cleanly."""
        if val is None:
            return "N/A"
        return f"{val:.2f}{suffix}"

    @staticmethod
    def format_market_cap(raw_cap: Optional[int]) -> str:
        """
        Format raw market cap in INR into clean Lakh Crores and Crores.

        1 Crore = 10,000,000 INR (10^7)
        1 Lakh Crore = 10,000,000,000,000 INR (10^12)
        """
        if not raw_cap or raw_cap <= 0:
            return "N/A"

        cap_in_crores = raw_cap / 10_000_000.0
        cap_in_lakh_crores = raw_cap / 1_000_000_000_000.0

        if cap_in_lakh_crores >= 1.0:
            return f"₹{cap_in_lakh_crores:.2f} Lakh Crores (₹{cap_in_crores:,.0f} Crores)"
        else:
            return f"₹{cap_in_crores:,.0f} Crores"

    @staticmethod
    def _get_queried_sectors(symbols: List[str]) -> Set[str]:
        """Return all sectors/subsectors for the queried symbols using company_metadata.json."""
        sectors: Set[str] = set()
        for sym in symbols:
            meta = _COMPANY_META.get(sym)
            if meta:
                if meta.get("sector"):
                    sectors.add(meta["sector"])
                for sub in meta.get("subsectors", []):
                    sectors.add(sub)
        return sectors

    @staticmethod
    def _sectors_overlap(impact_sectors_str: str, queried_sectors: Set[str]) -> bool:
        """Check if a macro sector impact string overlaps with any queried sector or contains universal macro terms."""
        if not impact_sectors_str:
            return False
            
        impact_lower = impact_sectors_str.lower()
        
        # Universal macro terms that should ALWAYS trigger a connection
        universal_terms = [
            "economy", "global", "india", "market", "finance", "macro", 
            "geopolitics", "index", "nifty", "interest", "rate", "inflation", 
            "war", "broad", "all", "general", "world", "crisis", "growth",
            "gdp", "fdi", "export", "import", "currency", "rupee", "usd",
            "rbi", "fed", "central bank", "policy", "treasury", "bond"
        ]
        
        if any(term in impact_lower for term in universal_terms):
            return True
            
        if not queried_sectors:
            return False
            
        for s in queried_sectors:
            if s.lower() in impact_lower or impact_lower in s.lower():
                return True
        return False

    @classmethod
    def build_prompt(
        cls,
        question: str,
        context: InvestorContext,
        chat_history: Optional[List[Dict[str, str]]] = None,
        macro_summary: Optional[Dict[str, Any]] = None,
        queried_symbols: Optional[List[str]] = None,
        is_filing_intent: bool = False
    ) -> str:
        """
        Build complete prompt string from question, InvestorContext, and chat history.

        Args:
            question: Original user query string.
            context: Compiled InvestorContext model.
            chat_history: Optional list of previous conversation turns.
            macro_summary: Optional latest macro intelligence agent summary.
            queried_symbols: Optional list of extracted company symbols.
            is_filing_intent: Whether the intent is pure filing/RAG search.

        Returns:
            Formatted prompt string.
        """
        prompt_parts: List[str] = []

        # Inject queried symbols banner only if specific companies are queried and not filing intent
        if queried_symbols and not is_filing_intent:
            from app.utils import CompanyNormalizer
            normalizer = CompanyNormalizer()
            named_symbols = [f"{sym} ({normalizer.get_primary_name(sym)})" for sym in queried_symbols]
            sym_list = ", ".join(named_symbols)
            is_multi = len(queried_symbols) > 1
            table_hint = (
                f"Output a side-by-side comparison table for these {len(queried_symbols)} stocks."
                if is_multi else
                "Output a single-stock factsheet table for this ONE stock only. Do NOT add rows for other companies."
            )
            prompt_parts.append(
                f"### QUERIED STOCKS: {sym_list}\n"
                f"CRITICAL: Your ENTIRE analysis must focus ONLY on {sym_list}. {table_hint}\n"
                f"Do NOT include data or rows for any other companies not listed above."
            )
            prompt_parts.append("")

        # Chat History
        if chat_history:
            prompt_parts.append("### CONVERSATION HISTORY")
            for msg in chat_history:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                prompt_parts.append(f"{role}: {content}")
            prompt_parts.append("")

        # Header & User Question
        prompt_parts.append(f"USER QUESTION: {question}\n")

        # 1. Market Data Section
        if context.market_data and not is_filing_intent:
            prompt_parts.append("### 1. REAL-TIME MARKET DATA")
            for sym, quote in context.market_data.items():
                if not quote.price or quote.price <= 0.0:
                    prompt_parts.append(f"[{sym}]: No valid market data found. Do not include {sym} in your analysis.")
                    continue
                    
                mcap_str = cls.format_market_cap(quote.market_cap)
                low_val = f"₹{quote.fifty_two_week_low}" if quote.fifty_two_week_low is not None else "N/A"
                high_val = f"₹{quote.fifty_two_week_high}" if quote.fifty_two_week_high is not None else "N/A"
                prompt_parts.append(
                    f"[{sym}] ({quote.symbol}): Price: ₹{quote.price} INR | 24h Change: {quote.change:+.2f} ({quote.change_percent:+.2f}%) | "
                    f"Volume: {quote.volume:,} | Market Cap: {mcap_str} | "
                    f"52-Week Range: {low_val} - {high_val}"
                )
                
                if hasattr(context, "key_stats") and context.key_stats and sym in context.key_stats:
                    stat = context.key_stats[sym]
                    prompt_parts.append(
                        f"  -> Key Stats for {sym}: P/E={cls.format_num(stat.pe_ratio)}, ROE={cls.format_pct(stat.roe)}, "
                        f"Net Margin={cls.format_pct(stat.profit_margins)}, Gross Margin={cls.format_pct(stat.gross_margins)}, "
                        f"Div Yield={cls.format_pct(stat.dividend_yield)}, Target Price=₹{cls.format_num(stat.target_price)}"
                    )
            prompt_parts.append("")

        # 2. Financial Statements & Quantitative Ratios Section
        if context.ratios and not is_filing_intent:
            prompt_parts.append("### 2. FINANCIAL RATIOS & QUANTITATIVE METRICS")
            for sym, snap in context.ratios.items():
                prof = snap.profitability
                val = snap.valuation
                lev = snap.leverage
                div = snap.dividend
                prompt_parts.append(
                    f"[{sym}] Financial Profile:\n"
                    f"  • Profitability: ROE={cls.format_pct(prof.roe)}, Net Margin={cls.format_pct(prof.net_profit_margin)}, Gross Margin={cls.format_pct(prof.gross_margin)}, ROCE={cls.format_pct(prof.roce)}\n"
                    f"  • Valuation: P/E={cls.format_num(val.pe_ratio)}, Forward P/E={cls.format_num(val.forward_pe)}, P/B={cls.format_num(val.pb_ratio)}, PEG={cls.format_num(val.peg_ratio)}\n"
                    f"  • Solvency & Liquidity: Debt/Equity={cls.format_num(lev.debt_to_equity)}, Current Ratio={cls.format_num(lev.current_ratio)}\n"
                    f"  • Dividend: Yield={cls.format_pct(div.dividend_yield)}"
                )
            prompt_parts.append("")

        # 2b. Supporting Evidence
        if getattr(context, "raw_metrics", None) and not is_filing_intent:
            prompt_parts.append("### 2b. SUPPORTING EVIDENCE (RAW METRICS)")
            for sym, metrics_list in context.raw_metrics.items():
                if metrics_list:
                    prompt_parts.append(f"[{sym}] Additional Raw Metrics:")
                    for m in metrics_list:
                        val_str = f"{m.get('value')} {m.get('unit', '')}".strip()
                        prompt_parts.append(f"  • {m.get('category')} | {m.get('label')}: {val_str}")
            prompt_parts.append("")

        # 3. Macro Intelligence Context
        if macro_summary and not is_filing_intent:
            prompt_parts.append("### 3. MACRO INTELLIGENCE SUMMARY (MACRO AGENT)")
            sum_data = macro_summary.get("summary", {}) if "summary" in macro_summary else macro_summary
            prompt_parts.append(
                f"Market Sentiment: {sum_data.get('sentiment') or sum_data.get('market_sentiment', 'Neutral')} "
                f"(Confidence: {sum_data.get('confidence', 0.5)})\n"
                f"Summary: {sum_data.get('text') or sum_data.get('summary_text', '')}\n"
                f"Global Watchlist Sectors: {', '.join(sum_data.get('watchlist', []))}"
            )

            events = macro_summary.get("events", [])
            if events:
                prompt_parts.append("\nMajor Macro Events (Global Context):")
                for ev in events:
                    importance_str = f" [Importance: {ev.get('importance', 'N/A')}]"
                    prompt_parts.append(
                        f"  • {ev.get('title')} ({ev.get('category', 'General')}){importance_str}\n"
                        f"    Details: {ev.get('summary')}\n"
                        f"    Source: {ev.get('source', 'N/A')}"
                    )

            sector_impacts = macro_summary.get("sector_impacts", [])
            if sector_impacts:
                queried_sectors = cls._get_queried_sectors(queried_symbols or [])
                relevant = []
                other = []
                for si in sector_impacts:
                    si_sector = si.get("sector", "")
                    if queried_sectors and cls._sectors_overlap(si_sector, queried_sectors):
                        relevant.append(si)
                    else:
                        other.append(si)

                if relevant:
                    prompt_parts.append("\n⚡ DIRECTLY RELEVANT Sector Impacts:")
                    for si in relevant:
                        prompt_parts.append(
                            f"  ★ Sector: {si.get('sector')} | Impact: {si.get('impact')}\n"
                            f"    Reason: {si.get('reason')}"
                        )
                if other:
                    prompt_parts.append("\nOther Macro Sector Impacts:")
                    for si in other:
                        prompt_parts.append(
                            f"  • Sector: {si.get('sector')} | Impact: {si.get('impact')}\n"
                            f"    Reason: {si.get('reason')}"
                        )
            prompt_parts.append("")

        # 4. News Timeline & AI Sentiment Section
        if context.news and not is_filing_intent:
            prompt_parts.append("### 4. RECENT NEWS TIMELINE & SENTIMENT")
            for sym, articles in context.news.items():
                header_sym = f"[{sym}] " if sym else ""
                prompt_parts.append(f"{header_sym}News Articles ({len(articles)} items):")
                for a in articles:
                    imp = f"[Impact: {a.importance_score}/10]" if a.importance_score else ""
                    prompt_parts.append(
                        f"  • [{a.published_time}] {a.headline} ({a.source}) {imp}\n"
                        f"    Summary: {a.summary}\n"
                        f"    Source URL: {a.url}"
                    )
            prompt_parts.append("")

        # 5. SEC & Annual Report Filing Evidence Section
        if context.filings:
            prompt_parts.append("### 5. SEC & ANNUAL REPORT FILING EVIDENCE")
            for sym, chunks in context.filings.items():
                prompt_parts.append(f"[{sym}] Filing Chunks ({len(chunks)} items):")
                for c in chunks:
                    page_str = f"Page {c.page_number}" if c.page_number else "N/A"
                    url_str = f" | Link: {c.source_url}" if c.source_url else ""
                    prompt_parts.append(
                        f"  --- [Evidence Chunk | {sym} | {c.filing_type or 'Annual Report'} | {page_str}{url_str} | Score: {c.confidence_score}] ---\n"
                        f"  {c.text}\n"
                    )
            prompt_parts.append("")

        # 6. Visual Chart References
        if context.image_urls and not is_filing_intent:
            prompt_parts.append("### 6. VISUAL CHART & DIAGRAM REFERENCES")
            prompt_parts.append("The following visual figures are available in the context:")
            for idx, url in enumerate(context.image_urls, 1):
                prompt_parts.append(f"  • [Figure {idx}]: {url}")
            prompt_parts.append("")

        # 7. Truncation Warning
        if context.context_truncated:
            prompt_parts.append(
                "NOTE: Context evidence was ranked and compressed to fit prompt budget bounds.\n"
            )

        # 8. Synthesis Instructions
        if is_filing_intent:
            prompt_parts.append(
                "### SYNTHESIS INSTRUCTIONS:\n"
                "1. STRICT RAG: Answer ONLY using the SEC & ANNUAL REPORT FILING EVIDENCE above.\n"
                "2. NO EXTERNAL KNOWLEDGE: Do not use news, live market data, or pre-trained knowledge.\n"
                "3. CHARTS: Refer to Figure numbers if images are relevant."
            )
        elif not queried_symbols:
            prompt_parts.append(
                "### SYNTHESIS INSTRUCTIONS:\n"
                "1. DIRECT & FACTUAL ANALYSIS: Answer the user's specific macroeconomic or geopolitical question directly. Explain the concrete, real-world mechanisms and historical/geopolitical facts of the event (e.g. for US-Iran: Strait of Hormuz, Persian Gulf oil logistics, crude price shocks, India's >85% crude import dependence, inflation, currency depreciation, trade routes, fiscal impact, RBI policy response, and impacted sectors).\n"
                "2. NO GENERIC BOILERPLATE: Avoid vague statements like 'Fluctuations can impact...'. Be concrete and analytical.\n"
                "3. ZERO PREVIOUS CHAT BLEED-THROUGH: Do NOT mention or compare companies from previous conversation turns. Treat this as a fresh, standalone macroeconomic analysis.\n"
                "4. NO TABLES: Do NOT generate stock comparison tables.\n"
                "5. NO DISCLAIMER: Do NOT write legal disclaimer paragraphs."
            )
        else:
            from app.utils import CompanyNormalizer
            is_multi = len(queried_symbols) > 1
            named_symbols = [f"{sym} ({CompanyNormalizer().get_primary_name(sym)})" for sym in queried_symbols]
            sym_list = ", ".join(named_symbols)
            table_rule = (
                "Output ONE side-by-side Markdown table comparing prices, market caps, P/E, ROE, and margins "
                f"for ONLY these stocks: {sym_list}." if is_multi
                else f"Output ONE single-stock factsheet table for ONLY {sym_list}. "
                     "Do NOT add rows for other companies."
            )
            prompt_parts.append(
                "### SYNTHESIS INSTRUCTIONS:\n"
                f"1. STRUCTURE: Organize into: ### Executive Takeaway, ### Market Data & Valuation, ### Financial Performance & Sector Analysis, ### News & Macro Catalysts.\n"
                f"2. TABLE: {table_rule}\n"
                "3. NO RAW CHUNK DUMPS: Do NOT output tables of raw filing chunks or '[Evidence Chunk...' tags. Extract clear factual points as narrative.\n"
                "4. SECTOR ACCURACY: Banking institutions (HDFCBANK, SBIN) are capital-intensive financials evaluated on NIM and loan growth (NOT asset-light IT models).\n"
                "5. STRICT NO HALLUCINATION: You MUST NOT invent, guess, or use external knowledge for any numbers (Price, Market Cap, P/E, Margins). Use ONLY the exact numbers provided in this prompt under 'REAL-TIME MARKET DATA' and 'FINANCIAL RATIOS'. If a metric is missing or 'N/A', state 'N/A'. DO NOT fill in gaps with pre-trained knowledge.\n"
                "6. NO DISCLAIMER: Do NOT write legal disclaimer paragraphs. The website UI auto-displays a SEBI disclaimer.\n"
                "7. MACRO & NEWS WEIGHTAGE: Use the provided macro events and sector impacts to inform your overall analysis. However, ONLY explicitly mention them in your response if they have a clear, direct, and significant impact on the specific stocks the user queried. Do NOT summarize unrelated macro news just because it is present in the prompt. Focus entirely on the queried stock(s).\n"
                "8. LIVE NEWS: When company-specific news articles are present, lead the ### News & Macro Catalysts section with them, then add relevant macro context below.\n"
                "9. USE REAL NAMES: Always refer to the company by its real descriptive name (e.g. Hindustan Unilever) in your text instead of its raw ticker symbol. Do NOT invent parent companies."
            )

        return "\n".join(prompt_parts)
