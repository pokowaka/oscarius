"""Tests for creating and initializing an OSCAR Schema v18 database."""

import sqlite3
import pytest
from pathlib import Path

from oscarius.db.connection import get_schema_version, verify_schema_version
from oscarius.db.schema import create_database_schema, init_default_channels
from oscarius.db.waveforms import list_channels


def test_create_database_schema_initializes_tables():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    assert get_schema_version(conn) == 0
    create_database_schema(conn, version=18)

    assert get_schema_version(conn) == 18
    assert verify_schema_version(conn) == 18

    # Check key tables exist
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "profiles" in tables
    assert "machines" in tables
    assert "sessions" in tables
    assert "channels" in tables
    assert "daily_summaries" in tables
    assert "event_lists" in tables
    assert "event_data" in tables
    assert "respiratory_events" in tables
    conn.close()


def test_init_default_channels_populates_profile_channels():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_database_schema(conn, version=18)

    conn.execute(
        "INSERT INTO profiles (id, username, data_folder, status) VALUES (1, 'user', '/dir', 'active')"
    )
    init_default_channels(conn, profile_id=1)

    channels = list_channels(conn, profile_id=1)
    codes = {c.channel_code for c in channels}

    assert "FlowRate" in codes
    assert "Pressure" in codes
    assert "Leak" in codes
    assert "Obstructive" in codes
    assert "ClearAirway" in codes
    assert "Hypopnea" in codes
    conn.close()
