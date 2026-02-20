import pandas as pd
import requests
import os
from datetime import datetime
import pytz

# CONFIG: PECLL (Callao) Node
NYC = pytz.timezone('America/New_York')
MASTER_FILE = "callao_master_data.csv"
API_URL = "https://api.apmterminals.com/tt-vessel-schedules?terminal=PECLL"

def run_sentinel():
    now_nyc = datetime.now(NYC).replace(tzinfo=None)
    ts = now_nyc.strftime('%Y-%m-%d %H:%M:%S')
    print(f"--- M5 DIRECT API GHOST INJECTION: {ts} ---")

    # These headers are the "Keys" to the Access Denied lock
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.apmterminals.com',
        'Referer': 'https://www.apmterminals.com/',
        'Connection': 'keep-alive'
    }

    try:
        # We use a session to handle potential cookie requirements automatically
        session = requests.Session()
        r = session.get(API_URL, headers=headers, timeout=15)
        
        if r.status_code != 200:
            print(f"FAILED: Status {r.status_code}")
            print(f"Server Message: {r.text[:200]}") # Diagnostics
            return

        data = r.json()
        
        # API check: If it's a list, we go. If it's a dict, we hunt for the key.
        items = data if isinstance(data, list) else data.get('vessels', [])
        
        if not items:
            print("API Success, but no vessel data in payload.")
            return

        df = pd.DataFrame(items)

        # Hunt for the 'berth' column (it's likely 'berth' or 'berthCode' in JSON)
        berth_col = next((c for c in df.columns if 'berth' in c.lower()), None)
        
        if not berth_col:
            print(f"Structure Error. Keys: {list(df.columns)}")
            return

        # Filter for Muelle 5 (A and D)
        m5 = df[df[berth_col].astype(str).str.contains('M5', case=False, na=False)].copy()

        if m5.empty:
            print("M5 is currently clear. No industrial activity detected.")
            # We still save an empty heartbeat to show the scraper is alive
            return

        # Add metadata and save
        m5['Timestamp_EST'] = ts
        file_exists = os.path.isfile(MASTER_FILE)
        m5.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
        
        print(f"ALPHA SECURED: {len(m5)} vessel(s) logged at M5.")

    except Exception as e:
        print(f"CRITICAL SYSTEM ERROR: {str(e)}")

if __name__ == "__main__":
    run_sentinel()
