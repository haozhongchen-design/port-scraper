import pandas as pd
from playwright.sync_api import sync_playwright
import os
from datetime import datetime
import pytz
import io

NYC = pytz.timezone('America/New_York')
MASTER_FILE = "callao_master_data.csv"
# We use the main UI link, NOT the API link
TARGET_URL = "https://www.apmterminals.com/track-and-trace/vessel-schedule?terminal=PECLL"

def run_sentinel():
    now_nyc = datetime.now(NYC).replace(tzinfo=None)
    ts = now_nyc.strftime('%Y-%m-%d %H:%M:%S')
    print(f"--- M5 STEALTH SCRAPE: {ts} ---")

    with sync_playwright() as p:
        # Launch a real, headless browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("Visiting APM Terminals...")
            page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

            # Wait specifically for the table to render on the screen
            page.wait_for_selector("table", timeout=30000)
            
            # Extract the table into a Pandas DataFrame
            html_content = page.content()
            tables = pd.read_html(io.StringIO(html_content))
            
            if not tables:
                print("No tables detected on page.")
                return

            df = tables[0]
            
            # Isolate Muelle 5 (M5)
            berth_col = next((c for c in df.columns if 'Berth' in str(c)), None)
            
            if berth_col:
                m5 = df[df[berth_col].astype(str).str.contains('M5', case=False, na=False)].copy()
                
                if not m5.empty:
                    m5['Timestamp_EST'] = ts
                    file_exists = os.path.isfile(MASTER_FILE)
                    m5.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
                    print(f"SUCCESS: {len(m5)} industrial vessels captured.")
                else:
                    print("M5 is clear.")
            else:
                print(f"Berth column not found. Available: {list(df.columns)}")

        except Exception as e:
            print(f"Scrape Failed: {str(e)}")
            
        finally:
            browser.close()

if __name__ == "__main__":
    run_sentinel()
