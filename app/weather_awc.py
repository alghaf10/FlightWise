"""Fetch METAR/TAF from NOAA Aviation Weather (aviationweather.gov) and map into FlightWise weather fields."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

METAR_URL = "https://aviationweather.gov/api/data/metar"
TAF_URL = "https://aviationweather.gov/api/data/taf"

# Precip / convection in METAR/TAF wx tokens (exclude BR/FG alone; those affect vis separately).
_PRECIP_TOKENS = re.compile(
    r"(^|[\s,])(\+|-|VC)?(RA|DZ|SN|PL|GR|GS|UP|RASN|SHRA|SHSN|SHUP|TS|TSRA|FZDZ|FZRA)\b",
    re.I,
)


def _parse_vis_sm(val: Any) -> float:
    if val is None:
        return 10.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().upper()
    if s in ("P6SM", "6+", "M6", "6PLUS"):
        return 10.0
    if s.startswith("M") and s[1:].replace(".", "").isdigit():
        return max(0.25, float(s[1:]))
    if s.startswith("P") and len(s) > 1:
        return 10.0
    try:
        return float(s.replace("SM", "").strip())
    except ValueError:
        return 10.0


def _ceiling_ft_from_clouds(clouds: list[dict[str, Any]] | None) -> int:
    if not clouds:
        return 10_000
    bases: list[int] = []
    for c in clouds:
        cover = (c.get("cover") or "").upper()
        base = c.get("base")
        if cover in ("BKN", "OVC", "VV") and base is not None:
            try:
                bases.append(int(base))
            except (TypeError, ValueError):
                continue
    return min(bases) if bases else 10_000


def _wind_kts_from_fcst(fcst: dict[str, Any]) -> float:
    wspd = float(fcst.get("wspd") or 0)
    wgst = fcst.get("wgst")
    if wgst is not None:
        try:
            wspd = max(wspd, float(wgst))
        except (TypeError, ValueError):
            pass
    return wspd


def _precip_from_wx(wx: str | None) -> bool:
    if not wx:
        return False
    return bool(_PRECIP_TOKENS.search(wx))


def metar_record_to_snapshot(rec: dict[str, Any]) -> dict[str, Any]:
    wind = float(rec.get("wspd") or 0)
    wgst = rec.get("wgst")
    if wgst is not None:
        try:
            wind = max(wind, float(wgst))
        except (TypeError, ValueError):
            pass
    vis = _parse_vis_sm(rec.get("visib"))
    ceil_ft = _ceiling_ft_from_clouds(rec.get("clouds"))
    raw = rec.get("rawOb") or rec.get("metarType") or ""
    wxs = rec.get("wxString") or ""
    precip = _precip_from_wx(wxs) or _precip_from_wx(str(raw))

    notes = f"METAR {rec.get('icaoId', '')} {rec.get('reportTime', '')}"
    if wxs:
        notes = f"{notes} wx:{wxs}"

    return {
        "wind_kts": wind,
        "visibility_sm": vis,
        "ceiling_ft": int(ceil_ft),
        "precipitation": precip,
        "notes": notes.strip(),
    }


def taf_fcst_to_snapshot(fcst: dict[str, Any]) -> dict[str, Any]:
    wind = _wind_kts_from_fcst(fcst)
    vis = _parse_vis_sm(fcst.get("visib"))
    ceil_ft = _ceiling_ft_from_clouds(fcst.get("clouds"))
    wxs = fcst.get("wxString") or ""
    precip = _precip_from_wx(wxs)

    return {
        "wind_kts": wind,
        "visibility_sm": vis,
        "ceiling_ft": int(ceil_ft),
        "precipitation": precip,
        "notes": f"TAF fcst wx:{wxs}" if wxs else "TAF forecast period",
    }


def _anchor_date_utc(
    metar_row: dict[str, Any] | None, fcsts: list[dict[str, Any]]
) -> str | None:
    """UTC calendar day from latest METAR report time or first TAF period (for slot ↔ TAF alignment)."""
    if metar_row and metar_row.get("reportTime"):
        rt = str(metar_row["reportTime"])
        try:
            d = datetime.fromisoformat(rt.replace("Z", "+00:00")).date()
            return d.isoformat()
        except ValueError:
            pass
    if fcsts:
        try:
            t0 = int(fcsts[0]["timeFrom"])
            return datetime.fromtimestamp(t0, tz=timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            pass
    return None


def _slot_range_unix_utc(date_str: str, start_hm: str, end_hm: str) -> tuple[int, int] | None:
    try:
        s = datetime.strptime(f"{date_str.strip()} {start_hm.strip()}", "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
        e = datetime.strptime(f"{date_str.strip()} {end_hm.strip()}", "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    if e <= s:
        return None
    return int(s.timestamp()), int(e.timestamp())


def _fcst_for_window(fcsts: list[dict[str, Any]], t0: int, t1: int) -> dict[str, Any] | None:
    mid = (t0 + t1) // 2
    for f in fcsts:
        try:
            f0 = int(f["timeFrom"])
            f1 = int(f["timeTo"])
        except (KeyError, TypeError, ValueError):
            continue
        if f0 <= mid < f1:
            return f
    for f in fcsts:
        try:
            f0 = int(f["timeFrom"])
            f1 = int(f["timeTo"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (t1 <= f0 or t0 >= f1):
            return f
    return None


def fetch_metar(icao: str, *, timeout: float = 15.0) -> dict[str, Any] | None:
    icao = icao.strip().upper()
    with httpx.Client(timeout=timeout) as client:
        r = client.get(METAR_URL, params={"ids": icao, "format": "json"})
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, list) or not data:
        return None
    row = data[0]
    return row if isinstance(row, dict) else None


def fetch_taf(icao: str, *, timeout: float = 15.0) -> dict[str, Any] | None:
    icao = icao.strip().upper()
    with httpx.Client(timeout=timeout) as client:
        r = client.get(TAF_URL, params={"ids": icao, "format": "json"})
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, list) or not data:
        return None
    row = data[0]
    return row if isinstance(row, dict) else None


def apply_metar_taf_to_request(request: dict[str, Any], *, timeout: float = 15.0) -> dict[str, Any]:
    """
    If ``request['metar_taf_station']`` is set, overwrite ``weather`` and ``weather_by_slot`` from AWC.
    Slot times are interpreted as UTC wall-clock combined with ``date`` when matching TAF periods.
    Returns a debug dict (always), with keys: ok, icao, error?, metar?, taf?, notes.
    """
    icao = request.get("metar_taf_station")
    if not icao:
        return {"ok": False, "skipped": True}
    icao = str(icao).strip().upper()
    out: dict[str, Any] = {"ok": False, "icao": icao}

    metar_row: dict[str, Any] | None = None
    taf_row: dict[str, Any] | None = None
    try:
        metar_row = fetch_metar(icao, timeout=timeout)
    except Exception as e:
        out["metar_error"] = str(e)
    try:
        taf_row = fetch_taf(icao, timeout=timeout)
    except Exception as e:
        out["taf_error"] = str(e)

    date_str = str(request.get("date") or "")[:10]
    slots_in = request.get("time_slots") or []

    by_slot: dict[str, dict[str, Any]] = {}
    baseline: dict[str, Any] = {}

    if metar_row:
        baseline = metar_record_to_snapshot(metar_row)
        out["metar_raw"] = metar_row.get("rawOb")
        out["metar_report_time"] = metar_row.get("reportTime")

    fcsts: list[dict[str, Any]] = []
    if taf_row and isinstance(taf_row.get("fcsts"), list):
        fcsts = [f for f in taf_row["fcsts"] if isinstance(f, dict)]
        out["taf_issue_time"] = taf_row.get("issueTime")
        out["taf_raw"] = taf_row.get("rawTAF")

    day_for_slots = _anchor_date_utc(metar_row, fcsts) or date_str
    if day_for_slots and day_for_slots != date_str:
        out["slot_date_used_utc"] = day_for_slots

    if baseline:
        request["weather"] = dict(baseline)
    elif not metar_row:
        request.setdefault("weather", {})

    if fcsts and day_for_slots:
        for ts in slots_in:
            if not isinstance(ts, dict):
                continue
            sid = ts.get("id")
            start = ts.get("start")
            end = ts.get("end")
            if not sid or not start or not end:
                continue
            rng = _slot_range_unix_utc(day_for_slots, str(start), str(end))
            if not rng:
                continue
            f0, f1 = rng
            fcst = _fcst_for_window(fcsts, f0, f1)
            if fcst:
                snap = taf_fcst_to_snapshot(fcst)
                snap["notes"] = f"{snap.get('notes', '')} ({icao} window {start}-{end}Z)".strip()
                by_slot[str(sid)] = snap

    if by_slot:
        request["weather_by_slot"] = by_slot

    if (not baseline) and fcsts:
        fb = taf_fcst_to_snapshot(fcsts[0])
        fb["notes"] = f"TAF baseline (first period) {icao}"
        request["weather"] = dict(fb)
        baseline = fb
        out["taf_baseline_only"] = not bool(metar_row)

    if not baseline and not by_slot:
        out["error"] = out.get("metar_error") or out.get("taf_error") or "no_awc_data"
        return out

    out["ok"] = True
    out["slots_from_taf"] = list(by_slot.keys())
    return out

