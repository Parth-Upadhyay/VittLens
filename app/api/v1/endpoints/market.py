"""
Market Data REST API Endpoints.
Exposes stock quotes, historical OHLCV series, company profiles, and key financial statistics.
"""

import json
import os
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.config.settings import Settings
from app.dependencies import get_settings
from app.schemas import CompanyInfo, HistoricalData, KeyStatistics, StockQuote
from app.services.market_service import MarketService

router = APIRouter(prefix="/market", tags=["Market Data"])


def get_market_service(settings: Settings = Depends(get_settings)) -> MarketService:
    return MarketService(settings)


@router.get("/symbols", response_model=Dict[str, List[str]], summary="Get all symbols and aliases")
async def get_all_symbols(settings: Settings = Depends(get_settings)) -> Dict[str, List[str]]:
    """Return a mapping of canonical symbols to their aliases for frontend search."""
    file_path = settings.aliases_file_path
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.get("/quote/{symbol}", response_model=StockQuote, summary="Get real-time stock quote")
async def get_stock_quote(
    symbol: str, service: MarketService = Depends(get_market_service)
) -> StockQuote:
    """Get real-time price quote and 24h market metrics for a company symbol."""
    try:
        return await service.get_stock_quote(symbol)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock quote data unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e


@router.get("/chart/{symbol}", response_model=HistoricalData, summary="Get historical OHLCV chart series")
async def get_chart_data(
    symbol: str,
    period: str = Query("1mo", description="Chart period (1d, 5d, 1mo, 3mo, 1y, 5y)"),
    interval: str = Query("1d", description="Bar interval (1m, 5m, 1h, 1d)"),
    service: MarketService = Depends(get_market_service),
) -> HistoricalData:
    """Get historical candlestick time-series bars."""
    try:
        return await service.get_chart_data(symbol, period, interval)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart data unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e


@router.get("/profile/{symbol}", response_model=CompanyInfo, summary="Get company profile overview")
async def get_company_profile(
    symbol: str, service: MarketService = Depends(get_market_service)
) -> CompanyInfo:
    """Get company legal profile, sector, industry, and description."""
    try:
        return await service.get_company_profile(symbol)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company profile unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e


@router.get("/stats/{symbol}", response_model=KeyStatistics, summary="Get key financial statistics")
async def get_key_statistics(
    symbol: str, service: MarketService = Depends(get_market_service)
) -> KeyStatistics:
    """Get key financial ratios, valuation metrics, and balance sheet statistics."""
    try:
        return await service.get_key_stats(symbol)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key statistics unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e


@router.get("/deep-analyze/{symbol}", summary="Get all available yfinance data for a company")
async def get_deep_analyze(
    symbol: str, service: MarketService = Depends(get_market_service)
) -> dict:
    """Return all available raw yfinance info fields for deep analysis display."""
    import asyncio
    import yfinance as yf
    try:
        ticker_symbol = service.mapper.to_yfinance_ticker(symbol)
        
        def _fetch_all():
            from app.services.financial_intelligence import FinancialIntelligenceService
            t = yf.Ticker(ticker_symbol, session=service.repository.session)
            
            try:
                fin = t.financials
                bs = t.balance_sheet
                fast_info = getattr(t, "fast_info", {})
            except Exception as e:
                from app.utils import get_logger
                get_logger("finnai.market_deep_analyze").warning(f"Failed to fetch statements for {ticker_symbol}: {e}")
                fin, bs, fast_info = None, None, {}
                
            fi_service = FinancialIntelligenceService()
            metrics = fi_service.normalize_metrics(ticker_symbol, fast_info, fin, bs)
            report = fi_service.generate_intelligence_report(ticker_symbol, metrics)
            
            return {
                "metrics": metrics,
                "snapshots": report.get("snapshots", {}),
                "key_insights": report.get("key_insights", []),
                "red_flags": report.get("red_flags", [])
            }
        
        data = await asyncio.to_thread(_fetch_all)
        return {"symbol": symbol, "ticker": ticker_symbol, **data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deep analyze data unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e
