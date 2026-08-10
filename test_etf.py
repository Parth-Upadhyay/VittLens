import asyncio
from app.services.market_service import MarketService
from app.config.settings import Settings

async def main():
    ms = MarketService(Settings())
    try:
        quote = await ms.get_stock_quote('NIFTYBEES')
        print("Quote Price:", quote.price)
    except Exception as e:
        print("Error fetching quote:", e)
    await ms.close()

if __name__ == "__main__":
    asyncio.run(main())
