import asyncio
import json
from app.services.market_service import MarketService
from app.config.settings import Settings

async def main():
    ms = MarketService(Settings())
    res = await ms.get_stock_quote('TCS')
    print("TCS Market Cap:", res.market_cap)
    print("TCS Price:", res.price)
    
    infy = await ms.get_stock_quote('INFY')
    print("INFY Market Cap:", infy.market_cap)
    print("INFY Price:", infy.price)
    
    await ms.close()

if __name__ == "__main__":
    asyncio.run(main())
