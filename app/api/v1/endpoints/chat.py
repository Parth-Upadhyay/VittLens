"""
Chat & Financial Analysis API Endpoints.
Provides POST /api/v1/chat (JSON completion) and POST /api/v1/chat/stream (SSE token streaming).
Supports chat thread persistence, AI title generation, and 50-message FIFO retention cap enforcement.
"""

import json
import uuid
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


def _is_gibberish_query(text: str) -> bool:
    """
    Returns True if the input looks like gibberish or keyboard mashing.
    Checks: too-short, keyboard patterns, vowel ratio, consonant runs.
    """
    import re
    q = text.strip()
    if not q or len(q) < 3:
        return True

    q_lower = q.lower()

    # 1. Keyboard patterns
    if any(pat in q_lower for pat in _KEYBOARD_PATTERNS):
        return True

    alpha_only = re.sub(r"[^a-z]", "", q_lower)
    if not alpha_only:
        return False  # purely numeric/symbolic — let planner handle it

    # 2. Vowel ratio on single-word or very short inputs
    words = q.split()
    if len(words) <= 2:
        vowels = sum(1 for c in alpha_only if c in "aeiou")
        ratio = vowels / len(alpha_only) if alpha_only else 0
        if len(alpha_only) >= 5 and ratio < 0.15:
            return True

    # 3. Consecutive consonant run >= 5 (e.g. "gfxfjd", "bhjkst")
    runs = re.split(r"[aeiou]+", alpha_only)
    if any(len(run) >= 5 for run in runs):
        return True

    return False


def _is_off_topic_query(text: str) -> bool:
    """
    Returns True if the query appears to have NO relation to finance, stocks,
    or the Indian equity markets.

    Strategy: tokenize the query and check if ANY word or bigram matches
    the finance keyword set. If nothing matches, the query is off-topic.
    This lets short but valid queries like 'TCS PE?' pass while blocking
    'what do you think of cr7', 'tell me a joke', 'recipe for pasta', etc.
    """
    import re
    q_lower = text.strip().lower()

    # Tokenise into words
    tokens = re.findall(r"[a-z0-9/]+", q_lower)

    # Check individual tokens
    for tok in tokens:
        if tok in _FINANCE_KEYWORDS:
            return False

    # Check bigrams (e.g. "market cap", "pe ratio", "52 week")
    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
    for bg in bigrams:
        if bg in _FINANCE_KEYWORDS:
            return False

    # Check if any finance keyword appears as a substring in the full text
    # (catches tickers like HDFCBANK, BHARTIARTL embedded in sentences)
    for kw in _FINANCE_KEYWORDS:
        if len(kw) >= 4 and kw in q_lower:
            return False

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

    # Prompt Guard: Block gibberish / rubbish / non-financial input
    if _is_gibberish_query(request_body.question):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_GIBBERISH_REJECT_MSG,
        )

    # Relevance Guard: Block off-topic queries (no finance keywords detected)
    if _is_off_topic_query(request_body.question):
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
) -> StreamingResponse:
    """
    Streams Server-Sent Events (SSE) containing progress events and real-time LLM token chunks.
    """
    user, guest = auth_identity
    logger.info(f"Starting SSE chat stream for {'User:' + user.email if user else 'Guest:' + guest.session_id}")

    # Prompt Guard: Block gibberish / rubbish / non-financial input
    if _is_gibberish_query(request_body.question) or _is_off_topic_query(request_body.question):
        reject_msg = _GIBBERISH_REJECT_MSG if _is_gibberish_query(request_body.question) else _OFF_TOPIC_REJECT_MSG
        async def _error_stream():
            error_event = json.dumps({"type": "error", "content": reject_msg})
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
