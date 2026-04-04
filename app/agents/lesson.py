"""Recommended lesson type per student from `lesson_types` and student stage."""

from __future__ import annotations

from typing import Any

_STAGE_ORDER = {"private": 0, "instrument": 1, "commercial": 2}


def _stage_rank(stage: str) -> int:
    return _STAGE_ORDER.get(str(stage).lower().strip(), 0)


def analyze(request: dict[str, Any]) -> dict[str, Any]:
    lesson_types = request.get("lesson_types") or []
    recommendations: dict[str, dict[str, Any]] = {}

    for s in request.get("students") or []:
        sid = s["id"]
        st_rank = _stage_rank(s.get("stage") or "private")
        best_id = "dual_vfr"
        best_suit = 0.5

        for lt in lesson_types:
            lid = lt["id"]
            min_rank = _stage_rank(lt.get("min_stage") or "private")
            suitable = lt.get("suitable_stages") or []
            stages_ok = not suitable or (s.get("stage") or "").lower() in {
                x.lower() for x in suitable
            }
            if st_rank < min_rank or not stages_ok:
                continue
            suit = 0.65 + 0.05 * (st_rank - min_rank)
            if suit > best_suit:
                best_suit = suit
                best_id = lid

        recommendations[sid] = {
            "lesson_type": best_id,
            "suitability": min(1.0, best_suit),
        }

    return {"recommendations": recommendations}
