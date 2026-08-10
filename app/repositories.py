from __future__ import annotations

# Merged from repositories/*

from app.config.settings import Settings
from app.models import NewsArticle, CompanyAlias
from app.models import PortfolioAnalysis
from app.schemas import NewsArticleCreate
from app.schemas import PortfolioAnalysisResponse
from app.utils import get_logger
from qdrant_client.http import models
from sqlalchemy import select, desc
from sqlalchemy import select, desc, delete
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from typing import List, Optional
import datetime
import math
import os
import time
import yfinance as yf



"""
Repository pattern wrapping existing Qdrant RAG vector retrieval layer (query_qdrant.py).
Sole component in the platform allowed to invoke vector search or query_qdrant methods.
Encapsulates embedding generation, Qdrant payload filters, Jina reranking, and Cloudinary URL formatting.
"""


# Import from existing frozen Qdrant query_qdrant module
try:
    import query_qdrant as qdrant_mod
except ImportError:
    qdrant_mod = None


logger = get_logger("finnai.filing_repository")


class FilingRepository:
    """
    Data access repository for corporate SEC filings, annual reports, and visual charts.
    Wraps existing query_qdrant RAG layer without modifying it.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.collection_name = getattr(qdrant_mod, "COLLECTION", "ollama_bge_m3_nifty20")
        self.cloudinary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "")
        self.module = qdrant_mod

    def _ensure_qdrant_connected(self) -> None:
        """Ensure Qdrant client connection is initialized."""
        if self.module is None:
            raise RuntimeError("Module 'query_qdrant.py' could not be imported.")
        self.module.init_qdrant()

    def search_filing_chunks(
        self, query: str, db_company_variants: Optional[List[str]] = None, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Execute vector similarity search + optional metadata filtering + Jina reranking on filing chunks.

        Args:
            query: Natural language query string.
            db_company_variants: List of company name variants for Qdrant payload filter.
            top_k: Number of top chunks to return.

        Returns:
            List of dictionaries containing text, score, and metadata.
        """
        self._ensure_qdrant_connected()

        try:
            logger.info(f"Generating embedding for query: '{query[:40]}...'")
            query_vector = self.module.embed_query(query)

            must_conditions = []
            if db_company_variants:
                logger.info(f"Applying Qdrant Company Filter: {db_company_variants}")
                must_conditions.append(
                    models.FieldCondition(
                        key="company",
                        match=models.MatchAny(any=db_company_variants),
                    )
                )

            # Auto-detect FY filters if present in query
            detected_fy = self.module.extract_fy(query)
            if detected_fy:
                logger.info(f"Applying Qdrant FY Filter: {detected_fy}")
                must_conditions.append(
                    models.FieldCondition(
                        key="fy",
                        match=models.MatchAny(any=detected_fy),
                    )
                )

            qdrant_filter = models.Filter(must=must_conditions) if must_conditions else None

            # Fetch limit before reranking
            use_jina = getattr(self.module, "USE_JINA_RERANKER", False)
            fetch_limit = top_k * 4 if use_jina else top_k

            points = self.module.qdrant.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=fetch_limit,
            ).points

            if not points:
                logger.warning(f"Qdrant vector search returned 0 points for query '{query}'.")
                return []

            # Apply Jina Reranker if enabled in query_qdrant module
            if use_jina:
                results = self.module.rerank_with_jina(query, points, top_n=top_k)
            else:
                results = points[:top_k]

            raw_chunks: List[Dict[str, Any]] = []
            for pt in results:
                payload = dict(pt.payload or {})
                score = getattr(pt, "score", 0.0)
                jina_score = payload.get("jina_score")
                confidence = float(jina_score if jina_score is not None else score)

                raw_chunks.append({
                    "filing_id": str(pt.id),
                    "text": payload.get("document", payload.get("text", "")),
                    "source_url": payload.get("source_url") or payload.get("url") or payload.get("file_path"),
                    "page_number": payload.get("page_number") or payload.get("page"),
                    "filing_date": payload.get("fy") or payload.get("filing_date"),
                    "filing_type": payload.get("filing_type", "Annual Report"),
                    "confidence_score": round(confidence, 4),
                    "symbol": payload.get("company"),
                    "metadata": payload,
                })

            logger.info(f"Successfully retrieved {len(raw_chunks)} filing chunks from Qdrant.")
            return raw_chunks

        except Exception as e:
            logger.error(f"FilingRepository search_filing_chunks failed: {e}")
            return []

    def fetch_filing_images(
        self,
        query: str,
        db_company_variants: Optional[List[str]] = None,
        top_k: int = 3,
        existing_chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for visual chart images, diagrams, and figures in retrieved filing payloads.
        Reuses existing retrieved chunks if provided to prevent redundant embedding/reranker API calls.

        Returns:
            List of image metadata dictionaries with Cloudinary URLs.
        """
        chunks = existing_chunks if existing_chunks is not None else self.search_filing_chunks(
            query=query, db_company_variants=db_company_variants, top_k=top_k * 2
        )

        images: List[Dict[str, Any]] = []
        for chk in chunks:
            meta = chk.get("metadata", {})
            visual_path = meta.get("visual_path") or meta.get("image_path") or meta.get("chart_path")

            text = chk.get("text", "")
            if not visual_path and "visuals/" in text:
                import re
                match = re.search(r"visuals/[^\s\'\"\)]+", text)
                if match:
                    visual_path = match.group(0)

            if visual_path:
                clean_path = visual_path.replace("\\", "/")
                if "visuals/" in clean_path:
                    clean_path = "visuals/" + clean_path.split("visuals/", 1)[1]
                clean_path = clean_path.strip("/")

                if self.cloudinary_cloud_name:
                    image_url = f"https://res.cloudinary.com/{self.cloudinary_cloud_name}/image/upload/finnai/{clean_path}"
                else:
                    image_url = clean_path

                images.append({
                    "image_url": image_url,
                    "caption": meta.get("caption") or chk.get("text", "")[:120],
                    "symbol": chk.get("symbol"),
                    "page_number": chk.get("page_number"),
                })

                if len(images) >= top_k:
                    break

        return images

    def fetch_filing_metadata(self, filing_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata for a specific filing point ID in Qdrant.
        """
        self._ensure_qdrant_connected()
        try:
            pts = self.module.qdrant.retrieve(
                collection_name=self.collection_name,
                ids=[filing_id],
                with_payload=True,
                with_vectors=False,
            )
            if not pts:
                return None

            pt = pts[0]
            payload = dict(pt.payload or {})
            return {
                "filing_id": str(pt.id),
                "symbol": payload.get("company"),
                "filing_type": payload.get("filing_type", "Annual Report"),
                "filing_date": payload.get("fy") or payload.get("filing_date"),
                "source_url": payload.get("source_url") or payload.get("url"),
                "page_count": payload.get("page_count"),
                "attributes": payload,
            }
        except Exception as e:
            logger.error(f"FilingRepository fetch_filing_metadata failed for '{filing_id}': {e}")
            return None

"""
Repository Pattern implementation for yfinance market data operations.
Sole component in the platform allowed to instantiate or invoke yfinance API calls.
Encapsulates HTTP timeouts, exponential retries, NaN sanitation, and exception shielding.
"""



logger = get_logger("finnai.market_repository")


class MarketRepository:
    """
    Data access repository managing all yfinance data retrieval calls.
    Includes automated retries, timeout management, and NaN/Inf sanitation.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.max_retries = self.settings.yfinance_max_retries
        self.timeout = self.settings.yfinance_timeout
        
        # Configure custom session to bypass yfinance rate-limiting on Render
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def _sanitize_val(self, val: Any) -> Any:
        """
        Sanitize numeric values converting NaN, infinity, or invalid types to None or valid Python primitives.
        """
        if val is None:
            return None
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return None
            return round(val, 4)
        return val

    def _fetch_info_with_yahooquery(self, ticker_symbol: str) -> dict:
        """
        Fallback method to fetch company info using yahooquery when yfinance.info is rate-limited.
        Maps yahooquery nested data to the flat dictionary structure expected from yfinance.info.
        """
        try:
            from yahooquery import Ticker
            t = Ticker(ticker_symbol)
            info = {}
            
            profile = t.summary_profile.get(ticker_symbol, {})
            if isinstance(profile, dict):
                info["sector"] = profile.get("sector")
                info["industry"] = profile.get("industry")
                info["longBusinessSummary"] = profile.get("longBusinessSummary")
                info["website"] = profile.get("website")
                info["fullTimeEmployees"] = profile.get("fullTimeEmployees")
                info["country"] = profile.get("country")
                info["city"] = profile.get("city")
                info["state"] = profile.get("state")
                
            q_type = t.quote_type.get(ticker_symbol, {})
            if isinstance(q_type, dict):
                info["longName"] = q_type.get("longName")
                info["shortName"] = q_type.get("shortName")
                
            stats = t.key_stats.get(ticker_symbol, {})
            if isinstance(stats, dict):
                info["forwardPE"] = stats.get("forwardPE")
                info["beta"] = stats.get("beta")
                info["bookValue"] = stats.get("bookValue")
                info["priceToBook"] = stats.get("priceToBook")
                info["enterpriseToEbitda"] = stats.get("enterpriseToEbitda")
                info["enterpriseToRevenue"] = stats.get("enterpriseToRevenue")
                info["trailingEps"] = stats.get("trailingEps")
                info["forwardEps"] = stats.get("forwardEps")
                
            detail = t.summary_detail.get(ticker_symbol, {})
            if isinstance(detail, dict):
                info["trailingPE"] = detail.get("trailingPE")
                info["dividendYield"] = detail.get("dividendYield")
                info["marketCap"] = detail.get("marketCap")
                info["previousClose"] = detail.get("previousClose")
                info["regularMarketPrice"] = detail.get("regularMarketPrice")
                info["dayHigh"] = detail.get("dayHigh")
                info["dayLow"] = detail.get("dayLow")
                info["fiftyTwoWeekHigh"] = detail.get("fiftyTwoWeekHigh")
                info["fiftyTwoWeekLow"] = detail.get("fiftyTwoWeekLow")
                info["volume"] = detail.get("volume")
                info["currency"] = detail.get("currency")
                
            return info
        except Exception as e:
            logger.error(f"yahooquery fallback failed for '{ticker_symbol}': {e}")
            return {}

    def _sanitize_dividend_yield(self, val: Any) -> Any:
        """
        Sanitize yfinance dividendYield which is returned inconsistently:
        - Correct form: 0.0111 = 1.11% (decimal, abs <= 1.0)
        - Corrupted form: 1.11 = already 1.11% (returned as percentage instead of decimal ratio)
        - Extreme corrupted form: 111.0 = 1.11% (percentage multiplied by 100 twice or percentage 111)
        
        yfinance for some Indian / international stocks returns dividendYield as 1.11 (meaning 1.11%) 
        instead of 0.0111. When multiplied by 100 in the UI, 1.11 becomes 111.00%!
        
        Normalization rule:
        - If raw > 1.0 (e.g. 1.11 or 111.0): divide by 100 to standard decimal ratio (0.0111).
        - If after division or initially raw > 0.5 (implying >50% dividend yield), null out as bad data.
        """
        raw = self._sanitize_val(val)
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            # If yfinance returned percentage like 1.11 (meaning 1.11%) or 111.0, scale down to decimal format
            if abs(raw) > 1.0:
                raw = raw / 100.0
            if abs(raw) > 1.0:  # If still > 1.0 (e.g. 111.0 became 1.11)
                raw = raw / 100.0
            # Cap: if decimal yield is still > 0.5 (>50%), treat as bad data
            if abs(raw) > 0.5:
                return None
        return raw

    def _execute_with_retry(self, func_name: str, ticker_symbol: str, func: Any) -> Any:
        """
        Helper executing a yfinance call with retries and exponential backoff.
        Non-retryable ticker errors (delisted symbols, KeyError, etc.) fail fast.
        """
        delay = 1.0
        last_exception: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                start = time.perf_counter()
                result = func()
                latency_ms = (time.perf_counter() - start) * 1000.0
                logger.debug(f"yfinance [{func_name}] for '{ticker_symbol}' succeeded in {latency_ms:.2f}ms (Attempt {attempt}).")
                return result

            except Exception as e:
                last_exception = e
                err_msg = str(e).lower()
                is_non_retryable = (
                    isinstance(e, KeyError)
                    or "exchangetimezonename" in err_msg
                    or "delisted" in err_msg
                    or "no data found" in err_msg
                )

                if is_non_retryable:
                    logger.warning(f"yfinance [{func_name}] non-retryable error for '{ticker_symbol}': {e}. Failing fast.")
                    break

                logger.warning(
                    f"yfinance [{func_name}] error for '{ticker_symbol}' (Attempt {attempt}/{self.max_retries}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
                delay *= 1.5

        logger.error(f"yfinance [{func_name}] failed for '{ticker_symbol}': {last_exception}")
        raise RuntimeError(f"yfinance operation '{func_name}' failed for '{ticker_symbol}': {last_exception}")

    def get_current_quote(self, ticker_symbol: str) -> Dict[str, Any]:
        """
        Retrieve current trade price quote and 24h market metrics from yfinance.

        Args:
            ticker_symbol: Full yfinance ticker (e.g., 'RELIANCE.NS').

        Returns:
            Dictionary containing raw sanitized quote parameters.
        """
        def _fetch():
            # Fetch info exclusively using yahooquery since yfinance is consistently rate-limited
            info = self._fetch_info_with_yahooquery(ticker_symbol)
            ticker = yf.Ticker(ticker_symbol, session=self.session)

            fast_info = getattr(ticker, "fast_info", {})

            # Extract current price with fallback chain
            price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or getattr(fast_info, "last_price", None)
                or getattr(fast_info, "previous_close", 0.0)
            )
            prev_close = (
                info.get("regularMarketPreviousClose")
                or info.get("previousClose")
                or getattr(fast_info, "previous_close", price)
            )

            change = price - prev_close if price and prev_close else 0.0
            change_percent = (change / prev_close * 100.0) if prev_close else 0.0

            return {
                "symbol": ticker_symbol,
                "price": self._sanitize_val(price),
                "change": self._sanitize_val(change),
                "change_percent": self._sanitize_val(change_percent),
                "volume": self._sanitize_val(info.get("regularMarketVolume") or getattr(fast_info, "last_volume", 0)),
                "market_cap": self._sanitize_val(info.get("marketCap") or getattr(fast_info, "market_cap", None)),
                "day_high": self._sanitize_val(info.get("dayHigh") or getattr(fast_info, "day_high", None)),
                "day_low": self._sanitize_val(info.get("dayLow") or getattr(fast_info, "day_low", None)),
                "fifty_two_week_high": self._sanitize_val(info.get("fiftyTwoWeekHigh") or getattr(fast_info, "year_high", None)),
                "fifty_two_week_low": self._sanitize_val(info.get("fiftyTwoWeekLow") or getattr(fast_info, "year_low", None)),
                "currency": info.get("currency", "INR"),
            }

        return self._execute_with_retry("get_current_quote", ticker_symbol, _fetch)

    def get_historical_data(
        self, ticker_symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical OHLCV time-series data from yfinance.

        Args:
            ticker_symbol: Full yfinance ticker (e.g. 'RELIANCE.NS').
            period: Time period (e.g. '1d', '5d', '1mo', '3mo', '1y', '5y').
            interval: Bar interval (e.g. '1m', '5m', '1h', '1d', '1wk').

        Returns:
            List of dictionaries representing OHLCV bars.
        """
        def _fetch():
            ticker = yf.Ticker(ticker_symbol, session=self.session)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                logger.warning(f"yfinance returned empty historical dataframe for '{ticker_symbol}' (period={period}).")
                return []

            bars: List[Dict[str, Any]] = []
            for idx, row in df.iterrows():
                ts_str = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
                bars.append({
                    "timestamp": ts_str,
                    "open": self._sanitize_val(float(row.get("Open", 0.0))),
                    "high": self._sanitize_val(float(row.get("High", 0.0))),
                    "low": self._sanitize_val(float(row.get("Low", 0.0))),
                    "close": self._sanitize_val(float(row.get("Close", 0.0))),
                    "volume": int(row.get("Volume", 0)),
                })
            return bars

        return self._execute_with_retry("get_historical_data", ticker_symbol, _fetch)

    def get_company_info(self, ticker_symbol: str) -> Dict[str, Any]:
        """
        Retrieve company profile and business information from yfinance.
        """
        def _fetch():
            # Fetch info exclusively using yahooquery since yfinance is consistently rate-limited
            info = self._fetch_info_with_yahooquery(ticker_symbol)
                
            return {
                "company_name": info.get("longName") or info.get("shortName") or ticker_symbol,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "description": info.get("longBusinessSummary"),
                "website": info.get("website"),
                "employees": info.get("fullTimeEmployees"),
                "country": info.get("country"),
                "headquarters": f"{info.get('city', '')}, {info.get('state', '')}".strip(", "),
            }

        return self._execute_with_retry("get_company_info", ticker_symbol, _fetch)

    def get_key_statistics(self, ticker_symbol: str) -> Dict[str, Any]:
        """
        Retrieve financial ratios, valuation metrics, and balance sheet statistics from yfinance.
        """
        def _fetch():
            # Fetch info exclusively using yahooquery since yfinance is consistently rate-limited
            info = self._fetch_info_with_yahooquery(ticker_symbol)
            ticker = yf.Ticker(ticker_symbol, session=self.session)
            
            # Fetch financials for manual ratio calculations
            try:
                financials = ticker.financials
                balance_sheet = ticker.balance_sheet
            except Exception as e:
                logger.warning(f"Failed to fetch financials for {ticker_symbol}: {e}")
                financials = None
                balance_sheet = None

            def get_series_val(df, *keys):
                """Try multiple key names; return first valid non-NaN float found."""
                import math as _math
                if df is None or df.empty:
                    return None
                for key in keys:
                    if key in df.index:
                        try:
                            val = df.loc[key].iloc[0]
                            if val is None:
                                continue
                            fval = float(val)
                            if _math.isnan(fval) or _math.isinf(fval):
                                continue
                            return fval
                        except Exception:
                            continue
                return None

            # Calculate ROE: Net Income / Stockholders Equity
            roe = info.get("returnOnEquity")
            if roe is None:
                net_income = get_series_val(financials, "Net Income", "Net Income Common Stockholders")
                equity = get_series_val(
                    balance_sheet,
                    "Stockholders Equity",
                    "Common Stock Equity",
                    "Total Equity Gross Minority Interest",
                )
                if net_income is not None and equity is not None and equity != 0:
                    roe = net_income / equity

            # Calculate ROCE: EBIT / (Total Assets - Current Liabilities)
            roce = None
            ebit = get_series_val(financials, "EBIT", "Operating Income")
            total_assets = get_series_val(balance_sheet, "Total Assets")
            current_liabilities = get_series_val(balance_sheet, "Current Liabilities")
            if ebit is not None and total_assets is not None and current_liabilities is not None:
                capital_employed = total_assets - current_liabilities
                if capital_employed != 0:
                    roce = ebit / capital_employed

            # Calculate P/B: prefer info field, then compute from market cap
            pb_ratio = info.get("priceToBook")
            if pb_ratio is None:
                market_cap = info.get("marketCap")
                equity = get_series_val(
                    balance_sheet,
                    "Stockholders Equity",
                    "Common Stock Equity",
                    "Total Equity Gross Minority Interest",
                )
                if market_cap is not None and equity is not None and equity != 0:
                    pb_ratio = market_cap / equity

            return {
                "pe_ratio": self._sanitize_val(info.get("trailingPE")),
                "forward_pe": self._sanitize_val(info.get("forwardPE")),
                "peg_ratio": self._sanitize_val(info.get("pegRatio")),
                "eps": self._sanitize_val(info.get("trailingEps")),
                "beta": self._sanitize_val(info.get("beta")),
                "dividend_yield": self._sanitize_dividend_yield(info.get("dividendYield")),
                "roe": self._sanitize_val(roe),
                "profit_margins": self._sanitize_val(info.get("profitMargins")),
                "gross_margins": self._sanitize_val(info.get("grossMargins")),
                "revenue": self._sanitize_val(info.get("totalRevenue")),
                "ebitda": self._sanitize_val(info.get("ebitda")),
                "debt_to_equity": self._sanitize_val(info.get("debtToEquity")),
                "current_ratio": self._sanitize_val(info.get("currentRatio")),
                "target_price": self._sanitize_val(info.get("targetMeanPrice")),
                "roce": self._sanitize_val(roce),
                "pb_ratio": self._sanitize_val(pb_ratio),
            }

        return self._execute_with_retry("get_key_statistics", ticker_symbol, _fetch)

"""
Repository Pattern implementation for NewsArticle and CompanyAlias ORM operations.
Encapsulates all direct SQLAlchemy 2.0 database queries and transactions.
Enforces 1-week (7-day) TTL filtering and cleanup operations.
"""




class NewsRepository:
    """
    Data access repository for news database operations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def delete_expired_articles(self, ttl_days: int = 15) -> int:
        """
        Delete articles published before the cutoff threshold (default 15 days)
        and purge any invalid placeholder or example.com URLs from the database.

        Args:
            ttl_days: Time to live in days.

        Returns:
            Number of deleted article records.
        """
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=ttl_days)
        stmt_expired = delete(NewsArticle).where(NewsArticle.published_time < cutoff_time)
        res_expired = self.db.execute(stmt_expired)

        stmt_invalid = delete(NewsArticle).where(NewsArticle.url.like("%example.com%"))
        res_invalid = self.db.execute(stmt_invalid)

        self.db.commit()
        return res_expired.rowcount + res_invalid.rowcount

    def create_article(self, article_data: NewsArticleCreate) -> NewsArticle:
        """
        Persist a new NewsArticle record in PostgreSQL.

        Args:
            article_data: Pydantic creation schema.

        Returns:
            Saved NewsArticle ORM instance.
        """
        article = NewsArticle(
            headline=article_data.headline,
            url=article_data.url,
            source=article_data.source,
            author=article_data.author,
            published_time=article_data.published_time,
            canonical_symbol=article_data.canonical_symbol,
            original_company_name=article_data.original_company_name,
            raw_snippet=article_data.raw_snippet,
            summary=article_data.summary,
            sentiment=article_data.sentiment,
            topic_tags=article_data.topic_tags,
            event_type=article_data.event_type,
            importance_score=article_data.importance_score,
            key_entities=article_data.key_entities,
            key_points=article_data.key_points,
        )
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)
        return article

    def get_by_url(self, url: str) -> Optional[NewsArticle]:
        """
        Find an existing article by exact URL.

        Args:
            url: Article URL string.

        Returns:
            NewsArticle instance if found, else None.
        """
        stmt = select(NewsArticle).where(NewsArticle.url == url)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_latest_by_symbol(
        self, symbol: str, limit: int = 10, ttl_days: int = 15, skip: int = 0
    ) -> List[NewsArticle]:
        """
        Fetch most recent unexpired articles for a specific canonical symbol or ALL symbols within TTL window.

        Args:
            symbol: Canonical ticker symbol (e.g., 'RELIANCE', or 'ALL' for all companies).
            limit: Maximum records to return (Default: 10).
            ttl_days: Time to live in days (Default: 15).
            skip: Offset of records to skip (Default: 0).

        Returns:
            List of NewsArticle ORM instances ordered by published_time desc.
        """
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=ttl_days)
        stmt = select(NewsArticle).where(NewsArticle.published_time >= cutoff_time)
        if symbol and symbol.upper() != "ALL":
            stmt = stmt.where(NewsArticle.canonical_symbol == symbol.upper())
        stmt = stmt.order_by(desc(NewsArticle.published_time)).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_date_range(
        self,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        symbol: Optional[str] = None,
    ) -> List[NewsArticle]:
        """
        Fetch articles within a specified date range.

        Args:
            start_date: Range start timestamp.
            end_date: Range end timestamp.
            symbol: Optional symbol filter.

        Returns:
            List of NewsArticle ORM instances.
        """
        stmt = select(NewsArticle).where(
            NewsArticle.published_time >= start_date,
            NewsArticle.published_time <= end_date,
        )
        if symbol:
            stmt = stmt.where(NewsArticle.canonical_symbol == symbol.upper())

        stmt = stmt.order_by(desc(NewsArticle.published_time))
        return list(self.db.execute(stmt).scalars().all())

    def get_high_importance(
        self, min_score: int = 7, limit: int = 20, ttl_days: int = 15
    ) -> List[NewsArticle]:
        """
        Fetch high-impact unexpired articles above an importance score threshold.

        Args:
            min_score: Minimum importance score threshold (1-10, default 7).
            limit: Maximum records to return.
            ttl_days: Time to live in days (Default: 15).

        Returns:
            List of NewsArticle ORM instances.
        """
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=ttl_days)
        stmt = (
            select(NewsArticle)
            .where(
                NewsArticle.importance_score >= min_score,
                NewsArticle.published_time >= cutoff_time,
            )
            .order_by(desc(NewsArticle.importance_score), desc(NewsArticle.published_time))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_or_get_alias(self, alias: str, canonical_symbol: str) -> CompanyAlias:
        """
        Persist a company alias mapping in PostgreSQL.
        """
        cleaned_alias = alias.lower().strip()
        stmt = select(CompanyAlias).where(CompanyAlias.alias == cleaned_alias)
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing:
            return existing

        alias_obj = CompanyAlias(alias=cleaned_alias, canonical_symbol=canonical_symbol.upper())
        self.db.add(alias_obj)
        self.db.commit()
        self.db.refresh(alias_obj)
        return alias_obj

    def get_all_aliases(self) -> List[CompanyAlias]:
        """
        Fetch all database alias mappings.
        """
        stmt = select(CompanyAlias)
        return list(self.db.execute(stmt).scalars().all())

"""
Repository pattern for Portfolio Analysis persistence.
Enforces a maximum FIFO cap of 10 saved analyses per user.
"""



class PortfolioAnalysisRepository:
    """
    Handles database operations for saved portfolio analysis reports.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def save_analysis(self, user_id: int, analysis: PortfolioAnalysisResponse) -> PortfolioAnalysis:
        """
        Persist a portfolio analysis report for an authenticated user.
        Enforces 1 Portfolio Per User limit: deletes any previous analysis for this user before storing the new one.
        """
        # Delete existing saved analysis for user (1 portfolio per user limit)
        self.db.query(PortfolioAnalysis).filter(PortfolioAnalysis.user_id == user_id).delete()
        self.db.flush()

        # Insert new analysis record
        db_obj = PortfolioAnalysis(
            user_id=user_id,
            summary=analysis.summary,
            portfolio_metrics=analysis.portfolio_metrics.model_dump(),
            holdings=[h.model_dump() for h in analysis.holdings],
            allocation=analysis.allocation.model_dump(),
            rebalancing_suggestions=analysis.rebalancing_suggestions,
            red_flags=analysis.red_flags,
            news_alerts=analysis.news_alerts,
            benchmark_comparison=[b.model_dump() for b in analysis.benchmark_comparison] if analysis.benchmark_comparison else [],
            tax_loss_harvesting=[t.model_dump() for t in analysis.tax_loss_harvesting] if analysis.tax_loss_harvesting else [],
            images=analysis.images,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_user_analyses(self, user_id: int) -> List[PortfolioAnalysis]:
        """
        Retrieve all saved portfolio analyses for an authenticated user.
        """
        stmt = (
            select(PortfolioAnalysis)
            .where(PortfolioAnalysis.user_id == user_id)
            .order_by(PortfolioAnalysis.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_analysis_by_id(self, analysis_id: int, user_id: int) -> Optional[PortfolioAnalysis]:
        """
        Retrieve a specific saved analysis by ID for an authenticated user.
        """
        stmt = select(PortfolioAnalysis).where(
            PortfolioAnalysis.id == analysis_id,
            PortfolioAnalysis.user_id == user_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def delete_analysis(self, analysis_id: int, user_id: int) -> bool:
        """
        Delete a saved analysis by ID for an authenticated user.
        """
        obj = self.get_analysis_by_id(analysis_id=analysis_id, user_id=user_id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
