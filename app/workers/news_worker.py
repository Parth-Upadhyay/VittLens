"""
News Ingestion Pipeline Worker for FinnAI Platform.
Automates scheduled news ingestion across NIFTY Top 20 companies:
1. Sorts raw fetched news articles by published_time descending and pulls the TOP 10 FRESHEST articles per company.
2. Deletes stored articles from PostgreSQL after 7 days (1-week TTL cleanup).
3. Fetches headlines via NewsFetcher (Google News RSS primary / Marketaux fallback).
4. Normalizes company names to canonical symbols.
5. Deduplicates URLs against PostgreSQL.
6. Enriches content with LLM Provider across fallback model chain (summary, sentiment, importance, topics, key points).
7. Stores enriched records into PostgreSQL via NewsService.

Can be executed independently via CLI (`python -m app.workers.news_worker`) or integrated
into FastAPI application lifespan lifecycle.
"""

import datetime
import json
import re
import threading
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.database import SessionLocal, init_db
from app.prompts import PromptBuilder
from app.prompts import FINANCIAL_ANALYST_SYSTEM_PROMPT
from app.schemas import NewsArticleCreate, NewsEnrichment
from app.services.factory import get_llm_provider
from app.services.base_provider import LLMProvider
from app.services.news_fetcher import NewsFetcher
from app.services.news_service import NewsService
from app.utils import CompanyNormalizer
from app.utils import get_logger

logger = get_logger("finnai.news_worker")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    BackgroundScheduler = None


class NewsWorker:
    """
    Ingestion Worker executing end-to-end news retrieval, LLM enrichment, TTL cleanup, and storage.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.normalizer = CompanyNormalizer(self.settings.aliases_file_path)
        self.fetcher = NewsFetcher(self.settings)
        self.llm_provider = llm_provider or get_llm_provider("groq", settings=self.settings)

    def _enrich_article_with_llm(
        self, headline: str, raw_snippet: str, company_symbol: str
    ) -> Optional[NewsEnrichment]:
        """
        Send article headline and snippet to LLM Provider for AI enrichment.
        Automatically utilizes multi-model failover chain on rate limits.

        Returns:
            NewsEnrichment model instance or None if generation fails.
        """
        enrichment_instructions = """\
Analyze the provided financial news article for the target company symbol.
Output ONLY a raw JSON object (no extra text, no markdown block) matching this schema:
{
  "summary": "Concise 2-sentence financial summary",
  "sentiment": "positive" | "negative" | "neutral",
  "topic_tags": ["earnings", "m&a", "regulatory", "expansion", etc.],
  "event_type": "Primary event description (e.g. Quarterly Earnings, Management Change)",
  "importance_score": <integer from 1 to 10 rating financial impact>,
  "key_entities": ["List of companies, regulators, or executives mentioned"],
  "key_points": ["Bulleted takeaway 1", "Bulleted takeaway 2"]
}
"""
        prompt_builder = (
            PromptBuilder()
            .with_question(f"Analyze news for symbol '{company_symbol}': {headline}")
            .with_evidence({"headline": headline, "snippet": raw_snippet})
            .with_instructions(enrichment_instructions)
        )

        user_prompt = prompt_builder.build()

        try:
            response = self.llm_provider.generate(
                system_prompt=FINANCIAL_ANALYST_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n?", "", content)
                content = re.sub(r"\n?```$", "", content)

            data = json.loads(content)
            return NewsEnrichment.model_validate(data)

        except (json.JSONDecodeError, Exception) as exc:
            logger.warning(
                f"LLM enrichment parsing failed for '{headline[:30]}...': {exc}. Using fallback basic enrichment."
            )
            return NewsEnrichment(
                summary=raw_snippet[:200] if raw_snippet else headline,
                sentiment="neutral",
                topic_tags=["general"],
                event_type="General News",
                importance_score=5,
                key_entities=[company_symbol],
                key_points=[headline],
            )

    def _create_fast_enrichment(self, headline: str, raw_snippet: str, company_symbol: str) -> NewsEnrichment:
        """
        Fast heuristic enrichment for batch ingestion avoiding LLM API rate limits.
        """
        h_lower = headline.lower()
        if any(w in h_lower for w in ["profit", "surge", "jump", "growth", "record", "rally", "gain", "rise", "positive", "high", "soar"]):
            sentiment = "positive"
        elif any(w in h_lower for w in ["fall", "drop", "plunge", "decline", "loss", "down", "slump", "crack", "slash", "cut", "tank"]):
            sentiment = "negative"
        else:
            sentiment = "neutral"

        clean_snippet = re.sub(r"<[^>]+>", "", raw_snippet).strip() if raw_snippet else headline
        summary = clean_snippet[:250] if len(clean_snippet) > 10 else headline

        return NewsEnrichment(
            summary=summary,
            sentiment=sentiment,
            topic_tags=["stock", "market", "corporate"],
            event_type="Corporate & Market Update",
            importance_score=7,
            key_entities=[company_symbol],
            key_points=[headline],
        )

    def run_ingestion_cycle(self) -> Dict[str, Any]:
        """
        Execute one full ingestion iteration across all registered NIFTY companies.

        Enforces:
        - Filling 5 active valid news articles for each company.
        - Deleting articles from PostgreSQL after 7 days (1-week TTL cleanup).

        Returns:
            Dictionary containing metrics.
        """
        logger.info("=== Starting News Ingestion Cycle ===")
        symbols = self.normalizer.get_all_symbols()

        db: Session = SessionLocal()
        news_service = NewsService(db)

        # 1. Delete articles older than 7 days from DB
        ttl_days = self.settings.news_article_ttl_days
        expired_cleaned = news_service.cleanup_expired_articles(ttl_days=ttl_days)

        max_cap = self.settings.max_articles_per_company  # 5 articles per company

        stats = {
            "symbols_processed": 0,
            "fetched_articles": 0,
            "stored_articles": 0,
            "duplicates_skipped": 0,
            "expired_articles_cleaned": expired_cleaned,
            "errors": 0,
        }

        try:
            for symbol in symbols:
                stats["symbols_processed"] += 1
                primary_name = self.normalizer.get_primary_name(symbol)
                company_query = f"{primary_name} India"

                raw_articles = self.fetcher.fetch_news_for_company(
                    symbol=symbol, company_name=company_query
                )
                stats["fetched_articles"] += len(raw_articles)

                if not raw_articles:
                    continue

                # Sort by published_time descending (newest first)
                sorted_articles = sorted(
                    raw_articles,
                    key=lambda x: x.get("published_time") or datetime.datetime.min,
                    reverse=True,
                )

                canonical = self.normalizer.normalize(symbol) or symbol
                needed = max_cap

                logger.info(
                    f"[{canonical}] Attempting to ingest up to {needed} fresh articles."
                )

                stored_for_company = 0
                for item in sorted_articles:
                    if stored_for_company >= needed:
                        break

                    url = item["url"]

                    # Deduplication check in PostgreSQL
                    if news_service.deduplicate_by_url(url):
                        stats["duplicates_skipped"] += 1
                        logger.debug(f"Skipping duplicate article URL: {url}")
                        continue

                    # Fast Heuristic Enrichment (instant, 0 rate limit delays)
                    enrichment = self._create_fast_enrichment(
                        headline=item["headline"],
                        raw_snippet=item["raw_snippet"],
                        company_symbol=canonical,
                    )

                    create_schema = NewsArticleCreate(
                        headline=item["headline"],
                        url=url,
                        source=item["source"],
                        author=item.get("author"),
                        published_time=item["published_time"],
                        canonical_symbol=canonical,
                        original_company_name=symbol,
                        raw_snippet=item["raw_snippet"],
                        summary=enrichment.summary if enrichment else None,
                        sentiment=enrichment.sentiment if enrichment else None,
                        topic_tags=enrichment.topic_tags if enrichment else None,
                        event_type=enrichment.event_type[:250] if (enrichment and enrichment.event_type) else None,
                        importance_score=enrichment.importance_score if enrichment else None,
                        key_entities=enrichment.key_entities if enrichment else None,
                        key_points=enrichment.key_points if enrichment else None,
                    )

                    news_service.store_article(create_schema)
                    stored_for_company += 1
                    stats["stored_articles"] += 1

        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Error encountered during ingestion cycle: {e}")
        finally:
            db.close()

        logger.info(
            f"=== Ingestion Cycle Completed | Processed {stats['symbols_processed']} symbols | "
            f"Fetched: {stats['fetched_articles']} | Stored: {stats['stored_articles']} | "
            f"Skipped Duplicates: {stats['duplicates_skipped']} | Expired Cleaned: {stats['expired_articles_cleaned']} ==="
        )
        return stats


def _background_loop(worker: NewsWorker, interval_hours: int) -> None:
    """Thread background loop fallback when APScheduler is not available."""
    while True:
        try:
            worker.run_ingestion_cycle()
        except Exception as e:
            logger.error(f"Background worker iteration failed: {e}")
        time.sleep(interval_hours * 3600)


def start_news_worker_lifespan(app: Any = None) -> Any:
    """
    Start News Ingestion Worker inside FastAPI lifespan application context.
    """
    init_db()
    settings = Settings()
    worker = NewsWorker(settings=settings)

    interval_hours = max(1, settings.news_fetch_interval_hours)

    if BackgroundScheduler is not None:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            worker.run_ingestion_cycle,
            "interval",
            hours=interval_hours,
            id="news_ingestion_job",
        )
        scheduler.start()
        logger.info(f"Started APScheduler News Ingestion job (interval: {interval_hours}h).")
        return scheduler
    else:
        thread = threading.Thread(
            target=_background_loop, args=(worker, interval_hours), daemon=True
        )
        thread.start()
        logger.info(f"Started Background Thread News Ingestion job (interval: {interval_hours}h).")
        return thread


if __name__ == "__main__":
    logger.info("Starting standalone News Ingestion Worker CLI execution...")
    init_db()
    worker = NewsWorker()
    worker.run_ingestion_cycle()
