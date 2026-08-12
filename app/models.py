from __future__ import annotations
from sqlalchemy import Column, Index, UniqueConstraint, func, text, Integer, String, Text, JSON, DateTime, Float, ForeignKey, Boolean

# Merged from models/*

from app.db.database import Base

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, JSON
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import Any
from typing import Any, Dict, List, Optional
from typing import List, Optional
from typing import Optional
import datetime



"""
SQLAlchemy 2.0 Chat History Models for FinnAI Platform.
Stores ChatThread and ChatMessage objects with cascade deletion rules.
"""




class ChatThread(Base):
    """
    Chat conversation thread grouping messages.
    """

    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New Financial Query", nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationships with cascade delete
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
    )


class ChatMessage(Base):
    """
    Individual turn message within a ChatThread.
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    images: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    sources: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    agents_used: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    symbols_queried: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    context_truncated: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        index=True,
    )

    thread: Mapped["ChatThread"] = relationship("ChatThread", back_populates="messages")

"""
SQLAlchemy 2.0 ORM models for News Pipeline (NewsArticle, CompanyAlias).
Includes strict Alembic-friendly indexing and unique constraints.
"""



class NewsArticle(Base):
    """
    SQLAlchemy model storing original news metadata and AI enrichment parameters.
    """

    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Original metadata
    headline = Column(Text, nullable=False)
    url = Column(String(2048), unique=True, index=True, nullable=False)
    source = Column(String(255), nullable=False)
    author = Column(String(255), nullable=True)
    published_time = Column(DateTime(timezone=True), index=True, nullable=False)
    fetch_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Normalized company identification
    canonical_symbol = Column(String(32), index=True, nullable=False)
    original_company_name = Column(String(255), nullable=False)

    # Raw content snippet
    raw_snippet = Column(Text, nullable=True)

    # AI Enrichment fields
    summary = Column(Text, nullable=True)
    sentiment = Column(String(32), nullable=True)  # 'positive', 'negative', 'neutral'
    topic_tags = Column(JSON, nullable=True)        # list of topic tag strings
    event_type = Column(String(255), nullable=True)   # e.g., 'earnings', 'regulatory'
    importance_score = Column(Integer, index=True, nullable=True) # Scale 1-10
    key_entities = Column(JSON, nullable=True)      # list/dict of mentioned entities
    key_points = Column(JSON, nullable=True)        # list of key analytical bullet points

    __table_args__ = (
        Index("idx_news_symbol_published", "canonical_symbol", "published_time"),
        Index("idx_news_symbol_importance", "canonical_symbol", "importance_score"),
    )

    def __repr__(self) -> str:
        return f"<NewsArticle id={self.id} symbol='{self.canonical_symbol}' headline='{self.headline[:30]}...'>"


class CompanyAlias(Base):
    """
    SQLAlchemy model storing mapped company name variations to canonical symbols.
    """

    __tablename__ = "company_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alias = Column(String(255), unique=True, index=True, nullable=False)
    canonical_symbol = Column(String(32), index=True, nullable=False)

    def __repr__(self) -> str:
        return f"<CompanyAlias alias='{self.alias}' -> symbol='{self.canonical_symbol}'>"

"""
SQLAlchemy ORM Model for Portfolio Analysis persistence.
Stores structured analysis reports capped at 10 per authenticated user (FIFO).
"""


class PortfolioAnalysis(Base):
    """
    Model representing a saved portfolio analysis report.
    """

    __tablename__ = "portfolio_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    summary = Column(Text, nullable=False)
    portfolio_metrics = Column(JSON, nullable=False)
    holdings = Column(JSON, nullable=False)
    allocation = Column(JSON, nullable=False)
    rebalancing_suggestions = Column(JSON, nullable=True)
    red_flags = Column(JSON, nullable=True)
    news_alerts = Column(JSON, nullable=True)
    benchmark_comparison = Column(JSON, nullable=True)
    tax_loss_harvesting = Column(JSON, nullable=True)
    images = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<PortfolioAnalysis id={self.id} user_id={self.user_id} created_at={self.created_at}>"

"""
SQLAlchemy 2.0 User Database Model.
Stores Google OAuth user profiles and account metadata.
"""




class User(Base):
    """
    User entity table in PostgreSQL / SQLite database.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50), default="google", nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    purpose_of_visit: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

"""
SQLAlchemy 2.0 Models for User Data (Portfolio Holdings, Preferences, Watchlist).
"""




class PortfolioHolding(Base):
    """
    User portfolio position holding record.
    """

    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)
    buy_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )


class UserPreferences(Base):
    """
    User UI preferences & prompt settings.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True, unique=True)
    guest_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True, unique=True)
    answer_style: Mapped[str] = mapped_column(String(50), default="Detailed", nullable=False)  # Concise | Detailed | Beginner | Expert
    default_symbols: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["RELIANCE", "TCS", "INFY", "HDFCBANK"], nullable=False)
    theme: Mapped[str] = mapped_column(String(20), default="Light", nullable=False)  # Dark | Light | System

    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )


class WatchlistItem(Base):
    """
    User watchlist ticker tracking item.
    """

    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

class UserRateLimit(Base):
    """
    Tracks daily API queries for authenticated users.
    """
    __tablename__ = "user_rate_limits"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    queries_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reset_date: Mapped[str] = mapped_column(
        String(20),
        default=lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        nullable=False
    )
