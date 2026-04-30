"""CP-SAT optimizer for FlightWise."""
from __future__ import annotations
from typing import Any
from ortools.sat.python import cp_model

SCORE_SCALE = 1000  # CP-SAT needs integers, so we multiply floats by this

def solve(state: dict[str, Any]) -> dict[str, Any]:
    request = state.get("request", {})
    weather_data = state.get("weather", {})
    student_data = state.get("students", {})
    instructor_data = state.get("instructors", {})
    aircraft_data = state.get("aircraft", {})
    lesson_data = state.get("lessons", {})

    students = request.get("students", [])
    instructors = request.get("instructors", [])
    aircraft_list = request.get("aircraft", [])
    time_slots = request.get("time_slots", [])

    # --- Basic validation ---
    if not students or not instructors or not aircraft_list or not time_slots:
        return {
            "status": "infeasible_input",
            "assignments": [],
            "unassigned_students": [s["id"] for s in students],
            "reason": "Missing students, instructors, aircraft, or time slots.",
        }

    # --- Pull agent scores ---
    weather_scores = _get_weather_scores(weather_data, time_slots)
    student_scores = _get_student_scores(student_data, students)
    instructor_scores = _get_instructor_scores(instructor_data, instructors)
    aircraft_scores = _get_aircraft_scores(aircraft_data, aircraft_list)
    lesson_scores = _get_lesson_scores(lesson_data, students)

    # --- Build model ---
    model = cp_model.CpModel()

    # Decision variables: x[s,i,a,t] = 1 if student s flies with instructor i on aircraft a at slot t
    x = {}
    for s in students:
        for i in instructors:
            for a in aircraft_list:
                for t in time_slots:
                    key = (s["id"], i["id"], a["id"], t["id"])
                    x[key] = model.NewBoolVar(f"x_{s['id']}_{i['id']}_{a['id']}_{t['id']}")

    # --- Hard Constraints ---

    # Weather gate: block slots where weather score = 0
    for s in students:
        for i in instructors:
            for a in aircraft_list:
                for t in time_slots:
                    if weather_scores.get(t["id"], 1.0) == 0.0:
                        model.Add(x[(s["id"], i["id"], a["id"], t["id"])] == 0)

    # Aircraft availability: block grounded aircraft
    for s in students:
        for i in instructors:
            for a in aircraft_list:
                for t in time_slots:
                    if not aircraft_scores.get(a["id"], {}).get("dispatchable", True):
                        model.Add(x[(s["id"], i["id"], a["id"], t["id"])] == 0)

    # Instructor availability: block slots instructor isn't available for
    for s in students:
        for i in instructors:
            for a in aircraft_list:
                for t in time_slots:
                    avail = i.get("availability", {})
                    slot_avail = avail.get(t["id"], [])
                    if not slot_avail:
                        model.Add(x[(s["id"], i["id"], a["id"], t["id"])] == 0)

    # One instructor per time slot (can't teach two students at once)
    for i in instructors:
        for t in time_slots:
            model.Add(
                sum(x[(s["id"], i["id"], a["id"], t["id"])]
                    for s in students for a in aircraft_list) <= 1
            )

    # One aircraft per time slot
    for a in aircraft_list:
        for t in time_slots:
            model.Add(
                sum(x[(s["id"], i["id"], a["id"], t["id"])]
                    for s in students for i in instructors) <= 1
            )

    # One flight per student per day
    for s in students:
        model.Add(
            sum(x[(s["id"], i["id"], a["id"], t["id"])]
                for i in instructors for a in aircraft_list for t in time_slots) <= 1
        )

    # --- Objective: maximize weighted composite score ---
    objective_terms = []
    for s in students:
        for i in instructors:
            for a in aircraft_list:
                for t in time_slots:
                    score = _compute_score(
                        s["id"], i["id"], a["id"], t["id"],
                        weather_scores, student_scores,
                        instructor_scores, aircraft_scores, lesson_scores
                    )
                    int_score = int(score * SCORE_SCALE)
                    objective_terms.append(int_score * x[(s["id"], i["id"], a["id"], t["id"])])

    model.Maximize(sum(objective_terms))

    # --- Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)

    status_map = {
        cp_model.OPTIMAL: "optimal",
        cp_model.FEASIBLE: "feasible",
        cp_model.INFEASIBLE: "infeasible",
        cp_model.UNKNOWN: "unknown",
    }
    status_name = status_map.get(status, "unknown")

    if status in (cp_model.INFEASIBLE, cp_model.UNKNOWN):
        return {
            "status": "infeasible",
            "solver_status": status_name,
            "assignments": [],
            "unassigned_students": [s["id"] for s in students],
        }

    # --- Collect assignments ---
    assignments = []
    assigned_ids = set()
    for s in students:
        for i in instructors:
            for a in aircraft_list:
                for t in time_slots:
                    key = (s["id"], i["id"], a["id"], t["id"])
                    if solver.Value(x[key]) == 1:
                        score = _compute_score(
                            s["id"], i["id"], a["id"], t["id"],
                            weather_scores, student_scores,
                            instructor_scores, aircraft_scores, lesson_scores
                        )
                        assignments.append({
                            "student_id": s["id"],
                            "instructor_id": i["id"],
                            "aircraft_id": a["id"],
                            "time_slot_id": t["id"],
                            "lesson_type_id": lesson_scores.get(s["id"], {}).get("lesson_type", "dual_vfr"),
                            "objective_value_contrib": round(score, 4),
                        })
                        assigned_ids.add(s["id"])

    unassigned = [s["id"] for s in students if s["id"] not in assigned_ids]

    return {
        "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
        "solver_status": status_name,
        "objective_value": int(solver.ObjectiveValue()),
        "assignments": assignments,
        "unassigned_students": unassigned,
    }


# --- Score helpers ---

def _compute_score(sid, iid, aid, tid,
                   weather_scores, student_scores,
                   instructor_scores, aircraft_scores, lesson_scores) -> float:
    readiness   = student_scores.get(sid, {}).get("readiness", 0.5)
    weather     = weather_scores.get(tid, 0.5)
    fit         = instructor_scores.get(iid, {}).get("fit_score", 0.5)
    reliability = aircraft_scores.get(aid, {}).get("reliability", 0.5)
    suitability = lesson_scores.get(sid, {}).get("suitability", 0.5)

    return (
        0.35 * readiness +
        0.25 * weather +
        0.20 * fit +
        0.10 * reliability +
        0.10 * suitability
    )


def _get_weather_scores(weather_data: dict, time_slots: list) -> dict[str, float]:
    scores = {}
    slot_scores = weather_data.get("slot_scores", {})
    global_score = weather_data.get("score", 1.0)
    for t in time_slots:
        scores[t["id"]] = slot_scores.get(t["id"], global_score)
    return scores


def _get_student_scores(student_data: dict, students: list) -> dict[str, dict]:
    scores = {}
    raw = student_data.get("scores", {})
    for s in students:
        scores[s["id"]] = raw.get(s["id"], {"readiness": 0.5})
    return scores


def _get_instructor_scores(instructor_data: dict, instructors: list) -> dict[str, dict]:
    scores = {}
    raw = instructor_data.get("scores", {})
    for i in instructors:
        scores[i["id"]] = raw.get(i["id"], {"fit_score": 0.5})
    return scores


def _get_aircraft_scores(aircraft_data: dict, aircraft_list: list) -> dict[str, dict]:
    scores = {}
    raw = aircraft_data.get("scores", {})
    for a in aircraft_list:
        scores[a["id"]] = raw.get(a["id"], {"dispatchable": True, "reliability": 0.8})
    return scores


def _get_lesson_scores(lesson_data: dict, students: list) -> dict[str, dict]:
    scores = {}
    raw = lesson_data.get("recommendations", {})
    for s in students:
        scores[s["id"]] = raw.get(s["id"], {"lesson_type": "dual_vfr", "suitability": 0.7})
    return scores