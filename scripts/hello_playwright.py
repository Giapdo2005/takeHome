"""Day 1 smoke test #1 — prove Playwright can drive a browser and read state.

This is a throwaway script. It does, by hand, the three things `BrowserSurface`
will do on Day 3:
  1. open a real browser and navigate,
  2. capture the accessibility tree as text (our PRIMARY perception signal),
  3. capture a screenshot (our SECONDARY signal + evidence).

Run:  python scripts/hello_playwright.py
Pass: it prints an accessibility snapshot and writes runs/smoke/example.png
"""

from __future__ import annotations

import pathlib

from playwright.sync_api import sync_playwright

OUT = pathlib.Path("runs/smoke")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # headless=False so you actually SEE it work. Flip to True for speed.
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://example.com", wait_until="load")
        print(f"url:   {page.url}")
        print(f"title: {page.title()}")

        # The accessibility tree, already rendered as compact text by Playwright.
        # This IS the format the Surface will put in Observation.a11y_tree on Day 3
        # and feed to the LLM instead of a screenshot. Lines look like:
        #   - button "Search"
        #   - textbox "Member ID"
        a11y = page.locator("body").aria_snapshot()
        print("\n--- aria snapshot (this is our primary perception signal) ---")
        print(a11y)

        shot = OUT / "example.png"
        page.screenshot(path=str(shot))
        print(f"\nscreenshot -> {shot}")

        browser.close()

    print("\nOK — Playwright works.")


if __name__ == "__main__":
    main()
