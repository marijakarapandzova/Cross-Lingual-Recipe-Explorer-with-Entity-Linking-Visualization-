from playwright.sync_api import sync_playwright
import time
import sys
sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # List all inputs
    inputs = page.locator("input").all()
    print(f"Found {len(inputs)} inputs")
    for i, inp in enumerate(inputs):
        ph = inp.get_attribute("placeholder") or ""
        tp = inp.get_attribute("type") or ""
        print(f"  [{i}] type={tp!r}  placeholder={ph!r}")

    # The ingredient input is the second text field (after search)
    # Find it by its placeholder
    ing_input = None
    for inp in inputs:
        ph = inp.get_attribute("placeholder") or ""
        if "sour cream" in ph or "onion" in ph or "Macedonian" in ph.lower():
            ing_input = inp
            break

    if not ing_input:
        # Fall back to second text input
        text_inputs = [i for i in inputs if i.get_attribute("type") != "password"]
        if len(text_inputs) >= 2:
            ing_input = text_inputs[1]

    if ing_input:
        ing_input.click()
        ing_input.fill("павлака")  # павлака
        print("Typed ingredient")
        time.sleep(0.5)
    else:
        print("ERROR: could not find ingredient input")
        browser.close()
        exit(1)

    # Click Analyze button
    analyze_btn = page.locator("button").filter(has_text="Analyze").first
    analyze_btn.click()
    print("Clicked Analyze — waiting for results...")
    time.sleep(7)

    page.screenshot(
        path="C:/Users/ivana/WebstormProjects/webprogaming_project/screenshot_02_result.png",
        full_page=True,
    )
    print("Screenshot saved: screenshot_02_result.png")
    browser.close()
