from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from app.db.database import Base

# ==============================================================================
# Pydantic Schemas
# ==============================================================================

class MarketSnapshotSchema(BaseModel):
    timestamp: datetime
    data: Dict[str, Optional[float]] # e.g. {"nifty": 25783, "oil": 72.1, ...}

class NewsArticleSchema(BaseModel):
    source: str
    title: str
    url: str
    published_at: str
    summary: Optional[str] = None

class MacroEventSchema(BaseModel):
    title: str
    category: str
    summary: str
    confidence: float
    importance: str # critical, high, medium, low
    source: str
    credibility: float

class SectorImpactSchema(BaseModel):
    sector: str
    reason: str
    impact: str # Positive, Negative, Neutral

class CompanyImpactSchema(BaseModel):
    company: str
    reason: str
    impact: str # Positive, Negative, Neutral

class MacroSummarySchema(BaseModel):
    market_sentiment: str
    confidence: float
    summary_text: str # From LLM
    major_events: List[MacroEventSchema] = Field(default_factory=list)
    positive_sectors: List[SectorImpactSchema] = Field(default_factory=list)
    negative_sectors: List[SectorImpactSchema] = Field(default_factory=list)
    affected_companies: List[CompanyImpactSchema] = Field(default_factory=list)
    watchlist: List[str] = Field(default_factory=list)

class MacroRunResponse(BaseModel):
    id: Optional[int] = None
    timestamp: datetime
    snapshot: Optional[MarketSnapshotSchema] = None
    summary: Optional[MacroSummarySchema] = None

# ==============================================================================
# SQLAlchemy Models
# ==============================================================================

class MacroRun(Base):
    __tablename__ = "macro_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String, default="completed") # e.g. running, failed, completed
    error_message = Column(String, nullable=True)

class MarketSnapshot(Base):
    __tablename__ = "macro_market_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("macro_runs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    data = Column(JSON, default=dict) # Raw JSON of indices

class NewsArticle(Base):
    __tablename__ = "macro_news_articles"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("macro_runs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String)
    title = Column(String)
    url = Column(String, unique=True, index=True)
    published_at = Column(String)
    summary = Column(String, nullable=True)

class MacroEvent(Base):
    __tablename__ = "macro_events"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("macro_runs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    title = Column(String)
    category = Column(String, index=True)
    summary = Column(String)
    confidence = Column(Float)
    importance = Column(String)
    source = Column(String)
    credibility = Column(Float)

class SectorImpact(Base):
    __tablename__ = "macro_sector_impacts"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("macro_runs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    sector = Column(String, index=True)
    reason = Column(String)
    impact = Column(String) # Positive, Negative

class CompanyImpact(Base):
    __tablename__ = "macro_company_impacts"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("macro_runs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    company = Column(String, index=True)
    reason = Column(String)
    impact = Column(String) # Positive, Negative

class MacroSummary(Base):
    __tablename__ = "macro_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("macro_runs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    market_sentiment = Column(String)
    confidence = Column(Float)
    summary_text = Column(String) # LLM output
    watchlist = Column(JSON, default=list) # List of strings

