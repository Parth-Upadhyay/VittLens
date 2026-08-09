"""
LLM Provider Factory module for FinnAI Platform.
Provides centralized factory functions to instantiate configured LLM providers.
"""

from app.config.settings import Settings
from app.services.base_provider import LLMProvider
from app.services.groq_service import GroqProvider


def get_llm_provider(
    provider_name: str = "groq", settings: Settings | None = None
) -> LLMProvider:
    """
    Factory function to instantiate an LLMProvider instance based on provider identifier.

    Args:
        provider_name: Identifier of desired LLM provider (default: 'groq').
        settings: Optional Settings configuration instance.

    Returns:
        Instance of LLMProvider implementation.

    Raises:
        ValueError: If unsupported provider identifier is passed.
    """
    provider_key = provider_name.lower().strip()

    if provider_key in ("groq", "default"):
        return GroqProvider(settings=settings)
    else:
        raise ValueError(
            f"Unsupported LLM provider '{provider_name}'. Supported providers: ['groq']"
        )
