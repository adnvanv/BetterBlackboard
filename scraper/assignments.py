"""Per-course assignment scraping."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List
from urllib.parse import urljoin

from playwright.async_api import BrowserContext
from selectolax.parser import HTMLParser

from app.config import settings
from scraper.parsers import parse_dt, parse_float


@dataclass
class AssignmentRecord:
    blackboard_id: str
    title: str
    due_at: datetime | None
    points_possible: float | None
    url: str | None


_ID_RE = re.compile(r"content_id=(_[^&]+)|/assignments?/(_[^/?#]+)")


async def fetch_assignments(ctx: BrowserContext, course_blackboard_id: str) -> List[AssignmentRecord]:
    base = settings.BLACKBOARD_URL.rstrip("/")
    page = await ctx.new_page()
    try:
        # Ultra-style course assignments page; older themes may differ.
        candidate_paths = [
            f"/ultra/courses/{course_blackboard_id}/outline",
            f"/webapps/blackboard/content/listContent.jsp?course_id={course_blackboard_id}",
        ]
        html = ""
        for p in candidate_paths:
            try:
                await page.goto(base + p, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_load_state("networkidle", timeout=15_000)
                html = await page.content()
                if html:
                    break
            except Exception:
                continue

        tree = HTMLParser(html)
        out: list[AssignmentRecord] = []
        seen: set[str] = set()

        # Strategy: find any link whose href looks like an assignment/content link.
        for a in tree.css("a"):
            href = a.attributes.get("href") or ""
            if "assignment" not in href.lower() and "content_id=" not in href.lower():
                continue
            m = _ID_RE.search(href)
            if not m:
                continue
            bb_id = m.group(1) or m.group(2)
            if bb_id in seen:
                continue
            seen.add(bb_id)
            title = (a.text() or "").strip()
            if not title:
                continue

            # Walk up to a row container to find due date / points text.
            container = a
            for _ in range(4):
                if container.parent is None:
                    break
                container = container.parent
            row_text = container.text(separator=" ", strip=True) if container else ""

            due_match = re.search(r"due[:\s]+([A-Za-z0-9,:\s/\-]+?(?:AM|PM|\d{4}))", row_text, re.I)
            due_at = parse_dt(due_match.group(1)) if due_match else None
            pts_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:points|pts)", row_text, re.I)
            pts = parse_float(pts_match.group(1)) if pts_match else None

            out.append(AssignmentRecord(
                blackboard_id=bb_id,
                title=title,
                due_at=due_at,
                points_possible=pts,
                url=urljoin(base + "/", href),
            ))
        return out
    finally:
        await page.close()
