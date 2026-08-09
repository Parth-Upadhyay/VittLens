"""
Quant Agent for FinnAI Platform.
Consumes QuantService exclusively to calculate quantitative financial ratios and multi-symbol comparisons.
Pure Python logic. Returns structured Pydantic models only (zero LLM calls, zero natural language generation).
"""

import asyncio
from typing import Dict, Optional
from app.agents.base_agent import BaseAgent
from app.config.settings import Settings
from app.schemas import AgentContext, QuantAgentResult
from app.schemas import QuantComparison, RatioSnapshot
from app.services.quant_service import QuantService
from app.utils import get_logger

logger = get_logger("finnai.agents.quant")


class QuantAgent(BaseAgent):
    """
    Quant Domain Agent executing ratio calculation and quantitative financial comparisons.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        quant_service: Optional[QuantService] = None,
    ) -> None:
        super().__init__(name="QuantAgent", settings=settings)
        self.quant_service = quant_service or QuantService(self.settings)

    async def _execute(self, context: AgentContext) -> QuantAgentResult:
        """
        Execute ratio snapshot calculation and side-by-side comparison for target symbols.
        """
        snapshots: Dict[str, RatioSnapshot] = {}
        comparison: Optional[QuantComparison] = None

        symbols = context.symbols or ["RELIANCE"]

        for symbol in symbols:
            snap = await self.quant_service.get_full_ratio_snapshot(symbol)
            snapshots[snap.canonical_symbol] = snap

        if len(symbols) > 1:
            comparison = await self.quant_service.compare_symbols(symbols)

        return QuantAgentResult(
            snapshots=snapshots,
            comparison=comparison,
        )
