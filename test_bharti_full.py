import pandas as pd
from yahooquery import Ticker
import json

# Remove pandas display limits
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

yq = Ticker('BHARTIARTL.NS')

output = []
output.append('=== PRICE INFO ===')
output.append(json.dumps(yq.price.get('BHARTIARTL.NS', {}), indent=2))

output.append('\n=== KEY STATS ===')
output.append(json.dumps(yq.key_stats.get('BHARTIARTL.NS', {}), indent=2))

output.append('\n=== SUMMARY DETAIL ===')
output.append(json.dumps(yq.summary_detail.get('BHARTIARTL.NS', {}), indent=2))

output.append('\n=== BALANCE SHEET ===')
bs = yq.balance_sheet(frequency='a')
if isinstance(bs, pd.DataFrame) and not bs.empty:
    output.append(bs.to_string())
else:
    output.append('No Balance Sheet')

output.append('\n=== INCOME STATEMENT ===')
inc = yq.income_statement(frequency='a')
if isinstance(inc, pd.DataFrame) and not inc.empty:
    output.append(inc.to_string())
else:
    output.append('No Income Statement')

with open('bharti_complete_output.md', 'w') as f:
    f.write('\n'.join(output))

