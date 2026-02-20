import pandas as pd
from playwright.sync_api import sync_playwright
import os
from datetime import datetime
import pytz
import io

NYC = pytz.timezone('America/New_York')
MASTER_FILE = "callao_master_data.csv"
TARGET_URL = "https://www.apmterminals.com/track-and-trace/vessel-schedule?terminal=PECLL"

def run_sentinel():
    now_nyc = datetime.now(NYC).replace(tzinfo=None)
    ts = now_nyc.strftime('%Y-%m-%d %H:%M:%S')
    print(f"--- M5 STEALTH SCRAPE: {ts} ---")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # We add a specific viewport size to ensure the table isn't hidden by "mobile" view
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        try:
            print("Visiting APM Terminals...")
            # CHANGE: Wait for 'domcontentloaded' instead of 'networkidle'
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

            print("Waiting for vessel table to appear...")
            # We wait for the specific 'table' tag or the data container
            page.wait_for_selector("table", timeout=45000)
            
            # Small pause to let the JavaScript finish rendering the rows
            page.wait_for_timeout(2000)

            # Extract the table
            html_content = page.content()
            tables = pd.read_html(io.StringIO(html_content))
            
            if not tables:
                print("No tables detected in the HTML.")
                return

            df = tables[0]
            
            # Filter for Muelle 5
            berth_col = next((c for c in df.columns if 'Berth' in str(c)), None)
            
            if berth_col:
                m5 = df[df[berth_col].astype(str).str.contains('M5', case=False, na=False)].copy()
                
                if not m5.empty:
                    m5['Timestamp_EST'] = ts
                    file_exists = os.path.isfile(MASTER_FILE)
                    m5.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
                    print(f"SUCCESS: {len(m5)} industrial vessels captured.")
                else:
                    print("M5 is clear. No industrial activity detected.")
            else:
                print(f"Berth column not found. Columns: {list(df.columns)}")

        except Exception as e:
            print(f"Scrape Failed: {str(e)}")
            
        finally:
            browser.close()

if __name__ == "__main__":
    run_sentinel()
