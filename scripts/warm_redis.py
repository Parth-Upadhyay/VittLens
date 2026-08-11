import sys
import os
import json
import time
import random
import asyncio
from tqdm import tqdm

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.endpoints.market import get_deep_analyze_metrics
from app.services.market_service import MarketService
from app.utils import get_logger

logger = get_logger("finnai.scripts.warm_redis")

ETFS = [
    "NIFTYBEES.NS", "BANKBEES.NS", "ITBEES.NS", "JUNIORBEES.NS", "GOLDBEES.NS",
    "LIQUIDBEES.NS", "PHARMABEES.NS", "AUTOBEES.NS", "INFRABEES.NS", "PSUBNKBEES.NS",
    "MID150BEES.NS", "SETFNIF50.NS", "SETFNIFBK.NS", "SETFNN50.NS", "NIFTYIETF.NS",
    "NEXT50IETF.NS", "HDFCNIFTY.NS", "HDFCNIFBAN.NS", "NIFTYETF.NS", "MIDCAPETF.NS",
    "NEXT50.NS", "ITETF.NS", "NIFTY1.NS", "IT.NS", "PSUBANK.NS", "CPSEETF.NS",
    "BSLNIFTY.NS", "HNGSNGBEES.NS", "MAHKTECH.NS", "MON100.NS", "MAFANG.NS",
    "MOM100.NS", "MOM50.NS", "MOINFRA.NS", "MOHEALTH.NS", "MOFSL-NIFTY500.NS",
    "SILVERBEES.NS", "SILVERIETF.NS", "HDFCSILVER.NS", "SILVERETF.NS", "GOLDETF.NS",
    "HDFCGOLD.NS", "ICICIGOLD.NS", "KOTAKGOLD.NS", "AXISGOLD.NS", "AXISNIFTY.NS",
    "AXISBNKETF.NS", "AXISTECETF.NS", "AXISNIFTYETF.NS", "ICICINIFTY.NS", "ICICIB22.NS",
    "ICICIM150.NS", "ICICINXT50.NS", "ICICIPHARM.NS", "ICICIAUTO.NS", "ICICIBANKN.NS",
    "ICICITECH.NS", "HDFCNEXT50.NS", "HDFCMID150.NS", "HDFCNIFTY100.NS", "HDFCNIFIT.NS",
    "HDFCPVTBAN.NS", "HDFCNIF100.NS", "SBIETFQLTY.NS", "SBIETFCON.NS", "SBIETF50.NS",
    "SBIETFPB.NS", "SBIETFP.NS", "SBIETFGILT.NS", "SBIETFGILT5.NS", "SBIETF10GILT.NS",
    "KOTAKNIFTY.NS", "KOTAKNEXT50.NS", "KOTAKMID50.NS", "KOTAKNV20.NS", "KOTAKALPHA.NS",
    "KOTAKIT.NS", "KOTAKPSUBK.NS", "KOTAKINFRA.NS", "UTI-NIFTYETF.NS", "UTINEXT50.NS",
    "UTIBANKETF.NS", "UTISENSETF.NS", "UTINIFTYETF.NS", "DSPN50ETF.NS", "DSPBANKETF.NS",
    "DSPITETF.NS", "DSPNIF100.NS", "BANDHANBNK.NS", "EQUAL50.NS", "MONQ50.NS",
    "MOMENTUM50.NS", "LOWVOL1.NS", "MOM30.NS", "QUALITY30.NS", "VALUE30.NS",
    "DIVOPPBEES.NS", "MNC.NS", "ESG.NS"
]

async def main():
    print("="*60)
    print(" FinnAI Redis Pre-Warming Script")
    print("="*60)
    print(f"Loaded {len(ETFS)} Indian ETFs.")
    
    # Load Nifty500
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "nifty500_aliases.json")
    try:
        with open(config_path, "r") as f:
            nifty = json.load(f)
            nifty_symbols = [n.get("canonical_symbol") for n in nifty]
            nifty_symbols = [s for s in nifty_symbols if s]
            print(f"Loaded {len(nifty_symbols)} Nifty 500 stocks.")
    except Exception as e:
        print(f"Failed to load Nifty 500 config: {e}")
        nifty_symbols = []
        
    print("\nNote: Mutual Funds require ISIN or specific Yahoo Finance (.BO/.NS) tickers to be fetched.")
    print("Please map your Mutual Fund names to yfinance tickers and add them to the ETFS list in this script to include them in the warming process.\n")
    
    all_symbols = list(set(nifty_symbols + ETFS))
    print(f"Total unique symbols to warm: {len(all_symbols)}")
    print("Starting pre-warming process. This will take some time due to rate-limit sleeps.")
    print("Press Ctrl+C to stop at any time.")
    
    market_service = MarketService()
    
    success = 0
    failed = 0
    
    for symbol in tqdm(all_symbols, desc="Warming Redis"):
        try:
            await get_deep_analyze_metrics(symbol, market_service)
            success += 1
        except Exception as e:
            logger.error(f"Failed to warm {symbol}: {e}")
            failed += 1
            
        # Sleep for a random interval between 1.5 and 3.5 seconds to avoid IP bans from Yahoo
        await asyncio.sleep(random.uniform(1.5, 3.5))

    print("="*60)
    print(f"Pre-warming complete!")
    print(f"Successfully warmed: {success}")
    print(f"Failed: {failed}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
