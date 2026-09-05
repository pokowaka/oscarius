"""Tests for the ResMed SD card importer."""

import json
from pathlib import Path
import pytest

from oscarius.db.connection import open_database
from oscarius.db.profiles import get_profile_by_username, list_machines
from oscarius.db.summaries import get_daily_summary, list_sessions_for_day
from oscarius.db.waveforms import get_waveform, list_respiratory_events
from oscarius.importers.resmed import (
    detect_resmed_card,
    read_resmed_identification,
    import_resmed_sd_card,
    ImportResult,
)
from tests.test_edf import create_synthetic_edf_bytes


@pytest.fixture
def mock_resmed_sd_card(tmp_path: Path) -> Path:
    """Creates a mock ResMed SD card directory hierarchy with valid EDF files."""
    card_dir = tmp_path / "resmed_sd"
    card_dir.mkdir()

    # Identification.json
    ident_data = {
        "FlowGenerator": {
            "IdentificationProfiles": {
                "Product": {
                    "SerialNumber": "23249988776",
                    "FamilyName": "AirSense 11",
                    "ProductTitle": "AutoSet",
                }
            }
        }
    }
    with open(card_dir / "Identification.json", "w") as f:
        json.dump(ident_data, f)

    # Dummy STR.edf
    with open(card_dir / "STR.edf", "wb") as f:
        f.write(create_synthetic_edf_bytes(label="Summary", num_records=1))

    # DATALOG directory
    datalog = card_dir / "DATALOG"
    datalog.mkdir()

    # BRP file (Flow Rate at 25 Hz)
    brp_bytes = create_synthetic_edf_bytes(
        label="Flow",
        num_records=4,
        record_duration=1.0,
        samples_per_record=25,
        sample_values=[val for val in range(-50, 50)],
    )
    with open(datalog / "20260904_230000_BRP.edf", "wb") as f:
        f.write(brp_bytes)

    # PLD file (Pressure and Leak at 1 Hz)
    # create a 2-signal EDF: Mask.Press and Leak
    pld_bytes = create_synthetic_edf_bytes(
        label="Mask.Press",
        num_records=4,
        record_duration=1.0,
        samples_per_record=1,
        sample_values=[80, 85, 90, 95],  # 8.0 to 9.5 cmH2O
    )
    with open(datalog / "20260904_230000_PLD.edf", "wb") as f:
        f.write(pld_bytes)

    # EVE file (Annotations)
    eve_bytes = create_synthetic_edf_bytes(
        label="Dummy",
        num_records=4,
        record_duration=1.0,
        samples_per_record=1,
        annotations_text="+1.0\x152.0\x14Obstructive Apnea\x14\x00+2.5\x151.5\x14Central Apnea\x14\x00",
    )
    with open(datalog / "20260904_230000_EVE.edf", "wb") as f:
        f.write(eve_bytes)

    return card_dir


def test_detect_resmed_card(mock_resmed_sd_card: Path):
    assert detect_resmed_card(mock_resmed_sd_card) is True
    assert detect_resmed_card(mock_resmed_sd_card.parent) is False


def test_read_resmed_identification(mock_resmed_sd_card: Path):
    ident = read_resmed_identification(mock_resmed_sd_card)
    assert ident["serial_number"] == "23249988776"
    assert ident["brand"] == "ResMed"
    assert "AirSense 11" in ident["model"]


def test_import_resmed_sd_card_end_to_end(mock_resmed_sd_card: Path, tmp_path: Path):
    db_path = tmp_path / "imported_oscar.db"

    result = import_resmed_sd_card(
        card_path=mock_resmed_sd_card,
        db_path=db_path,
        username="Erwin",
    )

    assert isinstance(result, ImportResult)
    assert result.sessions_imported == 1
    assert result.serial_number == "23249988776"

    # Verify database contents directly
    conn = open_database(db_path, read_only=True)

    # Profile created
    profile = get_profile_by_username(conn, "Erwin")
    assert profile is not None

    # Machine created
    machines = list_machines(conn, profile.id)
    assert len(machines) == 1
    assert machines[0].serial_number == "23249988776"

    # Session created
    sessions = list_sessions_for_day(conn, profile.id, "2026-09-04")
    assert len(sessions) == 1
    session_id = sessions[0].id

    # Daily summary computed
    summary = get_daily_summary(conn, profile.id, "2026-09-04")
    assert summary is not None
    assert summary.all_apnea_count == 2

    # Waveform stored & decodable
    wf = get_waveform(conn, session_id, "FlowRate")
    assert wf is not None
    assert wf.count == 100

    # Respiratory events stored
    events = list_respiratory_events(conn, session_id)
    assert len(events) == 2
    assert events[0].channel_code == "Obstructive"
    assert events[1].channel_code == "ClearAirway"

    conn.close()
