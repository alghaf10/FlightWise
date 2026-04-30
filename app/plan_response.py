"""Build API responses: enriched assignments, summary text, solver metrics."""

from __future__ import annotations

from typing import Any

from app.models import (
    AssignmentOut,
    FlightWiseInput,
    GeneratePlanResponse,
    PlanSummary,
    SolverMetrics,
)


def _names_maps(body: FlightWiseInput) -> tuple[dict[str, str], ...]:
    stu = {s.id: s.name for s in body.students}
    ins = {i.id: i.name for i in body.instructors}
    ac = {a.id: a.tail_number for a in body.aircraft}
    lt = {lt.id: lt.name for lt in body.lesson_types}
    slots = {ts.id: (ts.label or f"{ts.start}–{ts.end}") for ts in body.time_slots}
    return stu, ins, ac, lt, slots


def enrich_assignments(
    body: FlightWiseInput, raw: list[dict[str, Any]]
) -> list[AssignmentOut]:
    stu, ins, ac, lt, slots = _names_maps(body)
    out: list[AssignmentOut] = []
    for a in raw:
        lid = a.get("lesson_type_id", "dual_vfr")
        out.append(
            AssignmentOut(
                student_id=a["student_id"],
                instructor_id=a["instructor_id"],
                aircraft_id=a["aircraft_id"],
                time_slot_id=a["time_slot_id"],
                lesson_type_id=lid,
                objective_value_contrib=None,
                student_name=stu.get(a["student_id"]),
                instructor_name=ins.get(a["instructor_id"]),
                aircraft_tail=ac.get(a["aircraft_id"]),
                time_slot_label=slots.get(a["time_slot_id"]),
                lesson_type_name=lt.get(lid),
            )
        )
    return out


def build_plan_summary(
    *,
    api_status: str,
    body: FlightWiseInput,
    assignments: list[AssignmentOut],
    unassigned: list[str],
) -> PlanSummary:
    n_a = len(assignments)
    n_u = len(unassigned)
    n_s = len(body.students)

    if api_status == "success":
        headline = f"Scheduled {n_a} flight block(s)"
        msg = "All listed assignments satisfy weather, availability, and resource constraints."
    elif api_status == "partial":
        headline = f"Scheduled {n_a} of {n_s} student(s)"
        msg = "Some students could not be placed under current constraints."
    elif api_status == "infeasible":
        headline = "No complete schedule found"
        msg = "No feasible assignment for the given inputs, or no student could be placed."
    else:
        headline = "Schedule run finished with issues"
        msg = "Check solver metrics and trace for details."

    notes: list[str] = []
    if n_u:
        names, _, _, _, _ = _names_maps(body)
        for uid in unassigned[:12]:
            nm = names.get(uid, uid)
            notes.append(f"Not scheduled: {nm} ({uid})")
        if len(unassigned) > 12:
            notes.append(f"…and {len(unassigned) - 12} more.")

    return PlanSummary(
        headline=headline,
        status_message=msg,
        assigned_count=n_a,
        unassigned_count=n_u,
        total_students=n_s,
        notes=notes,
    )


def build_solver_metrics(opt: dict[str, Any]) -> SolverMetrics:
    return SolverMetrics(
        optimization_status=opt.get("status"),
        solver_status=opt.get("solver_status"),
        objective_value=opt.get("objective_value", opt.get("objective")),
    )


def build_generate_plan_response(
    *,
    body: FlightWiseInput,
    state: dict[str, Any],
    api_status: str,
) -> GeneratePlanResponse:
    opt = state.get("optimization") or {}
    raw_assign = opt.get("assignments") or []
    assignments = enrich_assignments(body, raw_assign)
    unassigned = list(opt.get("unassigned_students") or [])
    explanations = list(state.get("explanations") or [])

    summary = build_plan_summary(
        api_status=api_status,
        body=body,
        assignments=assignments,
        unassigned=unassigned,
    )
    solver = build_solver_metrics(opt)

    trace: dict[str, Any] = {
        "weather": state.get("weather"),
        "students": state.get("students"),
        "instructors": state.get("instructors"),
        "aircraft": state.get("aircraft"),
        "lessons": state.get("lessons"),
        "optimization_meta": {
            "status": opt.get("status"),
            "solver_status": opt.get("solver_status"),
            "objective": opt.get("objective"),
        },
    }

    return GeneratePlanResponse(
        status=api_status,
        summary=summary,
        solver=solver,
        assignments=assignments,
        unassigned_students=unassigned,
        explanations=explanations,
        trace=trace,
    )
