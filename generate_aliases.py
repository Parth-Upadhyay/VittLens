import json
import os
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

FILE_PATH = "config/nifty500_aliases.json"

def get_aliases(symbol):
    try:
        # Fetch data for Indian equities (.NS suffix)
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info
        aliases = set()
        
        # Keep the original lowercased symbol
        aliases.add(symbol.lower())
        
        long_name = info.get("longName")
        short_name = info.get("shortName")
        
        for name in [long_name, short_name]:
            if not name: 
                continue
            
            name = name.lower().strip()
            aliases.add(name)
            
            # Create cleaner aliases by removing common corporate suffixes
            suffixes = [
                " limited", " ltd.", " ltd", " corporation", 
                " inc.", " inc", " company", " co."
            ]
            
            for suffix in suffixes:
                if name.endswith(suffix):
                    clean_name = name[:-len(suffix)].strip()
                    # Also strip any trailing commas or spaces left over
                    clean_name = clean_name.rstrip(',').strip()
                    aliases.add(clean_name)
                    break # Stop stripping suffixes once one is removed
                    
        # Filter out extremely short or invalid aliases
        valid_aliases = [a for a in aliases if len(a) > 2]
        if not valid_aliases:
            valid_aliases = [symbol.lower()]
            
        return symbol, list(valid_aliases)
    except Exception as e:
        # Fallback to just the symbol if Yahoo Finance fails for this ticker
        return symbol, [symbol.lower()]

def main():
    if not os.path.exists(FILE_PATH):
        print(f"Error: {FILE_PATH} not found.")
        return

    with open(FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    symbols = list(data.keys())
    print(f"Fetching real corporate names for {len(symbols)} symbols from Yahoo Finance...")
    print("This will run concurrently using 20 threads. Please wait...\n")
    
    new_data = {}
    completed = 0
    total_aliases = 0
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(get_aliases, sym): sym for sym in symbols}
        
        for future in as_completed(futures):
            sym, aliases = future.result()
            new_data[sym] = sorted(aliases)
            total_aliases += len(aliases)
            completed += 1
            
            if completed % 50 == 0:
                print(f"Processed {completed}/{len(symbols)} companies...")
                
    # Sort the dictionary keys so the JSON is neat
    sorted_new_data = {k: new_data[k] for k in sorted(new_data)}
                
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted_new_data, f, indent=2)
        
    print(f"\nDone! Successfully updated '{FILE_PATH}'.")
    print(f"Generated {total_aliases} total aliases across {len(symbols)} canonical companies.")

if __name__ == "__main__":
    main()
