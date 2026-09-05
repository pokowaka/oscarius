"""ResMed CPAP SD card reader and SQLite database importer.

Discovers, parses, and populates OSCAR databases directly from ResMed AirSense/AirCurve
data directories (containing Identification.json/.tgt, STR.edf, and DATALOG/*_{BRP,PLD,EVE}.edf).
"""

import json
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union
import numpy as np

from oscarius.db.connection import open_database
from oscarius.db.schema import create_database_schema, init_default_channels
from oscarius.db.summaries import calculate_oscar_day, list_sessions_for_day
from oscarius.db.waveforms import encode_qcompress
from oscarius.importers.edf import read_edf, EDFFile


@dataclass(frozen=True)
class ImportResult:
    """Summary metrics of an executed SD card import operation."""

    sessions_imported: int
    days_updated: int
    brand: str
    model: str
    serial_number: str


# Mapping of signal name substrings in PLD to OSCAR channel IDs
PLD_CHANNEL_MAPPING = {
    "mask": 0x1001,       # Mask Pressure (Pressure)
    "press": 0x1001,      # Pressure fallback
    "leak": 0x1002,       # Leak Rate
    "epap": 0x1004,       # Expiratory Pressure
    "exp.press": 0x1004,  # Expiratory Pressure
    "tid": 0x1005,        # Tidal Volume
    "min.vent": 0x1006,   # Minute Ventilation
    "resp.rate": 0x1007,  # Respiratory Rate
    "snore": 0x1008,      # Snore
}


def _find_child_ci(parent: Path, name: str) -> Optional[Path]:
    """Finds a child file or directory matching name case-insensitively."""
    target = name.lower()
    if not parent.is_dir():
        return None
    for child in parent.iterdir():
        if child.name.lower() == target:
            return child
    return None


def detect_resmed_card(path: Union[Path, str]) -> bool:
    """Verifies whether a given path is a valid ResMed CPAP SD card.

    A valid card must contain a DATALOG directory and an STR.edf summary file.

    @param path: Filesystem directory path.
    @return: True if ResMed directory structure is confirmed.
    """
    card_dir = Path(path)
    if not card_dir.is_dir():
        return False

    datalog_dir = _find_child_ci(card_dir, "DATALOG")
    str_file = _find_child_ci(card_dir, "STR.edf")

    return datalog_dir is not None and str_file is not None


def read_resmed_identification(path: Union[Path, str]) -> dict[str, str]:
    """Extracts device serial number and product model from card identification files.

    Checks Identification.json (AirSense 11) and Identification.tgt (AirSense 10/S9).

    @param path: ResMed SD card root directory.
    @return: Dict with keys 'brand', 'model', 'serial_number'.
    """
    card_dir = Path(path)
    result = {
        "brand": "ResMed",
        "model": "AirSense",
        "serial_number": "Unknown",
    }

    # AirSense 11 format
    json_path = _find_child_ci(card_dir, "Identification.json")
    if json_path and json_path.is_file():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            product = (
                data.get("FlowGenerator", {})
                .get("IdentificationProfiles", {})
                .get("Product", {})
            )
            serial = product.get("SerialNumber")
            family = product.get("FamilyName", "AirSense 11")
            title = product.get("ProductTitle", "")
            if serial:
                result["serial_number"] = str(serial).strip()
            result["model"] = f"{family} {title}".strip()
            return result
        except Exception:
            pass

    # AirSense 10 / S9 format (.tgt)
    tgt_path = _find_child_ci(card_dir, "Identification.tgt")
    if tgt_path and tgt_path.is_file():
        try:
            with open(tgt_path, "r", encoding="latin1") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#FGT_SER"):
                        parts = line.split(maxsplit=1)
                        if len(parts) > 1:
                            result["serial_number"] = parts[1].strip()
                    elif line.startswith("#P_NAME"):
                        parts = line.split(maxsplit=1)
                        if len(parts) > 1:
                            result["model"] = parts[1].strip()
            return result
        except Exception:
            pass

    return result


def _resolve_annotation_channel(description: str) -> tuple[int, int]:
    """Maps an EDF+ annotation description string to an OSCAR channel_id and event_type."""
    desc = description.lower()
    if "central" in desc or "clear airway" in desc:
        return 0x2002, 2  # CA
    if "hypopnea" in desc:
        return 0x2003, 3  # H
    if "cheyne" in desc or "csr" in desc or "pb" in desc:
        return 0x2004, 4  # CSR
    if "flow limitation" in desc or "fl" in desc:
        return 0x2005, 5  # FL
    # Default to Obstructive Apnea
    return 0x2001, 1      # OA


def import_resmed_sd_card(
    card_path: Union[Path, str],
    db_path: Union[Path, str],
    username: str = "Default",
) -> ImportResult:
    """Ingests a ResMed CPAP SD card and populates the OSCAR SQLite database.

    Creates the database schema if needed, provisions the user profile, inserts
    device machine metadata, writes sessions with compressed waveform BLOBs,
    catalogs respiratory events, and calculates daily clinical summaries.

    @param card_path: Filesystem path to the root of the ResMed SD card.
    @param db_path: Filesystem path to the target SQLite database.
    @param username: User profile name.
    @return: ImportResult with import statistics.
    """
    card_dir = Path(card_path)
    if not card_dir.is_dir():
        raise FileNotFoundError(f"ResMed SD card directory not found: {card_dir}")

    db_file = Path(db_path)
    is_new_db = not db_file.exists() or db_file.stat().st_size == 0

    conn = open_database(db_file, read_only=False, create=True)
    if is_new_db:
        create_database_schema(conn, version=18)

    # 1. Resolve Profile
    row = conn.execute(
        "SELECT id FROM profiles WHERE username = ?", (username,)
    ).fetchone()
    if row:
        profile_id = row["id"]
    else:
        cursor = conn.execute(
            "INSERT INTO profiles (username, data_folder, status) VALUES (?, ?, 'active')",
            (username, str(card_dir)),
        )
        profile_id = cursor.lastrowid
        init_default_channels(conn, profile_id)

    # 2. Resolve Machine
    ident = read_resmed_identification(card_dir)
    mach_row = conn.execute(
        "SELECT id FROM machines WHERE profile_id = ? AND serial_number = ?",
        (profile_id, ident["serial_number"]),
    ).fetchone()
    if mach_row:
        machine_db_id = mach_row["id"]
    else:
        cursor = conn.execute(
            """
            INSERT INTO machines (
                profile_id, machine_id, loader_name, machine_type,
                brand, model, serial_number
            ) VALUES (?, 1001, 'ResMed', 0, ?, ?, ?)
            """,
            (profile_id, ident["brand"], ident["model"], ident["serial_number"]),
        )
        machine_db_id = cursor.lastrowid

    # 3. Discover Session File Groups in DATALOG
    datalog_dir = _find_child_ci(card_dir, "DATALOG")
    if not datalog_dir:
        conn.close()
        return ImportResult(0, 0, ident["brand"], ident["model"], ident["serial_number"])

    session_files: dict[str, dict[str, Path]] = defaultdict(dict)
    # Search all files in DATALOG recursively (some cards use YYYYMMDD subfolders)
    for p in datalog_dir.rglob("*.edf*"):
        name = p.name
        match = re.match(r"^(\d{8}_\d{6})_([A-Z]{3})\.edf(?:\.gz)?$", name, re.IGNORECASE)
        if match:
            prefix, kind = match.group(1), match.group(2).upper()
            session_files[prefix][kind] = p

    sessions_imported = 0
    impacted_days = set()

    # 4. Import each session group
    for prefix, kinds in sorted(session_files.items()):
        brp_path = kinds.get("BRP")
        if not brp_path:
            continue

        try:
            brp_edf = read_edf(brp_path)
        except Exception:
            continue

        session_start_ms = int(brp_edf.start_datetime.timestamp() * 1000)
        session_duration_ms = int(brp_edf.num_records * brp_edf.record_duration_sec * 1000)
        session_end_ms = session_start_ms + session_duration_ms

        # Check for existing session
        sess_check = conn.execute(
            "SELECT id FROM sessions WHERE machine_id = ? AND start_time = ?",
            (machine_db_id, session_start_ms),
        ).fetchone()

        if sess_check:
            continue

        cursor = conn.execute(
            """
            INSERT INTO sessions (machine_id, start_time, end_time, enabled, summary_only)
            VALUES (?, ?, ?, 1, 0)
            """,
            (machine_db_id, session_start_ms, session_end_ms),
        )
        session_id = cursor.lastrowid
        sessions_imported += 1
        impacted_days.add(calculate_oscar_day(session_start_ms))

        # Store Flow Rate from BRP
        try:
            flow_idx = brp_edf.get_signal_index("flow")
            flow_sig = brp_edf.signals[flow_idx]
            raw_flow_data = brp_edf._signal_raw_data[flow_idx]
            raw_bytes = raw_flow_data.tobytes()
            compressed_blob = encode_qcompress(raw_bytes)

            sample_rate = flow_sig.samples_per_record / brp_edf.record_duration_sec
            cursor = conn.execute(
                """
                INSERT INTO event_lists (
                    session_id, profile_id, channel_id, event_type, gain, offset,
                    sample_rate, first_time, last_time, count
                ) VALUES (?, ?, 0x1000, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    profile_id,
                    flow_sig.gain,
                    flow_sig.offset,
                    sample_rate,
                    session_start_ms,
                    session_end_ms,
                    len(raw_flow_data),
                ),
            )
            el_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO event_data (event_list_id, data_blob, checksum) VALUES (?, ?, 0)",
                (el_id, compressed_blob),
            )
        except Exception:
            pass

        # Store signals from PLD (Pressure, Leak, etc.)
        pld_path = kinds.get("PLD")
        if pld_path:
            try:
                pld_edf = read_edf(pld_path)
                for s_idx, sig in enumerate(pld_edf.signals):
                    sig_label_lower = sig.label.lower()
                    matched_channel_id = None
                    for key, ch_id in PLD_CHANNEL_MAPPING.items():
                        if key in sig_label_lower:
                            matched_channel_id = ch_id
                            break

                    if matched_channel_id:
                        raw_data = pld_edf._signal_raw_data[s_idx]
                        compressed = encode_qcompress(raw_data.tobytes())
                        sig_rate = sig.samples_per_record / pld_edf.record_duration_sec

                        cursor = conn.execute(
                            """
                            INSERT INTO event_lists (
                                session_id, profile_id, channel_id, event_type, gain, offset,
                                sample_rate, first_time, last_time, count
                            ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                session_id,
                                profile_id,
                                matched_channel_id,
                                sig.gain,
                                sig.offset,
                                sig_rate,
                                session_start_ms,
                                session_end_ms,
                                len(raw_data),
                            ),
                        )
                        conn.execute(
                            "INSERT INTO event_data (event_list_id, data_blob, checksum) VALUES (?, ?, 0)",
                            (cursor.lastrowid, compressed),
                        )
            except Exception:
                pass

        # Store annotations from EVE (Apneas, Hypopneas)
        eve_path = kinds.get("EVE")
        if eve_path:
            try:
                eve_edf = read_edf(eve_path)
                for annot in eve_edf.annotations:
                    ch_id, ev_type = _resolve_annotation_channel(annot.description)
                    ev_start_ms = session_start_ms + int(annot.onset_sec * 1000)
                    ev_dur_sec = max(1, int(round(annot.duration_sec)))

                    conn.execute(
                        """
                        INSERT INTO respiratory_events (
                            session_id, profile_id, channel_id, start_time, duration, event_type
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (session_id, profile_id, ch_id, ev_start_ms, ev_dur_sec, ev_type),
                    )
            except Exception:
                pass

    # 5. Compute & Update daily_summaries for impacted days
    days_updated = 0
    for day in impacted_days:
        sessions = list_sessions_for_day(conn, profile_id, day)
        if not sessions:
            continue

        total_hours = sum(s.duration_hours for s in sessions)
        session_ids = [s.id for s in sessions]

        placeholders = ",".join("?" * len(session_ids))
        event_counts = conn.execute(
            f"""
            SELECT channel_id, COUNT(*) as cnt
            FROM respiratory_events
            WHERE session_id IN ({placeholders})
            GROUP BY channel_id
            """,
            session_ids,
        ).fetchall()

        count_map = {row["channel_id"]: row["cnt"] for row in event_counts}
        oa_count = count_map.get(0x2001, 0)
        ca_count = count_map.get(0x2002, 0)
        h_count = count_map.get(0x2003, 0)
        all_apneas = oa_count + ca_count + h_count

        ahi = round(all_apneas / total_hours, 2) if total_hours > 0 else 0.0
        oahi = round(oa_count / total_hours, 2) if total_hours > 0 else 0.0
        cahi = round(ca_count / total_hours, 2) if total_hours > 0 else 0.0
        compliance = 1 if total_hours >= 4.0 else 0

        conn.execute(
            """
            INSERT OR REPLACE INTO daily_summaries (
                profile_id, date, total_hours, ahi, oahi, cahi,
                obstructive_hypopnea_count, central_hypopnea_count, all_apnea_count,
                compliance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                day,
                round(total_hours, 2),
                ahi,
                oahi,
                cahi,
                oa_count,
                ca_count,
                all_apneas,
                compliance,
            ),
        )
        days_updated += 1

    conn.commit()
    conn.close()

    return ImportResult(
        sessions_imported=sessions_imported,
        days_updated=days_updated,
        brand=ident["brand"],
        model=ident["model"],
        serial_number=ident["serial_number"],
    )
