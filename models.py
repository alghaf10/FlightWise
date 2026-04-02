"""Pydantic models for API and internal data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TimeSlot(BaseModel):
    """One schedulable block; `start` / `end` are local or UTC strings `HH:MM` (METAR/TAF mode uses UTC)."""

    id: str = Field(..., description="Stable ID referenced by instructor `availability`.")
    start: str = Field(..., examples=["09:00"], description="Start time `HH:MM`.")
    end: str = Field(..., examples=["11:00"], description="End time `HH:MM`.")
    label: str | None = Field(None, description="Human label shown in API output.")


class WeatherSnapshot(BaseModel):
    """Manual weather; optional if `metar_taf_station` fills METAR/TAF."""

    wind_kts: float | None = Field(None, description="Sustained wind (knots).")
    visibility_sm: float | None = Field(None, description="Visibility in statute miles.")
    ceiling_ft: int | None = Field(None, description="Ceiling AGL/MSL context as in your ops (feet).")
    precipitation: bool = Field(False, description="Precipitation present.")
    notes: str | None = Field(None, description="Free-text note.")


class Student(BaseModel):
    id: str = Field(..., description="Unique student id.")
    name: str = Field(..., description="Display name.")
    stage: str = Field(
        "private",
        description="Training stage: e.g. `private`, `instrument`, `commercial`.",
    )
    lessons_completed: int = Field(0, ge=0)
    hours_total: float = Field(0.0, ge=0)
    last_lesson_days_ago: int | None = Field(
        None, description="Days since last lesson; affects readiness scoring."
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque key/values for future rules (ignored by core MVP).",
    )


class Instructor(BaseModel):
    id: str
    name: str
    ratings: list[str] = Field(
        default_factory=list,
        description="e.g. `cfi`, `private`, `instrument`, `commercial`.",
    )
    availability: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map `time_slot_id` → list of `aircraft.id` allowed, or `['any']`.",
    )


class Aircraft(BaseModel):
    id: str
    tail_number: str
    type: str = Field("single_engine", description="Aircraft category label.")
    maintenance_due_hours: float | None = Field(
        None, description="If set, hours remaining until maintenance due."
    )
    hours_since_inspection: float = Field(0.0, ge=0)
    constraints: dict[str, Any] = Field(default_factory=dict)


class LessonType(BaseModel):
    id: str
    name: str
    min_stage: str = Field("private", description="Minimum student stage for this lesson.")
    suitable_stages: list[str] = Field(
        default_factory=list,
        description="Stages for which this lesson is appropriate.",
    )


FLIGHTWISE_INPUT_EXAMPLE: dict[str, Any] = {
    "date": "2026-04-01",
    "time_slots": [
        {"id": "am", "start": "09:00", "end": "11:00", "label": "Morning block"},
        {"id": "pm", "start": "13:00", "end": "15:00", "label": "Afternoon block"},
    ],
    "weather": {
        "wind_kts": 12,
        "visibility_sm": 10,
        "ceiling_ft": 5500,
        "precipitation": False,
    },
    "students": [
        {
            "id": "stu_1",
            "name": "Alex Rivera",
            "stage": "private",
            "lessons_completed": 8,
            "hours_total": 12.5,
            "last_lesson_days_ago": 5,
        },
        {
            "id": "stu_2",
            "name": "Sam Okonkwo",
            "stage": "private",
            "lessons_completed": 3,
            "hours_total": 5.0,
            "last_lesson_days_ago": 18,
        },
    ],
    "instructors": [
        {
            "id": "ins_1",
            "name": "Jordan Lee",
            "ratings": ["cfi", "private"],
            "availability": {"am": ["any"], "pm": ["any"]},
        },
    ],
    "aircraft": [
        {
            "id": "ac_1",
            "tail_number": "N123AB",
            "type": "single_engine",
            "hours_since_inspection": 45.0,
            "maintenance_due_hours": 100.0,
        },
    ],
    "lesson_types": [],
}

GENERATE_PLAN_EXAMPLE: dict[str, Any] = {
    "status": "success",
    "summary": {
        "headline": "Scheduled 2 flight block(s)",
        "status_message": "All listed assignments satisfy weather, availability, and resource constraints.",
        "assigned_count": 2,
        "unassigned_count": 0,
        "total_students": 2,
        "notes": [],
    },
    "solver": {
        "optimization_status": "optimal",
        "solver_status": "OPTIMAL",
        "objective_value": 125000,
    },
    "assignments": [
        {
            "student_id": "stu_1",
            "instructor_id": "ins_1",
            "aircraft_id": "ac_1",
            "time_slot_id": "am",
            "lesson_type_id": "dual_vfr",
            "objective_value_contrib": None,
            "student_name": "Alex Rivera",
            "instructor_name": "Jordan Lee",
            "aircraft_tail": "N123AB",
            "time_slot_label": "Morning block",
            "lesson_type_name": None,
        }
    ],
    "unassigned_students": [],
    "explanations": ["Alex Rivera was scheduled because the optimizer weighed …"],
    "trace": None,
}


class FlightWiseInput(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [FLIGHTWISE_INPUT_EXAMPLE]},
    )

    date: str = Field(
        ...,
        description="Schedule day `YYYY-MM-DD` (with METAR/TAF, slot times align to AWC UTC day).",
        examples=["2026-04-15"],
    )
    time_slots: list[TimeSlot] = Field(..., min_length=1)
    weather: WeatherSnapshot | dict[str, WeatherSnapshot] | None = Field(
        None,
        description="Global or per-slot-id manual weather; ignored as source when `metar_taf_station` succeeds.",
    )
    weather_by_slot: dict[str, dict[str, Any]] | None = Field(
        None,
        description="Override fields per `time_slot.id` merged on top of global `weather`.",
    )
    metar_taf_station: str | None = Field(
        default=None,
        examples=["KSEA"],
        description=(
            "ICAO ID (e.g. KSEA). When set, METAR + TAF are fetched from "
            "aviationweather.gov and fill `weather` / `weather_by_slot` (slot times = UTC). "
            "Overlaps TAF forecast periods per time block."
        ),
    )
    students: list[Student] = Field(..., min_length=1)
    instructors: list[Instructor] = Field(..., min_length=1)
    aircraft: list[Aircraft] = Field(..., min_length=1)
    lesson_types: list[LessonType] = Field(
        default_factory=list,
        description="If empty, built-in defaults are used for lesson selection.",
    )


class AssignmentOut(BaseModel):
    student_id: str
    instructor_id: str
    aircraft_id: str
    time_slot_id: str
    lesson_type_id: str
    objective_value_contrib: float | None = None
    student_name: str | None = Field(None, description="Resolved from request for display.")
    instructor_name: str | None = None
    aircraft_tail: str | None = None
    time_slot_label: str | None = None
    lesson_type_name: str | None = None


class PlanSummary(BaseModel):
    """Short human-oriented summary of the run."""

    headline: str = Field(..., description="One-line outcome.")
    status_message: str = Field(..., description="What the status means for operators.")
    assigned_count: int = Field(..., ge=0)
    unassigned_count: int = Field(..., ge=0)
    total_students: int = Field(..., ge=0)
    notes: list[str] = Field(
        default_factory=list,
        description="Bullets (e.g. who was not scheduled).",
    )


class SolverMetrics(BaseModel):
    """CP-SAT optimizer result summary."""

    optimization_status: str | None = Field(
        None, description="Internal solver result label (e.g. optimal, feasible, infeasible)."
    )
    solver_status: str | None = Field(None, description="OR-Tools status name.")
    objective_value: int | None = Field(None, description="Maximized weighted objective (integer scale).")


class GeneratePlanResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [GENERATE_PLAN_EXAMPLE]},
    )

    status: str = Field(
        ...,
        description="`success`, `partial`, `infeasible`, or `error`.",
        examples=["success"],
    )
    summary: PlanSummary
    solver: SolverMetrics
    assignments: list[AssignmentOut]
    unassigned_students: list[str] = Field(
        ...,
        description="Student ids with no assignment after optimization.",
    )
    explanations: list[str] = Field(
        ...,
        description="One short explanation per assignment (template or LLM).",
    )
    trace: dict[str, Any] | None = Field(
        default=None,
        description="Agent outputs + raw METAR/TAF debug when used; for troubleshooting.",
    )
