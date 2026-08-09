import json
import os
from typing import List, Dict, Any

def get_sector_rules() -> Dict[str, Any]:
    rules_path = os.path.join(os.path.dirname(__file__), '..', 'rules', 'sector_rules.json')
    try:
        with open(rules_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def map_sectors(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Maps events to sector impacts based on rules.
    """
    rules = get_sector_rules()
    sector_impacts = []
    
    for ev in events:
        category = ev.get("category")
        if category in rules:
            rule = rules[category]
            
            for sector in rule.get("Positive", []):
                sector_impacts.append({
                    "sector": sector,
                    "reason": f"Benefited by event: {ev.get('title')}",
                    "impact": "Positive"
                })
                
            for sector in rule.get("Negative", []):
                sector_impacts.append({
                    "sector": sector,
                    "reason": f"Negatively affected by event: {ev.get('title')}",
                    "impact": "Negative"
                })
                
    # Basic deduplication of sector impacts, favoring the first reason found
    unique_impacts = {}
    for imp in sector_impacts:
        key = (imp["sector"], imp["impact"])
        if key not in unique_impacts:
            unique_impacts[key] = imp
            
    return list(unique_impacts.values())
