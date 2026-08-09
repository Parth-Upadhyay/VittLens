"""
Main API v1 Router combining all endpoint modules.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    chat,
    chats,
    company,
    filing,
    market,
    news,
    portfolio,
    portfolio_analyzer,
    preferences,
    quant,
    watchlist,
)
from app.macro_agent.api import router as macro_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(chats.router)
api_v1_router.include_router(company.router)
api_v1_router.include_router(filing.router)
api_v1_router.include_router(market.router)
api_v1_router.include_router(news.router)
api_v1_router.include_router(portfolio.router)
api_v1_router.include_router(portfolio_analyzer.router)
api_v1_router.include_router(preferences.router)
api_v1_router.include_router(quant.router)
api_v1_router.include_router(watchlist.router)
api_v1_router.include_router(macro_router)


@api_v1_router.get("/health", tags=["Health"])
def health_check():
    """Platform health check status endpoint."""
    return {"status": "ok", "service": "FinnAI Intelligence Platform"}
