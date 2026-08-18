"""
database.py
Supabase 儲存層

資料表:
  events       - 所有觸發的事件
  frame_stats  - 人數統計時序資料
"""

from __future__ import annotations

import json
import os
from typing import Optional

from supabase import create_client, Client

from .types import Event


class Database:
    def __init__(self):
        # 取得 Render / 本機環境變數
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")

        if not self.supabase_url:
            raise RuntimeError(
                "找不到 SUPABASE_URL，請確認環境變數是否設定。"
            )

        if not self.supabase_key:
            raise RuntimeError(
                "找不到 SUPABASE_KEY，請確認環境變數是否設定。"
            )

        # 建立 Supabase Client
        self.client: Client = create_client(
            self.supabase_url,
            self.supabase_key,
        )

        print("✅ Supabase Database 已連線")

    # --------------------------------------------------
    # Events
    # --------------------------------------------------

    def insert_event(self, event: Event):
        """寫入事件到 Supabase events"""

        data = {
            "event_type": event.event_type,
            "severity": event.severity,
            "track_id": event.track_id,
            "zone": event.zone,
            "message": event.message,
            "extra_json": event.extra,
            "timestamp": event.timestamp,
        }

        response = (
            self.client
            .table("events")
            .insert(data)
            .execute()
        )

        return response

    # --------------------------------------------------
    # Frame Stats
    # --------------------------------------------------

    def insert_frame_stats(
        self,
        current_count: int,
        cumulative_unique_count: int,
        timestamp: Optional[float] = None,
    ):
        """寫入人數統計到 Supabase frame_stats"""

        import time

        data = {
            "current_count": current_count,
            "cumulative_unique_count": cumulative_unique_count,
            "timestamp": timestamp if timestamp is not None else time.time(),
        }

        response = (
            self.client
            .table("frame_stats")
            .insert(data)
            .execute()
        )

        return response

    # --------------------------------------------------
    # 最近事件
    # --------------------------------------------------

    def recent_events(
        self,
        limit: int = 200,
        min_severity: Optional[str] = None,
    ) -> list[dict]:

        severity_order = {
            "info": 0,
            "warning": 1,
            "critical": 2,
        }

        query = (
            self.client
            .table("events")
            .select(
                "event_type, severity, track_id, "
                "zone, message, extra_json, timestamp"
            )
        )

        # 過濾最低嚴重程度
        if min_severity in severity_order:
            allowed = [
                severity
                for severity, value in severity_order.items()
                if value >= severity_order[min_severity]
            ]

            query = query.in_("severity", allowed)

        response = (
            query
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data or []

    # --------------------------------------------------
    # 最近人數統計
    # --------------------------------------------------

    def recent_frame_stats(
        self,
        since_ts: Optional[float] = None,
        limit: int = 500,
    ) -> list[dict]:

        query = (
            self.client
            .table("frame_stats")
            .select(
                "current_count, "
                "cumulative_unique_count, "
                "timestamp"
            )
        )

        if since_ts is not None:
            query = query.gte("timestamp", since_ts)

            response = (
                query
                .order("timestamp", desc=False)
                .limit(limit)
                .execute()
            )

            return response.data or []

        else:
            response = (
                query
                .order("timestamp", desc=True)
                .limit(limit)
                .execute()
            )

            rows = response.data or []

            # 保持和原本 SQLite 版本相同：
            # 最舊 → 最新
            return list(reversed(rows))

    # --------------------------------------------------
    # 事件統計
    # --------------------------------------------------

    def event_counts_by_type(
        self,
        since_ts: Optional[float] = None,
    ) -> list[dict]:

        query = (
            self.client
            .table("events")
            .select("event_type")
        )

        if since_ts is not None:
            query = query.gte("timestamp", since_ts)

        response = query.execute()

        rows = response.data or []

        # Supabase REST 查回資料後，在 Python 統計
        counts = {}

        for row in rows:
            event_type = row.get("event_type")

            if event_type:
                counts[event_type] = counts.get(event_type, 0) + 1

        result = [
            {
                "event_type": event_type,
                "cnt": count,
            }
            for event_type, count in counts.items()
        ]

        result.sort(
            key=lambda x: x["cnt"],
            reverse=True,
        )

        return result

    # --------------------------------------------------
    # 關閉
    # --------------------------------------------------

    def close(self):
        """
        Supabase client 不需要像 SQLite 一樣手動 close。
        保留此方法是為了讓原本 main.py 不需要修改。
        """

        print("Supabase Database connection released.")
