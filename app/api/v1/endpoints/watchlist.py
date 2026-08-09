"""
Watchlist Management REST API Endpoints.
Provides GET /watchlist, POST /watchlist, and DELETE /watchlist/{symbol}.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.dependencies import get_current_user_or_guest, get_db, get_settings
from app.models import User
from app.auth import GuestSession
from app.models import WatchlistItem
from app.schemas import StockQuote
from app.services.market_service import MarketService
from app.utils import get_logger

logger = get_logger("finnai.api.watchlist")

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


class WatchlistAddRequest(BaseModel):
    symbol: str = Field(..., description="Canonical ticker symbol to add.")


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    quote: Optional[StockQuote] = None
    created_at: str


def get_market_service(settings: Settings = Depends(get_settings)) -> MarketService:
    return MarketService(settings)


@router.get("", response_model=List[WatchlistItemResponse], summary="Get user watchlist symbols")
async def get_watchlist(
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
    market_svc: MarketService = Depends(get_market_service),
) -> List[WatchlistItemResponse]:
    """Retrieve user watchlist items with live market quotes."""
    user, guest = auth_identity

    query = db.query(WatchlistItem)
    if user:
        query = query.filter(WatchlistItem.user_id == user.id)
    elif guest:
        query = query.filter(WatchlistItem.guest_session_id == guest.session_id)
    else:
        return []

    items = query.all()
    results = []
    for item in items:
        try:
            quote = await market_svc.get_stock_quote(item.symbol)
        except Exception:
            quote = None

        results.append(
            WatchlistItemResponse(
                id=item.id,
                symbol=item.symbol,
                quote=quote,
                created_at=item.created_at.isoformat(),
            )
        )

    return results


@router.post("", response_model=WatchlistItemResponse, summary="Add symbol to watchlist")
async def add_to_watchlist(
    body: WatchlistAddRequest,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
    market_svc: MarketService = Depends(get_market_service),
) -> WatchlistItemResponse:
    """Add a company symbol to user watchlist."""
    user, guest = auth_identity
    raw_sym = body.symbol.strip().upper()
    sym = market_svc.mapper.to_canonical_symbol(raw_sym)

    query = db.query(WatchlistItem).filter(WatchlistItem.symbol == sym)
    if user:
        existing = query.filter(WatchlistItem.user_id == user.id).first()
    elif guest:
        existing = query.filter(WatchlistItem.guest_session_id == guest.session_id).first()
    else:
        existing = None

    # Validate symbol by fetching quote before saving to database
    try:
        quote = await market_svc.get_stock_quote(sym)
    except Exception as e:
        logger.warning(f"Could not fetch initial market data for {sym}: {e}")
        quote = None

    if not existing:
        existing = WatchlistItem(
            user_id=user.id if user else None,
            guest_session_id=guest.session_id if guest else None,
            symbol=sym,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

    return WatchlistItemResponse(
        id=existing.id,
        symbol=existing.symbol,
        quote=quote,
        created_at=existing.created_at.isoformat(),
    )


@router.delete("/{symbol}", summary="Remove symbol from watchlist")
def remove_from_watchlist(
    symbol: str,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
    market_svc: MarketService = Depends(get_market_service),
) -> Dict[str, Any]:
    """Remove a symbol from user watchlist."""
    user, guest = auth_identity
    raw_sym = symbol.strip().upper()
    sym = market_svc.mapper.to_canonical_symbol(raw_sym)
    
    query = db.query(WatchlistItem).filter(WatchlistItem.symbol == sym)
    if user:
        item = query.filter(WatchlistItem.user_id == user.id).first()
    elif guest:
        item = query.filter(WatchlistItem.guest_session_id == guest.session_id).first()
    else:
        item = None

    if item:
        db.delete(item)
        db.commit()

    return {"status": "success", "message": f"Symbol '{sym}' removed from watchlist."}
