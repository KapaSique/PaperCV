from __future__ import annotations

import csv
import io
import sqlite3
import threading
from typing import Iterable, List, Optional

from cv.service import FrameMetrics


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS frames (
                    ts REAL,
                    status TEXT,
                    attention REAL,
                    focus_streak REAL,
                    yaw REAL,
                    pitch REAL,
                    roll REAL,
                    gaze_x REAL,
                    gaze_y REAL,
                    fps REAL
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_frames_ts ON frames(ts);")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    ts REAL,
                    type TEXT,
                    details TEXT
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);")
            self.conn.commit()

    def log_frame(self, metrics: FrameMetrics) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO frames (ts, status, attention, focus_streak, yaw, pitch, roll, gaze_x, gaze_y, fps)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metrics.timestamp,
                    metrics.status.value,
                    metrics.attention,
                    metrics.focus_streak,
                    metrics.yaw,
                    metrics.pitch,
                    metrics.roll,
                    metrics.gaze_x,
                    metrics.gaze_y,
                    metrics.fps,
                ),
            )
            self.conn.commit()

    def log_event(self, event_type: str, ts: float, details: Optional[str] = None) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO events (ts, type, details) VALUES (?, ?, ?)",
                (ts, event_type, details or ""),
            )
            self.conn.commit()

    def history(self, start_ts: float, end_ts: float) -> List[dict]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT ts, status, attention, focus_streak, yaw, pitch, roll, gaze_x, gaze_y, fps
                FROM frames WHERE ts BETWEEN ? AND ? ORDER BY ts ASC
                """,
                (start_ts, end_ts),
            )
            rows = cur.fetchall()
        keys = ["timestamp", "status", "attention", "focus_streak", "yaw", "pitch", "roll", "gaze_x", "gaze_y", "fps"]
        return [dict(zip(keys, row)) for row in rows]

    def events(self, start_ts: float, end_ts: float) -> List[dict]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT ts, type, details FROM events WHERE ts BETWEEN ? AND ? ORDER BY ts ASC",
                (start_ts, end_ts),
            )
            rows = cur.fetchall()
        keys = ["timestamp", "type", "details"]
        return [dict(zip(keys, row)) for row in rows]

    def export_csv(self, start_ts: float, end_ts: float) -> Iterable[bytes]:
        headers = ["timestamp", "status", "attention", "focus_streak", "yaw", "pitch", "roll", "gaze_x", "gaze_y", "fps"]
        yield ",".join(headers).encode() + b"\n"
        for row in self.history(start_ts, end_ts):
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=headers)
            writer.writerow(row)
            yield buf.getvalue().encode()
