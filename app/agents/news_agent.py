"""
News Agent for FinnAI Platform.
Consumes NewsService exclusively to read stored news summaries and AI enrichment records from PostgreSQL.
Never calls external news APIs directly.
Refactored to use LangGraph StateGraph orchestration.
"""

import asyncio
from typing import Dict, List, Optional
from langgraph.graph import StateGraph, END

from app.agents.base_agent import BaseAgent
from app.config.settings import Settings
from app.db.database import SessionLocal
from app.schemas import AgentContext, NewsAgentResult
from app.schemas import NewsArticleResponse
from app.schemas import NewsState
from app.services.news_service import NewsService
from app.utils import CompanyNormalizer
from app.utils import get_logger

logger = get_logger("finnai.agents.news")


class NewsAgent(BaseAgent):
    """
    News Domain Agent retrieving persisted news articles, sentiment, and AI enrichment from database.
    Orchestrated by LangGraph StateGraph.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        news_service: Optional[NewsService] = None,
    ) -> None:
        super().__init__(name="NewsAgent", settings=settings)
        self.news_service = news_service
        self.normalizer = CompanyNormalizer(self.settings.aliases_file_path)
        
        # Compile LangGraph StateGraph
        self.graph = self._build_graph()

    # --- LangGraph Nodes ---
    
    def node_fetch_news(self, state: NewsState) -> NewsState:
        """Fetch news from database for symbols in state, falling back or requesting Google RSS if needed."""
        symbols = state["symbols"]
        limit = state["limit"]
        importance_threshold = state["importance_threshold"]
        google_rss = state.get("google_rss", False)
        
        service = self.news_service or NewsService(state["db_session"])
        result_map: Dict[str, List[NewsArticleResponse]] = {}
        count = 0

        for symbol in symbols:
            raw_orm_list = service.get_latest_by_symbol(symbol=symbol, limit=limit)
            
            # Fetch from Google News RSS if explicitly requested or if no articles exist in database
            if google_rss or not raw_orm_list:
                try:
                    from app.services.news_fetcher import NewsFetcher
                    from app.schemas import NewsArticleCreate
                    
                    logger.info(f"Dynamically fetching Google RSS news for symbol '{symbol}'...")
                    fetcher = NewsFetcher(self.settings)
                    rss_articles = fetcher.fetch_google_news_rss(symbol)
                    
                    for art in rss_articles[:limit]:
                        try:
                            create_schema = NewsArticleCreate(
                                symbol=symbol,
                                headline=art["headline"],
                                url=art["url"],
                                source=art["source"],
                                published_time=art["published_time"],
                                raw_snippet=art["raw_snippet"],
                                summary=art["raw_snippet"],
                                sentiment="neutral",
                                importance_score=5
                            )
                            service.store_article(create_schema)
                        except Exception:
                            pass
                    # Re-fetch from DB to get the newly stored records
                    raw_orm_list = service.get_latest_by_symbol(symbol=symbol, limit=limit)
                except Exception as e:
                    logger.warning(f"Failed to dynamically fetch Google RSS news: {e}")

            pydantic_list: List[NewsArticleResponse] = []
            for item in raw_orm_list:
                if importance_threshold is not None:
                    score = getattr(item, "importance_score", None)
                    if score is not None and score < importance_threshold:
                        continue

                pydantic_list.append(NewsArticleResponse.model_validate(item))

            canonical = self.normalizer.normalize(symbol) or symbol.strip().upper()
            result_map[canonical] = pydantic_list
            count += len(pydantic_list)

        return {"articles_by_symbol": result_map, "total_articles": count}

    def _build_graph(self):
        """Compile the LangGraph StateGraph."""
        builder = StateGraph(NewsState)
        
        # Add Nodes
        builder.add_node("fetch_news", self.node_fetch_news)
        
        # Add Edges
        builder.set_entry_point("fetch_news")
        builder.add_edge("fetch_news", END)
        
        return builder.compile()

    async def _execute(self, context: AgentContext) -> NewsAgentResult:
        """
        Execute LangGraph news orchestration.
        """
        symbols = context.symbols or ["RELIANCE"]
        limit = context.top_k if context.top_k and context.top_k != 10 else self.settings.max_articles_per_company
        google_rss = context.metadata.get("google_rss", False)
        
        db = SessionLocal()
        try:
            initial_state = {
                "symbols": symbols,
                "limit": limit,
                "importance_threshold": context.importance_threshold,
                "db_session": db,
                "articles_by_symbol": {},
                "total_articles": 0,
                "google_rss": google_rss
            }
            
            # Since node_fetch_news is synchronous and does DB I/O, run the graph in a thread
            def _run_graph():
                return self.graph.invoke(initial_state)
                
            result_state = await asyncio.to_thread(_run_graph)
            
            return NewsAgentResult(
                articles_by_symbol=result_state["articles_by_symbol"],
                total_articles=result_state["total_articles"],
            )
        finally:
            db.close()
