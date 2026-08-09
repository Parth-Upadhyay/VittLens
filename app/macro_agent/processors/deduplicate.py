from typing import List, Dict, Any
from difflib import SequenceMatcher

def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def deduplicate_news(articles: List[Dict[str, Any]], similarity_threshold: float = 0.75) -> List[Dict[str, Any]]:
    """
    Removes duplicate or highly similar news articles based on their titles.
    """
    deduped = []
    for article in articles:
        title = article.get("title", "")
        if not title:
            continue
            
        is_duplicate = False
        for seen in deduped:
            if similar(title.lower(), seen.get("title", "").lower()) > similarity_threshold:
                is_duplicate = True
                break
                
        if not is_duplicate:
            deduped.append(article)
            
    return deduped
