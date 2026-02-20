import pandas as pd
import requests
import os
from datetime import datetime
import pytz

# CONFIG: Target - Port of Callao (PECLL)
NYC = pytz.timezone('America/New_York')
DATA_DIR = "."
MASTER_FILE = os.path.join(DATA_DIR, "callao_master_data.csv")

# Replace this with the exact URL of the webpage displaying the schedule
TARGET_URL = "https://www.apmterminals.com/track-and-trace/vessel-schedule?terminal=PECLL" 

# DISPLACEMENT ESTIMATION VARIABLES
TONS_PER_HOUR = 1200.0  # Estimated loading rate for mineral concentrates
MOORING_OVERHEAD = 4.0  # Hours lost to docking, customs, and undocking

def calculate_displacement(row, now):
    date_format = "%m/%d/%Y - %I:%M %p"
    
    try:
        arrived = datetime.strptime(str(row['Arrival time']).strip(), date_format)
    except Exception:
        return 0.0, 0.0 
        
    if pd.notna(row.get('Departure time')) and "DEPARTED" in str(row.get('Status', '')).upper():
        try:
            departed = datetime.strptime(str(row['Departure time']).strip(), date_format)
            stay_seconds = (departed - arrived).total_seconds()
        except Exception:
            stay_seconds = 0
    elif "AT BERTH" in str(row.get('Status', '')).upper():
        stay_seconds = (now - arrived).total_seconds()
    else:
        stay_seconds = 0
        
    stay_hours = round(max(0, stay_seconds / 3600.0), 2)
    
    active_loading = max(0, stay_hours - MOORING_OVERHEAD)
    est_tonnage = active_loading * TONS_PER_HOUR
    
    return stay_hours, round(est_tonnage, 2)

def run_sentinel():
    now_nyc = datetime.now(NYC).replace(tzinfo=None)
    timestamp = now_nyc.strftime('%Y-%m-%d %H:%M:%S')

    print(f"--- M5 SENTINEL GRIND: {timestamp} ---")

    try:
        # 1. Fetch the raw HTML of the webpage directly
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        r = requests.get(TARGET_URL, headers=headers, timeout=15)
        
        # 2. Extract all HTML tables from the page into DataFrames
        tables = pd.read_html(r.text)
        
        if not tables:
            print(f"[{timestamp}] CRITICAL: No HTML tables detected on the target page.")
            return
            
        # 3. Target the primary table on the page (usually index 0)
        df = tables[0]
        
        # Isolate M5 Industrial Berths Only
        if 'Berth' not in df.columns:
            print(f"[{timestamp}] ALERT: 'Berth' column missing. Target table layout may have changed.")
            return
            
        m5_vessels = df[df['Berth'].isin(['M5A', 'M5D'])].copy()
        
        if m5_vessels.empty:
            print(f"[{timestamp}] No active vessels at M5 mineral berths.")
            return

        # Calculate Displacement
        m5_vessels[['Stay_Hours', 'Est_Tonnage_Loaded']] = m5_vessels.apply(
            lambda x: pd.Series(calculate_displacement(x, now_nyc)), axis=1
        )
        
        m5_vessels['Scrape_Time'] = timestamp
        m5_vessels['Priority'] = 'HIGH'
        
        # Save to master tracking file
        file_exists = os.path.isfile(MASTER_FILE)
        m5_vessels.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
        
        print(f"[{timestamp}] Callao Success: {len(m5_vessels)} mineral vessels processed.")

    except Exception as e:
        print(f"[{timestamp}] System Error: {str(e)}")

if __name__ == "__main__":
    run_sentinel()
