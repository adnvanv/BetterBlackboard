from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app import views
from app.config import settings
from app.db import engine, init_db
from app.models import ScrapeRun, utcnow

log = logging.getLogger("app.main")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

app = FastAPI(title="BetterBlackboard")
_scheduler = None


@app.on_event("startup")
def _startup() -> None:
    init_db()
    _start_scheduler()


@app.on_event("shutdown")
def _shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass


def _start_scheduler() -> None:
    """Set up the daily auto-scrape if BB_SCHEDULE is configured."""
    global _scheduler
    if not settings.BB_SCHEDULE:
        log.info("BB_SCHEDULE empty — auto-scrape disabled.")
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.warning("APScheduler not installed — skipping schedule.")
        return

    parts = settings.BB_SCHEDULE.split()
    if len(parts) != 5:
        log.error("BB_SCHEDULE must be cron-style (5 fields), got %r", settings.BB_SCHEDULE)
        return
    minute, hour, dom, month, dow = parts

    sched = AsyncIOScheduler(timezone=settings.BB_TIMEZONE)
    sched.add_job(
        _scheduled_scrape,
        CronTrigger(minute=minute, hour=hour, day=dom, month=month, day_of_week=dow,
                    timezone=settings.BB_TIMEZONE),
        id="daily-scrape",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    sched.start()
    _scheduler = sched
    log.info("Daily scrape scheduled: '%s' (%s)", settings.BB_SCHEDULE, settings.BB_TIMEZONE)


async def _scheduled_scrape() -> None:
    """Cron-fired wrapper. Creates a ScrapeRun row then runs the pipeline."""
    log.info("Scheduled scrape firing.")
    with Session(engine) as s:
        run = ScrapeRun(started_at=utcnow(), status="running")
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
    await _run_scrape_async(run_id)


def get_session() -> Session:
    with Session(engine) as s:
        yield s


# ---------- JSON API ----------

@app.get("/api/dashboard")
def api_dashboard(session: Session = Depends(get_session)):
    return {
        "upcoming": views.upcoming(session),
        "recentGrades": views.recent_grade_rows(session),
        "recentAnnouncements": views.recent_announcements(session, limit=8),
        "health": views.health(session),
    }


@app.get("/api/assignments")
def api_assignments(
    course_id: Optional[int] = Query(None, alias="courseId"),
    status: str = "all",
    session: Session = Depends(get_session),
):
    return views.list_assignments(session, course_id=course_id, status=status)


@app.get("/api/announcements")
def api_announcements(
    course_id: Optional[int] = Query(None, alias="courseId"),
    session: Session = Depends(get_session),
):
    return views.list_announcements(session, course_id=course_id)


@app.get("/api/grades")
def api_grades(session: Session = Depends(get_session)):
    return views.grades_by_course(session)


@app.get("/api/courses")
def api_courses(session: Session = Depends(get_session)):
    return views.list_courses(session)


@app.get("/api/courses/{course_id}")
def api_course(course_id: int, session: Session = Depends(get_session)):
    detail = views.course_detail(session, course_id)
    if not detail:
        raise HTTPException(404, "Course not found")
    return detail


@app.get("/api/health")
def api_health(session: Session = Depends(get_session)):
    return views.health(session)


# ---------- Scrape trigger ----------

async def _run_scrape_async(run_id: int) -> None:
    """Background wrapper around pipeline.run_once(). pipeline.run_once() already
    creates its OWN ScrapeRun row; we update the placeholder row we made on the
    request thread so /api/health reflects the in-progress state immediately."""
    from scraper.pipeline import run_once

    try:
        await run_once()
        with Session(engine) as s:
            row = s.get(ScrapeRun, run_id)
            if row:
                row.status = "ok"
                row.finished_at = utcnow()
                # pipeline.run_once created its own row with the real course count;
                # mirror its status onto ours so the polling endpoint sees a final state.
                latest = s.exec(
                    select(ScrapeRun).order_by(ScrapeRun.started_at.desc())
                ).first()
                if latest and latest.id != run_id and latest.courses_scraped:
                    row.courses_scraped = latest.courses_scraped
                s.add(row)
                s.commit()
    except Exception as e:
        log.exception("Scrape failed")
        with Session(engine) as s:
            row = s.get(ScrapeRun, run_id)
            if row:
                row.status = "error"
                row.finished_at = utcnow()
                row.error = f"{e}\n{traceback.format_exc()}"
                s.add(row)
                s.commit()


@app.post("/api/scrape")
async def api_scrape(session: Session = Depends(get_session)):
    """Kick off a scrape in the background. Returns immediately with the run id.
    Returns 409 if another scrape started within the last 30 minutes is still running."""
    cutoff = utcnow() - timedelta(minutes=30)
    in_flight = session.exec(
        select(ScrapeRun)
        .where(ScrapeRun.status == "running")
        .where(ScrapeRun.started_at >= cutoff)
        .order_by(ScrapeRun.started_at.desc())
    ).first()
    if in_flight:
        return JSONResponse(
            {"started": False, "reason": "already-running", "runId": in_flight.id},
            status_code=409,
        )

    run = ScrapeRun(started_at=utcnow(), status="running")
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = run.id

    asyncio.create_task(_run_scrape_async(run_id))
    return JSONResponse({"started": True, "runId": run_id}, status_code=202)


# ---------- Session-cookie upload (used by login_client GUI) ----------

def _require_upload_token(x_upload_token: Optional[str] = Header(default=None)) -> None:
    expected = settings.BB_UPLOAD_TOKEN
    if not expected:
        raise HTTPException(503, "Upload endpoint disabled: BB_UPLOAD_TOKEN not set on the server.")
    if not x_upload_token or not secrets.compare_digest(x_upload_token, expected):
        raise HTTPException(401, "Bad or missing X-Upload-Token header.")


@app.post("/api/admin/session", dependencies=[Depends(_require_upload_token)])
async def api_upload_session(file: UploadFile = File(...)):
    """Receive a fresh storage_state.json from the login_client GUI and atomically
    replace the on-disk file the scraper reads."""
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "Payload too large.")
    # Validate it parses as JSON and looks like a Playwright storage_state.
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "Body is not valid JSON.")
    if not isinstance(payload, dict) or "cookies" not in payload:
        raise HTTPException(400, "JSON does not look like a Playwright storage_state (missing 'cookies').")

    dest = settings.BB_STORAGE_STATE
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    # Atomic replace via tempfile in the same directory.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(dest)) or ".", prefix=".storage_state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        os.replace(tmp, dest)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    return {"ok": True, "bytes": len(raw), "cookies": len(payload.get("cookies", []))}


# ---------- Static SPA (only if built) ----------

if (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # Don't shadow the API.
        if full_path.startswith("api/"):
            raise HTTPException(404)
        # Serve known files (favicon etc.) if they exist; otherwise SPA fallback.
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
