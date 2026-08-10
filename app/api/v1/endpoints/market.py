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
    """Return all available financial data for deep analysis display."""
    import asyncio
    try:
        ticker_symbol = service.mapper.to_yfinance_ticker(symbol)
        
        def _fetch_all():
            import pandas as pd
            from app.services.financial_intelligence import FinancialIntelligenceService
            
            fin = None
            bs = None
            fast_info_obj = None
            info = service.repository._fetch_info_with_yahooquery(ticker_symbol)
            
            # Primary: yahooquery for financial statements
            try:
                from yahooquery import Ticker as YQTicker
                yq = YQTicker(ticker_symbol)
                
                inc = yq.income_statement(frequency="a")
                bsheet = yq.balance_sheet(frequency="a")
                
                def _format_yq_statement(df):
                    if not isinstance(df, pd.DataFrame) or df.empty:
                        return None
                    # Drop symbol index if it exists
                    if isinstance(df.index, pd.MultiIndex):
                        df = df.droplevel(0)
                    elif getattr(df.index, 'name', None) == 'symbol':
                        df = df.reset_index(drop=True)
                        
                    if 'periodType' in df.columns:
                        df = df[df['periodType'] == '12M']
                        
                    if 'asOfDate' in df.columns:
                        # Sort by date descending (newest first)
                        df = df.sort_values('asOfDate', ascending=False)
                        # Set asOfDate as the index
                        df = df.set_index('asOfDate')
                    
                    # Transpose so metrics are rows, dates are columns
                    return df.T
                
                fin = _format_yq_statement(inc)
                bs = _format_yq_statement(bsheet)
                    
                # Build a minimal fast_info-like object from yahooquery
                price_data = yq.price.get(ticker_symbol, {})
                stats = yq.key_stats.get(ticker_symbol, {})
                
                class FastInfoProxy:
                    pass
                fast_info_obj = FastInfoProxy()
                if isinstance(price_data, dict):
                    fast_info_obj.last_price = price_data.get("regularMarketPrice")
                    fast_info_obj.market_cap = price_data.get("marketCap")
                    fast_info_obj.currency = price_data.get("currency", "INR")
                if isinstance(stats, dict):
                    fast_info_obj.shares = stats.get("sharesOutstanding")
                    
                # 52-week from summary_detail
                detail = yq.summary_detail.get(ticker_symbol, {})
                if isinstance(detail, dict):
                    fast_info_obj.year_high = detail.get("fiftyTwoWeekHigh")
                    fast_info_obj.year_low = detail.get("fiftyTwoWeekLow")
                    fast_info_obj.last_volume = detail.get("volume")
                    if not hasattr(fast_info_obj, 'last_price') or not fast_info_obj.last_price:
                        fast_info_obj.last_price = detail.get("regularMarketPrice")
                        
            except Exception as e:
                from app.utils import get_logger
                get_logger("finnai.market_deep_analyze").warning(f"yahooquery failed for {ticker_symbol}: {e}. Trying yfinance...")
                # Fallback: yfinance
                try:
                    import yfinance as yf
                    t = yf.Ticker(ticker_symbol, session=service.repository.session)
                    fin = t.financials
                    bs = t.balance_sheet
                    fast_info_obj = getattr(t, "fast_info", {})
                except Exception as e2:
                    get_logger("finnai.market_deep_analyze").warning(f"yfinance also failed for {ticker_symbol}: {e2}")
                
            fi_service = FinancialIntelligenceService()
            metrics = fi_service.normalize_metrics(ticker_symbol, fast_info_obj, fin, bs, info)
            report = fi_service.generate_intelligence_report(ticker_symbol, metrics)
            
            return {
                "metrics": metrics,
                **report,
            }
        
        data = await asyncio.to_thread(_fetch_all)
        return {"symbol": symbol, "ticker": ticker_symbol, **data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deep analyze data unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e
