"""Channel metadata, waveform binary BLOB decoding, and respiratory events for OSCAR databases."""

import sqlite3
import struct
import zlib
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Channel:
    """Represents an OSCAR channel definition (signal or event flag)."""

    id: int
    profile_id: int
    channel_id: int
    channel_code: str
    label: str
    fullname: Optional[str] = None
    default_color: Optional[str] = None
    type: int = 0


@dataclass(frozen=True)
class WaveformRecord:
    """Decompressed time-series waveform signal."""

    event_list_id: int
    session_id: int
    channel_id: int
    channel_code: str
    sample_rate: float
    gain: float
    offset: float
    first_time_ms: int
    last_time_ms: int
    count: int
    timestamps_ms: list[int]
    values: list[float]


@dataclass(frozen=True)
class RespiratoryEvent:
    """Discrete apnea, hypopnea, or respiratory arousal occurrence."""

    id: int
    session_id: int
    profile_id: int
    channel_id: int
    channel_code: str
    start_time_ms: int
    duration: int  # in seconds
    event_type: int
    label: Optional[str] = None
    fullname: Optional[str] = None


def qcompress_decode(payload: bytes) -> bytes:
    """Decodes a Qt qCompress binary payload.

    A qCompress payload consists of a 4-byte big-endian uint32 denoting
    the uncompressed byte length, followed by standard zlib compressed data.

    @param payload: Raw bytes read from database event_data.data_blob.
    @return: Decompressed raw byte stream.
    @raise ValueError: When the payload is truncated or length header does not match.
    """
    if len(payload) < 4:
        raise ValueError("qCompress payload too short: minimum 4 bytes required for length header")
    expected_len = struct.unpack(">I", payload[:4])[0]
    decompressed = zlib.decompress(payload[4:])
    if len(decompressed) != expected_len:
        raise ValueError(
            f"qCompress decompression length mismatch: header specifies {expected_len} bytes, "
            f"decompressed stream produced {len(decompressed)} bytes"
        )
    return decompressed


def list_channels(conn: sqlite3.Connection, profile_id: int) -> list[Channel]:
    """Retrieves all channel configurations registered for a profile.

    @param conn: Active database connection.
    @param profile_id: Database profile ID.
    @return: List of Channel instances.
    """
    rows = conn.execute(
        """
        SELECT id, profile_id, channel_id, channel_code, label, fullname, default_color, type
        FROM channels
        WHERE profile_id = ?
        ORDER BY channel_id ASC
        """,
        (profile_id,),
    ).fetchall()

    return [
        Channel(
            id=row["id"],
            profile_id=row["profile_id"],
            channel_id=row["channel_id"],
            channel_code=row["channel_code"],
            label=row["label"],
            fullname=row["fullname"],
            default_color=row["default_color"],
            type=int(row["type"] or 0),
        )
        for row in rows
    ]


def get_channel_by_code(
    conn: sqlite3.Connection, profile_id: int, channel_code: str
) -> Optional[Channel]:
    """Finds a channel definition by profile and symbolic channel code.

    @param conn: Active database connection.
    @param profile_id: Database profile ID.
    @param channel_code: Channel identifier (e.g., 'FlowRate', 'Pressure', 'Leak').
    @return: Channel instance if found, None otherwise.
    """
    row = conn.execute(
        """
        SELECT id, profile_id, channel_id, channel_code, label, fullname, default_color, type
        FROM channels
        WHERE profile_id = ? AND channel_code = ?
        """,
        (profile_id, channel_code),
    ).fetchone()

    if row is None:
        return None

    return Channel(
        id=row["id"],
        profile_id=row["profile_id"],
        channel_id=row["channel_id"],
        channel_code=row["channel_code"],
        label=row["label"],
        fullname=row["fullname"],
        default_color=row["default_color"],
        type=int(row["type"] or 0),
    )


def get_waveform(
    conn: sqlite3.Connection, session_id: int, channel_code: str
) -> Optional[WaveformRecord]:
    """Extracts and decodes the continuous waveform signal for a given session and channel.

    @param conn: Active database connection.
    @param session_id: Database session ID.
    @param channel_code: Symbolic channel code (e.g., 'FlowRate', 'Pressure').
    @return: WaveformRecord with timestamps (ms) and scaled float values, or None if not found.
    """
    row = conn.execute(
        """
        SELECT el.id, el.session_id, el.channel_id, el.event_type, el.gain, el.offset,
               el.sample_rate, el.first_time, el.last_time, el.count,
               c.channel_code, ed.data_blob
        FROM event_lists el
        JOIN channels c ON el.channel_id = c.channel_id AND el.profile_id = c.profile_id
        JOIN event_data ed ON el.id = ed.event_list_id
        WHERE el.session_id = ? AND c.channel_code = ?
        ORDER BY el.first_time ASC
        LIMIT 1
        """,
        (session_id, channel_code),
    ).fetchone()

    if row is None:
        return None

    raw_bytes = qcompress_decode(row["data_blob"])
    gain = float(row["gain"] or 1.0)
    offset = float(row["offset"] or 0.0)
    sample_rate = float(row["sample_rate"] or 25.0)
    first_time = int(row["first_time"])
    last_time = int(row["last_time"])

    # int16 little-endian samples
    num_samples = len(raw_bytes) // 2
    raw_integers = struct.unpack(f"<{num_samples}h", raw_bytes[: num_samples * 2])

    interval_ms = 1000.0 / sample_rate if sample_rate > 0 else 40.0
    timestamps = [first_time + int(i * interval_ms) for i in range(num_samples)]
    scaled_values = [raw * gain + offset for raw in raw_integers]

    return WaveformRecord(
        event_list_id=row["id"],
        session_id=row["session_id"],
        channel_id=row["channel_id"],
        channel_code=row["channel_code"],
        sample_rate=sample_rate,
        gain=gain,
        offset=offset,
        first_time_ms=first_time,
        last_time_ms=last_time,
        count=num_samples,
        timestamps_ms=timestamps,
        values=scaled_values,
    )


def list_respiratory_events(
    conn: sqlite3.Connection, session_id: int
) -> list[RespiratoryEvent]:
    """Retrieves all discrete apnea/hypopnea events cataloged for a session.

    @param conn: Active database connection.
    @param session_id: Database session ID.
    @return: List of RespiratoryEvent instances ordered chronologically.
    """
    rows = conn.execute(
        """
        SELECT re.id, re.session_id, re.profile_id, re.channel_id, re.start_time,
               re.duration, re.event_type, c.channel_code, c.label, c.fullname
        FROM respiratory_events re
        LEFT JOIN channels c ON re.channel_id = c.channel_id AND re.profile_id = c.profile_id
        WHERE re.session_id = ?
        ORDER BY re.start_time ASC
        """,
        (session_id,),
    ).fetchall()

    return [
        RespiratoryEvent(
            id=row["id"],
            session_id=row["session_id"],
            profile_id=row["profile_id"],
            channel_id=row["channel_id"],
            channel_code=row["channel_code"] or f"Channel_{row['channel_id']}",
            start_time_ms=row["start_time"],
            duration=row["duration"],
            event_type=row["event_type"],
            label=row["label"],
            fullname=row["fullname"],
        )
        for row in rows
    ]
