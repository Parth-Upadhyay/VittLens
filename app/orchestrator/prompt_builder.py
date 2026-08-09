"""
Orchestrator Prompt Builder for FinnAI Platform.
Converts InvestorContext into a structured, highly formatted prompt string for Groq LLM.
Supports single-symbol deep dives and multi-symbol side-by-side comparison layouts.
Includes automated Lakh Crore currency conversion and sector metadata injection.
"""

from typing import List, Optional, Dict, Any
from app.schemas import InvestorContext


class OrchestratorPromptBuilder:
    """
    Constructs comprehensive multi-agent financial prompts for single LLM synthesis calls.
    """

    @staticmethod
    def format_pct(val: Optional[float]) -> str:
        """Format raw decimal float into clean percentage string (e.g. 0.1384 -> 13.84%)."""
        if val is None:
            return "N/A"
        return f"{val * 100.0:.2f}%" if abs(val) <= 1.0 and val != 0 else f"{val:.2f}%"

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
        cap_in_lakh_crores = raw_cap / 1_0_000_000_000_000.0

        if cap_in_lakh_crores >= 1.0:
            return f"₹{cap_in_lakh_crores:.2f} Lakh Crores (₹{cap_in_crores:,.0f} Crores)"
        else:
            return f"₹{cap_in_crores:,.0f} Crores"

    @classmethod
    def build_prompt(
        cls,
        question: str,
        context: InvestorContext,
        chat_history: Optional[List[Dict[str, str]]] = None,
        macro_summary: Optional[Dict[str, Any]] = None,
        queried_symbols: Optional[List[str]] = None
    ) -> str:
        """
        Build complete prompt string from question, InvestorContext, and chat history.

        Args:
            question: Original user query string.
            context: Compiled InvestorContext model.
            chat_history: Optional list of previous conversation turns.
            macro_summary: Optional latest macro intelligence agent summary.

        Returns:
            Formatted prompt string.
        """
        prompt_parts: List[str] = []

        # Inject queried symbols banner at the very top so the LLM knows what the user asked about
        if queried_symbols:
            sym_list = ", ".join(queried_symbols)
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

        # 1. Market Data Section (Clean formatted Market Cap)
        if context.market_data:
            prompt_parts.append("### 1. REAL-TIME MARKET DATA")
            for sym, quote in context.market_data.items():
                mcap_str = cls.format_market_cap(quote.market_cap)
                prompt_parts.append(
                    f"[{sym}] ({quote.symbol}): Price: ₹{quote.price} INR | 24h Change: {quote.change:+.2f} ({quote.change_percent:+.2f}%) | "
                    f"Volume: {quote.volume:,} | Market Cap: {mcap_str} | "
                    f"52-Week Range: ₹{quote.fifty_two_week_low} - ₹{quote.fifty_two_week_high}"
                )
            prompt_parts.append("")

        # 2. Financial Statements & Quantitative Ratios Section (Pre-formatted clean ratios)
        if context.ratios:
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

        # 3. Macro Intelligence Context
        if macro_summary:
            prompt_parts.append("### 3. MACRO INTELLIGENCE SUMMARY (MACRO AGENT)")
            # Support both raw db model Dict format and Redis nested format
            sum_data = macro_summary.get("summary", {}) if "summary" in macro_summary else macro_summary
            prompt_parts.append(
                f"Market Sentiment: {sum_data.get('sentiment') or sum_data.get('market_sentiment', 'Neutral')} (Confidence: {sum_data.get('confidence', 0.5)})\n"
                f"Summary: {sum_data.get('text') or sum_data.get('summary_text', '')}\n"
                f"Watchlist Sectors/Companies: {', '.join(sum_data.get('watchlist', []))}"
            )
            
            # Detailed Macro Events
            events = macro_summary.get("events", [])
            if events:
                prompt_parts.append("\nMajor Macro Events:")
                for ev in events:
                    importance_str = f" [Importance: {ev.get('importance', 'N/A')}]"
                    prompt_parts.append(
                        f"  • {ev.get('title')} ({ev.get('category', 'General')}){importance_str}\n"
                        f"    Details: {ev.get('summary')}\n"
                        f"    Source: {ev.get('source', 'N/A')}"
                    )
            
            # Detailed Sector Impacts
            sector_impacts = macro_summary.get("sector_impacts", [])
            if sector_impacts:
                prompt_parts.append("\nSector Impacts:")
                for si in sector_impacts:
                    prompt_parts.append(
                        f"  • Sector: {si.get('sector')} | Impact: {si.get('impact')}\n"
                        f"    Reason: {si.get('reason')}"
                    )
            prompt_parts.append("")

        # 4. News Timeline & AI Sentiment Section
        if context.news:
            prompt_parts.append("### 4. RECENT NEWS TIMELINE & SENTIMENT")
            for sym, articles in context.news.items():
                prompt_parts.append(f"[{sym}] News Articles ({len(articles)} items):")
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
        if context.image_urls:
            prompt_parts.append("### 6. VISUAL CHART & DIAGRAM REFERENCES")
            prompt_parts.append("The following visual figures are available in the context:")
            for idx, url in enumerate(context.image_urls, 1):
                prompt_parts.append(f"  • [Figure {idx}]: {url}")
            prompt_parts.append("")

        # 7. Truncation Warning Flag
        if context.context_truncated:
            prompt_parts.append(
                "NOTE: Context evidence was ranked and compressed to fit prompt budget bounds.\n"
            )

        # 8. Synthesis Instructions
        is_multi = queried_symbols and len(queried_symbols) > 1
        table_rule = (
            "Output ONE side-by-side Markdown table comparing prices, market caps, P/E, ROE, and margins "
            f"for ONLY these stocks: {', '.join(queried_symbols or [])}." if is_multi
            else f"Output ONE single-stock factsheet table for ONLY {(queried_symbols or ['the queried stock'])[0]}. "
                 "Do NOT add rows for other companies."
        )
        prompt_parts.append(
            "### SYNTHESIS INSTRUCTIONS:\n"
            f"1. STRUCTURE: Organize into: ### Executive Takeaway, ### Market Data & Valuation, ### Financial Performance & Sector Analysis, ### News & Macro Catalysts.\n"
            f"2. TABLE: {table_rule}\n"
            "3. NO RAW CHUNK DUMPS: Do NOT output tables of raw filing chunks or '[Evidence Chunk...' tags. Extract clear factual points as narrative.\n"
            "4. SECTOR ACCURACY: Banking institutions (HDFCBANK, SBIN) are capital-intensive financials evaluated on NIM and loan growth (NOT asset-light IT models).\n"
            "5. NO DISCLAIMER: Do NOT write legal disclaimer paragraphs. The website UI auto-displays a SEBI disclaimer.\n"
            "6. MACRO AS BACKGROUND ONLY: The macro intelligence section provides global background context only. "
            "Do NOT let macro watchlist companies hijack the analysis — the primary focus must remain on the queried stock(s). "
            "Mention relevant macro events only as supporting context, not as the main subject."
        )

        return "\n".join(prompt_parts)
