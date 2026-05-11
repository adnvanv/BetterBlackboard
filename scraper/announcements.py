"""Announcement scraping (per-course + global)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List

from playwright.async_api import BrowserContext
from selectolax.parser import HTMLParser

from app.config import settings
from scraper.parsers import parse_dt


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

        # Classic Blackboard renders each announcement inside li.clearfix or div.announcement.
        candidates = tree.css("li.clearfix, div.announcement, article, div[role='listitem']")
        for node in candidates:
            title_node = node.css_first("h3, h4, .item-title, .announcement-title")
            if not title_node:
                continue
            title = title_node.text(strip=True)
            if not title:
                continue
            body_node = node.css_first(".vtbegenerated, .announcement-body, .content, .message")
            body_html = body_node.html if body_node else None
            posted_node = node.css_first(".announcementInfo, .posted-date, time")
            posted_text = posted_node.text(strip=True) if posted_node else ""
            posted_at = parse_dt(posted_text)
            author = None
            author_node = node.css_first(".author, .posted-by")
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
