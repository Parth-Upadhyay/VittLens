import asyncio
from typing import Optional
from app.utils import get_logger
from app.macro_agent.service import run_macro_pipeline

logger = get_logger("finnai.macro_agent.scheduler")

_scheduler_task: Optional[asyncio.Task] = None

async def _macro_loop(interval_hours: int = 1):
    """Background loop that runs the macro intelligence pipeline periodically."""
    logger.info(f"Macro Intelligence Agent scheduler started. Interval: {interval_hours} hour(s).")
    
    # We delay the first run slightly to allow FastAPI to fully boot
    await asyncio.sleep(10)
    
    while True:
        try:
            logger.info("Executing Macro Intelligence Pipeline...")
            await run_macro_pipeline()
            logger.info("Macro Intelligence Pipeline execution completed.")
        except Exception as e:
            logger.error(f"Error during Macro Intelligence Pipeline execution: {e}")
            
        await asyncio.sleep(interval_hours * 3600)

def start_macro_scheduler(app, interval_hours: int = 1):
    """Starts the asyncio background task for the macro agent."""
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_macro_loop(interval_hours))
    return _scheduler_task
