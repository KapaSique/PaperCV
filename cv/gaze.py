from __future__ import annotations

import math
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import cv2
import mediapipe as mp
import numpy as np

from .config import CVSettings


LEFT_IRIS = [468, 469, 470, 471]
RIGHT_IRIS = [473, 474, 475, 476]
LEFT_EYE = [33, 133, 159, 145, 153, 173]
RIGHT_EYE = [362, 263, 386, 374, 380, 390]

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
MODEL_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "face_landmarker.task"


@dataclass
class GazeResult:
    yaw: float
    pitch: float
    roll: float
    gaze_x: float
    gaze_y: float
    face_landmarks: Any
    bbox: tuple[int, int, int, int]


def _iter_landmarks(face_landmarks: Any):
    return getattr(face_landmarks, "landmark", face_landmarks)


def _landmarks_to_points(face_landmarks: Any, width: int, height: int, indices: Iterable[int]) -> np.ndarray:
    return np.array(
        [
            (_iter_landmarks(face_landmarks)[i].x * width, _iter_landmarks(face_landmarks)[i].y * height)
            for i in indices
        ],
        dtype=np.float64,
    )


def _rotation_matrix_to_euler_angles(rmat: np.ndarray) -> tuple[float, float, float]:
    sy = math.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
    singular = sy < 1e-6

    if not singular:
        x = math.atan2(rmat[2, 1], rmat[2, 2])
        y = math.atan2(-rmat[2, 0], sy)
        z = math.atan2(rmat[1, 0], rmat[0, 0])
    else:
        x = math.atan2(-rmat[1, 2], rmat[1, 1])
        y = math.atan2(-rmat[2, 0], sy)
        z = 0

    return math.degrees(x), math.degrees(y), math.degrees(z)


def _head_pose(face_landmarks: Any, width: int, height: int) -> tuple[float, float, float]:
    image_points = _landmarks_to_points(face_landmarks, width, height, [1, 152, 33, 263, 61, 291])
    model_points = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, -63.6, -12.5],
            [-43.3, 32.7, -26.0],
            [43.3, 32.7, -26.0],
            [-28.9, -28.9, -24.1],
            [28.9, -28.9, -24.1],
        ],
        dtype=np.float64,
    )

    focal_length = width
    center = (width / 2, height / 2)
    camera_matrix = np.array([[focal_length, 0, center[0]], [0, focal_length, center[1]], [0, 0, 1]], dtype="double")

    dist_coeffs = np.zeros((4, 1))  # type: ignore[assignment]
    success, rotation_vector, translation_vector = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not success:
        return 0.0, 0.0, 0.0

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    pitch, yaw, roll = _rotation_matrix_to_euler_angles(rotation_matrix)
    return yaw, pitch, roll


def _eye_gaze(face_landmarks: Any, eye_indices: Iterable[int], iris_indices: Iterable[int]) -> tuple[float, float]:
    eye_points = np.array([(_iter_landmarks(face_landmarks)[i].x, _iter_landmarks(face_landmarks)[i].y) for i in eye_indices], dtype=np.float32)
    iris_points = np.array([(_iter_landmarks(face_landmarks)[i].x, _iter_landmarks(face_landmarks)[i].y) for i in iris_indices], dtype=np.float32)

    eye_center = eye_points.mean(axis=0)
    iris_center = iris_points.mean(axis=0)
    width = max(eye_points[:, 0].max() - eye_points[:, 0].min(), 1e-4)
    height = max(eye_points[:, 1].max() - eye_points[:, 1].min(), 1e-4)

    dx = (iris_center[0] - eye_center[0]) / width
    dy = (iris_center[1] - eye_center[1]) / height
    return float(dx), float(dy)


def _gaze_vector(face_landmarks: Any) -> tuple[float, float]:
    left_dx, left_dy = _eye_gaze(face_landmarks, LEFT_EYE, LEFT_IRIS)
    right_dx, right_dy = _eye_gaze(face_landmarks, RIGHT_EYE, RIGHT_IRIS)
    gaze_x = (left_dx + right_dx) / 2.0
    gaze_y = (left_dy + right_dy) / 2.0
    return gaze_x, gaze_y


def _bbox_from_landmarks(face_landmarks: Any, width: int, height: int) -> tuple[int, int, int, int]:
    xs = [lmk.x * width for lmk in _iter_landmarks(face_landmarks)]
    ys = [lmk.y * height for lmk in _iter_landmarks(face_landmarks)]
    x_min, x_max = int(min(xs)), int(max(xs))
    y_min, y_max = int(min(ys)), int(max(ys))
    return x_min, y_min, x_max - x_min, y_max - y_min


def _ensure_model(model_path: Path) -> None:
    if model_path.exists():
        return
    model_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(MODEL_URL, model_path)


class GazeEstimator:
    def __init__(self, settings: CVSettings):
        self.settings = settings
        self.smooth_gaze: Optional[tuple[float, float]] = None
        self.mode = "solutions" if getattr(mp, "solutions", None) else "tasks"

        if self.mode == "solutions":
            from mediapipe import solutions as mp_solutions  # type: ignore

            self.face_mesh = mp_solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=settings.thresholds.min_detection_confidence,
                min_tracking_confidence=settings.thresholds.min_tracking_confidence,
            )
            self.landmarker = None
        else:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision

            _ensure_model(MODEL_PATH)
            base_options = mp_python.BaseOptions(model_asset_path=str(MODEL_PATH))
            options = mp_vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
                num_faces=1,
                running_mode=mp_vision.RunningMode.IMAGE,
            )
            self.landmarker = mp_vision.FaceLandmarker.create_from_options(options)
            self.face_mesh = None

    def close(self) -> None:
        if self.face_mesh:
            self.face_mesh.close()
        if self.landmarker:
            self.landmarker.close()

    def infer(self, frame) -> Optional[GazeResult]:
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if self.mode == "solutions":
            result = self.face_mesh.process(rgb) if self.face_mesh else None
            if not result or not result.multi_face_landmarks:
                return None
            face_landmarks = result.multi_face_landmarks[0]
        else:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self.landmarker.detect(mp_image) if self.landmarker else None
            if not result or not result.face_landmarks:
                return None
            face_landmarks = result.face_landmarks[0]

        yaw, pitch, roll = _head_pose(face_landmarks, width, height)
        gaze_x, gaze_y = _gaze_vector(face_landmarks)

        if self.smooth_gaze is None:
            self.smooth_gaze = (gaze_x, gaze_y)
        else:
            alpha = self.settings.thresholds.smoothing_alpha
            self.smooth_gaze = (
                alpha * gaze_x + (1 - alpha) * self.smooth_gaze[0],
                alpha * gaze_y + (1 - alpha) * self.smooth_gaze[1],
            )

        bbox = _bbox_from_landmarks(face_landmarks, width, height)
        return GazeResult(
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            gaze_x=self.smooth_gaze[0],
            gaze_y=self.smooth_gaze[1],
            face_landmarks=face_landmarks,
            bbox=bbox,
        )
