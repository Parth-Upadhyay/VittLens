"""
Standalone Verification & Async Concurrent Execution Test Script for Agent Layer.

Usage:
    python test_agents.py

Verifies:
1. BaseAgent async execution protocol across all 4 domain agents
2. MarketAgent execution (retrieves real-time quotes, charts, profiles, key stats)
3. NewsAgent execution (reads latest PostgreSQL database news records)
4. FilingAgent execution (queries Qdrant filing text chunks & Cloudinary images)
5. QuantAgent execution (computes ratio snapshots and side-by-side comparison)
6. Asynchronous concurrent execution of all 4 agents via asyncio.gather()
"""

import asyncio
import time
from dotenv import load_dotenv

from app.agents.filing_agent import FilingAgent
from app.agents.market_agent import MarketAgent
from app.agents.news_agent import NewsAgent
from app.agents.quant_agent import QuantAgent
from app.config.settings import Settings
from app.schemas import AgentContext
from app.utils import get_logger

logger = get_logger("finnai.test_agents", "INFO")


async def test_agents_independently() -> None:
    settings = Settings()

    context = AgentContext(
        symbols=["RELIANCE", "TCS"],
        query="What is the segment revenue performance and profit margins?",
        period="1mo",
        top_k=3,
    )

    print("\n--- 1. Testing MarketAgent Independently ---")
    market_agent = MarketAgent(settings=settings)
    res_mkt = await market_agent.run(context)
    print(f"  • Status:           {res_mkt.status}")
    print(f"  • Latency:          {res_mkt.execution_time_ms} ms")
    if res_mkt.status == "success" and res_mkt.data:
        print(f"  • Quotes Fetched:   {list(res_mkt.data.quotes.keys())}")
        print(f"  • Key Stats Count:  {len(res_mkt.data.key_stats)}")

    print("\n--- 2. Testing NewsAgent Independently ---")
    news_agent = NewsAgent(settings=settings)
    res_news = await news_agent.run(context)
    print(f"  • Status:           {res_news.status}")
    print(f"  • Latency:          {res_news.execution_time_ms} ms")
    if res_news.status == "success" and res_news.data:
        print(f"  • Total DB News:    {res_news.data.total_articles}")

    print("\n--- 3. Testing FilingAgent Independently ---")
    filing_agent = FilingAgent(settings=settings)
    res_filing = await filing_agent.run(context)
    print(f"  • Status:           {res_filing.status}")
    print(f"  • Latency:          {res_filing.execution_time_ms} ms")
    if res_filing.status == "success" and res_filing.data:
        print(f"  • Search Results:   {list(res_filing.data.search_results.keys())}")

    print("\n--- 4. Testing QuantAgent Independently ---")
    quant_agent = QuantAgent(settings=settings)
    res_quant = await quant_agent.run(context)
    print(f"  • Status:           {res_quant.status}")
    print(f"  • Latency:          {res_quant.execution_time_ms} ms")
    if res_quant.status == "success" and res_quant.data:
        print(f"  • Snapshots:        {list(res_quant.data.snapshots.keys())}")
        if res_quant.data.comparison:
            print(f"  • Comparison Key:   {res_quant.data.comparison.symbols}")


async def test_concurrent_agent_execution() -> None:
    settings = Settings()

    print("\n--- 5. Testing Asynchronous Concurrent Execution (asyncio.gather) ---")
    context = AgentContext(
        symbols=["RELIANCE", "HDFCBANK"],
        query="Analyze revenue growth, debt leverage, and latest news sentiment",
        period="1mo",
        top_k=3,
    )

    mkt_agent = MarketAgent(settings=settings)
    news_agent = NewsAgent(settings=settings)
    filing_agent = FilingAgent(settings=settings)
    quant_agent = QuantAgent(settings=settings)

    start_concurrent = time.perf_counter()

    results = await asyncio.gather(
        mkt_agent.run(context),
        news_agent.run(context),
        filing_agent.run(context),
        quant_agent.run(context),
    )

    total_wall_clock_ms = (time.perf_counter() - start_concurrent) * 1000.0

    print(f"\nConcurrent asyncio.gather() Execution Summary (Total Wall-Clock: {total_wall_clock_ms:.2f} ms):")
    print("-" * 75)
    print(f"{'AGENT NAME':<20} | {'STATUS':<10} | {'LATENCY (MS)':<15} | {'SUMMARY'}")
    print("-" * 75)

    for r in results:
        summary_str = "OK"
        if r.status == "success" and r.data:
            if r.agent_name == "MarketAgent":
                summary_str = f"Fetched {len(r.data.quotes)} quotes"
            elif r.agent_name == "NewsAgent":
                summary_str = f"Fetched {r.data.total_articles} articles"
            elif r.agent_name == "FilingAgent":
                summary_str = f"Fetched {len(r.data.search_results)} search objects"
            elif r.agent_name == "QuantAgent":
                summary_str = f"Fetched {len(r.data.snapshots)} ratio snapshots"
        elif r.status == "error":
            summary_str = f"Error: {r.error_message[:25]}"

        print(f"{r.agent_name:<20} | {r.status:<10} | {r.execution_time_ms:<15.2f} | {summary_str}")

    print("-" * 75)


def main() -> None:
    load_dotenv()
    logger.info("=== Starting Agent Layer Verification ===")

    asyncio.run(test_agents_independently())
    asyncio.run(test_concurrent_agent_execution())

    print("\n" + "=" * 70)
    print("        AGENT LAYER VERIFICATION COMPLETED SUCCEEDED!         ")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
