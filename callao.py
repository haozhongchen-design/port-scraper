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
    print(f"--- M5 CSV HIJACK V2: {ts} ---")

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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Hard pause to allow external tracking scripts to inject the cookie wall
            page.wait_for_timeout(4000)

            # 1. THE COOKIE CRUSHER (Broadened)
            try:
                print("Hunting for Cookie Banner...")
                cookie_button = page.locator("button:has-text('Allow all')").first
                if cookie_button.is_visible(timeout=5000):
                    cookie_button.click()
                    print("Cookie wall destroyed. Authorizing payload...")
                    page.wait_for_timeout(3000)
                else:
                    print("Cookie banner not visible. Proceeding...")
            except Exception:
                print("No cookie banner detected.")

            # 2. THE OMNI-LOCATOR
            print("Hunting for the CSV button using broad spectrum locator...")
            # This targets title, alt, aria-label, or raw text containing CSV or Export
            csv_locator = page.locator("css=[title*='CSV'], [alt*='CSV'], [aria-label*='CSV'], :text-is('CSV'), :has-text('Export as CSV')").first
            
            csv_locator.wait_for(state="visible", timeout=30000)
            
            # 3. INTERCEPTING THE DOWNLOAD
            print("Target acquired. Initiating download sequence...")
            with page.expect_download(timeout=45000) as download_info:
                csv_locator.click(force=True)
                
            download = download_info.value
            print(f"Download intercepted: {download.suggested_filename}")
            download.save_as(TEMP_FILE)

            # 4. PROCESSING THE RAW CSV
            print("Parsing official port data...")
            df = pd.read_csv(TEMP_FILE)
            
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)

            berth_col = next((c for c in df.columns if 'Berth' in str(c)), None)
            
            if berth_col:
                m5 = df[df[berth_col].astype(str).str.contains('M5', case=False, na=False)].copy()
                if not m5.empty:
                    m5['Timestamp_EST'] = ts
                    file_exists = os.path.isfile(MASTER_FILE)
                    m5.to_csv(MASTER_FILE, mode='a', index=False, header=not file_exists)
                    print(f"SUCCESS: {len(m5)} vessels captured at M5.")
                else:
                    print("M5 is clear. No industrial activity detected.")
            else:
                print(f"Berth column missing. Columns found: {list(df.columns)}")

        except Exception as e:
            print(f"Scrape Failed: {str(e)}")
            print("Capturing visual intelligence...")
            # This saves a picture of exactly what blocked the bot
            page.screenshot(path="csv_fail_screenshot.png")
            
        finally:
            browser.close()

if __name__ == "__main__":
    run_sentinel()
