"""Calendar event scraping (global calendar with course filtering)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List

from playwright.async_api import BrowserContext

from app.config import settings
from scraper.parsers import parse_dt


@dataclass
class CalendarRecord:
    blackboard_id: str
    course_blackboard_id: str | None
    title: str
    starts_at: datetime | None
    ends_at: datetime | None
    kind: str | None
    url: str | None


async def fetch_calendar(ctx: BrowserContext) -> List[CalendarRecord]:
    """Hit the calendar JSON feed used by Blackboard's calendar UI."""
    base = settings.BLACKBOARD_URL.rstrip("/")
    page = await ctx.new_page()
    try:
        # Wide window: 90 days back, 180 days forward.
        feed_url = (
            base
            + "/webapps/calendar/calendarFeed/lastNDays?start=-90&end=180&lang=en_US"
        )
        out: list[CalendarRecord] = []
        try:
            resp = await page.goto(feed_url, wait_until="domcontentloaded", timeout=30_000)
            text = await page.evaluate("() => document.body.innerText")
            data = json.loads(text)
        except Exception:
            return out

        if not isinstance(data, list):
            return out

        for ev in data:
            try:
                bb_id = str(ev.get("id") or ev.get("eventId") or ev.get("calendarId") or "")
                title = ev.get("title") or ev.get("name") or ""
                if not bb_id or not title:
                    continue
                starts = parse_dt(str(ev.get("start") or ev.get("startDate") or ""))
                ends = parse_dt(str(ev.get("end") or ev.get("endDate") or ""))
                kind = ev.get("type") or ev.get("category")
                url = ev.get("itemSourceUrl") or ev.get("url")
                course_id = None
                cal_id = ev.get("calendarId") or ""
                m = re.search(r"(_\d+_\d+)", str(cal_id))
                if m:
                    course_id = m.group(1)
                out.append(CalendarRecord(
                    blackboard_id=bb_id,
                    course_blackboard_id=course_id,
                    title=title,
                    starts_at=starts,
                    ends_at=ends,
                    kind=kind,
                    url=url,
                ))
            except Exception:
                continue
        return out
    finally:
        await page.close()
