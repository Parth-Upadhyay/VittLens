"""
Portfolio Controller REST API Endpoints.
Provides GET /portfolio, POST /portfolio, PUT /portfolio/{id}, and DELETE /portfolio/{id}.
Calculates live position market value, total P&L, and percentage changes.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.dependencies import get_current_user_or_guest, get_db, get_settings
from app.models import User
from app.auth import GuestSession
from app.models import PortfolioHolding
from app.services.market_service import MarketService
from app.utils import get_logger

logger = get_logger("finnai.api.portfolio")

router = APIRouter(prefix="/portfolio", tags=["Portfolio Controller"])


class HoldingCreateRequest(BaseModel):
    symbol: str = Field(..., description="Canonical ticker symbol (e.g. RELIANCE).")
    quantity: float = Field(..., gt=0, description="Quantity of shares held.")
    avg_price: float = Field(..., gt=0, description="Average buy price per share.")
    buy_date: Optional[str] = Field(default=None, description="Optional buy date string.")


class HoldingResponse(BaseModel):
    id: int
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    pnl: float
    pnl_percent: float
    buy_date: Optional[str] = None
    created_at: str


class PortfolioSummaryResponse(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_percent: float
    holdings: List[HoldingResponse] = Field(default_factory=list)


def get_market_service(settings: Settings = Depends(get_settings)) -> MarketService:
    return MarketService(settings)


@router.get("", response_model=PortfolioSummaryResponse, summary="Get portfolio holdings & P&L summary")
async def get_portfolio(
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
    market_svc: MarketService = Depends(get_market_service),
) -> PortfolioSummaryResponse:
    """Retrieve portfolio holdings with live price, market value, and total P&L metrics."""
    user, guest = auth_identity

    query = db.query(PortfolioHolding)
    if user:
        query = query.filter(PortfolioHolding.user_id == user.id)
    elif guest:
        query = query.filter(PortfolioHolding.guest_session_id == guest.session_id)
    else:
        return PortfolioSummaryResponse(total_value=0.0, total_cost=0.0, total_pnl=0.0, total_pnl_percent=0.0, holdings=[])

    holdings_orm = query.all()
    holding_responses: List[HoldingResponse] = []
    total_value = 0.0
    total_cost = 0.0

    for h in holdings_orm:
        try:
            quote = await market_svc.get_stock_quote(h.symbol)
            curr_price = quote.price if quote and quote.price > 0 else h.avg_price
        except Exception:
            curr_price = h.avg_price

        mkt_val = round(h.quantity * curr_price, 2)
        cost_val = round(h.quantity * h.avg_price, 2)
        pnl = round(mkt_val - cost_val, 2)
        pnl_pct = round((pnl / cost_val) * 100.0, 2) if cost_val > 0 else 0.0

        total_value += mkt_val
        total_cost += cost_val

        holding_responses.append(
            HoldingResponse(
                id=h.id,
                symbol=h.symbol.upper(),
                quantity=h.quantity,
                avg_price=h.avg_price,
                current_price=curr_price,
                market_value=mkt_val,
                pnl=pnl,
                pnl_percent=pnl_pct,
                buy_date=h.buy_date,
                created_at=h.created_at.isoformat(),
            )
        )

    tot_pnl = round(total_value - total_cost, 2)
    tot_pnl_pct = round((tot_pnl / total_cost) * 100.0, 2) if total_cost > 0 else 0.0

    return PortfolioSummaryResponse(
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        total_pnl=tot_pnl,
        total_pnl_percent=tot_pnl_pct,
        holdings=holding_responses,
    )


@router.post("", response_model=HoldingResponse, summary="Add holding to portfolio")
async def add_holding(
    body: HoldingCreateRequest,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
    market_svc: MarketService = Depends(get_market_service),
) -> HoldingResponse:
    """Add a new position holding to portfolio."""
    user, guest = auth_identity
    raw_sym = body.symbol.strip().upper()
    sym = market_svc.mapper.to_canonical_symbol(raw_sym)

    # Validate symbol by fetching quote before saving to database
    try:
        quote = await market_svc.get_stock_quote(sym)
        curr_price = quote.price if quote and quote.price > 0 else body.avg_price
    except Exception as e:
        logger.warning(f"Could not fetch initial market data for {sym}: {e}")
        curr_price = body.avg_price

    holding = PortfolioHolding(
        user_id=user.id if user else None,
        guest_session_id=guest.session_id if guest else None,
        symbol=sym,
        quantity=body.quantity,
        avg_price=body.avg_price,
        buy_date=body.buy_date,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)

    mkt_val = round(holding.quantity * curr_price, 2)
    cost_val = round(holding.quantity * holding.avg_price, 2)
    pnl = round(mkt_val - cost_val, 2)
    pnl_pct = round((pnl / cost_val) * 100.0, 2) if cost_val > 0 else 0.0

    return HoldingResponse(
        id=holding.id,
        symbol=holding.symbol,
        quantity=holding.quantity,
        avg_price=holding.avg_price,
        current_price=curr_price,
        market_value=mkt_val,
        pnl=pnl,
        pnl_percent=pnl_pct,
        buy_date=holding.buy_date,
        created_at=holding.created_at.isoformat(),
    )


class HoldingUpdateRequest(BaseModel):
    quantity: Optional[float] = Field(default=None, gt=0, description="Updated quantity of shares.")
    avg_price: Optional[float] = Field(default=None, gt=0, description="Updated average buy price.")
    buy_date: Optional[str] = Field(default=None, description="Updated buy date.")


@router.put("/{holding_id}", response_model=HoldingResponse, summary="Update a portfolio holding")
async def update_holding(
    holding_id: int,
    body: HoldingUpdateRequest,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
    market_svc: MarketService = Depends(get_market_service),
) -> HoldingResponse:
    """Update a portfolio position holding quantity or average buy price."""
    user, guest = auth_identity
    holding = db.query(PortfolioHolding).filter(PortfolioHolding.id == holding_id).first()

    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found.")

    if user and holding.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if body.quantity is not None:
        holding.quantity = body.quantity
    if body.avg_price is not None:
        holding.avg_price = body.avg_price
    if body.buy_date is not None:
        holding.buy_date = body.buy_date

    db.commit()
    db.refresh(holding)

    try:
        quote = await market_svc.get_stock_quote(holding.symbol)
        curr_price = quote.price if quote and quote.price > 0 else holding.avg_price
    except Exception:
        curr_price = holding.avg_price

    mkt_val = round(holding.quantity * curr_price, 2)
    cost_val = round(holding.quantity * holding.avg_price, 2)
    pnl = round(mkt_val - cost_val, 2)
    pnl_pct = round((pnl / cost_val) * 100.0, 2) if cost_val > 0 else 0.0

    return HoldingResponse(
        id=holding.id,
        symbol=holding.symbol,
        quantity=holding.quantity,
        avg_price=holding.avg_price,
        current_price=curr_price,
        market_value=mkt_val,
        pnl=pnl,
        pnl_percent=pnl_pct,
        buy_date=holding.buy_date,
        created_at=holding.created_at.isoformat(),
    )


@router.delete("/{holding_id}", summary="Remove a portfolio holding")
def remove_holding(
    holding_id: int,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Remove a portfolio holding position."""
    user, guest = auth_identity
    holding = db.query(PortfolioHolding).filter(PortfolioHolding.id == holding_id).first()

    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found.")

    if user and holding.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    db.delete(holding)
    db.commit()
    return {"status": "success", "message": f"Holding '{holding_id}' removed."}
