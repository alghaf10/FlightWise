"""SQLite database engine & session lifecycle."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _REPO_ROOT / "flightwise.db"
SQLITE_URL = f"sqlite:///{_DB_PATH.resolve().as_posix()}"

connect_args = {"check_same_thread": False}
engine = create_engine(SQLITE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    from app import db_models  # noqa: F401

    _recreate_if_schema_is_stale()
    SQLModel.metadata.create_all(engine)


def _recreate_if_schema_is_stale() -> None:
    """Small MVP migration: recreate roster DB if older local schema is detected."""
    insp = inspect(engine)
    if not insp.has_table("students"):
        return
    required = {
        "students": {
            "id",
            "name",
            "stage",
            "lessons_completed",
            "hours_total",
            "last_lesson_days_ago",
            "readiness_score",
            "priority",
            "weak_maneuvers",
            "active",
        },
        "instructors": {"id", "name", "ratings", "availability", "max_daily_blocks", "active"},
        "aircraft": {
            "id",
            "tail_number",
            "type",
            "hours_since_inspection",
            "maintenance_due_hours",
            "reliability_score",
            "maintenance_status",
            "dispatchable",
            "active",
        },
        "time_slots": {"id", "label", "start", "end", "active"},
    }
    stale = False
    for table, cols in required.items():
        if not insp.has_table(table):
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        if not cols.issubset(existing):
            stale = True
            break
    if stale:
        SQLModel.metadata.drop_all(engine)


def get_session() -> Generator[Session, None, None]:
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
