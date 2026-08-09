"""
Response Formatter for FinnAI Platform.
Parses raw Groq LLM synthesis string and InvestorContext into structured ChatResponse objects.
Ensures Cloudinary visual image URLs live in a dedicated images array for frontend <img> rendering.
"""

from typing import List, Optional, Set
from app.schemas import ChatResponse, InvestorContext
from app.utils import get_logger

logger = get_logger("finnai.response_formatter")


class ResponseFormatter:
    """
    Formats raw LLM text outputs and InvestorContext into structured ChatResponse schemas.
    """

    @staticmethod
    def format_response(
        raw_llm_answer: str,
        context: InvestorContext,
        agents_used: List[str],
        symbols_queried: List[str],
        confidence: Optional[float] = None,
    ) -> ChatResponse:
        """
        Format final ChatResponse object.

        Args:
            raw_llm_answer: Generated natural language answer from Groq LLM.
            context: Compiled InvestorContext containing news, filings, and image_urls.
            agents_used: List of agent names executed.
            symbols_queried: List of canonical symbols analyzed.
            confidence: Optional confidence score.

        Returns:
            ChatResponse Pydantic model.
        """
        # Collect direct citation sources from news and filings
        sources_set: Set[str] = set()

        for sym, art_list in context.news.items():
            for a in art_list:
                if a.url:
                    sources_set.add(a.url)

        for sym, chk_list in context.filings.items():
            for c in chk_list:
                if c.source_url:
                    sources_set.add(c.source_url)

        sources_list = sorted(list(sources_set))

        # Preserve Cloudinary image URLs in separate images list
        images_list = list(context.image_urls)

        return ChatResponse(
            answer=raw_llm_answer.strip(),
            sources=sources_list,
            agents_used=agents_used,
            images=images_list,
            symbols_queried=symbols_queried,
            context_truncated=context.context_truncated,
            confidence=confidence,
        )
