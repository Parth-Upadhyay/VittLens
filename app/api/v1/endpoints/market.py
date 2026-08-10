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
from app.cache import CacheService

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


@router.get("/deep-analyze/{symbol}/metrics", summary="Get all available raw metrics and agent data")
async def get_deep_analyze_metrics(
    symbol: str, service: MarketService = Depends(get_market_service)
) -> dict:
    """Return all available financial metrics for deep analysis display."""
    import asyncio
    try:
        ticker_symbol = service.mapper.to_yfinance_ticker(symbol)
        
        cache_key = f"market:deep_metrics:{ticker_symbol}"
        cached = await CacheService.get(cache_key)
        if cached:
            return {"symbol": symbol, "ticker": ticker_symbol, **cached}
        
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
                    # Pull missing valuation metrics from yfinance fallback
                    try:
                        yf_info = t.info
                        if isinstance(yf_info, dict):
                            for k, v in yf_info.items():
                                if k not in info or info[k] is None:
                                    info[k] = v
                    except Exception:
                        pass
                except Exception as e2:
                    get_logger("finnai.market_deep_analyze").warning(f"yfinance also failed for {ticker_symbol}: {e2}")
                
            fi_service = FinancialIntelligenceService()
            metrics = fi_service.normalize_metrics(ticker_symbol, fast_info_obj, fin, bs, info)
            agent_data = fi_service.extract_agent_data(ticker_symbol, fast_info_obj, fin, bs)
            
            return {
                "metrics": metrics,
                "agent_data": agent_data,
            }
        
        data = await asyncio.to_thread(_fetch_all)
        await CacheService.set(cache_key, data, ttl=43200)  # 12 hours
        return {"symbol": symbol, "ticker": ticker_symbol, **data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deep analyze metrics unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e


@router.get("/deep-analyze/{symbol}/synthesis", summary="Get LLM synthesis report for a company")
async def get_deep_analyze_synthesis(
    symbol: str, service: MarketService = Depends(get_market_service)
) -> dict:
    """Return the LLM generated deep analysis report."""
    import asyncio
    try:
        ticker_symbol = service.mapper.to_yfinance_ticker(symbol)
        
        cache_key = f"market:deep_synthesis:{ticker_symbol}"
        cached = await CacheService.get(cache_key)
        if cached:
            return {"symbol": symbol, "ticker": ticker_symbol, **cached}
        
        def _fetch_synthesis():
            import pandas as pd
            from app.services.financial_intelligence import FinancialIntelligenceService
            
            fin = None
            bs = None
            fast_info_obj = None
            info = service.repository._fetch_info_with_yahooquery(ticker_symbol)
            
            try:
                from yahooquery import Ticker as YQTicker
                yq = YQTicker(ticker_symbol)
                inc = yq.income_statement(frequency="a")
                bsheet = yq.balance_sheet(frequency="a")
                
                def _format_yq_statement(df):
                    if not isinstance(df, pd.DataFrame) or df.empty: return None
                    if isinstance(df.index, pd.MultiIndex): df = df.droplevel(0)
                    elif getattr(df.index, 'name', None) == 'symbol': df = df.reset_index(drop=True)
                    if 'periodType' in df.columns: df = df[df['periodType'] == '12M']
                    if 'asOfDate' in df.columns:
                        df = df.sort_values('asOfDate', ascending=False)
                        df = df.set_index('asOfDate')
                    return df.T
                
                fin = _format_yq_statement(inc)
                bs = _format_yq_statement(bsheet)
                
                price_data = yq.price.get(ticker_symbol, {})
                stats = yq.key_stats.get(ticker_symbol, {})
                class FastInfoProxy: pass
                fast_info_obj = FastInfoProxy()
                if isinstance(price_data, dict):
                    fast_info_obj.last_price = price_data.get("regularMarketPrice")
                    fast_info_obj.market_cap = price_data.get("marketCap")
                    fast_info_obj.currency = price_data.get("currency", "INR")
                if isinstance(stats, dict): fast_info_obj.shares = stats.get("sharesOutstanding")
                detail = yq.summary_detail.get(ticker_symbol, {})
                if isinstance(detail, dict):
                    fast_info_obj.year_high = detail.get("fiftyTwoWeekHigh")
                    fast_info_obj.year_low = detail.get("fiftyTwoWeekLow")
                    fast_info_obj.last_volume = detail.get("volume")
                    if not hasattr(fast_info_obj, 'last_price') or not fast_info_obj.last_price:
                        fast_info_obj.last_price = detail.get("regularMarketPrice")
            except Exception as e:
                from app.utils import get_logger
                get_logger("finnai.market_synthesis").warning(f"yahooquery failed for {ticker_symbol}: {e}. Trying yfinance...")
                try:
                    import yfinance as yf
                    t = yf.Ticker(ticker_symbol, session=service.repository.session)
                    fin = t.financials
                    bs = t.balance_sheet
                    fast_info_obj = getattr(t, "fast_info", {})
                    try:
                        yf_info = t.info
                        if isinstance(yf_info, dict):
                            for k, v in yf_info.items():
                                if k not in info or info[k] is None: info[k] = v
                    except Exception: pass
                except Exception as e2:
                    get_logger("finnai.market_synthesis").warning(f"yfinance failed for {ticker_symbol}: {e2}")
                
            fi_service = FinancialIntelligenceService()
            metrics = fi_service.normalize_metrics(ticker_symbol, fast_info_obj, fin, bs, info)
            report = fi_service.generate_intelligence_report(ticker_symbol, metrics)
            return report
        
        report_data = await asyncio.to_thread(_fetch_synthesis)
        await CacheService.set(cache_key, report_data, ttl=43200)  # 12 hours
        return {"symbol": symbol, "ticker": ticker_symbol, **report_data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Synthesis unavailable for '{symbol}'. Reason: {str(e)}",
        ) from e


def _calculate_cagr(start: float, end: float, years: int) -> float:
    if not start or start <= 0 or not end or end <= 0 or years <= 0:
        return 0.0
    return round(((end / start) ** (1 / years) - 1) * 100, 4)

def _calculate_avg_growth(values: list) -> float:
    growths = []
    for i in range(1, len(values)):
        if values[i-1] and values[i-1] > 0 and values[i] is not None:
            growths.append(((values[i] - values[i-1]) / values[i-1]) * 100)
    if not growths: return 0.0
    return round(sum(growths) / len(growths), 2)

@router.get("/deep-analyze/{symbol}/all", summary="Get all agent structured data")
async def get_agent_all(symbol: str, service: MarketService = Depends(get_market_service)):
    import datetime
    res = await get_deep_analyze_metrics(symbol, service)
    return {"status": "ok", "data": res.get("agent_data"), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}

@router.get("/deep-analyze/{symbol}/valuation", summary="Get agent valuation data")
async def get_agent_valuation(symbol: str, service: MarketService = Depends(get_market_service)):
    res = await get_deep_analyze_metrics(symbol, service)
    ad = res.get("agent_data", {})
    return {
        "status": "ok",
        "data": {
            "currentPrice": ad.get("current", {}).get("price"),
            "currency": ad.get("current", {}).get("currency"),
            "forwardPE": ad.get("valuation", {}).get("forwardPE"),
            "trailingPE": ad.get("valuation", {}).get("trailingPE"),
            "priceToBook": ad.get("valuation", {}).get("priceToBook"),
            "marketCap": ad.get("current", {}).get("marketCap"),
            "dayHigh": ad.get("current", {}).get("dayHigh"),
            "dayLow": ad.get("current", {}).get("dayLow"),
            "enterpriseValue": ad.get("valuation", {}).get("enterpriseValue")
        },
        "timestamp": ad.get("current", {}).get("timestamp")
    }

@router.get("/deep-analyze/{symbol}/growth", summary="Get agent growth data")
async def get_agent_growth(symbol: str, service: MarketService = Depends(get_market_service)):
    res = await get_deep_analyze_metrics(symbol, service)
    ad = res.get("agent_data", {})
    fins = ad.get("financials", [])
    
    # Financials are newest first, let's reverse them for growth calc (oldest first)
    fins_rev = list(reversed(fins))
    
    growth_rates = []
    for i, yr in enumerate(fins_rev):
        rev = yr.get("revenue")
        eps = yr.get("eps")
        prev_rev = fins_rev[i-1].get("revenue") if i > 0 else None
        prev_eps = fins_rev[i-1].get("eps") if i > 0 else None
        
        rev_growth = ((rev - prev_rev) / prev_rev * 100) if (i > 0 and rev and prev_rev and prev_rev > 0) else None
        eps_growth = ((eps - prev_eps) / prev_eps * 100) if (i > 0 and eps and prev_eps and prev_eps > 0) else None
        
        growth_rates.append({
            "year": yr.get("year"),
            "revenue": rev,
            "revenueGrowthYoY": rev_growth,
            "netIncome": yr.get("netIncome"),
            "eps": eps,
            "epsGrowthYoY": eps_growth,
            "operatingMargin": yr.get("operatingMargin")
        })
        
    cagr3 = 0.0
    if len(fins_rev) >= 4:
        cagr3 = _calculate_cagr(fins_rev[0].get("revenue"), fins_rev[-1].get("revenue"), len(fins_rev)-1)
        
    avg_eps = _calculate_avg_growth([f.get("eps") for f in fins_rev])
        
    return {
        "status": "ok",
        "data": {
            "financials": growth_rates, # Client requested old->new or new->old, we provide old->new based on the script
            "cagr3Year": cagr3,
            "averageEPSGrowth": avg_eps
        }
    }

@router.get("/deep-analyze/{symbol}/health", summary="Get agent health data")
async def get_agent_health(symbol: str, service: MarketService = Depends(get_market_service)):
    res = await get_deep_analyze_metrics(symbol, service)
    ad = res.get("agent_data", {})
    health = ad.get("health", {})
    fins = ad.get("financials", [])
    
    net_debt = health.get("netDebt", 0)
    debt_to_equity = health.get("debtToEquity", 0)
    current_ratio = health.get("currentRatio", 0)
    
    score = 50
    if net_debt is not None and net_debt < 0: score += 20
    if current_ratio is not None and current_ratio > 1: score += 10
    if debt_to_equity is not None and debt_to_equity < 1: score += 15
    score = min(score, 100)
    
    assessment = "Low Risk" if net_debt is not None and net_debt < 0 else "Moderate Risk"
    
    latest_ni = fins[0].get("netIncome") if fins else None
    latest_margin = fins[0].get("operatingMargin") if fins else None
    
    return {
        "status": "ok",
        "data": {
            "debt": {
                "totalDebt": health.get("totalDebt"),
                "cash": health.get("cash"),
                "netDebt": net_debt,
                "debtToEquity": str(round(debt_to_equity, 2)) if debt_to_equity else "0.00"
            },
            "liquidity": {
                "currentRatio": str(round(current_ratio, 2)) if current_ratio else "0.00",
                "netDebt": net_debt,
                "cashPosition": health.get("cash")
            },
            "profitability": {
                "netIncome": latest_ni,
                "operatingMargin": f"{round(latest_margin * 100, 1)}%" if latest_margin else "N/A"
            },
            "riskAssessment": {
                "score": score,
                "assessment": assessment
            }
        }
    }

@router.get("/deep-analyze/{symbol}/summary", summary="Get agent summary data")
async def get_agent_summary(symbol: str, service: MarketService = Depends(get_market_service)):
    res = await get_deep_analyze_metrics(symbol, service)
    ad = res.get("agent_data", {})
    health = ad.get("health", {})
    fins = ad.get("financials", [])
    
    net_debt = health.get("netDebt", 0)
    risk = "Low" if net_debt is not None and net_debt < 0 else "Moderate"
    
    latest_rev = fins[0].get("revenue") if fins else None
    latest_eps = fins[0].get("eps") if fins else None
    
    return {
        "status": "ok",
        "data": {
            "company": ad.get("company"),
            "price": ad.get("current", {}).get("price"),
            "forwardPE": ad.get("valuation", {}).get("forwardPE"),
            "recentRevenue": latest_rev,
            "recentEPS": latest_eps,
            "netDebt": net_debt,
            "riskLevel": risk
        }
    }

