from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.cache import RedisClient
import json
from typing import Dict, Any

router = APIRouter(prefix="/macro", tags=["Macro Intelligence"])

@router.get("/latest", response_model=Dict[str, Any])
async def get_latest_macro(db: Session = Depends(get_db)):
    """
    Returns the most recent macro intelligence summary.
    Attempts to serve from Redis cache first.
    """
    try:
        redis = await RedisClient.get_client()
        if redis:
            cached = await redis.get("macro_agent:latest")
            if cached:
                return json.loads(cached)
    except Exception:
        pass
        
    # Fallback to database
    from app.macro_agent.storage.postgres import MacroRepository
    repo = MacroRepository(db)
    summary = repo.get_latest_summary()
    if summary:
        return {
            "timestamp": summary.timestamp.isoformat(),
            "summary": {
                "sentiment": summary.market_sentiment,
                "confidence": summary.confidence,
                "text": summary.summary_text,
                "watchlist": summary.watchlist
            }
        }
    return {"message": "No macro intelligence data available yet."}

@router.get("/history")
async def get_macro_history(limit: int = 10, db: Session = Depends(get_db)):
    """Returns historical macro runs."""
    from app.macro_agent.storage.postgres import MacroRepository
    from app.macro_agent.models import MacroRun
    
    runs = db.query(MacroRun).order_by(MacroRun.timestamp.desc()).limit(limit).all()
    return [{"id": r.id, "timestamp": r.timestamp.isoformat(), "status": r.status} for r in runs]
