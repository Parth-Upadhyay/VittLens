import json
from typing import Dict, Any, List

def build_summary_prompt(
    snapshot: Dict[str, Any],
    events: List[Dict[str, Any]],
    sector_impacts: List[Dict[str, Any]]
) -> str:
    """
    Constructs a clean prompt for the LLM to generate the final summary JSON.
    """
    
    prompt = f"""
You are a Macro Intelligence AI for a financial platform.
Your task is to summarize the following pre-structured macroeconomic events and output a specific JSON format.
DO NOT create paragraphs of text. ONLY return the JSON structure.

### MARKET SNAPSHOT
{json.dumps(snapshot, indent=2)}

### CLASSIFIED EVENTS
{json.dumps(events, indent=2)}

### SECTOR IMPACTS
{json.dumps(sector_impacts, indent=2)}

### REQUIRED JSON OUTPUT FORMAT
{{
  "market_sentiment": "Risk On | Risk Off | Neutral",
  "confidence": <float between 0 and 1>,
  "summary_text": "<A brief 2-3 sentence overview of the current macro situation>",
  "watchlist": ["<list of 3-5 sectors/companies to watch closely>"]
}}

Determine the overall market sentiment based on the events and market snapshot.
Output ONLY valid JSON.
"""
    return prompt
