"""
Official source fetchers for Macro Intelligence Agent.
Pulls RBI, PIB, and SEBI RSS feeds — all free, no API key required.
"""

import asyncio
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

_RSS_FEEDS = [
    ("RBI", "https://www.rbi.org.in/rss/latest.xml"),
    ("PIB India", "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"),
    ("SEBI", "https://www.sebi.gov.in/sebi_data/rss/rss_all.xml"),
    ("Economic Times Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Business Standard", "https://www.business-standard.com/rss/markets-106.rss"),
    ("Mint Economy", "https://www.livemint.com/rss/economy"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("Investing.com Global", "https://www.investing.com/rss/news_285.rss"),
    ("CNBC World", "https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=12000000&id=100727362"),
    ("CNBC US Economy", "https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=12000000&id=20910258"),
]


def _fetch_rss(source_name: str, feed_url: str, max_items: int = 6) -> List[Dict[str, Any]]:
    articles = []
    try:
        req = urllib.request.Request(feed_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            root = ET.fromstring(r.read())

        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")
        for item in items[:max_items]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or title).strip()
            pub_str = item.findtext("pubDate") or ""
            try:
                pub_at = parsedate_to_datetime(pub_str).isoformat()
            except Exception:
                pub_at = datetime.utcnow().isoformat()

            if title and link:
                articles.append({
                    "source": source_name,
                    "title": title,
                    "url": link,
                    "published_at": pub_at,
                    "summary": desc[:500],
                })
    except Exception:
        pass
    return articles


async def fetch_official_sources() -> List[Dict[str, Any]]:
    """Fetch from RBI, PIB, SEBI, and major financial news RSS feeds concurrently."""
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, _fetch_rss, name, url)
        for name, url in _RSS_FEEDS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    combined = []
    for res in results:
        if isinstance(res, list):
            combined.extend(res)
    return combined
