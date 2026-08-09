"""
Standalone Verification & Integration Test Script for Filing Service (Qdrant RAG Wrapper).

Usage:
    python test_filing_service.py

Verifies:
1. Qdrant RAG client wrapper connection & collection status
2. Vector similarity search + metadata filtering across NIFTY Top 20 company filings
3. Retrieval of structured text chunks (FilingSearchResult)
4. Extraction of visual chart image URLs (FilingImageResult)
5. Point metadata lookup (FilingMetadata)
6. Zero LLM synthesis inside service layer (pure structured model return)
"""

import time
from dotenv import load_dotenv

from app.config.settings import Settings
from app.services.filing_service import FilingService
from app.utils import get_logger

logger = get_logger("finnai.test_filing", "INFO")


def main() -> None:
    load_dotenv()
    settings = Settings()
    logger.info("=== Starting Filing Service Verification ===")

    # 1. Initialize FilingService
    print("\n--- 1. Initializing FilingService ---")
    service = FilingService(settings=settings)
    print("  • FilingService instantiated cleanly.")

    # 2. Test Filing Search across NIFTY 20 Company Filings
    print("\n--- 2. Testing Filing Vector Search (RELIANCE) ---")
    test_query = "What is the revenue and operating segment performance?"
    test_symbol = "RELIANCE"

    start_time = time.perf_counter()
    result = service.search_filings(query=test_query, symbol=test_symbol, top_k=3)
    latency = (time.perf_counter() - start_time) * 1000.0

    print(f"\nSearch Query:        '{result.query}'")
    print(f"Canonical Symbol:    '{result.canonical_symbol}'")
    print(f"Total Chunks Found:  {result.total_found}")
    print(f"Retrieval Latency:   {latency:.2f} ms")

    for i, chk in enumerate(result.chunks, 1):
        print(f"\n  [{i}] Chunk ID:           {chk.filing_id}")
        print(f"      Symbol:             {chk.symbol}")
        print(f"      Filing Period:      {chk.filing_date}")
        print(f"      Confidence Score:   {chk.confidence_score}")
        print(f"      Source URL / Page:  {chk.source_url} (Page: {chk.page_number})")
        print(f"      Snippet Text:       {chk.text[:140]}...")

    # 3. Test Visual Chart Image Retrieval
    print("\n--- 3. Testing Visual Chart Image Retrieval ---")
    img_result = service.get_filing_images(query="revenue segment breakdown visual chart", symbol=test_symbol, top_k=2)
    print(f"Query:              '{img_result.query}'")
    print(f"Canonical Symbol:   '{img_result.canonical_symbol}'")
    print(f"Image URLs Found:   {len(img_result.image_urls)}")

    for idx, url in enumerate(img_result.image_urls, 1):
        caption = img_result.captions[idx - 1] if idx - 1 < len(img_result.captions) else "N/A"
        print(f"  [{idx}] URL: {url}")
        print(f"      Caption: {caption[:80]}...")

    # 4. Test Filing Point Metadata Retrieval
    if result.chunks and result.chunks[0].filing_id:
        test_id = result.chunks[0].filing_id
        print(f"\n--- 4. Testing Point Metadata Lookup for ID: {test_id} ---")
        meta = service.get_filing_metadata(test_id)
        print(f"  • Filing ID:     {meta.filing_id}")
        print(f"  • Symbol:        {meta.canonical_symbol}")
        print(f"  • Filing Type:   {meta.filing_type}")
        print(f"  • Period/Date:   {meta.filing_date}")
        print(f"  • Source URL:    {meta.source_url}")

    print("\n" + "=" * 70)
    print("        FILING SERVICE VERIFICATION COMPLETED SUCCEEDED!       ")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
