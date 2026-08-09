"""
Filing Service layer for FinnAI Platform.
Defensive wrapper around existing Qdrant RAG layer (query_qdrant.py).
Returns structured Pydantic models ONLY (zero LLM calls inside this service).
Integrates CompanyNormalizer for symbol resolution and FilingRepository for vector search.
"""

import asyncio
from typing import List, Optional
from app.config.settings import Settings
from app.repositories import FilingRepository
from app.schemas import (
    FilingChunk,
    FilingImageResult,
    FilingMetadata,
    FilingSearchResult,
)
from app.utils import CompanyNormalizer
from app.utils import get_logger
from app.cache import cache
from app.cache import rag_query_key

logger = get_logger("finnai.filing_service")

try:
    import query_qdrant as qdrant_mod
except ImportError:
    qdrant_mod = None


class FilingService:
    """
    Business service executing RAG document retrieval against corporate SEC filings and annual reports.
    Strictly decoupled from LLM generation (returns Pydantic search models for downstream Orchestrator synthesis).
    Uses robust async Redis caching for repeating queries.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        repository: Optional[FilingRepository] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.repository = repository or FilingRepository(self.settings)
        self.normalizer = CompanyNormalizer(self.settings.aliases_file_path)

    def _resolve_company_variants(self, symbol: Optional[str]) -> Optional[List[str]]:
        if not symbol:
            return None

        canonical = self.normalizer.normalize(symbol) or symbol.strip().upper()
        if qdrant_mod and hasattr(qdrant_mod, "COMPANY_VARIANTS"):
            variants = qdrant_mod.COMPANY_VARIANTS.get(canonical, [canonical])
            return variants

        return [canonical]

    @cache(ttl=86400, key_builder=lambda self, query, symbol=None, top_k=5: rag_query_key(query, f"{symbol}:{top_k}:search"), response_model=FilingSearchResult)
    async def search_filings(
        self, query: str, symbol: Optional[str] = None, top_k: int = 5
    ) -> FilingSearchResult:
        """Search corporate annual reports and filing text chunks in Qdrant."""
        canonical_symbol = self.normalizer.normalize(symbol) if symbol else None
        db_variants = self._resolve_company_variants(symbol)

        logger.info(f"FilingService search_filings: query='{query}', symbol='{canonical_symbol}', top_k={top_k}")
        raw_chunks = await asyncio.to_thread(
            self.repository.search_filing_chunks,
            query=query, db_company_variants=db_variants, top_k=top_k
        )

        chunks: List[FilingChunk] = []
        for raw in raw_chunks:
            chunks.append(
                FilingChunk(
                    filing_id=raw.get("filing_id"),
                    text=raw.get("text", ""),
                    source_url=raw.get("source_url"),
                    page_number=raw.get("page_number"),
                    filing_date=raw.get("filing_date"),
                    filing_type=raw.get("filing_type"),
                    confidence_score=raw.get("confidence_score", 0.0),
                    symbol=raw.get("symbol"),
                    metadata=raw.get("metadata", {}),
                )
            )

        return FilingSearchResult(
            query=query,
            canonical_symbol=canonical_symbol,
            chunks=chunks,
            total_found=len(chunks),
        )

    @cache(ttl=86400, key_builder=lambda self, query, symbol=None, top_k=3, existing_chunks=None: rag_query_key(query, f"{symbol}:{top_k}:images"), response_model=FilingImageResult)
    async def get_filing_images(
        self, query: str, symbol: Optional[str] = None, top_k: int = 3, existing_chunks: Optional[List[dict]] = None
    ) -> FilingImageResult:
        """Retrieve visual chart images, diagrams, and figures matching a query."""
        canonical_symbol = self.normalizer.normalize(symbol) if symbol else None
        db_variants = self._resolve_company_variants(symbol)

        logger.info(f"FilingService get_filing_images: query='{query}', symbol='{canonical_symbol}'")
        raw_images = await asyncio.to_thread(
            self.repository.fetch_filing_images,
            query=query, db_company_variants=db_variants, top_k=top_k, existing_chunks=existing_chunks
        )

        urls = [img["image_url"] for img in raw_images]
        captions = [img.get("caption", "") for img in raw_images]

        return FilingImageResult(
            query=query,
            canonical_symbol=canonical_symbol,
            image_urls=urls,
            captions=captions,
        )

    @cache(ttl=86400, key_builder=lambda self, filing_id: f"filing:meta:{filing_id}", response_model=FilingMetadata)
    async def get_filing_metadata(self, filing_id: str) -> FilingMetadata:
        """Retrieve metadata for a specific filing document ID."""
        logger.info(f"FilingService get_filing_metadata for ID '{filing_id}'")
        raw_meta = await asyncio.to_thread(self.repository.fetch_filing_metadata, filing_id)

        if not raw_meta:
            return FilingMetadata(
                filing_id=filing_id,
                canonical_symbol=None,
                filing_type="Unknown",
                filing_date=None,
                source_url=None,
                page_count=None,
                attributes={},
            )

        return FilingMetadata(
            filing_id=raw_meta["filing_id"],
            canonical_symbol=self.normalizer.normalize(raw_meta.get("symbol")) or raw_meta.get("symbol"),
            filing_type=raw_meta.get("filing_type"),
            filing_date=raw_meta.get("filing_date"),
            source_url=raw_meta.get("source_url"),
            page_count=raw_meta.get("page_count"),
            attributes=raw_meta.get("attributes", {}),
        )
