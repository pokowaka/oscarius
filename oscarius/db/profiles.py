"""Profile and device machine access for OSCAR databases."""

import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Profile:
    """Represents an OSCAR user profile."""

    id: int
    username: str
    data_folder: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class Machine:
    """Represents a CPAP, oximeter, or wearable device registered to a profile."""

    id: int
    profile_id: int
    machine_id: int
    loader_name: str
    machine_type: int
    brand: Optional[str] = None
    model: Optional[str] = None
    series: Optional[str] = None
    serial_number: Optional[str] = None
    model_number: Optional[str] = None
    last_imported: Optional[str] = None


def list_profiles(conn: sqlite3.Connection, active_only: bool = True) -> list[Profile]:
    """Lists all user profiles in the database.

    @param conn: Active database connection.
    @param active_only: When true, filters profiles to status='active'.
    @return: List of Profile records ordered by id.
    """
    query = "SELECT id, username, data_folder, status, created_at, updated_at FROM profiles"
    params: tuple = ()
    if active_only:
        query += " WHERE status = 'active'"
    query += " ORDER BY id ASC"

    rows = conn.execute(query, params).fetchall()
    return [
        Profile(
            id=row["id"],
            username=row["username"],
            data_folder=row["data_folder"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def get_profile(conn: sqlite3.Connection, profile_id: int) -> Optional[Profile]:
    """Retrieves a single user profile by primary key ID.

    @param conn: Active database connection.
    @param profile_id: Database profile ID.
    @return: Profile instance if found, None otherwise.
    """
    row = conn.execute(
        "SELECT id, username, data_folder, status, created_at, updated_at FROM profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()
    if row is None:
        return None
    return Profile(
        id=row["id"],
        username=row["username"],
        data_folder=row["data_folder"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_profile_by_username(conn: sqlite3.Connection, username: str) -> Optional[Profile]:
    """Retrieves a single user profile by username.

    @param conn: Active database connection.
    @param username: Unique username string.
    @return: Profile instance if found, None otherwise.
    """
    row = conn.execute(
        "SELECT id, username, data_folder, status, created_at, updated_at FROM profiles WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return None
    return Profile(
        id=row["id"],
        username=row["username"],
        data_folder=row["data_folder"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_machines(conn: sqlite3.Connection, profile_id: int) -> list[Machine]:
    """Lists all therapy and monitoring machines associated with a profile.

    @param conn: Active database connection.
    @param profile_id: Database profile ID.
    @return: List of Machine records.
    """
    rows = conn.execute(
        """
        SELECT id, profile_id, machine_id, loader_name, machine_type,
               brand, model, series, serial_number, model_number, last_imported
        FROM machines
        WHERE profile_id = ?
        ORDER BY id ASC
        """,
        (profile_id,),
    ).fetchall()
    return [
        Machine(
            id=row["id"],
            profile_id=row["profile_id"],
            machine_id=row["machine_id"],
            loader_name=row["loader_name"],
            machine_type=row["machine_type"],
            brand=row["brand"],
            model=row["model"],
            series=row["series"],
            serial_number=row["serial_number"],
            model_number=row["model_number"],
            last_imported=row["last_imported"],
        )
        for row in rows
    ]
