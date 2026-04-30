"""Per-slot weather scores for the CP-SAT objective and hard gates (score 0 = no fly)."""

from __future__ import annotations

from typing import Any


def _snapshot_score(w: dict[str, Any]) -> float:
    if w.get("precipitation"):
        return 0.0
    wind = float(w.get("wind_kts") or 0.0)
    vis = float(w.get("visibility_sm") or 10.0)
    ceil = int(w.get("ceiling_ft") or 20000)
    if wind > 30 or vis < 2.0 or ceil < 800:
        return 0.0
    if wind > 22 or vis < 5.0 or ceil < 2500:
        return 0.45
    if wind > 15 or vis < 8.0 or ceil < 4000:
        return 0.75
    return 1.0


def analyze(request: dict[str, Any]) -> dict[str, Any]:
    slots = request.get("time_slots") or []
    by_slot = request.get("weather_by_slot") or {}
    global_w = request.get("weather") or {}

    slot_scores: dict[str, float] = {}
    for t in slots:
        tid = t["id"]
        if tid in by_slot:
            slot_scores[tid] = _snapshot_score(by_slot[tid])
        else:
            slot_scores[tid] = _snapshot_score(global_w) if global_w else 1.0

    global_score = _snapshot_score(global_w) if global_w else (
        sum(slot_scores.values()) / len(slot_scores) if slot_scores else 1.0
    )

    return {
        "score": global_score,
        "slot_scores": slot_scores,
    }
