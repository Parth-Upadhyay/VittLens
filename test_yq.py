import json
from yahooquery import Ticker
t = Ticker("INFY.NS")
with open("test_yq.json", "w", encoding="utf-8") as f:
    json.dump({
        "price": t.price,
        "summary_detail": t.summary_detail,
        "financial_data": getattr(t, 'financial_data', {})
    }, f, indent=4)
