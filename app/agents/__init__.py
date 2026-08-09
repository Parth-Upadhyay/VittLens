"""
Agents package for FinnAI Platform.
Contains domain agents (Market, News, Filing, Quant) implementing BaseAgent interface.
"""

from app.agents.base_agent import BaseAgent
from app.agents.market_agent import MarketAgent
from app.agents.news_agent import NewsAgent
from app.agents.filing_agent import FilingAgent
from app.agents.quant_agent import QuantAgent

__all__ = [
    "BaseAgent",
    "MarketAgent",
    "NewsAgent",
    "FilingAgent",
    "QuantAgent",
]
