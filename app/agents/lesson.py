"""Recommended lesson type per student from `lesson_types` and student stage."""

from __future__ import annotations

from typing import Any

_STAGE_ORDER = {"private": 0, "instrument": 1, "commercial": 2}

_CANONICAL_STAGE: dict[str, str] = {
    "pre-solo": "private",
    "cross-country": "private",
    "cross country": "private",
    "private": "private",
    "instrument": "instrument",
    "instrument trainee": "instrument",
    "commercial": "commercial",
    "checkride prep": "commercial",
}


def _canonical_stage(stage: str) -> str:
    s = str(stage or "private").lower().strip()
    return _CANONICAL_STAGE.get(s, s if s in _STAGE_ORDER else "private")


def _stage_rank(stage: str) -> int:
    return _STAGE_ORDER.get(_canonical_stage(stage), 0)


def analyze(request: dict[str, Any]) -> dict[str, Any]:
    lesson_types = request.get("lesson_types") or []
    recommendations: dict[str, dict[str, Any]] = {}

    for s in request.get("students") or []:
        sid = s["id"]
        st_clean = _canonical_stage(s.get("stage") or "private")
        st_rank = _stage_rank(st_clean)
        preferred = ((s.get("constraints") or {}).get("preferred_lesson")) or ""

        best_id = "dual_vfr"
        best_suit = 0.45

        for lt in lesson_types:
            lid = lt["id"]
            min_rank = _stage_rank(lt.get("min_stage") or "private")
            suitable = lt.get("suitable_stages") or []
            stages_ok = not suitable or st_clean.lower() in {x.lower() for x in suitable}
            if st_rank < min_rank or not stages_ok:
                continue
            suit = 0.65 + 0.06 * max(0, st_rank - min_rank)
            if preferred and lid == preferred:
                suit = min(1.0, suit + 0.18)
            if suit > best_suit:
                best_suit = suit
                best_id = lid

        recommendations[sid] = {
            "lesson_type": best_id,
            "suitability": min(1.0, best_suit),
        }

    return {"recommendations": recommendations}
