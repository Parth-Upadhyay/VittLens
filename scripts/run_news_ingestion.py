"""
Standalone News Ingestion & TTL Cleanup Script for FinnAI Platform.

Automates scheduled and on-demand news ingestion across all 20 NIFTY companies:
1. Purges database records older than 7 days (7-day TTL window) and invalid example.com URLs.
2. Fetches 10 fresh, actual news articles per company from RSS / Marketaux.
3. Validates all article URLs to ensure only real, non-placeholder publisher links are retained.
4. Performs AI sentiment and financial enrichment via LLM.
5. Persists 10 fresh articles per company into the database.

Usage:
    python scripts/run_news_ingestion.py
"""

import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import init_db
from app.workers.news_worker import NewsWorker
from app.utils import get_logger

logger = get_logger("finnai.scripts.news_ingestion")


def main() -> None:
    print("=" * 70)
    print("      FINNAI REAL-TIME NEWS INGESTION & 7-DAY TTL CLEANUP       ")
    print("=" * 70)

    # 1. Initialize DB schema
    init_db()
    print("[OK] Database schema verified.")

    # 2. Instantiate worker and execute full cycle
    worker = NewsWorker()
    print("[OK] Starting ingestion cycle across NIFTY Top 20 companies...")
    print("  - Enforcing 7-day TTL cleanup (deleting articles >7 days old)")
    print("  - Purging invalid/example.com URLs")
    print("  - Ingesting 10 fresh, valid news articles per company")
    print("-" * 70)

    stats = worker.run_ingestion_cycle()

    print("\n" + "=" * 70)
    print("                    INGESTION SUMMARY REPORT                    ")
    print("=" * 70)
    print(f"  * Companies Processed : {stats['symbols_processed']}")
    print(f"  * Expired/Invalid Purged: {stats['expired_articles_cleaned']}")
    print(f"  * Total Articles Fetched: {stats['fetched_articles']}")
    print(f"  * New Articles Stored   : {stats['stored_articles']}")
    print(f"  * Duplicates Skipped    : {stats['duplicates_skipped']}")
    print(f"  * Ingestion Errors      : {stats['errors']}")
    print("=" * 70)
    print("[OK] News ingestion completed successfully!\n")


if __name__ == "__main__":
    main()
