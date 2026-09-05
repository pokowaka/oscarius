"""FastAPI route handlers for OSCAR sleep therapy endpoints."""

import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from oscarius.api.dependencies import get_db
from oscarius.db.profiles import (
    list_profiles,
    get_profile,
    list_machines,
)
from oscarius.db.summaries import (
    get_daily_summary,
    list_available_days,
    list_sessions_for_day,
)
from oscarius.db.waveforms import (
    get_waveform,
    list_respiratory_events,
)
from oscarius.signal.lttb import window_and_downsample

router = APIRouter(prefix="/api")


@router.get("/profiles")
def api_list_profiles(
    active_only: bool = True, conn: sqlite3.Connection = Depends(get_db)
):
    """Retrieves all registered user profiles."""
    profiles = list_profiles(conn, active_only=active_only)
    return [
        {
            "id": p.id,
            "username": p.username,
            "data_folder": p.data_folder,
            "status": p.status,
            "created_at": p.created_at,
        }
        for p in profiles
    ]


@router.get("/profiles/{profile_id}")
def api_get_profile(profile_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Retrieves profile details and registered devices."""
    profile = get_profile(conn, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

    machines = list_machines(conn, profile_id)
    return {
        "profile": {
            "id": profile.id,
            "username": profile.username,
            "data_folder": profile.data_folder,
            "status": profile.status,
        },
        "machines": [
            {
                "id": m.id,
                "brand": m.brand,
                "model": m.model,
                "serial_number": m.serial_number,
                "machine_type": m.machine_type,
                "loader_name": m.loader_name,
            }
            for m in machines
        ],
    }


@router.get("/profiles/{profile_id}/days")
def api_list_available_days(
    profile_id: int, conn: sqlite3.Connection = Depends(get_db)
):
    """Lists all available OSCAR dates (noon-to-noon) for a profile."""
    profile = get_profile(conn, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return list_available_days(conn, profile_id)


@router.get("/profiles/{profile_id}/days/{date}")
def api_get_daily_summary(
    profile_id: int, date: str, conn: sqlite3.Connection = Depends(get_db)
):
    """Retrieves daily summary metrics and sessions for a designated OSCAR day."""
    profile = get_profile(conn, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

    summary = get_daily_summary(conn, profile_id, date)
    sessions = list_sessions_for_day(conn, profile_id, date)

    if summary is None and not sessions:
        raise HTTPException(
            status_code=404,
            detail=f"No therapy data found for date {date} on profile {profile_id}",
        )

    summary_dict = None
    if summary:
        summary_dict = {
            "date": summary.date,
            "total_hours": summary.total_hours,
            "ahi": summary.ahi,
            "oahi": summary.oahi,
            "cahi": summary.cahi,
            "obstructive_hypopnea_count": summary.obstructive_hypopnea_count,
            "central_hypopnea_count": summary.central_hypopnea_count,
            "all_apnea_count": summary.all_apnea_count,
            "leak_median": summary.leak_median,
            "leak_95": summary.leak_95,
            "pressure_median": summary.pressure_median,
            "pressure_95": summary.pressure_95,
            "compliance_flag": summary.compliance_flag,
        }

    return {
        "date": date,
        "summary": summary_dict,
        "sessions": [
            {
                "id": s.id,
                "machine_id": s.machine_id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration_hours": s.duration_hours,
                "brand": s.brand,
                "model": s.model,
            }
            for s in sessions
        ],
    }


@router.get("/profiles/{profile_id}/days/{date}/events")
def api_get_daily_events(
    profile_id: int, date: str, conn: sqlite3.Connection = Depends(get_db)
):
    """Retrieves all respiratory events occurring across all sessions on that day."""
    profile = get_profile(conn, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

    sessions = list_sessions_for_day(conn, profile_id, date)
    all_events = []
    for s in sessions:
        events = list_respiratory_events(conn, s.id)
        for ev in events:
            all_events.append(
                {
                    "id": ev.id,
                    "session_id": ev.session_id,
                    "channel_code": ev.channel_code,
                    "start_time_ms": ev.start_time_ms,
                    "duration": ev.duration,
                    "label": ev.label,
                    "fullname": ev.fullname,
                }
            )

    all_events.sort(key=lambda x: x["start_time_ms"])
    return all_events


@router.get("/profiles/{profile_id}/sessions/{session_id}/waveform")
def api_get_session_waveform(
    profile_id: int,
    session_id: int,
    channel: str = Query(default="FlowRate", description="Symbolic channel code"),
    points: int = Query(
        default=2000, ge=10, le=20000, description="Target downsampling point count"
    ),
    start_ms: Optional[int] = Query(
        default=None, description="Optional start time window in ms"
    ),
    end_ms: Optional[int] = Query(
        default=None, description="Optional end time window in ms"
    ),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Extracts, decodes, and LTTB-downsamples a waveform for high-performance canvas rendering."""
    profile = get_profile(conn, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

    wf = get_waveform(conn, session_id, channel_code=channel)
    if wf is None:
        raise HTTPException(
            status_code=404,
            detail=f"Waveform channel {channel} not found for session {session_id}",
        )

    down_t, down_v = window_and_downsample(
        timestamps=wf.timestamps_ms,
        values=wf.values,
        target_points=points,
        start_time_ms=start_ms,
        end_time_ms=end_ms,
    )

    return {
        "session_id": session_id,
        "channel_code": channel,
        "sample_rate": wf.sample_rate,
        "first_time_ms": wf.first_time_ms,
        "last_time_ms": wf.last_time_ms,
        "total_points": wf.count,
        "downsampled_points": len(down_t),
        "timestamps_ms": down_t,
        "values": down_v,
    }
