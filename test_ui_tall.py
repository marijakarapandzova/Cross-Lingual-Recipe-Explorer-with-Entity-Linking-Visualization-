from playwright.sync_api import sync_playwright
import time
import sys
sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # Very tall viewport so Streamlit renders all content without virtual scroll
    page = browser.new_page(viewport={"width": 1400, "height": 4000})
    page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
    time.sleep(4)

    inputs = page.locator("input").all()
    ing_input = inputs[2]
    ing_input.click()
    ing_input.fill("павлака")
    time.sleep(0.4)

    page.locator("button").filter(has_text="Analyze").first.click()
    print("Clicked Analyze - waiting...")
    time.sleep(8)

    page.screenshot(
        path="C:/Users/ivana/WebstormProjects/webprogaming_project/screenshot_06_tall.png",
        full_page=True,
    )
    print("Tall screenshot saved")
    browser.close()
