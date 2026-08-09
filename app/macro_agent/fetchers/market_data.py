import yfinance as yf
from typing import Dict, Any

def fetch_market_snapshot() -> Dict[str, Any]:
    """
    Fetches the latest market data for major indices and commodities.
    """
    tickers = {
        "Nifty": "^NSEI",
        "Sensex": "^BSESN",
        "S&P500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Dow Jones": "^DJI",
        "Gold": "GC=F",
        "Silver": "SI=F",
        "Crude Oil": "CL=F",
        "Natural Gas": "NG=F",
        "USD Index": "DX-Y.NYB",
        "USDINR": "INR=X",
        "10Y Treasury Yield": "^TNX",
        "VIX": "^VIX"
    }

    snapshot = {}
    try:
        # We can download them all at once to save time
        ticker_list = list(tickers.values())
        data = yf.download(ticker_list, period="1d", group_by="ticker", auto_adjust=True)
        
        for name, symbol in tickers.items():
            try:
                if len(ticker_list) == 1:
                    last_close = data['Close'].iloc[-1]
                else:
                    last_close = data[symbol]['Close'].iloc[-1]
                snapshot[name] = float(last_close)
            except Exception:
                snapshot[name] = None
                
    except Exception as e:
        # Fallback to individual if batch fails or to return empty dict
        pass

    return snapshot
