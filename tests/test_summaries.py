"""Tests for sessions and daily summaries repository operations."""

import sqlite3
import pytest

from oscarius.db.summaries import (
    DailySummary,
    Session,
    calculate_oscar_day,
    get_daily_summary,
    list_daily_summaries,
    list_sessions_for_day,
    list_available_days,
)


def test_calculate_oscar_day():
    # 2026-09-04 23:00:00 UTC = 1788562800000 ms -> belongs to 2026-09-04
    assert calculate_oscar_day(1788562800000) == "2026-09-04"
    # 2026-09-05 06:00:00 UTC = 1788588000000 ms -> belongs to 2026-09-04 (before noon Sep 5)
    assert calculate_oscar_day(1788588000000) == "2026-09-04"
    # 2026-09-05 13:00:00 UTC = 1788613200000 ms -> belongs to 2026-09-05 (after noon Sep 5)
    assert calculate_oscar_day(1788613200000) == "2026-09-05"


def test_get_daily_summary(mock_db_conn: sqlite3.Connection):
    summary = get_daily_summary(mock_db_conn, profile_id=1, date="2026-09-04")
    assert summary is not None
    assert isinstance(summary, DailySummary)
    assert summary.date == "2026-09-04"
    assert summary.total_hours == 8.0
    assert summary.ahi == 1.5
    assert summary.oahi == 0.5
    assert summary.cahi == 1.0
    assert summary.obstructive_hypopnea_count == 4
    assert summary.central_hypopnea_count == 8
    assert summary.all_apnea_count == 12
    assert summary.leak_median == 2.4
    assert summary.leak_95 == 14.8
    assert summary.pressure_median == 8.5
    assert summary.pressure_95 == 12.2
    assert summary.compliance_flag is True


def test_get_daily_summary_not_found(mock_db_conn: sqlite3.Connection):
    summary = get_daily_summary(mock_db_conn, profile_id=1, date="1999-01-01")
    assert summary is None


def test_list_daily_summaries(mock_db_conn: sqlite3.Connection):
    summaries = list_daily_summaries(mock_db_conn, profile_id=1)
    assert len(summaries) == 1
    assert summaries[0].date == "2026-09-04"


def test_list_sessions_for_day(mock_db_conn: sqlite3.Connection):
    sessions = list_sessions_for_day(mock_db_conn, profile_id=1, oscar_day="2026-09-04")
    assert len(sessions) == 1
    sess = sessions[0]
    assert isinstance(sess, Session)
    assert sess.id == 1
    assert sess.brand == "ResMed"
    assert sess.model == "AirSense 11 AutoSet"
    assert sess.duration_hours == pytest.approx(8.0, 0.01)


def test_list_available_days(mock_db_conn: sqlite3.Connection):
    days = list_available_days(mock_db_conn, profile_id=1)
    assert days == ["2026-09-04"]
