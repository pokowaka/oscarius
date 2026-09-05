"""Tests for the pure-Python European Data Format (EDF / EDF+) parser."""

import struct
from datetime import datetime, timezone
import pytest

from oscarius.importers.edf import (
    read_edf,
    EDFFile,
    EDFSignalHeader,
    EDFAnnotation,
    parse_edf_annotations,
)


def create_synthetic_edf_bytes(
    label: str = "Flow",
    num_records: int = 2,
    record_duration: float = 1.0,
    samples_per_record: int = 5,
    sample_values: list[int] | None = None,
    annotations_text: str = "",
) -> bytes:
    """Helper to synthesize valid binary EDF bytes."""
    if sample_values is None:
        sample_values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    has_annot = bool(annotations_text)
    num_signals = 2 if has_annot else 1

    # Header 256 bytes
    version = b"0       "
    patient = b"Test Patient".ljust(80)
    recording = b"Test Recording".ljust(80)
    start_date = b"04.09.26"
    start_time = b"23.00.00"
    header_bytes_val = 256 + num_signals * 256
    header_bytes = str(header_bytes_val).encode("ascii").ljust(8)
    reserved = b"".ljust(44)
    records_str = str(num_records).encode("ascii").ljust(8)
    duration_str = str(record_duration).encode("ascii").ljust(8)
    signals_str = str(num_signals).encode("ascii").ljust(4)

    header = (
        version
        + patient
        + recording
        + start_date
        + start_time
        + header_bytes
        + reserved
        + records_str
        + duration_str
        + signals_str
    )
    assert len(header) == 256

    # Signal 1: The data signal
    sig_labels = label.encode("ascii").ljust(16)
    sig_transducers = b"None".ljust(80)
    sig_dimensions = b"L/min".ljust(8)
    sig_phys_min = b"-100.0".ljust(8)
    sig_phys_max = b"100.0".ljust(8)
    sig_dig_min = b"-1000".ljust(8)
    sig_dig_max = b"1000".ljust(8)
    sig_prefilter = b"".ljust(80)
    sig_samples_rec = str(samples_per_record).encode("ascii").ljust(8)
    sig_reserved = b"".ljust(32)

    if has_annot:
        sig_labels += b"EDF Annotations".ljust(16)
        sig_transducers += b"".ljust(80)
        sig_dimensions += b"".ljust(8)
        sig_phys_min += b"-1".ljust(8)
        sig_phys_max += b"1".ljust(8)
        sig_dig_min += b"-32768".ljust(8)
        sig_dig_max += b"32767".ljust(8)
        sig_prefilter += b"".ljust(80)
        annot_bytes_per_rec = max(len(annotations_text), 20)
        annot_samples_per_rec = annot_bytes_per_rec // 2
        sig_samples_rec += str(annot_samples_per_rec).encode("ascii").ljust(8)
        sig_reserved += b"".ljust(32)

    signal_headers = (
        sig_labels
        + sig_transducers
        + sig_dimensions
        + sig_phys_min
        + sig_phys_max
        + sig_dig_min
        + sig_dig_max
        + sig_prefilter
        + sig_samples_rec
        + sig_reserved
    )

    data_records = bytearray()
    val_idx = 0
    for r in range(num_records):
        for s in range(samples_per_record):
            val = sample_values[val_idx % len(sample_values)]
            val_idx += 1
            data_records.extend(struct.pack("<h", val))
        if has_annot:
            # Annotations block for this record
            raw_annot = annotations_text.encode("latin1") if r == 0 else b"+0\x14\x00"
            raw_annot = raw_annot.ljust(annot_samples_per_rec * 2, b"\x00")
            data_records.extend(raw_annot)

    return header + signal_headers + bytes(data_records)


def test_read_edf_header_and_signals():
    raw_data = create_synthetic_edf_bytes(
        label="Flow",
        num_records=2,
        record_duration=1.0,
        samples_per_record=5,
        sample_values=[0, 100, 200, 300, 400, 500, 600, 700, 800, 900],
    )
    edf = read_edf(raw_data)
    assert isinstance(edf, EDFFile)
    assert edf.num_records == 2
    assert edf.record_duration_sec == 1.0
    assert len(edf.signals) == 1

    sig = edf.signals[0]
    assert sig.label == "Flow"
    assert sig.phys_min == -100.0
    assert sig.phys_max == 100.0
    assert sig.dig_min == -1000
    assert sig.dig_max == 1000
    # Gain: (100 - (-100)) / (1000 - (-1000)) = 200 / 2000 = 0.1
    assert sig.gain == pytest.approx(0.1)

    timestamps, values = edf.get_signal_samples(0)
    assert len(values) == 10
    # First sample digital val is 0 -> 0 * 0.1 + 0 = 0.0
    assert values[0] == pytest.approx(0.0)
    # Second sample is 100 -> 10.0
    assert values[1] == pytest.approx(10.0)
    # Fifth sample is 400 -> 40.0
    assert values[4] == pytest.approx(40.0)


def test_parse_edf_annotations():
    # Standard EDF+ TAL: +onset\x15duration\x14annotation\x14\x00
    tal_data = b"+120.5\x1518.0\x14Obstructive Apnea\x14\x00+250.0\x1512.5\x14Central Apnea\x14\x00"
    annots = parse_edf_annotations(tal_data)
    assert len(annots) == 2
    assert annots[0].onset_sec == 120.5
    assert annots[0].duration_sec == 18.0
    assert annots[0].description == "Obstructive Apnea"
    assert annots[1].onset_sec == 250.0
    assert annots[1].duration_sec == 12.5
    assert annots[1].description == "Central Apnea"
