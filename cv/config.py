from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 24


@dataclass
class Thresholds:
    yaw_threshold_deg: float = 18.0
    pitch_threshold_deg: float = 15.0
    gaze_radius: float = 0.28
    smoothing_alpha: float = 0.55
    hysteresis_frames: int = 3
    window_seconds: float = 30.0
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


@dataclass
class CalibrationSettings:
    sample_frames: int = 45


@dataclass
class CVSettings:
    camera: CameraConfig = field(default_factory=CameraConfig)
    thresholds: Thresholds = field(default_factory=Thresholds)
    calibration: CalibrationSettings = field(default_factory=CalibrationSettings)

    @classmethod
    def from_dict(cls, payload: dict) -> "CVSettings":
        camera_data = payload.get("camera", {})
        attention_data = payload.get("attention", {})
        calibration_data = payload.get("calibration", {})

        camera = CameraConfig(
            index=int(camera_data.get("index", 0)),
            width=int(camera_data.get("width", 1280)),
            height=int(camera_data.get("height", 720)),
            fps=int(camera_data.get("fps", 24)),
        )
        thresholds = Thresholds(
            yaw_threshold_deg=float(attention_data.get("yaw_threshold_deg", 18.0)),
            pitch_threshold_deg=float(attention_data.get("pitch_threshold_deg", 15.0)),
            gaze_radius=float(attention_data.get("gaze_radius", 0.28)),
            smoothing_alpha=float(attention_data.get("smoothing_alpha", 0.55)),
            hysteresis_frames=int(attention_data.get("hysteresis_frames", 3)),
            window_seconds=float(attention_data.get("window_seconds", 30.0)),
            min_detection_confidence=float(attention_data.get("min_detection_confidence", 0.5)),
            min_tracking_confidence=float(attention_data.get("min_tracking_confidence", 0.5)),
        )
        calibration = CalibrationSettings(
            sample_frames=int(calibration_data.get("sample_frames", 45)),
        )
        return cls(camera=camera, thresholds=thresholds, calibration=calibration)
