#!/usr/bin/env python3
"""
dashboard/app.py
對應 Workflow: Database / Log -> Streamlit Dashboard -> Alert / AI Report

啟動方式（在專案根目錄執行）:
    streamlit run dashboard/app.py

這支程式只「讀取」main.py 寫入的 SQLite 資料庫與最新標註畫面，
兩者可以分開執行：main.py 在背景跑 Pipeline，Dashboard 負責視覺化與 AI 報告。
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import os
import psycopg

conn = psycopg.connect(os.environ["DATABASE_URL"])

df = pd.read_sql(
    "select * from frame_stats order by ts desc limit 100",
    conn
)

st.image(
    f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/frames/latest_frame.jpg"
)

# 讓 dashboard/app.py 可以 import 到專案根目錄下的 src/
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.database import Database
from src.alert import generate_ai_report

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"
config = load_config(CONFIG_PATH)

st.set_page_config(page_title="YOLOv8-Pose 行為/事件分析 Dashboard", layout="wide")


@st.cache_resource
def get_database(db_path: str) -> Database:
    return Database(path=db_path)


def load_state():
    config = load_config(CONFIG_PATH)
    db = get_database(config.database.path)
    return config, db


def render_header(config):
    st.title("🎥 YouTube 即時姿態辨識 / 行為事件分析 Dashboard")
    st.caption(f"來源: {config.source.youtube_url}")


def render_metrics(db: Database):
    frame_stats = db.recent_frame_stats(limit=1)
    latest = frame_stats[-1] if frame_stats else None

    col1, col2, col3 = st.columns(3)
    col1.metric("目前人數", latest["current_count"] if latest else "—")
    col2.metric("累積不重複人數", latest["cumulative_unique_count"] if latest else "—")

    recent_events = db.recent_events(limit=500)
    critical_count = sum(1 for e in recent_events if e["severity"] == "critical")
    col3.metric("近期重大事件數", critical_count)


def render_people_trend(db: Database):
    st.subheader("📈 人數趨勢")
    since = time.time() - 30 * 60  # 最近 30 分鐘
    rows = db.recent_frame_stats(since_ts=since, limit=2000)
    if not rows:
        st.info("目前尚無人數統計資料，請確認 main.py 正在執行中。")
        return

    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["timestamp"], unit="s")
    fig = px.line(
        df, x="time", y=["current_count", "cumulative_unique_count"],
        labels={"value": "人數", "time": "時間", "variable": "指標"},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_live_frame(config):
    st.subheader("🖼️ 即時畫面（含骨架 / ROI 標註）")
    frame_path = Path(config.capture.annotated_frame_path)
    if frame_path.exists():
        st.image(str(frame_path), use_container_width=True)
    else:
        st.info("尚未產生標註畫面，請確認 main.py 已啟動且 save_annotated_frame 設為 true。")


def render_event_breakdown(db: Database):
    st.subheader("📊 事件類型統計（近 24 小時）")
    since = time.time() - 24 * 3600
    counts = db.event_counts_by_type(since_ts=since)
    if not counts:
        st.info("近 24 小時內沒有事件紀錄。")
        return
    df = pd.DataFrame(counts)
    fig = px.bar(df, x="event_type", y="cnt", labels={"event_type": "事件類型", "cnt": "次數"})
    st.plotly_chart(fig, use_container_width=True)


def render_event_log(db: Database, config):
    st.subheader("📋 事件紀錄")
    severity_filter = st.selectbox("最低嚴重度", ["info", "warning", "critical"], index=0)
    events = db.recent_events(limit=config.dashboard.max_events_shown, min_severity=severity_filter)

    if not events:
        st.info("目前沒有符合條件的事件。")
        return

    df = pd.DataFrame(events)
    df["time"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df[["time", "severity", "event_type", "track_id", "zone", "message"]]

    def _highlight(row):
        color = {"critical": "background-color:#ffcccc", "warning": "background-color:#fff3cd"}.get(
            row["severity"], ""
        )
        return [color] * len(row)

    st.dataframe(df.style.apply(_highlight, axis=1), use_container_width=True, height=400)
    return events


def render_ai_report(events):
    st.subheader("🤖 AI 事件摘要報告")
    st.caption("點擊按鈕彙整近期事件；若已設定 ANTHROPIC_API_KEY 會呼叫 Claude 生成摘要，否則使用內建模板。")
    if st.button("生成 AI Report"):
        with st.spinner("正在彙整事件並生成報告..."):
            report = generate_ai_report(events or [])
        st.text_area("報告內容", report, height=220)


def main():
    config, db = load_state()
    render_header(config)

    auto_refresh = st.sidebar.checkbox("自動刷新", value=False)
    refresh_sec = config.dashboard.refresh_interval_sec
    st.sidebar.write(f"刷新頻率: 每 {refresh_sec} 秒")
    if st.sidebar.button("立即刷新"):
        st.rerun()

    render_metrics(db)

    left, right = st.columns([2, 1])
    with left:
        render_people_trend(db)
        render_event_breakdown(db)
    with right:
        render_live_frame(config)

    events = render_event_log(db, config)
    render_ai_report(events)

    if auto_refresh:
        time.sleep(refresh_sec)
        st.rerun()


if __name__ == "__main__":
    main()
