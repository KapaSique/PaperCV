import time

from backend.db import Database
from cv.attention import AttentionStatus
from cv.service import FrameMetrics


def test_db_insert_and_query(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    ts = time.time()
    metrics = FrameMetrics(
        timestamp=ts,
        status=AttentionStatus.AT_SCREEN,
        attention=95.0,
        focus_streak=4.5,
        yaw=1.0,
        pitch=2.0,
        roll=3.0,
        gaze_x=0.1,
        gaze_y=-0.1,
        fps=24.0,
    )
    db.log_frame(metrics)
    db.log_event("AWAY_START", ts + 1, "demo")

    frames = db.history(ts - 1, ts + 2)
    assert len(frames) == 1
    assert frames[0]["status"] == AttentionStatus.AT_SCREEN.value
    assert abs(frames[0]["attention"] - 95.0) < 1e-3

    events = db.events(ts, ts + 5)
    assert len(events) == 1
    assert events[0]["type"] == "AWAY_START"
