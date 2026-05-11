"""Login / re-login flow for Blackboard.

Two entry conditions are common after page.goto(BLACKBOARD_URL):

1. We're already logged in (saved storage_state cookies still valid) → return.
2. We get bounced to a "relogin" page that holds a single LOGIN button. Clicking
   that button hits the school's CAS server; if your CAS session is still alive
   it silently redirects back to Blackboard with a fresh session, no password
   prompt. We handle this case automatically.
3. CAS itself has expired and we end up on a real password form (possibly with
   MFA). We can't safely auto-fill that — bail out and tell the user to run
   `python -m scraper login` for an interactive session.
"""
from __future__ import annotations

import logging

from playwright.async_api import BrowserContext, Page

from app.config import settings
from scraper.session import is_logged_in

log = logging.getLogger("scraper.login")


async def _settle(page: Page) -> None:
    """Wait for redirects + Angular bootstrap to settle."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=20_000)
    except Exception:
        pass
    try:
        await page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception:
        pass


async def _click_relogin_button(page: Page) -> bool:
    """If the page has a LOGIN button (USC's CAS relogin gate), click it.
    Returns True if we clicked something."""
    # Strip target='_blank' so navigation stays in this tab.
    await page.evaluate(
        "() => document.querySelectorAll('a.buttonLogin, a[target=_blank]')"
        ".forEach(a => a.removeAttribute('target'))"
    )
    locator = page.locator(
        "a.buttonLogin, a:has-text('LOGIN'), a:has-text('Login'), button:has-text('Login')"
    ).first
    if not await locator.count():
        return False
    log.info("Clicking relogin LOGIN button at %s", page.url)
    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
            await locator.click()
    except Exception as e:
        log.info("Navigation after click didn't fire cleanly: %s", e)
    return True


async def _fill_cas_form(page: Page) -> bool:
    """If we're on a CAS login form, fill creds from .env and submit.
    Returns True if we did something."""
    user_loc = page.locator("input[name='username'], input#username").first
    pass_loc = page.locator("input[name='password'], input#password").first
    if not (await user_loc.count() and await pass_loc.count()):
        return False
    if not (settings.BLACKBOARD_USER and settings.BLACKBOARD_PASS):
        log.warning("CAS form detected but BLACKBOARD_USER/PASS not set in .env")
        return False
    log.info("Filling CAS form at %s", page.url)
    await user_loc.fill(settings.BLACKBOARD_USER)
    await pass_loc.fill(settings.BLACKBOARD_PASS)
    submit = page.locator(
        "button[name='submit'], button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign in')"
    ).first
    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=60_000):
            if await submit.count():
                await submit.click()
            else:
                await pass_loc.press("Enter")
    except Exception as e:
        log.info("Navigation after CAS submit didn't fire cleanly: %s", e)
    return True


async def _wait_for_duo(page: Page, timeout_s: int = 120) -> None:
    """Duo prompt is on screen — wait until the page leaves the Duo iframe/host
    or we reach a Blackboard URL. Times out so an unattended run still errors
    cleanly instead of hanging forever."""
    log.info("Waiting up to %ds for Duo MFA approval (check your phone).", timeout_s)
    deadline = timeout_s * 10  # poll every 100ms
    for _ in range(deadline):
        url = page.url.lower()
        if "blackboard." in url and "/login" not in url and "relogin" not in url:
            return
        if "duo" not in url and "cas" not in url:
            # We've navigated away from CAS/Duo — good enough.
            return
        await page.wait_for_timeout(100)
    raise RuntimeError("Timed out waiting for Duo MFA approval.")


async def ensure_logged_in(ctx: BrowserContext) -> Page:
    page = await ctx.new_page()
    log.info("Navigating to %s", settings.BLACKBOARD_URL)
    await page.goto(settings.BLACKBOARD_URL, wait_until="domcontentloaded")
    await _settle(page)
    log.info("After initial load, URL = %s", page.url)

    if await is_logged_in(page):
        log.info("Session looks good, continuing.")
        return page

    # Up to 5 steps through the relogin / CAS / Duo chain.
    for attempt in range(5):
        # Stage A: relogin "LOGIN" button.
        if await _click_relogin_button(page):
            await _settle(page)
            log.info("After step %d (relogin click), URL = %s", attempt + 1, page.url)
            if await is_logged_in(page):
                return page
            continue

        # Stage B: CAS username/password form.
        if "cas" in page.url.lower() and await _fill_cas_form(page):
            await _settle(page)
            log.info("After step %d (CAS submit), URL = %s", attempt + 1, page.url)

            # Stage C: Duo prompt if present.
            if "duo" in page.url.lower() or await page.locator("iframe[src*='duo']").count():
                await _wait_for_duo(page)
                await _settle(page)
                log.info("After Duo, URL = %s", page.url)

            if await is_logged_in(page):
                return page
            continue

        # Nothing matched on this attempt; bail.
        break

    raise RuntimeError(
        "SESSION_EXPIRED: Saved Blackboard session is no longer valid. "
        "Open BetterBlackboard-Login on your laptop, log in, then click 'Send session to server' "
        f"and try again. (last URL: {page.url})"
    )
