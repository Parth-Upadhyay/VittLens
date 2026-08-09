import json
from app.services.factory import get_llm_provider
from app.config.settings import Settings

async def generate_macro_summary(prompt: str) -> dict:
    """
    Generates a structured macro summary from the prompt using the configured LLM provider.
    Expects a JSON formatted string back from the LLM.
    """
    settings = Settings()
    llm = get_llm_provider(settings=settings)
    
    import asyncio
    response = await asyncio.to_thread(
        llm.generate,
        user_prompt=prompt,
        system_prompt="You are a Macro Intelligence JSON processor. ONLY output valid JSON. No markdown backticks, no explanations.",
        temperature=0.1
    )
    
    response_text = response.content
    
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].strip()
            
        data = json.loads(response_text)
        return data
    except Exception as e:
        # Fallback empty structure
        return {
            "market_sentiment": "Neutral",
            "confidence": 0.0,
            "summary_text": f"Error parsing LLM response: {str(e)}",
            "watchlist": []
        }
