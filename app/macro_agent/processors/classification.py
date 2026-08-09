from typing import List, Dict, Any

def classify_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Categorizes events and assigns importance.
    """
    keywords = {
        "Rate Cuts": ["rate cut", "powell", "rbi", "repo", "interest rate", "fed"],
        "High Inflation": ["inflation", "cpi", "wpi", "prices rising"],
        "Oil Rising": ["oil", "brent", "crude", "opec"],
        "AI Boom": ["ai", "artificial intelligence", "nvidia", "openai", "semiconductor"],
        "Weak Rupee": ["rupee", "inr", "usdinr", "depreciation"]
    }
    
    important_keywords = ["crash", "recession", "war", "emergency", "crisis", "cut", "hike", "plunge"]

    classified = []
    for ev in events:
        text = (ev.get("title", "") + " " + ev.get("summary", "")).lower()
        
        category = "Unknown"
        confidence = 0.5
        for cat, kws in keywords.items():
            if any(kw in text for kw in kws):
                category = cat
                confidence = 0.9
                break
                
        # Determine importance
        importance = "low"
        if any(kw in text for kw in important_keywords):
            importance = "critical"
        elif category != "Unknown":
            importance = "high"
        elif ev.get("credibility", 0) > 0.9:
            importance = "medium"

        ev["category"] = category
        ev["confidence"] = confidence
        ev["importance"] = importance
        classified.append(ev)

    return classified
