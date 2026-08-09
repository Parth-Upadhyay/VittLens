"""
Company Profile & Detail REST API Endpoints.
Provides consolidated GET /api/v1/company/{symbol} endpoint for Company Detail views.
"""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.config.settings import Settings
from app.dependencies import get_settings
from app.schemas import CompanyInfo, KeyStatistics, StockQuote
from app.schemas import RatioSnapshot
from app.services.market_service import MarketService
from app.services.quant_service import QuantService

router = APIRouter(prefix="/company", tags=["Company Detail"])


class CompanyDetailResponse(BaseModel):
    symbol: str
    profile: Optional[CompanyInfo] = None
    quote: Optional[StockQuote] = None
    quant_snapshot: Optional[RatioSnapshot] = None
    key_stats: Optional[KeyStatistics] = None


def get_market_service(settings: Settings = Depends(get_settings)) -> MarketService:
    return MarketService(settings)


def get_quant_service(settings: Settings = Depends(get_settings)) -> QuantService:
    return QuantService(settings)


@router.get("/{symbol}", response_model=CompanyDetailResponse, summary="Get consolidated company detail profile")
async def get_company_detail(
    symbol: str,
    market_svc: MarketService = Depends(get_market_service),
    quant_svc: QuantService = Depends(get_quant_service),
) -> CompanyDetailResponse:
    """Retrieve consolidated company legal profile, live stock quote, financial ratios, and stats."""
    sym = symbol.strip().upper()

    try:
        profile = await market_svc.get_company_profile(sym)
    except Exception:
        profile = None

    try:
        quote = await market_svc.get_stock_quote(sym)
    except Exception:
        quote = None

    try:
        quant_snap = await quant_svc.get_full_ratio_snapshot(sym)
    except Exception:
        quant_snap = None

    try:
        stats = await market_svc.get_key_stats(sym)
    except Exception:
        stats = None

    return CompanyDetailResponse(
        symbol=sym,
        profile=profile,
        quote=quote,
        quant_snapshot=quant_snap,
        key_stats=stats,
    )
