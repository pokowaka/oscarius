# Oscarius (OSCAR on the Web)

A modern web-based sleep therapy and CPAP data analysis platform with AI interpretation capabilities.

## Phase 1: Backend & Read-Only API

Phase 1 provides the core Python backend engine for reading OSCAR 2.0 SQLite databases (`oscar.db`), decoding compressed waveform signals, downsampling high-frequency data, and exposing REST endpoints for web frontends and AI agents.

### Features
- **OSCAR 2.0 SQLite Connection**: Verified read-only access supporting schemas v12 through v18.
- **Domain Repositories**:
  - Profiles and registered machines/devices.
  - Noon-to-noon "OSCAR Day" sleep window calculation.
  - Pre-computed `daily_summaries` (AHI, OAHI, CAHI, leak percentiles, pressure percentiles, compliance).
  - Therapy sessions and discrete respiratory event flags (OA, CA, Hypopnea).
  - Channel definitions and metadata.
- **Waveform Decompression**: Native Qt `qCompress` / zlib BLOB decoding for 16-bit time-series signals (`event_data`).
- **LTTB Downsampling**: Largest-Triangle-Three-Buckets decimation algorithm to downsample 700k+ points (e.g. 25 Hz Flow Rate) down to screen resolution (e.g. 1,000–2,000 points) in milliseconds without aliasing.
- **FastAPI REST API**: Endpoints for profiles, days, daily summaries, events, and windowed/downsampled waveforms.
- **Pure-Python EDF / EDF+ Parser**: Robust binary reader for European Data Format files and TAL annotations without external C dependencies.
- **ResMed SD Card Importer**: Direct ingestion of ResMed AirSense 10/11 and S9 SD cards into OSCAR Schema v18 SQLite databases.

### Importing ResMed SD Card Data

Create or update an OSCAR database directly from your ResMed SD card:

```bash
# Import SD card directory into oscar.db
python -m oscarius import /path/to/sdcard --db oscar.db --profile "Default"
```

### Running the Server

```bash
# Set path to your OSCAR database (optional, defaults to ~/Documents/OSCAR20_Data/oscar.db)
export OSCARIUS_DB_PATH="/path/to/oscar.db"

# Start the server
python -m oscarius serve --port 8000 --reload
```

Interactive OpenAPI docs will be available at `http://127.0.0.1:8000/docs`.

### Running Tests

```bash
python -m pytest
```
