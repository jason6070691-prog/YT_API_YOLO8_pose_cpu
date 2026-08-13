"""
database.py
對應 Workflow: Event Engine → Database / Log

輕量 SQLite 儲存層，不需額外安裝資料庫伺服器，方便 Demo / 單機部署。
Streamlit Dashboard 直接讀這個 SQLite 檔案來畫圖表。

資料表:
  events        - 所有觸發的事件 (跌倒/異常移動/徘徊/ROI擁擠/進出區域...)
  frame_stats   - 定期寫入的人數統計時序資料，用來畫「人數趨勢圖」
"""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from .types import Event

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    track_id INTEGER,
    zone TEXT,
    message TEXT NOT NULL,
    extra_json TEXT,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS frame_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    current_count INTEGER NOT NULL,
    cumulative_unique_count INTEGER NOT NULL,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_frame_stats_timestamp ON frame_stats(timestamp);
"""


class Database:
    def __init__(self, path: str = "data/events.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def insert_event(self, event: Event):
        import json
        self._conn.execute(
            "INSERT INTO events (event_type, severity, track_id, zone, message, extra_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_type,
                event.severity,
                event.track_id,
                event.zone,
                event.message,
                json.dumps(event.extra, ensure_ascii=False),
                event.timestamp,
            ),
        )
        self._conn.commit()

    def insert_frame_stats(self, current_count: int, cumulative_unique_count: int, timestamp: Optional[float] = None):
        self._conn.execute(
            "INSERT INTO frame_stats (current_count, cumulative_unique_count, timestamp) VALUES (?, ?, ?)",
            (current_count, cumulative_unique_count, timestamp or time.time()),
        )
        self._conn.commit()

    def recent_events(self, limit: int = 200, min_severity: Optional[str] = None) -> list[dict]:
        severity_order = {"info": 0, "warning": 1, "critical": 2}
        query = "SELECT event_type, severity, track_id, zone, message, extra_json, timestamp FROM events "
        params: list = []
        if min_severity in severity_order:
            allowed = [s for s, v in severity_order.items() if v >= severity_order[min_severity]]
            placeholders = ",".join("?" * len(allowed))
            query += f"WHERE severity IN ({placeholders}) "
            params += allowed
        query += "ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cur = self._conn.execute(query, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def recent_frame_stats(self, since_ts: Optional[float] = None, limit: int = 500) -> list[dict]:
        if since_ts is not None:
            cur = self._conn.execute(
                "SELECT current_count, cumulative_unique_count, timestamp FROM frame_stats "
                "WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT ?",
                (since_ts, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT current_count, cumulative_unique_count, timestamp FROM frame_stats "
                "ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return rows if since_ts is not None else list(reversed(rows))

    def event_counts_by_type(self, since_ts: Optional[float] = None) -> list[dict]:
        query = "SELECT event_type, COUNT(*) as cnt FROM events "
        params: list = []
        if since_ts is not None:
            query += "WHERE timestamp >= ? "
            params.append(since_ts)
        query += "GROUP BY event_type ORDER BY cnt DESC"
        cur = self._conn.execute(query, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self):
        self._conn.close()
