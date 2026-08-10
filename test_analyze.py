import requests
import json

files = {
    'file': ('portfolio.csv', 'symbol,quantity,avg_buy_price\nNIFTYBEES,35,280.85', 'text/csv')
}

response = requests.post('http://127.0.0.1:8000/api/v1/portfolio/analyze', files=files)
with open('output.json', 'w', encoding='utf-8') as f:
    json.dump(response.json(), f, indent=2)
print("Done")
