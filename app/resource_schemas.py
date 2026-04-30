"""Pydantic shapes for REST resources (distinct from planner `FlightWiseInput`)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models import WeatherSnapshot


class StudentCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=96)
    name: str = Field(..., max_length=200)
    stage: str = Field(default="private", max_length=64)
    lessons_completed: int = Field(default=0, ge=0)
    hours_total: float = Field(default=0.0, ge=0)
    last_lesson_days_ago: int | None = Field(default=None, ge=0)
    readiness_score: float = Field(default=0.65, ge=0, le=1)
    priority: int = Field(default=50, ge=0, le=100)
    weak_maneuvers: list[str] = Field(default_factory=list)
    active: bool = True


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    stage: str | None = Field(default=None, max_length=64)
    lessons_completed: int | None = Field(default=None, ge=0)
    hours_total: float | None = Field(default=None, ge=0)
    last_lesson_days_ago: int | None = Field(default=None, ge=0)
    readiness_score: float | None = Field(default=None, ge=0, le=1)
    priority: int | None = Field(default=None, ge=0, le=100)
    weak_maneuvers: list[str] | None = None
    active: bool | None = None


class InstructorCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=96)
    name: str = Field(..., max_length=200)
    ratings: list[str] = Field(default_factory=lambda: ["cfi", "private"])
    availability: dict[str, list[str]] = Field(
        ...,
        description="Map time_slot.id → aircraft ids allowed or ['any']",
    )
    max_daily_blocks: int | None = Field(default=6, ge=1, le=24)
    active: bool = True


class InstructorUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    ratings: list[str] | None = None
    availability: dict[str, list[str]] | None = None
    max_daily_blocks: int | None = Field(default=None, ge=1, le=24)
    active: bool | None = None


class AircraftCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=96)
    tail_number: str = Field(..., max_length=32)
    type: str = Field(default="C172", max_length=64)
    reliability_score: float = Field(default=0.88, ge=0.05, le=1)
    maintenance_status: str = Field(default="ok", max_length=64)
    dispatchable: bool = True
    hours_since_inspection: float = Field(default=40.0, ge=0.0)
    maintenance_due_hours: float | None = Field(default=100.0, ge=0.0)
    active: bool = True


class AircraftUpdate(BaseModel):
    tail_number: str | None = Field(default=None, max_length=32)
    type: str | None = Field(default=None, max_length=64)
    reliability_score: float | None = Field(default=None, ge=0.05, le=1)
    maintenance_status: str | None = Field(default=None, max_length=64)
    dispatchable: bool | None = None
    hours_since_inspection: float | None = Field(default=None, ge=0.0)
    maintenance_due_hours: float | None = Field(default=None, ge=0.0)
    active: bool | None = None


class TimeSlotCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=96)
    label: str = Field(default="", max_length=200)
    start: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM")
    end: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM")
    active: bool = True


class TimeSlotUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    active: bool | None = None


class PlanFromSelectionBody(BaseModel):
    student_ids: list[str] = Field(..., min_length=1)
    instructor_ids: list[str] = Field(..., min_length=1)
    aircraft_ids: list[str] = Field(..., min_length=1)
    time_slot_ids: list[str] = Field(..., min_length=1)
    date: str = Field(default="2026-04-16", description="YYYY-MM-DD")
    time: str | None = Field(default=None, description="HH:MM")
    weather_mode: str = Field(
        default="manual",
        description="`auto` uses `metar_taf_station` with manual weather fallback; `manual` uses `weather` only.",
    )
    weather: WeatherSnapshot | None = Field(
        None,
        description="Baseline manual weather when not using METAR/TAF exclusively.",
    )
    weather_by_slot: dict[str, dict[str, Any]] | None = None
    metar_taf_station: str | None = Field(
        None,
        description="Optional ICAO; when set, AWC METAR/TAF fill weather slots.",
        examples=["KAPA"],
    )
