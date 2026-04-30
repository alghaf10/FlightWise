"""Convert DB-backed selections into `FlightWiseInput` for the deterministic planner."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.db_models import DbAircraft, DbInstructor, DbStudent, DbTimeSlot, DailyPlanSnapshot
from app.models import Aircraft, FlightWiseInput, Instructor, LessonType, Student, TimeSlot, WeatherSnapshot
from app.resource_schemas import PlanFromSelectionBody

TRAINING_STAGE_TO_PLANNER_STAGE: dict[str, str] = {
    "pre-solo": "private",
    "cross-country": "private",
    "instrument": "instrument",
    "commercial": "commercial",
    "checkride prep": "commercial",
    "private": "private",
    "instrument trainee": "instrument",
}

DEFAULT_LESSONS: list[dict[str, Any]] = [
    {
        "id": "dual_vfr",
        "name": "Dual VFR proficiency",
        "min_stage": "private",
        "suitable_stages": ["private", "commercial"],
    },
    {
        "id": "pattern_work",
        "name": "Pattern / Traffic pattern",
        "min_stage": "private",
        "suitable_stages": ["private"],
    },
    {
        "id": "xc_dual",
        "name": "Cross-country dual",
        "min_stage": "private",
        "suitable_stages": ["private", "commercial"],
    },
    {
        "id": "ifr_vectors",
        "name": "IFR approaches / vectors",
        "min_stage": "instrument",
        "suitable_stages": ["instrument", "commercial"],
    },
    {
        "id": "commercial_maneuver",
        "name": "Commercial ACS maneuvers",
        "min_stage": "commercial",
        "suitable_stages": ["commercial"],
    },
    {
        "id": "prep_checkride",
        "name": "Checkride rehearsal",
        "min_stage": "commercial",
        "suitable_stages": ["commercial", "instrument"],
    },
]


def _stage_defaults(training_stage: str) -> tuple[int, float, int | None]:
    s = training_stage.lower().strip()
    if s in ("pre-solo",):
        return 4, 6.5, 5
    if s in ("cross-country",):
        return 16, 22.0, 4
    if s in ("instrument", "instrument trainee"):
        return 24, 48.0, 6
    if s in ("commercial",):
        return 12, 120.0, 3
    if s in ("checkride prep",):
        return 30, 95.0, 2
    return 10, 15.0, 7


def _map_planner_stage(training_stage: str) -> str:
    return TRAINING_STAGE_TO_PLANNER_STAGE.get(training_stage.lower().strip(), "private")


def _narrow_availability(
    avail: dict[str, list[str]],
    selected_slot_ids: set[str],
    selected_aircraft_ids: set[str],
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for sid in sorted(selected_slot_ids):
        slots = avail.get(sid)
        if not slots:
            continue
        allowed: list[str] = []
        for ent in slots:
            if str(ent).lower() == "any":
                allowed.extend(selected_aircraft_ids)
            elif ent in selected_aircraft_ids:
                allowed.append(ent)
        uniq = sorted({a for a in allowed if a in selected_aircraft_ids})
        if uniq:
            out[sid] = uniq
    return out


def _parse_json_array(raw: str) -> list[Any]:
    try:
        val = json.loads(raw or "[]")
        return val if isinstance(val, list) else []
    except json.JSONDecodeError:
        return []


def _parse_json_obj(raw: str) -> dict[str, Any]:
    try:
        val = json.loads(raw or "{}")
        return val if isinstance(val, dict) else {}
    except json.JSONDecodeError:
        return {}


def weather_default_dict() -> dict[str, Any]:
    return {
        "wind_kts": 10.0,
        "visibility_sm": 10.0,
        "ceiling_ft": 5000,
        "precipitation": False,
        "notes": "Manual baseline (database selection workflow)",
    }


def snapshot_selection(session: Session, body: PlanFromSelectionBody) -> None:
    snap = DailyPlanSnapshot(
        scheduled_date=body.date,
        selection_json=json.dumps(
            body.model_dump(),
            ensure_ascii=False,
        ),
    )
    session.add(snap)


def build_flightwise_input(session: Session, body: PlanFromSelectionBody, *, persist_snapshot: bool = True) -> FlightWiseInput:
    slot_set = set(body.time_slot_ids)
    student_id_set = set(body.student_ids)
    instructor_id_set = set(body.instructor_ids)
    aircraft_id_set = set(body.aircraft_ids)
    time_slot_set = set(body.time_slot_ids)

    stu_rows = [session.get(DbStudent, sid) for sid in body.student_ids]
    ins_rows = [session.get(DbInstructor, iid) for iid in body.instructor_ids]
    ac_rows = [session.get(DbAircraft, aid) for aid in body.aircraft_ids]
    ts_rows = [session.get(DbTimeSlot, tid) for tid in body.time_slot_ids]

    missing_s = sorted(student_id_set - {r.id for r in stu_rows if r is not None})
    if missing_s:
        raise HTTPException(status_code=404, detail=f"Unknown student id(s): {missing_s}")
    missing_i = sorted(instructor_id_set - {r.id for r in ins_rows if r is not None})
    if missing_i:
        raise HTTPException(status_code=404, detail=f"Unknown instructor id(s): {missing_i}")
    missing_a = sorted(aircraft_id_set - {r.id for r in ac_rows if r is not None})
    if missing_a:
        raise HTTPException(status_code=404, detail=f"Unknown aircraft id(s): {missing_a}")
    missing_t = sorted(time_slot_set - {r.id for r in ts_rows if r is not None})
    if missing_t:
        raise HTTPException(status_code=404, detail=f"Unknown time_slot id(s): {missing_t}")

    stu_rows = [r for r in stu_rows if r]
    ins_rows = [r for r in ins_rows if r]
    ac_rows = [r for r in ac_rows if r]
    ts_rows = [r for r in ts_rows if r]

    inactive: list[str] = []
    for r in stu_rows + ins_rows + ac_rows + ts_rows:
        if not r.active:
            inactive.append(str(getattr(r, "id", "?")))
    if inactive:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selected records include inactive ids: "
                f"{inactive}. Activate them first or omit from selection."
            ),
        )

    selected_air = {r.id for r in ac_rows}
    students_models: list[Student] = []
    for row in sorted(stu_rows, key=lambda x: x.id):
        default_lc, default_hrs, default_gap = _stage_defaults(row.training_stage)
        lc = row.lessons_completed if row.lessons_completed else default_lc
        hrs = row.hours_total if row.hours_total else default_hrs
        gap = row.last_lesson_days_ago if row.last_lesson_days_ago is not None else default_gap
        weak = _parse_json_array(row.weak_maneuvers_json)
        constraints: dict[str, Any] = {
            "training_stage_original": row.training_stage,
            "weak_maneuvers": weak,
            "priority": row.priority,
            "db_readiness_score": row.readiness_score,
        }
        students_models.append(
            Student(
                id=row.id,
                name=row.name,
                stage=_map_planner_stage(row.training_stage),
                lessons_completed=lc,
                hours_total=hrs,
                last_lesson_days_ago=gap,
                constraints=constraints,
            )
        )

    instructors_models: list[Instructor] = []
    for row in sorted(ins_rows, key=lambda x: x.id):
        certs = _parse_json_array(row.certifications_json)
        certs_s = [str(c).strip() for c in certs if str(c).strip()]
        if not certs_s:
            certs_s = ["cfi", "private"]
        avail_full = _parse_json_obj(row.availability_json)
        avail_typed = {
            str(k): [str(x) for x in v] if isinstance(v, list) else [] for k, v in avail_full.items()
        }
        narrowed = _narrow_availability(avail_typed, slot_set, selected_air)
        if not narrowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Instructor {row.id} has no availability intersecting chosen slots/aircraft "
                    "after narrowing. Expand availability mapping or selections."
                ),
            )
        instructors_models.append(
            Instructor(
                id=row.id,
                name=row.name,
                ratings=certs_s,
                availability=narrowed,
            )
        )

    aircraft_models: list[Aircraft] = []
    grounded = {"grounded", "aog", "maintenance"}
    for row in sorted(ac_rows, key=lambda x: x.id):
        maint = (row.maintenance_status or "").lower().strip()
        dispatch_ok = row.dispatchable and maint not in grounded
        ac_constraints = {
            "maintenance_status": row.maintenance_status,
            "reliability_override": row.reliability_score,
            "dispatchable_override": dispatch_ok,
        }
        aircraft_models.append(
            Aircraft(
                id=row.id,
                tail_number=row.tail_number,
                type=row.aircraft_type.lower().replace(" ", "_")[:64] or "single_engine",
                maintenance_due_hours=row.maintenance_due_hours,
                hours_since_inspection=row.hours_since_inspection,
                constraints=ac_constraints,
            )
        )

    slot_rows_by_id = {r.id: r for r in ts_rows}
    time_slots: list[TimeSlot] = []
    for sid in sorted(body.time_slot_ids):
        r = slot_rows_by_id[sid]
        label = (r.label or r.id).strip()
        label_with_range = f"{label} ({r.start}-{r.end})"
        time_slots.append(TimeSlot(id=r.id, start=r.start, end=r.end, label=label_with_range))

    mode = (body.weather_mode or "manual").strip().lower()
    station = (body.metar_taf_station or "").strip().upper()

    # Preserve manual values as fallback when auto weather is selected.
    manual_snapshot = body.weather or WeatherSnapshot(**weather_default_dict())
    if mode == "auto" and station:
        merged_wx = manual_snapshot
        metar_station = station
    else:
        merged_wx = manual_snapshot
        metar_station = None

    lesson_models = [LessonType(**lt) for lt in DEFAULT_LESSONS]

    inp = FlightWiseInput(
        date=body.date,
        time_slots=time_slots,
        weather=merged_wx,
        weather_by_slot=body.weather_by_slot,
        metar_taf_station=metar_station,
        students=students_models,
        instructors=instructors_models,
        aircraft=aircraft_models,
        lesson_types=lesson_models,
    )

    if persist_snapshot:
        snapshot_selection(session, body)

    return inp
