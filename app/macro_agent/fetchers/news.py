"""
Macro Intelligence News Fetcher.
Uses NewsAPI (multi-query) + Google News RSS as free fallback.
Stays within daily API limits by grouping queries.
"""

import asyncio
import httpx
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Targeted macro query bank — covers all major sector rules
_MACRO_QUERIES = [
    "RBI repo rate India monetary policy",
    "crude oil OPEC Brent price",
    "Nifty Sensex India stock market",
    "US Federal Reserve interest rate inflation",
    "India IT sector TCS Infosys earnings",
    "Indian rupee USD exchange rate",
    "USFDA pharma drug approval India",
    "India defence budget government spending",
    "gold silver commodity prices India",
    "5G spectrum telecom India",
    "India inflation CPI WPI",
    "FII DII foreign investment India market",
    "India GDP growth economy",
    "steel coal metal mining prices India",
    "India budget fiscal deficit government capex",
]


async def _fetch_newsapi_query(client: httpx.AsyncClient, api_key: str, query: str, days_back: int = 1) -> List[Dict[str, Any]]:
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={urllib.parse.quote(query)}"
        f"&from={from_date}&sortBy=publishedAt&language=en&pageSize=5"
        f"&apiKey={api_key}"
    )
    try:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code == 200:
            return [
                {
                    "source": a.get("source", {}).get("name", "NewsAPI"),
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "published_at": a.get("publishedAt", ""),
                    "summary": a.get("description", "") or a.get("content", ""),
                }
                for a in resp.json().get("articles", [])
                if a.get("title") and a.get("url")
            ]
    except Exception:
        pass
    return []


def _fetch_google_rss(query: str, max_items: int = 5) -> List[Dict[str, Any]]:
    encoded = urllib.parse.quote(f"{query}")
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
    articles = []
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            root = ET.fromstring(r.read())
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item")[:max_items]:
            title = item.findtext("title") or ""
            link = (item.findtext("link") or "").strip()
            pub_str = item.findtext("pubDate") or ""
            src_elem = item.find("source")
            source = src_elem.text if src_elem is not None else "Google News"
            desc = item.findtext("description") or title
            try:
                pub_at = parsedate_to_datetime(pub_str).isoformat()
            except Exception:
                pub_at = datetime.utcnow().isoformat()
            if title and link:
                articles.append({
                    "source": source,
                    "title": title.strip(),
                    "url": link,
                    "published_at": pub_at,
                    "summary": desc.strip(),
                })
    except Exception:
        pass
    return articles


async def fetch_macro_news() -> List[Dict[str, Any]]:
    """
    Fetches macro-level news using:
    1. NewsAPI — parallel multi-query (5 articles each, capped to 5 queries to save daily quota)
    2. Google News RSS — free fallback for remaining queries
    Returns up to ~50 raw articles.
    """
    api_key = os.getenv("NEWSAPI_KEY")
    combined: List[Dict[str, Any]] = []

    # Split: first 5 queries via NewsAPI (paid, high quality), rest via RSS
    newsapi_queries = _MACRO_QUERIES[:5]
    rss_queries = _MACRO_QUERIES[5:]

    if api_key:
        async with httpx.AsyncClient() as client:
            tasks = [_fetch_newsapi_query(client, api_key, q) for q in newsapi_queries]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    combined.extend(res)

    # RSS queries run in thread pool (sync urllib)
    loop = asyncio.get_event_loop()
    rss_tasks = [
        loop.run_in_executor(None, _fetch_google_rss, q, 4)
        for q in rss_queries
    ]
    rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)
    for res in rss_results:
        if isinstance(res, list):
            combined.extend(res)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for art in combined:
        u = art.get("url", "")
        if u and u not in seen:
            seen.add(u)
            deduped.append(art)

    return deduped
