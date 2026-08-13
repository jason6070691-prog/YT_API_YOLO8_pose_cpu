"""
anomaly_detector.py
對應 Workflow: 行為/事件分析 → 異常偵測

以 Pose 關鍵點 + bbox 幾何特徵，做輕量、不需額外訓練模型的異常行為判斷：
  1. 跌倒偵測 (fall_detection)：
     - bbox 寬高比過大（人變成「躺著」的形狀）
     - 肩膀到髖部的垂直距離 / bbox 高度 過小（身體被壓扁在水平方向）
     需連續 N 幀都符合才確認，降低單幀誤判。
  2. 異常快速移動 (sudden_motion)：例如奔跑、推擠、追逐等，
     使用 tracker 估算的移動速度來判斷。

注意：這是規則式 (rule-based) 的輕量判斷，適合做即時 Demo /
第一層過濾；正式場域建議搭配專門訓練過的行為辨識模型做二次確認。
"""
from __future__ import annotations
from typing import Dict, List

from .types import TrackState, Detection, Event
from .constants import LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP


def _bbox_aspect_ratio(bbox) -> float:
    x1, y1, x2, y2 = bbox
    w, h = max(x2 - x1, 1e-6), max(y2 - y1, 1e-6)
    return w / h


def _vertical_torso_ratio(keypoints, bbox) -> float | None:
    """肩膀中點到髖部中點的垂直距離 / bbox 高度。值越小代表身體越『橫躺』。"""
    try:
        ls, rs = keypoints[LEFT_SHOULDER], keypoints[RIGHT_SHOULDER]
        lh, rh = keypoints[LEFT_HIP], keypoints[RIGHT_HIP]
    except (IndexError, TypeError):
        return None

    kp_conf_min = 0.3
    pts = [ls, rs, lh, rh]
    if any(p[2] < kp_conf_min for p in pts):
        return None

    shoulder_y = (ls[1] + rs[1]) / 2.0
    hip_y = (lh[1] + rh[1]) / 2.0
    x1, y1, x2, y2 = bbox
    bbox_h = max(y2 - y1, 1e-6)
    return abs(hip_y - shoulder_y) / bbox_h


class AnomalyDetector:
    def __init__(
        self,
        fall_enabled: bool = True,
        fall_aspect_ratio_threshold: float = 1.4,
        fall_vertical_ratio_threshold: float = 0.55,
        fall_confirm_frames: int = 5,
        motion_enabled: bool = True,
        motion_speed_threshold: float = 550.0,
        motion_confirm_frames: int = 3,
    ):
        self.fall_enabled = fall_enabled
        self.fall_aspect_ratio_threshold = fall_aspect_ratio_threshold
        self.fall_vertical_ratio_threshold = fall_vertical_ratio_threshold
        self.fall_confirm_frames = fall_confirm_frames

        self.motion_enabled = motion_enabled
        self.motion_speed_threshold = motion_speed_threshold
        self.motion_confirm_frames = motion_confirm_frames

    def analyze(
        self,
        detections: List[Detection],
        tracks: Dict[int, TrackState],
        speed_lookup,
    ) -> List[Event]:
        """speed_lookup: callable(track_id) -> px/sec，由 PersonTracker 提供。"""
        events: List[Event] = []

        for det in detections:
            if det.track_id is None or det.track_id not in tracks:
                continue
            state = tracks[det.track_id]

            if self.fall_enabled:
                events += self._check_fall(det, state)

            if self.motion_enabled:
                events += self._check_sudden_motion(det, state, speed_lookup)

        return events

    def _check_fall(self, det: Detection, state: TrackState) -> List[Event]:
        aspect = _bbox_aspect_ratio(det.bbox)
        vertical_ratio = _vertical_torso_ratio(det.keypoints, det.bbox)

        looks_fallen = aspect >= self.fall_aspect_ratio_threshold or (
            vertical_ratio is not None and vertical_ratio <= self.fall_vertical_ratio_threshold
        )

        if looks_fallen:
            state.fall_streak += 1
        else:
            state.fall_streak = 0

        if state.fall_streak == self.fall_confirm_frames:
            return [
                Event(
                    event_type="fall",
                    severity="critical",
                    track_id=det.track_id,
                    zone=state.current_zone,
                    message=f"追蹤 ID {det.track_id} 疑似跌倒",
                    extra={"aspect_ratio": aspect, "vertical_ratio": vertical_ratio},
                )
            ]
        return []

    def _check_sudden_motion(self, det: Detection, state: TrackState, speed_lookup) -> List[Event]:
        speed = speed_lookup(det.track_id)
        if speed >= self.motion_speed_threshold:
            state.motion_streak += 1
        else:
            state.motion_streak = 0

        if state.motion_streak == self.motion_confirm_frames:
            return [
                Event(
                    event_type="sudden_motion",
                    severity="warning",
                    track_id=det.track_id,
                    zone=state.current_zone,
                    message=f"追蹤 ID {det.track_id} 偵測到異常快速移動 ({speed:.0f} px/s)",
                    extra={"speed_px_per_sec": speed},
                )
            ]
        return []
