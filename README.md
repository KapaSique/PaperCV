attention-guard
================

Real-time webcam attention monitor with gaze estimation, FastAPI backend, and React dashboard.

Approach
- MediaPipe face landmarker (tasks API) with iris landmarks, OpenCV for capture/overlays.
- Heuristics for attention: head yaw/pitch thresholds + gaze radius, smoothed and debounced.
- Rolling window + focus streak via in-memory buffer, persisted to SQLite with events.
- FastAPI exposes health, settings, calibration, websocket metrics, MJPEG preview, history, CSV export.
- React (Vite) UI shows live preview, overlays, attention %, streaks, tweakable thresholds, history timeline, and event feed.

File tree
- `backend/` FastAPI app (`main.py`), SQLite helper, schemas, tests.
- `cv/` CV logic (gaze estimation, attention window, hysteresis, service loop), tests.
- `frontend/` Vite React dashboard.
- `configs/default.yaml` defaults for camera + thresholds.
- `artifacts/sample-dashboard.svg` sample UI capture.
- `Makefile` convenience for dev/lint/test.

Backend API
- `GET /api/health`
- `GET/POST /api/settings`
- `POST /api/calibrate`
- `GET /api/history?start=&end=`
- `GET /api/export?start=&end=` (CSV)
- `GET /api/video` MJPEG preview with overlays
- `WS /api/stream` live metrics (>=5 Hz)

Run it
```bash
make install        # once; installs Python + frontend deps
make dev            # starts FastAPI on :8000 and Vite on :5173
```

Other commands
- `make backend` / `make frontend` to run individually.
- `make test` runs pytest for logic + DB.
- `make lint` runs ruff and frontend eslint.

Frontend
- Open `http://localhost:5173` (defaults to backend `http://localhost:8000`).
- Live preview comes from `/api/video`; metrics over websocket `/api/stream`.
- Settings form POSTs to `/api/settings`; calibrate button hits `/api/calibrate`.

Configs
- `configs/default.yaml` controls camera index/resolution/fps, yaw/pitch thresholds, gaze radius, smoothing alpha, window size, hysteresis frames, calibration frame count, and DB path.

Screenshots
- Sample dashboard: `artifacts/sample-dashboard.svg`

Troubleshooting
- MacOS camera permission: allow terminal/IDE to access camera in System Settings -> Privacy & Security -> Camera.
- If webcam is already in use, stop other apps or change `camera.index` in `configs/default.yaml`.
- MJPEG preview laggy: lower resolution/fps in config; reduce `window_seconds` for lighter DB writes.
- Mediapipe install issues on ARM Macs: ensure Python 3.10+ and run `pip install --upgrade pip setuptools wheel` before installing requirements.
- First run downloads the MediaPipe face_landmarker task model (~15MB) into `artifacts/face_landmarker.task`; ensure network is available once.

Notes
- Attention score = % of time in rolling window marked `AT_SCREEN`. Hysteresis (default 3 frames) debounces state flips.
- Events persisted: `AWAY_START/END`, `NO_FACE_START/END`, `CALIBRATION_DONE`. CSV export includes per-frame metrics.
