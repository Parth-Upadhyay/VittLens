"""
External News Fetcher service for FinnAI Platform.
Fetches financial news headlines and metadata from Google News RSS feed (primary)
with fallback to Marketaux REST API (secondary).
"""

import datetime
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from email.utils import parsedate_to_datetime

from app.config.settings import Settings
from app.utils import get_logger

logger = get_logger("finnai.news_fetcher")


class NewsFetcher:
    """
    Handles external HTTP requests to news RSS feeds and REST APIs.
    Isolated to the ingestion pipeline worker.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.marketaux_api_key = self.settings.marketaux_api_key
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def _is_valid_url(self, url: str) -> bool:
        """
        Validate URL format and filter out invalid/example/placeholder links.
        """
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return False
        url_lower = url.lower()
        invalid_patterns = ["example.com", "example.org", "example.net", "localhost", "placeholder", "test.com"]
        return not any(pat in url_lower for pat in invalid_patterns)

    def fetch_google_news_rss(self, query: str) -> List[Dict[str, Any]]:
        """
        Primary news fetcher using Google News RSS feed.

        Args:
            query: Company search query (e.g., 'Reliance Industries stock news India').

        Returns:
            List of article metadata dictionaries.
        """
        encoded_query = urllib.parse.quote(f"{query} stock news India")
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

        articles: List[Dict[str, Any]] = []
        try:
            req = urllib.request.Request(rss_url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel is None:
                return []

            for item in channel.findall("item"):
                title = item.findtext("title") or ""
                link = (item.findtext("link") or "").strip()
                pub_date_str = item.findtext("pubDate") or ""
                source_elem = item.find("source")
                source_name = source_elem.text if source_elem is not None else "Financial Press"
                description = item.findtext("description") or title

                try:
                    pub_time = parsedate_to_datetime(pub_date_str)
                except Exception:
                    pub_time = datetime.datetime.now(datetime.timezone.utc)

                if title and self._is_valid_url(link):
                    articles.append({
                        "headline": title.strip(),
                        "url": link,
                        "source": source_name.strip(),
                        "author": None,
                        "published_time": pub_time,
                        "raw_snippet": description.strip(),
                    })

            logger.info(f"Fetched {len(articles)} valid articles from Google News RSS (Primary) for query '{query}'.")
            return articles

        except Exception as e:
            logger.warning(f"Google News RSS primary fetch failed for query '{query}': {e}")
            return []

    def fetch_marketaux_api(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Secondary fallback news fetcher using Marketaux REST API.

        Args:
            symbol: Ticker symbol (e.g. 'RELIANCE').

        Returns:
            List of article metadata dictionaries.
        """
        if not self.marketaux_api_key:
            logger.debug("Marketaux API key not set. Skipping Marketaux secondary fetch.")
            return []

        url = f"https://api.marketaux.com/v1/news/all?symbols={symbol}&api_token={self.marketaux_api_key}&language=en"
        articles: List[Dict[str, Any]] = []

        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            items = data.get("data", [])
            for item in items:
                pub_str = item.get("published_at")
                try:
                    pub_time = datetime.datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    pub_time = datetime.datetime.now(datetime.timezone.utc)

                art_url = item.get("url", "").strip()
                if item.get("title") and self._is_valid_url(art_url):
                    articles.append({
                        "headline": item.get("title", "").strip(),
                        "url": art_url,
                        "source": item.get("source", "Marketaux").strip(),
                        "author": item.get("author"),
                        "published_time": pub_time,
                        "raw_snippet": item.get("description", item.get("snippet", "")),
                    })

            logger.info(f"Fetched {len(articles)} valid articles from Marketaux API (Secondary) for symbol '{symbol}'.")
            return articles

        except Exception as e:
            logger.warning(f"Marketaux API secondary fetch failed for symbol '{symbol}': {e}")
            return []

    def fetch_news_for_company(
        self, symbol: str, company_name: str
    ) -> List[Dict[str, Any]]:
        """
        Primary entrypoint for fetching news articles for a company symbol.
        Tries Google News RSS first (primary); falls back to Marketaux REST API (secondary) if empty or failing.

        Args:
            symbol: Canonical symbol (e.g., 'RELIANCE').
            company_name: Primary company name (e.g. 'Reliance Industries').

        Returns:
            List of article metadata dicts.
        """
        # Primary: Google News RSS
        articles = self.fetch_google_news_rss(company_name)

        # Secondary fallback: Marketaux REST API
        if not articles:
            logger.info(f"Google RSS primary fetch returned 0 articles for '{company_name}'. Triggering Marketaux fallback...")
            articles = self.fetch_marketaux_api(symbol)

        return articles
