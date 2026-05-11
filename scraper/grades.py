"""Per-course grade center scraping."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from playwright.async_api import BrowserContext
from selectolax.parser import HTMLParser

from app.config import settings
from scraper.parsers import parse_float


@dataclass
class GradeRecord:
    assignment_title: str  # used to match to Assignment row by title within the course
    score: float | None
    points_possible: float | None
    letter: str | None
    raw: str


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
        for row in tree.css("div.row, tr.gradebook-row"):
            title_node = row.css_first(".cell.gradable, .item-title, td.gradeColumn, a")
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

            out.append(GradeRecord(
                assignment_title=title,
                score=score,
                points_possible=possible,
                letter=letter,
                raw=raw,
            ))
        return out
    finally:
        await page.close()
