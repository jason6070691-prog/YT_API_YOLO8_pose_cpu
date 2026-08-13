"""
types.py
共用資料結構，串接 YOLOv8-Pose → Person Detection → Pose Keypoints →
Person Tracking → 行為/事件分析 各模組。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import time


@dataclass
class Detection:
    """單一幀、單一人的偵測結果 (Person Detection + Pose Keypoints)。"""
    track_id: Optional[int]         # None 代表尚未被 tracker 指派 ID
    bbox: Tuple[float, float, float, float]   # x1, y1, x2, y2
    conf: float
    keypoints: "list"               # [[x, y, conf], ...] 17 個 COCO 關鍵點
    frame_idx: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class TrackState:
    """單一 track_id 的時序狀態 (Person Tracking 模組維護)。"""
    track_id: int
    positions: list = field(default_factory=list)     # [(x, y, timestamp), ...]
    keypoints_history: list = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    current_zone: Optional[str] = None
    zone_enter_time: Optional[float] = None
    fall_streak: int = 0
    motion_streak: int = 0
    flags: dict = field(default_factory=dict)  # 已觸發過的一次性事件記錄，供 dedupe 使用


@dataclass
class Event:
    """行為/事件分析輸出的事件，最終寫入 Database / Log 並可能觸發 Alert。"""
    event_type: str          # fall / sudden_motion / loitering / roi_overcrowd / global_overcrowd / zone_enter / zone_exit
    severity: str            # info / warning / critical
    track_id: Optional[int]
    zone: Optional[str]
    message: str
    timestamp: float = field(default_factory=time.time)
    extra: dict = field(default_factory=dict)
