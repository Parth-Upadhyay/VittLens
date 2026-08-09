from __future__ import annotations

# Merged from cache/*

from app.config.settings import Settings
from app.utils import get_logger
from functools import wraps
from typing import Any, Optional
from typing import Callable, Any, Type, Optional
from typing import Optional
import hashlib
import orjson
import redis
import redis.asyncio as aioredis
import zlib



"""
Abstracted Redis caching service with zlib compression and orjson serialization.
"""

logger = get_logger("finnai.cache.service")
settings = Settings()

class CacheService:
    @staticmethod
    async def get(key: str) -> Optional[Any]:
        if not settings.cache_enabled:
            return None
            
        client = await RedisClient.get_client()
        if not client:
            return None
            
        try:
            data = await client.get(key)
            if not data:
                return None
                
            try:
                uncompressed = zlib.decompress(data)
                return orjson.loads(uncompressed)
            except zlib.error:
                # Fallback for uncompressed raw JSON data
                return orjson.loads(data)
        except Exception as e:
            logger.warning(f"Cache GET error for key '{key}': {e}")
            return None

    @staticmethod
    async def set(key: str, value: Any, ttl: int = 300) -> bool:
        if not settings.cache_enabled:
            return False
            
        client = await RedisClient.get_client()
        if not client:
            return False
            
        try:
            # Handle pydantic v2 models automatically by checking for model_dump
            if hasattr(value, 'model_dump'):
                dumped = value.model_dump()
            else:
                dumped = value
                
            serialized = orjson.dumps(dumped)
            compressed = zlib.compress(serialized)
            await client.setex(key, ttl, compressed)
            return True
        except Exception as e:
            logger.warning(f"Cache SET error for key '{key}': {e}")
            return False

    @staticmethod
    async def delete(key: str) -> bool:
        client = await RedisClient.get_client()
        if not client:
            return False
        try:
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache DELETE error for key '{key}': {e}")
            return False

    @staticmethod
    async def delete_pattern(pattern: str) -> int:
        client = await RedisClient.get_client()
        if not client:
            return 0
        try:
            count = 0
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)
                count += 1
            return count
        except Exception as e:
            logger.warning(f"Cache PATTERN DELETE error for '{pattern}': {e}")
            return 0


class SyncCacheService:
    """Synchronous cache service for use in non-async contexts (e.g., existing sync GroqProvider)."""
    _pool: Optional[redis.Redis] = None

    @classmethod
    def get_client(cls) -> Optional[redis.Redis]:
        if not settings.cache_enabled:
            return None
        if cls._pool is None:
            try:
                safe_url = settings.redis_url.replace("https://", "rediss://").replace("http://", "redis://")
                if "://" not in safe_url:
                    safe_url = f"redis://{safe_url}"
                cls._pool = redis.from_url(safe_url)
            except Exception as e:
                logger.warning(f"Sync Redis connection failed: {e}")
                cls._pool = None
        return cls._pool

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        client = cls.get_client()
        if not client: return None
        try:
            data = client.get(key)
            if not data: return None
            try:
                return orjson.loads(zlib.decompress(data))
            except zlib.error:
                return orjson.loads(data)
        except Exception as e:
            logger.warning(f"Sync Cache GET error: {e}")
            return None

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 300) -> bool:
        client = cls.get_client()
        if not client: return False
        try:
            if hasattr(value, 'model_dump'):
                dumped = value.model_dump()
            else:
                dumped = value
            serialized = orjson.dumps(dumped)
            compressed = zlib.compress(serialized)
            client.setex(key, ttl, compressed)
            return True
        except Exception as e:
            logger.warning(f"Sync Cache SET error: {e}")
            return False

"""
Async caching decorators for FastAPI services.
"""

def cache(ttl: int = 300, key_builder: Optional[Callable[..., str]] = None, response_model: Optional[Type[Any]] = None):
    """
    Asynchronous caching decorator.
    
    Args:
        ttl: Time to live in seconds.
        key_builder: A function that generates the cache key from the arguments.
                     If None, a default hash of args/kwargs is used.
        response_model: Optional Pydantic model class to reconstruct the cached dictionary.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                # Default fallback key (not recommended for complex nested arguments)
                key = f"{func.__module__}.{func.__name__}:{hash(str(args) + str(kwargs))}"
                
            # Attempt to retrieve from cache
            cached_val = await CacheService.get(key)
            if cached_val is not None:
                # Reconstruct Pydantic model if specified
                if response_model and isinstance(cached_val, dict):
                    return response_model.model_validate(cached_val)
                elif response_model and isinstance(cached_val, list):
                    return [response_model.model_validate(item) for item in cached_val]
                return cached_val
                
            # Execute original function
            result = await func(*args, **kwargs)
            
            # Save to cache if result is not None
            if result is not None:
                await CacheService.set(key, result, ttl)
                
            return result
        return wrapper
    return decorator

"""
Cache key generators.
Provides standardized formatting for Redis keys.
"""

def market_quote_key(symbol: str) -> str:
    return f"market:quote:{symbol}"

def market_chart_key(symbol: str, period: str, interval: str) -> str:
    return f"market:chart:{symbol}:{period}:{interval}"

def market_profile_key(symbol: str) -> str:
    return f"market:profile:{symbol}"

def market_stats_key(symbol: str) -> str:
    return f"market:stats:{symbol}"

def llm_generation_key(model: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
    raw = f"{model}:{system_prompt}:{user_prompt}:{temperature}"
    hashed = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return f"llm:gen:{hashed}"

def rag_query_key(query: str, filters: str = "") -> str:
    raw = f"{query}:{filters}"
    hashed = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return f"rag:query:{hashed}"

"""
Async Redis connection management.
"""

logger = get_logger("finnai.cache.redis")
settings = Settings()

class RedisClient:
    _pool: Optional[aioredis.Redis] = None

    @classmethod
    async def get_client(cls) -> Optional[aioredis.Redis]:
        if not settings.cache_enabled:
            return None
            
        if cls._pool is None:
            try:
                safe_url = settings.redis_url.replace("https://", "rediss://").replace("http://", "redis://")
                if "://" not in safe_url:
                    safe_url = f"redis://{safe_url}"
                cls._pool = aioredis.from_url(
                    safe_url,
                    max_connections=settings.redis_max_connections,
                    decode_responses=False  # We want raw bytes for zlib compression
                )
                # Test connection
                await cls._pool.ping()
                logger.info("Successfully connected to Redis.")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Caching will be bypassed.")
                cls._pool = None
                
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.aclose()
            cls._pool = None
            logger.info("Redis connection closed.")
