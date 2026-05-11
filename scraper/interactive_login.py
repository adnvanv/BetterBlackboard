"""One-time interactive login.

Opens a real (non-headless) browser, lets the user log in by hand
(including SSO + MFA), and waits until they reach the Blackboard dashboard.
Then saves the session cookies to storage_state.json so future headless
scrapes reuse the session.
"""
from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from app.config import settings


SUCCESS_MARKERS = ("/ultra/", "/webapps/portal", "tab_tab_group_id")


async def run_interactive_login() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(settings.BLACKBOARD_URL)

        print()
        print("=" * 60)
        print("Log in by hand in the browser window that just opened.")
        print("Complete SSO + Duo MFA. Once you see your Blackboard")
        print("dashboard with your courses, come back here and press Enter.")
        print("=" * 60)
        print()

        # Wait for the user to press Enter on the terminal.
        await asyncio.get_event_loop().run_in_executor(None, input, "Press Enter when logged in: ")

        url = page.url
        if "login" in url.lower() or "relogin" in url.lower() or "sso" in url.lower():
            print(f"WARNING: still on a login/SSO page:\n  {url}")
            print("Saving session anyway. If scraping fails, re-run `python -m scraper login`.")

        await ctx.storage_state(path=settings.BB_STORAGE_STATE)
        print(f"Saved session to {settings.BB_STORAGE_STATE}")
        await browser.close()
