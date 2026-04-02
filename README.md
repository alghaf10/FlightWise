# FlightWise (`app`)

FlightWise is a **FastAPI** service that builds flight-training schedules using **deterministic, rule-based agents** and an **OR-Tools CP-SAT** optimizer. A **LangGraph** workflow runs agents in order, then solves the assignment problem, then generates human-readable explanations (template by default; optional OpenAI).

## Requirements

Install dependencies from the parent project (`flightwise`):

```text
pip install -r requirements.txt
```

Key libraries: FastAPI, Pydantic v2, LangGraph, OR-Tools (`ortools`), Uvicorn. Optional: `openai` for LLM-generated explanations.

## Run the API

From the **`flightwise`** directory (parent of `app`), so Python can import the `app` package:

```text
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Health:** `GET /health`
- **Plan:** `POST /generate-plan` — body matches `FlightWiseInput` (see `models.py`)

OpenAPI docs: `http://localhost:8000/docs` · ReDoc: `/redoc` · **`/ui`** — browser UI (samples, run planner, formatted results).

REST: **`POST /api/v1/plan`** (same body/response as **`POST /generate-plan`**). **`GET /api/v1/examples`** — named sample JSON bodies for requests.

## High-level flow

1. Request JSON is validated as `FlightWiseInput`.
2. LangGraph runs: weather → student → instructor → aircraft → lesson → **CP-SAT solve** → explanation.
3. Response is `GeneratePlanResponse` (status, assignments, unassigned students, explanations, trace).

## METAR / TAF weather (optional)

Set **`metar_taf_station`** on the request to a US or worldwide **ICAO** ID (e.g. `KAPA`, `KSEA`). The workflow pulls **METAR** and **TAF** from [Aviation Weather (NOAA)](https://aviationweather.gov/) JSON APIs (`/api/data/metar`, `/api/data/taf`), fills **`weather`** from the latest METAR, and **`weather_by_slot`** from TAF forecast periods whose UTC window overlaps each `time_slot` (**`start` / `end` are interpreted as UTC**). The active UTC calendar day is taken from the METAR report time (or the TAF product) so it stays aligned with the live bulletin. Debug details appear under `trace.weather.awc` (raw text, issue times, slot mapping). Offline or blocked HTTP: omit `metar_taf_station` and pass **`weather`** / **`weather_by_slot`** manually.

Sample payloads in the repo: **`sample_synthetic_agents.json`** (rich synthetic students, instructors, aircraft, lesson types + `KAPA`), **`sample_schedule.json`**, **`sample_minimal.json`**.

## Project layout and files

| Path | Role |
|------|------|
| `__init__.py` | Package marker; exports FlightWise as the application package. |
| `main.py` | FastAPI app: `/`, `/ui`, `/health`, `/api/v1/plan`, `/generate-plan`, `/api/v1/examples`. |
| `models.py` | Request/response models: `FlightWiseInput`, `GeneratePlanResponse` (`summary`, `solver`, enriched `assignments`), etc. |
| `plan_response.py` | Maps workflow state to API response (names on assignments, `PlanSummary`, `SolverMetrics`). |
| `static/index.html` | Web UI for trying samples and viewing formatted JSON. |
| `state.py` | `FlightWiseState` `TypedDict`: request, agent outputs, optimization result, explanations, status. |
| `workflow.py` | LangGraph `StateGraph`: nodes wire agents, `solve`, and `explain`; `run_workflow()` entry. |
| `weather_awc.py` | METAR/TAF HTTP fetch + mapping into `weather` / `weather_by_slot` when `metar_taf_station` is set. |
| `agents/__init__.py` | Notes agents are rule-based (no LLMs in the scoring path). |
| `agents/weather.py` | Per-slot weather risk, VFR feasibility, suitability for the objective. |
| `agents/student.py` | Readiness and scheduling priority per student. |
| `agents/instructor.py` | Slot availability matrix and instructor–student fit scores. |
| `agents/aircraft.py` | Dispatchability, reliability, maintenance risk per aircraft. |
| `agents/lesson.py` | Recommended lesson type per student (uses `lesson_types` or defaults). |
| `optimizer/__init__.py` | Optimization package marker. |
| `optimizer/scheduler.py` | CP-SAT model: assign each student to at most one (instructor, aircraft, slot); no double-booking instructor or aircraft per slot; maximizes weighted readiness, fit, reliability, weather, lesson fit. |
| `explanation/__init__.py` | Explanation layer; optional LLM does not affect scores. |
| `explanation/explainer.py` | Builds per-assignment context; template explanations or batched OpenAI if `OPENAI_API_KEY` is set (`FLIGHTWISE_EXPLAIN_MODEL` optional, default `gpt-4o-mini`). |

## API response status

The API maps internal workflow/solver status to `GeneratePlanResponse.status`, for example `success`, `infeasible`, `partial`, or `error`, depending on assignments, unassigned students, and top-level `status`.

## Environment (optional explanations)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | If set and `openai` is installed, explanations may use the chat API. |
| `FLIGHTWISE_EXPLAIN_MODEL` | Model name for explanations (defaults to `gpt-4o-mini`). |

Without these, explanations use deterministic templates from the same structured facts as the optimizer.

## Design notes

- **Deterministic core:** Agent outputs and CP-SAT weights are reproducible given the same input; the explainer is isolated and does not feed back into scheduling.
- **Feasibility:** The solver only creates variables for combinations that pass weather, instructor availability, aircraft dispatch rules, and aircraft allowed for that instructor in that slot.
