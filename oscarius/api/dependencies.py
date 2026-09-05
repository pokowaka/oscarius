"""FastAPI dependency injection providers."""

import os
import sqlite3
from typing import Generator
from pathlib import Path

from oscarius.db.connection import open_database


def get_db_path() -> Path:
    """Resolves the default OSCAR SQLite database path from environment or home folder."""
    env_path = os.getenv("OSCARIUS_DB_PATH")
    if env_path:
        return Path(env_path)

    # Standard OSCAR 2.0 path: Documents/OSCAR20_Data/oscar.db
    home = Path.home()
    return home / "Documents" / "OSCAR20_Data" / "oscar.db"


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Provides a database connection for request lifecycle."""
    db_path = get_db_path()
    conn = open_database(db_path, read_only=True)
    try:
        yield conn
    finally:
        conn.close()
