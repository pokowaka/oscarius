"""Tests for Oscarius FastAPI REST endpoints."""

import sqlite3
import pytest
from fastapi.testclient import TestClient

from oscarius.api.app import create_app
from oscarius.api.dependencies import get_db


@pytest.fixture
def client(mock_db_conn: sqlite3.Connection) -> TestClient:
    """Provides a TestClient with overridden database dependency."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db_conn
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_list_profiles_endpoint(client: TestClient):
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) == 1
    assert profiles[0]["username"] == "default_user"


def test_get_profile_endpoint(client: TestClient):
    resp = client.get("/api/profiles/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"]["username"] == "default_user"
    assert len(data["machines"]) == 1
    assert data["machines"][0]["brand"] == "ResMed"


def test_get_profile_not_found(client: TestClient):
    resp = client.get("/api/profiles/999")
    assert resp.status_code == 404


def test_list_available_days_endpoint(client: TestClient):
    resp = client.get("/api/profiles/1/days")
    assert resp.status_code == 200
    days = resp.json()
    assert days == ["2026-09-04"]


def test_get_daily_summary_endpoint(client: TestClient):
    resp = client.get("/api/profiles/1/days/2026-09-04")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["date"] == "2026-09-04"
    assert data["summary"]["ahi"] == 1.5
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["id"] == 1


def test_get_daily_events_endpoint(client: TestClient):
    resp = client.get("/api/profiles/1/days/2026-09-04/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 2
    assert events[0]["duration"] == 22


def test_get_waveform_endpoint(client: TestClient):
    resp = client.get("/api/profiles/1/sessions/1/waveform?channel=FlowRate&points=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["channel_code"] == "FlowRate"
    assert len(data["timestamps_ms"]) == 50
    assert len(data["values"]) == 50


def test_static_files_mounted(tmp_path):
    from unittest.mock import patch
    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text("<!DOCTYPE html><html><body>Oscarius Web</body></html>")

    with patch("oscarius.api.app.FRONTEND_DIST", fake_dist):
        app = create_app()
        with TestClient(app) as tc:
            resp = tc.get("/")
            assert resp.status_code == 200
            assert "Oscarius Web" in resp.text
