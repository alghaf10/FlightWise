"""Aircraft dispatchability (hard) and reliability (soft)."""

from __future__ import annotations

from typing import Any


def analyze(request: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, dict[str, Any]] = {}
    for ac in request.get("aircraft") or []:
        aid = ac["id"]
        c = ac.get("constraints") or {}
        due = ac.get("maintenance_due_hours")
        since = float(ac.get("hours_since_inspection") or 0.0)
        due_num = float(due) if due is not None else None

        ov_dispatch = c.get("dispatchable_override")
        if ov_dispatch is not None:
            dispatchable = bool(ov_dispatch)
        else:
            dispatchable = True
            if due_num is not None and due_num <= 0:
                dispatchable = False
            elif due_num is not None and due_num < 15.0:
                dispatchable = False

        if dispatchable:
            ov_rel = c.get("reliability_override")
            if ov_rel is not None:
                try:
                    rel = max(0.05, min(1.0, float(ov_rel)))
                except (TypeError, ValueError):
                    rel = _legacy_reliability(due_num, since)
            else:
                rel = _legacy_reliability(due_num, since)
        else:
            rel = 0.1

        scores[aid] = {"dispatchable": dispatchable, "reliability": rel}
    return {"scores": scores}


def _legacy_reliability(due_num: float | None, since: float) -> float:
    rel = 0.75
    if due_num is not None and due_num > 0:
        rel = max(0.35, min(1.0, 1.0 - (since / max(float(due_num), 1.0)) * 0.35))
    return rel
