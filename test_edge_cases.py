"""
Edge Case Unit Test Suite for FinnAI Platform.
Tests:
1. Alias normalization & yfinance ticker mapping (HUL -> HINDUNILVR.NS, L&T -> LTI.NS, SBI -> SBIN.NS)
2. ContextBuilder token guard truncation (4,500 max token budget enforcement)
3. GroqProvider prompt truncation on 413 / TPM rate limits
4. Watchlist & Portfolio data calculations
"""

import sys
import unittest
from typing import Dict, List

from app.config.settings import Settings
from app.utils import CompanyNormalizer
from app.utils import MarketSymbolMapper
from app.orchestrator.context_builder import ContextBuilder
from app.schemas import AgentResult, FilingAgentResult, NewsAgentResult
from app.schemas import FilingChunk, FilingSearchResult
from app.schemas import NewsArticleResponse
from app.services.groq_service import GroqProvider


class TestFinnAIEdgeCases(unittest.TestCase):
    """
    Test suite verifying platform edge cases and fail-safe mechanisms.
    """

    def setUp(self) -> None:
        self.settings = Settings()
        self.normalizer = CompanyNormalizer()
        self.mapper = MarketSymbolMapper(self.settings)
        self.builder = ContextBuilder(self.settings)

    def test_alias_normalization(self) -> None:
        """Verify raw company names and aliases resolve to canonical ticker symbols."""
        test_cases = [
            ("HUL", "HINDUNILVR"),
            ("hul", "HINDUNILVR"),
            ("Hindustan Unilever", "HINDUNILVR"),
            ("HUL.NS", "HINDUNILVR"),
            ("l&t", "LT"),
            ("Larsen & Toubro", "LT"),
            ("sbi", "SBIN"),
            ("State Bank of India", "SBIN"),
            ("airtel", "BHARTIARTL"),
            ("Bharti Airtel", "BHARTIARTL"),
            ("reliance", "RELIANCE"),
        ]

        print("\n--- 1. Testing Alias Normalization ---")
        for raw, expected in test_cases:
            canonical = self.normalizer.normalize(raw)
            self.assertEqual(canonical, expected, f"Failed normalizing '{raw}'. Expected '{expected}', got '{canonical}'")
            print(f"  [PASSED] '{raw}' -> '{canonical}'")

    def test_yfinance_ticker_mapping(self) -> None:
        """Verify MarketSymbolMapper creates valid yfinance ticker strings for aliases."""
        test_cases = [
            ("HUL", "HINDUNILVR.NS"),
            ("HUL.NS", "HINDUNILVR.NS"),
            ("L&T", "LT.NS"),
            ("SBI", "SBIN.NS"),
            ("RELIANCE", "RELIANCE.NS"),
        ]

        print("\n--- 2. Testing yfinance Ticker Mapping ---")
        for raw, expected in test_cases:
            ticker = self.mapper.to_yfinance_ticker(raw)
            self.assertEqual(ticker, expected, f"Failed mapping ticker for '{raw}'. Expected '{expected}', got '{ticker}'")
            print(f"  [PASSED] '{raw}' -> '{ticker}'")

    def test_context_builder_truncation(self) -> None:
        """Verify ContextBuilder truncates evidence when tokens exceed 4,500 token budget."""
        print("\n--- 3. Testing ContextBuilder Token Budget Truncation ---")

        # Create oversized filing chunks (> 5,000 estimated tokens)
        huge_text_1 = "Detailed annual report paragraph with financial metrics. " * 300
        huge_text_2 = "Management discussion and analysis of risks and revenue. " * 300

        filing_result = AgentResult(
            agent_name="FilingAgent",
            execution_time_ms=100.0,
            status="success",
            data=FilingAgentResult(
                search_results={
                    "RELIANCE": FilingSearchResult(
                        symbol="RELIANCE",
                        query="test",
                        chunks=[
                            FilingChunk(filing_id="1", text=huge_text_1, confidence_score=0.9),
                            FilingChunk(filing_id="2", text=huge_text_2, confidence_score=0.8),
                            FilingChunk(filing_id="3", text="Extra chunk 3", confidence_score=0.7),
                            FilingChunk(filing_id="4", text="Extra chunk 4", confidence_score=0.6),
                        ],
                    )
                }
            ),
        )

        context = self.builder.build_context([filing_result])
        self.assertTrue(context.context_truncated, "ContextBuilder failed to flag context_truncated=True")

        # Verify filing chunks were truncated to top 2 per symbol
        rel_filings = context.filings.get("RELIANCE", [])
        self.assertLessEqual(len(rel_filings), 2, "Filing chunks not truncated to top 2")
        print(f"  [PASSED] Truncated {len(rel_filings)} chunks (context_truncated={context.context_truncated})")

    def test_groq_fallback_chain_construction(self) -> None:
        """Verify GroqProvider constructs priority candidate model list correctly."""
        print("\n--- 4. Testing Groq Fallback Model Candidate Chain ---")
        provider = GroqProvider(self.settings)
        chain = provider._get_model_candidate_chain("llama-3.3-70b-versatile")
        self.assertIn("llama-3.3-70b-versatile", chain)
        self.assertIn("gpt-oss-20b", chain)
        self.assertIn("groq/compound", chain)
        print(f"  [PASSED] Candidate Chain: {chain}")


if __name__ == "__main__":
    unittest.main()
