"""
News Service layer for FinnAI Platform.
Encapsulates news domain logic and wraps PostgreSQL operations via NewsRepository.
Enforces 1-week (7-day) article TTL cleanup and query filtering.
Strictly decoupled from external network APIs.
"""

import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.repositories import NewsRepository
from app.schemas import NewsArticleCreate, NewsArticleResponse
from app.cache import SyncCacheService
from app.utils import get_logger

logger = get_logger("finnai.news_service")


class NewsService:
    """
    Business service managing news data retrieval, storage, TTL cleanup, and deduplication.
    Directly consumes NewsRepository for database access.
    """

    def __init__(self, db: Session) -> None:
        self.repository = NewsRepository(db)

    def cleanup_expired_articles(self, ttl_days: int = 7) -> int:
        """
        Delete articles published prior to the TTL window (default: 7 days / 1 week).

        Args:
            ttl_days: Time to live in days.

        Returns:
            Number of deleted article records.
        """
        deleted_count = self.repository.delete_expired_articles(ttl_days=ttl_days)
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired news articles older than {ttl_days} days.")
        return deleted_count

    def deduplicate_by_url(self, url: str) -> bool:
        """
        Check whether an article with the given URL has already been ingested.

        Args:
            url: Unique article source URL.

        Returns:
            True if URL already exists in database (is duplicate), False otherwise.
        """
        existing = self.repository.get_by_url(url.strip())
        return existing is not None

    def store_article(self, article_data: NewsArticleCreate) -> NewsArticleResponse:
        """
        Persist a news article (with or without AI enrichment) into database.

        Args:
            article_data: NewsArticleCreate Pydantic schema.

        Returns:
            Saved NewsArticleResponse Pydantic ORM schema.
        """
        if self.deduplicate_by_url(article_data.url):
            logger.warning(f"Attempted to store duplicate article URL '{article_data.url}'. Fetching existing record.")
            existing = self.repository.get_by_url(article_data.url)
            return NewsArticleResponse.model_validate(existing)

        saved = self.repository.create_article(article_data)
        
        # Invalidate cache for this symbol so next fetch retrieves the new article
        cache_key = f"news:latest:{saved.canonical_symbol}"
        try:
            client = SyncCacheService.get_client()
            if client:
                keys = client.keys(f"{cache_key}:*")
                for key in keys:
                    client.delete(key)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for {saved.canonical_symbol}: {e}")
            
        logger.info(f"Persisted news article ID={saved.id} [{saved.canonical_symbol}] - '{saved.headline[:40]}...'")
        return NewsArticleResponse.model_validate(saved)

    def get_latest_by_symbol(
        self, symbol: str, limit: int = 10, ttl_days: int = 15, skip: int = 0
    ) -> List[NewsArticleResponse]:
        """
        Retrieve latest ingested unexpired news articles for a given canonical ticker symbol.

        Args:
            symbol: Canonical symbol (e.g., 'RELIANCE').
            limit: Record count cap (Default: 10).
            ttl_days: Time to live in days (Default: 15).
            skip: Offset of records to skip (Default: 0).

        Returns:
            List of NewsArticleResponse objects.
        """
        # Only use Redis cache for the latest page (skip == 0)
        cache_key = f"news:latest:{symbol}:{limit}"
        if skip == 0:
            cached_data = SyncCacheService.get(cache_key)
            if cached_data:
                return [NewsArticleResponse.model_validate(item) for item in cached_data]

        articles = self.repository.get_latest_by_symbol(
            symbol=symbol, limit=limit, ttl_days=ttl_days, skip=skip
        )
        responses = [NewsArticleResponse.model_validate(a) for a in articles]
        
        if skip == 0:
            SyncCacheService.set(cache_key, [r.model_dump(mode='json') for r in responses], ttl=3600)
            
        return responses

    def get_by_date_range(
        self,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        symbol: Optional[str] = None,
    ) -> List[NewsArticleResponse]:
        """
        Retrieve news articles published within a specific UTC date range.

        Args:
            start_date: Range start timestamp.
            end_date: Range end timestamp.
            symbol: Optional symbol filter.

        Returns:
            List of NewsArticleResponse objects.
        """
        articles = self.repository.get_by_date_range(
            start_date=start_date, end_date=end_date, symbol=symbol
        )
        return [NewsArticleResponse.model_validate(a) for a in articles]

    def get_high_importance(
        self, min_score: int = 7, limit: int = 20, ttl_days: int = 7
    ) -> List[NewsArticleResponse]:
        """
        Retrieve high financial impact unexpired articles exceeding an importance score threshold.

        Args:
            min_score: Threshold score (1 to 10).
            limit: Record count cap.
            ttl_days: Time to live in days (Default: 7).

        Returns:
            List of NewsArticleResponse objects.
        """
        articles = self.repository.get_high_importance(
            min_score=min_score, limit=limit, ttl_days=ttl_days
        )
        return [NewsArticleResponse.model_validate(a) for a in articles]
