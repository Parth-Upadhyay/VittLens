import pandas as pd
from yahooquery import Ticker
import json

yq = Ticker('BHARTIARTL.NS')

print('--- Fast Info Equivalents (Price/Stats/Summary) ---')
price = yq.price.get('BHARTIARTL.NS', {})
stats = yq.key_stats.get('BHARTIARTL.NS', {})
detail = yq.summary_detail.get('BHARTIARTL.NS', {})
fin_data = yq.financial_data.get('BHARTIARTL.NS', {})

print("Price:", json.dumps(price, indent=2))
print("Key Stats:", json.dumps(stats, indent=2))
print("Summary Detail:", json.dumps(detail, indent=2))

print('\n--- Balance Sheet Sample ---')
bs = yq.balance_sheet(frequency='a')
if isinstance(bs, pd.DataFrame) and not bs.empty:
    print(bs.columns.tolist())
    print(bs.head())
else:
    print('No Balance Sheet')

print('\n--- Income Statement Sample ---')
inc = yq.income_statement(frequency='a')
if isinstance(inc, pd.DataFrame) and not inc.empty:
    print(inc.columns.tolist())
    print(inc.head())
else:
    print('No Income Statement')
