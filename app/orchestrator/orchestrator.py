"""
Master Financial Orchestrator for FinnAI Platform.
Coordinates rule-based planning, concurrent domain agent execution, context aggregation with token budget enforcement,
single high-capacity LLM synthesis via GroqProvider (llama-3.3-70b-versatile), real-time event & token streaming, and response formatting.
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.agents.filing_agent import FilingAgent
from app.agents.market_agent import MarketAgent
from app.agents.news_agent import NewsAgent
from app.agents.quant_agent import QuantAgent
from app.config.settings import Settings
from app.orchestrator.context_builder import ContextBuilder
from app.orchestrator.planner import Planner
from app.orchestrator.prompt_builder import OrchestratorPromptBuilder
from app.orchestrator.response_formatter import ResponseFormatter
from app.prompts import FINANCIAL_ANALYST_SYSTEM_PROMPT
from app.schemas import AgentContext, AgentResult
from app.schemas import ChatRequest, ChatResponse, InvestorContext
from app.services.factory import get_llm_provider
from app.services.base_provider import LLMProvider
from app.utils import get_logger

logger = get_logger("finnai.orchestrator")


class FinancialOrchestrator:
    """
    Master Orchestrator managing multi-agent dispatch, token guard context building,
    single high-capacity LLM synthesis, real-time event streaming, and response formatting.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.planner = Planner(self.settings)
        self.context_builder = ContextBuilder(self.settings)
        self.prompt_builder = OrchestratorPromptBuilder()
        self.response_formatter = ResponseFormatter()

        # Domain Agents
        self.market_agent = MarketAgent(self.settings)
        self.news_agent = NewsAgent(self.settings)
        self.filing_agent = FilingAgent(self.settings)
        self.quant_agent = QuantAgent(self.settings)

        # High-capacity Groq LLM Provider for single synthesis call
        self.llm_provider = llm_provider or get_llm_provider("groq", settings=self.settings)

    async def _get_latest_macro_summary(self) -> Optional[dict]:
        """
        Retrieves the latest macro intelligence summary from Redis cache, falling back to SQLite/Postgres DB.
        """
        try:
            from app.cache import RedisClient
            redis = await RedisClient.get_client()
            if redis:
                cached = await redis.get("macro_agent:latest")
                if cached:
                    return json.loads(cached)
        except Exception as e:
            logger.warning(f"Failed to fetch macro intelligence from Redis: {e}")

        try:
            from app.db.database import SessionLocal
            from app.macro_agent.storage.postgres import MacroRepository
            from app.macro_agent.models import MacroEvent, SectorImpact
            db = SessionLocal()
            try:
                repo = MacroRepository(db)
                summary = repo.get_latest_summary()
                if summary:
                    events = db.query(MacroEvent).filter(MacroEvent.run_id == summary.run_id).all()
                    sector_impacts = db.query(SectorImpact).filter(SectorImpact.run_id == summary.run_id).all()
                    return {
                        "timestamp": summary.timestamp.isoformat(),
                        "summary": {
                            "sentiment": summary.market_sentiment,
                            "confidence": summary.confidence,
                            "text": summary.summary_text,
                            "watchlist": summary.watchlist
                        },
                        "events": [
                            {
                                "title": ev.title,
                                "category": ev.category,
                                "summary": ev.summary,
                                "importance": ev.importance,
                                "source": ev.source
                            } for ev in events
                        ],
                        "sector_impacts": [
                            {
                                "sector": s.sector,
                                "reason": s.reason,
                                "impact": s.impact
                            } for s in sector_impacts
                        ]
                    }
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to fetch macro intelligence fallback summary from DB: {e}")
        return None

    async def _execute_plan_and_build_context(
        self, request: ChatRequest
    ) -> tuple[InvestorContext, str, List[str], List[str], List[AgentResult]]:
        """
        Helper executing Planner, dispatching agents concurrently, and building InvestorContext & prompt.
        """
        plan = self.planner.create_plan(request)
        symbols = plan.extracted_symbols
        q = request.question

        agent_coroutines = []
        agent_names_used: List[str] = []

        for task in plan.tasks:
            agent_names_used.append(task.agent_name)
            metadata = {}
            if "google_rss" in task.params:
                metadata["google_rss"] = task.params["google_rss"]

            ctx = AgentContext(
                symbols=task.symbols,
                query=task.query,
                period=task.params.get("period", "1mo"),
                top_k=task.params.get("top_k", 5),
                metadata=metadata
            )

            if task.agent_name == "MarketAgent":
                agent_coroutines.append(self.market_agent.run(ctx))
            elif task.agent_name == "NewsAgent":
                agent_coroutines.append(self.news_agent.run(ctx))
            elif task.agent_name == "FilingAgent":
                agent_coroutines.append(self.filing_agent.run(ctx))
            elif task.agent_name == "QuantAgent":
                agent_coroutines.append(self.quant_agent.run(ctx))

        logger.info(f"Executing {len(agent_coroutines)} domain agents concurrently via asyncio.gather()...")
        agent_results: List[AgentResult] = await asyncio.gather(*agent_coroutines)

        context = self.context_builder.build_context(agent_results)
        macro_summary = await self._get_latest_macro_summary()
        synthesis_prompt = self.prompt_builder.build_prompt(request.question, context, request.chat_history, macro_summary=macro_summary, queried_symbols=symbols)

        return context, synthesis_prompt, agent_names_used, symbols, agent_results

    async def process_query(self, request: ChatRequest) -> ChatResponse:
        """
        Process a user question end-to-end synchronously.
        """
        overall_start = time.perf_counter()
        logger.info(f"=== FinancialOrchestrator processing query: '{request.question[:50]}...' ===")

        context, synthesis_prompt, agent_names_used, symbols, _ = (
            await self._execute_plan_and_build_context(request)
        )

        synthesis_model = self.settings.synthesis_model
        logger.info(f"Invoking Groq LLM synthesis model '{synthesis_model}' (EXACTLY 1 CALL)...")

        start_llm = time.perf_counter()
        llm_response = self.llm_provider.generate(
            system_prompt=FINANCIAL_ANALYST_SYSTEM_PROMPT,
            user_prompt=synthesis_prompt,
            temperature=0.2,
            model=synthesis_model,
        )
        llm_latency_ms = (time.perf_counter() - start_llm) * 1000.0
        logger.info(f"Groq LLM synthesis completed in {llm_latency_ms:.2f} ms.")

        response = self.response_formatter.format_response(
            raw_llm_answer=llm_response.content,
            context=context,
            agents_used=agent_names_used,
            symbols_queried=symbols,
        )

        total_latency_ms = (time.perf_counter() - overall_start) * 1000.0
        logger.info(f"=== FinancialOrchestrator query completed in {total_latency_ms:.2f} ms ===")
        return response

    async def process_query_event_stream(
        self, request: ChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process user query and yield real-time progress events followed by streaming LLM text tokens.

        Yields SSE-compatible event dictionaries:
        - {"type": "status", "stage": "planning", "message": "..."}
        - {"type": "agent_start", "agent": "MarketAgent", "message": "..."}
        - {"type": "agent_complete", "agent": "MarketAgent", "latency_ms": 120.0}
        - {"type": "token", "content": "..."}
        - {"type": "done", "images": [...], "sources": [...]}
        """
        overall_start = time.perf_counter()

        # Step 1: Planning
        yield {
            "type": "status",
            "stage": "planning",
            "message": f"🔍 Analyzing query intent & extracting company symbols...",
        }
        await asyncio.sleep(0.05)

        plan = self.planner.create_plan(request)
        symbols = plan.extracted_symbols
        q = request.question

        yield {
            "type": "status",
            "stage": "planning_complete",
            "message": f"📋 Target symbols identified: {symbols}. Dispatched {len(plan.tasks)} domain agents concurrently.",
            "symbols": symbols,
        }
        await asyncio.sleep(0.05)

        # Step 2: Agent Execution
        agent_coroutines = []
        agent_names_used: List[str] = []

        for task in plan.tasks:
            agent_names_used.append(task.agent_name)
            yield {
                "type": "agent_start",
                "agent": task.agent_name,
                "message": f"🚀 Launched {task.agent_name} for symbols {task.symbols}...",
            }
            metadata = {}
            if "google_rss" in task.params:
                metadata["google_rss"] = task.params["google_rss"]

            ctx = AgentContext(
                symbols=task.symbols,
                query=task.query,
                period=task.params.get("period", "1mo"),
                top_k=task.params.get("top_k", 5),
                metadata=metadata
            )

            if task.agent_name == "MarketAgent":
                agent_coroutines.append(self.market_agent.run(ctx))
            elif task.agent_name == "NewsAgent":
                agent_coroutines.append(self.news_agent.run(ctx))
            elif task.agent_name == "FilingAgent":
                agent_coroutines.append(self.filing_agent.run(ctx))
            elif task.agent_name == "QuantAgent":
                agent_coroutines.append(self.quant_agent.run(ctx))

        agent_results: List[AgentResult] = await asyncio.gather(*agent_coroutines)

        for res in agent_results:
            yield {
                "type": "agent_complete",
                "agent": res.agent_name,
                "status": res.status,
                "latency_ms": res.execution_time_ms,
                "message": f"✅ {res.agent_name} finished in {res.execution_time_ms} ms.",
            }

        # Step 3: Context Building & Token Guard
        yield {
            "type": "status",
            "stage": "context_building",
            "message": "📊 Aggregating agent context & enforcing Token Guard budget bounds (100k max tokens)...",
        }
        await asyncio.sleep(0.05)

        context = self.context_builder.build_context(agent_results)
        macro_summary = await self._get_latest_macro_summary()
        synthesis_prompt = self.prompt_builder.build_prompt(request.question, context, request.chat_history, macro_summary=macro_summary)

        synthesis_model = self.settings.synthesis_model
        yield {
            "type": "status",
            "stage": "synthesis_start",
            "message": f"💡 Invoking Groq LLM synthesis model '{synthesis_model}'...",
            "model": synthesis_model,
        }
        await asyncio.sleep(0.05)

        # Step 4: Token Streaming
        token_gen = self.llm_provider.generate_stream(
            system_prompt=FINANCIAL_ANALYST_SYSTEM_PROMPT,
            user_prompt=synthesis_prompt,
            temperature=0.2,
            model=synthesis_model,
        )

        for token in token_gen:
            yield {"type": "token", "content": token}
            await asyncio.sleep(0)

        # Step 5: Final Sources & Image Payload
        response = self.response_formatter.format_response(
            raw_llm_answer="",
            context=context,
            agents_used=agent_names_used,
            symbols_queried=symbols,
        )

        total_latency_ms = (time.perf_counter() - overall_start) * 1000.0

        yield {
            "type": "done",
            "images": response.images,
            "sources": response.sources,
            "agents_used": response.agents_used,
            "symbols_queried": response.symbols_queried,
            "context_truncated": response.context_truncated,
            "total_latency_ms": round(total_latency_ms, 2),
        }
