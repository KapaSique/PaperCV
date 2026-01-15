"""
Computer vision layer for attention-guard.
"""

from .attention import AttentionStatus, AttentionWindow, Hysteresis
from .config import CVSettings
from .service import CVService

__all__ = [
    "AttentionStatus",
    "AttentionWindow",
    "Hysteresis",
    "CVService",
    "CVSettings",
]
