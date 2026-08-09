"""
Filing Agent for FinnAI Platform.
Consumes FilingService exclusively to query Qdrant RAG annual report text chunks and Cloudinary visual chart images.
Returns structured Pydantic search models only (zero LLM calls, zero natural language generation).
"""

import asyncio
from typing import Dict, Optional
from app.agents.base_agent import BaseAgent
from app.config.settings import Settings
from app.schemas import AgentContext, FilingAgentResult
from app.schemas import FilingImageResult, FilingSearchResult
from app.services.filing_service import FilingService
from app.utils import get_logger

logger = get_logger("finnai.agents.filing")


class FilingAgent(BaseAgent):
    """
    Filing Domain Agent executing vector search and image retrieval across corporate SEC/annual report filings.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        filing_service: Optional[FilingService] = None,
    ) -> None:
        super().__init__(name="FilingAgent", settings=settings)
        self.filing_service = filing_service or FilingService(self.settings)

    async def _execute(self, context: AgentContext) -> FilingAgentResult:
        """
        Execute filing chunk search and visual chart retrieval.
        """
        search_results: Dict[str, FilingSearchResult] = {}
        image_results: Dict[str, FilingImageResult] = {}

        query = context.query or "Financial performance and operational overview"
        symbols = context.symbols or [None]
        top_k = context.top_k or 5

        for symbol in symbols:
            # Execute async FilingService search directly
            res_search = await self.filing_service.search_filings(query=query, symbol=symbol, top_k=top_k)

            # Convert chunks back to dict for image extraction
            raw_chks = [c.model_dump() for c in res_search.chunks]

            res_img = await self.filing_service.get_filing_images(
                query=query,
                symbol=symbol,
                top_k=3,
                existing_chunks=raw_chks,
            )

            key = res_search.canonical_symbol or symbol or "general"
            search_results[key] = res_search
            image_results[key] = res_img

        return FilingAgentResult(
            search_results=search_results,
            image_results=image_results,
        )
