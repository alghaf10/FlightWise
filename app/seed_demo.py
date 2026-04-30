"""Synthetic rows for demos (10 students · 4 instructors · 5 aircraft · 5 time slots)."""

from __future__ import annotations

import json

from sqlmodel import Session, select

from app.db_models import (
    DbAircraft,
    DbInstructor,
    DbStudent,
    DbTimeSlot,
    DailyPlanSnapshot,
)

DEMO_SLOTS: list[tuple[str, str, str, str]] = [
    ("demo_b1", "Morning Alpha", "08:00", "10:00"),
    ("demo_b2", "Morning Bravo", "10:00", "12:00"),
    ("demo_b3", "Midday", "12:30", "14:30"),
    ("demo_b4", "Afternoon", "15:00", "17:00"),
    ("demo_b5", "Evening Twilite", "17:30", "19:30"),
]

SLOT_IDS = [s[0] for s in DEMO_SLOTS]


def _avail_any() -> str:
    return json.dumps({sid: ["any"] for sid in SLOT_IDS}, ensure_ascii=False)


def _narrow_avail(subset_slots: list[str], aircraft_ids: list[str]) -> str:
    d = {sid: aircraft_ids[:] for sid in subset_slots}
    return json.dumps(d, ensure_ascii=False)


def truncate_demo_tables(session: Session) -> None:
    for cls in (DailyPlanSnapshot, DbStudent, DbInstructor, DbAircraft, DbTimeSlot):
        for row in list(session.exec(select(cls)).all()):
            session.delete(row)
    session.commit()


def populate_demo_database(session: Session, *, truncate: bool = True) -> dict[str, int]:
    """Insert demo roster. Call `truncate=True` to wipe prior rows first."""
    if truncate:
        truncate_demo_tables(session)

    slots = [
        DbTimeSlot(id=sid, label=label, start=st, end=en, active=True)
        for sid, label, st, en in DEMO_SLOTS
    ]
    session.add_all(slots)

    aircraft_specs: list[tuple[str, str, str, float, str, float, float | None, bool]] = [
        ("ac_c172_demo", "N172FW", "C172", 0.86, "ok", 55.0, 100.0, True),
        ("ac_pa28_demo", "N44PE", "PA-28", 0.91, "ok", 22.0, 80.0, True),
        ("ac_da40_demo", "N40DA", "DA40", 0.93, "ok", 18.5, 150.0, True),
        ("ac_sr22_demo", "N122SR", "SR22", 0.87, "ok", 90.0, 120.0, True),
        ("ac_backup_demo", "N901BZ", "C152", 0.74, "ok", 12.0, 50.0, True),
    ]
    planes = []
    for pid, tail, typ, rel, ms, hrs, mdue, dsp in aircraft_specs:
        planes.append(
            DbAircraft(
                id=pid,
                tail_number=tail,
                aircraft_type=typ,
                reliability_score=rel,
                maintenance_status=ms,
                dispatchable=dsp,
                hours_since_inspection=hrs,
                maintenance_due_hours=mdue,
                active=True,
            )
        )
    session.add_all(planes)

    session.add_all(
        [
            DbInstructor(
                id="ins_morgan_demo",
                name="Jordan Vance",
                certifications_json=json.dumps(["cfi", "cfii", "private", "instrument", "commercial"]),
                availability_json=_avail_any(),
                max_daily_blocks=5,
                active=True,
            ),
            DbInstructor(
                id="ins_riley_demo",
                name="Riley Thornton",
                certifications_json=json.dumps(["cfi", "private"]),
                availability_json=_narrow_avail(["demo_b1", "demo_b2", "demo_b3"], list({p[0] for p in aircraft_specs[:3]})),
                max_daily_blocks=6,
                active=True,
            ),
            DbInstructor(
                id="ins_cam_demo",
                name="Camille Ortiz",
                certifications_json=json.dumps(["cfi", "private", "instrument"]),
                availability_json=_avail_any(),
                max_daily_blocks=5,
                active=True,
            ),
            DbInstructor(
                id="ins_alex_demo",
                name="Alex Winters",
                certifications_json=json.dumps(["cfi", "cfii"]),
                availability_json=_narrow_avail(
                    ["demo_b3", "demo_b4", "demo_b5"],
                    [p[0] for p in aircraft_specs[2:]],
                ),
                max_daily_blocks=4,
                active=True,
            ),
        ]
    )

    students_data: list[tuple[str, str, str, int, float, int | None, float, int, list[str]]] = [
        ("stu_01_demo", "Morgan Kelley", "pre-solo", 4, 6.5, 5, 0.55, 60, []),
        ("stu_02_demo", "Ethan Briggs", "pre-solo", 5, 8.0, 7, 0.62, 55, ["stalls"]),
        ("stu_03_demo", "Sydney Park", "cross-country", 16, 22.0, 4, 0.72, 50, []),
        ("stu_04_demo", "Diego Ramos", "cross-country", 18, 27.0, 6, 0.68, 45, []),
        ("stu_05_demo", "Lena Friedman", "instrument", 24, 48.0, 6, 0.78, 70, []),
        ("stu_06_demo", "Hayden Patel", "instrument", 27, 55.0, 3, 0.81, 65, []),
        ("stu_07_demo", "Nova Grant", "commercial", 12, 120.0, 3, 0.84, 75, []),
        ("stu_08_demo", "Quinn Lowell", "commercial", 15, 138.0, 5, 0.79, 50, []),
        ("stu_09_demo", "Aria Bishop", "checkride prep", 30, 95.0, 2, 0.91, 90, []),
        ("stu_10_demo", "Jordan Miles", "checkride prep", 32, 101.0, 4, 0.87, 80, []),
    ]
    for sid, nm, ts, lessons, hours, gap, rd, pri, wm in students_data:
        session.add(
            DbStudent(
                id=sid,
                name=nm,
                training_stage=ts,
                lessons_completed=lessons,
                hours_total=hours,
                last_lesson_days_ago=gap,
                readiness_score=rd,
                priority=pri,
                weak_maneuvers_json=json.dumps(wm),
                active=True,
            )
        )

    session.commit()

    return {
        "students": len(list(session.exec(select(DbStudent)).all())),
        "instructors": len(list(session.exec(select(DbInstructor)).all())),
        "aircraft": len(list(session.exec(select(DbAircraft)).all())),
        "time_slots": len(list(session.exec(select(DbTimeSlot)).all())),
    }
