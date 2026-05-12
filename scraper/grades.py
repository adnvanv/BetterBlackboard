"""Per-course grade center scraping.

Supports two layouts:
- **Classic** "My Grades" (`/webapps/bb-mygrades-bb_bb60/myGrades`) — div.row + .cell.grade
- **Ultra** Gradebook student view (`/ultra/courses/<id>/gradebook/student`) — a MUI table
  where each cell is a `<td>` with an `aria-describedby` pointing at the column
  header id. We anchor on those header IDs (which are stable) rather than the
  hash-suffixed JSS class names.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from playwright.async_api import BrowserContext
from selectolax.parser import HTMLParser, Node

from app.config import settings
from scraper.parsers import parse_dt, parse_float


@dataclass
class GradeRecord:
    assignment_title: str  # used to match to Assignment row by title within the course
    score: float | None
    points_possible: float | None
    letter: str | None
    raw: str
    posted_at: Optional[datetime] = None


_DATE_RE = re.compile(
    r"\b(\d{1,2}/\d{1,2}/(?:\d{2}|\d{4})|\d{4}-\d{2}-\d{2})\b"
)
_GRADELIKE_RE = re.compile(r"\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*%|^\d+(?:\.\d+)?$|^[A-F][+\-]?$")


def _row_of(cell: Node) -> Optional[Node]:
    """Walk up to the nearest <tr> ancestor."""
    cur = cell.parent
    while cur is not None and cur.tag != "tr":
        cur = cur.parent
    return cur


def _parse_score(raw: str) -> tuple[float | None, float | None, str | None]:
    """Returns (score, points_possible, letter)."""
    if "/" in raw:
        left, _, right = raw.partition("/")
        return parse_float(left), parse_float(right), None
    n = parse_float(raw)
    if n is not None:
        return n, None, None
    return None, None, (raw or None)


def _parse_ultra(html: str) -> List[GradeRecord]:
    """Ultra Gradebook student-view: MUI <table> with aria-describedby anchors."""
    tree = HTMLParser(html)
    out: list[GradeRecord] = []
    seen_titles: set[str] = set()

    title_cells = tree.css("td[aria-describedby='course-student-grades-header-itemName']")
    for tc in title_cells:
        tr = _row_of(tc)
        if not tr:
            continue

        # Title — prefer the anchor-wrapped headline, fall back to plain text.
        title_node = tc.css_first(
            "a [id*='item-name'], a h4, [id*='item-name'], h4, a"
        )
        title = (title_node.text(strip=True) if title_node else tc.text(strip=True)).strip()
        # Strip icon/SVG noise; if there's a leading non-alphanumeric clump, peel it.
        title = re.sub(r"^[\s ​]+", "", title)
        if not title or title in seen_titles:
            continue

        # Due date — the column Blackboard labels "dueDate" in the table header.
        date_cell = tr.css_first("td[aria-describedby='course-student-grades-header-dueDate']")
        posted_at = parse_dt(date_cell.text(strip=True)) if date_cell else None

        # Grade — Blackboard's Ultra has used a few header names over versions.
        # Try the likely ones, then fall back to scanning siblings.
        grade_cell = None
        for aria in (
            "course-student-grades-header-grade",
            "course-student-grades-header-mark",
            "course-student-grades-header-score",
            "course-student-grades-header-attempt",
            "course-student-grades-header-displayGrade",
            "course-student-grades-header-points",
        ):
            grade_cell = tr.css_first(f"td[aria-describedby='{aria}']")
            if grade_cell:
                break
        if grade_cell is None:
            # Fallback: any other <td> in this row whose text looks like a grade.
            for cell in tr.css("td"):
                if cell in (tc, date_cell):
                    continue
                text = (cell.text(strip=True) or "")
                if text and _GRADELIKE_RE.search(text):
                    grade_cell = cell
                    break
        if grade_cell is None:
            continue
        raw = (grade_cell.text(strip=True) or "").strip()
        if not raw:
            continue

        score, possible, letter = _parse_score(raw)
        out.append(GradeRecord(
            assignment_title=title,
            score=score,
            points_possible=possible,
            letter=letter,
            raw=raw,
            posted_at=posted_at,
        ))
        seen_titles.add(title)
    return out


def _parse_classic(html: str) -> List[GradeRecord]:
    """Classic My Grades layout: div.row / tr.gradebook-row with .cell classes."""
    tree = HTMLParser(html)
    out: list[GradeRecord] = []
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

        score, possible, letter = _parse_score(raw)

        # Date inside this row, but ignore matches that are part of the grade ratio.
        row_text = row.text(separator=" ", strip=True) or ""
        posted_at = None
        for m in _DATE_RE.finditer(row_text):
            candidate = m.group(1)
            if candidate in raw:
                continue
            posted_at = parse_dt(candidate)
            if posted_at:
                break

        out.append(GradeRecord(
            assignment_title=title,
            score=score,
            points_possible=possible,
            letter=letter,
            raw=raw,
            posted_at=posted_at,
        ))
    return out


async def fetch_grades(ctx: BrowserContext, course_blackboard_id: str) -> List[GradeRecord]:
    base = settings.BLACKBOARD_URL.rstrip("/")
    page = await ctx.new_page()
    try:
        # Try both layouts; merge results, deduping by title.
        results: dict[str, GradeRecord] = {}
        for path in (
            f"/ultra/courses/{course_blackboard_id}/gradebook/student",
            f"/webapps/bb-mygrades-bb_bb60/myGrades?course_id={course_blackboard_id}&stream_name=mygrades",
        ):
            try:
                await page.goto(base + path, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_load_state("networkidle", timeout=15_000)
                html = await page.content()
            except Exception:
                continue
            if not html:
                continue
            parsed = _parse_ultra(html) + _parse_classic(html)
            for rec in parsed:
                if rec.assignment_title not in results:
                    results[rec.assignment_title] = rec
                else:
                    # Prefer the one with a posted_at if the existing one is null.
                    existing = results[rec.assignment_title]
                    if existing.posted_at is None and rec.posted_at is not None:
                        results[rec.assignment_title] = rec
        return list(results.values())
    finally:
        await page.close()
