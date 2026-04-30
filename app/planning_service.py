"""Planning pipeline: validated input → LangGraph workflow → API response."""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import ValidationError

from app.models import FlightWiseInput, GeneratePlanResponse
from app.plan_response import build_generate_plan_response
from app.workflow import run_workflow


def execute_plan_request(body: FlightWiseInput) -> GeneratePlanResponse:
    """Run deterministic workflow + CP-SAT, then wrap as `GeneratePlanResponse`."""
    try:
        payload = body.model_dump()
        state = run_workflow(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    opt = state.get("optimization") or {}
    assignments_raw = opt.get("assignments") or []
    unassigned = list(opt.get("unassigned_students") or [])

    top_status = state.get("status") or "ok"
    if top_status == "infeasible":
        api_status = "infeasible"
    elif top_status == "error":
        api_status = "error"
    elif not assignments_raw and unassigned:
        api_status = "partial" if assignments_raw else "infeasible"
    else:
        api_status = "success" if assignments_raw else "infeasible"

    return build_generate_plan_response(
        body=body,
        state=state,
        api_status=api_status,
    )
