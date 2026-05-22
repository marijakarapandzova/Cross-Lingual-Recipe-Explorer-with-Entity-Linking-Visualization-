from playwright.sync_api import sync_playwright
import time
import sys
sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
    time.sleep(3)

    inputs = page.locator("input").all()
    ing_input = inputs[2]
    ing_input.click()
    ing_input.fill("павлака")
    time.sleep(0.4)

    page.locator("button").filter(has_text="Analyze").first.click()
    time.sleep(7)

    # Scroll to bottom to trigger rendering of all lazy content
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)
    page.screenshot(
        path="C:/Users/ivana/WebstormProjects/webprogaming_project/screenshot_04_bottom.png",
    )
    print("Bottom screenshot saved")

    # Also scroll to mid-point
    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
    time.sleep(1)
    page.screenshot(
        path="C:/Users/ivana/WebstormProjects/webprogaming_project/screenshot_05_mid.png",
    )
    print("Mid screenshot saved")

    browser.close()
