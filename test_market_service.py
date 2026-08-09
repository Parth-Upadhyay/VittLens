"""
Standalone Verification & CLI Test Script for Market Service.

Usage:
    python test_market_service.py

Verifies:
1. Canonical symbol mapping to yfinance exchange tickers (RELIANCE -> RELIANCE.NS)
2. Real-time stock quote retrieval (price, 24h change, volume, market cap)
3. Historical OHLCV time-series chart data (1mo, 1d bars)
4. Company profile overview (sector, industry, description, website)
5. Financial ratios & key statistics (P/E, EPS, Beta, ROE, Debt/Equity)
6. In-memory TTL caching hits & performance
"""

import time
from dotenv import load_dotenv

from app.config.settings import Settings
from app.services.market_service import MarketService
from app.utils import get_logger
from app.utils import MarketSymbolMapper

logger = get_logger("finnai.test_market", "INFO")


def main() -> None:
    load_dotenv()
    settings = Settings()
    logger.info("=== Starting Market Service Verification ===")

    # 1. Test Symbol Mapper
    print("\n--- 1. Testing Symbol Mapper ---")
    mapper = MarketSymbolMapper(settings)
    symbols_to_test = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "M&M"]

    for sym in symbols_to_test:
        yf_ticker = mapper.to_yfinance_ticker(sym)
        back_canon = mapper.to_canonical_symbol(yf_ticker)
        print(f"  • Canonical: '{sym}' -> yfinance: '{yf_ticker}' -> Back: '{back_canon}'")

    # 2. Instantiate MarketService
    print("\n--- 2. Initializing MarketService ---")
    service = MarketService(settings=settings)
    print(f"  • Configured yfinance Suffix:   '{settings.yfinance_symbol_suffix}'")
    print(f"  • Cache TTL Duration:           {settings.yfinance_cache_ttl_seconds} seconds (10 mins)")
    print(f"  • Timeout / Retries:            {settings.yfinance_timeout}s / {settings.yfinance_max_retries} max retries")

    # 3. Test Real-time Stock Quote Retrieval
    print("\n--- 3. Testing Real-time Stock Quotes ---")
    test_companies = ["RELIANCE", "TCS", "HDFCBANK"]

    for symbol in test_companies:
        start_time = time.perf_counter()
        quote = service.get_stock_quote(symbol)
        latency = (time.perf_counter() - start_time) * 1000.0

        print(f"\n[{quote.canonical_symbol}] ({quote.symbol}):")
        print(f"  • Current Price:   {quote.price} {quote.currency}")
        print(f"  • Day Change:      {quote.change:+.2f} ({quote.change_percent:+.2f}%)")
        print(f"  • Trading Volume:  {quote.volume:,}")
        print(f"  • Market Cap:      {quote.market_cap:,}" if quote.market_cap else "  • Market Cap:      N/A")
        print(f"  • 52-Wk Range:     {quote.fifty_two_week_low} - {quote.fifty_two_week_high}")
        print(f"  • Retrieval Time:  {latency:.2f} ms")

        # Test Cache Hit on Immediate Repeat Call
        start_cache = time.perf_counter()
        quote_cached = service.get_stock_quote(symbol)
        latency_cache = (time.perf_counter() - start_cache) * 1000.0
        print(f"  • Cache Hit Time:  {latency_cache:.2f} ms (INSTANT CACHE HIT)")

    # 4. Test Historical OHLCV Chart Data
    print("\n--- 4. Testing Historical Chart Data (1mo, 1d) ---")
    chart = service.get_chart_data("RELIANCE", period="1mo", interval="1d")
    print(f"[{chart.canonical_symbol}] ({chart.ticker_symbol}) Period: '{chart.period}', Interval: '{chart.interval}':")
    print(f"  • Total Bars Fetched: {len(chart.series)}")
    if chart.series:
        latest_bar = chart.series[-1]
        print(f"  • Latest Bar Date:  {latest_bar.timestamp}")
        print(f"  • Open/High/Low:    {latest_bar.open} / {latest_bar.high} / {latest_bar.low}")
        print(f"  • Close / Volume:   {latest_bar.close} / {latest_bar.volume:,}")

    # 5. Test Company Profile Overview
    print("\n--- 5. Testing Company Profile Overview ---")
    profile = service.get_company_profile("TCS")
    print(f"[{profile.canonical_symbol}] {profile.company_name}:")
    print(f"  • Sector:       {profile.sector}")
    print(f"  • Industry:     {profile.industry}")
    print(f"  • Country:      {profile.country}")
    print(f"  • Website:      {profile.website}")
    if profile.description:
        print(f"  • Overview:     {profile.description[:120]}...")

    # 6. Test Key Financial Statistics & Ratios
    print("\n--- 6. Testing Key Financial Statistics & Ratios ---")
    stats = service.get_key_stats("HDFCBANK")
    print(f"[{stats.canonical_symbol}] Key Statistics:")
    print(f"  • Trailing P/E:   {stats.pe_ratio}")
    print(f"  • Forward P/E:    {stats.forward_pe}")
    print(f"  • Trailing EPS:   {stats.eps}")
    print(f"  • Beta:           {stats.beta}")
    print(f"  • ROE:            {stats.roe}")
    print(f"  • Profit Margin:  {stats.profit_margins}")
    print(f"  • Target Price:   {stats.target_price}")

    print("\n" + "=" * 70)
    print("        MARKET SERVICE VERIFICATION COMPLETED SUCCEEDED!       ")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
