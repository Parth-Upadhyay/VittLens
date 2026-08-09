from __future__ import annotations

# Merged from prompts/*

from typing import Any, Self
import json



"""
Structured prompt builder for FinnAI LLM Layer.
Provides a extensible, fluent builder pattern to assemble standardized financial prompts
with explicit sections (Question, Market Data, News, Financial Statements, Ratios, Evidence, Instructions).
Avoids unstructured string concatenation.
"""



class PromptBuilder:
    """
    Builder pattern for constructing structured, standardized prompts for financial LLM tasks.
    Allows dynamic registration and formatting of predefined and custom prompt sections.
    """

    SECTION_ORDER = [
        "QUESTION",
        "MARKET_DATA",
        "NEWS",
        "FINANCIAL_STATEMENTS",
        "RATIOS",
        "EVIDENCE",
        "INSTRUCTIONS",
    ]

    def __init__(self) -> None:
        self._sections: dict[str, Any] = {}
        self._custom_sections: dict[str, Any] = {}

    def with_question(self, question: str) -> Self:
        """Set the primary user question or inquiry."""
        self._sections["QUESTION"] = question.strip()
        return self

    def with_market_data(self, market_data: Any) -> Self:
        """Set market data section (dict, list, or formatted string)."""
        self._sections["MARKET_DATA"] = market_data
        return self

    def with_news(self, news: Any) -> Self:
        """Set news section context."""
        self._sections["NEWS"] = news
        return self

    def with_financial_statements(self, statements: Any) -> Self:
        """Set financial statements context (e.g. Income Statement, Balance Sheet)."""
        self._sections["FINANCIAL_STATEMENTS"] = statements
        return self

    def with_ratios(self, ratios: Any) -> Self:
        """Set financial ratios context."""
        self._sections["RATIOS"] = ratios
        return self

    def with_evidence(self, evidence: Any) -> Self:
        """Set evidence context (retrieved chunks, quotes, document excerpts)."""
        self._sections["EVIDENCE"] = evidence
        return self

    def with_instructions(self, instructions: str) -> Self:
        """Set specific analytical or response format instructions."""
        self._sections["INSTRUCTIONS"] = instructions.strip()
        return self

    def add_section(self, section_name: str, content: Any) -> Self:
        """
        Extensible escape hatch: add a custom section without modifying the core builder structure.

        Args:
            section_name: Unique title for the section.
            content: Data or text content of the section.
        """
        self._custom_sections[section_name.upper()] = content
        return self

    def _format_content(self, content: Any) -> str:
        """Helper to convert content structures into formatted Markdown strings."""
        if isinstance(content, str):
            return content
        elif isinstance(content, (dict, list)):
            return f"```json\n{json.dumps(content, indent=2, default=str)}\n```"
        else:
            return str(content)

    def build(self) -> str:
        """
        Assemble and format all non-empty sections into a clean structured prompt string.

        Returns:
            Formatted Markdown string ready to pass to the LLM.
        """
        blocks: list[str] = []

        # 1. Render predefined sections in specified order
        for section in self.SECTION_ORDER:
            if section in self._sections and self._sections[section]:
                formatted_title = section.replace("_", " ").title()
                content_str = self._format_content(self._sections[section])
                blocks.append(f"### {formatted_title}\n{content_str}")

        # 2. Render any custom sections
        for section, content in self._custom_sections.items():
            if content:
                formatted_title = section.replace("_", " ").title()
                content_str = self._format_content(content)
                blocks.append(f"### {formatted_title}\n{content_str}")

        return "\n\n".join(blocks)

"""
Centralized repository of system prompts for FinnAI platform.
Isolates persona instructions and behavioral constraints from LLM invocation logic.
"""

FINANCIAL_ANALYST_SYSTEM_PROMPT: str = """\
You are an expert AI Senior Financial Analyst specializing in Indian equity markets (NIFTY Top 20), quantitative finance, corporate financial reporting, and market intelligence.

Your objective is to provide objective, executive-level, data-backed financial analysis.

Adhere strictly to the following principles:

1. RESPONSE STRUCTURE (NO DUPLICATION & NO RAW EVIDENCE DUMPS):
   Structure your analysis into 4 clean, distinct sections:
   - ### Executive Takeaway: 1-2 sentence core financial verdict.
   - ### Market Data & Valuation Comparison: EXACTLY ONE unified side-by-side Markdown comparison table.
   - ### Financial Performance & Sector Analysis: Analytical narrative comparing business models and financial health.
   - ### Corporate Highlights & Filing Insights: Bulleted synthesis of key news events and annual report findings.

   CRITICAL RULES:
   - NEVER repeat or duplicate tables. Output EXACTLY ONE comparison table for ratios/market data.
   - NEVER dump raw internal debug strings or evidence chunk text (e.g. '[Evidence Chunk HDFCBANK Annual Report...').
   - NEVER output raw tables listing every filing chunk. Use filing evidence to extract factual insights in your text narrative.
   - DO NOT output disclaimer paragraphs at the bottom of responses. The website UI automatically displays a persistent SEBI legal disclaimer.

2. INDIAN CURRENCY & CRORE SCALE ACCURACY (CRITICAL):
   - 1 Crore = 10,000,000 INR (10^7 INR).
   - 1 Lakh Crore = 10,000,000,000,000 INR (10^12 INR / 1 Trillion INR).
   - Always format large market caps as "₹17.85 Lakh Crores" or "₹964.6 Crores". NEVER divide by 1,000,000 (Million)!

3. ACCURATE SECTOR KNOWLEDGE:
   - Banking & Financials (HDFCBANK, SBIN, ICICIBANK, KOTAKBANK, AXISBANK): Leveraged financial intermediaries evaluated on Net Interest Margins (NIM), ROE, loan growth, and asset quality. They are capital-intensive financial institutions, NOT asset-light firms!
   - IT Services (TCS, INFY, HCLTECH): Human-capital intensive, asset-light business model with high operating margins.
   - Conglomerates / Energy (RELIANCE, NTPC, TATASTEEL): Capital-heavy CapEx driven operations.

4. STOCK PREDICTIONS & FORWARD OUTLOOK (CRITICAL):
   - When asked for stock predictions, future price targets, or reasons for price movement:
     - DO NOT refuse to answer or output boilerplate "As an AI, I cannot predict the future" refusals.
     - Synthesize current price metrics, 52-week range, technical momentum, news sentiment, and financial ratios to provide an executive-level **Forward-Looking Market Outlook**.
     - Clearly outline:
       1) **Key Technical & Support/Resistance Levels** (e.g. 52-week high/low, recent price momentum).
       2) **News & Macro Catalysts** (recent corporate announcements, quarterly earnings, sector news).
       3) **Fundamental Valuation Support** (P/E relative to sector, ROE, margins).
       4) **Bullish & Bearish Target Scenarios** with directional catalysts.

5. STRUCTURED MARKDOWN TABLES:
   - Ensure all tables are formatted as clean, multi-line GitHub Flavored Markdown tables with proper newlines.
"""

DEFAULT_SYSTEM_PROMPT: str = """\
You are an AI Financial Intelligence Assistant. Provide accurate, helpful, and concise responses to financial and business inquiries.
"""
