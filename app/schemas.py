from __future__ import annotations

# Merged from schemas/*

from pydantic import BaseModel, Field
from pydantic import BaseModel, Field, ConfigDict
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Any, Dict, List, Literal, Optional, Tuple
from typing import Any, Dict, List, Optional
from typing import Any, List, Optional
from typing import Any, Literal
from typing import Any, Literal, Optional
from typing import Dict, List, Optional
from typing import TypedDict, List, Dict, Any, Optional
import datetime



"""
Pydantic schemas for Agent Layer (AgentContext, AgentResult, MarketAgentResult, NewsAgentResult, FilingAgentResult, QuantAgentResult).
Strictly typed input context and structured output result models for domain agents.
"""




class AgentContext(BaseModel):
    """
    Standardized execution context passed to all agents by the Orchestrator.
    """

    symbols: List[str] = Field(default_factory=list, description="Target company ticker symbols or aliases.")
    query: Optional[str] = Field(default=None, description="Natural language search query or prompt.")
    period: str = Field(default="1mo", description="Historical chart data period (e.g. '1d', '1mo', '1y').")
    interval: str = Field(default="1d", description="Historical bar interval (e.g. '1d', '1h').")
    date_range: Optional[Tuple[str, str]] = Field(default=None, description="Optional (start_date, end_date) range.")
    importance_threshold: Optional[int] = Field(default=None, description="Minimum news importance score threshold (1-10).")
    top_k: int = Field(default=5, description="Number of results or chunks to retrieve.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata dictionary.")

    model_config = ConfigDict(from_attributes=True)


class MarketAgentResult(BaseModel):
    """
    Structured result payload returned by MarketAgent.
    """

    quotes: Dict[str, StockQuote] = Field(default_factory=dict, description="Quotes mapped by symbol.")
    charts: Dict[str, HistoricalData] = Field(default_factory=dict, description="Chart data mapped by symbol.")
    profiles: Dict[str, CompanyInfo] = Field(default_factory=dict, description="Company profiles mapped by symbol.")
    key_stats: Dict[str, KeyStatistics] = Field(default_factory=dict, description="Key statistics mapped by symbol.")
    raw_metrics: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict, description="Raw supporting metrics from deep analyze")

    model_config = ConfigDict(from_attributes=True)


class NewsAgentResult(BaseModel):
    """
    Structured result payload returned by NewsAgent.
    """

    articles_by_symbol: Dict[str, List[NewsArticleResponse]] = Field(
        default_factory=dict, description="Latest database news articles mapped by canonical symbol."
    )
    total_articles: int = Field(default=0, description="Total news articles retrieved.")

    model_config = ConfigDict(from_attributes=True)


class FilingAgentResult(BaseModel):
    """
    Structured result payload returned by FilingAgent.
    """

    search_results: Dict[str, FilingSearchResult] = Field(
        default_factory=dict, description="Filing text chunks search results mapped by symbol or 'general'."
    )
    image_results: Dict[str, FilingImageResult] = Field(
        default_factory=dict, description="Filing visual chart images mapped by symbol or 'general'."
    )

    model_config = ConfigDict(from_attributes=True)


class QuantAgentResult(BaseModel):
    """
    Structured result payload returned by QuantAgent.
    """

    snapshots: Dict[str, RatioSnapshot] = Field(
        default_factory=dict, description="Quantitative ratio snapshots mapped by symbol."
    )
    comparison: Optional[QuantComparison] = Field(
        default=None, description="Side-by-side multi-symbol comparison snapshot if multiple symbols."
    )

    model_config = ConfigDict(from_attributes=True)


class AgentResult(BaseModel):
    """
    Standardized container result returned by all agent executions.
    """

    agent_name: str = Field(..., description="Name identifier of the executing agent.")
    status: Literal["success", "error"] = Field(..., description="Execution status.")
    execution_time_ms: float = Field(..., description="Execution latency in milliseconds.")
    data: Optional[Any] = Field(default=None, description="Domain agent result payload model.")
    error_message: Optional[str] = Field(default=None, description="Detailed error message if status is error.")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of execution completion.",
    )

    model_config = ConfigDict(from_attributes=True)

"""
Pydantic schemas for Orchestrator Chat Pipeline (ChatRequest, AgentTask, Plan, InvestorContext, ChatResponse).
Strictly typed schemas supporting multi-symbol queries, token guard truncation flags, and visual image arrays.
"""




class ChatRequest(BaseModel):
    """
    Incoming user query request model.
    """

    question: str = Field(..., description="User question or financial prompt.")
    symbols: List[str] = Field(default_factory=list, description="Optional list of company symbols or aliases.")
    chat_history: List[Dict[str, str]] = Field(default_factory=list, description="Previous conversation turn history.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary client metadata.")

    model_config = ConfigDict(from_attributes=True)


class AgentTask(BaseModel):
    """
    Individual task unit created by Planner and dispatched to a domain agent.
    """

    agent_name: str = Field(..., description="Name of target domain agent (MarketAgent, NewsAgent, FilingAgent, QuantAgent).")
    symbols: List[str] = Field(default_factory=list, description="Target canonical company symbols.")
    query: str = Field(..., description="Task query string.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Specific execution parameters.")

    model_config = ConfigDict(from_attributes=True)


class Plan(BaseModel):
    """
    Deterministic plan generated by Planner containing tasks and extracted metadata.
    """

    question: str = Field(..., description="Original user question.")
    tasks: List[AgentTask] = Field(default_factory=list, description="List of agent task items.")
    extracted_symbols: List[str] = Field(default_factory=list, description="Extracted canonical company symbols.")
    intent: str = Field(..., description="Primary query intent category.")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of plan generation.",
    )

    model_config = ConfigDict(from_attributes=True)


class InvestorContext(BaseModel):
    """
    Consolidated structured context compiled by ContextBuilder with Token Guard budget enforcement.
    """

    market_data: Dict[str, StockQuote] = Field(default_factory=dict, description="Stock quotes mapped by canonical symbol.")
    key_stats: Dict[str, KeyStatistics] = Field(default_factory=dict, description="Key statistics mapped by canonical symbol.")
    news: Dict[str, List[NewsArticleResponse]] = Field(default_factory=dict, description="News articles mapped by canonical symbol.")
    ratios: Dict[str, RatioSnapshot] = Field(default_factory=dict, description="Ratio snapshots mapped by canonical symbol.")
    filings: Dict[str, List[FilingChunk]] = Field(default_factory=dict, description="SEC filing chunks mapped by canonical symbol.")
    image_urls: List[str] = Field(default_factory=list, description="Flat list of Cloudinary visual chart image URLs.")
    context_truncated: bool = Field(default=False, description="Flag indicating whether ContextBuilder had to truncate evidence.")
    raw_metrics: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict, description="Raw supporting metrics from deep analyze")

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    """
    Final response payload returned to client or API route.
    """

    answer: str = Field(..., description="Synthesized financial intelligence response string.")
    sources: List[str] = Field(default_factory=list, description="List of source URLs or filing chunk citations.")
    agents_used: List[str] = Field(default_factory=list, description="Names of domain agents invoked.")
    images: List[str] = Field(default_factory=list, description="List of visual chart image URLs for frontend rendering.")
    symbols_queried: List[str] = Field(default_factory=list, description="List of canonical symbols analyzed.")
    context_truncated: bool = Field(default=False, description="True if evidence was truncated due to token budget.")
    confidence: Optional[float] = Field(default=None, description="Optional overall response confidence score.")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of response generation.",
    )

    model_config = ConfigDict(from_attributes=True)

"""
Pydantic schemas for Filing Service (FilingChunk, FilingSearchResult, FilingImageResult, FilingMetadata).
Strictly typed container models representing retrieved Qdrant SEC/annual report filing chunks and visual charts.
"""



class FilingChunk(BaseModel):
    """
    Single retrieved text chunk from corporate annual reports / filings.
    """

    filing_id: Optional[str] = Field(default=None, description="Unique Qdrant point ID or filing identifier.")
    text: str = Field(..., description="Extracted text chunk content.")
    source_url: Optional[str] = Field(default=None, description="Direct URL or Cloudinary path to source document.")
    page_number: Optional[int] = Field(default=None, description="Document page number.")
    filing_date: Optional[str] = Field(default=None, description="Filing or fiscal period date.")
    filing_type: Optional[str] = Field(default=None, description="Type of filing (e.g. Annual Report 10-K, 10-Q, Q3 Results).")
    confidence_score: float = Field(default=0.0, description="Vector similarity search or reranker relevance score.")
    symbol: Optional[str] = Field(default=None, description="Canonical company ticker symbol.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw document metadata dictionary.")

    model_config = ConfigDict(from_attributes=True)


class FilingSearchResult(BaseModel):
    """
    Container schema holding ranked retrieved filing chunks for a search query.
    """

    query: str = Field(..., description="User search query string.")
    canonical_symbol: Optional[str] = Field(default=None, description="Normalized canonical symbol if filtered.")
    chunks: List[FilingChunk] = Field(default_factory=list, description="Ordered list of relevant text chunks.")
    total_found: int = Field(default=0, description="Total number of chunks returned.")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of search execution.",
    )

    model_config = ConfigDict(from_attributes=True)


class FilingImageResult(BaseModel):
    """
    Container schema holding retrieved visual chart images and diagrams from filings.
    """

    query: str = Field(..., description="User search query string.")
    canonical_symbol: Optional[str] = Field(default=None, description="Normalized canonical symbol if filtered.")
    image_urls: List[str] = Field(default_factory=list, description="List of direct Cloudinary or image URLs.")
    captions: List[str] = Field(default_factory=list, description="Descriptive captions or figure headers.")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of image retrieval.",
    )

    model_config = ConfigDict(from_attributes=True)


class FilingMetadata(BaseModel):
    """
    Metadata summary for a specific corporate filing document.
    """

    filing_id: str = Field(..., description="Unique filing identifier.")
    canonical_symbol: Optional[str] = Field(default=None, description="Canonical company symbol.")
    filing_type: Optional[str] = Field(default=None, description="Type of filing.")
    filing_date: Optional[str] = Field(default=None, description="Filing or fiscal period date.")
    source_url: Optional[str] = Field(default=None, description="Source URL or document link.")
    page_count: Optional[int] = Field(default=None, description="Total page count if available.")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional document attributes.")

    model_config = ConfigDict(from_attributes=True)


class PortfolioState(TypedDict):
    """LangGraph State for Portfolio Analysis."""
    holdings_input: List[HoldingInput]
    db_session: Any # Pass DB session if needed
    analyzed_holdings: List[HoldingAnalysis]
    metrics: Optional[PortfolioMetrics]
    allocation: Optional[AllocationBreakdown]
    news_alerts: Dict[str, List[NewsArticleResponse]]
    red_flags: List[str]
    benchmark_comparison: List[BenchmarkComparison]
    tax_loss_harvesting: List[TaxLossHarvestingAlert]
    rebalancing_suggestions: List[str]
    summary_text: str
    final_response: Optional[PortfolioAnalysisResponse]


class NewsState(TypedDict):
    """LangGraph State for News Orchestration."""
    symbols: List[str]
    limit: int
    importance_threshold: Optional[int]
    db_session: Any
    articles_by_symbol: Dict[str, List[NewsArticleResponse]]
    total_articles: int
    google_rss: Optional[bool]

"""
Strongly typed Pydantic models for Groq LLM Layer requests, responses, and token telemetry.
"""



class Message(BaseModel):
    """Represents a single chat message in a conversation history."""

    role: Literal["system", "user", "assistant"] = Field(
        ..., description="Role of the message author."
    )
    content: str = Field(..., description="Text content of the message.")


class TokenUsage(BaseModel):
    """Token usage metrics returned by Groq API."""

    prompt_tokens: int = Field(default=0, ge=0, description="Tokens in the input prompt.")
    completion_tokens: int = Field(default=0, ge=0, description="Tokens in the generated completion.")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed.")


class GenerationMetadata(BaseModel):
    """Metadata tracking response timing, model info, and completion outcome."""

    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        description="ISO 8601 UTC timestamp of request completion.",
    )
    model: str = Field(..., description="Target model requested or executed.")
    latency_ms: float = Field(..., description="End-to-end request latency in milliseconds.")
    finish_reason: Optional[str] = Field(
        default=None, description="Reason model stopped generating (e.g., 'stop', 'length')."
    )


class LLMRequest(BaseModel):
    """Input parameters to construct an LLM chat generation request."""

    system_prompt: str = Field(..., description="System context or instructions.")
    user_prompt: str = Field(..., description="Formatted user inquiry or instruction.")
    context: Optional[dict[str, Any]] = Field(
        default=None, description="Structured contextual information (e.g. financial metrics)."
    )
    history: Optional[list[Message]] = Field(
        default=None, description="Prior conversation message history."
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature."
    )
    max_tokens: Optional[int] = Field(
        default=None, gt=0, description="Maximum number of tokens to generate."
    )


class LLMResponse(BaseModel):
    """Strongly typed response model returned by GroqService.generate()."""

    content: str = Field(..., description="Generated message response text.")
    metadata: GenerationMetadata = Field(..., description="Execution performance and timing metadata.")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Token usage summary.")
    raw_model_name: str = Field(default="groq", description="Exact model reported by the Groq API provider.")

"""
Pydantic schemas for Market Service (StockQuote, OHLCV, HistoricalData, CompanyInfo, KeyStatistics).
All fields are strictly typed with ISO 8601 UTC timestamps.
"""



class StockQuote(BaseModel):
    """
    Real-time stock price quote schema.
    """

    symbol: str = Field(..., description="Full yfinance ticker symbol (e.g. 'RELIANCE.NS').")
    canonical_symbol: str = Field(..., description="Canonical ticker symbol (e.g. 'RELIANCE').")
    price: float = Field(..., description="Current trade price.")
    change: float = Field(default=0.0, description="Absolute price change.")
    change_percent: float = Field(default=0.0, description="Percentage price change.")
    volume: int = Field(default=0, description="Trading volume.")
    market_cap: Optional[int] = Field(default=None, description="Market capitalization.")
    day_open: Optional[float] = Field(default=None, description="Day open price.")
    day_high: Optional[float] = Field(default=None, description="Day high price.")
    day_low: Optional[float] = Field(default=None, description="Day low price.")
    previous_close: Optional[float] = Field(default=None, description="Previous close price.")
    fifty_two_week_high: Optional[float] = Field(default=None, description="52-week high price.")
    fifty_two_week_low: Optional[float] = Field(default=None, description="52-week low price.")
    currency: str = Field(default="INR", description="Trading currency.")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of data retrieval.",
    )

    model_config = ConfigDict(from_attributes=True)


class OHLCV(BaseModel):
    """
    Single candlestick / time-series data point.
    """

    timestamp: str = Field(..., description="ISO 8601 timestamp or date string.")
    open: Optional[float] = Field(default=0.0, description="Opening price.")
    high: Optional[float] = Field(default=0.0, description="Highest price.")
    low: Optional[float] = Field(default=0.0, description="Lowest price.")
    close: Optional[float] = Field(default=0.0, description="Closing price.")
    volume: int = Field(default=0, description="Trading volume.")

    model_config = ConfigDict(from_attributes=True)


class HistoricalData(BaseModel):
    """
    Historical OHLCV time-series collection.
    """

    canonical_symbol: str = Field(..., description="Canonical ticker symbol (e.g. 'RELIANCE').")
    ticker_symbol: str = Field(..., description="Full yfinance ticker symbol (e.g. 'RELIANCE.NS').")
    period: str = Field(..., description="Time period requested (e.g. '1mo', '1y').")
    interval: str = Field(..., description="Bar interval (e.g. '1d', '1h').")
    series: List[OHLCV] = Field(default_factory=list, description="Ordered list of OHLCV bars.")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of retrieval.",
    )

    model_config = ConfigDict(from_attributes=True)


class CompanyInfo(BaseModel):
    """
    Company profile and operational overview.
    """

    canonical_symbol: str = Field(..., description="Canonical ticker symbol (e.g. 'RELIANCE').")
    company_name: str = Field(..., description="Official company legal name.")
    sector: Optional[str] = Field(default=None, description="Industry sector (e.g. 'Energy').")
    industry: Optional[str] = Field(default=None, description="Industry classification.")
    description: Optional[str] = Field(default=None, description="Business overview text.")
    website: Optional[str] = Field(default=None, description="Official company website URL.")
    employees: Optional[int] = Field(default=None, description="Full-time employee count.")
    country: Optional[str] = Field(default=None, description="Country of incorporation.")
    headquarters: Optional[str] = Field(default=None, description="City / state of headquarters.")

    model_config = ConfigDict(from_attributes=True)


class KeyStatistics(BaseModel):
    """
    Financial ratios, valuation metrics, and balance sheet statistics.
    """

    canonical_symbol: str = Field(..., description="Canonical ticker symbol (e.g. 'RELIANCE').")
    pe_ratio: Optional[float] = Field(default=None, description="Trailing Price-to-Earnings ratio.")
    forward_pe: Optional[float] = Field(default=None, description="Forward Price-to-Earnings ratio.")
    peg_ratio: Optional[float] = Field(default=None, description="Price/Earnings to Growth ratio.")
    eps: Optional[float] = Field(default=None, description="Trailing Earnings Per Share.")
    beta: Optional[float] = Field(default=None, description="5-year monthly Beta volatility.")
    dividend_yield: Optional[float] = Field(default=None, description="Annual dividend yield percentage.")
    roe: Optional[float] = Field(default=None, description="Return on Equity (manually computed from financials if not in info).")
    roce: Optional[float] = Field(default=None, description="Return on Capital Employed (EBIT / Capital Employed).")
    pb_ratio: Optional[float] = Field(default=None, description="Price-to-Book ratio (Market Cap / Stockholders Equity).")
    profit_margins: Optional[float] = Field(default=None, description="Net profit margin percentage.")
    gross_margins: Optional[float] = Field(default=None, description="Gross profit margin percentage.")
    revenue: Optional[int] = Field(default=None, description="Total annual revenue.")
    ebitda: Optional[int] = Field(default=None, description="EBITDA in reporting currency.")
    debt_to_equity: Optional[float] = Field(default=None, description="Total Debt to Equity ratio.")
    current_ratio: Optional[float] = Field(default=None, description="Current assets to current liabilities ratio.")
    target_price: Optional[float] = Field(default=None, description="Consensus analyst target price.")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of data retrieval.",
    )

    model_config = ConfigDict(from_attributes=True)

"""
Pydantic schemas for News Pipeline (NewsArticle, NewsEnrichment, CompanyAlias).
"""



class NewsEnrichment(BaseModel):
    """
    Structured Pydantic model for AI LLM enrichment extraction.
    """

    summary: str = Field(..., description="Concise 2-3 sentence executive summary of the article.")
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        ..., description="Overall market sentiment impact of the news."
    )
    topic_tags: list[str] = Field(
        default_factory=list, description="Categorical topic tags (e.g. ['earnings', 'm&a', 'governance'])."
    )
    event_type: str = Field(
        ..., description="Primary financial event type (e.g. 'Earnings Release', 'Regulatory Action')."
    )
    importance_score: int = Field(
        ..., ge=1, le=10, description="Financial impact/importance score from 1 (minor) to 10 (critical)."
    )
    key_entities: list[str] = Field(
        default_factory=list, description="List of key organizations, regulators, or executives mentioned."
    )
    key_points: list[str] = Field(
        default_factory=list, description="Key bullet points summarizing main financial takeaways."
    )


class NewsArticleCreate(BaseModel):
    """
    Schema used when creating a new news article record.
    """

    headline: str = Field(..., description="News article title / headline.")
    url: str = Field(..., description="Unique source URL.")
    source: str = Field(..., description="Publisher / source name (e.g. 'Economic Times').")
    author: str | None = Field(default=None, description="Article author name if available.")
    published_time: datetime.datetime = Field(..., description="Publication UTC timestamp.")

    canonical_symbol: str = Field(..., description="Normalized company ticker/symbol (e.g. 'RELIANCE').")
    original_company_name: str = Field(..., description="Original company name string parsed from source.")
    raw_snippet: str | None = Field(default=None, description="Raw article text snippet.")

    # Enrichment fields (populated after LLM processing)
    summary: str | None = None
    sentiment: str | None = None
    topic_tags: list[str] | None = None
    event_type: str | None = None
    importance_score: int | None = None
    key_entities: list[str] | None = None
    key_points: list[str] | None = None


class NewsArticleResponse(NewsArticleCreate):
    """
    Schema for database output responses.
    """

    id: int = Field(..., description="Database primary key integer ID.")
    fetch_time: datetime.datetime = Field(..., description="Timestamp when article was ingested.")

    model_config = ConfigDict(from_attributes=True)


class CompanyAliasSchema(BaseModel):
    """
    Schema for company alias mappings.
    """

    alias: str = Field(..., description="Variant name string (e.g., 'reliance industries').")
    canonical_symbol: str = Field(..., description="Canonical ticker symbol (e.g., 'RELIANCE').")

    model_config = ConfigDict(from_attributes=True)

"""
Pydantic Schemas for Portfolio Analyzer feature.
"""



class HoldingInput(BaseModel):
    """Parsed CSV holding row."""
    symbol: str
    name: Optional[str] = None
    quantity: float = Field(gt=0, description="Holding quantity")
    avg_buy_price: float = Field(gt=0, description="Average purchase price in INR")
    date_acquired: Optional[str] = None


class HoldingAnalysis(BaseModel):
    """Detailed holding analysis."""
    symbol: str
    name: str
    asset_type: str  # "stock", "etf", "mf"
    quantity: float
    avg_buy_price: float
    current_price: float
    total_invested: float
    current_value: float
    pnl: float
    pnl_percent: float
    day_change: float
    weight_percent: float
    sector: str
    pe_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    news_summary: Optional[str] = None


class PortfolioMetrics(BaseModel):
    """Portfolio-level performance & risk metrics."""
    total_value: float
    total_invested: float
    total_pnl: float
    total_pnl_percent: float
    day_pnl: float
    risk_score: int = Field(ge=1, le=10, description="Portfolio Risk Score 1-10")
    concentration_risk_percent: float = Field(description="Max single-holding exposure %")


class AllocationBreakdown(BaseModel):
    """Sector and Asset Type allocation distributions."""
    sector_breakdown: Dict[str, float]
    asset_type_breakdown: Dict[str, float]


class BenchmarkComparison(BaseModel):
    """NIFTY 50 Benchmark comparison metrics."""
    period: str  # "1M", "6M", "1Y"
    portfolio_return_percent: float
    nifty50_return_percent: float
    outperformance_percent: float


class TaxLossHarvestingAlert(BaseModel):
    """Tax loss harvesting opportunity recommendation."""
    symbol: str
    name: str
    unrealized_loss: float
    unrealized_loss_percent: float
    est_stcg_tax_saving: float  # 20% STCG offset
    est_ltcg_tax_saving: float  # 12.5% LTCG offset
    recommendation: str


class PortfolioAnalysisResponse(BaseModel):
    """Complete portfolio analysis report."""
    id: Optional[int] = None
    summary: str
    holdings: List[HoldingAnalysis]
    portfolio_metrics: PortfolioMetrics
    allocation: AllocationBreakdown
    rebalancing_suggestions: List[str]
    news_alerts: Dict[str, List[str]]
    red_flags: List[str]
    benchmark_comparison: List[BenchmarkComparison] = []
    tax_loss_harvesting: List[TaxLossHarvestingAlert] = []
    images: List[str] = []
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

"""
Pydantic schemas for Quant Service (Profitability, Valuation, Growth, Leverage, Efficiency, Dividend, RatioSnapshot, QuantComparison).
All calculated ratio fields are Optional[float] rounded to 4 decimal places with proper defaults.
"""



class ProfitabilityRatios(BaseModel):
    """
    Profitability and margin analysis ratios.
    """

    roe: Optional[float] = Field(default=None, description="Return on Equity (Net Income / Total Equity).")
    roa: Optional[float] = Field(default=None, description="Return on Assets (Net Income / Total Assets).")
    roce: Optional[float] = Field(default=None, description="Return on Capital Employed (EBIT / Capital Employed).")
    gross_margin: Optional[float] = Field(default=None, description="Gross Profit Margin percentage.")
    operating_margin: Optional[float] = Field(default=None, description="Operating Profit Margin percentage.")
    net_profit_margin: Optional[float] = Field(default=None, description="Net Profit Margin percentage.")

    model_config = ConfigDict(from_attributes=True)


class ValuationRatios(BaseModel):
    """
    Valuation multiples and price metrics.
    """

    pe_ratio: Optional[float] = Field(default=None, description="Trailing Price-to-Earnings multiple.")
    forward_pe: Optional[float] = Field(default=None, description="Forward Price-to-Earnings multiple.")
    pb_ratio: Optional[float] = Field(default=None, description="Price-to-Book Value multiple.")
    peg_ratio: Optional[float] = Field(default=None, description="Price/Earnings to Growth ratio.")
    ev_to_ebitda: Optional[float] = Field(default=None, description="Enterprise Value to EBITDA multiple.")

    model_config = ConfigDict(from_attributes=True)


class GrowthMetrics(BaseModel):
    """
    Historical Compound Annual Growth Rate (CAGR) and YoY growth metrics.
    """

    revenue_cagr_3yr: Optional[float] = Field(default=None, description="3-Year Revenue CAGR percentage.")
    revenue_cagr_5yr: Optional[float] = Field(default=None, description="5-Year Revenue CAGR percentage.")
    eps_cagr_3yr: Optional[float] = Field(default=None, description="3-Year EPS CAGR percentage.")
    eps_cagr_5yr: Optional[float] = Field(default=None, description="5-Year EPS CAGR percentage.")
    revenue_growth_yoy: Optional[float] = Field(default=None, description="Year-over-Year Revenue growth percentage.")
    eps_growth_yoy: Optional[float] = Field(default=None, description="Year-over-Year EPS growth percentage.")

    model_config = ConfigDict(from_attributes=True)


class LeverageRatios(BaseModel):
    """
    Financial leverage, solvency, and liquidity ratios.
    """

    debt_to_equity: Optional[float] = Field(default=None, description="Total Debt to Equity ratio.")
    current_ratio: Optional[float] = Field(default=None, description="Current Assets to Current Liabilities ratio.")
    quick_ratio: Optional[float] = Field(default=None, description="Quick Assets to Current Liabilities ratio.")
    interest_coverage: Optional[float] = Field(default=None, description="EBIT to Interest Expense coverage ratio.")

    model_config = ConfigDict(from_attributes=True)


class EfficiencyRatios(BaseModel):
    """
    Asset utilization and operational efficiency ratios.
    """

    asset_turnover: Optional[float] = Field(default=None, description="Asset Turnover Ratio (Revenue / Total Assets).")
    inventory_turnover: Optional[float] = Field(default=None, description="Inventory Turnover Ratio (COGS / Avg Inventory).")

    model_config = ConfigDict(from_attributes=True)


class DividendMetrics(BaseModel):
    """
    Dividend yield and payout distribution metrics.
    """

    dividend_yield: Optional[float] = Field(default=None, description="Annual Dividend Yield percentage.")
    payout_ratio: Optional[float] = Field(default=None, description="Dividend Payout Ratio percentage.")

    model_config = ConfigDict(from_attributes=True)


class RatioSnapshot(BaseModel):
    """
    Complete financial ratio and quantitative snapshot for a company.
    """

    symbol: str = Field(..., description="Full yfinance ticker symbol (e.g. 'RELIANCE.NS').")
    canonical_symbol: str = Field(..., description="Canonical ticker symbol (e.g. 'RELIANCE').")
    computed_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of calculation.",
    )
    profitability: ProfitabilityRatios = Field(..., description="Profitability ratios.")
    valuation: ValuationRatios = Field(..., description="Valuation ratios.")
    growth: GrowthMetrics = Field(..., description="Growth CAGR and YoY metrics.")
    leverage: LeverageRatios = Field(..., description="Leverage and solvency ratios.")
    efficiency: EfficiencyRatios = Field(..., description="Efficiency and turnover ratios.")
    dividend: DividendMetrics = Field(..., description="Dividend metrics.")

    model_config = ConfigDict(from_attributes=True)


class QuantComparison(BaseModel):
    """
    Side-by-side financial ratio comparison across multiple companies.
    """

    symbols: List[str] = Field(..., description="List of canonical symbols compared.")
    metrics_comparison: Dict[str, RatioSnapshot] = Field(
        ..., description="Dictionary mapping canonical symbol to its RatioSnapshot."
    )
    computed_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of comparison generation.",
    )

    model_config = ConfigDict(from_attributes=True)

# Agent Pipeline Redesign Schemas

class AgentCurrent(BaseModel):
    price: float
    currency: str
    change: Optional[float] = None
    change_percent: Optional[float] = None
    marketCap: Optional[float]
    dayOpen: Optional[float] = None
    dayHigh: Optional[float]
    dayLow: Optional[float]
    previousClose: Optional[float] = None
    fiftyTwoWeekHigh: Optional[float] = None
    fiftyTwoWeekLow: Optional[float] = None
    timestamp: str

class AgentValuation(BaseModel):
    forwardPE: Optional[float]
    trailingPE: Optional[float]
    priceToBook: Optional[float]
    enterpriseValue: Optional[float]

class AgentFinancialYear(BaseModel):
    year: int
    revenue: Optional[float]
    netIncome: Optional[float]
    eps: Optional[float]
    operatingMargin: Optional[float]

class AgentHealth(BaseModel):
    totalDebt: Optional[float]
    cash: Optional[float]
    netDebt: Optional[float]
    debtToEquity: Optional[float]
    currentRatio: Optional[float]

class AgentFinancialData(BaseModel):
    company: str
    current: AgentCurrent
    valuation: AgentValuation
    financials: List[AgentFinancialYear]
    health: AgentHealth

class AgentResponse(BaseModel):
    status: str
    data: Any
    timestamp: Optional[str] = None

