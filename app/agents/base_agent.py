"""
Abstract Base Agent interface for FinnAI Platform.
Defines common asynchronous execution protocol and standardized error handling.
"""

from abc import ABC, abstractmethod
import time
from typing import Any, Optional
from app.config.settings import Settings
from app.schemas import AgentContext, AgentResult
from app.utils import get_logger

logger = get_logger("finnai.agents.base")


class BaseAgent(ABC):
    """
    Abstract Base Class that all domain agents (Market, News, Filing, Quant) must implement.
    Guarantees consistent async execution interface: `async run(context: AgentContext) -> AgentResult`.
    """

    def __init__(self, name: str, settings: Optional[Settings] = None) -> None:
        self.name = name
        self.settings = settings or Settings()

    @abstractmethod
    async def _execute(self, context: AgentContext) -> Any:
        """
        Internal execution logic implemented by domain subclass agents.
        Must return structured Pydantic result payload.
        """
        pass

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Public entrypoint executing the agent with timing, error catching, and logging.

        Args:
            context: Standardized AgentContext input schema.

        Returns:
            Standardized AgentResult container model.
        """
        start_time = time.perf_counter()
        logger.info(f"[{self.name}] Starting execution for symbols: {context.symbols}...")

        try:
            payload_data = await self._execute(context)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            logger.info(f"[{self.name}] Execution succeeded in {latency_ms:.2f} ms.")
            return AgentResult(
                agent_name=self.name,
                status="success",
                execution_time_ms=round(latency_ms, 2),
                data=payload_data,
                error_message=None,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"[{self.name}] Execution failed after {latency_ms:.2f} ms: {e}")
            return AgentResult(
                agent_name=self.name,
                status="error",
                execution_time_ms=round(latency_ms, 2),
                data=None,
                error_message=str(e),
            )
