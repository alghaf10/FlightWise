"""Student readiness scores (0–1) for the optimizer."""

from __future__ import annotations

from typing import Any


def analyze(request: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, dict[str, float]] = {}
    for s in request.get("students") or []:
        sid = s["id"]
        lessons = int(s.get("lessons_completed") or 0)
        hours = float(s.get("hours_total") or 0.0)
        gap = s.get("last_lesson_days_ago")
        base = 0.35 + min(0.45, lessons / 40.0) + min(0.15, hours / 200.0)
        if gap is not None:
            g = int(gap)
            if g > 21:
                base -= 0.12
            elif g > 14:
                base -= 0.06
        scores[sid] = {"readiness": max(0.05, min(1.0, base))}
    return {"scores": scores}
