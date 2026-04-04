"""Instructor quality / fit scores (soft objective only; availability is a hard constraint)."""

from __future__ import annotations

from typing import Any


def analyze(request: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, dict[str, float]] = {}
    for ins in request.get("instructors") or []:
        iid = ins["id"]
        ratings = ins.get("ratings") or []
        n = len(ratings)
        fit = 0.55 + min(0.35, 0.05 * n)
        if "cfi" in ratings:
            fit += 0.05
        scores[iid] = {"fit_score": min(1.0, fit)}
    return {"scores": scores}
