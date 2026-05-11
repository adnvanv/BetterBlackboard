from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.utcnow()


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    blackboard_id: str = Field(index=True, unique=True)
    name: str
    code: Optional[str] = None
    term: Optional[str] = None
    url: Optional[str] = None
    first_seen_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class Assignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    blackboard_id: str = Field(index=True)
    title: str
    due_at: Optional[datetime] = None
    points_possible: Optional[float] = None
    url: Optional[str] = None
    first_seen_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class Announcement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: Optional[int] = Field(default=None, foreign_key="course.id", index=True)
    blackboard_id: str = Field(index=True)
    title: str
    body_html: Optional[str] = None
    posted_at: Optional[datetime] = None
    author: Optional[str] = None
    first_seen_at: datetime = Field(default_factory=utcnow)


class Grade(SQLModel, table=True):
    """Append-only: each scrape that sees a different score writes a new row."""

    id: Optional[int] = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="assignment.id", index=True)
    score: Optional[float] = None
    points_possible: Optional[float] = None
    letter: Optional[str] = None
    raw: Optional[str] = None
    scraped_at: datetime = Field(default_factory=utcnow)


class CalendarEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: Optional[int] = Field(default=None, foreign_key="course.id", index=True)
    blackboard_id: str = Field(index=True, unique=True)
    title: str
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    kind: Optional[str] = None
    url: Optional[str] = None
    first_seen_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class ScrapeRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None
    status: str = "running"
    error: Optional[str] = None
    courses_scraped: int = 0
