"""
Macro Intelligence LLM Summary Generator.
Parses rich JSON from LLM including key_events with per-event sector impacts.
"""

import json
import asyncio
from app.services.factory import get_llm_provider
from app.config.settings import Settings


async def generate_macro_summary(prompt: str) -> dict:
    """
    Generates a structured macro summary using the configured LLM provider.
    Returns a dict with market_sentiment, confidence, summary_text, watchlist, key_events.
    """
    settings = Settings()
    llm = get_llm_provider(settings=settings)

    response = await asyncio.to_thread(
        llm.generate,
        user_prompt=prompt,
        system_prompt=(
            "You are a Macro Intelligence JSON processor for an Indian equity platform. "
            "ONLY output valid JSON matching the exact schema provided. "
            "No markdown backticks, no explanations, no extra keys."
        ),
        temperature=0.15
    )

    response_text = response.content.strip()

    # Strip markdown fences if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].strip()

    # Find JSON object boundaries
    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    if start != -1 and end > start:
        response_text = response_text[start:end]

    try:
        data = json.loads(response_text)
        # Ensure key_events exists
        if "key_events" not in data:
            data["key_events"] = []
        return data
    except Exception as e:
        return {
            "market_sentiment": "Neutral",
            "confidence": 0.0,
            "summary_text": f"Macro pipeline ran but LLM summary parsing failed: {str(e)}",
            "watchlist": [],
            "key_events": []
        }
