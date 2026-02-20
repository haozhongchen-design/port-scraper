import pandas as pd
import os
from datetime import datetime
import pytz

# CONFIG: Target - Port of Callao (PECLL)
NYC = pytz.timezone('America/New_York')
DATA_DIR = "."
MASTER_FILE = os.path.join(DATA_DIR, "callao_master_data.csv")
DAILY_EXPORT = "Vessel-Schedule.csv" 

# DISPLACEMENT ESTIMATION VARIABLES
TONS_PER_HOUR = 1200.0  # Estimated loading rate for mineral concentrates
MOORING_OVERHEAD = 4.0  # Hours lost to docking, customs, and undocking

def calculate_displacement(row, now):
    date_format = "%m/%d/%Y - %I:%M %p"
    
    try:
        arrived = datetime.strptime(str(row['Arrival time']).strip(), date_format)
    except Exception:
        return 0.0, 0.0 
        
    if pd.notna(row['Departure time']) and "DEPARTED" in str(row['Status']).upper():
        try:
            departed = datetime.strptime(str(row['Departure time']).strip(), date_format)
            stay_seconds = (departed - arrived).total_seconds()
        except Exception:
            stay_seconds = 0
    elif "AT BERTH" in str(row['Status']).upper():
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

    try:
        # Load the raw maritime manifest
        df = pd.read_csv(DAILY_EXPORT)
        
        # Isolate M5 Industrial Berths Only
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

    except FileNotFoundError:
        # Safety catch if the user hasn't uploaded the CSV
        print(f"[{timestamp}] CRITICAL: {DAILY_EXPORT} not found. Awaiting raw data manifest.")
    except Exception as e:
        print(f"[{timestamp}] System Error: {str(e)}")

if __name__ == "__main__":
    run_sentinel()
