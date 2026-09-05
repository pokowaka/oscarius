"""Tests for profile and machine repository operations."""

import sqlite3
import pytest

from oscarius.db.profiles import (
    Profile,
    Machine,
    list_profiles,
    get_profile,
    get_profile_by_username,
    list_machines,
)


def test_list_profiles_active_only(mock_db_conn: sqlite3.Connection):
    profiles = list_profiles(mock_db_conn, active_only=True)
    assert len(profiles) == 1
    assert profiles[0].username == "default_user"
    assert profiles[0].status == "active"
    assert isinstance(profiles[0], Profile)


def test_list_profiles_all(mock_db_conn: sqlite3.Connection):
    profiles = list_profiles(mock_db_conn, active_only=False)
    assert len(profiles) == 2
    usernames = {p.username for p in profiles}
    assert usernames == {"default_user", "archived_user"}


def test_get_profile_by_id(mock_db_conn: sqlite3.Connection):
    profile = get_profile(mock_db_conn, profile_id=1)
    assert profile is not None
    assert profile.id == 1
    assert profile.username == "default_user"


def test_get_profile_by_id_not_found(mock_db_conn: sqlite3.Connection):
    profile = get_profile(mock_db_conn, profile_id=999)
    assert profile is None


def test_get_profile_by_username(mock_db_conn: sqlite3.Connection):
    profile = get_profile_by_username(mock_db_conn, "default_user")
    assert profile is not None
    assert profile.id == 1


def test_list_machines(mock_db_conn: sqlite3.Connection):
    machines = list_machines(mock_db_conn, profile_id=1)
    assert len(machines) == 1
    m = machines[0]
    assert isinstance(m, Machine)
    assert m.brand == "ResMed"
    assert m.model == "AirSense 11 AutoSet"
    assert m.serial_number == "23211234567"
