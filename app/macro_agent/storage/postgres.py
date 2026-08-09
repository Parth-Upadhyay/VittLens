from sqlalchemy.orm import Session
from app.macro_agent.models import (
    MacroRun, MarketSnapshot, NewsArticle, MacroEvent,
    SectorImpact, CompanyImpact, MacroSummary
)
from typing import List, Optional

class MacroRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self) -> MacroRun:
        run = MacroRun()
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_run_status(self, run_id: int, status: str, error: Optional[str] = None):
        run = self.db.query(MacroRun).filter(MacroRun.id == run_id).first()
        if run:
            run.status = status
            if error:
                run.error_message = error
            self.db.commit()

    def save_market_snapshot(self, run_id: int, snapshot_data: dict) -> MarketSnapshot:
        snapshot = MarketSnapshot(run_id=run_id, data=snapshot_data)
        self.db.add(snapshot)
        self.db.commit()
        return snapshot

    def save_news_articles(self, run_id: int, articles: List[dict]):
        for art in articles:
            # Simple upsert/ignore if exists would be better, but we can catch IntegrityError or just query first
            existing = self.db.query(NewsArticle).filter(NewsArticle.url == art["url"]).first()
            if not existing:
                news = NewsArticle(
                    run_id=run_id,
                    source=art.get("source"),
                    title=art.get("title"),
                    url=art.get("url"),
                    published_at=art.get("published_at"),
                    summary=art.get("summary")
                )
                self.db.add(news)
        self.db.commit()

    def save_events(self, run_id: int, events: List[dict]):
        for ev in events:
            db_ev = MacroEvent(
                run_id=run_id,
                title=ev.get("title"),
                category=ev.get("category"),
                summary=ev.get("summary"),
                confidence=ev.get("confidence", 0.0),
                importance=ev.get("importance", "low"),
                source=ev.get("source"),
                credibility=ev.get("credibility", 0.0)
            )
            self.db.add(db_ev)
        self.db.commit()

    def save_sector_impacts(self, run_id: int, impacts: List[dict]):
        for imp in impacts:
            db_imp = SectorImpact(
                run_id=run_id,
                sector=imp.get("sector"),
                reason=imp.get("reason"),
                impact=imp.get("impact")
            )
            self.db.add(db_imp)
        self.db.commit()

    def save_summary(self, run_id: int, sentiment: str, confidence: float, summary_text: str, watchlist: List[str]):
        summary = MacroSummary(
            run_id=run_id,
            market_sentiment=sentiment,
            confidence=confidence,
            summary_text=summary_text,
            watchlist=watchlist
        )
        self.db.add(summary)
        self.db.commit()
        return summary
    
    def get_latest_summary(self) -> Optional[MacroSummary]:
        return self.db.query(MacroSummary).order_by(MacroSummary.timestamp.desc()).first()
