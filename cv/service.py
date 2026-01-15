from __future__ import annotations

import asyncio
import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from .attention import AttentionStatus, AttentionWindow, Hysteresis
from .config import CVSettings
from .gaze import GazeEstimator, GazeResult


@dataclass
class FrameMetrics:
    timestamp: float
    status: AttentionStatus
    attention: float
    focus_streak: float
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    fps: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


class CVService:
    def __init__(self, settings: CVSettings, db=None, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.settings = settings
        self.db = db
        self.loop = loop or asyncio.get_event_loop()

        self.window = AttentionWindow(window_seconds=settings.thresholds.window_seconds)
        self.hysteresis = Hysteresis(frames=settings.thresholds.hysteresis_frames)
        self.estimator = GazeEstimator(settings)

        self.capture: Optional[cv2.VideoCapture] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.listeners: List[asyncio.Queue] = []
        self.last_frame_jpeg: Optional[bytes] = None
        self.last_state = AttentionStatus.NO_FACE
        self.prev_ts = time.time()
        self.calibrating = False
        self.calibration_samples: List[tuple[float, float, float, float]] = []
        self.calibration = {"yaw": 0.0, "pitch": 0.0, "gaze_x": 0.0, "gaze_y": 0.0, "ready": False}

        self.lock = threading.Lock()

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.capture:
            self.capture.release()
        self.estimator.close()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self.listeners.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self.listeners:
            self.listeners.remove(queue)

    def request_calibration(self) -> None:
        self.calibrating = True
        self.calibration_samples.clear()

    def update_settings(self, settings: CVSettings) -> None:
        self.settings = settings
        self.window.window_seconds = settings.thresholds.window_seconds
        self.hysteresis.frames = settings.thresholds.hysteresis_frames

    def _broadcast(self, metrics: FrameMetrics) -> None:
        payload = json.dumps(metrics.to_dict())
        for queue in self.listeners:
            self.loop.call_soon_threadsafe(self._push_queue, queue, payload)

    @staticmethod
    def _push_queue(queue: asyncio.Queue, payload: str) -> None:
        try:
            if queue.qsize() > 2:
                queue.get_nowait()
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            return

    def _store_frame(self, frame) -> None:
        ok, buf = cv2.imencode(".jpg", frame)
        if ok:
            with self.lock:
                self.last_frame_jpeg = buf.tobytes()

    def latest_frame(self) -> Optional[bytes]:
        with self.lock:
            return self.last_frame_jpeg

    def _classify(self, gaze: Optional[GazeResult]) -> tuple[AttentionStatus, float, float, float, float, float]:
        if gaze is None:
            return AttentionStatus.NO_FACE, 0.0, 0.0, 0.0, 0.0, 0.0

        yaw_delta = abs(gaze.yaw - self.calibration["yaw"])
        pitch_delta = abs(gaze.pitch - self.calibration["pitch"])
        gaze_dx = gaze.gaze_x - self.calibration["gaze_x"]
        gaze_dy = gaze.gaze_y - self.calibration["gaze_y"]
        gaze_mag = math.sqrt(gaze_dx * gaze_dx + gaze_dy * gaze_dy)

        if yaw_delta > self.settings.thresholds.yaw_threshold_deg or pitch_delta > self.settings.thresholds.pitch_threshold_deg:
            status = AttentionStatus.LOOKING_AWAY
        elif gaze_mag > self.settings.thresholds.gaze_radius:
            status = AttentionStatus.LOOKING_AWAY
        else:
            status = AttentionStatus.AT_SCREEN

        return status, gaze.yaw, gaze.pitch, gaze.roll, gaze.gaze_x, gaze.gaze_y

    def _handle_calibration(self, gaze: Optional[GazeResult]) -> None:
        if not self.calibrating or gaze is None:
            return

        self.calibration_samples.append((gaze.yaw, gaze.pitch, gaze.gaze_x, gaze.gaze_y))
        if len(self.calibration_samples) >= self.settings.calibration.sample_frames:
            yaw, pitch, gx, gy = np.mean(np.array(self.calibration_samples), axis=0).tolist()
            self.calibration.update({"yaw": yaw, "pitch": pitch, "gaze_x": gx, "gaze_y": gy, "ready": True})
            self.calibrating = False
            if self.db:
                self.db.log_event("CALIBRATION_DONE", time.time(), json.dumps(self.calibration))

    def _draw_overlay(self, frame, metrics: FrameMetrics, gaze: Optional[GazeResult]) -> Any:
        overlay = frame.copy()
        if gaze:
            x, y, w, h = gaze.bbox
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
            eye_center = (int((x + w / 2)), int((y + h / 2)))
            arrow_length = 80
            end_point = (
                int(eye_center[0] + gaze.gaze_x * arrow_length),
                int(eye_center[1] + gaze.gaze_y * arrow_length),
            )
            cv2.arrowedLine(overlay, eye_center, end_point, (0, 255, 255), 2, tipLength=0.2)

        cv2.putText(
            overlay,
            f"{metrics.status.value} | attention {metrics.attention:.1f}% | streak {metrics.focus_streak:.1f}s | fps {metrics.fps:.1f}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return overlay

    def _log_event_transition(self, new_state: AttentionStatus, ts: float) -> None:
        if not self.db:
            return

        if self.last_state == AttentionStatus.NO_FACE and new_state != AttentionStatus.NO_FACE:
            self.db.log_event("NO_FACE_END", ts)
        elif self.last_state != AttentionStatus.NO_FACE and new_state == AttentionStatus.NO_FACE:
            self.db.log_event("NO_FACE_START", ts)

        if self.last_state == AttentionStatus.AT_SCREEN and new_state == AttentionStatus.LOOKING_AWAY:
            self.db.log_event("AWAY_START", ts)
        elif self.last_state == AttentionStatus.LOOKING_AWAY and new_state == AttentionStatus.AT_SCREEN:
            self.db.log_event("AWAY_END", ts)

    def _run(self) -> None:
        self.capture = cv2.VideoCapture(self.settings.camera.index)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.camera.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.camera.height)
        if self.settings.camera.fps:
            self.capture.set(cv2.CAP_PROP_FPS, self.settings.camera.fps)

        last_ts = time.time()

        while self.running:
            ok, frame = self.capture.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            now = time.time()
            dt = now - last_ts
            fps = 1.0 / dt if dt > 0 else 0.0
            last_ts = now

            gaze = self.estimator.infer(frame)
            self._handle_calibration(gaze)
            status, yaw, pitch, roll, gx, gy = self._classify(gaze)
            stable_status = self.hysteresis.update(status)

            self.window.add(now, stable_status)
            attention_percent, focus_streak = self.window.compute(now)
            metrics = FrameMetrics(
                timestamp=now,
                status=stable_status,
                attention=attention_percent,
                focus_streak=focus_streak,
                yaw=yaw,
                pitch=pitch,
                roll=roll,
                gaze_x=gx,
                gaze_y=gy,
                fps=fps,
            )

            self._log_event_transition(stable_status, now)
            self.last_state = stable_status

            if self.db:
                self.db.log_frame(metrics)

            overlay = self._draw_overlay(frame, metrics, gaze)
            self._store_frame(overlay)
            self._broadcast(metrics)

        if self.capture:
            self.capture.release()
