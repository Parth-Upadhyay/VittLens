"""
Filing & SEC RAG Vector Search REST API Endpoints.
Exposes Qdrant SEC filing vector search and Cloudinary visual chart retrieval.
"""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.config.settings import Settings
from app.dependencies import get_settings
from app.schemas import FilingImageResult, FilingSearchResult
from app.services.filing_service import FilingService

router = APIRouter(prefix="/filings", tags=["SEC & Annual Report Filings"])


class FilingSearchRequest(BaseModel):
    query: str
    symbol: Optional[str] = None
    top_k: int = 5


def get_filing_service(settings: Settings = Depends(get_settings)) -> FilingService:
    return FilingService(settings)


@router.post("/search", response_model=FilingSearchResult, summary="Search SEC filing text chunks")
async def search_filings(
    body: FilingSearchRequest, service: FilingService = Depends(get_filing_service)
) -> FilingSearchResult:
    """Execute vector similarity search across SEC annual reports and quarterly filings."""
    return await service.search_filings(query=body.query, symbol=body.symbol, top_k=body.top_k)


@router.post("/images", response_model=FilingImageResult, summary="Retrieve visual chart image URLs")
async def get_filing_images(
    body: FilingSearchRequest, service: FilingService = Depends(get_filing_service)
) -> FilingImageResult:
    """Search visual chart images, diagrams, and figures in retrieved filing payloads."""
    return await service.get_filing_images(query=body.query, symbol=body.symbol, top_k=body.top_k)
