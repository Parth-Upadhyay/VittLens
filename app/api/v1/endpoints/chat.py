"""
Chat & Financial Analysis API Endpoints.
Provides POST /api/v1/chat (JSON completion) and POST /api/v1/chat/stream (SSE token streaming).
Supports chat thread persistence, AI title generation, and 50-message FIFO retention cap enforcement.
"""

import json
import uuid
import re
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import GuestSession
from app.dependencies import get_current_user_or_guest, enforce_rate_limit, get_db, get_orchestrator, get_settings
from app.models import ChatMessage, ChatThread
from app.models import User
from app.orchestrator.orchestrator import FinancialOrchestrator
from app.schemas import ChatRequest, ChatResponse
from app.services.factory import get_llm_provider
from app.services.retention_service import RetentionService
from app.utils import get_logger

logger = get_logger("finnai.api.chat")

router = APIRouter(prefix="/chat", tags=["Chat & Analysis"])


class ExtendedChatRequest(ChatRequest):
    """Chat request extending ChatRequest with optional thread ID."""
    chat_id: Optional[str] = Field(default=None, description="Optional existing chat thread ID.")


class EnrichedChatResponse(ChatResponse):
    """Extended response model including thread ID and guest query count metadata."""
    chat_id: str
    queries_remaining: int = -1  # -1 = Unlimited (authenticated user)
    guest_prompt_message: Optional[str] = None


def generate_thread_title(question: str, settings) -> str:
    """Generate a concise AI summary title for a new chat thread using Groq."""
    try:
        provider = get_llm_provider("groq", settings=settings)
        res = provider.generate(
            system_prompt="Summarize the question into a 3-5 word concise thread title. Return title text ONLY. No quotes.",
            user_prompt=question,
            max_tokens=15,
        )
        clean_title = res.content.strip().strip('"\'')
        return clean_title if clean_title else question[:30] + "..."
    except Exception:
        return question[:30] + "..."


_GIBBERISH_REJECT_MSG = (
    "That doesn't look like a valid query. "
    "Please type a question about Indian stocks, markets, or company financials."
)

_OFF_TOPIC_REJECT_MSG = (
    "I can only answer questions about Indian equity markets, stocks, company financials, "
    "and business news. Please ask something finance-related (e.g. 'What is the P/E ratio of TCS?', "
    "'Compare RELIANCE vs INFY', 'Latest news on HDFCBANK')."
)

_KEYBOARD_PATTERNS = [
    "asdf", "sdfg", "dfgh", "fghj", "ghjk", "hjkl",
    "qwer", "wert", "erty", "rtyu", "tyui", "yuio", "uiop",
    "zxcv", "xcvb", "cvbn", "vbnm",
    "qwerty", "asdfg", "zxcvb",
]

# Finance-related keywords — if ANY of these appear in the query, it passes the relevance check
_FINANCE_KEYWORDS = {
    # Market & trading
    "stock", "stocks", "share", "shares", "equity", "market", "markets", "trading", "trade",
    "invest", "investor", "investing", "investment", "portfolio", "watchlist",
    "buy", "sell", "hold", "long", "short", "bullish", "bearish",
    "nifty", "sensex", "bse", "nse", "index", "indices",
    "ipo", "listing", "demat", "broker", "brokerage",
    # Financial metrics
    "price", "pe", "p/e", "ratio", "pb", "p/b", "roe", "roce", "eps",
    "revenue", "profit", "loss", "margin", "ebitda", "ebit", "pat",
    "earnings", "quarter", "quarterly", "annual", "results", "guidance",
    "dividend", "yield", "payout", "bonus", "split", "buyback",
    "debt", "equity", "leverage", "solvency", "liquidity", "capital",
    "market cap", "marketcap", "valuation", "overvalued", "undervalued",
    "pe ratio", "forward pe", "peg", "book value", "intrinsic",
    # Company & sector terms
    "company", "companies", "sector", "industry", "conglomerate",
    "banking", "bank", "fintech", "nbfc", "insurance", "it sector",
    "pharma", "pharmaceutical", "fmcg", "automobile", "auto", "energy",
    "telecom", "infrastructure", "real estate", "realty", "retail",
    # Macro & economy
    "economy", "gdp", "inflation", "cpi", "wpi", "repo rate", "rbi",
    "sebi", "fed", "federal reserve", "interest rate", "fiscal", "monetary",
    "crude", "oil", "gold", "commodity", "forex", "rupee", "inr", "dollar",
    "fii", "dii", "fpi", "mutual fund", "mf", "etf", "bond", "treasury",
    # Chart / analysis
    "analysis", "analyse", "analyze", "technical", "fundamental", "chart",
    "support", "resistance", "trend", "momentum", "rsi", "macd", "moving average",
    "52 week", "52-week", "high", "low", "target", "forecast", "prediction",
    "outlook", "report", "filing", "annual report", "balance sheet",
    "income statement", "cash flow", "news", "catalyst",
    # Common Indian NIFTY companies & tickers (sampled)
    "reliance", "tcs", "infosys", "infy", "hdfc", "icici", "sbi", "wipro",
    "bhartiartl", "airtel", "hcltech", "kotak", "axisbank", "bajaj",
    "tatasteel", "tata", "adani", "ongc", "ntpc", "hindunilvr", "hul",
    "maruti", "suzuki", "sunpharma", "drreddy", "cipla", "ultracemco",
    "titan", "nestle", "itc", "powergrid", "coalindia", "jswsteel",
    "grasim", "hdfclife", "sbilife", "lici", "zomato", "nykaa", "paytm",
    "dmart", "avenue", "pidilitind", "shreecem", "siemens", "havells",
    "indigo", "interglobe", "irctc", "rail", "defence", "psu",
    # Question words that in finance context are valid
    "compare", "comparison", "vs", "versus", "difference", "best", "worst",
    "which", "recommend", "should", "worth", "performance", "return",
}


from app.services.factory import get_llm_provider

def _build_universe_tickers() -> set:
    terms = {
        "reliance", "tcs", "infosys", "infy", "hdfc", "icici", "sbi", "wipro",
        "bhartiartl", "airtel", "hcltech", "kotak", "axisbank", "bajaj",
        "tatasteel", "tata", "adani", "ongc", "ntpc", "hindunilvr", "hul",
        "maruti", "suzuki", "sunpharma", "drreddy", "cipla", "ultracemco",
        "titan", "nestle", "itc", "powergrid", "coalindia", "jswsteel",
        "grasim", "hdfclife", "sbilife", "lici", "zomato", "nykaa", "paytm",
        "dmart", "avenue", "pidilitind", "shreecem", "siemens", "havells",
        "indigo", "interglobe", "irctc", "hdfcbank", "icicibank"
    }
    try:
        from pathlib import Path
        import json
        universe_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "universe.json"
        with open(universe_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for category in data.values():
            for key, val in category.items():
                if val.get("symbol"):
                    terms.add(val["symbol"].lower())
                if val.get("name"):
                    terms.add(val["name"].lower())
    except Exception as e:
        logger.warning(f"Could not load universe terms for guardrail: {e}")
        
    # Sort by length descending so longer terms (full names) match before shorter ones
    return sorted([t for t in terms if len(t) >= 2], key=len, reverse=True)

_TICKERS_PATTERN = re.compile(
    r'\b(?:' + '|'.join(re.escape(t) for t in _build_universe_tickers()) + r')\b',
    re.IGNORECASE
)

async def _is_valid_financial_query(text: str, settings) -> bool:
    """
    Small LLM Intent Classifier (Prompt Guard).
    Uses a fast, low-parameter model to determine if the user query is a valid 
    financial/stock/market question or command, preventing off-topic abuse.
    """
    # Fast-pass heuristic: if explicit ticker symbols are present, immediately approve.
    q_lower = text.lower()
    if any(kw in q_lower for kw in ["compare", "vs", "stock", "price", "market", "economy", "indian", "india", "war", "global", "macro", "geopolitics", "rate", "gdp", "rbi", "fed"]):
        return True
        
    if _TICKERS_PATTERN.search(q_lower):
        return True
        
    try:
        provider = get_llm_provider("groq", settings=settings)
        # Use openai/gpt-oss-safeguard-20b as primary model; fallback models handle backups automatically
        res = provider.generate(
            model="openai/gpt-oss-safeguard-20b",
            system_prompt=(
                "You are a strict Prompt Guard for a financial AI assistant. "
                "Classify if the user's query is related to finance, stocks, investing, companies, or macroeconomics. "
                "Respond with EXACTLY 'YES' if it is valid, or 'NO' if it is off-topic (e.g. coding, recipes, general chat, gibberish)."
            ),
            user_prompt=f"Query: {text}",
            max_tokens=4,
            temperature=0.0
        )
        answer = res.content.strip().upper()
        return "YES" in answer
    except Exception:
        # Fail open if the LLM guard fails
        return True


@router.post("", response_model=EnrichedChatResponse, summary="Execute financial analysis query")
async def process_chat_query(
    request_body: ExtendedChatRequest,
    auth_identity: tuple = Depends(enforce_rate_limit),
    orchestrator: FinancialOrchestrator = Depends(get_orchestrator),
    db: Session = Depends(get_db),
    settings = Depends(get_settings),
) -> EnrichedChatResponse:
    """
    Execute multi-agent financial query for authenticated users or guest sessions.
    Persists thread & messages and enforces 50-message FIFO retention cap.
    """
    user, guest = auth_identity
    queries_remaining = -1
    guest_prompt = None

    if guest:
        queries_remaining = guest.queries_remaining
        if not guest.purpose_of_visit:
            guest_prompt = (
                "Welcome Guest! What brings you to FinnAI today? "
                "Submit your purpose of visit (e.g. Retail Investor, Research, Trader, Academic) "
                "via POST /api/v1/auth/guest/purpose."
            )

    # Prompt Guard: Small LLM Classifier blocking non-financial queries
    is_valid = await _is_valid_financial_query(request_body.question, settings)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_OFF_TOPIC_REJECT_MSG,
        )

    # 1. Resolve or Create ChatThread
    chat_id = request_body.chat_id
    if not chat_id:
        chat_id = str(uuid.uuid4())
        title = generate_thread_title(request_body.question, settings)
        thread = ChatThread(
            id=chat_id,
            user_id=user.id if user else None,
            guest_session_id=guest.session_id if guest else None,
            title=title,
        )
        db.add(thread)
        db.commit()
    else:
        thread = db.query(ChatThread).filter(ChatThread.id == chat_id).first()
        if not thread:
            chat_id = str(uuid.uuid4())
            title = generate_thread_title(request_body.question, settings)
            thread = ChatThread(
                id=chat_id,
                user_id=user.id if user else None,
                guest_session_id=guest.session_id if guest else None,
                title=title,
            )
            db.add(thread)
            db.commit()

    # 2. Persist User Prompt Message
    user_msg = ChatMessage(
        thread_id=chat_id,
        role="user",
        content=request_body.question,
    )
    db.add(user_msg)
    db.commit()

    # 3. Load prior conversation history from thread and inject into request
    MAX_HISTORY_TURNS = 8  # Load up to 8 prior messages (4 user + 4 assistant turns)
    try:
        prior_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.thread_id == chat_id)
            .order_by(ChatMessage.id.desc())
            .limit(MAX_HISTORY_TURNS)
            .all()
        )
        # Reverse to chronological order, exclude the just-added user message
        prior_messages = list(reversed(prior_messages))
        # Filter out the message we just inserted (it's the last one)
        prior_messages = [m for m in prior_messages if m.content != request_body.question or m.role != "user" or m.id == prior_messages[-1].id]
        # Build history list (skip the current user message itself)
        history_pairs = [
            {"role": m.role, "content": m.content[:1500]}  # Truncate long messages
            for m in prior_messages
            if not (m.role == "user" and m.content == request_body.question)
        ]
        request_body = request_body.model_copy(update={"chat_history": history_pairs})
    except Exception as e:
        logger.warning(f"Failed to load chat history for thread '{chat_id}': {e}")

    # 4. Delegate to FinancialOrchestrator
    base_response: ChatResponse = await orchestrator.process_query(request_body)

    # 4. Persist Assistant Response Message
    assistant_msg = ChatMessage(
        thread_id=chat_id,
        role="assistant",
        content=base_response.answer,
        images=base_response.images,
        sources=base_response.sources,
        agents_used=base_response.agents_used,
        symbols_queried=base_response.symbols_queried,
        context_truncated=base_response.context_truncated,
    )
    db.add(assistant_msg)
    db.commit()

    # 5. Enforce 50-Message FIFO Retention Cap
    retention_svc = RetentionService(settings)
    retention_svc.enforce_chat_message_limit(
        db=db,
        user_id=user.id if user else None,
        guest_session_id=guest.session_id if guest else None,
    )

    return EnrichedChatResponse(
        chat_id=chat_id,
        answer=base_response.answer,
        sources=base_response.sources,
        agents_used=base_response.agents_used,
        images=base_response.images,
        symbols_queried=base_response.symbols_queried,
        context_truncated=base_response.context_truncated,
        confidence=base_response.confidence,
        timestamp=base_response.timestamp,
        queries_remaining=queries_remaining,
        guest_prompt_message=guest_prompt,
    )


@router.post("/stream", summary="Execute real-time streaming financial analysis query (SSE)")
async def process_chat_query_stream(
    request_body: ExtendedChatRequest,
    response: Response,
    auth_identity: tuple = Depends(enforce_rate_limit),
    orchestrator: FinancialOrchestrator = Depends(get_orchestrator),
    settings = Depends(get_settings),
) -> StreamingResponse:
    """
    Streams Server-Sent Events (SSE) containing progress events and real-time LLM token chunks.
    """
    user, guest = auth_identity
    logger.info(f"Starting SSE chat stream for {'User:' + user.email if user else 'Guest:' + guest.session_id}")

    # Prompt Guard: Small LLM Classifier blocking non-financial queries
    is_valid = await _is_valid_financial_query(request_body.question, settings)
    if not is_valid:
        async def _error_stream():
            error_event = json.dumps({"type": "error", "content": _OFF_TOPIC_REJECT_MSG})
            yield f"data: {error_event}\n\n"
        stream_res = StreamingResponse(_error_stream(), media_type="text/event-stream")
        stream_res.raw_headers.extend(response.raw_headers)
        return stream_res

    async def sse_event_generator():
        event_stream = orchestrator.process_query_event_stream(request_body)
        async for event in event_stream:
            json_data = json.dumps(event)
            yield f"data: {json_data}\n\n"

    stream_res = StreamingResponse(sse_event_generator(), media_type="text/event-stream")
    stream_res.raw_headers.extend(response.raw_headers)
    return stream_res
