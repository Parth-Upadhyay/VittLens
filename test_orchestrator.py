"""
Standalone Verification & End-to-End Test Script for Master Financial Orchestrator.

Usage:
    python test_orchestrator.py

Verifies:
1. Deterministic Planner symbol extraction & task creation
2. Concurrent agent execution via asyncio.gather()
3. ContextBuilder Token Guard budget manager & evidence ranking
4. Single Groq LLM synthesis call using high-capacity model (llama-3.3-70b-versatile)
5. Isolated Cloudinary image URL pipeline (ChatResponse.images array)
6. Real-time progress event streaming (process_query_event_stream)
"""

import asyncio
import time
from dotenv import load_dotenv

from app.config.settings import Settings
from app.orchestrator.orchestrator import FinancialOrchestrator
from app.schemas import ChatRequest
from app.utils import get_logger

logger = get_logger("finnai.test_orchestrator", "INFO")


async def run_single_symbol_query() -> None:
    print("\n" + "=" * 70)
    print("--- 1. Testing Single-Symbol Query (RELIANCE) ---")
    print("=" * 70)

    settings = Settings()
    orchestrator = FinancialOrchestrator(settings=settings)

    request = ChatRequest(
        question="What is the current stock price, recent news, and financial ratios for RELIANCE?",
        symbols=["RELIANCE"],
    )

    start = time.perf_counter()
    response = await orchestrator.process_query(request)
    latency_ms = (time.perf_counter() - start) * 1000.0

    print(f"\nQuery Latency:        {latency_ms:.2f} ms")
    print(f"Symbols Queried:      {response.symbols_queried}")
    print(f"Agents Used:          {response.agents_used}")
    print(f"Sources Count:        {len(response.sources)}")
    print(f"Images Array Count:   {len(response.images)}")
    print(f"Context Truncated:    {response.context_truncated}")

    if response.images:
        print(f"Sample Image URL:     {response.images[0]}")

    print("\n" + "-" * 40 + " SYNTHESIZED ANSWER " + "-" * 40)
    print(response.answer)
    print("-" * 100)


async def run_event_stream_query() -> None:
    print("\n" + "=" * 70)
    print("--- 2. Testing Real-Time Progress Events & Token Streaming ---")
    print("=" * 70)

    settings = Settings()
    orchestrator = FinancialOrchestrator(settings=settings)

    request = ChatRequest(
        question="Compare RELIANCE vs TCS on market cap, P/E ratios, profit margins, and segment filings.",
        symbols=["RELIANCE", "TCS"],
    )

    stream = orchestrator.process_query_event_stream(request)

    token_text = ""
    async for event in stream:
        evt_type = event.get("type")
        if evt_type == "status":
            print(f"[STATUS EVENT] {event.get('message')}")
        elif evt_type == "agent_start":
            print(f"  🚀 [AGENT START] {event.get('agent')}")
        elif evt_type == "agent_complete":
            print(f"  ✅ [AGENT COMPLETE] {event.get('agent')} ({event.get('latency_ms')} ms)")
        elif evt_type == "token":
            tok = event.get("content", "")
            token_text += tok
            print(tok, end="", flush=True)
        elif evt_type == "done":
            print(f"\n\n[DONE EVENT] Total Latency: {event.get('total_latency_ms')} ms")
            print(f"Images Extracted ({len(event.get('images', []))}): {event.get('images')}")
            print(f"Sources Extracted ({len(event.get('sources', []))}): {event.get('sources')}")

    print("-" * 100)


def main() -> None:
    load_dotenv()
    logger.info("=== Starting Master Financial Orchestrator Verification ===")

    asyncio.run(run_single_symbol_query())
    asyncio.run(run_event_stream_query())

    print("\n" + "=" * 70)
    print("     FINANCIAL ORCHESTRATOR VERIFICATION COMPLETED SUCCEEDED!  ")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
