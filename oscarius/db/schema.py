"""Schema creation and channel initialization for OSCAR SQLite databases (Schema v18)."""

import sqlite3

SCHEMA_V18_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    data_folder TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'missing', 'archived')),
    status_changed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS machines (
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

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    summary_only INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(machine_id) REFERENCES machines(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    channel_code TEXT NOT NULL,
    label TEXT NOT NULL,
    fullname TEXT,
    default_color TEXT,
    type INTEGER DEFAULT 0,
    UNIQUE(profile_id, channel_id),
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS daily_summaries (
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

CREATE TABLE IF NOT EXISTS event_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    event_type INTEGER NOT NULL,
    gain REAL DEFAULT 1.0,
    offset REAL DEFAULT 0.0,
    sample_rate REAL DEFAULT 25.0,
    first_time INTEGER NOT NULL,
    last_time INTEGER NOT NULL,
    count INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_list_id INTEGER UNIQUE NOT NULL,
    data_blob BLOB NOT NULL,
    checksum INTEGER NOT NULL,
    FOREIGN KEY(event_list_id) REFERENCES event_lists(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS respiratory_events (
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

-- Optimization Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_machine ON sessions(machine_id, start_time);
CREATE INDEX IF NOT EXISTS idx_daily_summaries_profile_date ON daily_summaries(profile_id, date);
CREATE INDEX IF NOT EXISTS idx_event_lists_session_channel ON event_lists(session_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_respiratory_events_session ON respiratory_events(session_id, start_time);
"""

DEFAULT_CHANNELS = [
    (0x1000, "FlowRate", "Flow Rate", "Flow Rate (L/min)", "#0000ff", 0),
    (0x1001, "Pressure", "Mask Pressure", "Mask Pressure (cmH2O)", "#ff0000", 0),
    (0x1002, "Leak", "Leak Rate", "Leak Rate (L/min)", "#00aa00", 0),
    (0x1004, "EPAP", "EPAP", "Expiratory Positive Airway Pressure (cmH2O)", "#ff8800", 0),
    (0x1005, "TidalVolume", "Tidal Volume", "Tidal Volume (ml)", "#008888", 0),
    (0x1006, "MinuteVent", "Minute Vent", "Minute Ventilation (L/min)", "#880088", 0),
    (0x1007, "RespRate", "Resp. Rate", "Respiratory Rate (breaths/min)", "#444444", 0),
    (0x1008, "Snore", "Snore", "Snore Index", "#aa6600", 0),
    (0x2001, "Obstructive", "OA", "Obstructive Apnea", "#333333", 1),
    (0x2002, "ClearAirway", "CA", "Central / Clear Airway Apnea", "#990099", 1),
    (0x2003, "Hypopnea", "H", "Hypopnea", "#0088cc", 1),
    (0x2004, "CSR", "CSR", "Cheyne-Stokes Respiration", "#cc8800", 2),
    (0x2005, "FlowLimitation", "FL", "Flow Limitation", "#888800", 2),
]


def create_database_schema(conn: sqlite3.Connection, version: int = 18) -> None:
    """Creates all OSCAR schema tables and records the schema version.

    @param conn: Active database connection.
    @param version: Schema version number to record (default 18).
    """
    conn.executescript(SCHEMA_V18_DDL)
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()


def init_default_channels(conn: sqlite3.Connection, profile_id: int) -> None:
    """Populates standard channel definitions for a newly created profile.

    @param conn: Active database connection.
    @param profile_id: Profile ID to associate the channels with.
    """
    channel_rows = [
        (profile_id, ch_id, code, label, fullname, color, ch_type)
        for (ch_id, code, label, fullname, color, ch_type) in DEFAULT_CHANNELS
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO channels (
            profile_id, channel_id, channel_code, label, fullname, default_color, type
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        channel_rows,
    )
    conn.commit()
