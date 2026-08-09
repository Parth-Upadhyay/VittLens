"""
Database Retention & Memory Budget Manager for FinnAI Platform.
Enforces 7-day auto-purge for news articles and strict 50-message FIFO cap per user/guest.
Ensures zero orphaned data by cascade-deleting empty chat threads.
"""

import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config.settings import Settings
from app.models import ChatMessage, ChatThread
from app.models import NewsArticle
from app.utils import get_logger

logger = get_logger("finnai.retention_service")


class RetentionService:
    """
    Service enforcing free-tier database retention budget policies.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.news_ttl_days = self.settings.news_article_ttl_days
        self.max_messages_per_user = 50

    def purge_expired_news(self, db: Session) -> int:
        """
        Delete news articles published older than news_article_ttl_days (7 days).

        Returns:
            Count of deleted news records.
        """
        cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=self.news_ttl_days)
        try:
            deleted_count = db.query(NewsArticle).filter(NewsArticle.published_time < cutoff_date).delete(synchronize_session=False)
            db.commit()
            if deleted_count > 0:
                logger.info(f"RetentionService: Auto-purged {deleted_count} news articles older than {self.news_ttl_days} days.")
            return deleted_count
        except Exception as e:
            db.rollback()
            logger.error(f"RetentionService purge_expired_news error: {e}")
            return 0

    def enforce_chat_message_limit(
        self, db: Session, user_id: Optional[int] = None, guest_session_id: Optional[str] = None
    ) -> int:
        """
        Enforce strict 50-message FIFO cap per user or guest session across all chat threads.
        When message count > 50, deletes oldest messages.
        Cascade-deletes any empty ChatThread objects left behind.

        Returns:
            Count of purged messages.
        """
        if not user_id and not guest_session_id:
            return 0

        try:
            # Query all thread IDs belonging to this user or guest
            thread_query = db.query(ChatThread.id)
            if user_id:
                thread_query = thread_query.filter(ChatThread.user_id == user_id)
            else:
                thread_query = thread_query.filter(ChatThread.guest_session_id == guest_session_id)

            thread_ids = [t[0] for t in thread_query.all()]
            if not thread_ids:
                return 0

            # Count total messages across user's threads
            total_messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.thread_id.in_(thread_ids))
                .count()
            )

            if total_messages <= self.max_messages_per_user:
                return 0

            overflow = total_messages - self.max_messages_per_user
            logger.warning(
                f"RetentionService: Message count ({total_messages}) exceeds limit ({self.max_messages_per_user}). "
                f"Purging oldest {overflow} messages..."
            )

            # Find oldest message IDs to purge
            oldest_msg_ids = [
                m[0]
                for m in (
                    db.query(ChatMessage.id)
                    .filter(ChatMessage.thread_id.in_(thread_ids))
                    .order_by(ChatMessage.created_at.asc())
                    .limit(overflow)
                    .all()
                )
            ]

            if oldest_msg_ids:
                db.query(ChatMessage).filter(ChatMessage.id.in_(oldest_msg_ids)).delete(synchronize_session=False)
                db.commit()

            # Cascade delete empty ChatThreads with 0 messages left
            empty_threads = (
                db.query(ChatThread)
                .filter(ChatThread.id.in_(thread_ids))
                .filter(~ChatThread.messages.any())
                .all()
            )

            if empty_threads:
                for th in empty_threads:
                    logger.info(f"RetentionService: Purging empty thread '{th.id}' ('{th.title}') after FIFO message cleanup.")
                    db.delete(th)
                db.commit()

            return len(oldest_msg_ids)

        except Exception as e:
            db.rollback()
            logger.error(f"RetentionService enforce_chat_message_limit error: {e}")
            return 0
