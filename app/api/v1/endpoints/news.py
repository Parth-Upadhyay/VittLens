"""
News & Sentiment REST API Endpoints.
Exposes database news article queries and manual ingestion triggers.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.dependencies import get_db, get_settings
from app.schemas import NewsArticleResponse
from app.services.news_service import NewsService
from app.workers.news_worker import NewsWorker
from app.utils import MarketSymbolMapper

router = APIRouter(prefix="/news", tags=["News & Sentiment"])


@router.get("/{symbol}", response_model=List[NewsArticleResponse], summary="Get latest news for company symbol")
def get_company_news(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Max news items"),
    skip: int = Query(0, ge=0, description="Offset of records to skip"),
    db: Session = Depends(get_db),
) -> List[NewsArticleResponse]:
    """Retrieve latest AI-enriched news articles from PostgreSQL for a company symbol."""
    service = NewsService(db)
    
    if symbol and symbol.upper() != "ALL":
        mapper = MarketSymbolMapper()
        symbol = mapper.to_canonical_symbol(symbol)
        
    orm_list = service.get_latest_by_symbol(symbol=symbol, limit=limit, skip=skip)
    return [NewsArticleResponse.model_validate(item) for item in orm_list]


@router.post("/ingest", summary="Manually trigger news ingestion pipeline cycle")
def trigger_news_ingestion(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Manually execute a news ingestion iteration across all NIFTY Top 20 companies."""
    worker = NewsWorker(settings=settings)
    stats = worker.run_ingestion_cycle()
    return {"status": "success", "metrics": stats}
