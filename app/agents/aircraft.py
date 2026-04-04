"""Aircraft dispatchability (hard) and reliability (soft)."""

from __future__ import annotations

from typing import Any


def analyze(request: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, dict[str, Any]] = {}
    for ac in request.get("aircraft") or []:
        aid = ac["id"]
        due = ac.get("maintenance_due_hours")
        since = float(ac.get("hours_since_inspection") or 0.0)
        dispatchable = True
        if due is not None and float(due) <= 0:
            dispatchable = False
        elif due is not None and float(due) < 15.0:
            dispatchable = False

        rel = 0.75
        if due is not None and float(due) > 0:
            rel = max(0.35, min(1.0, 1.0 - (since / max(float(due), 1.0)) * 0.35))

        scores[aid] = {"dispatchable": dispatchable, "reliability": rel}
    return {"scores": scores}
