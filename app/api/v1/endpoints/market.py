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
            t = yf.Ticker(ticker_symbol, session=service.repository.session)
            info = service.repository._fetch_info_with_yahooquery(ticker_symbol)
            
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
                
                # 1. Grab raw values from financials
                net_income = _get(fin, "Net Income")
                total_revenue = _get(fin, "Total Revenue")
                gross_profit = _get(fin, "Gross Profit")
                operating_income = _get(fin, "Operating Income")
                ebitda = _get(fin, "EBITDA") or _get(fin, "Normalized EBITDA")
                ebit = _get(fin, "EBIT") or operating_income
                
                # 2. Grab raw values from balance sheet
                equity = _get(bs, "Stockholders Equity") or _get(bs, "Total Equity Gross Minority Interest")
                total_assets = _get(bs, "Total Assets")
                current_liabilities = _get(bs, "Current Liabilities")
                current_assets = _get(bs, "Current Assets")
                total_debt = _get(bs, "Total Debt")
                total_cash = _get(bs, "Cash And Cash Equivalents") or _get(bs, "Cash Cash Equivalents And Short Term Investments")
                
                # 3. Grab raw values from fast_info
                fast_info = getattr(t, "fast_info", {})
                price = getattr(fast_info, "last_price", None)
                market_cap = getattr(fast_info, "market_cap", None)
                shares = getattr(fast_info, "shares", None)
                
                # Assign fast_info basics
                if price: info.setdefault("regularMarketPrice", price)
                if price: info.setdefault("currentPrice", price)
                if market_cap: info.setdefault("marketCap", market_cap)
                if getattr(fast_info, "previous_close", None): info.setdefault("previousClose", fast_info.previous_close)
                if getattr(fast_info, "day_high", None): info.setdefault("dayHigh", fast_info.day_high)
                if getattr(fast_info, "day_low", None): info.setdefault("dayLow", fast_info.day_low)
                if getattr(fast_info, "year_high", None): info.setdefault("fiftyTwoWeekHigh", fast_info.year_high)
                if getattr(fast_info, "year_low", None): info.setdefault("fiftyTwoWeekLow", fast_info.year_low)
                if getattr(fast_info, "last_volume", None): info.setdefault("volume", fast_info.last_volume)
                if shares: info.setdefault("sharesOutstanding", shares)
                
                # Assign raw financials
                if total_revenue: info.setdefault("totalRevenue", total_revenue)
                if ebitda: info.setdefault("ebitda", ebitda)
                if total_debt: info.setdefault("totalDebt", total_debt)
                if total_cash: info.setdefault("totalCash", total_cash)
                
                # Calculate Ratios Natively
                if net_income and shares and shares != 0:
                    eps = net_income / shares
                    info.setdefault("trailingEps", eps)
                    if price and eps != 0:
                        info.setdefault("trailingPE", price / eps)
                        
                if total_revenue and shares and shares != 0:
                    info.setdefault("revenuePerShare", total_revenue / shares)
                    
                if total_cash and shares and shares != 0:
                    info.setdefault("totalCashPerShare", total_cash / shares)
                    
                if equity and shares and shares != 0:
                    info.setdefault("bookValue", equity / shares)
                    
                if equity and equity != 0:
                    if market_cap: info.setdefault("priceToBook", market_cap / equity)
                    if net_income: info.setdefault("returnOnEquity", net_income / equity)
                    if total_debt: info.setdefault("debtToEquity", (total_debt / equity) * 100) # yfinance uses percentage here
                    
                if total_revenue and total_revenue != 0:
                    if net_income: info.setdefault("profitMargins", net_income / total_revenue)
                    if gross_profit: info.setdefault("grossMargins", gross_profit / total_revenue)
                    if operating_income: info.setdefault("operatingMargins", operating_income / total_revenue)
                    
                if current_assets and current_liabilities and current_liabilities != 0:
                    info.setdefault("currentRatio", current_assets / current_liabilities)
                    
                if ebit and total_assets and current_liabilities:
                    cap_emp = total_assets - current_liabilities
                    if cap_emp != 0:
                        info.setdefault("returnOnCapitalEmployed", ebit / cap_emp)
                        
                if market_cap and total_debt is not None and total_cash is not None:
                    ev = market_cap + total_debt - total_cash
                    info.setdefault("enterpriseValue", ev)
                    if total_revenue and total_revenue != 0:
                        info.setdefault("enterpriseToRevenue", ev / total_revenue)
                    if ebitda and ebitda != 0:
                        info.setdefault("enterpriseToEbitda", ev / ebitda)
            except Exception as e:
                from app.utils import get_logger
                get_logger("finnai.market_deep_analyze").warning(f"Failed to manually compute ratios: {e}")
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
            detail=f"Deep analyze data unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e
