import os
from datetime import datetime, timezone, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client


# ============================================================
# Streamlit 設定
# ============================================================

st.set_page_config(
    page_title="YOLOv8 即時監控 Dashboard",
    page_icon="🎥",
    layout="wide",
)


# ============================================================
# Supabase 連線
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ 找不到 SUPABASE_URL 或 SUPABASE_KEY")
    st.stop()

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# ============================================================
# 台灣時區
# ============================================================

TAIWAN_TZ = timezone(timedelta(hours=8))


# ============================================================
# UTC → 台灣時間
# ============================================================

def taiwan_time(value):
    """
    將 Supabase 的時間轉成台灣時間。
    最後回傳字串，避免 Streamlit / Plotly 再自行轉時區。
    """

    if value is None:
        return "—"

    try:
        dt = pd.to_datetime(value, utc=True)

        if pd.isna(dt):
            return "—"

        dt = dt.tz_convert("Asia/Taipei")

        return dt.strftime("%Y-%m-%d %H:%M:%S")

    except Exception:
        return str(value)


# ============================================================
# 取得最新人數
# ============================================================

def get_latest_frame_stats():

    try:
        response = (
            supabase
            .table("frame_stats")
            .select(
                "current_count, cumulative_unique_count, ts"
            )
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]

    except Exception as e:
        st.warning(f"無法讀取人數資料：{e}")

    return None


# ============================================================
# 取得人數趨勢
# ============================================================

def get_frame_stats():

    try:
        response = (
            supabase
            .table("frame_stats")
            .select(
                "current_count, cumulative_unique_count, ts"
            )
            .order("ts", desc=False)
            .limit(500)
            .execute()
        )

        return response.data or []

    except Exception as e:
        st.warning(f"無法讀取人數趨勢：{e}")

    return []


# ============================================================
# 取得事件
# ============================================================

def get_events():

    try:
        response = (
            supabase
            .table("events")
            .select(
                "event_type, severity, track_id, zone, timestamp"
            )
            .order("timestamp", desc=True)
            .limit(200)
            .execute()
        )

        return response.data or []

    except Exception as e:
        st.warning(f"無法讀取事件資料：{e}")

    return []


# ============================================================
# 主 Dashboard
#
# Streamlit 1.61.1:
# fragment(run_every="2s")
#
# 不再使用：
# time.sleep(2)
# st.rerun()
#
# ============================================================

@st.fragment(run_every="2s")
def dashboard():

    # ========================================================
    # 標題
    # ========================================================

    st.title("🎥 YOLOv8 即時監控 Dashboard")

    st.caption(
        "YOLOv8-Pose ｜ 即時人物偵測 ｜ 行為 / 事件分析"
    )


    # ========================================================
    # 系統狀態
    # ========================================================

    col_status1, col_status2 = st.columns([1, 5])

    with col_status1:
        st.success("🟢 系統運作中")

    with col_status2:
        current_time = datetime.now(TAIWAN_TZ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        st.caption(
            f"最後更新：{current_time}（台灣時間）"
        )


    # ========================================================
    # 即時畫面
    # ========================================================

    st.subheader("🖼️ 即時監控畫面")

    image_url = (
        f"{SUPABASE_URL}"
        f"/storage/v1/object/public/frames/latest_frame.jpg"
        f"?t={int(datetime.now().timestamp())}"
    )

    st.image(
        image_url,
        use_container_width=True,
    )


    # ========================================================
    # 從 Supabase 取得資料
    # ========================================================

    latest = get_latest_frame_stats()
    frame_rows = get_frame_stats()
    events = get_events()


    # ========================================================
    # KPI
    # ========================================================

    current_count = (
        latest.get("current_count", 0)
        if latest
        else 0
    )

    unique_count = (
        latest.get("cumulative_unique_count", 0)
        if latest
        else 0
    )

    event_count = len(events)

    critical_count = sum(
        1
        for event in events
        if event.get("severity") == "critical"
    )


    st.subheader("📊 即時統計")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "目前人數",
            current_count,
        )

    with col2:
        st.metric(
            "累計不重複人數",
            unique_count,
        )

    with col3:
        st.metric(
            "事件總數",
            event_count,
        )

    with col4:
        st.metric(
            "重大事件",
            critical_count,
        )


    # ========================================================
    # 人數趨勢
    # ========================================================

    st.subheader("📈 人數趨勢")

    if frame_rows:

        df = pd.DataFrame(frame_rows)

        # ----------------------------------------------------
        # 重要：
        # 先當成 UTC
        # 再轉成台灣時間
        # 最後移除 timezone 資訊
        #
        # 這樣 Plotly 不會再把它轉回瀏覽器時區。
        # ----------------------------------------------------

        df["time"] = (
            pd.to_datetime(
                df["ts"],
                utc=True,
            )
            .dt.tz_convert("Asia/Taipei")
            .dt.tz_localize(None)
        )

        fig = px.line(
            df,
            x="time",
            y=[
                "current_count",
                "cumulative_unique_count",
            ],
            labels={
                "time": "時間（台灣時間）",
                "value": "人數",
                "variable": "統計項目",
            },
            title="即時人數變化",
        )

        fig.update_layout(
            hovermode="x unified",
            legend_title_text="",
            xaxis_title="時間（台灣時間）",
            yaxis_title="人數",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.info(
            "目前還沒有足夠的人數統計資料。"
        )


    # ========================================================
    # 事件統計
    # ========================================================

    st.subheader("⚠️ 事件統計")

    if events:

        event_df = pd.DataFrame(events)

        event_counts = (
            event_df["event_type"]
            .value_counts()
            .reset_index()
        )

        event_counts.columns = [
            "event_type",
            "count",
        ]

        fig = px.bar(
            event_counts,
            x="event_type",
            y="count",
            labels={
                "event_type": "事件類型",
                "count": "次數",
            },
            title="事件類型統計",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.info(
            "目前尚未偵測到事件。"
        )


    # ========================================================
    # 最新事件
    # ========================================================

    st.subheader("📋 最新事件")

    if events:

        event_df = pd.DataFrame(events)

        event_df["時間"] = (
            event_df["timestamp"]
            .apply(taiwan_time)
        )

        event_df = event_df.rename(
            columns={
                "event_type": "事件類型",
                "severity": "嚴重程度",
                "track_id": "人物 ID",
                "zone": "區域",
            }
        )

        display_columns = [
            "時間",
            "事件類型",
            "嚴重程度",
            "人物 ID",
            "區域",
        ]

        display_columns = [
            column
            for column in display_columns
            if column in event_df.columns
        ]

        st.dataframe(
            event_df[display_columns],
            use_container_width=True,
            hide_index=True,
            height=350,
        )

    else:

        st.success(
            "目前沒有事件紀錄 👍"
        )


    # ========================================================
    # 更新資訊
    # ========================================================

    st.divider()

    st.caption(
        "🔄 Dashboard 每 2 秒自動更新｜"
        "資料來源：Supabase｜"
        "時間：Asia/Taipei"
    )


# ============================================================
# 啟動 Dashboard
# ============================================================

dashboard()
