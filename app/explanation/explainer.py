"""Template explanations from workflow state (no effect on scores)."""

from __future__ import annotations

from typing import Any


def explain(state: dict[str, Any]) -> list[str]:
    req = state.get("request") or {}
    opt = state.get("optimization") or {}
    lines: list[str] = []

    stu_map = {s["id"]: s.get("name", s["id"]) for s in req.get("students") or []}
    ins_map = {i["id"]: i.get("name", i["id"]) for i in req.get("instructors") or []}
    ac_map = {a["id"]: a.get("tail_number", a["id"]) for a in req.get("aircraft") or []}
    slot_map = {
        t["id"]: (t.get("label") or f"{t.get('start', '')}–{t.get('end', '')}")
        for t in req.get("time_slots") or []
    }

    for a in opt.get("assignments") or []:
        sn = stu_map.get(a.get("student_id"), a.get("student_id"))
        ins = ins_map.get(a.get("instructor_id"), a.get("instructor_id"))
        tail = ac_map.get(a.get("aircraft_id"), a.get("aircraft_id"))
        slot = slot_map.get(a.get("time_slot_id"), a.get("time_slot_id"))
        lt = a.get("lesson_type_id", "")
        lines.append(
            f"{sn} flies with {ins} in {tail} during {slot} ({lt})."
        )

    for uid in opt.get("unassigned_students") or []:
        lines.append(f"No slot found for {stu_map.get(uid, uid)} under current constraints.")

    if not lines:
        lines.append("No assignments produced; check inputs and solver status.")

    return lines
