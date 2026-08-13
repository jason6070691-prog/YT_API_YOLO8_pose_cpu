"""
roi_manager.py
對應 Workflow: 行為/事件分析 → ROI 區域

依照 config.yaml 定義的多邊形區域 (zones)，判斷每個追蹤目標目前位於哪個 ROI：
  - 進出區域事件 (zone_enter / zone_exit)
  - 區域人數超過容量上限 (roi_overcrowd)
  - 同一人在同一區域停留過久 (loitering)
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .types import Detection, TrackState, Event
from .geometry import point_in_polygon, bbox_foot_point


@dataclass
class Zone:
    name: str
    polygon: list
    max_capacity: Optional[int] = None


class ROIManager:
    def __init__(self, zones_cfg: list, loitering_enabled: bool = True, dwell_seconds: float = 30.0):
        self.zones = [Zone(z["name"], z["polygon"], z.get("max_capacity")) for z in zones_cfg]
        self.loitering_enabled = loitering_enabled
        self.dwell_seconds = dwell_seconds

    def _find_zone(self, point) -> Optional[Zone]:
        for zone in self.zones:
            if point_in_polygon(point, zone.polygon):
                return zone
        return None

    def analyze(self, detections: List[Detection], tracks: Dict[int, TrackState]) -> List[Event]:
        events: List[Event] = []
        now = time.time()
        zone_occupancy: Dict[str, int] = {z.name: 0 for z in self.zones}

        for det in detections:
            if det.track_id is None or det.track_id not in tracks:
                continue
            state = tracks[det.track_id]
            foot_point = bbox_foot_point(det.bbox)
            zone = self._find_zone(foot_point)
            zone_name = zone.name if zone else None

            if zone_name != state.current_zone:
                if state.current_zone is not None:
                    events.append(
                        Event(
                            event_type="zone_exit",
                            severity="info",
                            track_id=det.track_id,
                            zone=state.current_zone,
                            message=f"追蹤 ID {det.track_id} 離開區域「{state.current_zone}」",
                        )
                    )
                if zone_name is not None:
                    events.append(
                        Event(
                            event_type="zone_enter",
                            severity="info",
                            track_id=det.track_id,
                            zone=zone_name,
                            message=f"追蹤 ID {det.track_id} 進入區域「{zone_name}」",
                        )
                    )
                state.current_zone = zone_name
                state.zone_enter_time = now if zone_name else None

            if zone_name:
                zone_occupancy[zone_name] += 1

                if self.loitering_enabled and state.zone_enter_time is not None:
                    dwell = now - state.zone_enter_time
                    already_flagged = state.flags.get(f"loiter_{zone_name}")
                    if dwell >= self.dwell_seconds and not already_flagged:
                        state.flags[f"loiter_{zone_name}"] = True
                        events.append(
                            Event(
                                event_type="loitering",
                                severity="warning",
                                track_id=det.track_id,
                                zone=zone_name,
                                message=f"追蹤 ID {det.track_id} 在「{zone_name}」停留超過 {int(dwell)} 秒",
                                extra={"dwell_seconds": dwell},
                            )
                        )

        for zone in self.zones:
            count = zone_occupancy.get(zone.name, 0)
            if zone.max_capacity is not None and count > zone.max_capacity:
                events.append(
                    Event(
                        event_type="roi_overcrowd",
                        severity="warning",
                        track_id=None,
                        zone=zone.name,
                        message=f"區域「{zone.name}」人數 {count} 超過容量 {zone.max_capacity}",
                        extra={"count": count, "max_capacity": zone.max_capacity},
                    )
                )

        return events

    def occupancy_snapshot(self, tracks: Dict[int, TrackState]) -> Dict[str, int]:
        snapshot = {z.name: 0 for z in self.zones}
        for state in tracks.values():
            if state.current_zone:
                snapshot[state.current_zone] = snapshot.get(state.current_zone, 0) + 1
        return snapshot
