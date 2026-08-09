"""
Background Workers package for FinnAI Platform.
"""

from app.workers.news_worker import NewsWorker, start_news_worker_lifespan

__all__ = ["NewsWorker", "start_news_worker_lifespan"]
