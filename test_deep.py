import asyncio
from app.api.v1.endpoints.market import get_deep_analyze
from app.services.market_service import MarketService
import json

async def main():
    service = MarketService()
    try:
        res = await get_deep_analyze("INFY", service)
        print(json.dumps(res["metrics"], indent=2))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
