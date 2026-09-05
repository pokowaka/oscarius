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

## Phase 2: Web Frontend & Waveform Visualizer

- **Clinical Scorecard**: Daily therapy duration, compliance badge (&ge;4h), total AHI with clinical rating, OAHI, CAHI, HI, 95% Leak, and 95% Pressure.
- **Synchronized Multi-Track Waveform Canvas**:
  - **Flow Rate** (&plusmn;60 L/min at 25 Hz) with overlaid semi-transparent color tags for respiratory events (OA, CA, H).
  - **Mask Pressure** (4–20 cmH2O).
  - **Leak Rate** (0–40 L/min) with clinical 24 L/min redline threshold.
  - Synchronized hover crosshairs with live physical unit readouts.
  - Interactive mouse-wheel zoom, drag-to-pan, and minimap overview timeline.
- **Click-to-Inspect Events Log**: Clicking any event in the events log immediately zooms the waveform viewer to that event with a 30-second context window.

### Importing ResMed SD Card Data

Create or update an OSCAR database directly from your ResMed SD card:

```bash
# Import SD card directory into oscar.db
python -m oscarius import /path/to/sdcard --db oscar.db --profile "Default"
```

### Running the Application

#### Production Mode (Single-Server)
FastAPI automatically serves the pre-built frontend SPA at `/`:

```bash
# Build frontend bundle
cd frontend && npm run build && cd ..

# Start server
export OSCARIUS_DB_PATH="/path/to/oscar.db"
python -m oscarius serve --port 8000
```
Open `http://localhost:8000` in your browser.

#### Development Mode
Run backend and frontend with live reloading:

```bash
# Terminal 1: Backend
python -m oscarius serve --port 8000 --reload

# Terminal 2: Vite Dev Server (with proxy to :8000)
cd frontend && npm run dev
```

### Running Tests

```bash
python -m pytest
```
