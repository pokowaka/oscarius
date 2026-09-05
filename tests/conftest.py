"""Pytest fixtures for oscarius database tests."""

import sqlite3
import struct
import zlib
from pathlib import Path
import pytest


SCHEMA_V18_SQL = """
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    data_folder TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'missing', 'archived')),
    status_changed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE machines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    machine_id INTEGER NOT NULL,
    loader_name TEXT NOT NULL,
    machine_type INTEGER NOT NULL,
    brand TEXT,
    model TEXT,
    series TEXT,
    serial_number TEXT,
    model_number TEXT,
    last_imported TEXT,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    summary_only INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(machine_id) REFERENCES machines(id) ON DELETE CASCADE
);

CREATE TABLE channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    channel_code TEXT NOT NULL,
    label TEXT NOT NULL,
    fullname TEXT,
    default_color TEXT,
    type INTEGER DEFAULT 0,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    total_hours REAL DEFAULT 0,
    ahi REAL DEFAULT 0,
    oahi REAL DEFAULT 0,
    cahi REAL DEFAULT 0,
    obstructive_hypopnea_count INTEGER DEFAULT 0,
    central_hypopnea_count INTEGER DEFAULT 0,
    all_apnea_count INTEGER DEFAULT 0,
    leak_median REAL DEFAULT 0,
    leak_95 REAL DEFAULT 0,
    pressure_median REAL DEFAULT 0,
    pressure_95 REAL DEFAULT 0,
    compliance_flag INTEGER DEFAULT 0,
    UNIQUE(profile_id, date),
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE event_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    event_type INTEGER NOT NULL, -- 0: waveform, 1: event
    gain REAL DEFAULT 1.0,
    offset REAL DEFAULT 0.0,
    sample_rate REAL DEFAULT 25.0,
    first_time INTEGER NOT NULL,
    last_time INTEGER NOT NULL,
    count INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE event_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_list_id INTEGER UNIQUE NOT NULL,
    data_blob BLOB NOT NULL,
    checksum INTEGER NOT NULL,
    FOREIGN KEY(event_list_id) REFERENCES event_lists(id) ON DELETE CASCADE
);

CREATE TABLE respiratory_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    start_time INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    event_type INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
"""


def encode_qcompress(raw_bytes: bytes) -> bytes:
    """Encode raw bytes as a Qt qCompress payload (4-byte length + zlib stream)."""
    header = struct.pack(">I", len(raw_bytes))
    return header + zlib.compress(raw_bytes, level=9)


@pytest.fixture
def mock_db_conn() -> sqlite3.Connection:
    """Provides an in-memory SQLite database populated with schema v18 and test records."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_V18_SQL)

    # Insert schema version 18
    conn.execute("INSERT INTO schema_version (version) VALUES (18)")

    # Insert test profiles
    conn.execute(
        "INSERT INTO profiles (id, username, data_folder, status) VALUES (1, 'default_user', '/path/to/default', 'active')"
    )
    conn.execute(
        "INSERT INTO profiles (id, username, data_folder, status) VALUES (2, 'archived_user', '/path/to/archived', 'archived')"
    )

    # Insert test machine
    conn.execute(
        """
        INSERT INTO machines (id, profile_id, machine_id, loader_name, machine_type, brand, model, serial_number)
        VALUES (1, 1, 101, 'ResMed', 0, 'ResMed', 'AirSense 11 AutoSet', '23211234567')
        """
    )

    # Insert channel mapping
    channels_data = [
        (1, 1, 0x1000, "FlowRate", "Flow Rate", "Flow Rate (L/min)", "#0000ff", 0),
        (2, 1, 0x1001, "Pressure", "Mask Pressure", "Mask Pressure (cmH2O)", "#ff0000", 0),
        (3, 1, 0x1002, "Leak", "Leak Rate", "Leak Rate (L/min)", "#00aa00", 0),
        (4, 1, 0x2001, "Obstructive", "OA", "Obstructive Apnea", "#333333", 1),
        (5, 1, 0x2002, "ClearAirway", "CA", "Central Apnea", "#990099", 1),
    ]
    conn.executemany(
        """
        INSERT INTO channels (id, profile_id, channel_id, channel_code, label, fullname, default_color, type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        channels_data,
    )

    # OSCAR day: 2026-09-04 (sleep from 23:00 on Sep 4 to 07:00 on Sep 5)
    # 2026-09-04 23:00:00 UTC = 1788562800000 ms
    # 2026-09-05 07:00:00 UTC = 1788591600000 ms
    start_ms = 1788562800000
    end_ms = 1788591600000

    conn.execute(
        """
        INSERT INTO sessions (id, machine_id, start_time, end_time, enabled, summary_only)
        VALUES (1, 1, ?, ?, 1, 0)
        """,
        (start_ms, end_ms),
    )

    # Insert daily summary for 2026-09-04
    conn.execute(
        """
        INSERT INTO daily_summaries (
            id, profile_id, date, total_hours, ahi, oahi, cahi,
            obstructive_hypopnea_count, central_hypopnea_count, all_apnea_count,
            leak_median, leak_95, pressure_median, pressure_95, compliance_flag
        ) VALUES (1, 1, '2026-09-04', 8.0, 1.5, 0.5, 1.0, 4, 8, 12, 2.4, 14.8, 8.5, 12.2, 1)
        """
    )

    # Insert respiratory events
    conn.execute(
        """
        INSERT INTO respiratory_events (id, session_id, profile_id, channel_id, start_time, duration, event_type)
        VALUES (1, 1, 1, 0x2001, ?, 22, 1)
        """,
        (start_ms + 3600000,),  # 1 hour into sleep
    )
    conn.execute(
        """
        INSERT INTO respiratory_events (id, session_id, profile_id, channel_id, start_time, duration, event_type)
        VALUES (2, 1, 1, 0x2002, ?, 18, 2)
        """,
        (start_ms + 7200000,),  # 2 hours into sleep
    )

    # Insert a synthetic Flow Rate waveform (100 samples)
    # raw samples: int16 values from -50 to 50
    raw_samples = b"".join(struct.pack("<h", val) for val in range(-50, 50))
    blob = encode_qcompress(raw_samples)
    conn.execute(
        """
        INSERT INTO event_lists (
            id, session_id, profile_id, channel_id, event_type, gain, offset,
            sample_rate, first_time, last_time, count
        ) VALUES (1, 1, 1, 0x1000, 0, 0.1, 0.0, 25.0, ?, ?, 100)
        """,
        (start_ms, start_ms + 4000),
    )
    conn.execute(
        "INSERT INTO event_data (id, event_list_id, data_blob, checksum) VALUES (1, 1, ?, 0)",
        (blob,),
    )

    conn.commit()
    yield conn
    conn.close()
