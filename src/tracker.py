"""
tracker.py
對應 Workflow: Person Tracking

接收 pose_detector.py 每一幀輸出的 Detection（已含 ByteTrack 指派的 track_id），
維護每個 track_id 的時序狀態：位置歷史、關鍵點歷史、存活時間、移動速度等。
這些狀態是後續「行為/事件分析」(人數統計/異常偵測/ROI) 的輸入依據。
"""
from __future__ import annotations
import time
import logging
from typing import Dict, List

from .types import Detection, TrackState
from .geometry import bbox_foot_point, euclidean_distance

logger = logging.getLogger(__name__)


class PersonTracker:
    def __init__(self, max_history: int = 60, lost_track_ttl_sec: float = 5.0):
        self.max_history = max_history
        self.lost_track_ttl_sec = lost_track_ttl_sec
        self.tracks: Dict[int, TrackState] = {}

    def update(self, detections: List[Detection]) -> Dict[int, TrackState]:
        """用當前幀的偵測結果更新所有 track 的狀態，回傳本幀仍存活的 tracks。"""
        now = time.time()
        seen_ids = set()

        for det in detections:
            if det.track_id is None:
                continue  # 沒有被指派 ID（例如剛好漏偵測），略過時序追蹤
            seen_ids.add(det.track_id)

            state = self.tracks.get(det.track_id)
            if state is None:
                state = TrackState(track_id=det.track_id, first_seen=now)
                self.tracks[det.track_id] = state

            foot_point = bbox_foot_point(det.bbox)
            state.positions.append((foot_point[0], foot_point[1], now))
            state.keypoints_history.append(det.keypoints)
            state.last_seen = now

            if len(state.positions) > self.max_history:
                state.positions.pop(0)
            if len(state.keypoints_history) > self.max_history:
                state.keypoints_history.pop(0)

        self._prune_stale(now)
        return {tid: st for tid, st in self.tracks.items() if tid in seen_ids}

    def _prune_stale(self, now: float):
        stale_ids = [
            tid for tid, st in self.tracks.items()
            if now - st.last_seen > self.lost_track_ttl_sec
        ]
        for tid in stale_ids:
            logger.debug("Track %s 已離場，移除狀態", tid)
            del self.tracks[tid]

    def speed_px_per_sec(self, track_id: int, window: int = 5) -> float:
        """估算最近 window 幀的平均移動速度 (像素/秒)。"""
        state = self.tracks.get(track_id)
        if state is None or len(state.positions) < 2:
            return 0.0
        recent = state.positions[-window:]
        if len(recent) < 2:
            return 0.0
        (x0, y0, t0), (x1, y1, t1) = recent[0], recent[-1]
        dt = t1 - t0
        if dt <= 0:
            return 0.0
        return euclidean_distance((x0, y0), (x1, y1)) / dt

    def active_count(self) -> int:
        return len(self.tracks)
