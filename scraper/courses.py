"""Enumerate favorited courses from Blackboard Ultra's /ultra/course page.

We only scrape favorited courses — these are the ones the user actively cares
about (current semester), and the favorites set is small and predictable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from playwright.async_api import BrowserContext
from selectolax.parser import HTMLParser

from app.config import settings


@dataclass
class CourseRecord:
    blackboard_id: str
    name: str
    code: str | None
    term: str | None
    url: str | None


# e.g. "CSCE587-001-SPRING-2026" → code "CSCE587-001", term "SPRING 2026"
_CODE_TERM_RE = re.compile(
    r"^(?P<code>.+?)-(?P<term>(?:SPRING|SUMMER|FALL|WINTER)[-\s]?\d{4})$",
    re.IGNORECASE,
)


def _parse_code_term(display_id: str) -> tuple[str | None, str | None]:
    if not display_id:
        return None, None
    m = _CODE_TERM_RE.match(display_id.strip())
    if not m:
        return display_id.strip(), None
    return m.group("code"), m.group("term").replace("-", " ").upper()


async def fetch_courses(ctx: BrowserContext) -> List[CourseRecord]:
    base = settings.BLACKBOARD_URL.rstrip("/")
    page = await ctx.new_page()
    try:
        await page.goto(base + "/ultra/course", wait_until="domcontentloaded", timeout=30_000)
        # Angular renders the course tiles after API calls finish.
        try:
            await page.wait_for_selector("article[data-course-id]", timeout=20_000)
        except Exception:
            pass
        # Give Angular a moment to settle and any virtualization to flush.
        await page.wait_for_load_state("networkidle", timeout=15_000)
        # Scroll to the bottom in case more cards load lazily.
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)
        html = await page.content()
    finally:
        await page.close()

    tree = HTMLParser(html)
    out: list[CourseRecord] = []

    for art in tree.css("article[data-course-id]"):
        bb_id = art.attributes.get("data-course-id")
        if not bb_id:
            continue

        # Favorited filter: button.js-favourite-button has aria-label starting with "Remove"
        # for favorited courses, "Add" for unfavorited.
        fav_btn = art.css_first("button.js-favourite-button")
        if not fav_btn:
            continue
        aria = (fav_btn.attributes.get("aria-label") or "").lower()
        if not aria.startswith("remove"):
            continue  # not favorited

        name_node = art.css_first("h4.js-course-title-element, h4[id^='course-name-']")
        name = name_node.text(strip=True) if name_node else ""
        if not name:
            continue

        code_node = art.css_first("span[id^='course-id-']")
        display_id = code_node.text(strip=True) if code_node else ""
        code, term = _parse_code_term(display_id)

        # Build a URL from the id; Ultra outline is the canonical landing page.
        url = f"{base}/ultra/courses/{bb_id}/cl/outline"

        out.append(CourseRecord(
            blackboard_id=bb_id,
            name=name,
            code=code,
            term=term,
            url=url,
        ))

    return out
