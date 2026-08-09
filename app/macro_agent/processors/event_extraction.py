from typing import List, Dict, Any

def extract_events(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts events from deduplicated news articles deterministically.
    Assigns credibility based on the source.
    """
    events = []
    
    # Simple credibility mapping
    credibility_map = {
        "Reuters": 0.99,
        "Bloomberg": 0.95,
        "Financial Times": 0.95,
        "CNBC": 0.90,
        "Mint": 0.85,
        "Business Standard": 0.85,
        "Economic Times": 0.85,
        "GDELT": 0.70,
        "NewsAPI": 0.70
    }

    for article in articles:
        source = article.get("source", "Unknown")
        credibility = credibility_map.get(source, 0.60)
        
        # A deterministic extraction just assumes the article title is the event for now
        # More advanced NLP could be placed here later.
        events.append({
            "title": article.get("title", ""),
            "summary": article.get("summary", ""),
            "source": source,
            "credibility": credibility,
            # We don't assign category/importance here, that happens in classification
        })
        
    return events
