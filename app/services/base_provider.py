"""
Abstract Base Class defining LLM Provider contract.
"""

from abc import ABC, abstractmethod
from typing import Generator, Optional
from app.schemas import LLMResponse


class LLMProvider(ABC):
    """
    Abstract interface for LLM Providers (e.g. GroqProvider).
    """

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate completion response synchronously.
        """
        pass

    @abstractmethod
    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Stream completion tokens real-time as a Generator.
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test provider connectivity.
        """
        pass
