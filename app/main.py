"""
FastAPI Application Entry Point for FinnAI Platform.
Configures CORS middleware, database schema initialization, news ingestion worker lifespan,
and includes all API v1 routers under /api/v1.

Run locally:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.config.settings import Settings
from app.db.database import init_db
from app.utils import get_logger
from app.workers.news_worker import start_news_worker_lifespan
from app.cache import RedisClient

logger = get_logger("finnai.main")
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI Lifespan context manager.
    Initializes database tables and starts background news ingestion worker.
    """
    logger.info("=== Starting FinnAI Platform FastAPI Service ===")

    # 1. Initialize database schema
    init_db()
    logger.info("Database schema verified.")

    # 2. Start background news worker scheduler
    worker_handle = start_news_worker_lifespan(app)

    # 3. Start Macro Intelligence background scheduler (every 1 hour)
    from app.macro_agent.scheduler import start_macro_scheduler
    macro_handle = start_macro_scheduler(app, interval_hours=1)

    yield

    logger.info("=== Shutting down FinnAI Platform FastAPI Service ===")
    
    # 3. Close Redis connection pool
    await RedisClient.close()


# Instantiate FastAPI Application
app = FastAPI(
    title="FinnAI Financial Intelligence Platform API",
    description="Production-grade AI Financial Intelligence Platform for NIFTY Top 20 companies.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS Middleware
cors_origins_str = settings.cors_origins
if cors_origins_str == "*":
    origins = ["*"]
else:
    origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Router
app.include_router(api_v1_router)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled API error on '{request.method} {request.url.path}': {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "error": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
