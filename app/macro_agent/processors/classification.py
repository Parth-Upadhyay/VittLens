"""
Event Classification Processor for Macro Intelligence Agent.
Maps news articles to 30+ macro event categories matching sector_rules.json.
Supports multi-label classification and numeric importance scoring (1-10).
"""

from typing import List, Dict, Any

# 30+ category keyword map — must match keys in sector_rules.json
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Oil Rising": ["oil rises", "oil surge", "crude rises", "brent rises", "opec cuts", "oil rally", "oil price up", "petrol price hike"],
    "Oil Falling": ["oil falls", "oil drop", "crude falls", "brent falls", "opec raises", "oil tumbles", "oil price down", "oil slump"],
    "Rate Cut (RBI)": ["rate cut", "rbi cuts", "repo cut", "rbi eases", "policy easing", "rate reduction", "accommodative policy"],
    "Rate Hike (RBI)": ["rate hike", "rbi hikes", "repo hike", "rbi tightens", "rate increase", "hawkish policy", "monetary tightening"],
    "Rate Cut (Fed)": ["fed cuts", "federal reserve cut", "powell cut", "us rate cut", "fomc cut"],
    "Rate Hike (Fed)": ["fed hikes", "federal reserve hike", "powell hike", "us rate hike", "fomc hike"],
    "High Inflation": ["inflation rises", "cpi up", "wpi up", "inflation surge", "prices rising", "inflation high", "price pressure"],
    "Inflation Cooling": ["inflation falls", "cpi down", "wpi down", "inflation eases", "inflation cooling", "prices cooling"],
    "Weak Rupee (INR Depreciation)": ["rupee falls", "rupee weakens", "rupee low", "inr depreciation", "usdinr rises", "rupee hits low", "dollar rises against rupee"],
    "Strong Rupee (INR Appreciation)": ["rupee rises", "rupee gains", "rupee strengthens", "inr appreciates", "usdinr falls"],
    "AI Boom": ["artificial intelligence", "ai boom", "nvidia earnings", "openai", "generative ai", "ai spending", "chatgpt", "machine learning capex"],
    "US Economy Slowdown": ["us recession", "us gdp falls", "us slowdown", "american economy weak", "us layoffs", "us unemployment rises"],
    "US Economy Recovery": ["us gdp grows", "us economy strong", "us recovery", "american economy", "us jobs growth", "us consumer spending"],
    "China Slowdown": ["china slowdown", "china gdp misses", "china demand falls", "china property crisis", "evergrande", "china weak"],
    "China Demand Recovery": ["china recovery", "china gdp beats", "china demand rises", "china stimulus", "pboc eases"],
    "Government Capex Surge": ["government capex", "infra spending", "budget capex", "national infrastructure", "pm gati shakti", "india infrastructure", "defence order"],
    "Budget Deficit / Fiscal Tightening": ["fiscal deficit", "budget deficit", "spending cuts", "fiscal tightening", "austerity"],
    "Coal Prices Rising": ["coal prices rise", "coal surge", "thermal coal up", "coal shortage"],
    "Coal Prices Falling": ["coal prices fall", "coal drops", "thermal coal down", "coal surplus"],
    "Gold Prices Rising": ["gold rises", "gold rally", "gold hits high", "gold surge", "precious metals up"],
    "Monsoon Weak": ["monsoon deficit", "weak monsoon", "below normal rainfall", "drought", "el nino"],
    "Monsoon Normal / Good": ["normal monsoon", "good monsoon", "above normal rainfall", "monsoon on track", "la nina"],
    "5G Rollout": ["5g launch", "5g spectrum", "5g rollout", "telecom 5g", "airtel 5g", "jio 5g"],
    "USFDA Crackdown": ["usfda warning", "fda import alert", "fda 483", "fda crackdown", "pharma fda violation", "usfda ban"],
    "USFDA Approvals Surge": ["fda approval", "usfda approves", "drug approval", "nda approval", "anda approval", "fda clears"],
    "Defence Spending Increase": ["defence budget", "defence spending rises", "military budget", "india defence", "defence order", "hal order", "bel contract"],
    "Defence Budget Constraint": ["defence budget cut", "defence spending falls", "military cuts"],
    "FII Inflows": ["fii buying", "fii inflows", "foreign buying", "fpi inflow", "foreign investment india"],
    "FII Outflows": ["fii selling", "fii outflows", "foreign selling", "fpi outflow", "foreign exit india"],
    "Housing Boom": ["real estate surge", "housing demand", "property prices rise", "home sales up", "real estate boom"],
    "EV Adoption Acceleration": ["ev sales surge", "electric vehicle", "ev adoption", "ev market grows", "ev charging"],
    "Renewable Energy Policy Push": ["solar policy", "renewable energy push", "green energy target", "wind energy", "clean energy india"],
    "Global Recession Risk": ["global recession", "world economy slowdown", "imf downgrades", "recession fears", "global slowdown"],
    "Geopolitical Tensions": ["geopolitical tension", "war", "conflict", "sanctions", "ukraine", "taiwan", "middle east conflict", "trade war"],
    "Credit Rating Upgrade (India Sovereign)": ["india rating upgrade", "moody's upgrade india", "s&p upgrades india", "fitch upgrades india"],
    "Earnings Beat": ["beats estimates", "profit surges", "revenue beats", "earnings beat", "quarterly results beat", "q results above"],
    "Earnings Miss": ["misses estimates", "profit falls", "revenue miss", "earnings miss", "quarterly results miss", "q results below"],
}

_CRITICAL_KEYWORDS = [
    "crash", "collapse", "emergency", "crisis", "plunge", "war", "sanctions",
    "default", "ban", "halt", "investigation", "fraud", "bankruptcy"
]

_HIGH_IMPORTANCE = [
    "cut", "hike", "surge", "rally", "beats", "misses", "approval", "order"
]


def classify_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Multi-label classification: each event can match multiple categories.
    Assigns numeric importance score 1-10.
    """
    classified = []
    for ev in events:
        text = (ev.get("title", "") + " " + ev.get("summary", "")).lower()

        matched_categories = []
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                matched_categories.append(cat)

        # Primary category (first match), store all matches
        primary_category = matched_categories[0] if matched_categories else "General"

        # Importance scoring (1-10)
        if any(kw in text for kw in _CRITICAL_KEYWORDS):
            importance = 9
        elif matched_categories:
            importance = 7
            if any(kw in text for kw in _HIGH_IMPORTANCE):
                importance = 8
        elif ev.get("credibility", 0) > 0.9:
            importance = 5
        else:
            importance = 3

        ev["category"] = primary_category
        ev["all_categories"] = matched_categories
        ev["importance"] = importance
        ev["confidence"] = 0.9 if matched_categories else 0.4
        classified.append(ev)

    # Sort by importance descending
    classified.sort(key=lambda x: x.get("importance", 0), reverse=True)
    return classified
