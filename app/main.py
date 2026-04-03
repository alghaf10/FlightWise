"""FastAPI entry point for FlightWise."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Running `python .../app/main.py` only puts `app/` on sys.path; imports need repo root.
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# When you Run this file, imports below can take 10–30s the first time (ortools/langgraph).
if __name__ == "__main__":
    print(
        "FlightWise: loading libraries (wait if this is the first run after boot)...",
        flush=True,
    )

from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import ValidationError

from app.models import FLIGHTWISE_INPUT_EXAMPLE, FlightWiseInput, GeneratePlanResponse
from app.plan_response import build_generate_plan_response
from app.workflow import run_workflow

_STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="FlightWise",
    description=(
        "Flight training scheduling API: rule-based agents (weather, students, instructors, "
        "aircraft, lessons) feed an OR-Tools CP-SAT optimizer. Optional METAR/TAF from "
        "aviationweather.gov when `metar_taf_station` is set. Responses include `summary`, "
        "`solver`, enriched `assignments`, and optional `trace`. **Web UI:** [`/ui`](/ui)."
    ),
    version="0.2.0",
    openapi_tags=[
        {
            "name": "Planning",
            "description": "Submit a `FlightWiseInput` JSON body and receive a structured plan.",
        },
        {
            "name": "Meta",
            "description": "Health check and downloadable example payloads.",
        },
        {
            "name": "UI",
            "description": "Browser UI (HTML).",
        },
    ],
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/ui", status_code=302)


@app.get("/ui", tags=["UI"], include_in_schema=False)
def plan_ui() -> FileResponse:
    return FileResponse(_STATIC / "index.html", media_type="text/html; charset=utf-8")


@app.get("/health", tags=["Meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "flightwise"}


def _examples_list() -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    catalog: list[tuple[str, str, str]] = [
        ("sample_minimal", "Minimal — one student, one slot", "sample_minimal.json"),
        ("sample_schedule", "Multi-slot schedule (manual weather)", "sample_schedule.json"),
        ("sample_synthetic", "Full synthetic + METAR/TAF (KAPA)", "sample_synthetic_agents.json"),
    ]
    examples: list[dict[str, Any]] = []
    for eid, title, fname in catalog:
        p = root / fname
        if p.exists():
            examples.append(
                {
                    "id": eid,
                    "title": title,
                    "body": json.loads(p.read_text(encoding="utf-8")),
                }
            )
    examples.append(
        {
            "id": "openapi_example",
            "title": "Same as OpenAPI default example",
            "body": dict(FLIGHTWISE_INPUT_EXAMPLE),
        }
    )
    return {"examples": examples}


@app.get("/api/v1/examples", tags=["Meta"])
def api_examples() -> dict[str, Any]:
    """Named JSON bodies you can paste into `POST /api/v1/plan` or Swagger."""
    return _examples_list()


def _run_plan(body: FlightWiseInput) -> GeneratePlanResponse:
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


@app.post(
    "/generate-plan",
    response_model=GeneratePlanResponse,
    tags=["Planning"],
    summary="Generate schedule (legacy path)",
)
def generate_plan(
    body: FlightWiseInput = Body(
        ...,
        openapi_examples={
            "sample_schedule": {
                "summary": "Sample training day",
                "description": "Two slots, two students, one instructor, one aircraft.",
                "value": FLIGHTWISE_INPUT_EXAMPLE,
            }
        },
    ),
) -> GeneratePlanResponse:
    return _run_plan(body)


@app.post(
    "/api/v1/plan",
    response_model=GeneratePlanResponse,
    tags=["Planning"],
    summary="Generate schedule",
    response_description="Structured plan with summary, solver metrics, and display-ready assignments.",
)
def api_v1_plan(
    body: FlightWiseInput = Body(
        ...,
        openapi_examples={
            "sample_schedule": {
                "summary": "Sample training day",
                "description": "Two slots, two students, one instructor, one aircraft.",
                "value": FLIGHTWISE_INPUT_EXAMPLE,
            }
        },
    ),
) -> GeneratePlanResponse:
    return _run_plan(body)


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as e:
        print(
            "Missing uvicorn. From the flightwise folder run: pip install -r requirements.txt",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1) from e

    host, port = "127.0.0.1", 8000
    print(
        f"FlightWise: starting server at http://{host}:{port}  (UI: /ui  API docs: /docs)\n",
        flush=True,
    )
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError as e:
        print(
            f"Could not bind {host}:{port} — is another server already using it?\n{e}",
            flush=True,
        )
        raise SystemExit(1) from e
