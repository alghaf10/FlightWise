"""Explanations from workflow state (no effect on scores).

- **Detailed template** (default): uses weather, readiness, instructor fit, and lesson recommendations.
- **Optional OpenAI**: set ``OPENAI_API_KEY`` and keep ``FLIGHTWISE_EXPLAIN_USE_LLM`` enabled (default on when the key is set).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


def _slot_weather_phrase(score: float | None) -> str:
    if score is None:
        return "Weather suitability was not scored for this slot."
    s = float(score)
    if s >= 0.95:
        return "Weather suitability is high (favorable VFR relative to training limits)."
    if s >= 0.75:
        return "Weather suitability is decent with some limits (still within operating gates)."
    if s >= 0.45:
        return "Weather is marginal; the optimizer still allowed this slot under current gates."
    return "Weather is tight for this slot; verify limits before dispatch."


def _should_use_openai() -> bool:
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        return False
    v = (os.getenv("FLIGHTWISE_EXPLAIN_USE_LLM") or "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _build_context_dict(state: dict[str, Any]) -> dict[str, Any]:
    req = state.get("request") or {}
    wx = state.get("weather") or {}
    stu = state.get("students") or {}
    ins = state.get("instructors") or {}
    les = state.get("lessons") or {}
    opt = state.get("optimization") or {}
    stu_map = {s["id"]: s for s in req.get("students") or []}
    ins_map = {i["id"]: i for i in req.get("instructors") or []}
    ac_map = {a["id"]: a for a in req.get("aircraft") or []}
    slot_map = {t["id"]: t for t in req.get("time_slots") or []}
    enriched: list[dict[str, Any]] = []
    for a in opt.get("assignments") or []:
        sid = a.get("student_id")
        enriched.append(
            {
                "assignment": a,
                "student_profile": stu_map.get(sid),
                "instructor_profile": ins_map.get(a.get("instructor_id")),
                "aircraft_profile": ac_map.get(a.get("aircraft_id")),
                "time_slot": slot_map.get(a.get("time_slot_id")),
                "readiness": (stu.get("scores") or {}).get(sid),
                "instructor_fit": (ins.get("scores") or {}).get(a.get("instructor_id")),
                "lesson_recommendation": (les.get("recommendations") or {}).get(sid),
                "slot_weather_score": (wx.get("slot_scores") or {}).get(a.get("time_slot_id")),
            }
        )
    unassigned = []
    for uid in opt.get("unassigned_students") or []:
        unassigned.append(
            {
                "student_id": uid,
                "student_profile": stu_map.get(uid),
                "readiness": (stu.get("scores") or {}).get(uid),
                "lesson_recommendation": (les.get("recommendations") or {}).get(uid),
            }
        )
    return {
        "date": req.get("date"),
        "metar_taf_station": req.get("metar_taf_station"),
        "global_weather_score": wx.get("score"),
        "slot_weather_scores": wx.get("slot_scores"),
        "enriched_assignments": enriched,
        "unassigned": unassigned,
        "solver_status": {
            "status": opt.get("status"),
            "solver_status": opt.get("solver_status"),
            "objective_value": opt.get("objective_value", opt.get("objective")),
        },
    }


def _explain_openai(state: dict[str, Any]) -> list[str] | None:
    from openai import OpenAI

    ctx = _build_context_dict(state)
    model = os.getenv("FLIGHTWISE_EXPLAIN_MODEL", "gpt-4o-mini")
    client = OpenAI()
    system = (
        "You are an expert flight-training operations assistant. "
        "You receive structured scheduling context from a deterministic optimizer (weather scores, readiness, "
        "instructor fit, lesson recommendations, and final assignments). "
        "Write clear, professional explanations for operators. "
        "Return ONLY valid JSON with this exact shape: "
        '{"explanations": ["string", ...]}. '
        "Produce one string per scheduled assignment in the same order as `enriched_assignments`, "
        "then one string per entry in `unassigned` in order. "
        "Each string must be 2–5 sentences and mention relevant factors (weather for that block, student readiness, "
        "instructor fit, lesson focus, aircraft) when data is present. "
        "If there are no assignments and only unassigned students, only list unassigned explanations."
    )
    user = "Context JSON:\n" + json.dumps(ctx, indent=2, default=str)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        data = json.loads(m.group(0))
    ex = data.get("explanations")
    if not isinstance(ex, list):
        return None
    out = [str(x).strip() for x in ex if str(x).strip()]
    return out or None


def explain_detailed(state: dict[str, Any]) -> list[str]:
    """Rich template explanations using agent outputs (no LLM)."""
    req = state.get("request") or {}
    wx = state.get("weather") or {}
    stu = state.get("students") or {}
    ins = state.get("instructors") or {}
    les = state.get("lessons") or {}
    opt = state.get("optimization") or {}

    slot_scores: dict[str, float] = wx.get("slot_scores") or {}
    stu_scores = stu.get("scores") or {}
    ins_scores = ins.get("scores") or {}
    lec = les.get("recommendations") or {}

    stu_map = {s["id"]: s for s in req.get("students") or []}
    ins_map = {i["id"]: i for i in req.get("instructors") or []}
    ac_map = {a["id"]: a for a in req.get("aircraft") or []}
    slot_map = {
        t["id"]: (t.get("label") or f"{t.get('start', '')}–{t.get('end', '')}")
        for t in req.get("time_slots") or []
    }

    lines: list[str] = []
    for a in opt.get("assignments") or []:
        sid = a.get("student_id")
        iid = a.get("instructor_id")
        aid = a.get("aircraft_id")
        tid = a.get("time_slot_id")
        lt = a.get("lesson_type_id", "")

        sn = stu_map.get(sid, {}).get("name", sid)
        stage = stu_map.get(sid, {}).get("stage", "")
        ins_nm = ins_map.get(iid, {}).get("name", iid)
        tail = ac_map.get(aid, {}).get("tail_number", aid)
        slot_label = slot_map.get(tid, tid)

        rd = stu_scores.get(sid, {}).get("readiness")
        fit = ins_scores.get(iid, {}).get("fit_score")
        ws = slot_scores.get(tid)
        rec = lec.get(sid, {})
        rec_lt = rec.get("lesson_type", "")
        rec_su = rec.get("suitability")

        parts = [
            f"{sn} ({stage}) is scheduled in {slot_label} with {ins_nm} in {tail}.",
            _slot_weather_phrase(ws),
        ]
        if rd is not None:
            parts.append(f"Readiness score is {float(rd):.2f} (recency, hours, and lesson progress).")
        if fit is not None:
            parts.append(f"Instructor fit score is {float(fit):.2f} based on ratings and experience profile.")
        if rec_lt:
            su = f"{float(rec_su):.2f}" if rec_su is not None else "n/a"
            parts.append(f"Lesson focus aligns with recommended track `{rec_lt}` (suitability {su}).")
        if lt and lt != rec_lt:
            parts.append(f"The optimizer scheduled lesson type `{lt}` for this block.")
        lines.append(" ".join(parts))

    for uid in opt.get("unassigned_students") or []:
        sp = stu_map.get(uid, {})
        nm = sp.get("name", uid)
        rd = stu_scores.get(uid, {}).get("readiness")
        extra = f" Readiness was {float(rd):.2f}." if rd is not None else ""
        lines.append(
            f"No feasible slot remained for {nm} under current weather, instructor/aircraft availability, "
            f"and lesson constraints.{extra} Consider relaxing availability or adding capacity."
        )

    if not lines:
        lines.append(
            "No assignments were produced. Check solver status, weather gates, and that each student has "
            "at least one feasible instructor/aircraft/slot combination."
        )

    return lines


def explain(state: dict[str, Any]) -> list[str]:
    """Template and optional OpenAI explanations (does not affect optimization)."""
    if _should_use_openai():
        try:
            out = _explain_openai(state)
            if out:
                return out
        except Exception:
            pass
    return explain_detailed(state)
