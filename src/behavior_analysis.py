"""
behavior_analysis.py
對應 Workflow: Person Tracking → 行為/事件分析 → (人數統計 / 異常偵測 / ROI 區域)

這一層是三個子模組的協調者 (orchestrator)：把每一幀的 Detection + TrackState
分別餵給 PeopleCounter / AnomalyDetector / ROIManager，並把三者輸出的事件
彙整成單一清單，交給 event_engine.py 做去重、分級與寫入。
"""
from __future__ import annotations
from typing import Dict, List

from .types import Detection, TrackState, Event
from .people_counter import PeopleCounter
from .anomaly_detector import AnomalyDetector
from .roi_manager import ROIManager


class BehaviorAnalyzer:
    def __init__(self, config, tracker):
        b = config.behavior
        self.tracker = tracker

        self.people_counter = PeopleCounter(
            overcrowd_threshold=b.people_counting.overcrowd_threshold,
            log_interval_sec=b.people_counting.log_interval_sec,
        ) if b.people_counting.enabled else None

        ad = b.anomaly_detection
        self.anomaly_detector = AnomalyDetector(
            fall_enabled=ad.fall_detection.enabled,
            fall_aspect_ratio_threshold=ad.fall_detection.aspect_ratio_threshold,
            fall_vertical_ratio_threshold=ad.fall_detection.vertical_ratio_threshold,
            fall_confirm_frames=ad.fall_detection.confirm_frames,
            motion_enabled=ad.sudden_motion.enabled,
            motion_speed_threshold=ad.sudden_motion.speed_threshold_px_per_sec,
            motion_confirm_frames=ad.sudden_motion.confirm_frames,
        ) if ad.enabled else None

        self.loitering_enabled = ad.enabled and ad.loitering.enabled
        self.roi_manager = ROIManager(
            zones_cfg=b.roi.zones,
            loitering_enabled=self.loitering_enabled,
            dwell_seconds=ad.loitering.dwell_seconds,
        ) if b.roi.enabled else None

    def analyze(self, detections: List[Detection], tracks: Dict[int, TrackState]):
        """回傳 (people_stats: dict|None, events: List[Event])"""
        events: List[Event] = []
        people_stats = None

        if self.people_counter is not None:
            people_stats, cnt_events = self.people_counter.analyze(tracks)
            events += cnt_events

        if self.anomaly_detector is not None:
            events += self.anomaly_detector.analyze(
                detections, tracks, speed_lookup=self.tracker.speed_px_per_sec
            )

        if self.roi_manager is not None:
            events += self.roi_manager.analyze(detections, tracks)

        return people_stats, events

    def roi_snapshot(self, tracks: Dict[int, TrackState]) -> Dict[str, int]:
        if self.roi_manager is None:
            return {}
        return self.roi_manager.occupancy_snapshot(tracks)
