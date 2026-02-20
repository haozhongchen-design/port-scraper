import pandas as pd
import requests
import os
import io # Added for StringIO
from datetime import datetime
import pytz

# CONFIG: Target - Port of Callao (PECLL)
NYC = pytz.timezone('America/New_York')
DATA_DIR = "."
MASTER_FILE = os.path.join(DATA_DIR, "callao_master_data.csv")
TARGET_URL = "https://www.apmterminals.com/track-and-trace/vessel-schedule?terminal=PECLL" 

# DISPLACEMENT ESTIMATION VARIABLES
TONS_PER_HOUR = 1200.0
MOORING_OVERHEAD = 4.0

def calculate_displacement(row, now):
    try:
        arrival_col = next((c for c in row.index if 'Arrival' in str(c)), None)
        status_col = next((c for c in row.index if 'Status' in str(c)), None)
        departure_col = next((c for c in row.index if 'Departure' in str(c)), None)

        if not arrival_col: return 0.0, 0.0

        arrived = pd.to_datetime(row[arrival_col])
        if arrived.tzinfo is not None: arrived = arrived.tz_convert(None)
        
        status = str(row.get(status_col, '')).upper()
        
        if pd.notna(row.get(departure_col)) and "DEPARTED" in status:
            departed = pd.to_datetime(row[departure_col])
            if departed.tzinfo is not None: departed = departed.tz_convert(None)
            stay_seconds = (departed - arrived).total_seconds()
        elif "AT BERTH" in status or "ARRIVED" in status:
            stay_seconds = (now - arrived).total_seconds()
        else:
            stay_seconds = 0
            
        stay_hours = round(max(0, stay_seconds / 3600.0), 2)
        active_loading = max(0, stay_hours - MOORING_OVERHEAD)
        return stay_hours, round(active_loading * TONS_PER_HOUR, 2)
    except:
        return 0.0, 0.0

def run_sentinel():
    now_nyc = datetime.now(NYC).replace(tzinfo=None)
    timestamp = now_nyc.strftime('%Y-%m-%d %H:%M:%S')
    print(f"--- M5 SENTINEL GRIND: {timestamp} ---")

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(TARGET_URL, headers=headers, timeout=15)
        
        # FIXED: Wrap r.text in StringIO to satisfy the FutureWarning
        tables = pd.read_html(io.StringIO(r.text))
        
        if not tables:
            print(f"[{timestamp}] CRITICAL: No HTML tables detected.")
            return
            
        df = tables[0]
        berth_col = next((c for c in df.columns if 'Berth' in str(c)), None)
        
        if not berth_col:
            m5_vessels = df.copy() 
        else:
            m5_vessels = df[df[berth_col].astype(str).str.contains('M5', na=False)].copy()
        
        if m5_vessels.empty:
            print(f"[{timestamp}] No active vessels at M5.")
            return

        m5_vessels[['Stay_Hours', 'Est_Tonnage_Loaded']] = m5_vessels.apply(
            lambda x: pd.Series(calculate_displacement(x, now_nyc)), axis=1
        )
        m5_vessels['Scrape_Time'] = timestamp
        
        file_exists = os.path.isfile(MASTER_FILE)
        m5_vessels.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
        print(f"[{timestamp}] Callao Success: {len(m5_vessels)} logged.")

    except Exception as e:
        print(f"[{timestamp}] System Error: {str(e)}")

if __name__ == "__main__":
    run_sentinel()
