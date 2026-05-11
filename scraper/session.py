"""Playwright session management with cookie persistence.

Reuses a saved storage_state.json so we don't log in on every scrape.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import settings


@asynccontextmanager
async def browser_context() -> AsyncIterator[tuple[Browser, BrowserContext]]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=settings.BB_HEADLESS)
        storage = (
            settings.BB_STORAGE_STATE
            if os.path.exists(settings.BB_STORAGE_STATE)
            else None
        )
        ctx = await browser.new_context(storage_state=storage)
        try:
            yield browser, ctx
        finally:
            try:
                await ctx.storage_state(path=settings.BB_STORAGE_STATE)
            except Exception:
                pass
            await ctx.close()
            await browser.close()


async def is_logged_in(page: Page) -> bool:
    """We're logged in iff the URL is a Blackboard page AND not a login/CAS gate."""
    url = page.url.lower()
    # Hard fail: any auth-flow URL.
    if any(s in url for s in ("/cas/", "auth.sc.edu", "shibboleth", "/sso", "/login", "relogin", "duosecurity")):
        return False
    # Any URL inside the Blackboard host on /ultra/ or /webapps/ is logged-in territory.
    if "/ultra" in url or "/webapps/" in url:
        return True
    # Bare blackboard.<school> root could be either landing or post-login dashboard;
    # if there's an Ultra app shell, we're in.
    if "blackboard." in url:
        try:
            return await page.evaluate(
                """() => !!document.querySelector(
                    'bb-base-courses, bb-base-deck, bb-ultra-page, [ng-app="ultraApp"], #base-page'
                )"""
            )
        except Exception:
            return False
    return False
