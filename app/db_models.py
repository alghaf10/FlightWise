"""SQLModel persistence for MVP (SQLite only)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, String, Text
from sqlmodel import Field, SQLModel


class DbStudent(SQLModel, table=True):
    __tablename__ = "students"

    id: str = Field(primary_key=True, max_length=96)
    name: str = Field(max_length=200)
    training_stage: str = Field(default="private", sa_column=Column("stage", String(64), nullable=False))
    lessons_completed: int = Field(default=0, ge=0)
    hours_total: float = Field(default=0.0, ge=0)
    last_lesson_days_ago: int | None = Field(default=None, ge=0)
    readiness_score: float = Field(default=0.65, ge=0.0, le=1.0)
    priority: int = Field(default=50, ge=0, le=100)
    weak_maneuvers_json: str = Field(
        default="[]",
        sa_column=Column("weak_maneuvers", Text, nullable=False),
    )
    active: bool = Field(default=True)


class DbInstructor(SQLModel, table=True):
    __tablename__ = "instructors"

    id: str = Field(primary_key=True, max_length=96)
    name: str = Field(max_length=200)
    certifications_json: str = Field(default='["cfi","private"]', sa_column=Column("ratings", Text))
    availability_json: str = Field(default="{}", sa_column=Column("availability", Text))
    max_daily_blocks: int | None = Field(default=6, ge=1, le=24)
    active: bool = Field(default=True)


class DbAircraft(SQLModel, table=True):
    __tablename__ = "aircraft"

    id: str = Field(primary_key=True, max_length=96)
    tail_number: str = Field(max_length=32)
    aircraft_type: str = Field(default="C172", sa_column=Column("type", String(64), nullable=False))
    reliability_score: float = Field(default=0.88, ge=0.05, le=1.0)
    maintenance_status: str = Field(default="ok", max_length=64)
    dispatchable: bool = Field(default=True)
    hours_since_inspection: float = Field(default=40.0, ge=0.0)
    maintenance_due_hours: float | None = Field(default=100.0, ge=0.0)
    active: bool = Field(default=True)


class DbTimeSlot(SQLModel, table=True):
    __tablename__ = "time_slots"

    id: str = Field(primary_key=True, max_length=96)
    label: str = Field(default="", max_length=200)
    start: str = Field(max_length=8)
    end: str = Field(max_length=8)
    active: bool = Field(default=True)


class DailyPlanSnapshot(SQLModel, table=True):
    """Optional audit log of selections + weather keyed by date."""

    __tablename__ = "daily_plan_snapshots"

    id: int | None = Field(default=None, primary_key=True)
    scheduled_date: str = Field(max_length=16)
    selection_json: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
