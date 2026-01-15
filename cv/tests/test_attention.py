import time

from cv.attention import AttentionStatus, AttentionWindow, Hysteresis


def test_attention_window_percent_and_streak():
    window = AttentionWindow(window_seconds=10.0)
    base = 100.0
    window.add(base, AttentionStatus.AT_SCREEN)
    window.add(base + 5, AttentionStatus.LOOKING_AWAY)

    attention, streak = window.compute(base + 10)
    assert 45.0 <= attention <= 55.0
    assert streak == 0.0

    window.add(base + 9, AttentionStatus.AT_SCREEN)
    attention, streak = window.compute(base + 10)
    assert attention > 50.0
    assert 0.9 <= streak <= 1.1


def test_hysteresis_threshold():
    hyst = Hysteresis(frames=3, stable=AttentionStatus.NO_FACE)
    states = [
        AttentionStatus.LOOKING_AWAY,
        AttentionStatus.LOOKING_AWAY,
        AttentionStatus.LOOKING_AWAY,
        AttentionStatus.AT_SCREEN,
        AttentionStatus.AT_SCREEN,
        AttentionStatus.AT_SCREEN,
    ]
    stable_states = [hyst.update(s) for s in states]
    assert stable_states[1] == AttentionStatus.NO_FACE
    assert stable_states[2] == AttentionStatus.LOOKING_AWAY
    assert stable_states[-1] == AttentionStatus.AT_SCREEN
