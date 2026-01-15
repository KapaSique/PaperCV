from __future__ import annotations

from typing import List

from pydantic import BaseModel


class CameraSchema(BaseModel):
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 24


class AttentionSchema(BaseModel):
    yaw_threshold_deg: float = 18.0
    pitch_threshold_deg: float = 15.0
    gaze_radius: float = 0.28
    smoothing_alpha: float = 0.55
    hysteresis_frames: int = 3
    window_seconds: float = 30.0
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


class CalibrationSchema(BaseModel):
    sample_frames: int = 45


class SettingsSchema(BaseModel):
    camera: CameraSchema = CameraSchema()
    attention: AttentionSchema = AttentionSchema()
    calibration: CalibrationSchema = CalibrationSchema()


class FrameSchema(BaseModel):
    timestamp: float
    status: str
    attention: float
    focus_streak: float
    yaw: float
    pitch: float
    roll: float
    gaze_x: float
    gaze_y: float
    fps: float


class HistoryResponse(BaseModel):
    frames: List[FrameSchema]
    events: List[dict]
