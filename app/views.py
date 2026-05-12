"""Query helpers. Each returns plain dicts so they can be fed to Pydantic
response models in app.main."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select


# Strip embedded "Due: ..." sub-text and trailing type label chip that the
# scraper accidentally concatenates into assignment titles.
_DUE_INLINE = re.compile(r"\s*Due:\s*[A-Za-z]+\s*\d{1,2},?\s*\d{4}.*$", re.IGNORECASE)
_TYPE_TRAIL = re.compile(
    r"(?:Assignment|Quiz|Exam|Test|Discussion|Survey|Project)\s*$",
    re.IGNORECASE,
)


def clean_title(s: str | None) -> str:
    if not s:
        return s or ""
    s = _DUE_INLINE.sub("", s)
    s = _TYPE_TRAIL.sub("", s).rstrip()
    return s


def _is_new_grade(session: Session, latest: "Grade", week_ago: datetime) -> bool:
    """A grade row is shown as 'new' iff (a) it was scraped in the last week AND
    (b) there exists a prior reading for the same assignment with a different score.
    This avoids labelling every row 'new' on the first ever scrape."""
    if latest.scraped_at < week_ago:
        return False
    prior = session.exec(
        select(Grade)
        .where(Grade.assignment_id == latest.assignment_id)
        .where(Grade.id != latest.id)
        .order_by(Grade.scraped_at.desc())
    ).first()
    if not prior:
        return False
    return (
        prior.score != latest.score
        or prior.raw != latest.raw
        or prior.letter != latest.letter
    )

from app.models import (
    Announcement,
    Assignment,
    CalendarEvent,
    Course,
    Grade,
    ScrapeRun,
)


def _course_dict(c: Course) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "code": c.code,
        "term": c.term,
        "url": c.url,
    }


def urgency_class(when: datetime) -> str:
    delta = when - datetime.utcnow()
    seconds = delta.total_seconds()
    if seconds < 24 * 3600:
        return "urgent"
    if seconds < 72 * 3600:
        return "soon"
    return "later"


def upcoming(session: Session, days: int = 14) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    horizon = now + timedelta(days=days)
    floor = now - timedelta(hours=12)
    items: list[dict[str, Any]] = []

    rows = session.exec(
        select(Assignment, Course)
        .join(Course, Course.id == Assignment.course_id)
        .where(Assignment.due_at != None)  # noqa: E711
        .where(Assignment.due_at <= horizon)
        .where(Assignment.due_at >= floor)
    ).all()
    for a, c in rows:
        items.append({
            "kind": "assignment",
            "id": a.id,
            "title": a.title,
            "when": a.due_at,
            "course": c.name,
            "courseId": c.id,
            "url": a.url,
            "urgency": urgency_class(a.due_at),
            "manual": (a.blackboard_id or "").startswith("manual:"),
        })

    events = session.exec(
        select(CalendarEvent, Course)
        .join(Course, Course.id == CalendarEvent.course_id, isouter=True)
        .where(CalendarEvent.starts_at != None)  # noqa: E711
        .where(CalendarEvent.starts_at <= horizon)
        .where(CalendarEvent.starts_at >= floor)
    ).all()
    for ev, c in events:
        items.append({
            "kind": "event",
            "title": ev.title,
            "when": ev.starts_at,
            "course": c.name if c else None,
            "courseId": c.id if c else None,
            "url": ev.url,
            "urgency": urgency_class(ev.starts_at),
        })

    items.sort(key=lambda x: x["when"])
    return items


def announcement_dict(ann: Announcement, course: Course | None) -> dict[str, Any]:
    return {
        "id": ann.id,
        "title": ann.title,
        "bodyHtml": ann.body_html,
        "postedAt": ann.posted_at,
        "author": ann.author,
        "course": course.name if course else None,
        "courseId": course.id if course else None,
    }


def recent_announcements(session: Session, limit: int = 10) -> list[dict[str, Any]]:
    rows = session.exec(
        select(Announcement, Course)
        .join(Course, Course.id == Announcement.course_id, isouter=True)
        .order_by(
            Announcement.posted_at.desc().nulls_last(),
            Announcement.first_seen_at.desc(),
            Announcement.id.desc(),
        )
        .limit(limit)
    ).all()
    return [announcement_dict(a, c) for a, c in rows]


def grades_by_course(session: Session) -> list[dict[str, Any]]:
    courses = session.exec(select(Course)).all()
    out: list[dict[str, Any]] = []
    week_ago = datetime.utcnow() - timedelta(days=7)
    for c in courses:
        assignments = session.exec(
            select(Assignment).where(Assignment.course_id == c.id)
        ).all()
        rows: list[dict[str, Any]] = []
        total_score = 0.0
        total_possible = 0.0
        for a in assignments:
            latest = session.exec(
                select(Grade)
                .where(Grade.assignment_id == a.id)
                .order_by(Grade.scraped_at.desc())
            ).first()
            if not latest:
                continue
            rows.append({
                "title": clean_title(a.title),
                "dueAt": a.due_at,
                "postedAt": latest.posted_at,
                "score": latest.score,
                "possible": latest.points_possible,
                "letter": latest.letter,
                "raw": latest.raw,
                "isNew": _is_new_grade(session, latest, week_ago),
                "scrapedAt": latest.scraped_at,
            })
            if latest.score is not None and latest.points_possible:
                total_score += latest.score
                total_possible += latest.points_possible
        if not rows:
            continue
        avg = (total_score / total_possible * 100) if total_possible else None
        out.append({
            "course": _course_dict(c),
            "averagePct": avg,
            "rows": rows,
        })
    return out


def recent_grade_rows(
    session: Session,
    limit: int = 15,
    per_course: int = 3,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Latest entered grades across all courses, with per-course balancing.

    Pulling strictly by due_at across the whole table tends to fill the limit
    with one course that has lots of due-dated assignments (the others often
    have NULL due_at because the parser couldn't extract a date from their
    page). Instead, take the top `per_course` grades from each course, then
    sort the union and crop to `limit`. Gives a mix across courses.
    """
    week_ago = datetime.utcnow() - timedelta(days=days)
    picks: list[tuple[Grade, Assignment, Course]] = []
    courses = session.exec(select(Course)).all()
    far_past = datetime.min

    def _grade_rank(g: Grade, a: Assignment) -> datetime:
        """Time used to rank: posted_at if Blackboard exposed one, else the
        assignment's due_at, else scraped_at as a last resort."""
        return g.posted_at or a.due_at or g.scraped_at or far_past

    for course in courses:
        assignments = session.exec(
            select(Assignment).where(Assignment.course_id == course.id)
        ).all()
        course_rows: list[tuple[Grade, Assignment, Course]] = []
        for a in assignments:
            latest = session.exec(
                select(Grade)
                .where(Grade.assignment_id == a.id)
                .order_by(Grade.scraped_at.desc())
            ).first()
            if not latest:
                continue
            course_rows.append((latest, a, course))
        # Pick the top `per_course` from this course by our rank, newest first.
        course_rows.sort(key=lambda t: _grade_rank(t[0], t[1]), reverse=True)
        picks.extend(course_rows[:per_course])

    # Sort union of picks globally so the dashboard's order is consistent.
    picks.sort(key=lambda t: _grade_rank(t[0], t[1]), reverse=True)
    picks = picks[:limit]

    return [{
        "title": f"{clean_title(a.title)} — {c.name}",
        "dueAt": a.due_at,
        "postedAt": g.posted_at,
        "score": g.score,
        "possible": g.points_possible,
        "letter": g.letter,
        "raw": g.raw,
        "isNew": _is_new_grade(session, g, week_ago),
        "scrapedAt": g.scraped_at,
    } for g, a, c in picks]


def list_assignments(session: Session, course_id: int | None = None,
                     status: str = "all") -> list[dict[str, Any]]:
    now = datetime.utcnow()
    q = select(Assignment, Course).join(Course, Course.id == Assignment.course_id)
    if course_id is not None:
        q = q.where(Assignment.course_id == course_id)
    if status == "upcoming":
        q = q.where(Assignment.due_at != None).where(Assignment.due_at >= now)  # noqa: E711
    elif status == "past":
        q = q.where(Assignment.due_at != None).where(Assignment.due_at < now)  # noqa: E711
    q = q.order_by(Assignment.due_at.asc().nulls_last())
    rows = session.exec(q).all()
    return [{
        "id": a.id,
        "title": a.title,
        "dueAt": a.due_at,
        "pointsPossible": a.points_possible,
        "url": a.url,
        "course": c.name,
        "courseId": c.id,
        "manual": (a.blackboard_id or "").startswith("manual:"),
    } for a, c in rows]


def list_announcements(session: Session, course_id: int | None = None) -> list[dict[str, Any]]:
    q = select(Announcement, Course).join(Course, Course.id == Announcement.course_id, isouter=True)
    if course_id is not None:
        q = q.where(Announcement.course_id == course_id)
    q = q.order_by(
        Announcement.posted_at.desc().nulls_last(),
        Announcement.first_seen_at.desc(),
        Announcement.id.desc(),
    )
    return [announcement_dict(a, c) for a, c in session.exec(q).all()]


def list_courses(session: Session) -> list[dict[str, Any]]:
    return [_course_dict(c) for c in session.exec(select(Course).order_by(Course.name)).all()]


def course_detail(session: Session, course_id: int) -> dict[str, Any] | None:
    course = session.get(Course, course_id)
    if not course:
        return None
    return {
        "course": _course_dict(course),
        "assignments": list_assignments(session, course_id=course_id, status="all"),
        "announcements": list_announcements(session, course_id=course_id),
        "gradeGroups": [g for g in grades_by_course(session) if g["course"]["id"] == course_id],
    }


def health(session: Session) -> dict[str, Any]:
    from app import progress as _progress

    run = session.exec(select(ScrapeRun).order_by(ScrapeRun.started_at.desc())).first()
    snap = _progress.snapshot()
    base = {"progress": snap}
    if not run:
        return {**base, "status": "no-runs", "coursesScraped": 0}
    return {
        **base,
        "status": run.status,
        "startedAt": run.started_at,
        "finishedAt": run.finished_at,
        "coursesScraped": run.courses_scraped,
        "error": run.error,
    }
