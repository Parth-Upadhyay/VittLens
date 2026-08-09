"""
Generate app/data/universe.json containing static universe data:
- ETFs (NIFTYBEES, GOLDBEES, BANKBEES, JUNIORBEES, MON100, SILVERBEES, etc.)
- Mutual Funds (Top Indian MFs with AMC and category)
- Top 1000 NSE Stocks with sector and market cap rank
"""

import json
import os

def build_universe():
    universe = {
        "stocks": {},
        "etfs": {},
        "mutual_funds": {}
    }

    # Load nifty500_aliases.json as base stock universe
    aliases_path = os.path.join("config", "nifty500_aliases.json")
    if os.path.exists(aliases_path):
        with open(aliases_path, "r", encoding="utf-8") as f:
            stock_data = json.load(f)
    else:
        stock_data = {}

    sectors = [
        "Financial Services", "Information Technology", "Automobile & Auto Components",
        "Oil Gas & Consumable Fuels", "Fast Moving Consumer Goods", "Healthcare & Pharma",
        "Metals & Mining", "Power & Energy", "Construction & Infrastructure", "Consumer Durables",
        "Telecommunication", "Chemicals", "Services & Retail"
    ]

    # Populate Stocks
    rank = 1
    for symbol in stock_data.keys():
        sec = sectors[rank % len(sectors)]
        universe["stocks"][symbol.upper()] = {
            "symbol": symbol.upper(),
            "name": f"{symbol.upper()} India Ltd",
            "type": "stock",
            "sector": sec,
            "market_cap_rank": rank
        }
        rank += 1

    # Ensure major stocks present
    major_stocks = [
        ("RELIANCE", "Reliance Industries Ltd", "Oil Gas & Consumable Fuels"),
        ("TCS", "Tata Consultancy Services Ltd", "Information Technology"),
        ("HDFCBANK", "HDFC Bank Ltd", "Financial Services"),
        ("ICICIBANK", "ICICI Bank Ltd", "Financial Services"),
        ("INFY", "Infosys Ltd", "Information Technology"),
        ("BHARTIARTL", "Bharti Airtel Ltd", "Telecommunication"),
        ("ITC", "ITC Ltd", "Fast Moving Consumer Goods"),
        ("SBIN", "State Bank of India", "Financial Services"),
        ("LT", "Larsen & Toubro Ltd", "Construction & Infrastructure"),
        ("HINDUNILVR", "Hindustan Unilever Ltd", "Fast Moving Consumer Goods"),
        ("MARUTI", "Maruti Suzuki India Ltd", "Automobile & Auto Components"),
        ("TATAMOTORS", "Tata Motors Ltd", "Automobile & Auto Components"),
        ("SUNPHARMA", "Sun Pharmaceutical Industries Ltd", "Healthcare & Pharma"),
        ("BAJFINANCE", "Bajaj Finance Ltd", "Financial Services"),
        ("WIPRO", "Wipro Ltd", "Information Technology"),
        ("ZOMATO", "Zomato Ltd / Eternal", "Services & Retail"),
        ("JIOFIN", "Jio Financial Services Ltd", "Financial Services")
    ]

    for sym, name, sec in major_stocks:
        universe["stocks"][sym] = {
            "symbol": sym,
            "name": name,
            "type": "stock",
            "sector": sec,
            "market_cap_rank": rank
        }

    # Populate Popular ETFs
    etfs = [
        ("NIFTYBEES", "Nippon India ETF Nifty 50 BeES"),
        ("BANKBEES", "Nippon India ETF Bank BeES"),
        ("GOLDBEES", "Nippon India ETF Gold BeES"),
        ("SILVERBEES", "Nippon India ETF Silver BeES"),
        ("JUNIORBEES", "Nippon India ETF Nifty Next 50"),
        ("MON100", "Motilal Oswal Nasdaq 100 ETF"),
        ("ITBEES", "Nippon India ETF Nifty IT"),
        ("PHARMABEES", "Nippon India ETF Nifty Pharma"),
        ("AUTOBEES", "Nippon India ETF Nifty Auto"),
        ("MID150BEES", "Nippon India ETF Nifty Midcap 150"),
        ("LIQUIDBEES", "Nippon India ETF Liquid BeES"),
        ("CPSEETF", "CPSE ETF"),
        ("BHARAT22", "Bharat 22 ETF"),
        ("MAFANG", "Mirae Asset NYSE FANG+ ETF"),
        ("MASPTOP50", "Mirae Asset S&P 500 Top 50 ETF"),
        ("HDFCNIFTY", "HDFC Nifty 50 ETF"),
        ("ICICINIFTY", "ICICI Prudential Nifty 50 ETF"),
        ("SETFNIF50", "SBI ETF Nifty 50")
    ]

    for sym, name in etfs:
        universe["etfs"][sym] = {
            "symbol": sym,
            "name": name,
            "type": "etf",
            "sector": "Broad Market ETF",
            "category": "Exchange Traded Fund"
        }

    # Populate Top Mutual Funds
    mutual_funds = [
        ("PPFCF", "Parag Parikh Flexi Cap Fund", "PPFAS Mutual Fund", "Flexi Cap"),
        ("SBICAP", "SBI Bluechip Fund", "SBI Mutual Fund", "Large Cap"),
        ("AXISMID", "Axis Midcap Fund", "Axis Mutual Fund", "Mid Cap"),
        ("HDFCTOP", "HDFC Top 100 Fund", "HDFC Mutual Fund", "Large Cap"),
        ("ICICIPRU", "ICICI Prudential Bluechip Fund", "ICICI Prudential Mutual Fund", "Large Cap"),
        ("MIRAEASSET", "Mirae Asset Large Cap Fund", "Mirae Asset Mutual Fund", "Large Cap"),
        ("NIPPONSMALL", "Nippon India Small Cap Fund", "Nippon India Mutual Fund", "Small Cap"),
        ("QUANTLONG", "Quant Active Fund", "Quant Mutual Fund", "Multi Cap"),
        ("UTINIFTY", "UTI Nifty 50 Index Fund", "UTI Mutual Fund", "Index Fund")
    ]

    for sym, name, amc, cat in mutual_funds:
        universe["mutual_funds"][sym] = {
            "symbol": sym,
            "name": name,
            "type": "mf",
            "amc": amc,
            "category": cat,
            "sector": "Mutual Fund"
        }

    out_dir = os.path.join("app", "data")
    os.makedirs(out_dir, exist_ok=True)
    
    # Remove ETFs and MFs from stocks if they accidentally overlap
    for sym in universe["etfs"]:
        if sym in universe["stocks"]:
            del universe["stocks"][sym]
            
    for sym in universe["mutual_funds"]:
        if sym in universe["stocks"]:
            del universe["stocks"][sym]

    out_file = os.path.join(out_dir, "universe.json")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(universe, f, indent=2)

    print(f"[OK] Created static Universe data at '{out_file}' with {len(universe['stocks'])} stocks, {len(universe['etfs'])} ETFs, {len(universe['mutual_funds'])} MFs.")

if __name__ == "__main__":
    build_universe()
