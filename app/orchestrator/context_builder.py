"""
ContextBuilder for FinnAI Platform.
Aggregates AgentResult payloads into a unified InvestorContext.
Implements a Token Guard / Context Budget Manager (MAX_CONTEXT_TOKENS) that ranks,
proportionalizes, and truncates evidence to prevent oversized prompts.
"""

from typing import Dict, List, Optional
from app.config.settings import Settings
from app.schemas import (
    AgentResult,
    FilingAgentResult,
    MarketAgentResult,
    NewsAgentResult,
    QuantAgentResult,
)
from app.schemas import InvestorContext
from app.schemas import FilingChunk
from app.schemas import StockQuote
from app.schemas import NewsArticleResponse
from app.schemas import RatioSnapshot
from app.schemas import KeyStatistics
from app.utils import get_logger

logger = get_logger("finnai.context_builder")


class ContextBuilder:
    """
    Context aggregation and Token Guard budget manager.
    Merges agent outputs and enforces prompt token limits.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.max_tokens = self.settings.max_context_tokens

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count using 1 token ≈ 4 characters heuristic.
        """
        return max(1, len(text) // 4)

    def build_context(self, results: List[AgentResult]) -> InvestorContext:
        """
        Aggregate list of AgentResult objects into an InvestorContext.

        Args:
            results: List of AgentResult models returned by agent executions.

        Returns:
            InvestorContext model with Token Guard truncation flags.
        """
        market_data: Dict[str, StockQuote] = {}
        key_stats: Dict[str, KeyStatistics] = {}
        news: Dict[str, List[NewsArticleResponse]] = {}
        ratios: Dict[str, RatioSnapshot] = {}
        filings: Dict[str, List[FilingChunk]] = {}
        image_urls: List[str] = []
        raw_metrics: Dict[str, List[Dict[str, Any]]] = {}

        for r in results:
            if r.status != "success" or not r.data:
                continue

            # Process MarketAgentResult
            if isinstance(r.data, MarketAgentResult):
                for sym, quote in r.data.quotes.items():
                    market_data[sym] = quote
                for sym, stat in r.data.key_stats.items():
                    key_stats[sym] = stat
                if hasattr(r.data, 'raw_metrics'):
                    for sym, r_metrics in r.data.raw_metrics.items():
                        raw_metrics[sym] = r_metrics

            # Process NewsAgentResult
            elif isinstance(r.data, NewsAgentResult):
                for sym, art_list in r.data.articles_by_symbol.items():
                    news.setdefault(sym, []).extend(art_list)

            # Process QuantAgentResult
            elif isinstance(r.data, QuantAgentResult):
                for sym, snap in r.data.snapshots.items():
                    ratios[sym] = snap

            # Process FilingAgentResult
            elif isinstance(r.data, FilingAgentResult):
                for sym, search_obj in r.data.search_results.items():
                    filings.setdefault(sym, []).extend(search_obj.chunks)

                for sym, img_obj in r.data.image_results.items():
                    for url in img_obj.image_urls:
                        if url not in image_urls:
                            image_urls.append(url)

        # Token Budget Enforcement (Token Guard)
        context_truncated = False
        total_estimated_tokens = 0

        # Calculate current total token footprint
        for sym, quote in market_data.items():
            total_estimated_tokens += self._estimate_tokens(str(quote.model_dump()))

        for sym, snap in ratios.items():
            total_estimated_tokens += self._estimate_tokens(str(snap.model_dump()))

        for sym, art_list in news.items():
            for a in art_list:
                total_estimated_tokens += self._estimate_tokens(f"{a.headline} {a.summary}")

        for sym, chk_list in filings.items():
            for c in chk_list:
                total_estimated_tokens += self._estimate_tokens(c.text)

        logger.info(
            f"ContextBuilder token estimate: {total_estimated_tokens} / {self.max_tokens} max budget."
        )

        # Truncate evidence if over budget
        if total_estimated_tokens > self.max_tokens:
            context_truncated = True
            logger.warning(
                f"Context budget exceeded ({total_estimated_tokens} > {self.max_tokens}). "
                "Applying proportional evidence ranking and truncation..."
            )

            # 1. Truncate Filing Chunks (keep top 2 confidence_score per symbol & cap length)
            for sym in list(filings.keys()):
                chk_list = filings[sym]
                sorted_chks = sorted(chk_list, key=lambda x: x.confidence_score, reverse=True)
                trimmed_chks = sorted_chks[:2]
                for chk in trimmed_chks:
                    if len(chk.text) > 800:
                        chk.text = chk.text[:800] + "..."
                filings[sym] = trimmed_chks

            # 2. Truncate News (keep top 3 importance_score per symbol)
            for sym in list(news.keys()):
                art_list = news[sym]
                sorted_arts = sorted(
                    art_list, key=lambda x: x.importance_score or 0, reverse=True
                )
                news[sym] = sorted_arts[:3]

        return InvestorContext(
            market_data=market_data,
            key_stats=key_stats,
            news=news,
            ratios=ratios,
            filings=filings,
            image_urls=image_urls,
            context_truncated=context_truncated,
            raw_metrics=raw_metrics,
        )
