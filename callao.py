import pandas as pd
from playwright.sync_api import sync_playwright
import os
from datetime import datetime
import pytz

NYC = pytz.timezone('America/New_York')
MASTER_FILE = "callao_master_data.csv"
TEMP_FILE = "apm_temp_download.csv"
TARGET_URL = "https://www.apmterminals.com/track-and-trace/vessel-schedule?terminal=PECLL"

def run_sentinel():
    now_nyc = datetime.now(NYC).replace(tzinfo=None)
    ts = now_nyc.strftime('%Y-%m-%d %H:%M:%S')
    print(f"--- M5 CSV HIJACK: {ts} ---")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, downloads_path=".")
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            accept_downloads=True
        )
        page = context.new_page()

        try:
            print("Force-loading APM Terminals...")
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            except Exception as load_err:
                print(f"Initial load timeout bypassed: {load_err}")

            # 1. THE COOKIE CRUSHER
            try:
                cookie_button = page.get_by_text("Allow all", exact=True)
                cookie_button.click(timeout=5000)
                print("Cookie wall destroyed.")
                page.wait_for_timeout(2000)
            except:
                print("No cookie banner detected. Proceeding...")

            # 2. HUNTING THE EXPORT BUTTON
            print("Hunting for the 'Export as CSV' button...")
            
            # We use a CSS selector that looks for ANY element with the title "Export as CSV"
            # We use an asterisk (*) for a partial match just in case there are hidden spaces
            export_button = page.locator("[title*='Export as CSV']")
            
            # Wait for it to actually appear on the screen
            export_button.wait_for(state="visible", timeout=30000)
            
            # 3. INTERCEPTING THE DOWNLOAD
            print("Button located. Initiating download sequence...")
            with page.expect_download(timeout=45000) as download_info:
                # We force the click in case another invisible element is slightly overlapping it
                export_button.click(force=True)
                
            download = download_info.value
            print(f"Download intercepted: {download.suggested_filename}")
            
            # Save it locally so Pandas can read it
            download.save_as(TEMP_FILE)

            # 4. PROCESSING THE RAW CSV
            print("Parsing official port data...")
            df = pd.read_csv(TEMP_FILE)
            
            # Clean up the temporary file immediately
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)

            # Isolate Muelle 5
            berth_col = next((c for c in df.columns if 'Berth' in str(c)), None)
            
            if berth_col:
                m5 = df[df[berth_col].astype(str).str.contains('M5', case=False, na=False)].copy()
                if not m5.empty:
                    m5['Timestamp_EST'] = ts
                    file_exists = os.path.isfile(MASTER_FILE)
                    m5.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
                    print(f"SUCCESS: {len(m5)} vessels captured at M5 and saved to Master Log.")
                else:
                    print("M5 is clear. No industrial activity detected.")
            else:
                print(f"Berth column not found in the downloaded CSV. Available columns: {list(df.columns)}")

        except Exception as e:
            print(f"Scrape Failed: {str(e)}")
            
        finally:
            browser.close()

if __name__ == "__main__":
    run_sentinel()
