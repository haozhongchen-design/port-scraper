import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import csv
import os

# --- 1. THE CONFIGURATION HUB ---
# To add a new port, simply add its name and URL here.
TARGET_PORTS = {
    "Callao": "https://www.searates.com/es/port/callao_pe/port-schedule",
    "Angamos": "https://www.searates.com/es/port/puerto_angamos_cl/port-schedule"
}

NYC = pytz.timezone('America/New_York')
DATA_DIR = "data"

def run_processor():
    now_nyc = datetime.now(NYC)
    time_est = now_nyc.strftime('%Y-%m-%d %H:%M:%S') 
    
    print(f"--- PROCESSOR START: {time_est} ---")

    # Ensure the data folder exists
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    headers = {'User-Agent': 'Mozilla/5.0'}

    # --- 2. THE AGGREGATOR LOOP ---
    for port_name, url in TARGET_PORTS.items():
        print(f"Targeting Node: {port_name}...")
        
        try:
            r = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            rows = soup.find_all('tr')
            bulk_carriers = []
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    vessel_name = cols[0].text.strip()
                    vessel_type = cols[1].text.strip().lower()
                    
                    # Target ONLY the ships carrying raw ore/metal
                    if "bulk" in vessel_type or "ore" in vessel_type:
                        eta = cols[2].text.strip()
                        etd = cols[3].text.strip()
                        bulk_carriers.append({
                            "name": vessel_name,
                            "eta": eta,
                            "etd": etd
                        })

            if not bulk_carriers:
                print(f"[{port_name}] No bulk carriers found.")
                continue

            # --- 3. DYNAMIC CSV GENERATION ---
            filename = os.path.join(DATA_DIR, f"{port_name.lower()}_export_data.csv")
            
            with open(filename, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Time_EST", "Vessel_Name", "ETA", "ETD"])
                for ship in bulk_carriers:
                    writer.writerow([time_est, ship['name'], ship['eta'], ship['etd']])
                
            print(f"SUCCESS: {port_name} - {len(bulk_carriers)} vessels logged.")

        except Exception as e:
            print(f"SYSTEM ERROR on {port_name}: {e}")

if __name__ == "__main__":
    run_processor()
