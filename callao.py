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
    print(f"--- M5 INTERACTIVE SCRAPE: {ts} ---")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        try:
            print("Force-loading APM Terminals...")
            try:
                # We use domcontentloaded so we can interact with the cookie banner immediately
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            except Exception as load_err:
                print(f"Initial load timeout bypassed: {load_err}")

            # 1. THE COOKIE CRUSHER
            try:
                print("Hunting for Cookie Banner...")
                # We look for the exact text from your diagnostic dump
                cookie_button = page.get_by_text("Allow all", exact=True)
                cookie_button.click(timeout=10000)
                print("Cookie wall destroyed. Authorizing data payload...")
                
                # Give the site 3 seconds to process the click and trigger the API
                page.wait_for_timeout(3000)
            except Exception as e:
                print("No cookie banner detected. Proceeding...")

            # 2. THE TABLE HUNT
            print("Hunting for the Vessel Table...")
            try:
                page.wait_for_selector("table", timeout=30000)
            except:
                print("Timeout: The site might be using a custom div-grid instead of an HTML table.")
            
            # Final settle time for JavaScript to render the rows
            page.wait_for_timeout(3000) 

            html_content = page.content()
            
            try:
                tables = pd.read_html(io.StringIO(html_content), flavor='lxml')
            except ValueError:
                print("Pandas Error: No HTML <table> tags exist in the DOM.")
                print("Fallback Diagnostic: Attempting to pull raw text...")
                print(page.inner_text("body")[:1000])
                return
            
            if not tables:
                print("Table found but empty.")
                return

            df = tables[0]
            
            # Isolate Muelle 5
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
                print(f"Berth column not found. Available: {list(df.columns)}")

        except Exception as e:
            print(f"Scrape Failed: {str(e)}")
            
        finally:
            browser.close()

if __name__ == "__main__":
    run_sentinel()
