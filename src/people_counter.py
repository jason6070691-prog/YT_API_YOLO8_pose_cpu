"""
people_counter.py
對應 Workflow: 行為/事件分析 → 人數統計

統計當前畫面人數、累積出現過的不重複人數，並在超過閾值時產生擁擠事件。
"""
from __future__ import annotations
import time
from typing import Dict, List

from .types import TrackState, Event


class PeopleCounter:
    def __init__(self, overcrowd_threshold: int = 15, log_interval_sec: float = 5.0):
        self.overcrowd_threshold = overcrowd_threshold
        self.log_interval_sec = log_interval_sec
        self.unique_ids_seen: set[int] = set()
        self._last_log_time = 0.0

    def analyze(self, tracks: Dict[int, TrackState]) -> tuple[dict, List[Event]]:
        """回傳 (統計摘要 dict, 觸發的 Event 清單)。"""
        now = time.time()
        current_count = len(tracks)
        self.unique_ids_seen.update(tracks.keys())

        stats = {
            "timestamp": now,
            "current_count": current_count,
            "cumulative_unique_count": len(self.unique_ids_seen),
        }

        events: List[Event] = []
        if current_count > self.overcrowd_threshold:
            events.append(
                Event(
                    event_type="global_overcrowd",
                    severity="warning",
                    track_id=None,
                    zone=None,
                    message=f"畫面人數 {current_count} 超過閾值 {self.overcrowd_threshold}",
                    extra={"current_count": current_count},
                )
            )

        should_log = (now - self._last_log_time) >= self.log_interval_sec
        if should_log:
            self._last_log_time = now
        stats["should_log"] = should_log

        return stats, events
