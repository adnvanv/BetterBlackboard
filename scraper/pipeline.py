"""Orchestrate per-course scrapes and persist to the DB."""
from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime

from sqlmodel import select

from app.config import settings
from app.db import init_db, session_scope
from app.models import (
    Announcement,
    Assignment,
    CalendarEvent,
    Course,
    Grade,
    ScrapeRun,
    utcnow,
)
from scraper.announcements import fetch_announcements
from scraper.assignments import fetch_assignments
from scraper.calendar import fetch_calendar
from scraper.courses import fetch_courses
from scraper.grades import fetch_grades
from scraper.login import ensure_logged_in
from scraper.session import browser_context

log = logging.getLogger("scraper.pipeline")


async def _scrape_course(ctx, course_bb_id: str):
    """Run all per-course scrapers concurrently for one course."""
    return await asyncio.gather(
        fetch_assignments(ctx, course_bb_id),
        fetch_announcements(ctx, course_bb_id),
        fetch_grades(ctx, course_bb_id),
        return_exceptions=True,
    )


def _upsert_course(session, rec) -> Course:
    existing = session.exec(
        select(Course).where(Course.blackboard_id == rec.blackboard_id)
    ).first()
    now = utcnow()
    if existing:
        existing.name = rec.name
        existing.code = rec.code or existing.code
        existing.term = rec.term or existing.term
        existing.url = rec.url or existing.url
        existing.last_seen_at = now
        session.add(existing)
        return existing
    course = Course(
        blackboard_id=rec.blackboard_id,
        name=rec.name,
        code=rec.code,
        term=rec.term,
        url=rec.url,
    )
    session.add(course)
    session.flush()
    return course


def _upsert_assignment(session, course_id: int, rec) -> Assignment:
    existing = session.exec(
        select(Assignment).where(
            Assignment.course_id == course_id,
            Assignment.blackboard_id == rec.blackboard_id,
        )
    ).first()
    if existing:
        existing.title = rec.title
        if rec.due_at:
            existing.due_at = rec.due_at
        if rec.points_possible is not None:
            existing.points_possible = rec.points_possible
        if rec.url:
            existing.url = rec.url
        existing.last_seen_at = utcnow()
        session.add(existing)
        return existing
    a = Assignment(
        course_id=course_id,
        blackboard_id=rec.blackboard_id,
        title=rec.title,
        due_at=rec.due_at,
        points_possible=rec.points_possible,
        url=rec.url,
    )
    session.add(a)
    session.flush()
    return a


def _upsert_announcement(session, course_id: int | None, rec) -> None:
    existing = session.exec(
        select(Announcement).where(Announcement.blackboard_id == rec.blackboard_id)
    ).first()
    if existing:
        return
    session.add(Announcement(
        course_id=course_id,
        blackboard_id=rec.blackboard_id,
        title=rec.title,
        body_html=rec.body_html,
        posted_at=rec.posted_at,
        author=rec.author,
    ))


def _record_grade(session, course_id: int, rec) -> None:
    """Match grade to an assignment by title within the course; append a Grade row only if changed."""
    assignment = session.exec(
        select(Assignment).where(
            Assignment.course_id == course_id,
            Assignment.title == rec.assignment_title,
        )
    ).first()
    if not assignment:
        # Create a stub assignment so we can attach the grade.
        assignment = Assignment(
            course_id=course_id,
            blackboard_id=f"grade-stub::{rec.assignment_title}",
            title=rec.assignment_title,
            due_at=getattr(rec, "posted_at", None),
        )
        session.add(assignment)
        session.flush()
    else:
        # If the assignments-page scraper couldn't extract a due date but the
        # grade row gave us one, backfill it. This is what powers the
        # chronological ordering on the dashboard for Ultra courses.
        rec_dt = getattr(rec, "posted_at", None)
        if rec_dt is not None and assignment.due_at is None:
            assignment.due_at = rec_dt
            session.add(assignment)

    last = session.exec(
        select(Grade)
        .where(Grade.assignment_id == assignment.id)
        .order_by(Grade.scraped_at.desc())
    ).first()
    new_posted_at = getattr(rec, "posted_at", None)
    if last and last.score == rec.score and last.letter == rec.letter and last.raw == rec.raw:
        # Score didn't change. But if we now have a posted_at (e.g., after we
        # added that field) and the stored row doesn't, backfill it so the
        # "Latest grades" ranking can use it.
        if new_posted_at is not None and last.posted_at is None:
            last.posted_at = new_posted_at
            session.add(last)
        return
    session.add(Grade(
        assignment_id=assignment.id,
        score=rec.score,
        points_possible=rec.points_possible,
        letter=rec.letter,
        raw=rec.raw,
        posted_at=new_posted_at,
    ))


def _upsert_calendar(session, rec, course_lookup: dict[str, int]) -> None:
    course_id = course_lookup.get(rec.course_blackboard_id) if rec.course_blackboard_id else None
    existing = session.exec(
        select(CalendarEvent).where(CalendarEvent.blackboard_id == rec.blackboard_id)
    ).first()
    now = utcnow()
    if existing:
        existing.title = rec.title
        existing.starts_at = rec.starts_at or existing.starts_at
        existing.ends_at = rec.ends_at or existing.ends_at
        existing.kind = rec.kind or existing.kind
        existing.url = rec.url or existing.url
        if course_id is not None:
            existing.course_id = course_id
        existing.last_seen_at = now
        session.add(existing)
        return
    session.add(CalendarEvent(
        course_id=course_id,
        blackboard_id=rec.blackboard_id,
        title=rec.title,
        starts_at=rec.starts_at,
        ends_at=rec.ends_at,
        kind=rec.kind,
        url=rec.url,
    ))


async def run_once() -> int:
    """Run one full scrape. Returns number of courses scraped."""
    from app import progress

    init_db()

    with session_scope() as s:
        run = ScrapeRun(started_at=utcnow(), status="running")
        s.add(run)
        s.flush()
        run_id = run.id

    progress.reset(run_id)
    courses_scraped = 0
    try:
        progress.set_stage("Logging in")
        async with browser_context() as (_browser, ctx):
            await ensure_logged_in(ctx)
            progress.set_stage("Listing courses")
            course_records = await fetch_courses(ctx)
            progress.set_totals(len(course_records))

            with session_scope() as s:
                course_id_by_bb: dict[str, int] = {}
                for cr in course_records:
                    c = _upsert_course(s, cr)
                    course_id_by_bb[cr.blackboard_id] = c.id

            sem = asyncio.Semaphore(settings.BB_SCRAPE_CONCURRENCY)
            name_by_bb = {cr.blackboard_id: cr.name for cr in course_records}
            done_counter = {"n": 0}

            async def with_sem(bb_id):
                async with sem:
                    progress.set_stage("Scraping", detail=name_by_bb.get(bb_id, bb_id))
                    res = await _scrape_course(ctx, bb_id)
                    done_counter["n"] += 1
                    progress.step(done_counter["n"], detail=name_by_bb.get(bb_id, bb_id))
                    return bb_id, res

            tasks = [with_sem(cr.blackboard_id) for cr in course_records]
            results = await asyncio.gather(*tasks)

            with session_scope() as s:
                # Refresh lookup with fresh session.
                for cr in course_records:
                    course = s.exec(
                        select(Course).where(Course.blackboard_id == cr.blackboard_id)
                    ).first()
                    if course:
                        course_id_by_bb[cr.blackboard_id] = course.id

                for bb_id, three in results:
                    course_id = course_id_by_bb.get(bb_id)
                    if course_id is None:
                        continue
                    assignments_res, announcements_res, grades_res = three

                    if not isinstance(assignments_res, Exception):
                        for a in assignments_res:
                            _upsert_assignment(s, course_id, a)
                        s.flush()
                    else:
                        log.warning("assignments failed for %s: %s", bb_id, assignments_res)

                    if not isinstance(announcements_res, Exception):
                        for ann in announcements_res:
                            _upsert_announcement(s, course_id, ann)
                    else:
                        log.warning("announcements failed for %s: %s", bb_id, announcements_res)

                    if not isinstance(grades_res, Exception):
                        for g in grades_res:
                            _record_grade(s, course_id, g)
                    else:
                        log.warning("grades failed for %s: %s", bb_id, grades_res)

                    courses_scraped += 1

            progress.set_stage("Calendar")
            calendar_records = await fetch_calendar(ctx)
            with session_scope() as s:
                for cr in calendar_records:
                    _upsert_calendar(s, cr, course_id_by_bb)

        with session_scope() as s:
            run = s.get(ScrapeRun, run_id)
            run.finished_at = utcnow()
            run.status = "ok"
            run.courses_scraped = courses_scraped
            s.add(run)
        progress.finish(True, f"Scraped {courses_scraped} course(s).")
        return courses_scraped
    except Exception as e:
        with session_scope() as s:
            run = s.get(ScrapeRun, run_id)
            if run:
                run.finished_at = utcnow()
                run.status = "error"
                run.error = f"{e}\n{traceback.format_exc()}"
                s.add(run)
        progress.finish(False, str(e))
        raise
