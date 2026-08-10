import pandas as pd
from yahooquery import Ticker

def _format_yq_statement(df):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    # Drop symbol index if it exists
    if isinstance(df.index, pd.MultiIndex):
        df = df.droplevel(0)
    elif df.index.name == 'symbol':
        df = df.reset_index(drop=True)
        
    if 'asOfDate' in df.columns:
        # Sort by date descending (newest first)
        df = df.sort_values('asOfDate', ascending=False)
        # Set asOfDate as the index
        df = df.set_index('asOfDate')
    
    # Transpose so metrics are rows, dates are columns
    return df.T

yq = Ticker('3MINDIA.NS')
inc = yq.income_statement(frequency="a")
fin = _format_yq_statement(inc)

print("Columns:", fin.columns)
print("Index:", fin.index[:5])
if 'TotalRevenue' in fin.index:
    print("TotalRevenue values:", fin.loc['TotalRevenue'].values)
