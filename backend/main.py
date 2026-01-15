from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
import yaml
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from cv import CVService
from cv.config import CVSettings

from .config_loader import load_settings, persist_settings
from .db import Database
from .schemas import HistoryResponse, SettingsSchema

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "configs" / "default.yaml"

raw_cfg: Dict[str, Any] = {}
if CONFIG_PATH.exists():
    with CONFIG_PATH.open("r") as fh:
        raw_cfg = yaml.safe_load(fh) or {}

cv_settings: CVSettings = load_settings(str(CONFIG_PATH))
db_path = raw_cfg.get("storage", {}).get("database_path", "artifacts/attention_guard.db")
DB_PATH = ROOT / db_path
database = Database(str(DB_PATH))

app = FastAPI(title="attention-guard", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

loop = asyncio.get_event_loop()
cv_service = CVService(cv_settings, db=database, loop=loop)


def _schema_from_settings(settings: CVSettings) -> SettingsSchema:
    return SettingsSchema(
        camera={
            "index": settings.camera.index,
            "width": settings.camera.width,
            "height": settings.camera.height,
            "fps": settings.camera.fps,
        },
        attention={
            "yaw_threshold_deg": settings.thresholds.yaw_threshold_deg,
            "pitch_threshold_deg": settings.thresholds.pitch_threshold_deg,
            "gaze_radius": settings.thresholds.gaze_radius,
            "smoothing_alpha": settings.thresholds.smoothing_alpha,
            "hysteresis_frames": settings.thresholds.hysteresis_frames,
            "window_seconds": settings.thresholds.window_seconds,
            "min_detection_confidence": settings.thresholds.min_detection_confidence,
            "min_tracking_confidence": settings.thresholds.min_tracking_confidence,
        },
        calibration={"sample_frames": settings.calibration.sample_frames},
    )


@app.on_event("startup")
async def startup() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    cv_service.loop = asyncio.get_running_loop()
    cv_service.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    cv_service.stop()


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "cv_running": cv_service.running}


@app.get("/api/settings", response_model=SettingsSchema)
async def get_settings() -> SettingsSchema:
    return _schema_from_settings(cv_settings)


@app.post("/api/settings", response_model=SettingsSchema)
async def update_settings(payload: SettingsSchema) -> SettingsSchema:
    global cv_settings
    cv_settings = CVSettings.from_dict(payload.dict())
    cv_service.update_settings(cv_settings)
    persist_settings(str(CONFIG_PATH), payload.dict())
    return payload


@app.post("/api/calibrate")
async def calibrate() -> Dict[str, str]:
    cv_service.request_calibration()
    return {"status": "CALIBRATION_REQUESTED"}


@app.websocket("/api/stream")
async def websocket_stream(ws: WebSocket) -> None:
    await ws.accept()
    queue = cv_service.subscribe()
    try:
        while True:
            payload = await queue.get()
            await ws.send_text(payload)
    except WebSocketDisconnect:
        pass
    finally:
        cv_service.unsubscribe(queue)


@app.get("/api/history", response_model=HistoryResponse)
async def history(
    start: Optional[float] = Query(None),
    end: Optional[float] = Query(None),
) -> HistoryResponse:
    now = time.time()
    start_ts = start or (now - 60 * 10)
    end_ts = end or now
    frames = database.history(start_ts, end_ts)
    events = database.events(start_ts, end_ts)
    return HistoryResponse(frames=frames, events=events)


@app.get("/api/export")
async def export(
    start: Optional[float] = Query(None),
    end: Optional[float] = Query(None),
) -> StreamingResponse:
    now = time.time()
    start_ts = start or (now - 60 * 10)
    end_ts = end or now
    filename = f"attention_{int(start_ts)}_{int(end_ts)}.csv"
    generator = database.export_csv(start_ts, end_ts)
    return StreamingResponse(generator, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/video")
async def video_feed() -> StreamingResponse:
    boundary = "frame"

    async def frame_generator():
        while True:
            frame = cv_service.latest_frame()
            if frame:
                yield b"--" + boundary.encode() + b"\r\n"
                yield b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.08)

    media_type = f"multipart/x-mixed-replace; boundary={boundary}"
    return StreamingResponse(frame_generator(), media_type=media_type)


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
