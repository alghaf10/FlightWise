"""Shared LangGraph state for FlightWise."""

from __future__ import annotations

from typing import Any, TypedDict


class FlightWiseState(TypedDict, total=False):
    """Workflow state; agents append structured analysis, optimizer fills result."""

    # Original request body (dict for flexibility with nested models)
    request: dict[str, Any]

    # Agent outputs (deterministic, structured)
    weather: dict[str, Any]
    students: dict[str, Any]
    instructors: dict[str, Any]
    aircraft: dict[str, Any]
    lessons: dict[str, Any]

    # Combined scoring tensors / indices for the solver
    solver_payload: dict[str, Any]

    # CP-SAT result
    optimization: dict[str, Any]

    # Natural language (explanation layer only)
    explanations: list[str]

    # API-facing status
    status: str
    error: str | None
