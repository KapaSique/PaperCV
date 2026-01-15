from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque


class AttentionStatus(str, Enum):
    AT_SCREEN = "AT_SCREEN"
    LOOKING_AWAY = "LOOKING_AWAY"
    NO_FACE = "NO_FACE"


@dataclass
class AttentionSample:
    timestamp: float
    status: AttentionStatus


@dataclass
class AttentionWindow:
    window_seconds: float = 30.0
    samples: Deque[AttentionSample] = field(default_factory=deque)

    def add(self, timestamp: float, status: AttentionStatus) -> None:
        self.samples.append(AttentionSample(timestamp=timestamp, status=status))
        self._trim(timestamp)

    def _trim(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

    def compute(self, now: float) -> tuple[float, float]:
        """
        Returns (attention_percent, focus_streak_seconds).
        """
        self._trim(now)
        if not self.samples:
            return 0.0, 0.0

        window_start = now - self.window_seconds
        attentive = 0.0
        prev_time = now

        for sample in reversed(self.samples):
            segment_start = max(sample.timestamp, window_start)
            duration = max(prev_time - segment_start, 0.0)
            if sample.status == AttentionStatus.AT_SCREEN:
                attentive += duration
            prev_time = segment_start
            if sample.timestamp < window_start:
                break

        total = min(self.window_seconds, now - self.samples[0].timestamp)
        total = max(total, 1e-6)
        attention_percent = max(min(100.0 * attentive / total, 100.0), 0.0)
        streak = self._compute_streak(now, window_start)
        return attention_percent, streak

    def _compute_streak(self, now: float, window_start: float) -> float:
        if not self.samples:
            return 0.0

        streak = 0.0
        prev_time = now
        for sample in reversed(self.samples):
            segment_start = max(sample.timestamp, window_start)
            duration = max(prev_time - segment_start, 0.0)
            if sample.status == AttentionStatus.AT_SCREEN:
                streak += duration
            else:
                break
            prev_time = segment_start
            if segment_start <= window_start:
                break
        return streak


@dataclass
class Hysteresis:
    frames: int = 3
    stable: AttentionStatus = AttentionStatus.NO_FACE
    candidate: AttentionStatus | None = None
    count: int = 0

    def update(self, incoming: AttentionStatus) -> AttentionStatus:
        if incoming == self.stable:
            self.candidate = None
            self.count = 0
            return self.stable

        if incoming == self.candidate:
            self.count += 1
        else:
            self.candidate = incoming
            self.count = 1

        if self.count >= self.frames:
            self.stable = incoming
            self.count = 0
            self.candidate = None

        return self.stable
