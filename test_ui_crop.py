from playwright.sync_api import sync_playwright
import time
import sys
sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 4000})
    page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
    time.sleep(4)

    inputs = page.locator("input").all()
    ing_input = inputs[2]
    ing_input.click()
    ing_input.fill("павлака")
    time.sleep(0.4)

    page.locator("button").filter(has_text="Analyze").first.click()
    time.sleep(8)

    # Clip: capture only the lower half where stages 4+5 are
    page.screenshot(
        path="C:/Users/ivana/WebstormProjects/webprogaming_project/screenshot_07_usda.png",
        clip={"x": 145, "y": 700, "width": 1255, "height": 900},
    )
    print("USDA section screenshot saved")
    browser.close()
