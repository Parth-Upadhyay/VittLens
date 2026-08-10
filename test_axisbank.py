from yahooquery import Ticker
import json

t = Ticker("AXISBANK.NS")
print("KEY STATS:", json.dumps(t.key_stats, indent=2))
print("SUMMARY DETAIL:", json.dumps(t.summary_detail, indent=2))
print("FINANCIAL DATA:", json.dumps(t.financial_data, indent=2))
