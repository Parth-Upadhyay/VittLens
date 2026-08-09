import httpx
import os
from typing import List, Dict, Any
from datetime import datetime, timedelta

async def fetch_newsapi(query: str, days_back: int = 1) -> List[Dict[str, Any]]:
    """
    Fetches financial/macro news from NewsAPI.
    Uses NEWSAPI_KEY from environment.
    """
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        return []
    
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = f"https://newsapi.org/v2/everything?q={query}&from={from_date}&sortBy=publishedAt&language=en&apiKey={api_key}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                articles = []
                for item in data.get("articles", [])[:10]:
                    articles.append({
                        "source": item.get("source", {}).get("name", "NewsAPI"),
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "published_at": item.get("publishedAt", ""),
                        "summary": item.get("description", "")
                    })
                return articles
    except Exception:
        pass
    return []

async def fetch_marketaux() -> List[Dict[str, Any]]:
    """
    Fetches global macro news from Marketaux API.
    """
    api_key = os.getenv("MARKETAUX_API_KEY")
    if not api_key:
        return []
        
    url = f"https://api.marketaux.com/v1/news/all?language=en&limit=10&api_token={api_key}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                articles = []
                for item in data.get("data", []):
                    articles.append({
                        "source": item.get("source", "Marketaux"),
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "published_at": item.get("published_at", ""),
                        "summary": item.get("description", "")
                    })
                return articles
    except Exception:
        pass
    return []

async def fetch_macro_news() -> List[Dict[str, Any]]:
    """
    Combines news from NewsAPI and Marketaux.
    """
    # Run them concurrently
    import asyncio
    newsapi_task = asyncio.create_task(fetch_newsapi("macro OR economy OR Nifty OR RBI OR inflation", 1))
    marketaux_task = asyncio.create_task(fetch_marketaux())
    
    results = await asyncio.gather(newsapi_task, marketaux_task, return_exceptions=True)
    
    combined = []
    for res in results:
        if isinstance(res, list):
            combined.extend(res)
            
    return combined
