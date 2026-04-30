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
        computed = max(0.05, min(1.0, base))

        c = s.get("constraints") or {}
        db_r = c.get("db_readiness_score")
        if db_r is not None:
            try:
                blended = 0.45 * float(db_r) + 0.55 * computed
                base_read = max(0.05, min(1.0, blended))
            except (TypeError, ValueError):
                base_read = computed
        else:
            base_read = computed

        priority = int(c.get("priority", 50))
        pri_boost = min(0.12, max(0.0, (priority / 100.0) * 0.12))
        readiness = max(0.05, min(1.0, base_read + pri_boost))

        scores[sid] = {"readiness": readiness}
    return {"scores": scores}
