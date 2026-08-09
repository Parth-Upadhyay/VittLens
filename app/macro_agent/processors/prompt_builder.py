"""
Macro LLM Summary Prompt Builder.
Asks LLM for a rich structured JSON with per-event sector impact mapping.
"""

import json
from typing import Dict, Any, List


def build_summary_prompt(
    snapshot: Dict[str, Any],
    events: List[Dict[str, Any]],
    sector_impacts: List[Dict[str, Any]]
) -> str:
    """
    Constructs a detailed prompt for the LLM to generate a rich macro summary JSON.
    The LLM is asked to produce a structured response including key_events with
    per-event sector impact, sentiment, and importance.
    """
    # Only pass top-15 events to avoid token overflow
    top_events = events[:15]

    prompt = f"""You are a Macro Intelligence AI for an Indian equity financial platform (NIFTY 500).
Analyze the provided market snapshot, classified macro events, and pre-computed sector impacts.
Return ONLY a valid JSON object matching the exact schema below. No markdown, no explanations.

### MARKET SNAPSHOT
{json.dumps(snapshot, indent=2, default=str)}

### CLASSIFIED MACRO EVENTS (top {len(top_events)})
{json.dumps(top_events, indent=2, default=str)}

### PRE-COMPUTED SECTOR IMPACTS
{json.dumps(sector_impacts[:20], indent=2, default=str)}

### REQUIRED JSON OUTPUT SCHEMA
{{
  "market_sentiment": "Risk On | Risk Off | Neutral",
  "confidence": <float 0.0-1.0>,
  "summary_text": "<3-4 sentence executive macro overview covering India markets, global triggers, RBI/Fed policy, commodity moves>",
  "watchlist": ["<5-7 most relevant sectors or themes to watch e.g. IT, Energy, Banking, Pharma>"],
  "key_events": [
    {{
      "title": "<concise event title>",
      "category": "<event category e.g. Rate Cut, Oil Rising>",
      "summary": "<2-sentence detail on the event and its India market impact>",
      "importance": <integer 1-10>,
      "sector_impact": {{
        "positive": ["<list of positively affected sectors>"],
        "negative": ["<list of negatively affected sectors>"]
      }},
      "source": "<source name>"
    }}
  ]
}}

Rules:
- Include 5-10 key_events, prioritizing highest importance ones.
- If market snapshot shows Nifty/Sensex data, use it to inform sentiment.
- If no clear direction, default sentiment to Neutral with confidence 0.5.
- Always output valid JSON. No trailing commas.
"""
    return prompt
