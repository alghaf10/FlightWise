"""LangGraph workflow: ordered agents → optimization → explanation."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents import aircraft, instructor, lesson, student, weather
from app.explanation.explainer import explain
from app.optimizer.scheduler import solve
from app.state import FlightWiseState
from app.weather_awc import apply_metar_taf_to_request


def _weather_node(state: FlightWiseState) -> dict[str, Any]:
    body = {**state["request"]}
    awc = apply_metar_taf_to_request(body, timeout=20.0)
    wx = weather.analyze(body)
    if not awc.get("skipped"):
        wx = {**wx, "awc": awc}
    return {"weather": wx, "request": body}


def _student_node(state: FlightWiseState) -> dict[str, Any]:
    return {"students": student.analyze(state["request"])}


def _instructor_node(state: FlightWiseState) -> dict[str, Any]:
    return {"instructors": instructor.analyze(state["request"])}


def _aircraft_node(state: FlightWiseState) -> dict[str, Any]:
    return {"aircraft": aircraft.analyze(state["request"])}


def _lesson_node(state: FlightWiseState) -> dict[str, Any]:
    return {"lessons": lesson.analyze(state["request"])}


def _optimization_node(state: FlightWiseState) -> dict[str, Any]:
    result = solve(state)
    status = "ok"
    if result.get("status") == "infeasible":
        status = "infeasible"
    elif result.get("status") == "infeasible_input":
        status = "error"
    return {"optimization": result, "status": status}


def _explanation_node(state: FlightWiseState) -> dict[str, Any]:
    return {"explanations": explain(state)}


def build_graph() -> StateGraph:
    g = StateGraph(FlightWiseState)
    g.add_node("weather", _weather_node)
    g.add_node("student", _student_node)
    g.add_node("instructor", _instructor_node)
    g.add_node("aircraft", _aircraft_node)
    g.add_node("lesson", _lesson_node)
    g.add_node("optimization", _optimization_node)
    g.add_node("explanation", _explanation_node)

    g.add_edge(START, "weather")
    g.add_edge("weather", "student")
    g.add_edge("student", "instructor")
    g.add_edge("instructor", "aircraft")
    g.add_edge("aircraft", "lesson")
    g.add_edge("lesson", "optimization")
    g.add_edge("optimization", "explanation")
    g.add_edge("explanation", END)
    return g


_compiled = None


def get_workflow():
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile()
    return _compiled


def run_workflow(request_body: dict[str, Any]) -> FlightWiseState:
    """Execute full pipeline from JSON dict input."""
    initial: FlightWiseState = {
        "request": request_body,
        "status": "pending",
        "error": None,
    }
    return get_workflow().invoke(initial)
