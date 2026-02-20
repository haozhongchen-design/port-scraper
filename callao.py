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
        # 1. Launch Stealth Browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        try:
            # 2. Navigate to page
            print("Navigating to APM Terminals...")
            page.goto(TARGET_URL, wait_until="networkidle", timeout=90000)

            # 3. Wait for the vessel table to render (adjust selector if needed)
            # We target the common 'table' tag or a specific data container
            page.wait_for_selector("table", timeout=30000)
            
            # 4. Extract HTML content of the table
            html_content = page.content()
            tables = pd.read_html(io.StringIO(html_content))
            
            if not tables:
                print("No tables found in browser DOM.")
                return

            df = tables[0]
            
            # 5. Filter for Muelle 5 (Industrial Concentration)
            # We look for 'Berth' in columns and 'M5' in values
            berth_col = next((c for c in df.columns if 'Berth' in str(c)), None)
            
            if berth_col:
                m5 = df[df[berth_col].astype(str).str.contains('M5', case=False, na=False)].copy()
                
                if not m5.empty:
                    m5['Scrape_Timestamp_EST'] = ts
                    file_exists = os.path.isfile(MASTER_FILE)
                    m5.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
                    print(f"SUCCESS: {len(m5)} industrial vessels captured.")
                else:
                    print("M5 is currently clear.")
            else:
                print(f"Berth column not found. Available: {list(df.columns)}")

        except Exception as e:
            print(f"Stealth Scrape Failed: {str(e)}")
            # Optional: Save a screenshot to debug why it failed
            # page.screenshot(path="debug_error.png")
            
        finally:
            browser.close()

if __name__ == "__main__":
    run_sentinel()
