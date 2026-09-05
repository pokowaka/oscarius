"""Tests for database connection and schema verification."""

import sqlite3
import pytest
from pathlib import Path

from oscarius.db.connection import (
    open_database,
    get_schema_version,
    verify_schema_version,
    SchemaVersionError,
    DatabaseNotFoundError,
)


def test_open_database_returns_connection_with_row_factory(tmp_path: Path):
    db_file = tmp_path / "test.db"
    conn_create = sqlite3.connect(db_file)
    conn_create.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn_create.execute("INSERT INTO schema_version VALUES (18)")
    conn_create.commit()
    conn_create.close()

    conn = open_database(db_file, read_only=True)
    assert isinstance(conn, sqlite3.Connection)
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row["version"] == 18
    conn.close()


def test_open_database_raises_if_file_not_found(tmp_path: Path):
    missing_file = tmp_path / "nonexistent.db"
    with pytest.raises(DatabaseNotFoundError):
        open_database(missing_file)


def test_get_schema_version(mock_db_conn: sqlite3.Connection):
    version = get_schema_version(mock_db_conn)
    assert version == 18


def test_get_schema_version_returns_zero_when_table_missing():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    assert get_schema_version(conn) == 0
    conn.close()


def test_verify_schema_version_succeeds_for_supported_version(mock_db_conn: sqlite3.Connection):
    version = verify_schema_version(mock_db_conn, min_version=12, max_version=18)
    assert version == 18


def test_verify_schema_version_fails_for_unsupported_version(mock_db_conn: sqlite3.Connection):
    with pytest.raises(SchemaVersionError, match="Unsupported schema version: 18"):
        verify_schema_version(mock_db_conn, min_version=1, max_version=10)
