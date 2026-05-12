"""Announcement scraping (per-course + global)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List

from playwright.async_api import BrowserContext
from selectolax.parser import HTMLParser

from app.config import settings
from scraper.parsers import parse_dt


# Catch common "Posted Apr 23, 2026" / "April 23, 2026 8:15 AM" patterns in
# the raw body/row text when the explicit date element selector misses.
_BODY_DATE_RE = re.compile(
    r"(?:posted\s+(?:on\s+)?)?"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)",
    re.IGNORECASE,
)


@dataclass
class AnnouncementRecord:
    blackboard_id: str
    title: str
    body_html: str | None
    posted_at: datetime | None
    author: str | None


def _stable_id(course_id: str, title: str, posted: str) -> str:
    h = hashlib.sha1(f"{course_id}|{title}|{posted}".encode("utf-8")).hexdigest()[:16]
    return f"ann_{h}"


async def fetch_announcements(ctx: BrowserContext, course_blackboard_id: str) -> List[AnnouncementRecord]:
    base = settings.BLACKBOARD_URL.rstrip("/")
    page = await ctx.new_page()
    try:
        paths = [
            f"/webapps/blackboard/execute/announcement?method=search&context=course&course_id={course_blackboard_id}",
            f"/ultra/courses/{course_blackboard_id}/announcements",
        ]
        html = ""
        for p in paths:
            try:
                await page.goto(base + p, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_load_state("networkidle", timeout=15_000)
                html = await page.content()
                if html:
                    break
            except Exception:
                continue

        tree = HTMLParser(html)
        out: list[AnnouncementRecord] = []

        # Classic Blackboard renders each announcement inside li.clearfix or
        # div.announcement; Ultra uses bb-announcement-item / role=listitem.
        candidates = tree.css(
            "li.clearfix, div.announcement, article, div[role='listitem'], "
            "bb-announcement-item, .announcement-item"
        )
        for node in candidates:
            title_node = node.css_first(
                "h3, h4, .item-title, .announcement-title, .title, [bb-translate]"
            )
            if not title_node:
                continue
            title = title_node.text(strip=True)
            if not title:
                continue
            body_node = node.css_first(
                ".vtbegenerated, .announcement-body, .content, .message, .body, .announcement-content"
            )
            body_html = body_node.html if body_node else None
            posted_node = node.css_first(
                # USC's Ultra theme uses .list-item-date-sent. Keep the other
                # selectors as fallbacks for classic and other Ultra layouts.
                ".list-item-date-sent, .announcementInfo, .posted-date, time, "
                ".date, .posted, .timestamp, .announcement-date"
            )
            posted_text = posted_node.text(strip=True) if posted_node else ""

            # First try the explicit element's text.
            posted_at = parse_dt(posted_text)
            # Fallback 1: <time datetime="ISO"> attribute.
            if not posted_at and posted_node is not None:
                dt_attr = posted_node.attributes.get("datetime")
                if dt_attr:
                    posted_at = parse_dt(dt_attr)
            # Fallback 2: scan the row text and body html for a "Month D, YYYY" pattern.
            if not posted_at:
                row_text = node.text(separator=" ", strip=True) or ""
                m = _BODY_DATE_RE.search(row_text)
                if not m and body_html:
                    m = _BODY_DATE_RE.search(body_html)
                if m:
                    posted_at = parse_dt(m.group(1))

            author = None
            author_node = node.css_first(".author, .posted-by, .by-line, .submitter")
            if author_node:
                author = author_node.text(strip=True)

            out.append(AnnouncementRecord(
                blackboard_id=_stable_id(course_blackboard_id, title, posted_text),
                title=title,
                body_html=body_html,
                posted_at=posted_at,
                author=author,
            ))
        return out
    finally:
        await page.close()
