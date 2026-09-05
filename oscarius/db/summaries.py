"""Daily therapy summaries and session access for OSCAR databases."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class DailySummary:
    """Pre-calculated clinical statistics for a single OSCAR sleep day."""

    id: int
    profile_id: int
    date: str  # YYYY-MM-DD
    total_hours: float
    ahi: float
    oahi: float
    cahi: float
    obstructive_hypopnea_count: int
    central_hypopnea_count: int
    all_apnea_count: int
    leak_median: float
    leak_95: float
    pressure_median: float
    pressure_95: float
    compliance_flag: bool


@dataclass(frozen=True)
class Session:
    """Represents a continuous therapy or recording session."""

    id: int
    machine_id: int
    start_time: int  # ms since epoch
    end_time: int  # ms since epoch
    enabled: bool
    summary_only: bool
    brand: Optional[str] = None
    model: Optional[str] = None

    @property
    def duration_hours(self) -> float:
        """Computes the total session duration in decimal hours."""
        return max(0.0, (self.end_time - self.start_time) / 3600000.0)


def calculate_oscar_day(epoch_ms: int) -> str:
    """Calculates the OSCAR noon-to-noon day identifier (YYYY-MM-DD) for a given epoch millisecond.

    An OSCAR day runs from 12:00 (noon) to 12:00 the following calendar day,
    ensuring midnight-crossing sleep sessions are cataloged under the initial evening.

    @param epoch_ms: Timestamp in milliseconds since Unix epoch.
    @return: ISO date string (YYYY-MM-DD).
    """
    epoch_sec = epoch_ms // 1000
    shifted_sec = epoch_sec - 12 * 3600
    return datetime.fromtimestamp(shifted_sec, tz=timezone.utc).strftime("%Y-%m-%d")


def get_daily_summary(
    conn: sqlite3.Connection, profile_id: int, date: str
) -> Optional[DailySummary]:
    """Retrieves pre-computed summary statistics for a profile on an OSCAR day.

    @param conn: Active database connection.
    @param profile_id: Database profile ID.
    @param date: OSCAR day string (YYYY-MM-DD).
    @return: DailySummary instance if found, None otherwise.
    """
    row = conn.execute(
        """
        SELECT id, profile_id, date, total_hours, ahi, oahi, cahi,
               obstructive_hypopnea_count, central_hypopnea_count, all_apnea_count,
               leak_median, leak_95, pressure_median, pressure_95, compliance_flag
        FROM daily_summaries
        WHERE profile_id = ? AND date = ?
        """,
        (profile_id, date),
    ).fetchone()

    if row is None:
        return None

    return DailySummary(
        id=row["id"],
        profile_id=row["profile_id"],
        date=row["date"],
        total_hours=float(row["total_hours"] or 0.0),
        ahi=float(row["ahi"] or 0.0),
        oahi=float(row["oahi"] or 0.0),
        cahi=float(row["cahi"] or 0.0),
        obstructive_hypopnea_count=int(row["obstructive_hypopnea_count"] or 0),
        central_hypopnea_count=int(row["central_hypopnea_count"] or 0),
        all_apnea_count=int(row["all_apnea_count"] or 0),
        leak_median=float(row["leak_median"] or 0.0),
        leak_95=float(row["leak_95"] or 0.0),
        pressure_median=float(row["pressure_median"] or 0.0),
        pressure_95=float(row["pressure_95"] or 0.0),
        compliance_flag=bool(row["compliance_flag"]),
    )


def list_daily_summaries(
    conn: sqlite3.Connection,
    profile_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[DailySummary]:
    """Lists daily summaries for a profile within an optional date range.

    @param conn: Active database connection.
    @param profile_id: Database profile ID.
    @param start_date: Optional inclusive start date (YYYY-MM-DD).
    @param end_date: Optional inclusive end date (YYYY-MM-DD).
    @param limit: Optional max number of records.
    @return: List of DailySummary records ordered chronologically descending.
    """
    query = """
        SELECT id, profile_id, date, total_hours, ahi, oahi, cahi,
               obstructive_hypopnea_count, central_hypopnea_count, all_apnea_count,
               leak_median, leak_95, pressure_median, pressure_95, compliance_flag
        FROM daily_summaries
        WHERE profile_id = ?
    """
    params: list = [profile_id]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY date DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(query, tuple(params)).fetchall()
    return [
        DailySummary(
            id=row["id"],
            profile_id=row["profile_id"],
            date=row["date"],
            total_hours=float(row["total_hours"] or 0.0),
            ahi=float(row["ahi"] or 0.0),
            oahi=float(row["oahi"] or 0.0),
            cahi=float(row["cahi"] or 0.0),
            obstructive_hypopnea_count=int(row["obstructive_hypopnea_count"] or 0),
            central_hypopnea_count=int(row["central_hypopnea_count"] or 0),
            all_apnea_count=int(row["all_apnea_count"] or 0),
            leak_median=float(row["leak_median"] or 0.0),
            leak_95=float(row["leak_95"] or 0.0),
            pressure_median=float(row["pressure_median"] or 0.0),
            pressure_95=float(row["pressure_95"] or 0.0),
            compliance_flag=bool(row["compliance_flag"]),
        )
        for row in rows
    ]


def list_sessions_for_day(
    conn: sqlite3.Connection, profile_id: int, oscar_day: str
) -> list[Session]:
    """Retrieves all therapy sessions that took place during a designated OSCAR day.

    @param conn: Active database connection.
    @param profile_id: Database profile ID.
    @param oscar_day: OSCAR day string (YYYY-MM-DD).
    @return: List of Session records.
    """
    rows = conn.execute(
        """
        SELECT s.id, s.machine_id, s.start_time, s.end_time, s.enabled, s.summary_only,
               m.brand, m.model
        FROM sessions s
        JOIN machines m ON s.machine_id = m.id
        WHERE m.profile_id = ?
          AND s.enabled = 1
        ORDER BY s.start_time ASC
        """,
        (profile_id,),
    ).fetchall()

    matching_sessions = []
    for row in rows:
        if calculate_oscar_day(row["start_time"]) == oscar_day:
            matching_sessions.append(
                Session(
                    id=row["id"],
                    machine_id=row["machine_id"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    enabled=bool(row["enabled"]),
                    summary_only=bool(row["summary_only"]),
                    brand=row["brand"],
                    model=row["model"],
                )
            )
    return matching_sessions


def list_available_days(conn: sqlite3.Connection, profile_id: int) -> list[str]:
    """Lists all distinct OSCAR dates available for a profile, sorted descending.

    @param conn: Active database connection.
    @param profile_id: Database profile ID.
    @return: List of YYYY-MM-DD date strings.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT date
        FROM daily_summaries
        WHERE profile_id = ?
        ORDER BY date DESC
        """,
        (profile_id,),
    ).fetchall()
    return [row["date"] for row in rows]
