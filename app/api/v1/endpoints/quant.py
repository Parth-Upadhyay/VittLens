"""
Quant & Ratio Analysis REST API Endpoints.
Exposes full financial ratio snapshots and multi-company comparative models.
"""

from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.config.settings import Settings
from app.dependencies import get_settings
from app.schemas import QuantComparison, RatioSnapshot
from app.services.quant_service import QuantService

router = APIRouter(prefix="/quant", tags=["Quantitative Analysis"])


class CompareRequest(BaseModel):
    symbols: List[str]


def get_quant_service(settings: Settings = Depends(get_settings)) -> QuantService:
    return QuantService(settings)


@router.get("/snapshot/{symbol}", response_model=RatioSnapshot, summary="Get full financial ratio snapshot")
def get_ratio_snapshot(
    symbol: str, service: QuantService = Depends(get_quant_service)
) -> RatioSnapshot:
    """Compute and return full quantitative ratio snapshot for a company symbol."""
    return service.get_full_ratio_snapshot(symbol)


@router.post("/compare", response_model=QuantComparison, summary="Generate multi-company side-by-side comparison")
def compare_companies(
    body: CompareRequest, service: QuantService = Depends(get_quant_service)
) -> QuantComparison:
    """Generate side-by-side financial ratio snapshot comparisons across multiple symbols."""
    return service.compare_symbols(body.symbols)
