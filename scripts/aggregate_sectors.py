import asyncio
import json
import statistics
import sys
import os
from collections import defaultdict

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cache import CacheService
from app.utils import get_logger

logger = get_logger("finnai.scripts.aggregate_sectors")

async def run_aggregation():
    logger.info("Connecting to Redis to fetch deep metrics...")
    
    from app.cache import RedisClient
    client = await RedisClient.get_client()
    
    # 1. Fetch all deep metric keys
    keys = await client.keys("market:deep_metrics:*") if client else []
    if not keys:
        logger.warning("No deep_metrics keys found in Redis. Please run warm_redis.py first.")
        return
        
    logger.info(f"Found {len(keys)} company metrics in cache. Aggregating by sector...")
    
    sector_data = defaultdict(lambda: defaultdict(list))
    
    from app.config.settings import Settings
    from app.utils import CompanyNormalizer
    mapper = CompanyNormalizer()
    
    from app.cache import CacheService
    
    for key_bytes in keys:
        key = key_bytes.decode('utf-8') if isinstance(key_bytes, bytes) else key_bytes
        data = await CacheService.get(key)
        if not data:
            continue
            
        try:
            symbol = data.get("symbol") or data.get("ticker")
            ad = data.get("agent_data", {})
            metrics = data.get("metrics", [])
            
            canonical = mapper.normalize(symbol)
            meta = mapper.company_meta.get(canonical, {})
            sector = meta.get("sector", "Unknown")
            
            if sector == "Unknown":
                continue
                
            pe = ad.get("valuation", {}).get("trailingPE") or ad.get("valuation", {}).get("forwardPE")
            pb = ad.get("valuation", {}).get("priceToBook")
            roe = next((m.get("value") for m in metrics if m.get("key") == "roe"), None)
            rev_growth = next((m.get("value") for m in metrics if m.get("key") == "revenueGrowth"), None)
            net_margin = next((m.get("value") for m in metrics if m.get("key") == "netMargin"), None)
            op_margin = next((m.get("value") for m in metrics if m.get("key") == "operatingMargin"), None)
            
            if pe and pe > 0 and pe < 500: sector_data[sector]["pe"].append(pe)
            if pb and pb > 0 and pb < 100: sector_data[sector]["pb"].append(pb)
            if roe is not None: sector_data[sector]["roe"].append(roe)
            if rev_growth is not None: sector_data[sector]["rev_growth"].append(rev_growth)
            if net_margin is not None: sector_data[sector]["net_margin"].append(net_margin)
            if op_margin is not None: sector_data[sector]["op_margin"].append(op_margin)
            
        except Exception as e:
            logger.warning(f"Error parsing key {key}: {e}")
            
    # 2. Compute averages and medians
    for sector, metrics in sector_data.items():
        stats = {}
        for metric_name, values in metrics.items():
            if not values:
                continue
            stats[metric_name] = {
                "median": statistics.median(values),
                "average": statistics.mean(values),
                "max": max(values),
                "min": min(values),
                "count": len(values)
            }
            
        cache_key = f"market:sector_stats:{sector}"
        await CacheService.set(cache_key, stats, ttl=86400)
        logger.info(f"Aggregated [{sector}]: {len(metrics.get('pe', []))} valid companies.")
        
    logger.info("Sector aggregation complete.")

if __name__ == "__main__":
    asyncio.run(run_aggregation())
