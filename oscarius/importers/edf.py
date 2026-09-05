"""Pure-Python parser for European Data Format (EDF and EDF+) medical time series.

Reads standard .edf and gzip-compressed .edf.gz files without external C dependencies,
extracting signal samples, calibration coefficients, and timestamped clinical annotations.
"""

import gzip
import io
import re
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
import numpy as np


@dataclass(frozen=True)
class EDFSignalHeader:
    """Header metadata and calibration factors for an individual EDF signal channel."""

    label: str
    transducer: str
    dimension: str
    phys_min: float
    phys_max: float
    dig_min: int
    dig_max: int
    prefilter: str
    samples_per_record: int
    gain: float
    offset: float


@dataclass(frozen=True)
class EDFAnnotation:
    """Timestamped event annotation embedded within an EDF+ record."""

    onset_sec: float
    duration_sec: float
    description: str


def parse_edf_annotations(tal_bytes: bytes) -> list[EDFAnnotation]:
    """Parses Time-stamped Annotation Lists (TAL) from an EDF+ annotation channel.

    EDF+ TAL format per record:
    +<onset>[\x15<duration>]\x14<description>\x14...[\x00]
    """
    annotations = []
    # TAL strings are Latin-1 / ASCII separated by \x14 (DC4) and \x15 (NAK)
    text = tal_bytes.decode("latin1", errors="ignore")

    # Split by null bytes that separate TAL blocks
    blocks = text.split("\x00")
    for block in blocks:
        if not block or not block.startswith("+"):
            continue

        parts = block.split("\x14")
        if len(parts) < 2:
            continue

        time_part = parts[0]
        # Check if duration is specified via \x15
        if "\x15" in time_part:
            onset_str, duration_str = time_part[1:].split("\x15", 1)
        else:
            onset_str = time_part[1:]
            duration_str = "0.0"

        try:
            onset = float(onset_str)
            duration = float(duration_str) if duration_str else 0.0
        except ValueError:
            continue

        # Descriptions follow in subsequent \x14-separated segments
        for desc in parts[1:]:
            desc = desc.strip()
            if desc:
                annotations.append(
                    EDFAnnotation(
                        onset_sec=onset,
                        duration_sec=duration,
                        description=desc,
                    )
                )

    return annotations


class EDFFile:
    """In-memory representation of an open European Data Format file."""

    def __init__(
        self,
        version: str,
        patient_id: str,
        recording_id: str,
        start_date_str: str,
        start_time_str: str,
        start_datetime: datetime,
        num_records: int,
        record_duration_sec: float,
        signals: list[EDFSignalHeader],
        signal_raw_data: list[np.ndarray],
        annotations: list[EDFAnnotation],
    ) -> None:
        self.version = version
        self.patient_id = patient_id
        self.recording_id = recording_id
        self.start_date_str = start_date_str
        self.start_time_str = start_time_str
        self.start_datetime = start_datetime
        self.num_records = num_records
        self.record_duration_sec = record_duration_sec
        self.signals = signals
        self._signal_raw_data = signal_raw_data
        self.annotations = annotations

    def get_signal_index(self, label_or_idx: Union[int, str]) -> int:
        """Resolves a signal index by numeric index or case-insensitive label substring."""
        if isinstance(label_or_idx, int):
            if 0 <= label_or_idx < len(self.signals):
                return label_or_idx
            raise IndexError(f"Signal index {label_or_idx} out of range (0-{len(self.signals)-1})")

        query = label_or_idx.strip().lower()
        for i, sig in enumerate(self.signals):
            if sig.label.strip().lower() == query:
                return i
        # Fallback: substring search
        for i, sig in enumerate(self.signals):
            if query in sig.label.strip().lower():
                return i
        raise KeyError(f"No signal found matching label '{label_or_idx}'")

    def get_signal_samples(
        self, signal_name_or_idx: Union[int, str], raw: bool = False
    ) -> tuple[np.ndarray, np.ndarray]:
        """Extracts timestamps (in ms relative to epoch) and physical sample values.

        @param signal_name_or_idx: Signal index or label name.
        @param raw: If true, returns unscaled raw integer data.
        @return: Tuple of (timestamps_ms_array, values_array).
        """
        idx = self.get_signal_index(signal_name_or_idx)
        sig = self.signals[idx]
        raw_vals = self._signal_raw_data[idx]

        start_ms = int(self.start_datetime.timestamp() * 1000)
        total_samples = len(raw_vals)

        # Sample rate calculation
        samples_per_sec = sig.samples_per_record / self.record_duration_sec
        interval_ms = 1000.0 / samples_per_sec if samples_per_sec > 0 else 40.0

        indices = np.arange(total_samples)
        timestamps = (start_ms + indices * interval_ms).astype(np.int64)

        if raw:
            return timestamps, raw_vals

        physical_values = raw_vals.astype(np.float64) * sig.gain + sig.offset
        return timestamps, physical_values


def read_edf(source: Union[Path, str, bytes]) -> EDFFile:
    """Parses an EDF or EDF+ file from a filesystem path or in-memory byte buffer.

    @param source: Path to .edf / .edf.gz file, or raw bytes.
    @return: Parsed EDFFile instance.
    """
    if isinstance(source, (Path, str)):
        path_obj = Path(source)
        if not path_obj.is_file():
            raise FileNotFoundError(f"EDF file not found: {path_obj}")
        if path_obj.suffix.lower() == ".gz":
            with gzip.open(path_obj, "rb") as gz_f:
                raw_bytes = gz_f.read()
        else:
            with open(path_obj, "rb") as f:
                raw_bytes = f.read()
    else:
        raw_bytes = source
        # Detect gzip magic number 0x1f8b
        if len(raw_bytes) >= 2 and raw_bytes[:2] == b"\x1f\x8b":
            raw_bytes = gzip.decompress(raw_bytes)

    if len(raw_bytes) < 256:
        raise ValueError("File too short for EDF header (minimum 256 bytes required)")

    # Parse 256-byte main header
    version = raw_bytes[0:8].decode("ascii", errors="ignore").strip()
    patient_id = raw_bytes[8:88].decode("ascii", errors="ignore").strip()
    recording_id = raw_bytes[88:168].decode("ascii", errors="ignore").strip()
    start_date_str = raw_bytes[168:176].decode("ascii", errors="ignore").strip()
    start_time_str = raw_bytes[176:184].decode("ascii", errors="ignore").strip()
    header_bytes_len = int(raw_bytes[184:192].decode("ascii", errors="ignore").strip() or 256)
    reserved_44 = raw_bytes[192:236].decode("ascii", errors="ignore").strip()
    num_records_str = raw_bytes[236:244].decode("ascii", errors="ignore").strip()
    num_records = int(num_records_str) if num_records_str and num_records_str != "-1" else 0
    record_dur_str = raw_bytes[244:252].decode("ascii", errors="ignore").strip()
    record_duration = float(record_dur_str) if record_dur_str else 1.0
    num_signals_str = raw_bytes[252:256].decode("ascii", errors="ignore").strip()
    num_signals = int(num_signals_str) if num_signals_str else 0

    # Parse start timestamp
    try:
        day, month, year = [int(p) for p in re.split(r"[.\-/]", start_date_str)[:3]]
        # 2-digit year conversion per EDF spec: yy >= 80 -> 19yy, else 20yy
        full_year = 1900 + year if year >= 80 else 2000 + year
        hour, minute, sec = [int(p) for p in re.split(r"[.:]", start_time_str)[:3]]
        start_datetime = datetime(full_year, month, day, hour, minute, sec, tzinfo=timezone.utc)
    except Exception:
        start_datetime = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Parse signal headers
    ns = num_signals
    expected_header_size = 256 + ns * 256
    if len(raw_bytes) < expected_header_size:
        raise ValueError(f"EDF file truncated: expected {expected_header_size} bytes header, found {len(raw_bytes)}")

    offset = 256
    sig_labels = [raw_bytes[offset + i * 16 : offset + (i + 1) * 16].decode("ascii", errors="ignore").strip() for i in range(ns)]
    offset += ns * 16
    sig_transducers = [raw_bytes[offset + i * 80 : offset + (i + 1) * 80].decode("ascii", errors="ignore").strip() for i in range(ns)]
    offset += ns * 80
    sig_dimensions = [raw_bytes[offset + i * 8 : offset + (i + 1) * 8].decode("ascii", errors="ignore").strip() for i in range(ns)]
    offset += ns * 8
    sig_phys_min = [float(raw_bytes[offset + i * 8 : offset + (i + 1) * 8].decode("ascii", errors="ignore").strip() or 0.0) for i in range(ns)]
    offset += ns * 8
    sig_phys_max = [float(raw_bytes[offset + i * 8 : offset + (i + 1) * 8].decode("ascii", errors="ignore").strip() or 1.0) for i in range(ns)]
    offset += ns * 8
    sig_dig_min = [int(raw_bytes[offset + i * 8 : offset + (i + 1) * 8].decode("ascii", errors="ignore").strip() or 0) for i in range(ns)]
    offset += ns * 8
    sig_dig_max = [int(raw_bytes[offset + i * 8 : offset + (i + 1) * 8].decode("ascii", errors="ignore").strip() or 1) for i in range(ns)]
    offset += ns * 8
    sig_prefilters = [raw_bytes[offset + i * 80 : offset + (i + 1) * 80].decode("ascii", errors="ignore").strip() for i in range(ns)]
    offset += ns * 80
    sig_samples_per_rec = [int(raw_bytes[offset + i * 8 : offset + (i + 1) * 8].decode("ascii", errors="ignore").strip() or 0) for i in range(ns)]
    offset += ns * 8
    # Reserved bytes ns * 32
    offset += ns * 32

    signal_headers = []
    for i in range(ns):
        d_min, d_max = sig_dig_min[i], sig_dig_max[i]
        p_min, p_max = sig_phys_min[i], sig_phys_max[i]
        gain = (p_max - p_min) / (d_max - d_min) if d_max != d_min else 1.0
        cal_offset = p_min - d_min * gain
        signal_headers.append(
            EDFSignalHeader(
                label=sig_labels[i],
                transducer=sig_transducers[i],
                dimension=sig_dimensions[i],
                phys_min=p_min,
                phys_max=p_max,
                dig_min=d_min,
                dig_max=d_max,
                prefilter=sig_prefilters[i],
                samples_per_record=sig_samples_per_rec[i],
                gain=gain,
                offset=cal_offset,
            )
        )

    # Read data records
    record_byte_size = sum(s * 2 for s in sig_samples_per_rec)
    data_payload = raw_bytes[expected_header_size:]

    if record_byte_size > 0:
        actual_records = len(data_payload) // record_byte_size
        if num_records == 0:
            num_records = actual_records
    else:
        actual_records = 0

    signal_raw_arrays = [
        np.zeros(actual_records * s, dtype=np.int16) for s in sig_samples_per_rec
    ]
    all_annotations: list[EDFAnnotation] = []

    data_offset = 0
    for r in range(actual_records):
        for s_idx, s_count in enumerate(sig_samples_per_rec):
            chunk_len = s_count * 2
            chunk = data_payload[data_offset : data_offset + chunk_len]
            data_offset += chunk_len

            if "annotation" in sig_labels[s_idx].lower():
                annots = parse_edf_annotations(chunk)
                all_annotations.extend(annots)
            else:
                unpacked = struct.unpack(f"<{s_count}h", chunk)
                start_i = r * s_count
                signal_raw_arrays[s_idx][start_i : start_i + s_count] = unpacked

    return EDFFile(
        version=version,
        patient_id=patient_id,
        recording_id=recording_id,
        start_date_str=start_date_str,
        start_time_str=start_time_str,
        start_datetime=start_datetime,
        num_records=actual_records,
        record_duration_sec=record_duration,
        signals=signal_headers,
        signal_raw_data=signal_raw_arrays,
        annotations=all_annotations,
    )
