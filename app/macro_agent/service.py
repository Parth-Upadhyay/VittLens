import asyncio
import json
from datetime import datetime
from app.db.database import SessionLocal
from app.cache import RedisClient
from app.macro_agent.storage.postgres import MacroRepository
from app.macro_agent.fetchers.market_data import fetch_market_snapshot
from app.macro_agent.fetchers.news import fetch_macro_news
from app.macro_agent.fetchers.official_sources import fetch_official_sources
from app.macro_agent.processors.deduplicate import deduplicate_news
from app.macro_agent.processors.event_extraction import extract_events
from app.macro_agent.processors.classification import classify_events
from app.macro_agent.processors.sector_mapping import map_sectors
from app.macro_agent.processors.prompt_builder import build_summary_prompt
from app.macro_agent.processors.llm_summary import generate_macro_summary

async def run_macro_pipeline():
    """
    Executes the full Macro Intelligence pipeline.
    """
    db = SessionLocal()
    repo = MacroRepository(db)
    
    # 1. Initialize Run
    run = repo.create_run()
    
    try:
        # 2. Fetch Data
        market_snapshot_task = asyncio.to_thread(fetch_market_snapshot)
        news_task = fetch_macro_news()
        official_task = fetch_official_sources()
        
        market_snapshot, news_articles, official_releases = await asyncio.gather(
            market_snapshot_task, news_task, official_task
        )
        
        all_raw_news = news_articles + official_releases
        
        # Save raw data
        repo.save_market_snapshot(run.id, market_snapshot)
        repo.save_news_articles(run.id, all_raw_news)
        
        # 3. Process Pipeline
        deduped_news = deduplicate_news(all_raw_news)
        raw_events = extract_events(deduped_news)
        classified_events = classify_events(raw_events)
        
        sector_impacts = map_sectors(classified_events)
        
        # Save processed data
        repo.save_events(run.id, classified_events)
        repo.save_sector_impacts(run.id, sector_impacts)
        
        # 4. Prompt Builder & Summarization
        prompt = build_summary_prompt(
            snapshot=market_snapshot,
            events=classified_events,
            sector_impacts=sector_impacts
        )
        summary_result = await generate_macro_summary(prompt)
        
        # Save final summary
        summary = repo.save_summary(
            run.id,
            sentiment=summary_result.get("market_sentiment", "Neutral"),
            confidence=summary_result.get("confidence", 0.0),
            summary_text=summary_result.get("summary_text", ""),
            watchlist=summary_result.get("watchlist", [])
        )
        
        repo.update_run_status(run.id, "completed")
        
        # 5. Update Redis Cache
        try:
            redis = await RedisClient.get_client()
            if redis:
                cache_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "market_snapshot": market_snapshot,
                    "summary": {
                        "sentiment": summary.market_sentiment,
                        "confidence": summary.confidence,
                        "text": summary.summary_text,
                        "watchlist": summary.watchlist
                    },
                    "events": classified_events,
                    "sector_impacts": sector_impacts
                }
                await redis.set("macro_agent:latest", json.dumps(cache_data), ex=3600*2) # Cache for 2 hours
        except Exception as e:
            pass # Non-critical if cache fails
            
    except Exception as e:
        repo.update_run_status(run.id, "failed", error=str(e))
    finally:
        db.close()
