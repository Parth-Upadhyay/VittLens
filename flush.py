import asyncio
from app.cache import RedisClient

async def flush():
    c = await RedisClient.get_client()
    if c:
        await c.flushdb()
        print('Flushed!')

if __name__ == '__main__':
    asyncio.run(flush())
