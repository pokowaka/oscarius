"""SQLite database connection management and schema validation for OSCAR databases.

This module provides verified read-only or read-write access to SQLite databases
originating from OSCAR 2.0 (Schema versions 12 through 18).
"""

import sqlite3
from pathlib import Path


class DatabaseError(Exception):
    """Base exception for Oscarius database operations."""


class DatabaseNotFoundError(DatabaseError):
    """Raised when the specified SQLite database file does not exist on disk."""


class SchemaVersionError(DatabaseError):
    """Raised when an OSCAR database has an unsupported schema version."""


def open_database(
    db_path: Path | str,
    read_only: bool = True,
    create: bool = False,
) -> sqlite3.Connection:
    """Opens a connection to an OSCAR SQLite database with dict-like row access.

    @param db_path: Filesystem path to the SQLite database file or memory URI.
    @param read_only: If true, opens database in immutable/read-only mode.
    @param create: If true and read_only is false, allows creating a new database file.
    @return: Configured sqlite3.Connection with Row row_factory enabled.
    """
    path_obj = Path(db_path) if isinstance(db_path, str) else db_path

    if str(db_path) != ":memory:" and not str(db_path).startswith("file:"):
        if read_only:
            if not path_obj.is_file():
                raise DatabaseNotFoundError(f"Database file not found at path: {path_obj}")
            uri = f"file:{path_obj.resolve()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        else:
            if not create and not path_obj.is_file():
                raise DatabaseNotFoundError(f"Database file not found at path: {path_obj}")
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path_obj, check_same_thread=False)
    else:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)

    conn.row_factory = sqlite3.Row
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Retrieves the current schema version number recorded in the database.

    @param conn: Active SQLite connection to check.
    @return: Integer schema version (e.g., 18), or 0 if schema_version table is absent.
    """
    try:
        row = conn.execute(
            "SELECT MAX(version) AS version FROM schema_version"
        ).fetchone()
        if row and row["version"] is not None:
            return int(row["version"])
        return 0
    except sqlite3.OperationalError:
        return 0


def verify_schema_version(
    conn: sqlite3.Connection,
    min_version: int = 12,
    max_version: int = 18,
) -> int:
    """Asserts that the database schema is compatible with the supported versions.

    @param conn: Active SQLite connection to validate.
    @param min_version: Minimum compatible schema version (default 12).
    @param max_version: Maximum supported schema version (default 18).
    @return: Verified schema version number.
    @raise SchemaVersionError: When schema version falls outside the supported range.
    """
    version = get_schema_version(conn)
    if version < min_version or version > max_version:
        raise SchemaVersionError(
            f"Unsupported schema version: {version}. "
            f"Oscarius supports schema versions {min_version} to {max_version}."
        )
    return version
