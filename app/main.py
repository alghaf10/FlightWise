"""FastAPI entry point for FlightWise."""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Running `python .../app/main.py` only puts `app/` on sys.path; imports need repo root.
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Optional: load `.env` from the project root if present (no file is required to run FlightWise).
from dotenv import load_dotenv

_DOTENV_PATH = _repo_root / ".env"
_DOTENV_LOADED = load_dotenv(_DOTENV_PATH)

# When you Run this file, imports below can take 10–30s the first time (ortools/langgraph).
if __name__ == "__main__":
    print(
        "FlightWise: loading libraries (wait if this is the first run after boot)...",
        flush=True,
    )

from typing import Any

from fastapi import Body, FastAPI
from fastapi.responses import FileResponse, RedirectResponse

from app.db import init_db
from app.models import FLIGHTWISE_INPUT_EXAMPLE, FlightWiseInput, GeneratePlanResponse
from app.planning_service import execute_plan_request
from app.resource_router import router as resource_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


_STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="FlightWise",
    lifespan=lifespan,
    description=(
        "Flight training scheduling API: rule-based agents (weather, students, instructors, "
        "aircraft, lessons) feed an OR-Tools CP-SAT optimizer. Optional METAR/TAF from "
        "aviationweather.gov when `metar_taf_station` is set. Responses include `summary`, "
        "`solver`, enriched `assignments`, and optional `trace`. SQLite roster APIs under `/api/v1/` "
        "for students, instructors, aircraft, and time slots plus `POST /api/v1/plan/from-selection`. "
        "**`/ui`** is the planner UI."
    ),
    version="0.3.0",
    openapi_tags=[
        {
            "name": "Planning",
            "description": "Submit a `FlightWiseInput` JSON body or build from roster selection.",
        },
        {"name": "Meta", "description": "Health check and downloadable example payloads."},
        {"name": "UI", "description": "Browser UI (HTML)."},
        {"name": "Database & selection", "description": "SQLite roster CRUD + plan from selected IDs."},
    ],
)

app.include_router(resource_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/ui", status_code=302)


@app.get("/ui", tags=["UI"], include_in_schema=False)
def plan_ui() -> FileResponse:
    return FileResponse(
        _STATIC / "index.html",
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health", tags=["Meta"])
def health() -> dict[str, Any]:
    """Liveness check."""
    db_path = _repo_root / "flightwise.db"
    return {
        "status": "ok",
        "service": "flightwise",
        "dotenv_file_loaded": _DOTENV_LOADED,
        "dotenv_path": str(_DOTENV_PATH),
        "planner_requires_env": False,
        "database_file_present": db_path.exists(),
    }


def _find_sample_json(fname: str) -> Path | None:
    for base in (_repo_root, Path(__file__).resolve().parent):
        p = base / fname
        if p.exists():
            return p
    return None


def _examples_list() -> dict[str, Any]:
    catalog: list[tuple[str, str, str]] = [
        ("sample_minimal", "Minimal — one student, one slot", "sample_minimal.json"),
        ("sample_schedule", "Multi-slot schedule (manual weather)", "sample_schedule.json"),
        ("sample_weekend_academy", "Synthetic — busy day, 6 blocks, 6 students", "sample_weekend_academy.json"),
        ("sample_hub_spoke", "Synthetic — 7 students, 5 blocks", "sample_hub_spoke_day.json"),
        ("sample_sunrise_blocks", "Synthetic — dawn-to-dusk blocks", "sample_sunrise_blocks.json"),
        ("sample_synthetic", "Full synthetic + METAR/TAF (KAPA)", "sample_synthetic_agents.json"),
    ]
    examples: list[dict[str, Any]] = []
    for eid, title, fname in catalog:
        p = _find_sample_json(fname)
        if p is not None:
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
    return execute_plan_request(body)


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
    return execute_plan_request(body)


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
