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
    print(f"--- M5 AGGRESSIVE SCRAPE: {ts} ---")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        try:
            print("Force-loading APM Terminals (ignoring timeouts)...")
            try:
                # 'commit' means it stops waiting as soon as the server responds. No networkidle trap.
                page.goto(TARGET_URL, wait_until="commit", timeout=30000)
            except Exception as load_err:
                print(f"Initial load timeout bypassed: {load_err}")

            print("Hunting for the Vessel Table...")
            # Wait for the table to actually enter the DOM
            page.wait_for_selector("table", timeout=45000)
            
            # Let the rows populate
            page.wait_for_timeout(3000) 

            html_content = page.content()
            tables = pd.read_html(io.StringIO(html_content))
            
            if not tables:
                print("Table found but empty.")
                return

            df = tables[0]
            
            berth_col = next((c for c in df.columns if 'Berth' in str(c)), None)
            
            if berth_col:
                m5 = df[df[berth_col].astype(str).str.contains('M5', case=False, na=False)].copy()
                
                if not m5.empty:
                    m5['Timestamp_EST'] = ts
                    file_exists = os.path.isfile(MASTER_FILE)
                    m5.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
                    print(f"SUCCESS: {len(m5)} vessels captured at M5.")
                else:
                    print("M5 is clear.")
            else:
                print(f"Berth column not found. Available: {list(df.columns)}")

        except Exception as e:
            print(f"Scrape Failed: {str(e)}")
            page.screenshot(path="scrape_error_capture.png")
            
        finally:
            browser.close()

if __name__ == "__main__":
    run_sentinel()
