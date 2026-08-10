import asyncio
from app.repositories import MarketRepository

async def main():
    repo = MarketRepository()
    try:
        df_fin = await repo.get_financials('3MINDIA.NS')
        print('Finance:', type(df_fin), not df_fin.empty if hasattr(df_fin, 'empty') else df_fin)
    except Exception as e:
        print('Finance Error:', e)

    try:
        df_bs = await repo.get_balance_sheet('3MINDIA.NS')
        print('BS:', type(df_bs), not df_bs.empty if hasattr(df_bs, 'empty') else df_bs)
    except Exception as e:
        print('BS Error:', e)
        
    try:
        info = await repo.get_company_info('3MINDIA.NS')
        print('Info keys:', info.keys() if info else None)
    except Exception as e:
        print('Info Error:', e)

asyncio.run(main())
