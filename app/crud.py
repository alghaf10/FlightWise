"""CRUD helpers backed by SQLite / SQLModel."""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from app.db_models import DbAircraft, DbInstructor, DbStudent, DbTimeSlot


def student_to_dict(row: DbStudent) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "stage": row.training_stage,
        "lessons_completed": row.lessons_completed,
        "hours_total": row.hours_total,
        "last_lesson_days_ago": row.last_lesson_days_ago,
        "readiness_score": row.readiness_score,
        "priority": row.priority,
        "weak_maneuvers": json.loads(row.weak_maneuvers_json or "[]"),
        "active": row.active,
    }


def instructor_to_dict(row: DbInstructor) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "ratings": json.loads(row.certifications_json or "[]"),
        "availability": json.loads(row.availability_json or "{}"),
        "max_daily_blocks": row.max_daily_blocks,
        "active": row.active,
    }


def aircraft_to_dict(row: DbAircraft) -> dict[str, Any]:
    return {
        "id": row.id,
        "tail_number": row.tail_number,
        "type": row.aircraft_type,
        "reliability_score": row.reliability_score,
        "maintenance_status": row.maintenance_status,
        "dispatchable": row.dispatchable,
        "hours_since_inspection": row.hours_since_inspection,
        "maintenance_due_hours": row.maintenance_due_hours,
        "active": row.active,
    }


def timeslot_to_dict(row: DbTimeSlot) -> dict[str, Any]:
    return {"id": row.id, "label": row.label, "start": row.start, "end": row.end, "active": row.active}


def list_students(session: Session, *, active_only: bool) -> list[dict[str, Any]]:
    stmt = select(DbStudent)
    if active_only:
        stmt = stmt.where(DbStudent.active.is_(True))
    return [student_to_dict(r) for r in session.exec(stmt).all()]


def list_instructors(session: Session, *, active_only: bool) -> list[dict[str, Any]]:
    stmt = select(DbInstructor)
    if active_only:
        stmt = stmt.where(DbInstructor.active.is_(True))
    return [instructor_to_dict(r) for r in session.exec(stmt).all()]


def list_aircraft(session: Session, *, active_only: bool) -> list[dict[str, Any]]:
    stmt = select(DbAircraft)
    if active_only:
        stmt = stmt.where(DbAircraft.active.is_(True))
    return [aircraft_to_dict(r) for r in session.exec(stmt).all()]


def list_time_slots(session: Session, *, active_only: bool) -> list[dict[str, Any]]:
    stmt = select(DbTimeSlot)
    if active_only:
        stmt = stmt.where(DbTimeSlot.active.is_(True))
    return [timeslot_to_dict(r) for r in session.exec(stmt).all()]
