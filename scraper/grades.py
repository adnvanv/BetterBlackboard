"""Per-course grade center scraping."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List

from playwright.async_api import BrowserContext
from selectolax.parser import HTMLParser

from app.config import settings
from scraper.parsers import parse_dt, parse_float


@dataclass
class GradeRecord:
    assignment_title: str  # used to match to Assignment row by title within the course
    score: float | None
    points_possible: float | None
    letter: str | None
    raw: str
    posted_at: datetime | None = None


# M/D/YY or M/D/YYYY anywhere in the row text; also catches ISO yyyy-mm-dd.
_DATE_RE = re.compile(
    r"\b(\d{1,2}/\d{1,2}/(?:\d{2}|\d{4})|\d{4}-\d{2}-\d{2})\b"
)


def _extract_posted_at(row, raw_grade: str) -> datetime | None:
    """Find the M/D/YY-style date that Blackboard renders next to each grade.

    We scan the row's full text but skip any match that lives inside the
    raw grade text (so a score like '10/100' isn't mistaken for a date).
    """
    row_text = row.text(separator=" ", strip=True) or ""
    for m in _DATE_RE.finditer(row_text):
        candidate = m.group(1)
        if candidate in raw_grade:
            continue  # part of the grade ratio, not a date
        dt = parse_dt(candidate)
        if dt:
            return dt
    return None


async def fetch_grades(ctx: BrowserContext, course_blackboard_id: str) -> List[GradeRecord]:
    base = settings.BLACKBOARD_URL.rstrip("/")
    page = await ctx.new_page()
    try:
        paths = [
            f"/webapps/bb-mygrades-bb_bb60/myGrades?course_id={course_blackboard_id}&stream_name=mygrades",
            f"/ultra/courses/{course_blackboard_id}/gradebook/student",
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
        out: list[GradeRecord] = []

        # Classic My Grades layout: each assignment is a row with class containing "row".
        # Ultra: div with role=row or various MUI-styled rows.
        for row in tree.css("div.row, tr.gradebook-row, [role='row']"):
            title_node = row.css_first(
                ".cell.gradable, .item-title, td.gradeColumn, a, [role='cell']"
            )
            if not title_node:
                continue
            title = title_node.text(strip=True)
            if not title:
                continue
            grade_node = row.css_first(".cell.grade, .grade-value, td.grade")
            raw = grade_node.text(strip=True) if grade_node else ""
            if not raw:
                continue

            score: float | None = None
            possible: float | None = None
            letter: str | None = None

            if "/" in raw:
                left, _, right = raw.partition("/")
                score = parse_float(left)
                possible = parse_float(right)
            else:
                score = parse_float(raw)
                if score is None:
                    letter = raw or None

            posted_at = _extract_posted_at(row, raw)

            out.append(GradeRecord(
                assignment_title=title,
                score=score,
                points_possible=possible,
                letter=letter,
                raw=raw,
                posted_at=posted_at,
            ))
        return out
    finally:
        await page.close()
