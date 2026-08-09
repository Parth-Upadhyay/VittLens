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
async def get_all_symbols() -> Dict[str, List[str]]:
    """Return a mapping of canonical symbols to their aliases for frontend search."""
    file_path = "config/nifty500_aliases.json"
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
            detail=f"Stock quote data unavailable for '{symbol}'. Symbol may be delisted or invalid.",
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
            detail=f"Chart data unavailable for '{symbol}'. Symbol may be delisted or invalid.",
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
            detail=f"Company profile unavailable for '{symbol}'.",
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
            detail=f"Key statistics unavailable for '{symbol}'.",
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
            t = yf.Ticker(ticker_symbol)
            info = t.info or {}
            
            # Fetch financials for manually computed ratios
            try:
                fin = t.financials
                bs = t.balance_sheet
                
                def _get(df, key):
                    if df is not None and key in df.index and not df.empty:
                        try:
                            val = df.loc[key].iloc[0]
                            return float(val) if val is not None else None
                        except Exception:
                            pass
                    return None
                
                net_income = _get(fin, "Net Income")
                equity = _get(bs, "Stockholders Equity")
                total_assets = _get(bs, "Total Assets")
                current_liabilities = _get(bs, "Current Liabilities")
                ebit = _get(fin, "EBIT") or _get(fin, "Operating Income")
                
                if net_income and equity and equity != 0 and not info.get("returnOnEquity"):
                    info["returnOnEquity"] = net_income / equity
                    
                if ebit and total_assets and current_liabilities:
                    cap_emp = total_assets - current_liabilities
                    if cap_emp != 0:
                        info["returnOnCapitalEmployed"] = ebit / cap_emp
                        
                if not info.get("priceToBook") and info.get("marketCap") and equity and equity != 0:
                    info["priceToBook"] = info["marketCap"] / equity
                    
            except Exception:
                pass
            
            # Sanitize: remove None, NaN, non-serializable types, and lists of dicts
            result = {}
            import math
            for k, v in info.items():
                if v is None:
                    continue
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    continue
                if isinstance(v, (list, dict)):
                    continue
                
                # Normalize dividend yield keys if present
                if k in ("dividendYield", "fiveYearAvgDividendYield") and isinstance(v, (int, float)):
                    div_val = service.repository._sanitize_dividend_yield(v)
                    if div_val is None:
                        continue
                    v = div_val
                    
                result[k] = v
            return result
        
        data = await asyncio.to_thread(_fetch_all)
        return {"symbol": symbol, "ticker": ticker_symbol, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deep analyze data unavailable for '{symbol}'.",
        ) from e
