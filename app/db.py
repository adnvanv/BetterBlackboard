import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# Make sure the parent directory exists (e.g. /data when running in Docker).
_db_parent = os.path.dirname(os.path.abspath(settings.BB_DB_PATH))
if _db_parent:
    os.makedirs(_db_parent, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.BB_DB_PATH}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    # Import models so SQLModel.metadata sees them.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate_columns()


def _migrate_columns() -> None:
    """Small in-place migrator for SQLite: add columns that were introduced
    after the DB was first created. SQLAlchemy's `create_all` doesn't ALTER
    existing tables. Each entry is (table, column, type)."""
    additions: list[tuple[str, str, str]] = [
        ("grade", "posted_at", "DATETIME"),
    ]
    with engine.begin() as conn:
        for table, column, coltype in additions:
            existing = {
                row[1]  # name column from PRAGMA table_info
                for row in conn.exec_driver_sql(f'PRAGMA table_info("{table}")').fetchall()
            }
            if column not in existing:
                conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {coltype}')


@contextmanager
def session_scope() -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
