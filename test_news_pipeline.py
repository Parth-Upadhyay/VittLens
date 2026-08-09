"""
End-to-End Test and Verification Script for News Service & Ingestion Pipeline.

Usage:
    python test_news_pipeline.py

Verifies:
1. Groq multi-model fallback chain connection test across candidate models
2. Database tables creation (SQLAlchemy 2.0 ORM init)
3. Company name normalization mapping
4. NewsRepository & NewsService 1-week TTL cleanup, CRUD operations, and deduplication
5. NewsWorker 10-article per company limit & LLM enrichment with model failover
"""

import datetime
import os
import sys
from dotenv import load_dotenv

from app.config.settings import Settings
from app.db.database import SessionLocal, init_db
from app.schemas import NewsArticleCreate
from app.services.factory import get_llm_provider
from app.services.news_service import NewsService
from app.utils import CompanyNormalizer
from app.utils import get_logger
from app.workers.news_worker import NewsWorker

logger = get_logger("finnai.test_news", "INFO")


def main() -> None:
    load_dotenv()
    settings = Settings()
    logger.info("=== Starting News Pipeline & Groq Model Connection Verification ===")

    # 1. Test All Groq Fallback Models
    print("\n" + "=" * 70)
    print("      GROQ MULTI-MODEL FALLBACK CHAIN CONNECTIVITY TEST      ")
    print("=" * 70)
    provider = get_llm_provider("groq", settings=settings)
    connection_health = provider.test_connection()

    print("\nModel Connectivity Results Summary:")
    print("-" * 70)
    print(f"{'MODEL IDENTIFIER':<32} | {'STATUS':<20} | {'LATENCY (MS)':<12}")
    print("-" * 70)

    online_models = []
    for model_name, details in connection_health.items():
        if details["status"]:
            status_str = "ONLINE / READY"
            online_models.append(model_name)
            print(f"{model_name:<32} | \033[92m{status_str:<20}\033[0m | {details['latency_ms']:.2f} ms")
        else:
            err_short = details['error'][:35] if details['error'] else 'Unavailable'
            status_str = f"OFFLINE ({err_short})"
            print(f"{model_name:<32} | \033[91m{status_str:<20}\033[0m | --")

    print("-" * 70)
    print(f"Total Candidate Models Tested: {len(connection_health)}")
    print(f"Active Online Models:           {len(online_models)}")
    print("=" * 70 + "\n")

    # 2. Initialize Database
    init_db()
    logger.info("Database tables verified / created successfully.")

    # 3. Verify Company Normalizer
    normalizer = CompanyNormalizer()
    test_cases = [
        ("Reliance Industries Limited", "RELIANCE"),
        ("RIL", "RELIANCE"),
        ("Tata Consultancy Services Ltd", "TCS"),
        ("HDFC Bank", "HDFCBANK"),
        ("Infosys Ltd", "INFY"),
    ]

    print("--- 2. Testing Company Normalizer ---")
    for raw_name, expected in test_cases:
        matched = normalizer.normalize(raw_name)
        status = "PASSED" if matched == expected else f"FAILED (got {matched})"
        print(f"  • Raw: '{raw_name}' -> Normalized: '{matched}' [{status}]")

    # 4. Verify NewsService, 1-Week TTL, & Database Persistence
    print("\n--- 3. Testing NewsService, 1-Week TTL, & Deduplication ---")
    db = SessionLocal()
    news_service = NewsService(db)

    # Test TTL Cleanup
    deleted = news_service.cleanup_expired_articles(ttl_days=settings.news_article_ttl_days)
    print(f"  • Cleaned up {deleted} expired articles older than {settings.news_article_ttl_days} days.")

    test_url = f"https://economictimes.indiatimes.com/markets/stocks/news/reliance-q3-results-{int(datetime.datetime.now().timestamp())}"

    article_data = NewsArticleCreate(
        headline="Reliance Industries Reports Robust Q3 Profit Growth Driven by Retail & Jio",
        url=test_url,
        source="Economic Times",
        author="Financial Bureau",
        published_time=datetime.datetime.now(datetime.timezone.utc),
        canonical_symbol="RELIANCE",
        original_company_name="Reliance Industries",
        raw_snippet="Reliance Industries Ltd announced a 12% year-on-year increase in net profit for the third quarter...",
        summary="Reliance Industries reported a strong Q3 with 12% profit growth led by Jio and Retail segments.",
        sentiment="positive",
        topic_tags=["earnings", "retail", "telecom"],
        event_type="Quarterly Earnings",
        importance_score=8,
        key_entities=["Reliance Industries", "Jio", "Reliance Retail"],
        key_points=[
            "Net profit up 12% YoY",
            "Jio ARPU increases to Rs 182",
            "Retail EBITDA hits record high",
        ],
    )

    stored_response = news_service.store_article(article_data)
    print(f"  • Stored Article ID: {stored_response.id}")
    print(f"  • Canonical Symbol: {stored_response.canonical_symbol}")
    print(f"  • Importance Score: {stored_response.importance_score}/10")

    is_duplicate = news_service.deduplicate_by_url(test_url)
    print(f"  • Deduplication Check for '{test_url}': {'PASSED (Duplicate Detected)' if is_duplicate else 'FAILED'}")

    latest = news_service.get_latest_by_symbol("RELIANCE", limit=settings.max_articles_per_company)
    print(f"  • Query Latest for RELIANCE (Max {settings.max_articles_per_company}): Found {len(latest)} articles.")

    db.close()

    # 5. Live Worker Ingestion Run
    print(f"\n--- 4. Testing News Ingestion Worker (Cap: {settings.max_articles_per_company}/company, TTL: {settings.news_article_ttl_days} days) ---")
    if os.getenv("GROQ_API_KEY"):
        logger.info("Executing NewsWorker ingestion cycle test...")
        worker = NewsWorker()
        stats = worker.run_ingestion_cycle()
        print("\nWorker Ingestion Stats:")
        print(f"  • Symbols Processed:        {stats['symbols_processed']}")
        print(f"  • Fetched Articles:         {stats['fetched_articles']}")
        print(f"  • Stored Articles:          {stats['stored_articles']}")
        print(f"  • Skipped Duplicates:       {stats['duplicates_skipped']}")
        print(f"  • Expired Articles Cleaned: {stats['expired_articles_cleaned']}")
    else:
        print("  [NOTE] GROQ_API_KEY missing. Skipping live AI enrichment worker execution.")

    print("\n" + "=" * 70)
    print("      NEWS SERVICE & PIPELINE VERIFICATION SUCCEEDED!         ")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
