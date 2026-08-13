"""
event_engine.py
對應 Workflow: 行為/事件分析 → Event Engine → Database / Log → Alert / AI Report

把 BehaviorAnalyzer 輸出的原始事件做：
  1. 套用 config 的嚴重度對照表 (severity_map)
  2. 去重 (同一 track_id + 同一事件類型，在 dedupe_window_sec 內只處理一次)
  3. 寫入資料庫 (Database)
  4. 交給 AlertDispatcher 決定是否要發告警 (Alert)
"""
from __future__ import annotations
import time
from typing import Dict, List, Tuple

from .types import Event
from .database import Database
from .alert import AlertDispatcher


class EventEngine:
    def __init__(
        self,
        database: Database,
        alert_dispatcher: AlertDispatcher,
        severity_map: dict,
        dedupe_window_sec: float = 10.0,
    ):
        self.database = database
        self.alert_dispatcher = alert_dispatcher
        self.severity_map = severity_map
        self.dedupe_window_sec = dedupe_window_sec
        self._last_seen: Dict[Tuple[str, object], float] = {}

    def _is_duplicate(self, event: Event) -> bool:
        key = (event.event_type, event.track_id)
        now = event.timestamp
        last = self._last_seen.get(key)
        if last is not None and (now - last) < self.dedupe_window_sec:
            return True
        self._last_seen[key] = now
        return False

    def process(self, events: List[Event]) -> List[Event]:
        """處理一批事件：套用嚴重度、去重、寫 DB、發告警。回傳實際被記錄的事件。"""
        recorded: List[Event] = []
        for event in events:
            if event.event_type in self.severity_map:
                event.severity = self.severity_map[event.event_type]

            if self._is_duplicate(event):
                continue

            self.database.insert_event(event)
            self.alert_dispatcher.dispatch(event)
            recorded.append(event)

        return recorded
