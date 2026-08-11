import httpx

def test_amfi():
    url = "https://portal.amfiindia.com/spages/NAVAll.txt"
    with httpx.Client() as client:
        resp = client.get(url)
    
    lines = resp.text.split("\n")[:30]
    for i, line in enumerate(lines):
        print(f"{i}: {line.strip()}")

if __name__ == "__main__":
    test_amfi()
