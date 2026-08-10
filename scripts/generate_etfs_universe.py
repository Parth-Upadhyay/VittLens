import json
import os

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "data", "universe.json")

def load_universe():
    if os.path.exists(UNIVERSE_PATH):
        with open(UNIVERSE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"stocks": {}, "etfs": {}, "mutual_funds": {}}

def save_universe(data):
    with open(UNIVERSE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def main():
    universe = load_universe()
    if "etfs" not in universe:
        universe["etfs"] = {}
    if "mutual_funds" not in universe:
        universe["mutual_funds"] = {}
        
    print(f"Loaded existing universe. Current ETFs: {len(universe['etfs'])}, MFs: {len(universe['mutual_funds'])}")

    # Add Popular ETFs
    popular_etfs = [
        # Broad Market ETFs
        ("NIFTYBEES", "Nippon India Nifty 50 ETF", "Broad Market ETF"),
        ("JUNIORBEES", "Nippon India Nifty Next 50 ETF", "Broad Market ETF"),
        ("BANKBEES", "Nippon India Nifty Bank ETF", "Sectoral ETF (Banking)"),
        ("MID150BEES", "Nippon India Nifty Midcap 150 ETF", "Broad Market ETF"),
        ("NIFTYIETF", "ICICI Prudential Nifty 50 ETF", "Broad Market ETF"),
        ("SETFNIF50", "SBI Nifty 50 ETF", "Broad Market ETF"),
        ("SETFNIFBK", "SBI Nifty Bank ETF", "Sectoral ETF (Banking)"),
        ("ICICINIFTY", "ICICI Prudential Nifty 50 ETF", "Broad Market ETF"),
        ("KOTAKNIFTY", "Kotak Nifty 50 ETF", "Broad Market ETF"),
        ("UTINIFTETF", "UTI Nifty 50 ETF", "Broad Market ETF"),
        ("HDFCNIFTY", "HDFC Nifty 50 ETF", "Broad Market ETF"),
        ("MON100", "Motilal Oswal Nasdaq 100 ETF", "International ETF"),
        ("MAFANG", "Mirae Asset NYSE FANG+ ETF", "International ETF"),
        ("MOMOMENTUM", "Motilal Oswal Nifty 200 Momentum 30 ETF", "Smart Beta ETF"),
        ("KOTAKBKETF", "Kotak Nifty Bank ETF", "Sectoral ETF (Banking)"),
        
        # Sectoral / Thematic ETFs
        ("ITBEES", "Nippon India Nifty IT ETF", "Sectoral ETF (IT)"),
        ("CPSEETF", "CPSE ETF", "Thematic ETF (PSU)"),
        ("PHARMABEES", "Nippon India Nifty Pharma ETF", "Sectoral ETF (Pharma)"),
        ("CONSUMBEES", "Nippon India Nifty Consumption ETF", "Sectoral ETF (Consumption)"),
        ("INFRAETF", "ICICI Prudential Nifty Infrastructure ETF", "Thematic ETF (Infra)"),
        ("PSUBNKBEES", "Nippon India Nifty PSU Bank ETF", "Sectoral ETF (PSU Bank)"),
        ("PVTBANIETF", "ICICI Prudential Nifty Private Bank ETF", "Sectoral ETF (Private Bank)"),
        ("AUTOBEES", "Nippon India Nifty Auto ETF", "Sectoral ETF (Auto)"),
        ("FMCGIETF", "ICICI Prudential Nifty FMCG ETF", "Sectoral ETF (FMCG)"),
        ("HEALTHY", "ICICI Prudential Nifty Healthcare ETF", "Sectoral ETF (Healthcare)"),
        ("MAKEINDIA", "Nippon India Nifty India Manufacturing ETF", "Thematic ETF (Manufacturing)"),
        ("COMMODIES", "ICICI Prudential Nifty Commodities ETF", "Thematic ETF (Commodities)"),
        ("INFRABEES", "Nippon India Nifty Infrastructure ETF", "Thematic ETF (Infra)"),
        ("DIVOPPBEES", "Nippon India Nifty Dividend Opportunities 50 ETF", "Smart Beta ETF"),
        
        # Smart Beta / Factor ETFs
        ("NV20IETF", "ICICI Prudential Nifty50 Value 20 ETF", "Smart Beta ETF (Value)"),
        ("LOWVOLIETF", "ICICI Prudential Nifty100 Low Volatility 30 ETF", "Smart Beta ETF (Low Volatility)"),
        ("ALPHAETF", "ICICI Prudential Nifty Alpha 50 ETF", "Smart Beta ETF (Alpha)"),
        
        # Commodities (Gold & Silver)
        ("GOLDBEES", "Nippon India ETF Gold BeES", "Commodity ETF (Gold)"),
        ("GOLDIETF", "ICICI Prudential Gold ETF", "Commodity ETF (Gold)"),
        ("SETFGOLD", "SBI Gold ETF", "Commodity ETF (Gold)"),
        ("HDFCGOLD", "HDFC Gold ETF", "Commodity ETF (Gold)"),
        ("KOTAKGOLD", "Kotak Gold ETF", "Commodity ETF (Gold)"),
        ("AXISGOLD", "Axis Gold ETF", "Commodity ETF (Gold)"),
        ("SILVERBEES", "Nippon India Silver ETF", "Commodity ETF (Silver)"),
        ("SILVERIETF", "ICICI Prudential Silver ETF", "Commodity ETF (Silver)"),
        ("SETFSILVER", "SBI Silver ETF", "Commodity ETF (Silver)"),
        
        # Debt / Liquid ETFs
        ("LIQUIDBEES", "Nippon India ETF Liquid BeES", "Liquid ETF"),
        ("LIQUIDIETF", "ICICI Prudential Liquid ETF", "Liquid ETF"),
        ("SETFLIQUID", "SBI Liquid ETF", "Liquid ETF"),
        ("GSEC10YEAR", "Nippon India ETF Nifty 10 yr Benchmark G-Sec", "Debt ETF (G-Sec)"),
        ("GSEC5IETF", "ICICI Prudential Nifty 5 yr Benchmark G-SEC ETF", "Debt ETF (G-Sec)"),
        ("BBETF0423", "Bharat Bond ETF - April 2023", "Debt ETF (Corporate Bond)"),
        ("BBETF0430", "Bharat Bond ETF - April 2030", "Debt ETF (Corporate Bond)"),
        ("SDL24BGETF", "Aditya Birla Sun Life Nifty SDL Sep 2024 ETF", "Debt ETF (SDL)"),
    ]

    for symbol, name, sector in popular_etfs:
        universe["etfs"][symbol] = {
            "symbol": symbol,
            "name": name,
            "type": "etf",
            "sector": sector,
            "market_cap_rank": 0
        }

    # Add Popular Mutual Funds
    popular_mfs = [
        ("PPFAS", "Parag Parikh Flexi Cap Fund", "Flexi Cap Fund"),
        ("HDFCSMALLCAP", "HDFC Small Cap Fund", "Small Cap Fund"),
        ("SBIBLUECHIP", "SBI Bluechip Fund", "Large Cap Fund"),
        ("ICICIPRUVALUE", "ICICI Prudential Value Discovery Fund", "Value Fund"),
        ("AXISLONGTERM", "Axis Long Term Equity Fund", "ELSS (Tax Saver)"),
        ("MIRAEASSETELSS", "Mirae Asset Tax Saver Fund", "ELSS (Tax Saver)"),
        ("NIPPONSMALLCAP", "Nippon India Small Cap Fund", "Small Cap Fund"),
        ("KOTAKEMERGING", "Kotak Emerging Equity Fund", "Mid Cap Fund"),
        ("DSPMIDCAP", "DSP Midcap Fund", "Mid Cap Fund"),
        ("UTIFLEXICAP", "UTI Flexi Cap Fund", "Flexi Cap Fund"),
        ("SBISUPER", "SBI Magnum Midcap Fund", "Mid Cap Fund"),
        ("HDFCMIDCAP", "HDFC Mid-Cap Opportunities Fund", "Mid Cap Fund"),
        ("ICICIPRUTECH", "ICICI Prudential Technology Fund", "Sectoral Fund (IT)"),
        ("TATAETHICAL", "Tata Ethical Fund", "Thematic Fund (Ethical)"),
        ("SBIHEALTHCARE", "SBI Healthcare Opportunities Fund", "Sectoral Fund (Healthcare)"),
    ]

    for symbol, name, sector in popular_mfs:
        universe["mutual_funds"][symbol] = {
            "symbol": symbol,
            "name": name,
            "type": "mutual_fund",
            "sector": sector,
            "market_cap_rank": 0
        }

    save_universe(universe)
    print(f"Updated universe JSON! Now containing {len(universe['etfs'])} ETFs and {len(universe['mutual_funds'])} Mutual Funds.")

if __name__ == "__main__":
    main()
