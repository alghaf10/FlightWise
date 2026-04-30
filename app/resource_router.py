"""REST API for persistent roster entities + planner selection."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.crud import (
    aircraft_to_dict,
    instructor_to_dict,
    list_aircraft,
    list_instructors,
    list_students,
    list_time_slots,
    student_to_dict,
    timeslot_to_dict,
)
from app.db import get_session
from app.db_models import DbAircraft, DbInstructor, DbStudent, DbTimeSlot
from app.models import GeneratePlanResponse
from app.planning_service import execute_plan_request
from app.resource_schemas import (
    AircraftCreate,
    AircraftUpdate,
    InstructorCreate,
    InstructorUpdate,
    PlanFromSelectionBody,
    StudentCreate,
    StudentUpdate,
    TimeSlotCreate,
    TimeSlotUpdate,
)
from app.seed_demo import populate_demo_database
from app.selection_bridge import build_flightwise_input

router = APIRouter(prefix="/api/v1", tags=["Database & selection"])


# --- Students -----------------------------------------------------------------
@router.get("/students", summary="List students")
def api_list_students(
    *,
    active_only: bool = Query(False),
    session: Session = Depends(get_session),
):
    return {"items": list_students(session, active_only=active_only)}


@router.post("/students", summary="Create student")
def api_create_student(
    body: StudentCreate,
    session: Session = Depends(get_session),
):
    if session.get(DbStudent, body.id):
        raise HTTPException(status_code=409, detail=f"Student id already exists: {body.id}")
    row = DbStudent(
        id=body.id,
        name=body.name,
        training_stage=body.stage,
        lessons_completed=body.lessons_completed,
        hours_total=body.hours_total,
        last_lesson_days_ago=body.last_lesson_days_ago,
        readiness_score=body.readiness_score,
        priority=body.priority,
        weak_maneuvers_json=json.dumps(body.weak_maneuvers, ensure_ascii=False),
        active=body.active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return student_to_dict(row)


@router.put("/students/{id}", summary="Update student")
def api_update_student(
    id: str,
    body: StudentUpdate,
    session: Session = Depends(get_session),
):
    row = session.get(DbStudent, id)
    if not row:
        raise HTTPException(status_code=404, detail="Student not found")
    data = body.model_dump(exclude_unset=True)
    if "stage" in data:
        data["training_stage"] = data.pop("stage")
    if "weak_maneuvers" in data:
        data["weak_maneuvers_json"] = json.dumps(data.pop("weak_maneuvers"), ensure_ascii=False)
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return student_to_dict(row)


@router.delete("/students/{id}", summary="Delete student")
def api_delete_student(id: str, session: Session = Depends(get_session)):
    row = session.get(DbStudent, id)
    if not row:
        raise HTTPException(status_code=404, detail="Student not found")
    session.delete(row)
    session.commit()
    return {"deleted": id}


# --- Instructors --------------------------------------------------------------
@router.get("/instructors", summary="List instructors")
def api_list_instructors(
    *,
    active_only: bool = Query(False),
    session: Session = Depends(get_session),
):
    return {"items": list_instructors(session, active_only=active_only)}


@router.post("/instructors", summary="Create instructor")
def api_create_instructor(
    body: InstructorCreate,
    session: Session = Depends(get_session),
):
    if session.get(DbInstructor, body.id):
        raise HTTPException(status_code=409, detail=f"Instructor id already exists: {body.id}")
    row = DbInstructor(
        id=body.id,
        name=body.name,
        certifications_json=json.dumps(body.ratings, ensure_ascii=False),
        availability_json=json.dumps(body.availability, ensure_ascii=False),
        max_daily_blocks=body.max_daily_blocks,
        active=body.active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return instructor_to_dict(row)


@router.put("/instructors/{id}", summary="Update instructor")
def api_update_instructor(
    id: str,
    body: InstructorUpdate,
    session: Session = Depends(get_session),
):
    row = session.get(DbInstructor, id)
    if not row:
        raise HTTPException(status_code=404, detail="Instructor not found")
    data = body.model_dump(exclude_unset=True)
    if "ratings" in data:
        data["certifications_json"] = json.dumps(data.pop("ratings"), ensure_ascii=False)
    if "availability" in data:
        data["availability_json"] = json.dumps(data.pop("availability"), ensure_ascii=False)
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return instructor_to_dict(row)


@router.delete("/instructors/{id}", summary="Delete instructor")
def api_delete_instructor(id: str, session: Session = Depends(get_session)):
    row = session.get(DbInstructor, id)
    if not row:
        raise HTTPException(status_code=404, detail="Instructor not found")
    session.delete(row)
    session.commit()
    return {"deleted": id}


# --- Aircraft -----------------------------------------------------------------
@router.get("/aircraft", summary="List aircraft")
def api_list_aircraft(
    *,
    active_only: bool = Query(False),
    session: Session = Depends(get_session),
):
    return {"items": list_aircraft(session, active_only=active_only)}


@router.post("/aircraft", summary="Create aircraft")
def api_create_aircraft(
    body: AircraftCreate,
    session: Session = Depends(get_session),
):
    if session.get(DbAircraft, body.id):
        raise HTTPException(status_code=409, detail=f"Aircraft id already exists: {body.id}")
    row = DbAircraft(
        id=body.id,
        tail_number=body.tail_number,
        aircraft_type=body.type,
        reliability_score=body.reliability_score,
        maintenance_status=body.maintenance_status,
        dispatchable=body.dispatchable,
        hours_since_inspection=body.hours_since_inspection,
        maintenance_due_hours=body.maintenance_due_hours,
        active=body.active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return aircraft_to_dict(row)


@router.put("/aircraft/{id}", summary="Update aircraft")
def api_update_aircraft(
    id: str,
    body: AircraftUpdate,
    session: Session = Depends(get_session),
):
    row = session.get(DbAircraft, id)
    if not row:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    data = body.model_dump(exclude_unset=True)
    if "type" in data:
        data["aircraft_type"] = data.pop("type")
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return aircraft_to_dict(row)


@router.delete("/aircraft/{id}", summary="Delete aircraft")
def api_delete_aircraft(id: str, session: Session = Depends(get_session)):
    row = session.get(DbAircraft, id)
    if not row:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    session.delete(row)
    session.commit()
    return {"deleted": id}


# --- Time slots ---------------------------------------------------------------
@router.get("/time-slots", summary="List time slots")
def api_list_time_slots(
    *,
    active_only: bool = Query(False),
    session: Session = Depends(get_session),
):
    return {"items": list_time_slots(session, active_only=active_only)}


@router.post("/time-slots", summary="Create time slot")
def api_create_time_slot(
    body: TimeSlotCreate,
    session: Session = Depends(get_session),
):
    if session.get(DbTimeSlot, body.id):
        raise HTTPException(status_code=409, detail=f"Time slot id already exists: {body.id}")
    row = DbTimeSlot(id=body.id, label=body.label or "", start=body.start, end=body.end, active=body.active)
    session.add(row)
    session.commit()
    session.refresh(row)
    return timeslot_to_dict(row)


@router.put("/time-slots/{id}", summary="Update time slot")
def api_update_time_slot(id: str, body: TimeSlotUpdate, session: Session = Depends(get_session)):
    row = session.get(DbTimeSlot, id)
    if not row:
        raise HTTPException(status_code=404, detail="Time slot not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return timeslot_to_dict(row)


@router.delete("/time-slots/{id}", summary="Delete time slot")
def api_delete_time_slot(id: str, session: Session = Depends(get_session)):
    row = session.get(DbTimeSlot, id)
    if not row:
        raise HTTPException(status_code=404, detail="Time slot not found")
    session.delete(row)
    session.commit()
    return {"deleted": id}


# --- Seed & plan --------------------------------------------------------------
@router.post("/seed-demo-data", summary="Load synthetic demo roster (10/4/5/5)")
def api_seed_demo(
    truncate: bool = Query(True),
    session: Session = Depends(get_session),
):
    counts = populate_demo_database(session, truncate=truncate)
    return {"status": "ok", "counts": counts}


@router.post(
    "/plan/from-selection",
    response_model=GeneratePlanResponse,
    summary="Planner from roster selection (IDs)",
)
def api_plan_from_selection(
    body: PlanFromSelectionBody,
    session: Session = Depends(get_session),
):
    fw_input = build_flightwise_input(session, body, persist_snapshot=True)
    session.commit()
    return execute_plan_request(fw_input)
