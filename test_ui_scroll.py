from playwright.sync_api import sync_playwright
import time
import sys
sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # Fill ingredient input (index 2 found earlier)
    inputs = page.locator("input").all()
    ing_input = inputs[2]
    ing_input.click()
    ing_input.fill("павлака")
    time.sleep(0.4)

    page.locator("button").filter(has_text="Analyze").first.click()
    time.sleep(7)

    # Full-page screenshot captures everything
    page.screenshot(
        path="C:/Users/ivana/WebstormProjects/webprogaming_project/screenshot_03_full.png",
        full_page=True,
    )
    print("Full-page screenshot saved")
    browser.close()
