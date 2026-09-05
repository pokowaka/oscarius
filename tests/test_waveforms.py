"""Tests for waveform BLOB decoding, channels, and respiratory events."""

import sqlite3
import pytest
import numpy as np

from oscarius.db.waveforms import (
    qcompress_decode,
    Channel,
    WaveformRecord,
    RespiratoryEvent,
    list_channels,
    get_channel_by_code,
    get_waveform,
    list_respiratory_events,
)


def test_qcompress_decode_valid():
    # 4-byte big endian length followed by zlib payload
    import struct, zlib
    raw = b"Hello, OSCAR waveform data!"
    header = struct.pack(">I", len(raw))
    payload = header + zlib.compress(raw)
    
    decompressed = qcompress_decode(payload)
    assert decompressed == raw


def test_qcompress_decode_invalid_header():
    with pytest.raises(ValueError, match="payload too short"):
        qcompress_decode(b"12")


def test_list_channels(mock_db_conn: sqlite3.Connection):
    channels = list_channels(mock_db_conn, profile_id=1)
    assert len(channels) == 5
    codes = {c.channel_code for c in channels}
    assert "FlowRate" in codes
    assert "Pressure" in codes


def test_get_channel_by_code(mock_db_conn: sqlite3.Connection):
    ch = get_channel_by_code(mock_db_conn, profile_id=1, channel_code="FlowRate")
    assert ch is not None
    assert ch.channel_id == 0x1000
    assert ch.label == "Flow Rate"


def test_get_waveform(mock_db_conn: sqlite3.Connection):
    # In mock_db_conn:
    # 100 samples with gain 0.1, offset 0.0, sample_rate 25.0, int16 values from -50 to 49
    wf = get_waveform(mock_db_conn, session_id=1, channel_code="FlowRate")
    assert wf is not None
    assert isinstance(wf, WaveformRecord)
    assert wf.count == 100
    assert wf.sample_rate == 25.0
    assert len(wf.values) == 100
    assert len(wf.timestamps_ms) == 100
    # First value was -50 * 0.1 = -5.0
    assert wf.values[0] == pytest.approx(-5.0, 0.001)
    # 50th value was 0 * 0.1 = 0.0
    assert wf.values[50] == pytest.approx(0.0, 0.001)
    # Timestamps interval for 25Hz is 1000/25 = 40ms
    assert wf.timestamps_ms[1] - wf.timestamps_ms[0] == 40


def test_list_respiratory_events(mock_db_conn: sqlite3.Connection):
    events = list_respiratory_events(mock_db_conn, session_id=1)
    assert len(events) == 2
    assert events[0].duration == 22
    assert events[0].channel_code == "Obstructive"
    assert events[1].duration == 18
    assert events[1].channel_code == "ClearAirway"
